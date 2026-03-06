from __future__ import annotations

from pathlib import Path

import typer
from pydantic_settings import BaseSettings, SettingsConfigDict

from legal_kb.ingestion import run_ingestion


ROOT_DIR = Path(__file__).resolve().parents[4]
ENV_FILES = (ROOT_DIR / ".env", ROOT_DIR / ".env.example")


class IngestSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="VOZJUSTA_",
        extra="ignore",
        env_file=ENV_FILES,
        env_file_encoding="utf-8",
    )

    database_url: str = "postgresql+psycopg://vozjusta:vozjusta@localhost:5432/vozjusta"
    ollama_base_url: str = "http://localhost:11434"
    embedding_model: str = "nomic-embed-text"


app = typer.Typer(no_args_is_help=True, help="CLI de ingestão da base jurídica VozJusta")


@app.callback()
def callback() -> None:
    """Comandos da CLI de ingestão."""


@app.command("run")
def run_command(
    path: str = typer.Option("knowledge_base/raw", help="Pasta com documentos curados"),
    chunk_size: int = typer.Option(900, help="Tamanho do chunk"),
    overlap: int = typer.Option(120, help="Overlap entre chunks"),
) -> None:
    settings = IngestSettings()
    result = run_ingestion(
        path=Path(path),
        database_url=settings.database_url,
        ollama_base_url=settings.ollama_base_url,
        embedding_model=settings.embedding_model,
        chunk_size=chunk_size,
        overlap=overlap,
    )
    typer.echo(
        "Ingestão concluída | "
        f"run_id={result.run_id} "
        f"status={result.status} "
        f"documents={result.total_documents} "
        f"chunks={result.total_chunks}"
    )


def main() -> None:
    app()
