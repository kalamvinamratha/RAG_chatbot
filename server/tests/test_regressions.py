import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from google.genai.types import ContentEmbedding, EmbedContentResponse
from qdrant_client import AsyncQdrantClient, models
from sqlalchemy import select

from app.agents.registry import agent_registry
from app.config import get_settings
from app.db.models import Document, DocumentChunk, HealthcareAgent
from app.db.neo4j_client import Neo4jService, neo4j_service
from app.db.qdrant_client import QdrantService
from app.ingestion.chunkers.semantic_chunker import MedicalSemanticChunker
from app.ingestion.entity_extractor import MedicalEntityExtractor
from app.ingestion.models import ExtractedEntity, ExtractedRelationship, ParsedDocument, ParsedPage
from app.ingestion.parsers.factory import get_parser_for_file
from app.rag.bm25_search import BM25Retriever
from app.rag.embeddings import EmbeddingService
from app.rag.graph_search import GraphRetriever
from app.rag.multi_doc_synthesizer import MultiDocumentSynthesizer


async def add_document(db, text="hypertension", owner="admin", status="completed"):
    agent = (
        await db.execute(select(HealthcareAgent).where(HealthcareAgent.domain_key == "cardiology"))
    ).scalar_one()
    doc = Document(
        id=uuid.uuid4(),
        owner_id=owner,
        agent_id=agent.id,
        filename="note.txt",
        file_type="txt",
        storage_path=str(get_settings().UPLOAD_DIR / "note.txt"),
        status=status,
    )
    db.add(doc)
    await db.flush()
    chunk = DocumentChunk(document_id=doc.id, agent_id=agent.id, chunk_index=0, content=text)
    db.add(chunk)
    await db.commit()
    return doc, chunk


async def test_embedding_sdk_response_and_no_hash_fallback():
    service = EmbeddingService()
    service.openai_api_key = None
    service.api_key = "test-key"
    values = [0.5] * service.dimension
    fake = MagicMock()
    fake.aio.models.embed_content = AsyncMock(
        return_value=EmbedContentResponse(embeddings=[ContentEmbedding(values=values)])
    )
    with patch("google.genai.Client", return_value=fake):
        assert await service.get_embedding("hypertension") == values
        assert fake.aio.models.embed_content.call_args.kwargs["config"].output_dimensionality == 768
        fake.aio.models.embed_content.side_effect = RuntimeError("provider unavailable")
        with pytest.raises(RuntimeError):
            await service.get_embedding("hypertension")


async def test_openai_primary_embedding_and_fallback_to_gemini():
    """Verify OpenAI text-embedding-3-small is used as primary, and falls back to Gemini if OpenAI fails."""
    service = EmbeddingService()
    service.openai_api_key = "test-openai-key"
    service.api_key = "test-gemini-key"
    mock_values = [0.123] * service.dimension

    # 1. Primary OpenAI success
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"data": [{"embedding": mock_values}]}

    with patch(
        "httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_resp
    ) as mock_post:
        result = await service.get_embedding("atrial fibrillation")
        assert result == mock_values
        assert mock_post.await_count == 1
        call_json = mock_post.call_args.kwargs["json"]
        assert call_json["model"] == "text-embedding-3-small"
        assert call_json["dimensions"] == 768

    # 2. OpenAI failure falls back to Gemini
    mock_fail_resp = MagicMock()
    mock_fail_resp.status_code = 429
    mock_fail_resp.text = "Quota exceeded"

    fake_gemini = MagicMock()
    gemini_values = [0.999] * service.dimension
    fake_gemini.aio.models.embed_content = AsyncMock(
        return_value=EmbedContentResponse(embeddings=[ContentEmbedding(values=gemini_values)])
    )

    with (
        patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_fail_resp),
        patch("google.genai.Client", return_value=fake_gemini),
    ):
        result = await service.get_embedding("atrial fibrillation")
        assert result == gemini_values
        assert fake_gemini.aio.models.embed_content.await_count == 1


async def test_qdrant_real_client_contract():
    service = QdrantService()
    service.client = AsyncQdrantClient(location=":memory:")
    await service.init_collection(vector_size=3)
    point_id = str(uuid.uuid4())
    await service.upsert_chunks(
        [
            models.PointStruct(
                id=point_id,
                vector=[1.0, 0.0, 0.0],
                payload={"document_id": "a", "agent_id": "cardio"},
            )
        ]
    )
    assert len(await service.search_dense([1.0, 0.0, 0.0], "cardio", ["a"])) == 1
    assert await service.search_dense([1.0, 0.0, 0.0], "cardio", ["b"]) == []
    assert await service.search_dense([1.0, 0.0, 0.0], "cardio", []) == []
    await service.close()


