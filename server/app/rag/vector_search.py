import logging
from typing import Any

from app.db.qdrant_client import qdrant_service
from app.rag.embeddings import embedding_service

logger = logging.getLogger(__name__)


class VectorRetriever:
    async def retrieve(
        self,
        query: str,
        agent_id: str | None = None,
        document_ids: list[str] | None = None,
        limit: int = 15,
    ) -> list[dict[str, Any]]:
        """Retrieve candidate chunks from Qdrant using dense semantic vector search."""
        try:
            query_vector = await embedding_service.get_embedding(query)
            score_threshold = 0.0 if document_ids else 0.25
            points = await qdrant_service.search_dense(
                query_vector=query_vector,
                agent_id=agent_id,
                document_ids=document_ids,
                limit=limit,
                score_threshold=score_threshold,
            )
            results: list[dict[str, Any]] = []
            for p in points:
                payload = p.payload or {}
                results.append(
                    {
                        "chunk_id": payload.get("chunk_id", str(p.id)),
                        "document_id": payload.get("document_id"),
                        "filename": payload.get("filename", "Unknown Document"),
                        "page_number": payload.get("page_number"),
                        "content": payload.get("content", ""),
                        "chunk_type": payload.get("chunk_type", "text"),
                        "image_path": payload.get("image_path"),
                        "score": p.score,
                        "source": "vector",
                    }
                )
            return results
        except Exception as e:
            logger.warning("Vector retrieval note (is Qdrant running?): %s", e)
            return []


vector_retriever = VectorRetriever()
