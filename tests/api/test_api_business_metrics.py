from __future__ import annotations

from dataclasses import dataclass

from fastapi.testclient import TestClient

import vozjusta_api.main as api_main
from rag_core.prompts import DISCLAIMER_TEXT
from vozjusta_api.metrics import (
    BUSINESS_CANNOT_ANSWER_TOTAL,
    BUSINESS_INGESTION_RUNS_TOTAL,
    BUSINESS_KB_LAST_SUCCESS_UNIXTIME,
    BUSINESS_QUESTIONS_TOTAL,
    BUSINESS_SOURCES_PER_ANSWER,
    BUSINESS_THEME_DETECTION_TOTAL,
)
from vozjusta_api.schemas import AskResponse, SourceItem


@dataclass
class DummyIngestResult:
    run_id: int = 44
    status: str = "success"
    total_documents: int = 3
    total_chunks: int = 12
    path: str = "knowledge_base/raw"


class FakeAnswerService:
    def ask(self, question: str) -> AskResponse:
        return AskResponse(
            answer="A discriminação racial no trabalho é vedada e pode configurar crime. [fonte:1]",
            sources=[
                SourceItem(
                    title="Lei 7.716/1989 - crimes resultantes de preconceito de raça",
                    source_url="https://www.planalto.gov.br/ccivil_03/leis/l7716.htm",
                    authority="Legislação Federal",
                    excerpt="Define os crimes resultantes de preconceito.",
                    legal_ref="Lei 7.716/1989",
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
        return DummyIngestResult(path=path)


class FakeFallbackService(FakeAnswerService):
    def ask(self, question: str) -> AskResponse:
        return AskResponse(
            answer="Não encontrei contexto suficiente para orientar com segurança.",
            sources=[],
            disclaimer=DISCLAIMER_TEXT,
            confidence="low",
            cannot_answer_reason="sem_contexto",
        )


class FakeIngestSuccessService(FakeAnswerService):
    pass


class FakeIngestInvalidPathService(FakeAnswerService):
    def run_admin_ingestion(self, path: str):
        raise FileNotFoundError("Pasta não encontrada")


def _counter_value(counter, **labels: str) -> float:
    return counter.labels(**labels)._value.get()


def _histogram_count(histogram) -> float:
    for metric in histogram.collect():
        for sample in metric.samples:
            if sample.name == "vozjusta_business_sources_per_answer_count":
                return float(sample.value)
    raise AssertionError("Série _count de vozjusta_business_sources_per_answer não encontrada")


def test_ask_updates_business_metrics_for_answer() -> None:
    api_main.app.state.rag_service = FakeAnswerService()
    client = TestClient(api_main.app)

    before_questions = _counter_value(
        BUSINESS_QUESTIONS_TOTAL,
        theme="discriminacao_racial",
        outcome="answer",
        confidence="high",
    )
    before_detection = _counter_value(
        BUSINESS_THEME_DETECTION_TOTAL,
        theme="discriminacao_racial",
        method="source",
    )
    before_sources_count = _histogram_count(BUSINESS_SOURCES_PER_ANSWER)

    response = client.post(
        "/api/v1/ask",
        json={"question": "Discriminação racial no trabalho é crime no Brasil?"},
    )

    assert response.status_code == 200
    assert (
        _counter_value(
            BUSINESS_QUESTIONS_TOTAL,
            theme="discriminacao_racial",
            outcome="answer",
            confidence="high",
        )
        == before_questions + 1
    )
    assert (
        _counter_value(
            BUSINESS_THEME_DETECTION_TOTAL,
            theme="discriminacao_racial",
            method="source",
        )
        == before_detection + 1
    )
    assert _histogram_count(BUSINESS_SOURCES_PER_ANSWER) == before_sources_count + 1


def test_ask_updates_business_metrics_for_fallback() -> None:
    api_main.app.state.rag_service = FakeFallbackService()
    client = TestClient(api_main.app)

    before_questions = _counter_value(
        BUSINESS_QUESTIONS_TOTAL,
        theme="denuncia_discriminacao",
        outcome="fallback",
        confidence="low",
    )
    before_detection = _counter_value(
        BUSINESS_THEME_DETECTION_TOTAL,
        theme="denuncia_discriminacao",
        method="keyword",
    )
    before_cannot_answer = _counter_value(
        BUSINESS_CANNOT_ANSWER_TOTAL,
        theme="denuncia_discriminacao",
        reason="sem_contexto",
    )

    response = client.post(
        "/api/v1/ask",
        json={"question": "Como denunciar discriminação no trabalho?"},
    )

    assert response.status_code == 200
    assert (
        _counter_value(
            BUSINESS_QUESTIONS_TOTAL,
            theme="denuncia_discriminacao",
            outcome="fallback",
            confidence="low",
        )
        == before_questions + 1
    )
    assert (
        _counter_value(
            BUSINESS_THEME_DETECTION_TOTAL,
            theme="denuncia_discriminacao",
            method="keyword",
        )
        == before_detection + 1
    )
    assert (
        _counter_value(
            BUSINESS_CANNOT_ANSWER_TOTAL,
            theme="denuncia_discriminacao",
            reason="sem_contexto",
        )
        == before_cannot_answer + 1
    )


def test_admin_ingest_updates_business_metrics_and_gauge() -> None:
    api_main.app.state.rag_service = FakeIngestSuccessService()
    client = TestClient(api_main.app)

    before_success = _counter_value(BUSINESS_INGESTION_RUNS_TOTAL, status="success")
    before_last_success = BUSINESS_KB_LAST_SUCCESS_UNIXTIME._value.get()

    response = client.post(
        "/api/v1/admin/ingest/run",
        json={"path": "knowledge_base/raw"},
        headers={"X-Admin-Token": api_main.settings.admin_token},
    )

    assert response.status_code == 200
    assert _counter_value(BUSINESS_INGESTION_RUNS_TOTAL, status="success") == before_success + 1
    assert BUSINESS_KB_LAST_SUCCESS_UNIXTIME._value.get() >= before_last_success


def test_admin_ingest_invalid_path_updates_metric() -> None:
    api_main.app.state.rag_service = FakeIngestInvalidPathService()
    client = TestClient(api_main.app)

    before_invalid_path = _counter_value(BUSINESS_INGESTION_RUNS_TOTAL, status="invalid_path")

    response = client.post(
        "/api/v1/admin/ingest/run",
        json={"path": "missing/path"},
        headers={"X-Admin-Token": api_main.settings.admin_token},
    )

    assert response.status_code == 400
    assert _counter_value(BUSINESS_INGESTION_RUNS_TOTAL, status="invalid_path") == before_invalid_path + 1
