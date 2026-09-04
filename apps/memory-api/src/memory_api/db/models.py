from __future__ import annotations

import uuid
from datetime import UTC, datetime
from enum import StrEnum

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    Text,
    UniqueConstraint,
    text,
)
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
    openrouter_key_ciphertext: Mapped[str | None] = mapped_column(Text, nullable=True)
    openrouter_key_last4: Mapped[str | None] = mapped_column(Text, nullable=True)
    openrouter_model: Mapped[str | None] = mapped_column(Text, nullable=True)

    memories: Mapped[list[Memory]] = relationship(back_populates="org")
    users: Mapped[list[User]] = relationship(back_populates="org")
    api_keys: Mapped[list[ApiKey]] = relationship(back_populates="org")


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("orgs.id"), nullable=False
    )
    google_id: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    email: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    org: Mapped[Org] = relationship(back_populates="users")
    api_keys: Mapped[list[ApiKey]] = relationship(back_populates="created_by")


class ApiKey(Base):
    __tablename__ = "api_keys"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("orgs.id"), nullable=False
    )
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    key_hash: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    key_last4: Mapped[str] = mapped_column(Text, nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    org: Mapped[Org] = relationship(back_populates="api_keys")
    created_by: Mapped[User] = relationship(back_populates="api_keys")


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


class KvFact(Base):
    __tablename__ = "kv_facts"
    __table_args__ = (
        UniqueConstraint("org_id", "fact_type", "entity", name="uq_kv_facts_org_type_entity"),
        Index("idx_kv_facts_org_type", "org_id", "fact_type"),
        Index("idx_kv_facts_memory", "memory_id"),
        Index(
            "idx_kv_facts_org_user",
            "org_id",
            "user_key",
            postgresql_where=text("user_key IS NOT NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("orgs.id"), nullable=False
    )
    memory_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("memories.id", ondelete="CASCADE"), nullable=False
    )
    user_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    fact_type: Mapped[str] = mapped_column(Text, nullable=False)
    entity: Mapped[str] = mapped_column(Text, nullable=False)
    value: Mapped[str | None] = mapped_column(Text, nullable=True)
    importance: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class GraphNode(Base):
    __tablename__ = "graph_nodes"
    __table_args__ = (
        UniqueConstraint("org_id", "entity_key", name="uq_graph_nodes_org_key"),
        Index("idx_graph_nodes_org_key", "org_id", "entity_key"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("orgs.id"), nullable=False
    )
    entity_key: Mapped[str] = mapped_column(Text, nullable=False)
    label: Mapped[str] = mapped_column(Text, nullable=False)
    properties: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class GraphEdgeRow(Base):
    __tablename__ = "graph_edges"
    __table_args__ = (
        Index("idx_graph_edges_org", "org_id"),
        Index(
            "idx_graph_edges_subject",
            "subject_id",
            postgresql_where=text("valid = true"),
        ),
        Index(
            "idx_graph_edges_object",
            "object_id",
            postgresql_where=text("valid = true"),
        ),
        Index("idx_graph_edges_memory", "memory_id"),
        Index("idx_graph_edges_valid_time", "org_id", "valid_from", "valid_to"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("orgs.id"), nullable=False
    )
    subject_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("graph_nodes.id"), nullable=False
    )
    relation: Mapped[str] = mapped_column(Text, nullable=False)
    object_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("graph_nodes.id"), nullable=False
    )
    memory_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("memories.id", ondelete="SET NULL"), nullable=True
    )
    valid: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    valid_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    valid_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    properties: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class EventStatus(StrEnum):
    pending = "pending"
    processing = "processing"
    processed = "processed"
    failed = "failed"


class EventBuffer(Base):
    __tablename__ = "event_buffer"
    __table_args__ = (Index("ix_event_buffer_status_created", "status", "created_at"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("orgs.id"), nullable=False
    )
    session_id: Mapped[str] = mapped_column(Text, nullable=False)
    event_type: Mapped[str] = mapped_column(Text, nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    status: Mapped[EventStatus] = mapped_column(
        Enum(EventStatus, name="event_status", native_enum=True),
        nullable=False,
        default=EventStatus.pending,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
