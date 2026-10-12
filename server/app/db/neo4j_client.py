import contextlib
import json
import logging
import time
from pathlib import Path
from typing import Any

from neo4j import AsyncDriver, AsyncGraphDatabase

from app.config import get_settings
from app.domain_types import ENTITY_TYPES, RELATIONSHIP_TYPES

logger = logging.getLogger(__name__)
settings = get_settings()


class InMemoryGraphStore:
    """Resilient in-memory knowledge graph store for local environments without Neo4j."""

    def __init__(self, persist_path: Path | None = None) -> None:
        self.persist_path = persist_path
        self.entities: dict[str, str] = {}
        self.doc_chunks: dict[str, set[str]] = {}
        self.chunks: dict[str, dict[str, Any]] = {}
        self.relationships: list[dict[str, Any]] = []
        self._load()

    def _load(self) -> None:
        if self.persist_path and self.persist_path.is_file():
            try:
                data = json.loads(self.persist_path.read_text(encoding="utf-8"))
                self.entities = data.get("entities", {})
                self.doc_chunks = {k: set(v) for k, v in data.get("doc_chunks", {}).items()}
                self.chunks = data.get("chunks", {})
                self.relationships = data.get("relationships", [])
            except Exception as e:
                logger.debug("Could not load local graph cache: %s", e)

    def _save(self) -> None:
        if self.persist_path:
            try:
                self.persist_path.parent.mkdir(parents=True, exist_ok=True)
                data = {
                    "entities": self.entities,
                    "doc_chunks": {k: list(v) for k, v in self.doc_chunks.items()},
                    "chunks": self.chunks,
                    "relationships": self.relationships,
                }
                self.persist_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
            except Exception as e:
                logger.debug("Could not persist local graph cache: %s", e)

    def add_entity_and_relations(
        self,
        document_id: str,
        chunk_id: str,
        entities: list[dict[str, Any]],
        relationships: list[dict[str, Any]],
    ) -> None:
        for entity in entities:
            label = entity.get("type", "")
            if label not in ENTITY_TYPES:
                raise ValueError("Unsupported entity type")
            name = entity.get("name", "").strip().lower()
            if name:
                self.entities[name] = label

        for rel in relationships:
            rel_type = rel.get("type", "")
            if rel_type not in RELATIONSHIP_TYPES:
                raise ValueError("Unsupported relationship type")
            source = rel.get("source", "").strip().lower()
            target = rel.get("target", "").strip().lower()
            if source and target:
                self.relationships.append(
                    {
                        "source": source,
                        "source_type": self.entities.get(source, "Disease"),
                        "relationship": rel_type,
                        "target": target,
                        "target_type": self.entities.get(target, "Treatment"),
                        "chunk_id": chunk_id,
                        "document_id": document_id,
                    }
                )

        self.doc_chunks.setdefault(document_id, set()).add(chunk_id)
        self.chunks[chunk_id] = {
            "document_id": document_id,
            "entities": entities,
        }
        self._save()

    def query_subgraph_for_entities(
        self,
        entity_names: list[str],
        chunk_ids: list[str],
        limit: int = 25,
    ) -> list[dict[str, Any]]:
        if not chunk_ids:
            return []
        chunk_set = set(chunk_ids)
        clean_names = {e.strip().lower() for e in entity_names if e.strip()}

        matched: list[dict[str, Any]] = []
        seen = set()
        for r in self.relationships:
            if r["chunk_id"] not in chunk_set:
                continue
            if clean_names and r["source"] not in clean_names and r["target"] not in clean_names:
                continue
            key = (r["source"], r["relationship"], r["target"], r["chunk_id"])
            if key not in seen:
                seen.add(key)
                matched.append(r)
                if len(matched) >= limit:
                    break
        return matched

    def delete_by_document(self, document_id: str) -> None:
        self.relationships = [r for r in self.relationships if r.get("document_id") != document_id]
        chunks_to_remove = self.doc_chunks.pop(document_id, set())
        for cid in chunks_to_remove:
            self.chunks.pop(cid, None)
        active_names = {r["source"] for r in self.relationships} | {
            r["target"] for r in self.relationships
        }
        for chunk in self.chunks.values():
            for e in chunk.get("entities", []):
                active_names.add(e.get("name", "").strip().lower())
        self.entities = {k: v for k, v in self.entities.items() if k in active_names}
        self._save()


