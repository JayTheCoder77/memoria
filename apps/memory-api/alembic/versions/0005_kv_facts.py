"""add kv_facts for hybrid exact lookup

Revision ID: 0005_kv_facts
Revises: 0004_openrouter_byok
Create Date: 2026-09-04
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0005_kv_facts"
down_revision: str | None = "0004_openrouter_byok"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "kv_facts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "org_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("orgs.id"),
            nullable=False,
        ),
        sa.Column(
            "memory_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("memories.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("user_key", sa.Text(), nullable=True),
        sa.Column("fact_type", sa.Text(), nullable=False),
        sa.Column("entity", sa.Text(), nullable=False),
        sa.Column("value", sa.Text(), nullable=True),
        sa.Column("importance", sa.Float(), nullable=False, server_default="0.5"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("org_id", "fact_type", "entity", name="uq_kv_facts_org_type_entity"),
    )
    op.create_index("idx_kv_facts_org_type", "kv_facts", ["org_id", "fact_type"])
    op.create_index("idx_kv_facts_memory", "kv_facts", ["memory_id"])
    op.create_index(
        "idx_kv_facts_org_user",
        "kv_facts",
        ["org_id", "user_key"],
        postgresql_where=sa.text("user_key IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("idx_kv_facts_org_user", table_name="kv_facts")
    op.drop_index("idx_kv_facts_memory", table_name="kv_facts")
    op.drop_index("idx_kv_facts_org_type", table_name="kv_facts")
    op.drop_table("kv_facts")
