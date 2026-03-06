"""Ingestion orchestration for curated legal documents."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from rag_core import chunk_text, clean_text

from .db import get_session_factory
from .loader import LoadedDocument, load_documents
from .models import Chunk, Document, IngestionRun, Source
from .ollama import OllamaEmbeddingClient


EMBEDDING_DIM = 768


@dataclass(frozen=True)
class IngestionSummary:
    run_id: int
    status: str
    total_documents: int
    total_chunks: int
    path: str


def _checksum(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _get_or_create_source(session: Session, doc: LoadedDocument) -> Source:
    source = session.scalar(select(Source).where(Source.source_url == str(doc.manifest.source_url)))
    if source:
        return source

    source = Source(
        title=doc.manifest.title,
        authority=doc.manifest.authority,
        source_url=str(doc.manifest.source_url),
        source_type=doc.manifest.source_type,
        legal_ref=doc.manifest.legal_ref,
        effective_date=doc.manifest.effective_date,
    )
    session.add(source)
    session.flush()
    return source


def _assert_embedding_size(embedding: list[float]) -> None:
    if len(embedding) != EMBEDDING_DIM:
        raise ValueError(
            f"Embedding inválido: esperado {EMBEDDING_DIM}, recebido {len(embedding)}."
        )


def _create_run(session: Session, path: str) -> IngestionRun:
    run = IngestionRun(
        path=path,
        status="running",
        total_documents=0,
        total_chunks=0,
    )
    session.add(run)
    session.commit()
    session.refresh(run)
    return run


def run_ingestion(
    path: str | Path,
    database_url: str,
    ollama_base_url: str,
    embedding_model: str,
    chunk_size: int = 900,
    overlap: int = 120,
) -> IngestionSummary:
    target_path = str(Path(path).resolve())
    documents = load_documents(target_path)

    session_factory = get_session_factory(database_url)
    embedding_client = OllamaEmbeddingClient(base_url=ollama_base_url, model=embedding_model)

    with session_factory() as session:
        run = _create_run(session, target_path)
        run_id = run.id

    total_documents = 0
    total_chunks = 0

    try:
        with session_factory() as session:
            run = session.get(IngestionRun, run_id)
            assert run is not None

            for loaded_doc in documents:
                normalized_text = clean_text(loaded_doc.text)
                checksum = _checksum(normalized_text)

                existing = session.scalar(select(Document).where(Document.checksum == checksum))
                if existing:
                    continue

                source = _get_or_create_source(session, loaded_doc)

                document = Document(
                    source_id=source.id,
                    filename=loaded_doc.file_path.name,
                    checksum=checksum,
                    raw_text=normalized_text,
                )
                session.add(document)
                session.flush()

                chunks = chunk_text(normalized_text, chunk_size=chunk_size, overlap=overlap)
                for idx, chunk in enumerate(chunks):
                    embedding = embedding_client.embed(chunk)
                    _assert_embedding_size(embedding)
                    session.add(
                        Chunk(
                            document_id=document.id,
                            source_id=source.id,
                            chunk_index=idx,
                            text=chunk,
                            legal_ref=source.legal_ref,
                            embedding=embedding,
                        )
                    )

                total_documents += 1
                total_chunks += len(chunks)

            run.status = "success"
            run.total_documents = total_documents
            run.total_chunks = total_chunks
            run.finished_at = datetime.now(UTC)
            session.commit()

    except Exception as exc:
        with session_factory() as session:
            run = session.get(IngestionRun, run_id)
            if run:
                run.status = "failed"
                run.error_message = str(exc)
                run.finished_at = datetime.now(UTC)
                session.commit()
        raise

    return IngestionSummary(
        run_id=run_id,
        status="success",
        total_documents=total_documents,
        total_chunks=total_chunks,
        path=target_path,
    )
