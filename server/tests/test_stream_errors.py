import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select

from app.db.models import HealthcareAgent
from app.rag.generator import rag_coordinator


async def test_stream_failure_is_an_explicit_event(api_client, db_session, monkeypatch):
    agent = (await db_session.execute(select(HealthcareAgent))).scalars().first()
    monkeypatch.setattr(
        rag_coordinator,
        "execute_tri_hybrid_retrieval",
        AsyncMock(side_effect=RuntimeError("store down")),
    )
    response = await api_client.post(
        "/api/v1/chat/stream", json={"agent_id": str(agent.id), "message": "query"}
    )
    assert "event: error" in response.text
    assert "event: done" not in response.text


@pytest.mark.parametrize("mode", ["quota", "daily", "partial", "empty", "recover"])
async def test_provider_stream_is_honest_and_retries_safely(
    api_client, db_session, monkeypatch, mode
):
    from google import genai

    agent = (await db_session.execute(select(HealthcareAgent))).scalars().first()
    monkeypatch.setattr(rag_coordinator, "openai_api_key", None)
    monkeypatch.setattr(rag_coordinator, "api_key", "fake-test-key")
    monkeypatch.setattr(rag_coordinator, "gemini_api_key", "fake-test-key")
    monkeypatch.setattr(rag_coordinator, "groq_api_key", None)
    monkeypatch.setattr(
        rag_coordinator,
        "execute_tri_hybrid_retrieval",
        AsyncMock(return_value=([{"filename": "synthetic.txt", "content": "LVEF 42 percent"}], [])),
    )
    calls = []
    sleep = AsyncMock()
    monkeypatch.setattr("app.rag.generator.asyncio.sleep", sleep)

    class QuotaError(Exception):
        code = 429
        details = {"error": {"details": [{"retryDelay": "42615s"}]}} if mode == "daily" else {}

    async def generate(**kwargs):
        calls.append(kwargs)
        if mode in {"quota", "daily"} or (mode == "recover" and len(calls) == 1):
            raise QuotaError("temporary quota")

        async def tokens():
            if mode == "empty":
                return
            yield SimpleNamespace(text="LVEF 42 percent [1]")
            if mode == "partial":
                raise QuotaError("interrupted")

        return tokens()

    monkeypatch.setattr(
        genai,
        "Client",
        lambda **_: SimpleNamespace(
            aio=SimpleNamespace(models=SimpleNamespace(generate_content_stream=generate))
        ),
    )
    response = await api_client.post(
        "/api/v1/chat/stream", json={"agent_id": str(agent.id), "message": "LVEF?"}
    )
    if mode == "recover":
        assert "event: done" in response.text
        assert "event: error" not in response.text
        assert len(calls) == 2
        assert sleep.await_count == 1
    else:
        assert "event: error" in response.text
        assert "event: done" not in response.text
        assert "Clinical Synthesis" not in response.text
        assert len(calls) == (3 if mode == "quota" else 1)
        assert sleep.await_count == (2 if mode == "quota" else 0)
    if mode == "partial":
        assert response.text.count("LVEF 42 percent [1]") == 1
    session_id = next(
        json.loads(line[6:])["session_id"]
        for line in response.text.splitlines()
        if line.startswith("data: ") and "session_id" in line
    )
    history = await api_client.get(f"/api/v1/chat/sessions/{session_id}/messages")
    assert [m["role"] for m in history.json()] == (
        ["user", "assistant"] if mode == "recover" else ["user"]
    )


