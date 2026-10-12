import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.neo4j_client import neo4j_service
from app.ingestion.entity_extractor import medical_extractor
from app.rag.evidence import chunk_payload, scoped_chunks

logger = logging.getLogger(__name__)


class GraphRetriever:
    async def retrieve(
        self,
        query: str,
        db_session: AsyncSession,
        agent_id: str | None = None,
        limit: int = 15,
        document_ids: list[str] | None = None,
        owner_id: str | None = None,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        extraction = await medical_extractor.extract_from_chunk(query)
        names = [e.name for e in extraction.entities]
        rows = await scoped_chunks(db_session, agent_id, document_ids, owner_id)
        if not names or not rows:
            return [], []
        allowed = {str(chunk.id): (chunk, filename) for chunk, filename in rows}
        try:
            triples = await neo4j_service.query_subgraph_for_entities(
                entity_names=names,
                chunk_ids=list(allowed),
                limit=limit,
            )
        except Exception as exc:
            logger.warning("Graph retrieval unavailable: %s", exc)
            return [], []
        triples = [t for t in triples if t.get("chunk_id") in allowed]
        ids = list(dict.fromkeys(t["chunk_id"] for t in triples))
        candidates = [{**chunk_payload(*allowed[cid], "graph"), "score": 1.0} for cid in ids]
        return candidates, triples


graph_retriever = GraphRetriever()
