"""add per-org extraction instructions and categories

Revision ID: 0012_extraction_policy
Revises: 0011_scopes
Create Date: 2026-09-29
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0012_extraction_policy"
down_revision: str | None = "0011_scopes"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("orgs", sa.Column("extraction_instructions", sa.Text(), nullable=True))
    op.add_column(
        "orgs",
        sa.Column(
            "categories",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )


def downgrade() -> None:
    op.drop_column("orgs", "categories")
    op.drop_column("orgs", "extraction_instructions")