class Neo4jService:
    def __init__(self) -> None:
        self.driver: AsyncDriver | None = None
        self._fallback_store: InMemoryGraphStore | None = None
        self._connection_failed: bool = False
        self._last_connect_attempt: float = 0.0

    @property
    def fallback_store(self) -> InMemoryGraphStore:
        if self._fallback_store is None:
            self._fallback_store = InMemoryGraphStore(
                persist_path=settings.UPLOAD_DIR / "local_graph_store.json"
            )
        return self._fallback_store

    async def connect(self) -> AsyncDriver | None:
        if self.driver is not None:
            return self.driver
        now = time.monotonic()
        if self._connection_failed and (now - self._last_connect_attempt < 10.0):
            return None
        self._last_connect_attempt = now
        try:
            driver = AsyncGraphDatabase.driver(
                settings.NEO4J_URI,
                auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD),
            )
            await driver.verify_connectivity()
            self.driver = driver
            self._connection_failed = False
            return self.driver
        except Exception as e:
            self._connection_failed = True
            logger.warning(
                "Could not connect to Neo4j at %s (%s). Using embedded local graph store.",
                settings.NEO4J_URI,
                e,
            )
            return None

    async def close(self) -> None:
        if self.driver:
            with contextlib.suppress(Exception):
                await self.driver.close()
            self.driver = None

    async def init_schema(self) -> None:
        """Initializes uniqueness constraints and indexes for healthcare entities."""
        driver = await self.connect() if self.driver is None else self.driver
        if not driver:
            logger.info("Neo4j offline. Local knowledge graph store ready.")
            return

        queries = [
            "CREATE CONSTRAINT disease_name_unique IF NOT EXISTS FOR (d:Disease) REQUIRE d.name IS UNIQUE;",
            "CREATE CONSTRAINT symptom_name_unique IF NOT EXISTS FOR (s:Symptom) REQUIRE s.name IS UNIQUE;",
            "CREATE CONSTRAINT medication_name_unique IF NOT EXISTS FOR (m:Medication) REQUIRE m.name IS UNIQUE;",
            "CREATE CONSTRAINT treatment_name_unique IF NOT EXISTS FOR (t:Treatment) REQUIRE t.name IS UNIQUE;",
            "CREATE CONSTRAINT labtest_name_unique IF NOT EXISTS FOR (l:LabTest) REQUIRE l.name IS UNIQUE;",
            "CREATE CONSTRAINT chunk_id_unique IF NOT EXISTS FOR (c:Chunk) REQUIRE c.id IS UNIQUE;",
            "CREATE INDEX disease_name_idx IF NOT EXISTS FOR (d:Disease) ON (d.name);",
            "CREATE INDEX medication_name_idx IF NOT EXISTS FOR (m:Medication) ON (m.name);",
        ]
        try:
            async with driver.session() as session:
                for query in queries:
                    try:
                        await session.run(query)
                    except Exception as q_err:
                        logger.debug("Schema query note: %s", q_err)
            logger.info("Neo4j healthcare schema and constraints initialized.")
        except Exception as e:
            logger.warning(
                f"Could not connect to Neo4j to initialize schema (is Neo4j running?): {e}"
            )

    async def run_query(
        self, query: str, parameters: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        """Run Cypher query and return results as list of dicts."""
        driver = await self.connect() if self.driver is None else self.driver
        if driver is None:
            raise RuntimeError(f"Neo4j unavailable at {settings.NEO4J_URI}")
        async with driver.session() as session:
            result = await session.run(query, parameters or {})
            records = await result.data()
            return records

    async def add_entity_and_relations(
        self,
        document_id: str,
        chunk_id: str,
        entities: list[dict[str, Any]],
        relationships: list[dict[str, Any]],
    ) -> None:
        """Upsert extracted entities and their medical relationships linked to a source chunk and document."""
        # 1. Validation (must raise ValueError on unsupported types)
        for entity in entities:
            label = entity.get("type", "")
            if label not in ENTITY_TYPES:
                raise ValueError("Unsupported entity type")
        for rel in relationships:
            rel_type = rel.get("type", "")
            if rel_type not in RELATIONSHIP_TYPES:
                raise ValueError("Unsupported relationship type")

        # 2. Add to resilient local graph store
        self.fallback_store.add_entity_and_relations(
            document_id=document_id,
            chunk_id=chunk_id,
            entities=entities,
            relationships=relationships,
        )

        # 3. Attempt Neo4j sync if driver available
        driver = await self.connect() if self.driver is None else self.driver
        if driver:
            try:
                async with driver.session() as session:
                    # Upsert Chunk node
                    await session.run(
                        """
                        MERGE (c:Chunk {id: $chunk_id})
                        SET c.document_id = $document_id
                        """,
                        {"chunk_id": chunk_id, "document_id": document_id},
                    )

                    # Upsert entities and link to chunk
                    for entity in entities:
                        name = entity.get("name", "").strip().lower()
                        label = entity.get("type", "")
                        if not name:
                            continue
                        cypher = f"""
                        MERGE (e:{label} {{name: $name}})
                        WITH e
                        MATCH (c:Chunk {{id: $chunk_id}})
                        MERGE (c)-[:MENTIONS]->(e)
                        """
                        await session.run(
                            cypher,
                            {"name": name, "chunk_id": chunk_id, "document_id": document_id},
                        )

                    # Upsert relationships between entities
                    for rel in relationships:
                        source_name = rel.get("source", "").strip().lower()
                        target_name = rel.get("target", "").strip().lower()
                        rel_type = rel.get("type", "")
                        if not source_name or not target_name:
                            continue
                        cypher = f"""
                        MATCH (c:Chunk {{id: $chunk_id}})-[:MENTIONS]->(s {{name: $source_name}})
                        MATCH (c)-[:MENTIONS]->(t {{name: $target_name}})
                        MERGE (s)-[r:{rel_type} {{chunk_id: $chunk_id}}]->(t)
                        SET r.document_id = $document_id
                        """
                        await session.run(
                            cypher,
                            {
                                "source_name": source_name,
                                "target_name": target_name,
                                "document_id": document_id,
                                "chunk_id": chunk_id,
                            },
                        )
            except Exception as e:
                logger.warning("Neo4j upsert failed (%s). Preserved in local graph store.", e)

    async def query_subgraph_for_entities(
        self,
        entity_names: list[str],
        chunk_ids: list[str],
        limit: int = 25,
    ) -> list[dict[str, Any]]:
        """Given a list of identified clinical entities in user query, find neighboring relationships and contraindications."""
        if not chunk_ids:
            return []

        clean_names = [e.strip().lower() for e in entity_names if e.strip()]

        driver = await self.connect() if self.driver is None else self.driver
        if driver:
            try:
                cypher = """
                MATCH (c:Chunk)-[:MENTIONS]->(start)
                WHERE c.id IN $chunk_ids AND (size($names) = 0 OR start.name IN $names)
                MATCH (start)-[r]-(neighbor)
                WHERE r.chunk_id = c.id AND type(r) IN $types AND neighbor.name IS NOT NULL
                RETURN
                    DISTINCT startNode(r).name AS source,
                    labels(startNode(r))[0] AS source_type,
                    type(r) AS relationship,
                    endNode(r).name AS target,
                    labels(endNode(r))[0] AS target_type,
                    c.id AS chunk_id,
                    c.document_id AS document_id
                LIMIT $limit
                """
                async with driver.session() as session:
                    result = await session.run(
                        cypher,
                        {
                            "names": clean_names,
                            "limit": limit,
                            "chunk_ids": chunk_ids,
                            "types": sorted(RELATIONSHIP_TYPES),
                        },
                    )
                    records = await result.data()
                    if records:
                        return records
            except Exception as e:
                logger.warning("Neo4j query failed (%s); using local graph fallback", e)

        return self.fallback_store.query_subgraph_for_entities(entity_names, chunk_ids, limit)

    async def delete_by_document(self, document_id: str) -> None:
        self.fallback_store.delete_by_document(document_id)
        driver = await self.connect() if self.driver is None else self.driver
        if driver:
            try:
                await self.run_query(
                    "MATCH ()-[r]->() WHERE r.document_id = $document_id DELETE r",
                    {"document_id": document_id},
                )
                await self.run_query(
                    "MATCH (c:Chunk {document_id: $document_id}) DETACH DELETE c",
                    {"document_id": document_id},
                )
                await self.run_query(
                    "MATCH (e) WHERE any(label IN labels(e) WHERE label IN $types) "
                    "AND NOT (e)<-[:MENTIONS]-(:Chunk) DETACH DELETE e",
                    {"types": sorted(ENTITY_TYPES)},
                )
            except Exception as e:
                logger.warning("Neo4j delete skipped or failed (%s)", e)

    async def sync_fallback_to_neo4j(self) -> dict[str, int]:
        """Syncs all entities, chunks, and relationships from fallback local store into live Neo4j."""
        driver = await self.connect()
        if not driver:
            raise RuntimeError("Cannot sync to Neo4j: driver not connected")

        fb = self.fallback_store
        synced_chunks = 0
        synced_entities = 0
        synced_rels = 0

        async with driver.session() as session:
            for chunk_id, chunk_data in fb.chunks.items():
                doc_id = chunk_data.get("document_id", "")
                await session.run(
                    """
                    MERGE (c:Chunk {id: $chunk_id})
                    SET c.document_id = $document_id
                    """,
                    {"chunk_id": chunk_id, "document_id": doc_id},
                )
                synced_chunks += 1

                for entity in chunk_data.get("entities", []):
                    name = entity.get("name", "").strip().lower()
                    label = entity.get("type", "")
                    if not name or label not in ENTITY_TYPES:
                        continue
                    cypher = f"""
                    MERGE (e:{label} {{name: $name}})
                    WITH e
                    MATCH (c:Chunk {{id: $chunk_id}})
                    MERGE (c)-[:MENTIONS]->(e)
                    """
                    await session.run(cypher, {"name": name, "chunk_id": chunk_id})
                    synced_entities += 1

            for rel in fb.relationships:
                source_name = rel.get("source", "").strip().lower()
                target_name = rel.get("target", "").strip().lower()
                rel_type = rel.get("relationship", "")
                chunk_id = rel.get("chunk_id", "")
                doc_id = rel.get("document_id", "")
                if not source_name or not target_name or rel_type not in RELATIONSHIP_TYPES:
                    continue
                cypher = f"""
                MATCH (c:Chunk {{id: $chunk_id}})-[:MENTIONS]->(s {{name: $source_name}})
                MATCH (c)-[:MENTIONS]->(t {{name: $target_name}})
                MERGE (s)-[r:{rel_type} {{chunk_id: $chunk_id}}]->(t)
                SET r.document_id = $document_id
                """
                await session.run(
                    cypher,
                    {
                        "source_name": source_name,
                        "target_name": target_name,
                        "document_id": doc_id,
                        "chunk_id": chunk_id,
                    },
                )
                synced_rels += 1

        logger.info(
            "Synced %d chunks, %d entity mentions, and %d relationships into Neo4j.",
            synced_chunks,
            synced_entities,
            synced_rels,
        )
        return {
            "chunks": synced_chunks,
            "entities": synced_entities,
            "relationships": synced_rels,
        }


neo4j_service = Neo4jService()