async def test_gemini_quota_exhaustion_fails_over_to_groq(api_client, db_session, monkeypatch):
    """When Gemini hits quota limits, the coordinator must seamlessly fall back to Groq."""
    from google import genai

    agent = (await db_session.execute(select(HealthcareAgent))).scalars().first()
    monkeypatch.setattr(rag_coordinator, "openai_api_key", None)
    monkeypatch.setattr(rag_coordinator, "api_key", "fake-gemini-key")
    monkeypatch.setattr(rag_coordinator, "gemini_api_key", "fake-gemini-key")
    monkeypatch.setattr(rag_coordinator, "groq_api_key", "fake-groq-key")
    monkeypatch.setattr(
        rag_coordinator,
        "execute_tri_hybrid_retrieval",
        AsyncMock(return_value=([{"filename": "synthetic.txt", "content": "LVEF 42 percent"}], [])),
    )

    class QuotaError(Exception):
        code = 429
        details = {"error": {"details": [{"retryDelay": "42615s"}]}}

    async def failing_gemini_generate(**kwargs):
        raise QuotaError("Daily quota exhausted on Gemini")

    monkeypatch.setattr(
        genai,
        "Client",
        lambda **_: SimpleNamespace(
            aio=SimpleNamespace(
                models=SimpleNamespace(generate_content_stream=failing_gemini_generate)
            )
        ),
    )

    async def mock_groq_stream(query, system_context, history=None):
        yield "Grounded "
        yield "clinical guidance "
        yield "from Groq fallback model [1]."

    monkeypatch.setattr(rag_coordinator, "_stream_with_groq", mock_groq_stream)

    response = await api_client.post(
        "/api/v1/chat/stream", json={"agent_id": str(agent.id), "message": "What is the LVEF?"}
    )

    assert response.status_code == 200
    assert "event: token" in response.text
    assert "from Groq fallback model [1]" in response.text
    assert "event: done" in response.text
    assert "event: error" not in response.text

    session_id = next(
        json.loads(line[6:])["session_id"]
        for line in response.text.splitlines()
        if line.startswith("data: ") and "session_id" in line
    )
    history = await api_client.get(f"/api/v1/chat/sessions/{session_id}/messages")
    messages = history.json()
    assert len(messages) == 2
    assert messages[1]["role"] == "assistant"
    assert "from Groq fallback model [1]" in messages[1]["content"]


async def test_openai_primary_stream_and_failover_hierarchy(api_client, db_session, monkeypatch):
    """OpenAI is used first, and if unavailable/quota-exhausted, fails over to Groq then Gemini."""
    agent = (await db_session.execute(select(HealthcareAgent))).scalars().first()
    monkeypatch.setattr(rag_coordinator, "openai_api_key", "fake-openai-key")
    monkeypatch.setattr(rag_coordinator, "groq_api_key", "fake-groq-key")
    monkeypatch.setattr(rag_coordinator, "gemini_api_key", "fake-gemini-key")
    monkeypatch.setattr(
        rag_coordinator,
        "execute_tri_hybrid_retrieval",
        AsyncMock(
            return_value=([{"filename": "protocol.txt", "content": "Heparin 5000 units"}], [])
        ),
    )

    # 1. Success on OpenAI primary
    async def mock_openai_success(query, system_context, history=None):
        yield "Primary answer "
        yield "from OpenAI gpt-4o-mini [1]."

    monkeypatch.setattr(rag_coordinator, "_stream_with_openai", mock_openai_success)

    response = await api_client.post(
        "/api/v1/chat/stream", json={"agent_id": str(agent.id), "message": "Heparin dosage?"}
    )
    assert response.status_code == 200
    assert "from OpenAI gpt-4o-mini [1]" in response.text
    assert "event: done" in response.text

    # 2. When OpenAI fails, fail over to Groq
    async def mock_openai_failure(query, system_context, history=None):
        return
        yield ""

    async def mock_groq_fallback(query, system_context, history=None):
        yield "Failover answer "
        yield "from Groq model [1]."

    monkeypatch.setattr(rag_coordinator, "_stream_with_openai", mock_openai_failure)
    monkeypatch.setattr(rag_coordinator, "_stream_with_groq", mock_groq_fallback)

    response = await api_client.post(
        "/api/v1/chat/stream", json={"agent_id": str(agent.id), "message": "Heparin dosage?"}
    )
    assert response.status_code == 200
    assert "from Groq model [1]" in response.text
    assert "event: done" in response.text
