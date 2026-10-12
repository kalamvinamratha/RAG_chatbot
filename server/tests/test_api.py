from unittest.mock import AsyncMock, MagicMock

from app.db.neo4j_client import neo4j_service
from app.db.qdrant_client import qdrant_service


async def test_health_reports_failure(api_client, monkeypatch):
    from app import main

    engine = MagicMock()
    engine.connect.side_effect = RuntimeError("db down")
    monkeypatch.setattr(main, "engine", engine)
    monkeypatch.setattr(
        qdrant_service, "connect", AsyncMock(side_effect=RuntimeError("qdrant down"))
    )
    monkeypatch.setattr(
        neo4j_service, "run_query", AsyncMock(side_effect=RuntimeError("neo4j down"))
    )
    response = await api_client.get("/health")
    assert response.status_code == 503
    assert response.json()["status"] == "unhealthy"


async def test_health_connected(api_client, monkeypatch, session_factory):
    from app import main
    from app.db import postgres

    monkeypatch.setattr(main, "engine", postgres.engine)
    monkeypatch.setattr(
        qdrant_service, "connect", AsyncMock(return_value=MagicMock(get_collections=AsyncMock()))
    )
    monkeypatch.setattr(neo4j_service, "run_query", AsyncMock(return_value=[]))
    response = await api_client.get("/health")
    assert response.status_code == 200
    assert response.json()["database"] == "connected"


async def test_list_agents_endpoint(api_client):
    response = await api_client.get("/api/v1/agents")
    assert response.status_code == 200
    assert len(response.json()) == 4


async def test_authentication_and_cookie(api_client):
    api_client.headers.pop("authorization")
    assert (await api_client.get("/api/v1/agents")).status_code == 401
    assert (
        await api_client.post("/api/v1/auth/session", json={"api_key": "wrong"})
    ).status_code == 401
    response = await api_client.post("/api/v1/auth/session", json={"api_key": "test-admin-key"})
    assert response.status_code == 200
    assert "HttpOnly" in response.headers["set-cookie"]
    assert (await api_client.get("/api/v1/agents")).status_code == 200
    assert (
        await api_client.post(
            "/api/v1/auth/session",
            json={"api_key": "test-admin-key"},
            headers={"Origin": "https://evil.example"},
        )
    ).status_code == 403


async def test_graph_empty_is_empty(api_client):
    response = await api_client.get("/api/v1/graph/subgraph")
    assert response.status_code == 200
    assert response.json()["nodes"] == []


async def test_voice_does_not_invent_text(api_client):
    response = await api_client.post(
        "/api/v1/voice/transcribe", files={"file": ("dictation.webm", b"invalid", "audio/webm")}
    )
    assert response.status_code == 503
    assert "text" not in response.json()


async def test_private_uploads_are_not_static(api_client):
    response = await api_client.get("/uploads/documents/patient.txt")
    assert response.status_code == 404


async def test_chat_session_lifecycle(api_client):
    agents_resp = await api_client.get("/api/v1/agents")
    agent_id = agents_resp.json()[0]["id"]

    # 1. Create a session
    resp = await api_client.post(
        "/api/v1/chat/sessions",
        json={"agent_id": agent_id, "title": "Test Consultation"},
    )
    assert resp.status_code == 201
    session_id = resp.json()["id"]

    # 2. List sessions
    list_resp = await api_client.get(f"/api/v1/chat/sessions?agent_id={agent_id}")
    assert list_resp.status_code == 200
    sessions = list_resp.json()
    assert any(s["id"] == session_id for s in sessions)

    # 3. Get messages for the session
    msgs_resp = await api_client.get(f"/api/v1/chat/sessions/{session_id}/messages")
    assert msgs_resp.status_code == 200
    assert msgs_resp.json() == []

    # 4. Delete session
    del_resp = await api_client.delete(f"/api/v1/chat/sessions/{session_id}")
    assert del_resp.status_code == 204

    # 5. Verify deleted
    list_after = await api_client.get(f"/api/v1/chat/sessions?agent_id={agent_id}")
    assert not any(s["id"] == session_id for s in list_after.json())
