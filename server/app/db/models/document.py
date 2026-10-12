import uuid
from typing import TYPE_CHECKING

from sqlalchemy import JSON, BigInteger, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.models.base import TimeStampedUUIDModel

if TYPE_CHECKING:
    from app.db.models.agent import HealthcareAgent
    from app.db.models.document_chunk import DocumentChunk


class Document(TimeStampedUUIDModel):
    __tablename__ = "documents"

    owner_id: Mapped[str] = mapped_column(
        String(100), default="admin", server_default="admin", index=True
    )

    agent_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("healthcare_agents.id", ondelete="CASCADE"), index=True
    )
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_type: Mapped[str] = mapped_column(String(20), nullable=False)  # pdf, docx, xlsx, pptx, txt
    file_size_bytes: Mapped[int] = mapped_column(BigInteger, default=0)
    storage_path: Mapped[str] = mapped_column(String(500), nullable=False)
    status: Mapped[str] = mapped_column(
        String(30), default="pending", index=True
    )  # pending, processing, completed, failed
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSON, default=dict)

    agent: Mapped["HealthcareAgent"] = relationship("HealthcareAgent", back_populates="documents")
    chunks: Mapped[list["DocumentChunk"]] = relationship(
        "DocumentChunk", back_populates="document", cascade="all, delete-orphan"
    )
