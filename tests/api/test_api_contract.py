from __future__ import annotations

from dataclasses import dataclass

from fastapi.testclient import TestClient

import vozjusta_api.main as api_main
from rag_core.prompts import DISCLAIMER_TEXT
from vozjusta_api.schemas import AskResponse, SourceItem


@dataclass
class DummyIngestResult:
    run_id: int = 10
    status: str = "success"
    total_documents: int = 2
    total_chunks: int = 6
    path: str = "/tmp/raw"


class FakeService:
    def ask(self, question: str) -> AskResponse:
        return AskResponse(
            answer=f"Resposta para: {question} [fonte:1]",
            sources=[
                SourceItem(
                    title="Cartilha MPT",
                    source_url="https://mpt.mp.br/",
                    authority="MPT",
                    excerpt="trecho",
                    legal_ref="CLT",
                )
            ],
            disclaimer=DISCLAIMER_TEXT,
            confidence="medium",
            cannot_answer_reason=None,
        )

    def list_sources(self):
        return [
            {
                "id": 1,
                "title": "Fonte",
                "authority": "MPT",
                "source_url": "https://mpt.mp.br/",
                "source_type": "cartilha",
                "legal_ref": "CLT",
                "effective_date": None,
            }
        ]

    def health(self):
        return {
            "status": "ok",
            "database": "up",
            "ollama": "up",
            "timestamp": "2026-03-10T00:00:00Z",
        }

    def run_admin_ingestion(self, path: str):
        return DummyIngestResult(path=path)


class FailingAskService(FakeService):
    def ask(self, question: str) -> AskResponse:
        raise RuntimeError('Modelo Ollama "nomic-embed-text" não encontrado.')


def _client():
    api_main.app.state.rag_service = FakeService()
    return TestClient(api_main.app)


def test_ask_contract():
    client = _client()
    response = client.post("/api/v1/ask", json={"question": "O que é assédio moral?"})
    assert response.status_code == 200
    body = response.json()
    assert set(body.keys()) == {
        "answer",
        "sources",
        "disclaimer",
        "confidence",
        "cannot_answer_reason",
    }


def test_sources_contract():
    client = _client()
    response = client.get("/api/v1/sources")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_health_contract():
    client = _client()
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json()["status"] in {"ok", "degraded"}


def test_admin_ingest_requires_token():
    client = _client()

    unauthorized = client.post("/api/v1/admin/ingest/run", json={"path": "knowledge_base/raw"})
    assert unauthorized.status_code == 401

    authorized = client.post(
        "/api/v1/admin/ingest/run",
        json={"path": "knowledge_base/raw"},
        headers={"X-Admin-Token": api_main.settings.admin_token},
    )
    assert authorized.status_code == 200


def test_ask_runtime_dependency_error_returns_503():
    api_main.app.state.rag_service = FailingAskService()
    client = TestClient(api_main.app)

    response = client.post("/api/v1/ask", json={"question": "Pergunta teste"})
    assert response.status_code == 503
    assert "Modelo Ollama" in response.json()["detail"]
