"""store per-org Groq BYOK credentials

Revision ID: 0007_groq_byok
Revises: 0006_graph
Create Date: 2026-09-07
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007_groq_byok"
down_revision: str | None = "0006_graph"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("orgs", sa.Column("groq_key_ciphertext", sa.Text(), nullable=True))
    op.add_column("orgs", sa.Column("groq_key_last4", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("orgs", "groq_key_last4")
    op.drop_column("orgs", "groq_key_ciphertext")
