from __future__ import annotations

import sys

import requests
import typer


app = typer.Typer(no_args_is_help=True, help="Avaliação de aceitação do endpoint /api/v1/ask")

QUESTIONS = [
    "O que caracteriza assédio moral no trabalho?",
    "Discriminação racial no trabalho é crime no Brasil?",
    "Como denunciar discriminação de gênero no ambiente de trabalho?",
    "Quais são os direitos sobre igualdade salarial?",
    "Quais direitos trabalhistas me protegem contra humilhações repetidas?",
    "Quais canais oficiais posso usar para denunciar discriminação no trabalho?",
]


@app.callback()
def callback() -> None:
    """Comandos da CLI de avaliação."""


@app.command("run")
def run(base_url: str = typer.Option("http://localhost:8000", help="URL base da API")) -> None:
    failed = False

    for question in QUESTIONS:
        response = requests.post(
            f"{base_url.rstrip('/')}/api/v1/ask",
            json={"question": question},
            timeout=60,
        )

        if response.status_code != 200:
            typer.echo(f"[FAIL] status != 200 para pergunta: {question}")
            failed = True
            continue

        payload = response.json()
        answer = payload.get("answer", "")
        disclaimer = payload.get("disclaimer", "")
        confidence = payload.get("confidence", "low")
        sources = payload.get("sources", [])

        has_ptbr = any(ch in answer.lower() for ch in ["ção", "ã", "direito", "trabalho", "discriminação"])
        has_disclaimer = "não substitui" in disclaimer.lower()
        has_sources_when_confident = confidence == "low" or len(sources) > 0

        if not (has_ptbr and has_disclaimer and has_sources_when_confident):
            typer.echo(f"[FAIL] validação para pergunta: {question}")
            failed = True
        else:
            typer.echo(f"[OK] {question}")

    if failed:
        sys.exit(1)

    typer.echo("Avaliação concluída com sucesso.")


def main() -> None:
    app()
