from __future__ import annotations

import requests

from vozjusta_api.ollama_client import OllamaClient


class DummyResponse:
    def __init__(self, payload: dict, status_code: int = 200) -> None:
        self._payload = payload
        self.status_code = status_code
        self.text = ""

    def json(self) -> dict:
        return self._payload

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}")


def test_embed_timeout_raises_runtime_error(monkeypatch) -> None:
    client = OllamaClient(
        base_url="http://localhost:11434",
        chat_model="llama3.1:8b",
        embedding_model="nomic-embed-text",
        timeout_seconds=1,
    )

    def _raise_timeout(*args, **kwargs):
        raise requests.Timeout("timeout")

    monkeypatch.setattr(requests, "post", _raise_timeout)

    try:
        client.embed("teste")
        raise AssertionError("Era esperado RuntimeError")
    except RuntimeError as exc:
        assert "Timeout" in str(exc)


def test_chat_sends_keep_alive_and_num_predict(monkeypatch) -> None:
    client = OllamaClient(
        base_url="http://localhost:11434",
        chat_model="llama3.1:8b",
        embedding_model="nomic-embed-text",
        timeout_seconds=1,
        num_predict=180,
        keep_alive="20m",
    )

    sent_payload = {}

    def _fake_post(url, json, timeout):  # noqa: ANN001
        sent_payload["url"] = url
        sent_payload["json"] = json
        sent_payload["timeout"] = timeout
        return DummyResponse({"message": {"content": "ok"}})

    monkeypatch.setattr(requests, "post", _fake_post)

    answer = client.chat(system_prompt="s", user_prompt="u")
    assert answer == "ok"
    assert sent_payload["url"].endswith("/api/chat")
    assert sent_payload["json"]["keep_alive"] == "20m"
    assert sent_payload["json"]["options"]["num_predict"] == 180


def test_chat_timeout_raises_runtime_error(monkeypatch) -> None:
    client = OllamaClient(
        base_url="http://localhost:11434",
        chat_model="llama3.1:8b",
        embedding_model="nomic-embed-text",
        timeout_seconds=1,
    )

    def _raise_timeout(*args, **kwargs):
        raise requests.Timeout("timeout")

    monkeypatch.setattr(requests, "post", _raise_timeout)

    try:
        client.chat(system_prompt="s", user_prompt="u")
        raise AssertionError("Era esperado RuntimeError")
    except RuntimeError as exc:
        assert "Timeout" in str(exc)
