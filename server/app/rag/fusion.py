from typing import Any


class ReciprocalRankFusion:
    def __init__(self, k: int = 60) -> None:
        self.k = k

    def fuse(
        self,
        retrieval_lists: dict[str, list[dict[str, Any]]],
        top_k: int = 15,
    ) -> list[dict[str, Any]]:
        """Combine multiple retrieval result lists (vector, bm25, graph) using Reciprocal Rank Fusion."""
        chunk_scores: dict[str, float] = {}
        chunk_map: dict[str, dict[str, Any]] = {}
        chunk_sources: dict[str, set[str]] = {}

        for source_name, results in retrieval_lists.items():
            for rank, item in enumerate(results):
                chunk_id = str(item["chunk_id"])
                # Compute RRF score contribution
                rrf_score = 1.0 / (self.k + (rank + 1))
                chunk_scores[chunk_id] = chunk_scores.get(chunk_id, 0.0) + rrf_score

                if chunk_id not in chunk_map:
                    chunk_map[chunk_id] = dict(item)
                    chunk_sources[chunk_id] = set()

                chunk_sources[chunk_id].add(source_name)

        # Build fused list
        fused_items: list[dict[str, Any]] = []
        for chunk_id, total_score in chunk_scores.items():
            item = chunk_map[chunk_id]
            item["rrf_score"] = total_score
            item["sources"] = list(chunk_sources[chunk_id])
            fused_items.append(item)

        # Sort descending by fused score
        fused_items.sort(key=lambda x: x["rrf_score"], reverse=True)
        return fused_items[:top_k]


rrf_fusion = ReciprocalRankFusion()
