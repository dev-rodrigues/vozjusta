#!/usr/bin/env python3
"""Synthetic Prometheus exporter for local/demo business simulation.

This exporter emits the same VozJusta business metric names with synthetic,
time-varying values so dashboards can be stress-tested without relying on the
LLM path.
"""

from __future__ import annotations

import argparse
import random
import signal
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo

from prometheus_client import Counter, Gauge, Histogram, start_http_server


THEMES: tuple[str, ...] = (
    "assedio_moral",
    "discriminacao_racial",
    "discriminacao_genero",
    "igualdade_salarial",
    "direitos_trabalhistas",
    "denuncia_discriminacao",
    "outros",
)

OUTCOMES: tuple[str, ...] = ("answer", "fallback", "error")
CONFIDENCE_LEVELS: tuple[str, ...] = ("high", "medium", "low")
REASONS: tuple[str, ...] = (
    "sem_contexto",
    "contexto_insuficiente",
    "resposta_vazia_modelo",
    "runtime_error",
    "other",
)
INGESTION_STATUSES: tuple[str, ...] = ("success", "invalid_path", "failed", "other")
METHODS: tuple[str, ...] = ("source", "keyword", "default")
DISCLAIMERS: tuple[str, ...] = ("true", "false")

ASK_REQUEST_TOTAL = Counter(
    "vozjusta_ask_requests_total",
    "Total de perguntas processadas",
    ["result"],
)

ASK_FALLBACK_TOTAL = Counter(
    "vozjusta_ask_fallback_total",
    "Quantidade de respostas com fallback por baixa confianca",
)

ASK_LATENCY_SECONDS = Histogram(
    "vozjusta_ask_latency_seconds",
    "Latencia total do endpoint /api/v1/ask",
)

BUSINESS_QUESTIONS_TOTAL = Counter(
    "vozjusta_business_questions_total",
    "Volume de perguntas por tema, outcome e confianca",
    ["theme", "outcome", "confidence"],
)

BUSINESS_CANNOT_ANSWER_TOTAL = Counter(
    "vozjusta_business_cannot_answer_total",
    "Contagem de nao respostas por tema e motivo",
    ["theme", "reason"],
)

BUSINESS_SOURCES_PER_ANSWER = Histogram(
    "vozjusta_business_sources_per_answer",
    "Quantidade de fontes retornadas por resposta",
    buckets=(0, 1, 2, 3, 4, 6, 8, 10),
)

BUSINESS_DISCLAIMER_COMPLIANCE_TOTAL = Counter(
    "vozjusta_business_disclaimer_compliance_total",
    "Conformidade de disclaimer nas respostas",
    ["compliant"],
)

BUSINESS_THEME_DETECTION_TOTAL = Counter(
    "vozjusta_business_theme_detection_total",
    "Metodo de deteccao de tema",
    ["theme", "method"],
)

BUSINESS_INGESTION_RUNS_TOTAL = Counter(
    "vozjusta_business_ingestion_runs_total",
    "Total de execucoes de ingestao da base juridica",
    ["status"],
)

BUSINESS_KB_LAST_SUCCESS_UNIXTIME = Gauge(
    "vozjusta_business_kb_last_success_unixtime",
    "Timestamp unix da ultima ingestao bem-sucedida",
)

RUNNING = True


def _signal_handler(_sig: int, _frame) -> None:
    global RUNNING
    RUNNING = False


def weighted_choice(items: list[tuple[str, int]]) -> str:
    keys = [key for key, _ in items]
    weights = [weight for _, weight in items]
    return random.choices(keys, weights=weights, k=1)[0]


def preinitialize_metric_series() -> None:
    for result in OUTCOMES:
        ASK_REQUEST_TOTAL.labels(result=result)

    for theme in THEMES:
        for outcome in OUTCOMES:
            for confidence in CONFIDENCE_LEVELS:
                BUSINESS_QUESTIONS_TOTAL.labels(
                    theme=theme,
                    outcome=outcome,
                    confidence=confidence,
                )

    for theme in THEMES:
        for reason in REASONS:
            BUSINESS_CANNOT_ANSWER_TOTAL.labels(theme=theme, reason=reason)

    for compliant in DISCLAIMERS:
        BUSINESS_DISCLAIMER_COMPLIANCE_TOTAL.labels(compliant=compliant)

    for theme in THEMES:
        for method in METHODS:
            BUSINESS_THEME_DETECTION_TOTAL.labels(theme=theme, method=method)

    for status in INGESTION_STATUSES:
        BUSINESS_INGESTION_RUNS_TOTAL.labels(status=status)


