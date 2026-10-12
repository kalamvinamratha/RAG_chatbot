import re
from typing import Any

from rank_bm25 import BM25Plus
from sqlalchemy.ext.asyncio import AsyncSession

from app.rag.evidence import chunk_payload, scoped_chunks


class BM25Retriever:
    @staticmethod
    def _tokenize(text: str) -> list[str]:
        return re.findall(r"\b[a-zA-Z0-9_\-\./]+\b", text.lower())

    async def retrieve(
        self,
        query: str,
        db_session: AsyncSession,
        agent_id: str | None = None,
        document_ids: list[str] | None = None,
        limit: int = 15,
        owner_id: str | None = None,
    ) -> list[dict[str, Any]]:
        rows = await scoped_chunks(db_session, agent_id, document_ids, owner_id)
        query_tokens = self._tokenize(query)
        if not rows or not query_tokens:
            return []
        tokens = [self._tokenize(chunk.content) for chunk, _ in rows]
        if not any(tokens):
            return []
        scores = BM25Plus(tokens).get_scores(query_tokens)
        candidates = []
        for idx, (chunk, filename) in enumerate(rows):
            # Eligibility is a lexical match, not an arbitrary score threshold.
            if set(query_tokens).intersection(tokens[idx]):
                candidates.append(
                    {**chunk_payload(chunk, filename, "bm25"), "score": float(scores[idx])}
                )

        if not candidates and document_ids and rows:
            # If scoped to specific documents and no exact lexical match (e.g. summary or overview query),
            # provide scoped document chunks so evidence is preserved.
            for chunk, filename in rows[:limit]:
                candidates.append({**chunk_payload(chunk, filename, "bm25"), "score": 0.5})

        return sorted(candidates, key=lambda c: c["score"], reverse=True)[:limit]


bm25_retriever = BM25Retriever()
