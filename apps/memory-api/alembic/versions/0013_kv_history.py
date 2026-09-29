"""add kv_fact_history for versioned fact values

Revision ID: 0013_kv_history
Revises: 0012_extraction_policy
Create Date: 2026-09-29
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0013_kv_history"
down_revision: str | None = "0012_extraction_policy"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "kv_fact_history",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "org_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("orgs.id"),
            nullable=False,
        ),
        sa.Column("user_id", sa.Text(), nullable=False, server_default=""),
        sa.Column("fact_type", sa.Text(), nullable=False),
        sa.Column("entity", sa.Text(), nullable=False),
        sa.Column("value", sa.Text(), nullable=True),
        sa.Column(
            "memory_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("memories.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "valid_from",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("valid_to", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "idx_kv_fact_history_scope",
        "kv_fact_history",
        ["org_id", "user_id", "fact_type", "entity"],
    )
    op.create_index(
        "uq_kv_fact_history_open",
        "kv_fact_history",
        ["org_id", "user_id", "fact_type", "entity"],
        unique=True,
        postgresql_where=sa.text("valid_to IS NULL"),
    )
    op.execute(
        sa.text(
            """
            INSERT INTO kv_fact_history (
                org_id, user_id, fact_type, entity, value, memory_id
            )
            SELECT org_id, user_id, fact_type, entity, value, memory_id
            FROM kv_facts
            """
        )
    )


def downgrade() -> None:
    op.drop_index("uq_kv_fact_history_open", table_name="kv_fact_history")
    op.drop_index("idx_kv_fact_history_scope", table_name="kv_fact_history")
    op.drop_table("kv_fact_history")
