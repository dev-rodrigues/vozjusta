from __future__ import annotations

import logging

from fastapi.testclient import TestClient

import vozjusta_api.main as api_main
from legal_kb.models import Base
from rag_core.prompts import DISCLAIMER_TEXT
from vozjusta_api.schemas import AskResponse, SourceItem


class FakeSecurityService:
    def ask(self, question: str) -> AskResponse:
        return AskResponse(
            answer="Resposta segura [fonte:1]",
            sources=[
                SourceItem(
                    title="Fonte",
                    source_url="https://mpt.mp.br/",
                    authority="MPT",
                    excerpt="Trecho",
                    legal_ref="CLT",
                )
            ],
            disclaimer=DISCLAIMER_TEXT,
            confidence="medium",
            cannot_answer_reason=None,
        )

    def list_sources(self):
        return []

    def health(self):
        return {
            "status": "ok",
            "database": "up",
            "ollama": "up",
            "timestamp": "2026-03-10T00:00:00Z",
        }

    def run_admin_ingestion(self, path: str):
        raise NotImplementedError


def test_no_conversation_history_tables() -> None:
    table_names = set(Base.metadata.tables.keys())
    assert "conversation_history" not in table_names
    assert "messages" not in table_names


def test_question_text_not_written_to_logs(caplog) -> None:
    api_main.app.state.rag_service = FakeSecurityService()
    client = TestClient(api_main.app)

    secret_phrase = "DADO-SENSIVEL-QUE-NAO-DEVE-IR-PARA-LOG"

    with caplog.at_level(logging.INFO):
        response = client.post(
            "/api/v1/ask",
            json={"question": f"Minha pergunta {secret_phrase}"},
        )

    assert response.status_code == 200
    combined_logs = "\n".join(record.getMessage() for record in caplog.records)
    assert secret_phrase not in combined_logs