@dataclass(frozen=True)
class TrafficProfile:
    min_requests: int
    max_requests: int
    burst_probability: float


def get_profile(now: datetime) -> TrafficProfile:
    hour = now.hour
    weekday = now.isoweekday()

    is_peak = (9 <= hour <= 12) or (14 <= hour <= 18)
    is_night = hour < 7 or hour >= 22
    is_weekend = weekday >= 6

    if is_peak and not is_weekend:
        return TrafficProfile(min_requests=3, max_requests=8, burst_probability=0.28)
    if is_night:
        return TrafficProfile(min_requests=0, max_requests=2, burst_probability=0.08)
    if is_weekend:
        return TrafficProfile(min_requests=1, max_requests=4, burst_probability=0.14)
    return TrafficProfile(min_requests=2, max_requests=5, burst_probability=0.18)


def pick_theme(now: datetime) -> str:
    hour = now.hour
    weekday = now.isoweekday()

    night = hour < 7 or hour >= 22
    weekend = weekday >= 6

    if night:
        return weighted_choice(
            [
                ("denuncia_discriminacao", 18),
                ("assedio_moral", 18),
                ("discriminacao_racial", 16),
                ("discriminacao_genero", 16),
                ("direitos_trabalhistas", 14),
                ("igualdade_salarial", 10),
                ("outros", 8),
            ]
        )

    if weekend:
        return weighted_choice(
            [
                ("direitos_trabalhistas", 21),
                ("denuncia_discriminacao", 20),
                ("discriminacao_racial", 16),
                ("discriminacao_genero", 15),
                ("assedio_moral", 14),
                ("igualdade_salarial", 10),
                ("outros", 4),
            ]
        )

    return weighted_choice(
        [
            ("denuncia_discriminacao", 20),
            ("discriminacao_racial", 18),
            ("assedio_moral", 16),
            ("discriminacao_genero", 16),
            ("direitos_trabalhistas", 14),
            ("igualdade_salarial", 12),
            ("outros", 4),
        ]
    )


def pick_outcome(theme: str) -> str:
    if theme == "outros":
        return weighted_choice([("answer", 72), ("fallback", 22), ("error", 6)])
    if theme == "denuncia_discriminacao":
        return weighted_choice([("answer", 85), ("fallback", 11), ("error", 4)])
    return weighted_choice([("answer", 89), ("fallback", 8), ("error", 3)])


def pick_confidence(outcome: str) -> str:
    if outcome == "error":
        return "low"
    if outcome == "fallback":
        return weighted_choice([("low", 86), ("medium", 14)])
    return weighted_choice([("high", 34), ("medium", 50), ("low", 16)])


def pick_reason(outcome: str) -> str | None:
    if outcome == "fallback":
        return weighted_choice(
            [
                ("sem_contexto", 46),
                ("contexto_insuficiente", 34),
                ("resposta_vazia_modelo", 12),
                ("other", 8),
            ]
        )
    if outcome == "error":
        return weighted_choice([("runtime_error", 74), ("other", 26)])
    return None


def pick_theme_detection_method(theme: str) -> str:
    if theme == "outros":
        return weighted_choice([("source", 14), ("keyword", 28), ("default", 58)])
    return weighted_choice([("source", 72), ("keyword", 23), ("default", 5)])


def pick_sources_count(outcome: str) -> int:
    if outcome == "answer":
        return int(weighted_choice([("1", 20), ("2", 35), ("3", 28), ("4", 12), ("5", 5)]))
    if outcome == "fallback":
        return int(weighted_choice([("0", 46), ("1", 39), ("2", 15)]))
    return 0


