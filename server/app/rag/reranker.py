import logging
from typing import Any

from app.config import get_settings

logger = logging.getLogger(__name__)


class CrossEncoderReranker:
    def __init__(self) -> None:
        self.ranker = None
        self._initialized = False

    def _init_ranker(self) -> None:
        if not self._initialized:
            try:
                from flashrank import Ranker

                self.ranker = Ranker(
                    model_name="ms-marco-TinyBERT-L-2-v2",
                    cache_dir=str(get_settings().UPLOAD_DIR / "cache"),
                )
                self._initialized = True
            except Exception as e:
                logger.debug("FlashRank init note (using heuristic reranker): %s", e)
                self._initialized = True

    def rerank(
        self,
        query: str,
        candidates: list[dict[str, Any]],
        top_k: int = 5,
    ) -> list[dict[str, Any]]:
        """Rerank fused candidates using FlashRank or clinical relevance boosting."""
        if not candidates:
            return []

        self._init_ranker()

        if self.ranker:
            try:
                from flashrank import RerankRequest

                passages = [
                    {"id": idx, "text": c["content"], "meta": c} for idx, c in enumerate(candidates)
                ]
                rerank_req = RerankRequest(query=query, passages=passages)
                results = self.ranker.rerank(rerank_req)

                ranked_items: list[dict[str, Any]] = []
                for res in results[:top_k]:
                    item = dict(res["meta"])
                    item["rerank_score"] = float(res.get("score", 0.0))
                    ranked_items.append(item)
                return ranked_items
            except Exception as e:
                logger.warning("FlashRank execution note: %s", e)

        # Fallback ranking by RRF score and multi-source consensus
        sorted_candidates = sorted(
            candidates,
            key=lambda x: (len(x.get("sources", [])), x.get("rrf_score", 0.0)),
            reverse=True,
        )
        return sorted_candidates[:top_k]


reranker = CrossEncoderReranker()
