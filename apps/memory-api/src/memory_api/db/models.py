from __future__ import annotations

import uuid
from datetime import UTC, datetime
from enum import StrEnum

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, Enum, Float, ForeignKey, Index, Integer, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from memory_api.services.embedding import EMBEDDING_DIM


class Base(DeclarativeBase):
    pass


class MemoryType(StrEnum):
    episodic = "episodic"
    semantic = "semantic"
    procedural = "procedural"


def _utcnow() -> datetime:
    return datetime.now(UTC)


class Org(Base):
    __tablename__ = "orgs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    memories: Mapped[list[Memory]] = relationship(back_populates="org")


class Memory(Base):
    __tablename__ = "memories"
    __table_args__ = (Index("ix_memories_org_session", "org_id", "session_id"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("orgs.id"), nullable=False
    )
    session_id: Mapped[str] = mapped_column(Text, nullable=False)
    memory_type: Mapped[MemoryType] = mapped_column(
        Enum(MemoryType, name="memory_type", native_enum=True),
        nullable=False,
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list[float]] = mapped_column(Vector(EMBEDDING_DIM), nullable=False)
    importance: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)
    access_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    source_metadata: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_accessed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    org: Mapped[Org] = relationship(back_populates="memories")
