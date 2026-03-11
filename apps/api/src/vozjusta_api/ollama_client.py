from __future__ import annotations

from typing import Any

import requests


class OllamaClient:
    def __init__(
        self,
        base_url: str,
        chat_model: str,
        embedding_model: str,
        timeout_seconds: int = 90,
        num_predict: int = 220,
        num_ctx: int = 2048,
        keep_alive: str = "30m",
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.chat_model = chat_model
        self.embedding_model = embedding_model
        self.timeout_seconds = timeout_seconds
        self.num_predict = num_predict
        self.num_ctx = num_ctx
        self.keep_alive = keep_alive

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

    def _raise_model_missing(self, response: requests.Response, model: str) -> None:
        message = self._extract_error_message(response).lower()
        if "model" in message and "not found" in message:
            raise RuntimeError(
                f'Modelo Ollama "{model}" não encontrado. '
                f'Execute `docker exec vozjusta-ollama ollama pull {model}` '
                f'ou `ollama pull {model}`.'
            )

    def embed(self, text: str) -> list[float]:
        payload = {"model": self.embedding_model, "input": text}
        try:
            response = requests.post(
                f"{self.base_url}/api/embed",
                json=payload,
                timeout=self.timeout_seconds,
            )
        except requests.Timeout as exc:
            raise RuntimeError(
                f"Timeout ao chamar Ollama embeddings ({self.embedding_model}). "
                f"Aumente VOZJUSTA_OLLAMA_TIMEOUT_SECONDS ou use modelo menor."
            ) from exc
        except requests.RequestException as exc:
            raise RuntimeError(f"Falha de rede ao chamar Ollama embeddings: {exc}") from exc

        if response.status_code == 404:
            self._raise_model_missing(response, self.embedding_model)
            try:
                legacy = requests.post(
                    f"{self.base_url}/api/embeddings",
                    json={"model": self.embedding_model, "prompt": text},
                    timeout=self.timeout_seconds,
                )
            except requests.Timeout as exc:
                raise RuntimeError(
                    f"Timeout ao chamar Ollama embeddings ({self.embedding_model}). "
                    f"Aumente VOZJUSTA_OLLAMA_TIMEOUT_SECONDS ou use modelo menor."
                ) from exc
            except requests.RequestException as exc:
                raise RuntimeError(f"Falha de rede ao chamar Ollama embeddings: {exc}") from exc
            if legacy.status_code == 404:
                self._raise_model_missing(legacy, self.embedding_model)
            legacy.raise_for_status()
            legacy_data = legacy.json()
            legacy_embedding = legacy_data.get("embedding", [])
            return [float(value) for value in legacy_embedding]

        response.raise_for_status()
        data: dict[str, Any] = response.json()
        if isinstance(data.get("embeddings"), list) and data["embeddings"]:
            return [float(value) for value in data["embeddings"][0]]
        if isinstance(data.get("embedding"), list):
            return [float(value) for value in data["embedding"]]
        raise RuntimeError("Não foi possível obter embedding do Ollama")

    def chat(self, system_prompt: str, user_prompt: str) -> str:
        options: dict[str, Any] = {}
        if self.num_predict > 0:
            options["num_predict"] = self.num_predict
        if self.num_ctx > 0:
            options["num_ctx"] = self.num_ctx

        payload = {
            "model": self.chat_model,
            "stream": False,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "keep_alive": self.keep_alive,
        }
        if options:
            payload["options"] = options
        try:
            response = requests.post(
                f"{self.base_url}/api/chat",
                json=payload,
                timeout=self.timeout_seconds,
            )
        except requests.Timeout as exc:
            raise RuntimeError(
                f"Timeout ao chamar Ollama chat ({self.chat_model}). "
                f"Aumente VOZJUSTA_OLLAMA_TIMEOUT_SECONDS ou use modelo menor."
            ) from exc
        except requests.RequestException as exc:
            raise RuntimeError(f"Falha de rede ao chamar Ollama chat: {exc}") from exc
        if response.status_code == 404:
            self._raise_model_missing(response, self.chat_model)
        response.raise_for_status()
        data = response.json()
        message = data.get("message", {})
        content = message.get("content", "")
        if not isinstance(content, str):
            raise RuntimeError("Resposta inválida do endpoint /api/chat")
        return content.strip()

    def is_healthy(self) -> bool:
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=10)
            response.raise_for_status()
            return True
        except requests.RequestException:
            return False
