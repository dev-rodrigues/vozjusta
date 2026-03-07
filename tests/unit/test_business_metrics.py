from __future__ import annotations

from rag_core.prompts import DISCLAIMER_TEXT
from vozjusta_api.metrics import (
    BUSINESS_CANNOT_ANSWER_TOTAL,
    BUSINESS_DISCLAIMER_COMPLIANCE_TOTAL,
    BUSINESS_INGESTION_RUNS_TOTAL,
    BUSINESS_KB_LAST_SUCCESS_UNIXTIME,
    BUSINESS_QUESTIONS_TOTAL,
    BUSINESS_SOURCES_PER_ANSWER,
    BUSINESS_THEME_DETECTION_TOTAL,
    detect_theme,
    observe_business_ask,
    observe_business_ingestion_run,
)
from vozjusta_api.schemas import SourceItem


def _counter_value(counter, **labels: str) -> float:
    return counter.labels(**labels)._value.get()


def _histogram_count(histogram) -> float:
    for metric in histogram.collect():
        for sample in metric.samples:
            if sample.name == "vozjusta_business_sources_per_answer_count":
                return float(sample.value)
    raise AssertionError("Série _count de vozjusta_business_sources_per_answer não encontrada")


def test_detect_theme_prefers_source_over_question_keyword() -> None:
    question = "Como denunciar discriminação no trabalho?"
    sources = [
        SourceItem(
            title="Lei 7.716/1989 - crimes resultantes de preconceito de raça",
            source_url="https://www.planalto.gov.br/ccivil_03/leis/l7716.htm",
            authority="Legislação Federal",
            excerpt="Define crimes resultantes de preconceito de raça ou de cor.",
            legal_ref="Lei 7.716/1989",
        )
    ]

    theme, method = detect_theme(question, sources)

    assert theme == "discriminacao_racial"
    assert method == "source"


def test_detect_theme_by_keyword_when_source_is_generic() -> None:
    question = "Quais direitos trabalhistas me protegem contra abusos?"

    theme, method = detect_theme(question, [])

    assert theme == "direitos_trabalhistas"
    assert method == "keyword"


def test_detect_theme_defaults_to_outros() -> None:
    question = "Qual é o melhor horário para fazer entrevista de emprego?"

    theme, method = detect_theme(question, [])

    assert theme == "outros"
    assert method == "default"


def test_observe_business_ask_updates_metrics() -> None:
    question = "Quais direitos trabalhistas tenho em caso de assédio?"
    sources = [
        SourceItem(
            title="Direitos trabalhistas e proteção no emprego",
            source_url="https://www.gov.br/trabalho",
            authority="Ministério do Trabalho",
            excerpt="A legislação trabalhista protege o trabalhador.",
            legal_ref="CLT",
        )
    ]

    before_questions = _counter_value(
        BUSINESS_QUESTIONS_TOTAL,
        theme="direitos_trabalhistas",
        outcome="answer",
        confidence="medium",
    )
    before_detection = _counter_value(
        BUSINESS_THEME_DETECTION_TOTAL,
        theme="direitos_trabalhistas",
        method="source",
    )
    before_disclaimer = _counter_value(
        BUSINESS_DISCLAIMER_COMPLIANCE_TOTAL,
        compliant="true",
    )
    before_sources_count = _histogram_count(BUSINESS_SOURCES_PER_ANSWER)

    observe_business_ask(
        question=question,
        outcome="answer",
        confidence="medium",
        cannot_answer_reason=None,
        sources=sources,
        disclaimer=DISCLAIMER_TEXT,
    )

    assert (
        _counter_value(
            BUSINESS_QUESTIONS_TOTAL,
            theme="direitos_trabalhistas",
            outcome="answer",
            confidence="medium",
        )
        == before_questions + 1
    )
    assert (
        _counter_value(
            BUSINESS_THEME_DETECTION_TOTAL,
            theme="direitos_trabalhistas",
            method="source",
        )
        == before_detection + 1
    )
    assert (
        _counter_value(
            BUSINESS_DISCLAIMER_COMPLIANCE_TOTAL,
            compliant="true",
        )
        == before_disclaimer + 1
    )
    assert _histogram_count(BUSINESS_SOURCES_PER_ANSWER) == before_sources_count + 1


def test_observe_business_ask_fallback_tracks_reason_and_non_compliance() -> None:
    question = "Pergunta genérica sem base curada"

    before_questions = _counter_value(
        BUSINESS_QUESTIONS_TOTAL,
        theme="outros",
        outcome="fallback",
        confidence="low",
    )
    before_reason = _counter_value(
        BUSINESS_CANNOT_ANSWER_TOTAL,
        theme="outros",
        reason="sem_contexto",
    )
    before_detection = _counter_value(
        BUSINESS_THEME_DETECTION_TOTAL,
        theme="outros",
        method="default",
    )
    before_disclaimer = _counter_value(
        BUSINESS_DISCLAIMER_COMPLIANCE_TOTAL,
        compliant="false",
    )

    observe_business_ask(
        question=question,
        outcome="fallback",
        confidence="low",
        cannot_answer_reason="sem_contexto",
        sources=[],
        disclaimer="resposta informativa sem frase esperada",
    )

    assert (
        _counter_value(
            BUSINESS_QUESTIONS_TOTAL,
            theme="outros",
            outcome="fallback",
            confidence="low",
        )
        == before_questions + 1
    )
    assert (
        _counter_value(
            BUSINESS_CANNOT_ANSWER_TOTAL,
            theme="outros",
            reason="sem_contexto",
        )
        == before_reason + 1
    )
    assert (
        _counter_value(
            BUSINESS_THEME_DETECTION_TOTAL,
            theme="outros",
            method="default",
        )
        == before_detection + 1
    )
    assert (
        _counter_value(
            BUSINESS_DISCLAIMER_COMPLIANCE_TOTAL,
            compliant="false",
        )
        == before_disclaimer + 1
    )


def test_observe_business_ingestion_success_updates_counter_and_gauge() -> None:
    before_success = _counter_value(BUSINESS_INGESTION_RUNS_TOTAL, status="success")
    before_timestamp = BUSINESS_KB_LAST_SUCCESS_UNIXTIME._value.get()

    observe_business_ingestion_run("success")

    assert _counter_value(BUSINESS_INGESTION_RUNS_TOTAL, status="success") == before_success + 1
    assert BUSINESS_KB_LAST_SUCCESS_UNIXTIME._value.get() >= before_timestamp