def pick_latency(outcome: str) -> float:
    if outcome == "error":
        return random.uniform(0.4, 4.5)
    if outcome == "fallback":
        return random.uniform(0.8, 9.0)
    return random.uniform(0.6, 14.0)


def pick_disclaimer_compliant() -> str:
    return weighted_choice([("true", 96), ("false", 4)])


def maybe_record_ingestion_event(now_ts: float) -> None:
    roll = random.random()
    if roll < 0.010:
        BUSINESS_INGESTION_RUNS_TOTAL.labels(status="success").inc()
        BUSINESS_KB_LAST_SUCCESS_UNIXTIME.set(now_ts)
        return
    if roll < 0.014:
        BUSINESS_INGESTION_RUNS_TOTAL.labels(status="failed").inc()
        return
    if roll < 0.017:
        BUSINESS_INGESTION_RUNS_TOTAL.labels(status="invalid_path").inc()
        return
    if roll < 0.018:
        BUSINESS_INGESTION_RUNS_TOTAL.labels(status="other").inc()


def simulate_tick(tz: ZoneInfo) -> None:
    now = datetime.now(tz)
    now_ts = time.time()
    profile = get_profile(now)

    requests_count = random.randint(profile.min_requests, profile.max_requests)
    if random.random() < profile.burst_probability:
        requests_count += random.randint(2, 5)

    for _ in range(requests_count):
        theme = pick_theme(now)
        outcome = pick_outcome(theme)
        confidence = pick_confidence(outcome)
        reason = pick_reason(outcome)
        method = pick_theme_detection_method(theme)
        sources_count = pick_sources_count(outcome)
        latency = pick_latency(outcome)
        disclaimer_compliant = pick_disclaimer_compliant()

        ASK_REQUEST_TOTAL.labels(result=outcome).inc()
        ASK_LATENCY_SECONDS.observe(latency)

        if outcome == "fallback":
            ASK_FALLBACK_TOTAL.inc()

        BUSINESS_QUESTIONS_TOTAL.labels(
            theme=theme,
            outcome=outcome,
            confidence=confidence,
        ).inc()

        BUSINESS_THEME_DETECTION_TOTAL.labels(theme=theme, method=method).inc()
        BUSINESS_SOURCES_PER_ANSWER.observe(float(sources_count))
        BUSINESS_DISCLAIMER_COMPLIANCE_TOTAL.labels(compliant=disclaimer_compliant).inc()

        if reason:
            BUSINESS_CANNOT_ANSWER_TOTAL.labels(theme=theme, reason=reason).inc()

    maybe_record_ingestion_event(now_ts)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="VozJusta synthetic exporter for Prometheus/Grafana demo data."
    )
    parser.add_argument("--host", default="0.0.0.0", help="Host bind do exporter.")
    parser.add_argument("--port", type=int, default=9201, help="Porta do exporter.")
    parser.add_argument(
        "--interval-seconds",
        type=float,
        default=5.0,
        help="Intervalo de atualizacao das metricas sinteticas.",
    )
    parser.add_argument(
        "--timezone",
        default="America/Sao_Paulo",
        help="Timezone para simular padroes de horario.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    if args.interval_seconds <= 0:
        print("interval-seconds deve ser maior que zero.", file=sys.stderr)
        return 1

    try:
        tz = ZoneInfo(args.timezone)
    except Exception:
        print(f"Timezone invalida: {args.timezone}", file=sys.stderr)
        return 1

    random.seed()
    preinitialize_metric_series()

    # Start with a recent successful ingestion to avoid stale "epoch-like" freshness.
    BUSINESS_KB_LAST_SUCCESS_UNIXTIME.set(time.time() - random.uniform(1800, 36000))

    signal.signal(signal.SIGINT, _signal_handler)
    signal.signal(signal.SIGTERM, _signal_handler)

    start_http_server(port=args.port, addr=args.host)
    print(
        f"[synthetic-exporter] listening on http://{args.host}:{args.port}/metrics "
        f"(interval={args.interval_seconds}s, tz={args.timezone})"
    )

    while RUNNING:
        simulate_tick(tz)
        time.sleep(args.interval_seconds)

    print("[synthetic-exporter] stopped")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

