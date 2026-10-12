from typing import TYPE_CHECKING

from sqlalchemy import Boolean, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.models.base import TimeStampedUUIDModel

if TYPE_CHECKING:
    from app.db.models.chat import ChatSession
    from app.db.models.document import Document


class HealthcareAgent(TimeStampedUUIDModel):
    __tablename__ = "healthcare_agents"

    domain_key: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    specialty: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    system_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    icon: Mapped[str] = mapped_column(String(50), default="stethoscope")
    color: Mapped[str] = mapped_column(String(30), default="#0D9488")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")

    documents: Mapped[list["Document"]] = relationship(
        "Document", back_populates="agent", cascade="all, delete-orphan"
    )
    chat_sessions: Mapped[list["ChatSession"]] = relationship(
        "ChatSession", back_populates="agent", cascade="all, delete-orphan"
    )
