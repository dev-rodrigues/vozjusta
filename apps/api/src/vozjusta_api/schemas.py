from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class AskRequest(BaseModel):
    question: str = Field(
        min_length=3,
        max_length=1800,
        description="Pergunta do usuário sobre discriminação, assédio ou direitos trabalhistas.",
        examples=["O que fazer se eu sofrer assédio moral no trabalho?"],
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "question": "Discriminação racial no trabalho é crime no Brasil?",
            }
        }
    }


class SourceItem(BaseModel):
    title: str
    source_url: str
    authority: str
    excerpt: str
    legal_ref: str


class AskResponse(BaseModel):
    answer: str = Field(description="Resposta do assistente em português brasileiro.")
    sources: list[SourceItem] = Field(
        description="Fontes usadas para fundamentar a resposta."
    )
    disclaimer: str = Field(description="Aviso de caráter informativo da resposta.")
    confidence: Literal["high", "medium", "low"] = Field(
        description="Nível de confiança da resposta com base no contexto recuperado."
    )
    cannot_answer_reason: str | None = Field(
        default=None,
        description="Razão técnica quando o sistema não tem base suficiente para responder.",
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "answer": (
                    "A discriminação racial no trabalho pode configurar crime e violação de direitos "
                    "fundamentais [fonte:1]."
                ),
                "sources": [
                    {
                        "title": "Discriminação racial no trabalho",
                        "source_url": "https://www.planalto.gov.br/ccivil_03/leis/l7716.htm",
                        "authority": "Legislação Federal",
                        "excerpt": "A Lei 7.716/1989 define crimes resultantes de preconceito...",
                        "legal_ref": "Lei 7.716/1989; Lei 12.288/2010",
                    }
                ],
                "disclaimer": "Resposta informativa, com base em fontes públicas. Não substitui orientação jurídica profissional.",
                "confidence": "high",
                "cannot_answer_reason": None,
            }
        }
    }


class IngestRunRequest(BaseModel):
    path: str = Field(
        default="knowledge_base/raw",
        description="Caminho da pasta com documentos curados para ingestão.",
        examples=["knowledge_base/raw"],
    )


class IngestRunResponse(BaseModel):
    run_id: int = Field(description="Identificador da execução de ingestão.")
    status: str = Field(description="Status final da execução.")
    total_documents: int = Field(description="Quantidade de documentos processados.")
    total_chunks: int = Field(description="Quantidade de chunks gerados.")
    path: str = Field(description="Pasta de origem utilizada na ingestão.")


class SourceView(BaseModel):
    id: int
    title: str
    authority: str
    source_url: str
    source_type: str
    legal_ref: str
    effective_date: str | None


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    database: Literal["up", "down"]
    ollama: Literal["up", "down"]
    timestamp: datetime
