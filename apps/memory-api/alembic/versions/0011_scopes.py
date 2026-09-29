"""add user and agent scope columns

Revision ID: 0011_scopes
Revises: 0010_memory_fts
Create Date: 2026-09-29
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0011_scopes"
down_revision: str | None = "0010_memory_fts"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("memories", sa.Column("user_id", sa.Text(), nullable=True))
    op.add_column("memories", sa.Column("agent_id", sa.Text(), nullable=True))

    op.add_column("kv_facts", sa.Column("user_id", sa.Text(), nullable=True))
    op.add_column("kv_facts", sa.Column("agent_id", sa.Text(), nullable=True))
    op.execute("UPDATE kv_facts SET user_id = COALESCE(user_id, '')")
    op.alter_column(
        "kv_facts",
        "user_id",
        existing_type=sa.Text(),
        nullable=False,
        server_default="",
    )
    op.drop_constraint("uq_kv_facts_org_type_entity", "kv_facts", type_="unique")
    op.create_unique_constraint(
        "uq_kv_facts_org_user_type_entity",
        "kv_facts",
        ["org_id", "user_id", "fact_type", "entity"],
    )

    op.add_column("graph_nodes", sa.Column("user_id", sa.Text(), nullable=True))
    op.add_column("graph_nodes", sa.Column("agent_id", sa.Text(), nullable=True))
    op.execute(
        "UPDATE graph_nodes SET user_id = COALESCE(user_id, ''), "
        "agent_id = COALESCE(agent_id, '')"
    )
    op.alter_column(
        "graph_nodes",
        "user_id",
        existing_type=sa.Text(),
        nullable=False,
        server_default="",
    )
    op.alter_column(
        "graph_nodes",
        "agent_id",
        existing_type=sa.Text(),
        nullable=False,
        server_default="",
    )
    op.drop_constraint("uq_graph_nodes_org_key", "graph_nodes", type_="unique")
    op.create_unique_constraint(
        "uq_graph_nodes_org_user_agent_key",
        "graph_nodes",
        ["org_id", "user_id", "agent_id", "entity_key"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_graph_nodes_org_user_agent_key", "graph_nodes", type_="unique"
    )
    op.create_unique_constraint(
        "uq_graph_nodes_org_key", "graph_nodes", ["org_id", "entity_key"]
    )
    op.drop_column("graph_nodes", "agent_id")
    op.drop_column("graph_nodes", "user_id")

    op.drop_constraint(
        "uq_kv_facts_org_user_type_entity", "kv_facts", type_="unique"
    )
    op.create_unique_constraint(
        "uq_kv_facts_org_type_entity",
        "kv_facts",
        ["org_id", "fact_type", "entity"],
    )
    op.drop_column("kv_facts", "agent_id")
    op.drop_column("kv_facts", "user_id")

    op.drop_column("memories", "agent_id")
    op.drop_column("memories", "user_id")
