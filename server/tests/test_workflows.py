import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from qdrant_client import AsyncQdrantClient
from sqlalchemy import select

from app.config import get_settings
from app.db.models import Document, DocumentChunk, HealthcareAgent
from app.db.neo4j_client import neo4j_service
from app.db.qdrant_client import qdrant_service
from app.rag.embeddings import embedding_service
from app.rag.follow_up_generator import follow_up_generator
from app.rag.generator import rag_coordinator
from app.rag.reranker import reranker


@pytest.fixture
async def indexed_services(monkeypatch):
    client = AsyncQdrantClient(location=":memory:")
    monkeypatch.setattr(qdrant_service, "client", client)
    await qdrant_service.init_collection()
    monkeypatch.setattr(
        embedding_service, "get_embedding", AsyncMock(return_value=[1.0] + [0.0] * 767)
    )
    monkeypatch.setattr(neo4j_service, "add_entity_and_relations", AsyncMock())
    monkeypatch.setattr(neo4j_service, "delete_by_document", AsyncMock())
    monkeypatch.setattr(neo4j_service, "query_subgraph_for_entities", AsyncMock(return_value=[]))
    monkeypatch.setattr(reranker, "rerank", lambda query, candidates, top_k: candidates[:top_k])
    monkeypatch.setattr(follow_up_generator, "generate_suggestions", AsyncMock(return_value=[]))
    yield
    await client.close()


async def upload(api_client, db_session, text="Patient has hypertension and takes metoprolol."):
    agent = (
        await db_session.execute(
            select(HealthcareAgent).where(HealthcareAgent.domain_key == "cardiology")
        )
    ).scalar_one()
    response = await api_client.post(
        "/api/v1/documents/upload",
        data={"agent_id": str(agent.id)},
        files={"file": ("record.txt", text.encode(), "text/plain")},
    )
    return response, agent


async def test_upload_chat_history_and_delete(
    api_client, db_session, indexed_services, monkeypatch
):
    response, agent = await upload(api_client, db_session)
    assert response.status_code == 201
    doc_id = response.json()["document_id"]
    fake_client = MagicMock()

    async def stream(**kwargs):
        async def tokens():
            yield SimpleNamespace(text="Source-grounded response")

        return tokens()

    fake_client.aio.models.generate_content_stream = AsyncMock(side_effect=stream)
    monkeypatch.setattr(rag_coordinator, "api_key", "test-key")
    monkeypatch.setattr("google.genai.Client", lambda **kwargs: fake_client)
    payload = {
        "agent_id": str(agent.id),
        "document_ids": [doc_id],
        "message": "Explain hypertension",
    }
    first = await api_client.post("/api/v1/chat/stream", json=payload)
    assert "event: done" in first.text
    sessions = (await api_client.get("/api/v1/chat/sessions")).json()
    session_id = sessions[0]["id"]
    second = await api_client.post(
        "/api/v1/chat/stream",
        json={**payload, "session_id": session_id, "message": "What about its treatment?"},
    )
    assert "event: done" in second.text
    contents = fake_client.aio.models.generate_content_stream.call_args.kwargs["contents"]
    assert [c.role for c in contents] == ["user", "model", "user"]
    assert "Explain hypertension" in contents[0].parts[0].text
    messages = (await api_client.get(f"/api/v1/chat/sessions/{session_id}/messages")).json()
    assert messages[1]["citations"][0]["document_id"] == doc_id
    assert (await api_client.delete(f"/api/v1/documents/{doc_id}")).status_code == 204
    assert not (await api_client.get("/api/v1/documents")).json()
    assert not (await qdrant_service.client.scroll(collection_name=qdrant_service.collection_name))[
        0
    ]


async def test_ingestion_failure_is_retryable(
    api_client, db_session, indexed_services, monkeypatch
):
    monkeypatch.setattr(
        neo4j_service, "add_entity_and_relations", AsyncMock(side_effect=RuntimeError("graph down"))
    )
    response, _ = await upload(api_client, db_session)
    assert response.status_code == 503
    docs = (await api_client.get("/api/v1/documents")).json()
    assert docs[0]["status"] == "failed"
    assert not (await db_session.execute(select(DocumentChunk))).scalars().all()
    monkeypatch.setattr(neo4j_service, "add_entity_and_relations", AsyncMock())
    retry = await api_client.post(f"/api/v1/documents/{docs[0]['id']}/retry")
    assert retry.status_code == 200
    assert retry.json()["status"] == "completed"


