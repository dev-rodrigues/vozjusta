from __future__ import annotations

import logging
import time
from contextlib import asynccontextmanager
from uuid import uuid4

import uvicorn
from fastapi import Depends, FastAPI, HTTPException, Request, Security
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import APIKeyHeader

from .logging_config import configure_logging, correlation_id_ctx
from .metrics import (
    ASK_FALLBACK_TOTAL,
    ASK_LATENCY_SECONDS,
    ASK_REQUEST_TOTAL,
    metrics_response,
    observe_business_ask,
    observe_business_ask_runtime_error,
    observe_business_ingestion_run,
    set_business_kb_last_success_unixtime,
)
from .schemas import (
    AskRequest,
    AskResponse,
    HealthResponse,
    IngestRunRequest,
    IngestRunResponse,
    SourceView,
)
from .service import RagService
from .settings import Settings


settings = Settings()
configure_logging(settings.app_log_level)
logger = logging.getLogger("vozjusta.api")

API_TAGS = [
    {
        "name": "Chat",
        "description": "Operações para perguntas jurídicas sobre discriminação e assédio no trabalho.",
    },
    {
        "name": "Knowledge Base",
        "description": "Consulta das fontes jurídicas atualmente disponíveis para o RAG.",
    },
    {
        "name": "Admin",
        "description": "Operações administrativas protegidas por token.",
    },
    {
        "name": "Observability",
        "description": "Saúde da aplicação e métricas para monitoramento.",
    },
]

admin_token_scheme = APIKeyHeader(
    name="X-Admin-Token",
    auto_error=False,
    description="Token administrativo exigido para endpoints de ingestão.",
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    rag_service = RagService(settings=settings)
    app.state.rag_service = rag_service
    set_business_kb_last_success_unixtime(
        rag_service.get_last_successful_ingestion_unixtime()
    )
    logger.info("api_initialized", extra={"event_env": settings.app_env})
    yield


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description=(
        "API RAG jurídico do VozJusta para orientação informativa sobre "
        "assédio moral, discriminação e direitos trabalhistas."
    ),
    docs_url="/swagger",
    redoc_url="/redoc",
    openapi_tags=API_TAGS,
    contact={"name": "Equipe VozJusta"},
    license_info={"name": "MIT"},
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allowed_origins_list,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def correlation_middleware(request: Request, call_next):
    correlation_id = request.headers.get("X-Correlation-Id", str(uuid4()))
    token = correlation_id_ctx.set(correlation_id)
    started = time.perf_counter()

    try:
        response = await call_next(request)
    finally:
        duration_ms = (time.perf_counter() - started) * 1000
        logger.info(
            "request_completed",
            extra={
                "event_method": request.method,
                "event_path": request.url.path,
                "event_duration_ms": round(duration_ms, 2),
            },
        )
        correlation_id_ctx.reset(token)

    response.headers["X-Correlation-Id"] = correlation_id
    return response


def _service(request: Request) -> RagService:
    if not hasattr(request.app.state, "rag_service"):
        request.app.state.rag_service = RagService(settings=settings)
    return request.app.state.rag_service


def require_admin_token(x_admin_token: str | None = Security(admin_token_scheme)) -> str:
    if x_admin_token != settings.admin_token:
        raise HTTPException(status_code=401, detail="Token administrativo inválido")
    return x_admin_token


@app.get(
    "/api/v1/health",
    response_model=HealthResponse,
    tags=["Observability"],
    summary="Health check da API",
    description="Retorna o estado atual da API, banco de dados e serviço Ollama.",
)
def health(request: Request) -> HealthResponse:
    return HealthResponse.model_validate(_service(request).health())


@app.get(
    "/api/v1/sources",
    response_model=list[SourceView],
    tags=["Knowledge Base"],
    summary="Listar fontes jurídicas",
    description="Lista fontes jurídicas ativas que sustentam as respostas do RAG.",
)
def list_sources(request: Request) -> list[SourceView]:
    return _service(request).list_sources()


@app.post(
    "/api/v1/ask",
    response_model=AskResponse,
    tags=["Chat"],
    summary="Perguntar ao assistente jurídico",
    description=(
        "Recebe uma pergunta em linguagem natural e retorna resposta em pt-BR "
        "com fontes, nível de confiança e disclaimer informativo."
    ),
)
def ask(request: Request, payload: AskRequest) -> AskResponse:
    try:
        with ASK_LATENCY_SECONDS.time():
            response = _service(request).ask(payload.question)
    except RuntimeError as exc:
        logger.error("ask_runtime_error", extra={"event_error": str(exc)})
        ASK_REQUEST_TOTAL.labels(result="error").inc()
        observe_business_ask_runtime_error(payload.question)
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    if response.cannot_answer_reason:
        ASK_FALLBACK_TOTAL.inc()
        ASK_REQUEST_TOTAL.labels(result="fallback").inc()
        outcome = "fallback"
    else:
        ASK_REQUEST_TOTAL.labels(result="answer").inc()
        outcome = "answer"

    observe_business_ask(
        question=payload.question,
        outcome=outcome,
        confidence=response.confidence,
        cannot_answer_reason=response.cannot_answer_reason,
        sources=response.sources,
        disclaimer=response.disclaimer,
    )

    return response


@app.post(
    "/api/v1/admin/ingest/run",
    response_model=IngestRunResponse,
    tags=["Admin"],
    summary="Executar ingestão da base jurídica",
    description=(
        "Dispara uma execução manual de ingestão da pasta curada. "
        "Endpoint protegido por `X-Admin-Token`."
    ),
)
def admin_ingest(
    request: Request,
    payload: IngestRunRequest,
    _: str = Depends(require_admin_token),
) -> IngestRunResponse:
    try:
        result = _service(request).run_admin_ingestion(path=payload.path)
    except FileNotFoundError as exc:
        observe_business_ingestion_run("invalid_path")
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        observe_business_ingestion_run("failed")
        logger.error("admin_ingest_runtime_error", extra={"event_error": str(exc)})
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    observe_business_ingestion_run(result.status)
    return IngestRunResponse(
        run_id=result.run_id,
        status=result.status,
        total_documents=result.total_documents,
        total_chunks=result.total_chunks,
        path=result.path,
    )


@app.get(
    "/metrics",
    tags=["Observability"],
    summary="Métricas Prometheus",
    description="Exposição de métricas técnicas e de negócio para monitoramento no Prometheus.",
)
def metrics():
    return metrics_response()


def run() -> None:
    uvicorn.run(
        "vozjusta_api.main:app",
        host=settings.host,
        port=settings.port,
        reload=False,
    )
