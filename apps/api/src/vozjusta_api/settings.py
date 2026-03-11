from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


ROOT_DIR = Path(__file__).resolve().parents[4]
ENV_FILES = (ROOT_DIR / ".env", ROOT_DIR / ".env.example")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="VOZJUSTA_",
        extra="ignore",
        env_file=ENV_FILES,
        env_file_encoding="utf-8",
    )

    app_name: str = "VozJusta API"
    app_env: str = "development"
    app_log_level: str = "INFO"

    host: str = "0.0.0.0"
    port: int = 8000

    database_url: str = "postgresql+psycopg://vozjusta:vozjusta@localhost:5432/vozjusta"

    ollama_base_url: str = "http://localhost:11434"
    ollama_chat_model: str = "llama3.1:8b"
    ollama_embedding_model: str = "nomic-embed-text"
    ollama_timeout_seconds: int = 300
    ollama_num_predict: int = 96
    ollama_num_ctx: int = 1024
    ollama_keep_alive: str = "30m"

    admin_token: str = "trocar-token-admin"
    minimum_similarity_for_answer: float = 0.45
    rag_retrieve_top_k: int = 4
    rag_context_top_k: int = 1
    rag_context_excerpt_max_chars: int = 320
    ask_cache_ttl_seconds: int = 600
    ask_cache_max_items: int = 256
    cors_allowed_origins: str = "http://localhost:5173"

    @property
    def cors_allowed_origins_list(self) -> list[str]:
        parsed = [item.strip() for item in self.cors_allowed_origins.split(",") if item.strip()]
        return parsed or ["http://localhost:5173"]
