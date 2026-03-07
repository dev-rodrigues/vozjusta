from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from threading import Lock
from time import monotonic

from sqlalchemy import text

from legal_kb.db import get_session_factory
from legal_kb.ingestion import IngestionSummary, run_ingestion
from legal_kb.models import Source
from rag_core import (
    DISCLAIMER_TEXT,
    build_system_prompt,
    build_user_prompt,
    should_fallback,
)

from .ollama_client import OllamaClient
from .schemas import AskResponse, SourceItem, SourceView
from .settings import Settings


@dataclass(frozen=True)
class RetrievedContext:
    title: str
    source_url: str
    authority: str
    legal_ref: str
    excerpt: str
    score: float


@dataclass
class CachedAskResult:
    response: AskResponse
    expires_at: float


class RagService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.session_factory = get_session_factory(settings.database_url)
        self.ollama = OllamaClient(
            base_url=settings.ollama_base_url,
            chat_model=settings.ollama_chat_model,
            embedding_model=settings.ollama_embedding_model,
            timeout_seconds=settings.ollama_timeout_seconds,
            num_predict=settings.ollama_num_predict,
            keep_alive=settings.ollama_keep_alive,
        )
        self._cache_lock = Lock()
        self._ask_cache: OrderedDict[str, CachedAskResult] = OrderedDict()

    @staticmethod
    def _vector_literal(values: list[float]) -> str:
        return "[" + ",".join(f"{value:.8f}" for value in values) + "]"

    def _retrieve(self, embedding: list[float], limit: int = 8) -> list[RetrievedContext]:
        sql = text(
            """
            SELECT
              s.title,
              s.source_url,
              s.authority,
              c.legal_ref,
              c.text AS excerpt,
              1 - (c.embedding <=> CAST(:embedding AS vector)) AS score
            FROM chunks c
            JOIN sources s ON s.id = c.source_id
            ORDER BY c.embedding <=> CAST(:embedding AS vector)
            LIMIT :limit;
            """
        )

        with self.session_factory() as session:
            rows = session.execute(
                sql,
                {
                    "embedding": self._vector_literal(embedding),
                    "limit": limit,
                },
            ).mappings()
            return [
                RetrievedContext(
                    title=row["title"],
                    source_url=row["source_url"],
                    authority=row["authority"],
                    legal_ref=row["legal_ref"],
                    excerpt=row["excerpt"],
                    score=float(row["score"]),
                )
                for row in rows
            ]

    @staticmethod
    def _normalize_question(question: str) -> str:
        return " ".join(question.strip().lower().split())

    def _evict_expired(self, now: float) -> None:
        stale_keys = [key for key, item in self._ask_cache.items() if item.expires_at <= now]
        for key in stale_keys:
            self._ask_cache.pop(key, None)

    def _get_cached_response(self, question_key: str) -> AskResponse | None:
        if self.settings.ask_cache_ttl_seconds <= 0 or self.settings.ask_cache_max_items <= 0:
            return None

        now = monotonic()
        with self._cache_lock:
            self._evict_expired(now)
            cached = self._ask_cache.get(question_key)
            if not cached:
                return None
            self._ask_cache.move_to_end(question_key)
            return cached.response.model_copy(deep=True)

    def _put_cached_response(self, question_key: str, response: AskResponse) -> None:
        if self.settings.ask_cache_ttl_seconds <= 0 or self.settings.ask_cache_max_items <= 0:
            return

        now = monotonic()
        expires_at = now + float(self.settings.ask_cache_ttl_seconds)
        with self._cache_lock:
            self._evict_expired(now)
            self._ask_cache[question_key] = CachedAskResult(
                response=response.model_copy(deep=True),
                expires_at=expires_at,
            )
            self._ask_cache.move_to_end(question_key)

            while len(self._ask_cache) > self.settings.ask_cache_max_items:
                self._ask_cache.popitem(last=False)

    def list_sources(self) -> list[SourceView]:
        with self.session_factory() as session:
            rows = session.query(Source).order_by(Source.title.asc()).all()
            return [
                SourceView(
                    id=row.id,
                    title=row.title,
                    authority=row.authority,
                    source_url=row.source_url,
                    source_type=row.source_type,
                    legal_ref=row.legal_ref,
                    effective_date=row.effective_date.isoformat() if row.effective_date else None,
                )
                for row in rows
            ]

    def health(self) -> dict:
        database_up = False
        with self.session_factory() as session:
            try:
                session.execute(text("SELECT 1"))
                database_up = True
            except Exception:
                database_up = False

        ollama_up = self.ollama.is_healthy()
        status = "ok" if database_up and ollama_up else "degraded"

        return {
            "status": status,
            "database": "up" if database_up else "down",
            "ollama": "up" if ollama_up else "down",
            "timestamp": datetime.now(UTC),
        }

    def run_admin_ingestion(self, path: str) -> IngestionSummary:
        return run_ingestion(
            path=Path(path),
            database_url=self.settings.database_url,
            ollama_base_url=self.settings.ollama_base_url,
            embedding_model=self.settings.ollama_embedding_model,
            chunk_size=900,
            overlap=120,
        )

    def _fallback_response(
        self,
        reason: str,
        contexts: list[RetrievedContext],
    ) -> AskResponse:
        top_sources = [
            SourceItem(
                title=item.title,
                source_url=item.source_url,
                authority=item.authority,
                excerpt=item.excerpt[:380],
                legal_ref=item.legal_ref,
            )
            for item in contexts[:2]
        ]

        answer = (
            "Não encontrei contexto jurídico suficiente para uma resposta confiável neste momento. "
            "Você pode procurar orientação em canais oficiais como MPT, sindicato da categoria, "
            "Ministério do Trabalho ou Defensoria Pública."
        )

        return AskResponse(
            answer=answer,
            sources=top_sources,
            disclaimer=DISCLAIMER_TEXT,
            confidence="low",
            cannot_answer_reason=reason,
        )

    def ask(self, question: str) -> AskResponse:
        question_key = self._normalize_question(question)
        cached_response = self._get_cached_response(question_key)
        if cached_response:
            return cached_response

        embedding = self.ollama.embed(question)
        context_top_k = max(1, self.settings.rag_context_top_k)
        retrieve_top_k = max(context_top_k, self.settings.rag_retrieve_top_k)
        contexts = self._retrieve(embedding, limit=retrieve_top_k)

        if not contexts:
            response = self._fallback_response(reason="sem_contexto", contexts=[])
            self._put_cached_response(question_key, response)
            return response

        decision = should_fallback(
            top_score=contexts[0].score,
            minimum_score=self.settings.minimum_similarity_for_answer,
        )

        if decision.fallback:
            response = self._fallback_response(reason=decision.reason or "fallback", contexts=contexts)
            self._put_cached_response(question_key, response)
            return response

        selected = contexts[:context_top_k]
        context_payload = [
            {
                "title": item.title,
                "authority": item.authority,
                "legal_ref": item.legal_ref,
                "excerpt": item.excerpt,
            }
            for item in selected
        ]

        answer = self.ollama.chat(
            system_prompt=build_system_prompt(),
            user_prompt=build_user_prompt(question, context_payload),
        )

        if not answer:
            response = self._fallback_response(reason="resposta_vazia_modelo", contexts=selected)
            self._put_cached_response(question_key, response)
            return response

        sources = [
            SourceItem(
                title=item.title,
                source_url=item.source_url,
                authority=item.authority,
                excerpt=item.excerpt[:380],
                legal_ref=item.legal_ref,
            )
            for item in selected
        ]

        response = AskResponse(
            answer=answer,
            sources=sources,
            disclaimer=DISCLAIMER_TEXT,
            confidence=decision.confidence,
            cannot_answer_reason=None,
        )
        self._put_cached_response(question_key, response)
        return response
