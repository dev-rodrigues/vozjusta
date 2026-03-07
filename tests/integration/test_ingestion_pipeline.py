from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import func, select, text

from legal_kb.db import get_engine, get_session_factory
from legal_kb.ingestion import run_ingestion
from legal_kb.models import Base, Chunk, Document, Source
from legal_kb.ollama import OllamaEmbeddingClient


TEST_DATABASE_URL = None


@pytest.mark.integration
def test_ingestion_persists_in_pgvector(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Nunca usar o banco principal da aplicação para teste destrutivo.
    from os import getenv

    test_database_url = getenv("VOZJUSTA_TEST_DATABASE_URL")
    if not test_database_url:
        pytest.skip("Defina VOZJUSTA_TEST_DATABASE_URL para rodar testes de integração com banco dedicado")

    if test_database_url == getenv("VOZJUSTA_DATABASE_URL"):
        pytest.skip("VOZJUSTA_TEST_DATABASE_URL não pode apontar para o mesmo banco da aplicação")

    engine = get_engine(test_database_url)

    try:
        with engine.begin() as conn:
            conn.execute(text("SELECT 1"))
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    except Exception:
        pytest.skip("PostgreSQL com pgvector não disponível para teste de integração")

    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)

    doc_path = tmp_path / "lei.md"
    manifest_path = tmp_path / "lei.manifest.json"

    doc_path.write_text("Texto de exemplo sobre discriminação no trabalho.", encoding="utf-8")
    manifest_path.write_text(
        """
        {
          "title": "Lei de Teste",
          "authority": "Planalto",
          "source_url": "https://www.planalto.gov.br/",
          "source_type": "lei",
          "legal_ref": "Lei Teste",
          "effective_date": "2020-01-01"
        }
        """,
        encoding="utf-8",
    )

    monkeypatch.setattr(
        OllamaEmbeddingClient,
        "embed",
        lambda self, text: [0.001] * 768,
    )

    result = run_ingestion(
        path=tmp_path,
        database_url=test_database_url,
        ollama_base_url="http://localhost:11434",
        embedding_model="nomic-embed-text",
    )

    assert result.status == "success"
    assert result.total_documents == 1
    assert result.total_chunks >= 1

    session_factory = get_session_factory(test_database_url)
    with session_factory() as session:
        total_sources = session.scalar(select(func.count()).select_from(Source))
        total_documents = session.scalar(select(func.count()).select_from(Document))
        total_chunks = session.scalar(select(func.count()).select_from(Chunk))

    assert (total_sources or 0) == 1
    assert (total_documents or 0) == 1
    assert (total_chunks or 0) >= 1
