from rag_core.guardrails import decide_confidence, should_fallback


def test_decide_confidence_ranges() -> None:
    assert decide_confidence(0.8) == "high"
    assert decide_confidence(0.6) == "medium"
    assert decide_confidence(0.2) == "low"


def test_should_fallback_for_low_score() -> None:
    decision = should_fallback(top_score=0.3, minimum_score=0.45)
    assert decision.fallback is True
    assert decision.reason == "contexto_insuficiente"
