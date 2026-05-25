import httpx
import pytest

import agents.base as base_module
from agents.base import BaseAgent


class DummyNotesAgent(BaseAgent):
    async def execute(self):
        return None


class FakeAsyncClient:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = 0

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return None

    async def post(self, *args, **kwargs):
        response = self.responses[min(self.calls, len(self.responses) - 1)]
        self.calls += 1
        return response


@pytest.mark.asyncio
async def test_wafer_concurrency_text_waits_one_second_and_retries(monkeypatch):
    monkeypatch.setattr(base_module, "COMMENTARY_NOTES_LLM_BACKEND", "wafer")
    monkeypatch.setattr(base_module, "WAFER_MODEL", "wafer-model")
    monkeypatch.setattr(base_module, "WAFER_BASE_URL", "https://wafer.test")
    monkeypatch.setattr(base_module, "WAFER_API_KEY", "test-key")
    monkeypatch.setenv("LLM_MAX_RETRY_ATTEMPTS", "2")

    request = httpx.Request("POST", "https://wafer.test/v1/chat/completions")
    fake_client = FakeAsyncClient([
        httpx.Response(400, text="provider concurrency limit exceeded", request=request),
        httpx.Response(200, json={"choices": [{"message": {"content": "ok"}}]}, request=request),
    ])
    sleeps = []

    async def fake_sleep(seconds):
        sleeps.append(seconds)

    async def fake_audit(**kwargs):
        return None

    monkeypatch.setattr(base_module.httpx, "AsyncClient", lambda **kwargs: fake_client)
    monkeypatch.setattr(base_module.asyncio, "sleep", fake_sleep)
    monkeypatch.setattr(base_module, "audit_llm_call", fake_audit)

    agent = DummyNotesAgent(model_id="unused", agent_type="note_organizer")

    result = await agent.call_llm("hello")

    assert result == "ok"
    assert fake_client.calls == 2
    assert sleeps == [1.0]


@pytest.mark.asyncio
async def test_wafer_non_retryable_error_fails_without_retry(monkeypatch):
    monkeypatch.setattr(base_module, "COMMENTARY_NOTES_LLM_BACKEND", "wafer")
    monkeypatch.setattr(base_module, "WAFER_MODEL", "wafer-model")
    monkeypatch.setattr(base_module, "WAFER_BASE_URL", "https://wafer.test")
    monkeypatch.setattr(base_module, "WAFER_API_KEY", "test-key")
    monkeypatch.setenv("LLM_MAX_RETRY_ATTEMPTS", "3")

    request = httpx.Request("POST", "https://wafer.test/v1/chat/completions")
    fake_client = FakeAsyncClient([
        httpx.Response(400, text="invalid model", request=request),
    ])
    sleeps = []

    async def fake_sleep(seconds):
        sleeps.append(seconds)

    async def fake_audit(**kwargs):
        return None

    monkeypatch.setattr(base_module.httpx, "AsyncClient", lambda **kwargs: fake_client)
    monkeypatch.setattr(base_module.asyncio, "sleep", fake_sleep)
    monkeypatch.setattr(base_module, "audit_llm_call", fake_audit)

    agent = DummyNotesAgent(model_id="unused", agent_type="note_organizer")

    with pytest.raises(ValueError, match="invalid model"):
        await agent.call_llm("hello")

    assert fake_client.calls == 1
    assert sleeps == []
