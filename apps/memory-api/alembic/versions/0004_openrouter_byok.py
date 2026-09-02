"""store per-org OpenRouter BYOK credentials

Revision ID: 0004_openrouter_byok
Revises: 0003_phase2
Create Date: 2026-09-02
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004_openrouter_byok"
down_revision: str | None = "0003_phase2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("orgs", sa.Column("openrouter_key_ciphertext", sa.Text(), nullable=True))
    op.add_column("orgs", sa.Column("openrouter_key_last4", sa.Text(), nullable=True))
    op.add_column("orgs", sa.Column("openrouter_model", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("orgs", "openrouter_model")
    op.drop_column("orgs", "openrouter_key_last4")
    op.drop_column("orgs", "openrouter_key_ciphertext")
