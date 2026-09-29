"""add weighted full-text column on memories

Revision ID: 0010_memory_fts
Revises: 0009_embedding_stamp
Create Date: 2026-09-29
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0010_memory_fts"
down_revision: str | None = "0009_embedding_stamp"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE memories ADD COLUMN content_tsv tsvector "
        "GENERATED ALWAYS AS ("
        "setweight(to_tsvector('english', coalesce(content, '')), 'A')"
        ") STORED"
    )
    op.execute(
        "CREATE INDEX ix_memories_content_tsv ON memories USING GIN (content_tsv)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_memories_content_tsv")
    op.drop_column("memories", "content_tsv")
