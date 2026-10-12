import pytest

from app.agents.registry import agent_registry
from app.rag.follow_up_generator import follow_up_generator
from app.rag.fusion import rrf_fusion
from app.rag.multi_doc_synthesizer import multi_doc_synthesizer


def test_domain_agent_registry():
    agents = agent_registry.list_agents()
    assert len(agents) >= 4

    cardio = agent_registry.get_agent("cardiology")
    assert cardio.domain_key == "cardiology"
    assert "Cardiology" in cardio.specialty

    context = cardio.build_system_context(
        retrieved_contexts=["Patient has Atrial Fibrillation."],
        graph_knowledge=[
            {
                "source": "atrial fibrillation",
                "source_type": "Disease",
                "relationship": "TREATS",
                "target": "metoprolol",
                "target_type": "Medication",
            }
        ],
    )
    assert "Dr. Cardio" in context
    assert "Strict Grounding" in context
    assert "Atrial Fibrillation" in context
    assert "metoprolol" in context


def test_reciprocal_rank_fusion():
    stream_vector = [
        {"chunk_id": "c1", "content": "Vector match 1"},
        {"chunk_id": "c2", "content": "Vector match 2"},
    ]
    stream_bm25 = [
        {"chunk_id": "c2", "content": "BM25 match 1"},
        {"chunk_id": "c3", "content": "BM25 match 2"},
    ]
    stream_graph = [
        {"chunk_id": "c2", "content": "Graph match 1"},
    ]

    streams = {
        "vector": stream_vector,
        "bm25": stream_bm25,
        "graph": stream_graph,
    }

    fused = rrf_fusion.fuse(streams, top_k=5)
    assert len(fused) == 3
    # c2 was present in all 3 streams, so it must have the highest RRF score
    assert fused[0]["chunk_id"] == "c2"
    assert set(fused[0]["sources"]) == {"vector", "bm25", "graph"}


def test_multi_document_synthesizer():
    chunks = [
        {"filename": "Discharge_Jan.pdf", "content": "Patient prescribed Metoprolol 25mg daily."},
        {
            "filename": "Clinic_Note_March.pdf",
            "content": "Dose adjusted to Metoprolol 100mg twice daily.",
        },
    ]
    analysis = multi_doc_synthesizer.analyze_cross_document_context(chunks)
    assert analysis["is_multi_doc"] is True
    assert analysis["document_count"] == 2
    assert len(analysis["contradictions"]) >= 1
    assert "Metoprolol" in analysis["contradictions"][0]["subject"]


@pytest.mark.asyncio
async def test_follow_up_question_generator():
    questions = await follow_up_generator.generate_suggestions(
        domain_specialty="Cardiology",
        user_query="What are the risks of Atrial Fibrillation?",
        assistant_response="Atrial Fibrillation increases the risk of stroke and heart failure.",
    )
    assert len(questions) == 3
    assert all(isinstance(q, str) and len(q) > 5 for q in questions)
