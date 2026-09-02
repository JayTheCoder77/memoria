"""create orgs and memories tables

Revision ID: 0001_phase1
Revises:
Create Date: 2026-09-02
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

revision: str = "0001_phase1"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "orgs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    memory_type = postgresql.ENUM(
        "episodic",
        "semantic",
        "procedural",
        name="memory_type",
        create_type=False,
    )
    memory_type.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "memories",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "org_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("orgs.id"),
            nullable=False,
        ),
        sa.Column("session_id", sa.Text(), nullable=False),
        sa.Column("memory_type", memory_type, nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("embedding", Vector(384), nullable=False),
        sa.Column("importance", sa.Float(), nullable=False),
        sa.Column("access_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "source_metadata",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_accessed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_memories_org_session", "memories", ["org_id", "session_id"])


def downgrade() -> None:
    op.drop_index("ix_memories_org_session", table_name="memories")
    op.drop_table("memories")
    postgresql.ENUM(name="memory_type").drop(op.get_bind(), checkfirst=True)
    op.drop_table("orgs")
