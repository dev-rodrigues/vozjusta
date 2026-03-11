#!/usr/bin/env python3
"""Backfill VozJusta business metrics into Prometheus TSDB using OpenMetrics blocks.

This script generates synthetic historical samples (past N hours) and imports
them into the running Prometheus container with `promtool tsdb create-blocks-from openmetrics`.
"""

from __future__ import annotations

import argparse
import random
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Iterable
from zoneinfo import ZoneInfo


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


def weighted_choice(items: list[tuple[str, int]]) -> str:
    labels = [label for label, _ in items]
    weights = [weight for _, weight in items]
    return random.choices(labels, weights=weights, k=1)[0]


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


def pick_sources_count(outcome: str) -> int:
    if outcome == "answer":
        return int(weighted_choice([("1", 20), ("2", 35), ("3", 28), ("4", 12), ("5", 5)]))
    if outcome == "fallback":
        return int(weighted_choice([("0", 46), ("1", 39), ("2", 15)]))
    return 0


def format_value(value: float) -> str:
    if float(value).is_integer():
        return str(int(value))
    return f"{value:.6f}".rstrip("0").rstrip(".")


def format_labels(labels: dict[str, str]) -> str:
    if not labels:
        return ""
    parts = [f'{name}="{labels[name]}"' for name in sorted(labels)]
    return "{" + ",".join(parts) + "}"


def sample_line(name: str, value: float, ts_seconds: int, labels: dict[str, str]) -> str:
    return f"{name}{format_labels(labels)} {format_value(value)} {ts_seconds}\n"


def iter_timestamps(start: datetime, end: datetime, step: timedelta) -> Iterable[datetime]:
    current = start
    while current <= end:
        yield current
        current += step