async def test_bm25_small_corpus_and_scope(db_session):
    doc, _ = await add_document(db_session)
    retriever = BM25Retriever()
    results = await retriever.retrieve(
        "hypertension", db_session, str(doc.agent_id), [str(doc.id)], owner_id="admin"
    )
    assert len(results) == 1
    assert await retriever.retrieve("unrelated", db_session, owner_id="admin") == []
    assert await retriever.retrieve("hypertension", db_session, owner_id="other") == []
    doc.status = "deleting"
    await db_session.commit()
    assert await retriever.retrieve("hypertension", db_session, owner_id="admin") == []


async def test_bm25_does_not_truncate_at_500(db_session):
    doc, _ = await add_document(db_session, text="ordinary")
    db_session.add_all(
        [
            DocumentChunk(
                document_id=doc.id, agent_id=doc.agent_id, chunk_index=i + 1, content="ordinary"
            )
            for i in range(500)
        ]
    )
    db_session.add(
        DocumentChunk(
            document_id=doc.id, agent_id=doc.agent_id, chunk_index=501, content="rareterm"
        )
    )
    await db_session.commit()
    assert len(await BM25Retriever().retrieve("rareterm", db_session, owner_id="admin")) == 1


async def test_graph_filters_document_and_owner(db_session, monkeypatch):
    doc, chunk = await add_document(db_session)
    _, other_chunk = await add_document(db_session, owner="other")
    triples = [
        {"chunk_id": str(chunk.id), "source": "a", "target": "b", "relationship": "TREATS"},
        {"chunk_id": str(other_chunk.id)},
    ]
    query = AsyncMock(return_value=triples)
    monkeypatch.setattr(neo4j_service, "query_subgraph_for_entities", query)
    chunks, records = await GraphRetriever().retrieve(
        "hypertension", db_session, str(doc.agent_id), document_ids=[str(doc.id)], owner_id="admin"
    )
    assert len(chunks) == len(records) == 1
    assert query.call_args.kwargs["chunk_ids"] == [str(chunk.id)]


async def test_graph_query_preserves_direction_and_provenance():
    service = Neo4jService()
    session = MagicMock()
    session.run = AsyncMock(return_value=SimpleNamespace(data=AsyncMock(return_value=[])))
    driver = MagicMock()
    driver.session.return_value.__aenter__.return_value = session
    service.driver = driver
    await service.query_subgraph_for_entities(["hypertension"], ["chunk-1"])
    query, params = session.run.call_args.args
    assert "startNode(r).name AS source" in query
    assert "endNode(r).name AS target" in query
    assert "r.chunk_id = c.id" in query
    assert params["chunk_ids"] == ["chunk-1"]


def test_negation_does_not_create_relationships():
    result = MedicalEntityExtractor()._heuristic_extract(
        "Patient has hypertension. Metoprolol is NOT used to treat hypertension."
    )
    assert result.entities
    assert not result.relationships


@pytest.mark.parametrize(
    "factory,kwargs",
    [
        (ExtractedEntity, {"name": "a", "type": "Disease) DELETE"}),
        (ExtractedRelationship, {"source": "a", "target": "b", "type": "TREATS]->() DELETE"}),
    ],
)
def test_graph_type_allowlist(factory, kwargs):
    with pytest.raises(ValueError):
        factory(**kwargs)


def test_identical_doses_are_not_contradictions():
    chunks = [
        {"filename": "a.txt", "content": "Metoprolol 25 mg daily"},
        {"filename": "b.txt", "content": "Metoprolol 25.0mg once daily"},
    ]
    assert MultiDocumentSynthesizer().analyze_cross_document_context(chunks)["contradictions"] == []


def test_chunks_and_tables_obey_size_limit():
    document = ParsedDocument(
        "long.txt",
        "txt",
        1,
        [
            ParsedPage(
                1,
                "a" * 10000,
                ["| col |\n| --- |\n" + "\n".join("| " + "b" * 200 + " |" for _ in range(30))],
            )
        ],
    )
    chunks = MedicalSemanticChunker(500, 50).chunk_document(document)
    assert all(len(chunk.content) <= 500 for chunk in chunks)
    assert len(chunks) > 20


def test_csv_parser_and_unsupported_legacy(tmp_path):
    csv = tmp_path / "labs.csv"
    csv.write_text("test,value\nHbA1c,5.5\n")
    parsed = get_parser_for_file(csv).parse(csv)
    assert "HbA1c" in parsed.pages[0].tables[0]
    for ext in (".doc", ".xls", ".ppt"):
        with pytest.raises(ValueError):
            get_parser_for_file("old" + ext)


def test_custom_agent_uses_saved_prompt():
    record = SimpleNamespace(
        domain_key="oncology",
        name="Oncology",
        specialty="Oncology",
        description="Cancer care",
        system_prompt="Saved custom prompt",
        color="teal",
        icon="heart",
    )
    assert agent_registry.from_record(record).system_prompt == "Saved custom prompt"
