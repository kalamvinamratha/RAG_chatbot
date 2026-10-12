import logging
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.neo4j_client import neo4j_service
from app.db.postgres import get_db
from app.rag.evidence import scoped_chunks
from app.security import require_owner

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/graph", tags=["Knowledge Graph"])


@router.get("/subgraph")
async def get_subgraph(
    entity: str | None = None,
    agent_id: uuid.UUID | None = None,
    document_ids: list[uuid.UUID] | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    owner: str = Depends(require_owner),
) -> dict[str, Any]:
    rows = await scoped_chunks(
        db,
        str(agent_id) if agent_id else None,
        [str(d) for d in document_ids] if document_ids is not None else None,
        owner,
    )
    ids = [str(chunk.id) for chunk, _ in rows]
    try:
        records = await neo4j_service.query_subgraph_for_entities(
            [entity] if entity else [],
            chunk_ids=ids,
            limit=limit,
        )
    except Exception as exc:
        logger.warning("Graph unavailable: %s", exc)
        raise HTTPException(503, "Knowledge graph unavailable") from exc
    nodes, edges = {}, []
    for record in records:
        if record.get("chunk_id") not in ids:
            continue
        source, target = record.get("source"), record.get("target")
        if not source or not target:
            continue
        for key, kind in ((source, "source_type"), (target, "target_type")):
            nodes[key] = {"id": key, "label": key.title(), "type": record.get(kind, "Entity")}
        edges.append({"source": source, "target": target, "label": record["relationship"]})
    return {
        "nodes": list(nodes.values()),
        "edges": edges,
        "total_nodes": len(nodes),
        "total_edges": len(edges),
    }
