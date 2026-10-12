import uuid
from typing import TYPE_CHECKING

from sqlalchemy import JSON, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.models.base import TimeStampedUUIDModel

if TYPE_CHECKING:
    from app.db.models.agent import HealthcareAgent
    from app.db.models.citation import Citation


class ChatSession(TimeStampedUUIDModel):
    __tablename__ = "chat_sessions"

    owner_id: Mapped[str] = mapped_column(
        String(100), default="admin", server_default="admin", index=True
    )

    agent_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("healthcare_agents.id", ondelete="CASCADE"), index=True
    )
    title: Mapped[str] = mapped_column(String(200), default="New Clinical Consultation")

    agent: Mapped["HealthcareAgent"] = relationship(
        "HealthcareAgent", back_populates="chat_sessions"
    )
    messages: Mapped[list["ChatMessage"]] = relationship(
        "ChatMessage",
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="ChatMessage.created_at",
    )


class ChatMessage(TimeStampedUUIDModel):
    __tablename__ = "chat_messages"

    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("chat_sessions.id", ondelete="CASCADE"), index=True
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False)  # user, assistant, system
    content: Mapped[str] = mapped_column(Text, nullable=False)
    model_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    visual_payload: Mapped[dict | None] = mapped_column(
        JSON, nullable=True
    )  # diagrams, formulas, charts
    follow_up_suggestions: Mapped[list[str] | None] = mapped_column(JSON, default=list)

    session: Mapped["ChatSession"] = relationship("ChatSession", back_populates="messages")
    citations: Mapped[list["Citation"]] = relationship(
        "Citation", back_populates="message", cascade="all, delete-orphan"
    )
