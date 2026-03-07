from __future__ import annotations

from fastapi.testclient import TestClient

import vozjusta_api.main as api_main
from rag_core.prompts import DISCLAIMER_TEXT
from vozjusta_api.schemas import AskResponse, SourceItem


class FakeAcceptanceService:
    def ask(self, question: str) -> AskResponse:
        return AskResponse(
            answer=(
                "Com base nas fontes, há proteção legal contra discriminação e assédio "
                "no trabalho [fonte:1]."
            ),
            sources=[
                SourceItem(
                    title="Fonte oficial",
                    source_url="https://www.planalto.gov.br/",
                    authority="Legislação Federal",
                    excerpt="Trecho legal",
                    legal_ref="CLT",
                )
            ],
            disclaimer=DISCLAIMER_TEXT,
            confidence="high",
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


def test_questions_for_six_topics():
    api_main.app.state.rag_service = FakeAcceptanceService()
    client = TestClient(api_main.app)

    questions = [
        "O que é assédio moral no trabalho?",
        "Discriminação racial no trabalho é crime?",
        "Como reconhecer discriminação de gênero no emprego?",
        "Quais regras de igualdade salarial existem?",
        "Quais direitos trabalhistas me protegem?",
        "Como denunciar discriminação no trabalho?",
    ]

    for question in questions:
        response = client.post("/api/v1/ask", json={"question": question})
        assert response.status_code == 200
        payload = response.json()
        assert "não substitui" in payload["disclaimer"].lower()
        assert len(payload["sources"]) > 0
        assert payload["confidence"] in {"high", "medium", "low"}