def generate_openmetrics_payload(
    *,
    hours: int,
    step_minutes: int,
    timezone: str,
    mode_label: str,
    seed: int | None,
) -> tuple[str, dict[str, str]]:
    if seed is not None:
        random.seed(seed)
    else:
        random.seed()

    tz = ZoneInfo(timezone)
    step = timedelta(minutes=step_minutes)
    end_dt = datetime.now(tz).replace(second=0, microsecond=0)
    start_dt = end_dt - timedelta(hours=hours)

    questions: dict[tuple[str, str, str], float] = {
        (theme, outcome, confidence): 0.0
        for theme in THEMES
        for outcome in OUTCOMES
        for confidence in CONFIDENCE_LEVELS
    }
    cannot_answer: dict[tuple[str, str], float] = {
        (theme, reason): 0.0
        for theme in THEMES
        for reason in REASONS
    }
    ingestion_runs: dict[str, float] = {status: 0.0 for status in INGESTION_STATUSES}
    sources_sum = 0.0
    sources_count = 0.0
    last_success_unixtime = start_dt.timestamp() - (3 * 3600)

    total_requests = 0
    answer_count = 0
    fallback_count = 0
    error_count = 0

    lines: list[str] = [
        "# HELP vozjusta_business_questions_total Volume de perguntas por tema, outcome e confianca.\n",
        "# TYPE vozjusta_business_questions_total counter\n",
        "# HELP vozjusta_business_cannot_answer_total Contagem de nao respostas por tema e motivo.\n",
        "# TYPE vozjusta_business_cannot_answer_total counter\n",
        "# HELP vozjusta_business_sources_per_answer_sum Soma acumulada de fontes por resposta.\n",
        "# TYPE vozjusta_business_sources_per_answer_sum counter\n",
        "# HELP vozjusta_business_sources_per_answer_count Contagem acumulada de respostas com fontes.\n",
        "# TYPE vozjusta_business_sources_per_answer_count counter\n",
        "# HELP vozjusta_business_ingestion_runs_total Total de execucoes de ingestao por status.\n",
        "# TYPE vozjusta_business_ingestion_runs_total counter\n",
        "# HELP vozjusta_business_kb_last_success_unixtime Timestamp unix da ultima ingestao bem-sucedida.\n",
        "# TYPE vozjusta_business_kb_last_success_unixtime gauge\n",
    ]

    for now in iter_timestamps(start_dt, end_dt, step):
        profile = get_profile(now)
        requests_count = random.randint(profile.min_requests, profile.max_requests)
        if random.random() < profile.burst_probability:
            requests_count += random.randint(2, 5)

        for _ in range(requests_count):
            theme = pick_theme(now)
            outcome = pick_outcome(theme)
            confidence = pick_confidence(outcome)
            reason = pick_reason(outcome)
            sources_for_answer = pick_sources_count(outcome)

            questions[(theme, outcome, confidence)] += 1.0
            sources_sum += float(sources_for_answer)
            sources_count += 1.0
            total_requests += 1

            if outcome == "answer":
                answer_count += 1
            elif outcome == "fallback":
                fallback_count += 1
            else:
                error_count += 1

            if reason is not None:
                cannot_answer[(theme, reason)] += 1.0

        roll = random.random()
        if roll < 0.010:
            ingestion_runs["success"] += 1.0
            last_success_unixtime = now.timestamp()
        elif roll < 0.014:
            ingestion_runs["failed"] += 1.0
        elif roll < 0.017:
            ingestion_runs["invalid_path"] += 1.0
        elif roll < 0.018:
            ingestion_runs["other"] += 1.0

        # Guarantee at least one successful ingestion roughly every 14h.
        if now.timestamp() - last_success_unixtime > 14 * 3600:
            ingestion_runs["success"] += 1.0
            last_success_unixtime = now.timestamp() - random.uniform(60, 600)

        ts_seconds = int(now.timestamp())
        mode_labels = {"mode": mode_label}

        for theme in THEMES:
            for outcome in OUTCOMES:
                for confidence in CONFIDENCE_LEVELS:
                    labels = {
                        "theme": theme,
                        "outcome": outcome,
                        "confidence": confidence,
                        **mode_labels,
                    }
                    lines.append(
                        sample_line(
                            "vozjusta_business_questions_total",
                            questions[(theme, outcome, confidence)],
                            ts_seconds,
                            labels,
                        )
                    )

        for theme in THEMES:
            for reason in REASONS:
                labels = {"theme": theme, "reason": reason, **mode_labels}
                lines.append(
                    sample_line(
                        "vozjusta_business_cannot_answer_total",
                        cannot_answer[(theme, reason)],
                        ts_seconds,
                        labels,
                    )
                )

        for status in INGESTION_STATUSES:
            labels = {"status": status, **mode_labels}
            lines.append(
                sample_line(
                    "vozjusta_business_ingestion_runs_total",
                    ingestion_runs[status],
                    ts_seconds,
                    labels,
                )
            )

        lines.append(
            sample_line(
                "vozjusta_business_sources_per_answer_sum",
                sources_sum,
                ts_seconds,
                mode_labels,
            )
        )
        lines.append(
            sample_line(
                "vozjusta_business_sources_per_answer_count",
                sources_count,
                ts_seconds,
                mode_labels,
            )
        )
        lines.append(
            sample_line(
                "vozjusta_business_kb_last_success_unixtime",
                last_success_unixtime,
                ts_seconds,
                mode_labels,
            )
        )

    lines.append("# EOF\n")

    summary = {
        "start": start_dt.isoformat(),
        "end": end_dt.isoformat(),
        "hours": str(hours),
        "step_minutes": str(step_minutes),
        "total_requests": str(total_requests),
        "answers": str(answer_count),
        "fallbacks": str(fallback_count),
        "errors": str(error_count),
        "ingestion_success": str(int(ingestion_runs["success"])),
        "ingestion_failed": str(int(ingestion_runs["failed"])),
        "ingestion_invalid_path": str(int(ingestion_runs["invalid_path"])),
        "ingestion_other": str(int(ingestion_runs["other"])),
        "mode_label": mode_label,
    }
    return "".join(lines), summary


def run_checked(cmd: list[str], capture_output: bool = False) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        check=True,
        text=True,
        capture_output=capture_output,
    )