async def test_failed_delete_is_hidden_and_retryable(
    api_client, db_session, indexed_services, monkeypatch
):
    response, agent = await upload(api_client, db_session)
    doc_id = response.json()["document_id"]
    original = qdrant_service.delete_by_document
    monkeypatch.setattr(
        qdrant_service, "delete_by_document", AsyncMock(side_effect=RuntimeError("down"))
    )
    assert (await api_client.delete(f"/api/v1/documents/{doc_id}")).status_code == 503
    assert (await api_client.get("/api/v1/documents")).json()[0]["status"] == "deleting"
    answer = await api_client.post(
        "/api/v1/chat/stream",
        json={"agent_id": str(agent.id), "message": "hypertension", "document_ids": []},
    )
    assert "insufficient" in answer.text or "sufficient clinical evidence" in answer.text
    monkeypatch.setattr(qdrant_service, "delete_by_document", original)
    assert (await api_client.delete(f"/api/v1/documents/{doc_id}")).status_code == 204


async def test_ownership_and_session_specialty(api_client, db_session, indexed_services):
    response, agent = await upload(api_client, db_session)
    doc_id = response.json()["document_id"]
    other = {"Authorization": "Bearer test-other-key"}
    assert not (await api_client.get("/api/v1/documents", headers=other)).json()
    assert (
        await api_client.get(f"/api/v1/documents/{doc_id}/chunks", headers=other)
    ).status_code == 404
    assert (
        await api_client.delete(f"/api/v1/documents/{doc_id}", headers=other)
    ).status_code == 404
    assert (
        await api_client.post(
            "/api/v1/chat/stream",
            json={"agent_id": str(agent.id), "message": "hypertension", "document_ids": [doc_id]},
            headers=other,
        )
    ).status_code == 404
    session = (
        await api_client.post("/api/v1/chat/sessions", json={"agent_id": str(agent.id)})
    ).json()["id"]
    assert (
        await api_client.get(f"/api/v1/chat/sessions/{session}/messages", headers=other)
    ).status_code == 404
    neuro = (
        await db_session.execute(
            select(HealthcareAgent).where(HealthcareAgent.domain_key == "neurology")
        )
    ).scalar_one()
    response = await api_client.post(
        "/api/v1/chat/stream",
        json={"session_id": session, "agent_id": str(neuro.id), "message": "stroke"},
    )
    assert response.status_code == 409


async def test_asset_is_private_and_removed_with_document(api_client, db_session, indexed_services):
    response, _ = await upload(api_client, db_session)
    doc_id = uuid.UUID(response.json()["document_id"])
    doc = await db_session.get(Document, doc_id)
    chunk = (
        await db_session.execute(select(DocumentChunk).where(DocumentChunk.document_id == doc_id))
    ).scalar_one()
    image = get_settings().UPLOAD_DIR / "documents" / str(doc_id) / "images" / "chart.png"
    image.parent.mkdir(parents=True)
    image.write_bytes(b"example image")
    chunk.metadata_json = {"image_path": str(image)}
    await db_session.commit()
    url = f"/api/v1/documents/{doc.id}/assets/chart.png"
    assert (await api_client.get(url)).status_code == 200
    assert (
        await api_client.get(url, headers={"Authorization": "Bearer test-other-key"})
    ).status_code == 404
    assert (await api_client.delete(f"/api/v1/documents/{doc_id}")).status_code == 204
    assert not image.exists()


async def test_audio_provider_failure_returns_no_text(api_client, monkeypatch):
    monkeypatch.setattr(get_settings(), "GROQ_API_KEY", "test")
    response = MagicMock()
    import httpx

    response.raise_for_status.side_effect = httpx.HTTPStatusError(
        "failed", request=MagicMock(), response=MagicMock()
    )
    fake = MagicMock()
    fake.__aenter__.return_value.post = AsyncMock(return_value=response)
    monkeypatch.setattr("app.api.v1.voice.httpx.AsyncClient", lambda **kwargs: fake)
    result = await api_client.post(
        "/api/v1/voice/transcribe", files={"file": ("audio.webm", b"invalid", "audio/webm")}
    )
    assert result.status_code == 502
    assert "text" not in result.json()
    assert (
        fake.__aenter__.return_value.post.call_args.kwargs["files"]["file"][0] == "recording.webm"
    )


async def test_upload_size_limit(api_client, db_session, monkeypatch):
    monkeypatch.setattr(get_settings(), "MAX_UPLOAD_BYTES", 2)
    response, _ = await upload(api_client, db_session)
    assert response.status_code == 413
    assert not (await db_session.execute(select(Document))).scalars().all()
