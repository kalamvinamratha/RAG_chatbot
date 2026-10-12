import logging
from typing import Any

from qdrant_client import AsyncQdrantClient
from qdrant_client.http import models

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class QdrantService:
    def __init__(self) -> None:
        self.client: AsyncQdrantClient | None = None
        self.collection_name = settings.QDRANT_COLLECTION_NAME

    async def connect(self) -> AsyncQdrantClient:
        if self.client is not None:
            return self.client
        try:
            remote_client = AsyncQdrantClient(
                host=settings.QDRANT_HOST,
                port=settings.QDRANT_PORT,
                api_key=settings.QDRANT_API_KEY or None,
                https=(
                    settings.QDRANT_HTTPS
                    if settings.QDRANT_HTTPS is not None
                    else settings.QDRANT_HOST not in {"localhost", "127.0.0.1", "::1", "qdrant"}
                ),
                timeout=1.0,
            )
            await remote_client.get_collections()
            self.client = remote_client
            return self.client
        except Exception as e:
            logger.warning(
                "Remote Qdrant server unreachable at %s:%s (%s). Falling back to embedded local Qdrant.",
                settings.QDRANT_HOST,
                settings.QDRANT_PORT,
                e,
            )
            local_storage = settings.UPLOAD_DIR / "qdrant_local"
            local_storage.mkdir(parents=True, exist_ok=True)
            self.client = AsyncQdrantClient(path=str(local_storage))
            return self.client

    async def close(self) -> None:
        if self.client:
            await self.client.close()
            self.client = None

    async def init_collection(self, vector_size: int | None = None) -> None:
        """Initializes the Qdrant collection with dense and sparse vector configurations and payload indexes."""
        client = await self.connect()
        dim = vector_size or settings.EMBEDDING_DIMENSION

        try:
            collections = await client.get_collections()
            exists = any(c.name == self.collection_name for c in collections.collections)

            if not exists:
                logger.info(
                    f"Creating Qdrant collection: {self.collection_name} with dimension {dim}"
                )
                await client.create_collection(
                    collection_name=self.collection_name,
                    vectors_config=models.VectorParams(
                        size=dim,
                        distance=models.Distance.COSINE,
                    ),
                    sparse_vectors_config={
                        "bm25": models.SparseVectorParams(
                            index=models.SparseIndexParams(on_disk=False)
                        )
                    },
                )

                # Create payload indexes for high-speed agent and document scoping
                await client.create_payload_index(
                    collection_name=self.collection_name,
                    field_name="agent_id",
                    field_schema=models.PayloadSchemaType.KEYWORD,
                )
                await client.create_payload_index(
                    collection_name=self.collection_name,
                    field_name="document_id",
                    field_schema=models.PayloadSchemaType.KEYWORD,
                )
                await client.create_payload_index(
                    collection_name=self.collection_name,
                    field_name="chunk_type",
                    field_schema=models.PayloadSchemaType.KEYWORD,
                )
                logger.info("Qdrant collection and payload indexes created successfully.")
            else:
                logger.info(f"Qdrant collection '{self.collection_name}' already exists.")
        except Exception as e:
            logger.warning(f"Could not initialize Qdrant collection (is Qdrant running?): {e}")

    async def upsert_chunks(
        self,
        points: list[models.PointStruct],
    ) -> None:
        """Upsert document chunk vectors and metadata into Qdrant."""
        client = await self.connect()
        await client.upsert(
            collection_name=self.collection_name,
            points=points,
        )

    async def search_dense(
        self,
        query_vector: list[float],
        agent_id: str | None = None,
        document_ids: list[str] | None = None,
        limit: int = 10,
        score_threshold: float = 0.35,
    ) -> list[models.ScoredPoint]:
        """Perform dense semantic similarity search filtered by agent and optionally selected documents."""
        client = await self.connect()

        must_conditions: list[Any] = []
        if agent_id:
            must_conditions.append(
                models.FieldCondition(
                    key="agent_id",
                    match=models.MatchValue(value=str(agent_id)),
                )
            )
        if document_ids is not None:
            if not document_ids:
                return []
            must_conditions.append(
                models.FieldCondition(
                    key="document_id",
                    match=models.MatchAny(any=[str(doc_id) for doc_id in document_ids]),
                )
            )

        query_filter = models.Filter(must=must_conditions) if must_conditions else None

        results = await client.query_points(
            collection_name=self.collection_name,
            query=query_vector,
            query_filter=query_filter,
            limit=limit,
            score_threshold=score_threshold,
            with_payload=True,
        )
        return results.points

    async def delete_by_document(self, document_id: str) -> None:
        """Delete all chunk vectors associated with a deleted document."""
        client = await self.connect()
        await client.delete(
            collection_name=self.collection_name,
            points_selector=models.FilterSelector(
                filter=models.Filter(
                    must=[
                        models.FieldCondition(
                            key="document_id",
                            match=models.MatchValue(value=str(document_id)),
                        )
                    ]
                )
            ),
        )


qdrant_service = QdrantService()
