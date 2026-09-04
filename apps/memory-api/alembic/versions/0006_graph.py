"""add graph_nodes and graph_edges for hybrid relationship lookup

Revision ID: 0006_graph
Revises: 0005_kv_facts
Create Date: 2026-09-04
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0006_graph"
down_revision: str | None = "0005_kv_facts"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "graph_nodes",
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
        sa.Column("entity_key", sa.Text(), nullable=False),
        sa.Column("label", sa.Text(), nullable=False),
        sa.Column(
            "properties",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("org_id", "entity_key", name="uq_graph_nodes_org_key"),
    )
    op.create_index("idx_graph_nodes_org_key", "graph_nodes", ["org_id", "entity_key"])
    op.create_table(
        "graph_edges",
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
        sa.Column(
            "subject_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("graph_nodes.id"),
            nullable=False,
        ),
        sa.Column("relation", sa.Text(), nullable=False),
        sa.Column(
            "object_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("graph_nodes.id"),
            nullable=False,
        ),
        sa.Column(
            "memory_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("memories.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("valid", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column(
            "valid_from",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("valid_to", sa.DateTime(timezone=True), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="1.0"),
        sa.Column(
            "properties",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("idx_graph_edges_org", "graph_edges", ["org_id"])
    op.create_index(
        "idx_graph_edges_subject",
        "graph_edges",
        ["subject_id"],
        postgresql_where=sa.text("valid = true"),
    )
    op.create_index(
        "idx_graph_edges_object",
        "graph_edges",
        ["object_id"],
        postgresql_where=sa.text("valid = true"),
    )
    op.create_index("idx_graph_edges_memory", "graph_edges", ["memory_id"])
    op.create_index(
        "idx_graph_edges_valid_time",
        "graph_edges",
        ["org_id", "valid_from", "valid_to"],
    )


def downgrade() -> None:
    op.drop_index("idx_graph_edges_valid_time", table_name="graph_edges")
    op.drop_index("idx_graph_edges_memory", table_name="graph_edges")
    op.drop_index("idx_graph_edges_object", table_name="graph_edges")
    op.drop_index("idx_graph_edges_subject", table_name="graph_edges")
    op.drop_index("idx_graph_edges_org", table_name="graph_edges")
    op.drop_table("graph_edges")
    op.drop_index("idx_graph_nodes_org_key", table_name="graph_nodes")
    op.drop_table("graph_nodes")
