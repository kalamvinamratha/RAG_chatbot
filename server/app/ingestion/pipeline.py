import asyncio
import logging
import uuid
from pathlib import Path

from qdrant_client.http import models as qdrant_models
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Document, DocumentChunk
from app.db.neo4j_client import neo4j_service
from app.db.qdrant_client import qdrant_service
from app.ingestion.chunkers.semantic_chunker import MedicalSemanticChunker
from app.ingestion.entity_extractor import medical_extractor
from app.ingestion.models import ExtractedChunk, ExtractionResult, ParsedDocument
from app.ingestion.multimodal_processor import MultimodalImageProcessor
from app.ingestion.parsers.factory import get_parser_for_file
from app.rag.embeddings import embedding_service

logger = logging.getLogger(__name__)


class IngestionPipeline:
    def __init__(self) -> None:
        self.chunker = MedicalSemanticChunker()
        self.multimodal_processor = MultimodalImageProcessor()

    async def process_document(
        self,
        document_id: uuid.UUID,
        agent_id: uuid.UUID,
        file_path: Path | str,
        db_session: AsyncSession,
    ) -> dict[str, int]:
        """Complete end-to-end multi-format ingestion pipeline."""
        path = Path(file_path)
        document = await db_session.get(Document, document_id)
        if not document:
            raise ValueError("Document not found")
        logger.info(f"Starting ingestion for document {document_id}: {path.name}")

        # 1. Parse document based on file type
        parser = get_parser_for_file(path)
        if hasattr(parser, "output_dir"):
            parser.output_dir = path.parent / "images"
            parser.output_dir.mkdir(parents=True, exist_ok=True)
        parsed_doc: ParsedDocument = await asyncio.to_thread(parser.parse, path)
        parsed_doc.filename = document.filename

        # GUARDRAIL: Strict Healthcare Domain Validation
        from app.rag.guardrails import DomainGuardrailException, domain_guardrail

        is_valid, reason = await domain_guardrail.validate_document_domain(parsed_doc)
        if not is_valid:
            logger.warning("Document %s rejected by domain guardrail: %s", document_id, reason)
            raise DomainGuardrailException(reason)

        # 2. Semantic & table chunking
        chunks: list[ExtractedChunk] = self.chunker.chunk_document(parsed_doc)

        # 3. Multimodal image / chart processing (Add-on feature)
        current_chunk_count = len(chunks)
        for page in parsed_doc.pages:
            for img_path in page.image_paths:
                try:
                    visual_chunk = await self.multimodal_processor.process_image(
                        image_path=img_path,
                        page_number=page.page_number,
                        document_filename=document.filename,
                        chunk_index=current_chunk_count,
                    )
                    chunks.append(visual_chunk)
                    current_chunk_count += 1
                except Exception as e:
                    logger.warning("Error processing multimodal image %s: %s", img_path, e)

        if not chunks:
            raise ValueError("Document contains no extractable text or images")

        # 4. High-speed batch embedding generation (bulk vectorization)
        chunk_texts = [c.content for c in chunks]
        embeddings = await embedding_service.get_embeddings_batch(chunk_texts)

        # 5. Paced medical entity extraction (controlled concurrency pool with rate-limiting pacing)
        sem = asyncio.Semaphore(2)

        async def _extract_safe(text: str) -> ExtractionResult:
            if len(text.strip()) < 25:
                return ExtractionResult()
            async with sem:
                for attempt in range(3):
                    try:
                        # Rate-limiting pacing delay
                        await asyncio.sleep(0.35 * (attempt + 1))
                        return await medical_extractor.extract_from_chunk(text)
                    except Exception as ex:
                        if "429" in str(ex) and attempt < 2:
                            logger.warning(
                                "Rate limit hit during entity extraction, backing off: %s", ex
                            )
                            await asyncio.sleep(2.0 * (attempt + 1))
                            continue
                        logger.warning("Entity extraction note on chunk: %s", ex)
                        return ExtractionResult()
                return ExtractionResult()

        extractions = await asyncio.gather(*(_extract_safe(c.content) for c in chunks))

        # 6. Save chunks to PostgreSQL and prepare vector points & graph relations
        qdrant_points: list[qdrant_models.PointStruct] = []
        entities_count = 0
        relations_count = 0

        for chunk, emb, extraction in zip(chunks, embeddings, extractions, strict=True):
            chunk_db = DocumentChunk(
                document_id=document_id,
                agent_id=agent_id,
                chunk_index=chunk.chunk_index,
                content=chunk.content,
                page_number=chunk.page_number,
                chunk_type=chunk.chunk_type,
                metadata_json=chunk.metadata,
            )
            db_session.add(chunk_db)
            await db_session.flush()

            qdrant_id = str(chunk_db.id)
            chunk_db.qdrant_point_id = qdrant_id

            qdrant_points.append(
                qdrant_models.PointStruct(
                    id=qdrant_id,
                    vector=emb,
                    payload={
                        "chunk_id": str(chunk_db.id),
                        "document_id": str(document_id),
                        "agent_id": str(agent_id),
                        "page_number": chunk.page_number,
                        "chunk_type": chunk.chunk_type,
                        "content": chunk.content,
                        "filename": document.filename,
                        **chunk.metadata,
                    },
                )
            )

            # Required stores must succeed before the document becomes searchable.
            if extraction.entities or extraction.relationships:
                await neo4j_service.add_entity_and_relations(
                    document_id=str(document_id),
                    chunk_id=str(chunk_db.id),
                    entities=[{"name": e.name, "type": e.type} for e in extraction.entities],
                    relationships=[
                        {"source": r.source, "target": r.target, "type": r.type}
                        for r in extraction.relationships
                    ],
                )
                entities_count += len(extraction.entities)
                relations_count += len(extraction.relationships)

        # 7. Bulk upsert to Qdrant
        await qdrant_service.upsert_chunks(qdrant_points)

        # 8. Update Document in Postgres
        doc_record = await db_session.get(Document, document_id)
        if doc_record:
            doc_record.status = "completed"
            doc_record.summary = (
                f"Successfully parsed and indexed {len(chunks)} chunks across {parsed_doc.total_pages} pages/sheets. "
                f"Extracted {entities_count} medical entities and {relations_count} relationships into Knowledge Graph."
            )
            doc_record.metadata_json = {
                "total_pages": parsed_doc.total_pages,
                "total_chunks": len(chunks),
                "entities_count": entities_count,
                "relations_count": relations_count,
            }
            await db_session.commit()

        logger.info(
            f"Ingestion completed for document {document_id}: {len(chunks)} chunks, "
            f"{entities_count} entities, {relations_count} relationships."
        )

        return {
            "chunks_count": len(chunks),
            "entities_count": entities_count,
            "relations_count": relations_count,
        }


ingestion_pipeline = IngestionPipeline()
