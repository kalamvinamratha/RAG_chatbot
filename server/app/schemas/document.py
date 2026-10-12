import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class DocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    agent_id: uuid.UUID
    filename: str
    file_type: str
    file_size_bytes: int
    status: str
    error_message: str | None = None
    summary: str | None = None
    metadata_json: dict[str, Any] | None = None
    created_at: datetime


class DocumentChunkResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    document_id: uuid.UUID
    agent_id: uuid.UUID
    chunk_index: int
    content: str
    page_number: int | None = None
    chunk_type: str
    created_at: datetime


class DocumentUploadResponse(BaseModel):
    document_id: uuid.UUID
    filename: str
    status: str
    message: str
    chunks_indexed: int
    entities_extracted: int
    relations_extracted: int
