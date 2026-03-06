"""Ollama client dedicated to embedding generation."""

from __future__ import annotations

from typing import Any

import requests


class OllamaEmbeddingClient:
    def __init__(self, base_url: str, model: str, timeout_seconds: int = 60) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout_seconds = timeout_seconds

    @staticmethod
    def _extract_error_message(response: requests.Response) -> str:
        try:
            data = response.json()
            if isinstance(data, dict):
                error = data.get("error")
                if isinstance(error, str) and error.strip():
                    return error.strip()
        except ValueError:
            pass
        return response.text.strip() or f"HTTP {response.status_code}"

    def _raise_if_model_missing(self, response: requests.Response) -> None:
        message = self._extract_error_message(response).lower()
        if "model" in message and "not found" in message:
            raise RuntimeError(
                f'Modelo Ollama "{self.model}" não encontrado. '
                f'Baixe o modelo antes da ingestão com: '
                f'`docker exec vozjusta-ollama ollama pull {self.model}` '
                f'ou `ollama pull {self.model}`.'
            )

    def embed(self, text: str) -> list[float]:
        payload = {"model": self.model, "input": text}

        response = requests.post(
            f"{self.base_url}/api/embed",
            json=payload,
            timeout=self.timeout_seconds,
        )

        if response.status_code == 404:
            self._raise_if_model_missing(response)
            legacy_payload = {"model": self.model, "prompt": text}
            legacy_response = requests.post(
                f"{self.base_url}/api/embeddings",
                json=legacy_payload,
                timeout=self.timeout_seconds,
            )
            if legacy_response.status_code == 404:
                self._raise_if_model_missing(legacy_response)
            legacy_response.raise_for_status()
            data = legacy_response.json()
            embedding = data.get("embedding")
            if not isinstance(embedding, list):
                raise RuntimeError("Resposta inválida do endpoint /api/embeddings")
            return [float(value) for value in embedding]

        response.raise_for_status()
        data: dict[str, Any] = response.json()

        embeddings = data.get("embeddings")
        if isinstance(embeddings, list) and embeddings:
            first = embeddings[0]
            if isinstance(first, list):
                return [float(value) for value in first]

        single_embedding = data.get("embedding")
        if isinstance(single_embedding, list):
            return [float(value) for value in single_embedding]

        raise RuntimeError("Resposta inválida do endpoint /api/embed")

    def is_healthy(self) -> bool:
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=10)
            response.raise_for_status()
            return True
        except requests.RequestException:
            return False
