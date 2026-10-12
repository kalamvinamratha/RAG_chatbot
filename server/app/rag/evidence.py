import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Document, DocumentChunk


def chunk_payload(chunk: DocumentChunk, filename: str, source: str) -> dict[str, Any]:
    return {
        "chunk_id": str(chunk.id),
        "document_id": str(chunk.document_id),
        "filename": filename,
        "page_number": chunk.page_number,
        "content": chunk.content,
        "chunk_type": chunk.chunk_type,
        "image_path": (chunk.metadata_json or {}).get("image_path"),
        "source": source,
    }


async def scoped_chunks(
    db: AsyncSession,
    agent_id: str | None,
    document_ids: list[str] | None,
    owner_id: str | None,
):
    stmt = (
        select(DocumentChunk, Document.filename)
        .join(Document)
        .where(Document.status == "completed")
    )
    if agent_id:
        stmt = stmt.where(Document.agent_id == uuid.UUID(agent_id))
    if owner_id:
        stmt = stmt.where(Document.owner_id == owner_id)
    if document_ids is not None:
        stmt = stmt.where(Document.id.in_([uuid.UUID(d) for d in document_ids]))
    return (await db.execute(stmt)).all()
