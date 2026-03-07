from __future__ import annotations

import time
import unicodedata
from collections.abc import Mapping, Sequence
from typing import Any

from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest
from starlette.responses import Response


THEMES: tuple[str, ...] = (
    "assedio_moral",
    "discriminacao_racial",
    "discriminacao_genero",
    "igualdade_salarial",
    "direitos_trabalhistas",
    "denuncia_discriminacao",
    "outros",
)

ASK_OUTCOMES = {"answer", "fallback", "error"}
CONFIDENCE_LEVELS = {"high", "medium", "low"}
CANNOT_ANSWER_REASONS = {
    "sem_contexto",
    "contexto_insuficiente",
    "resposta_vazia_modelo",
    "runtime_error",
    "other",
}
INGESTION_STATUSES = {"success", "invalid_path", "failed", "other"}

_THEME_KEYWORDS: dict[str, tuple[str, ...]] = {
    "denuncia_discriminacao": (
        "como denunciar",
        "fazer denuncia",
        "canal de denuncia",
        "registrar denuncia",
        "denuncia",
        "denunciar",
        "retaliacao",
        "mpt",
        "ouvidoria",
    ),
    "assedio_moral": (
        "assedio moral",
        "humilhacao",
        "constrangimento",
        "perseguicao",
        "abuso de autoridade",
    ),
    "discriminacao_racial": (
        "discriminacao racial",
        "racismo",
        "preconceito racial",
        "igualdade racial",
        "lei 7.716",
        "lei 7716",
        "estatuto da igualdade racial",
    ),
    "discriminacao_genero": (
        "discriminacao de genero",
        "identidade de genero",
        "sexismo",
        "maternidade",
        "gravidez",
        "lei 9.799",
    ),
    "igualdade_salarial": (
        "igualdade salarial",
        "equiparacao salarial",
        "salario igual",
        "transparencia remuneratoria",
        "transparencia salarial",
        "lei 14.611",
    ),
    "direitos_trabalhistas": (
        "direitos trabalhistas",
        "direito trabalhista",
        "justica do trabalho",
        "trabalhador",
        "empregador",
        "clt",
    ),
}

ASK_LATENCY_SECONDS = Histogram(
    "vozjusta_ask_latency_seconds",
    "Latencia total do endpoint /api/v1/ask",
)

ASK_FALLBACK_TOTAL = Counter(
    "vozjusta_ask_fallback_total",
    "Quantidade de respostas com fallback por baixa confianca",
)

ASK_REQUEST_TOTAL = Counter(
    "vozjusta_ask_requests_total",
    "Total de perguntas processadas",
    ["result"],
)

BUSINESS_QUESTIONS_TOTAL = Counter(
    "vozjusta_business_questions_total",
    "Volume de perguntas por tema, outcome e confianca",
    ["theme", "outcome", "confidence"],
)

BUSINESS_CANNOT_ANSWER_TOTAL = Counter(
    "vozjusta_business_cannot_answer_total",
    "Contagem de nao respostas por tema e motivo",
    ["theme", "reason"],
)

BUSINESS_SOURCES_PER_ANSWER = Histogram(
    "vozjusta_business_sources_per_answer",
    "Quantidade de fontes retornadas por resposta",
    buckets=(0, 1, 2, 3, 4, 6, 8, 10),
)

BUSINESS_DISCLAIMER_COMPLIANCE_TOTAL = Counter(
    "vozjusta_business_disclaimer_compliance_total",
    "Conformidade de disclaimer nas respostas",
    ["compliant"],
)

BUSINESS_THEME_DETECTION_TOTAL = Counter(
    "vozjusta_business_theme_detection_total",
    "Metodo de deteccao de tema",
    ["theme", "method"],
)

BUSINESS_INGESTION_RUNS_TOTAL = Counter(
    "vozjusta_business_ingestion_runs_total",
    "Total de execucoes de ingestao da base juridica",
    ["status"],
)

BUSINESS_KB_LAST_SUCCESS_UNIXTIME = Gauge(
    "vozjusta_business_kb_last_success_unixtime",
    "Timestamp unix da ultima ingestao bem-sucedida",
)


def _normalize_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value.lower())
    without_accents = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    return " ".join(without_accents.split())