def apply_backfill(openmetrics_file: Path, container: str, restart_prometheus: bool) -> int:
    tmp_root = "/tmp/vozjusta-backfill"
    blocks_dir = f"{tmp_root}/blocks"
    input_path = f"{tmp_root}/input.openmetrics"

    run_checked(["docker", "exec", container, "sh", "-lc", f"rm -rf {tmp_root} && mkdir -p {blocks_dir}"])
    run_checked(["docker", "cp", str(openmetrics_file), f"{container}:{input_path}"])
    run_checked(
        [
            "docker",
            "exec",
            container,
            "promtool",
            "tsdb",
            "create-blocks-from",
            "openmetrics",
            "--quiet",
            input_path,
            blocks_dir,
        ]
    )
    block_count_output = run_checked(
        [
            "docker",
            "exec",
            container,
            "sh",
            "-lc",
            f"find {blocks_dir} -maxdepth 1 -mindepth 1 -type d | wc -l",
        ],
        capture_output=True,
    ).stdout.strip()
    block_count = int(block_count_output or "0")

    run_checked(
        [
            "docker",
            "exec",
            container,
            "sh",
            "-lc",
            f"for d in {blocks_dir}/*; do [ -d \"$d\" ] && cp -R \"$d\" /prometheus/; done",
        ]
    )

    if restart_prometheus:
        run_checked(["docker", "restart", container])

    return block_count


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Backfill historico de metricas de negocio VozJusta no Prometheus.",
    )
    parser.add_argument("--hours", type=int, default=90, help="Quantidade de horas para tras.")
    parser.add_argument(
        "--step-minutes",
        type=int,
        default=5,
        help="Resolucao temporal em minutos para gerar amostras.",
    )
    parser.add_argument(
        "--timezone",
        default="America/Sao_Paulo",
        help="Timezone para distribuicao organica de trafego.",
    )
    parser.add_argument(
        "--mode-label",
        default="synthetic_backfill",
        help="Valor do label mode para separar as series sintéticas.",
    )
    parser.add_argument("--seed", type=int, default=None, help="Seed opcional para reproducao.")
    parser.add_argument(
        "--output-file",
        default="logs/vozjusta_backfill_90h.openmetrics",
        help="Arquivo OpenMetrics de saida.",
    )
    parser.add_argument(
        "--prometheus-container",
        default="vozjusta-prometheus",
        help="Nome do container Prometheus.",
    )
    parser.add_argument(
        "--no-apply",
        action="store_true",
        help="Somente gera arquivo OpenMetrics sem importar no TSDB.",
    )
    parser.add_argument(
        "--no-restart",
        action="store_true",
        help="Nao reinicia o Prometheus apos copiar os blocos.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    if args.hours <= 0:
        print("--hours deve ser > 0", file=sys.stderr)
        return 1
    if args.step_minutes <= 0:
        print("--step-minutes deve ser > 0", file=sys.stderr)
        return 1

    try:
        payload, summary = generate_openmetrics_payload(
            hours=args.hours,
            step_minutes=args.step_minutes,
            timezone=args.timezone,
            mode_label=args.mode_label,
            seed=args.seed,
        )
    except Exception as exc:
        print(f"Falha ao gerar payload OpenMetrics: {exc}", file=sys.stderr)
        return 1

    output_file = Path(args.output_file)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(payload, encoding="utf-8")

    print("Backfill OpenMetrics gerado com sucesso:")
    print(f"- arquivo: {output_file}")
    print(f"- periodo: {summary['start']} -> {summary['end']}")
    print(f"- requests: {summary['total_requests']} (answer={summary['answers']}, fallback={summary['fallbacks']}, error={summary['errors']})")
    print(
        "- ingestao: "
        f"success={summary['ingestion_success']}, "
        f"failed={summary['ingestion_failed']}, "
        f"invalid_path={summary['ingestion_invalid_path']}, "
        f"other={summary['ingestion_other']}"
    )

    if args.no_apply:
        print("Modo --no-apply: nenhum bloco foi importado no Prometheus.")
        return 0

    try:
        block_count = apply_backfill(
            openmetrics_file=output_file,
            container=args.prometheus_container,
            restart_prometheus=not args.no_restart,
        )
    except subprocess.CalledProcessError as exc:
        print("Falha ao importar blocos no Prometheus.", file=sys.stderr)
        print(f"Comando: {' '.join(exc.cmd)}", file=sys.stderr)
        if exc.stdout:
            print(exc.stdout, file=sys.stderr)
        if exc.stderr:
            print(exc.stderr, file=sys.stderr)
        return exc.returncode or 1

    print(f"Blocos TSDB importados: {block_count}")
    if args.no_restart:
        print("Prometheus nao foi reiniciado (--no-restart).")
    else:
        print("Prometheus reiniciado para carregar os blocos importados.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
