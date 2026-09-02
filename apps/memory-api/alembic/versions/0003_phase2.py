"""add event_buffer and ivfflat memory index

Revision ID: 0003_phase2
Revises: 0002_users_api_keys
Create Date: 2026-09-02
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003_phase2"
down_revision: str | None = "0002_users_api_keys"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    event_status = postgresql.ENUM(
        "pending",
        "processing",
        "processed",
        "failed",
        name="event_status",
        create_type=False,
    )
    event_status.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "event_buffer",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "org_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("orgs.id"),
            nullable=False,
        ),
        sa.Column("session_id", sa.Text(), nullable=False),
        sa.Column("event_type", sa.Text(), nullable=False),
        sa.Column(
            "payload",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("status", event_status, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_event_buffer_status_created",
        "event_buffer",
        ["status", "created_at"],
    )
    op.execute(
        "CREATE INDEX ix_memories_embedding ON memories "
        "USING ivfflat (embedding vector_cosine_ops) WITH (lists = 10)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_memories_embedding")
    op.drop_index("ix_event_buffer_status_created", table_name="event_buffer")
    op.drop_table("event_buffer")
    postgresql.ENUM(name="event_status").drop(op.get_bind(), checkfirst=True)
