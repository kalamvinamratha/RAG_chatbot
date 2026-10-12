import asyncio
import logging
import shutil
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db.models import Document, DocumentChunk, HealthcareAgent
from app.db.neo4j_client import neo4j_service
from app.db.postgres import get_db
from app.db.qdrant_client import qdrant_service
from app.ingestion.pipeline import ingestion_pipeline
from app.schemas.document import DocumentChunkResponse, DocumentResponse, DocumentUploadResponse
from app.security import require_owner
from app.storage import managed_path, save_upload

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/documents", tags=["Documents"])
SUPPORTED = {".pdf", ".docx", ".xlsx", ".csv", ".pptx", ".txt", ".md"}


async def owned_document(db: AsyncSession, document_id: uuid.UUID, owner: str) -> Document:
    doc = await db.get(Document, document_id)
    if not doc or doc.owner_id != owner:
        raise HTTPException(404, "Document not found")
    return doc


async def ingest(doc: Document, db: AsyncSession) -> DocumentUploadResponse:
    doc_id, filename, agent_id, storage_path = doc.id, doc.filename, doc.agent_id, doc.storage_path
    try:
        result = await ingestion_pipeline.process_document(
            doc_id, agent_id, managed_path(storage_path), db
        )
    except Exception as exc:
        from app.rag.guardrails import DomainGuardrailException

        await db.rollback()
        doc = await db.get(Document, doc_id)
        if isinstance(exc, DomainGuardrailException):
            if doc:
                doc.status = "failed"
                doc.error_message = str(exc)
                await db.commit()
            logger.warning("Domain guardrail rejected document %s: %s", doc_id, exc)
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        if doc:
            doc.status = "failed"
            doc.error_message = "Indexing failed. Check server logs, then retry."
            await db.commit()
        logger.exception("Ingestion failed for document %s", doc_id)
        raise HTTPException(503, "Document indexing failed; retry after services recover") from exc
    return DocumentUploadResponse(
        document_id=doc_id,
        filename=filename,
        status="completed",
        message="Document indexed.",
        chunks_indexed=result["chunks_count"],
        entities_extracted=result["entities_count"],
        relations_extracted=result["relations_count"],
    )


@router.post("/upload", response_model=DocumentUploadResponse, status_code=201)
async def upload_document(
    agent_id: uuid.UUID = Form(...),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    owner: str = Depends(require_owner),
):
    agent = await db.get(HealthcareAgent, agent_id)
    if not agent or not agent.is_active:
        raise HTTPException(404, "Agent not found")
    filename = Path((file.filename or "document").replace("\\", "/")).name
    ext = Path(filename).suffix.lower()
    if ext not in SUPPORTED:
        raise HTTPException(400, "Supported formats: PDF, DOCX, XLSX, CSV, PPTX, TXT, MD")
    doc_id = uuid.uuid4()
    saved_path = get_settings().UPLOAD_DIR / "documents" / str(doc_id) / ("source" + ext)
    size = await save_upload(file, saved_path)
    doc = Document(
        id=doc_id,
        owner_id=owner,
        agent_id=agent_id,
        filename=filename,
        file_type=ext.lstrip("."),
        file_size_bytes=size,
        storage_path=str(saved_path),
        status="processing",
    )
    db.add(doc)
    await db.commit()
    return await ingest(doc, db)


@router.get("", response_model=list[DocumentResponse])
async def list_documents(
    agent_id: uuid.UUID | None = None,
    db: AsyncSession = Depends(get_db),
    owner: str = Depends(require_owner),
):
    stmt = select(Document).where(Document.owner_id == owner).order_by(Document.created_at.desc())
    if agent_id:
        stmt = stmt.where(Document.agent_id == agent_id)
    return (await db.execute(stmt)).scalars().all()


@router.get("/{document_id}/chunks", response_model=list[DocumentChunkResponse])
async def get_document_chunks(
    document_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    owner: str = Depends(require_owner),
):
    await owned_document(db, document_id, owner)
    stmt = (
        select(DocumentChunk)
        .where(DocumentChunk.document_id == document_id)
        .order_by(DocumentChunk.chunk_index)
    )
    return (await db.execute(stmt)).scalars().all()


@router.get("/{document_id}/assets/{filename}")
async def get_document_asset(
    document_id: uuid.UUID,
    filename: str,
    db: AsyncSession = Depends(get_db),
    owner: str = Depends(require_owner),
):
    doc = await owned_document(db, document_id, owner)
    if doc.status != "completed":
        raise HTTPException(404, "Asset unavailable")
    chunks = (
        (await db.execute(select(DocumentChunk).where(DocumentChunk.document_id == document_id)))
        .scalars()
        .all()
    )
    for chunk in chunks:
        raw = (chunk.metadata_json or {}).get("image_path")
        if raw and Path(raw).name == filename:
            path = managed_path(raw)
            if path.is_file():
                return FileResponse(path)
    raise HTTPException(404, "Asset not found")


@router.post("/{document_id}/retry", response_model=DocumentUploadResponse)
async def retry_document(
    document_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    owner: str = Depends(require_owner),
):
    doc = await owned_document(db, document_id, owner)
    if doc.status not in {"failed", "completed"}:
        raise HTTPException(409, "Document is already processing or being deleted")
    doc.status, doc.error_message = "processing", None
    await db.commit()
    try:
        await qdrant_service.delete_by_document(str(document_id))
        await neo4j_service.delete_by_document(str(document_id))
        await db.execute(delete(DocumentChunk).where(DocumentChunk.document_id == document_id))
        await db.commit()
    except Exception as exc:
        await db.rollback()
        doc = await db.get(Document, document_id)
        doc.status = "failed"
        doc.error_message = "Index cleanup failed; retry after services recover."
        await db.commit()
        raise HTTPException(503, "Index cleanup failed") from exc
    return await ingest(doc, db)


@router.delete("/{document_id}", status_code=204)
async def delete_document(
    document_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    owner: str = Depends(require_owner),
):
    doc = await owned_document(db, document_id, owner)
    if doc.status == "processing":
        raise HTTPException(409, "Wait for document processing to finish")
    doc.status = "deleting"  # A durable tombstone excludes evidence even if cleanup fails.
    await db.commit()
    try:
        await qdrant_service.delete_by_document(str(document_id))
        await neo4j_service.delete_by_document(str(document_id))
        chunks = (
            (
                await db.execute(
                    select(DocumentChunk).where(DocumentChunk.document_id == document_id)
                )
            )
            .scalars()
            .all()
        )
        for chunk in chunks:
            raw = (chunk.metadata_json or {}).get("image_path")
            if raw:
                managed_path(raw).unlink(missing_ok=True)
        path = managed_path(doc.storage_path)
        document_dir = get_settings().UPLOAD_DIR / "documents" / str(document_id)
        if path.parent == document_dir.resolve() and document_dir.exists():
            await asyncio.to_thread(shutil.rmtree, document_dir)
        else:
            path.unlink(missing_ok=True)
        await db.delete(doc)
        await db.commit()
    except Exception as exc:
        await db.rollback()
        logger.exception("Cleanup failed for document %s", document_id)
        raise HTTPException(
            503, "Deletion incomplete. Document is hidden from retrieval; retry deletion."
        ) from exc
