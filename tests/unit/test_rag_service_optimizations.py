from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from vozjusta_api.service import RagService, RetrievedContext
from vozjusta_api.settings import Settings


def _contexts(total: int = 4) -> list[RetrievedContext]:
    return [
        RetrievedContext(
            title=f"Fonte {idx}",
            source_url=f"https://exemplo{idx}.gov.br",
            authority="Autoridade",
            legal_ref="CLT",
            excerpt=f"Trecho {idx}",
            score=0.9 - (idx * 0.01),
        )
        for idx in range(total)
    ]


def test_ask_uses_cache_and_avoids_second_model_call(monkeypatch) -> None:
    settings = Settings(
        database_url="sqlite+pysqlite:///:memory:",
        rag_retrieve_top_k=8,
        rag_context_top_k=2,
        ask_cache_ttl_seconds=300,
        ask_cache_max_items=32,
    )
    service = RagService(settings)

    calls: dict[str, int] = {"embed": 0, "chat": 0}

    def _embed(text: str) -> list[float]:
        calls["embed"] += 1
        return [0.001] * 768

    def _chat(system_prompt: str, user_prompt: str) -> str:
        calls["chat"] += 1
        return "Resposta em cache [fonte:1]"

    monkeypatch.setattr(service.ollama, "embed", _embed)
    monkeypatch.setattr(service.ollama, "chat", _chat)
    monkeypatch.setattr(service, "_retrieve", lambda embedding, limit=8: _contexts(4))

    first = service.ask("Existe discriminação racial no trabalho?")
    second = service.ask("Existe discriminação racial no trabalho?")

    assert calls["embed"] == 1
    assert calls["chat"] == 1
    assert first.answer == second.answer
    assert len(first.sources) == 2


def test_ask_uses_configured_retrieve_and_context_top_k(monkeypatch) -> None:
    settings = Settings(
        database_url="sqlite+pysqlite:///:memory:",
        rag_retrieve_top_k=6,
        rag_context_top_k=2,
        ask_cache_ttl_seconds=0,
        ask_cache_max_items=0,
    )
    service = RagService(settings)

    seen: dict[str, Any] = {"limit": None}

    def _retrieve(embedding: list[float], limit: int = 8) -> list[RetrievedContext]:
        seen["limit"] = limit
        return _contexts(5)

    monkeypatch.setattr(service.ollama, "embed", lambda text: [0.001] * 768)
    monkeypatch.setattr(service.ollama, "chat", lambda system_prompt, user_prompt: "ok [fonte:1]")
    monkeypatch.setattr(service, "_retrieve", _retrieve)

    response = service.ask("Teste top k")
    assert seen["limit"] == 6
    assert len(response.sources) == 2


def test_get_last_successful_ingestion_unixtime_with_datetime() -> None:
    settings = Settings(database_url="sqlite+pysqlite:///:memory:")
    service = RagService(settings)

    expected = datetime(2026, 3, 10, 15, 0, tzinfo=UTC)

    class _Result:
        def scalar_one_or_none(self):
            return expected

    class _Session:
        def execute(self, _sql):
            return _Result()

    class _SessionContext:
        def __enter__(self):
            return _Session()

        def __exit__(self, exc_type, exc, tb):
            return False

    service.session_factory = lambda: _SessionContext()

    assert service.get_last_successful_ingestion_unixtime() == expected.timestamp()


def test_get_last_successful_ingestion_unixtime_with_invalid_value_returns_none() -> None:
    settings = Settings(database_url="sqlite+pysqlite:///:memory:")
    service = RagService(settings)

    class _Result:
        def scalar_one_or_none(self):
            return "invalid-date"

    class _Session:
        def execute(self, _sql):
            return _Result()

    class _SessionContext:
        def __enter__(self):
            return _Session()

        def __exit__(self, exc_type, exc, tb):
            return False

    service.session_factory = lambda: _SessionContext()

    assert service.get_last_successful_ingestion_unixtime() is None


def test_get_last_successful_ingestion_unixtime_handles_query_failure() -> None:
    settings = Settings(database_url="sqlite+pysqlite:///:memory:")
    service = RagService(settings)

    class _Session:
        def execute(self, _sql):
            raise RuntimeError("db indisponivel")

    class _SessionContext:
        def __enter__(self):
            return _Session()

        def __exit__(self, exc_type, exc, tb):
            return False

    service.session_factory = lambda: _SessionContext()

    assert service.get_last_successful_ingestion_unixtime() is None
