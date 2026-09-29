"""stamp memories with the embedder that wrote them

Revision ID: 0009_embedding_stamp
Revises: 0008_usage_ledger
Create Date: 2026-09-29
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0009_embedding_stamp"
down_revision: str | None = "0008_usage_ledger"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("memories", sa.Column("embedding_model", sa.Text(), nullable=True))
    op.add_column("memories", sa.Column("embedding_version", sa.Integer(), nullable=True))
    op.execute("UPDATE memories SET embedding_model = 'hash' WHERE embedding_model IS NULL")
    op.execute("UPDATE memories SET embedding_version = 1 WHERE embedding_version IS NULL")
    op.alter_column("memories", "embedding_model", nullable=False)
    op.alter_column("memories", "embedding_version", nullable=False)


def downgrade() -> None:
    op.drop_column("memories", "embedding_version")
    op.drop_column("memories", "embedding_model")
