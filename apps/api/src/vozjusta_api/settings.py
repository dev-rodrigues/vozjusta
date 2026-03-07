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
    ollama_num_predict: int = 220
    ollama_keep_alive: str = "30m"

    admin_token: str = "trocar-token-admin"
    minimum_similarity_for_answer: float = 0.45
    rag_retrieve_top_k: int = 8
    rag_context_top_k: int = 2
    ask_cache_ttl_seconds: int = 600
    ask_cache_max_items: int = 256
