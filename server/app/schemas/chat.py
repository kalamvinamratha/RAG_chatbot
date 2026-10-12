import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ChatSessionCreate(BaseModel):
    agent_id: uuid.UUID
    title: str = "New Clinical Consultation"


class ChatSessionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    agent_id: uuid.UUID
    title: str
    created_at: datetime
    updated_at: datetime


class CitationResponse(BaseModel):
    citation_number: int
    document_id: str | None = None
    chunk_id: str | None = None
    filename: str
    page_number: int | None = None
    excerpt: str
    score: float
    chunk_type: str = "text"
    image_path: str | None = None
    sources: list[str] = Field(default_factory=list)


class ChatMessageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    session_id: uuid.UUID
    role: str
    content: str
    model_name: str | None = None
    visual_payload: dict[str, Any] | None = None
    follow_up_suggestions: list[str] | None = None
    created_at: datetime
    citations: list[CitationResponse] = Field(default_factory=list)


class ChatQueryRequest(BaseModel):
    session_id: uuid.UUID | None = None
    agent_id: uuid.UUID
    message: str = Field(..., min_length=1, max_length=20000)
    document_ids: list[uuid.UUID] | None = None