def _sanitize_confidence(value: str) -> str:
    lowered = _normalize_text(value)
    return lowered if lowered in CONFIDENCE_LEVELS else "low"


def _sanitize_outcome(value: str) -> str:
    lowered = _normalize_text(value)
    return lowered if lowered in ASK_OUTCOMES else "error"


def _sanitize_reason(value: str) -> str:
    lowered = _normalize_text(value).replace(" ", "_")
    if lowered in CANNOT_ANSWER_REASONS:
        return lowered
    return "other"


def _sanitize_ingestion_status(value: str) -> str:
    lowered = _normalize_text(value).replace(" ", "_")
    if lowered in INGESTION_STATUSES:
        return lowered
    return "other"


def _detect_theme_from_text(text: str) -> str:
    normalized = _normalize_text(text)
    if not normalized:
        return "outros"

    for theme, keywords in _THEME_KEYWORDS.items():
        if any(keyword in normalized for keyword in keywords):
            return theme
    return "outros"


def _source_to_text(source: Any) -> str:
    keys = ["title", "legal_ref", "excerpt", "authority", "source_url"]
    values: list[str] = []

    if isinstance(source, Mapping):
        for key in keys:
            value = source.get(key)
            if isinstance(value, str) and value.strip():
                values.append(value)
        return " ".join(values)

    for key in keys:
        value = getattr(source, key, None)
        if isinstance(value, str) and value.strip():
            values.append(value)

    return " ".join(values)


def detect_theme(question: str, sources: Sequence[Any]) -> tuple[str, str]:
    source_blob = " ".join(_source_to_text(item) for item in sources)
    source_theme = _detect_theme_from_text(source_blob)
    if source_theme != "outros":
        return source_theme, "source"

    keyword_theme = _detect_theme_from_text(question)
    if keyword_theme != "outros":
        return keyword_theme, "keyword"

    return "outros", "default"


def _is_disclaimer_compliant(disclaimer: str) -> bool:
    normalized = _normalize_text(disclaimer)
    expected = _normalize_text("Nao substitui orientacao juridica profissional")
    return expected in normalized


def observe_business_ask(
    *,
    question: str,
    outcome: str,
    confidence: str,
    cannot_answer_reason: str | None,
    sources: Sequence[Any],
    disclaimer: str,
) -> None:
    theme, method = detect_theme(question, sources)
    BUSINESS_THEME_DETECTION_TOTAL.labels(theme=theme, method=method).inc()

    safe_outcome = _sanitize_outcome(outcome)
    safe_confidence = _sanitize_confidence(confidence)
    BUSINESS_QUESTIONS_TOTAL.labels(
        theme=theme,
        outcome=safe_outcome,
        confidence=safe_confidence,
    ).inc()

    BUSINESS_SOURCES_PER_ANSWER.observe(float(len(sources)))

    compliant = "true" if _is_disclaimer_compliant(disclaimer) else "false"
    BUSINESS_DISCLAIMER_COMPLIANCE_TOTAL.labels(compliant=compliant).inc()

    if cannot_answer_reason:
        BUSINESS_CANNOT_ANSWER_TOTAL.labels(
            theme=theme,
            reason=_sanitize_reason(cannot_answer_reason),
        ).inc()


def observe_business_ask_runtime_error(question: str) -> None:
    theme, method = detect_theme(question, [])
    BUSINESS_THEME_DETECTION_TOTAL.labels(theme=theme, method=method).inc()
    BUSINESS_QUESTIONS_TOTAL.labels(theme=theme, outcome="error", confidence="low").inc()
    BUSINESS_CANNOT_ANSWER_TOTAL.labels(theme=theme, reason="runtime_error").inc()
    BUSINESS_SOURCES_PER_ANSWER.observe(0.0)
    BUSINESS_DISCLAIMER_COMPLIANCE_TOTAL.labels(compliant="false").inc()


def observe_business_ingestion_run(status: str) -> None:
    safe_status = _sanitize_ingestion_status(status)
    BUSINESS_INGESTION_RUNS_TOTAL.labels(status=safe_status).inc()
    if safe_status == "success":
        BUSINESS_KB_LAST_SUCCESS_UNIXTIME.set(time.time())


def metrics_response() -> Response:
    data = generate_latest()
    return Response(content=data, media_type=CONTENT_TYPE_LATEST)
