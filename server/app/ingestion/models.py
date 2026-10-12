from dataclasses import dataclass, field
from typing import Any

from app.domain_types import ENTITY_TYPES, RELATIONSHIP_TYPES


@dataclass
class ParsedPage:
    page_number: int
    text: str
    tables: list[str] = field(default_factory=list)
    image_paths: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ParsedDocument:
    filename: str
    file_type: str
    total_pages: int
    pages: list[ParsedPage]
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ExtractedChunk:
    chunk_index: int
    content: str
    page_number: int | None
    chunk_type: str  # text, table, visual_summary
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ExtractedEntity:
    name: str
    type: str  # Disease, Symptom, Medication, Treatment, LabTest
    description: str | None = None

    def __post_init__(self):
        if self.type not in ENTITY_TYPES or not self.name.strip():
            raise ValueError("Invalid medical entity")
        self.name = self.name.strip().lower()


@dataclass
class ExtractedRelationship:
    source: str
    target: str
    type: str  # TREATS, CAUSES, CONTRAINDICATES, INDICATES, DIAGNOSED_BY
    confidence: float = 1.0

    def __post_init__(self):
        if (
            self.type not in RELATIONSHIP_TYPES
            or not self.source.strip()
            or not self.target.strip()
        ):
            raise ValueError("Invalid medical relationship")
        self.source = self.source.strip().lower()
        self.target = self.target.strip().lower()


@dataclass
class ExtractionResult:
    entities: list[ExtractedEntity] = field(default_factory=list)
    relationships: list[ExtractedRelationship] = field(default_factory=list)
