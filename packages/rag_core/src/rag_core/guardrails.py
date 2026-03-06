"""Confidence and fallback decisions for RAG responses."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class GuardrailDecision:
    confidence: str
    fallback: bool
    reason: str | None


def decide_confidence(top_score: float) -> str:
    if top_score >= 0.78:
        return "high"
    if top_score >= 0.55:
        return "medium"
    return "low"


def should_fallback(top_score: float, minimum_score: float = 0.45) -> GuardrailDecision:
    confidence = decide_confidence(top_score)
    if top_score < minimum_score:
        return GuardrailDecision(
            confidence=confidence,
            fallback=True,
            reason="contexto_insuficiente",
        )
    return GuardrailDecision(confidence=confidence, fallback=False, reason=None)
