"""g-i-3 graph foundations: facts + graph_nodes + graph_edges + graph_events + graph_snapshots.

Revision ID: 0002_g_i_3_graph
Revises: 0001_g_i_1_memory
Create Date: 2026-06-02

5 tables (the shared graph that g-i-2 reasons over and g-i-3 extends).
Worldmodel-specific tables (corrections, candidate_edges, candidate_rules,
entity_merges) land in 0003 once g-i-3 Phase B code is in.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002_g_i_3_graph"
down_revision: str | None = "0001_g_i_1_memory"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "facts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("org_id", sa.String(64), nullable=False),
        sa.Column("subject", sa.String(255), nullable=False),
        sa.Column("predicate", sa.String(128), nullable=False),
        sa.Column("object", sa.Text, nullable=False),
        sa.Column("source_item_id", sa.String(64), nullable=False),
        sa.Column("asserted_by_type", sa.String(16), nullable=False),
        sa.Column("asserted_by_id", sa.String(255), nullable=False),
        sa.Column("confidence", sa.Float, nullable=False, server_default="1.0"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index("ix_facts_org_id", "facts", ["org_id"])
    op.create_index("ix_facts_source_item_id", "facts", ["source_item_id"])
    op.create_index("ix_facts_org_subject", "facts", ["org_id", "subject"])
    op.create_index("ix_facts_org_predicate", "facts", ["org_id", "predicate"])

    op.create_table(
        "graph_nodes",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("org_id", sa.String(64), nullable=False),
        sa.Column("org_unit", sa.String(64), nullable=False),
        sa.Column("type", sa.String(16), nullable=False),
        sa.Column("canonical_name", sa.String(255), nullable=False),
        sa.Column("aliases", sa.JSON, nullable=False, server_default="[]"),
        sa.Column("attributes", sa.JSON, nullable=False, server_default="{}"),
        sa.Column("source_item_ids", sa.JSON, nullable=False, server_default="[]"),
        sa.Column(
            "first_seen", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "last_seen", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index("ix_nodes_org_id", "graph_nodes", ["org_id"])
    op.create_index("ix_nodes_org_unit", "graph_nodes", ["org_unit"])
    op.create_index("ix_nodes_org_canonical", "graph_nodes", ["org_id", "canonical_name"])
    op.create_index("ix_nodes_org_type", "graph_nodes", ["org_id", "type"])

    op.create_table(
        "graph_edges",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("org_id", sa.String(64), nullable=False),
        sa.Column(
            "from_node",
            sa.String(36),
            sa.ForeignKey("graph_nodes.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "to_node",
            sa.String(36),
            sa.ForeignKey("graph_nodes.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("type", sa.String(16), nullable=False),
        sa.Column("asserted_by_type", sa.String(16), nullable=False),
        sa.Column("asserted_by_id", sa.String(255), nullable=False),
        sa.Column(
            "asserted_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("weight", sa.Float, nullable=False, server_default="1.0"),
        sa.Column("weight_source", sa.String(16), nullable=False, server_default="default"),
        sa.Column("alpha", sa.Integer, nullable=False, server_default="1"),
        sa.Column("beta", sa.Integer, nullable=False, server_default="1"),
        sa.Column("trust", sa.Float, nullable=False, server_default="0.0"),
        sa.Column("decay_lambda", sa.Float, nullable=False, server_default="0.0"),
        sa.Column("status", sa.String(16), nullable=False, server_default="asserted"),
    )
    op.create_index("ix_edges_org_id", "graph_edges", ["org_id"])
    op.create_index("ix_edges_org_from", "graph_edges", ["org_id", "from_node"])
    op.create_index("ix_edges_org_to", "graph_edges", ["org_id", "to_node"])
    op.create_index(
        "ix_edges_org_type_status", "graph_edges", ["org_id", "type", "status"]
    )

    op.create_table(
        "graph_events",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("org_id", sa.String(64), nullable=False),
        sa.Column("version", sa.BigInteger, nullable=False),
        sa.Column("event_type", sa.String(32), nullable=False),
        sa.Column("target_type", sa.String(16), nullable=False),
        sa.Column("target_id", sa.String(36), nullable=False),
        sa.Column("payload", sa.JSON, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_events_org_id", "graph_events", ["org_id"])
    op.create_index("ix_events_target_id", "graph_events", ["target_id"])
    op.create_index("ix_events_org_version", "graph_events", ["org_id", "version"])
    op.create_index("ix_events_org_created", "graph_events", ["org_id", "created_at"])

    op.create_table(
        "graph_snapshots",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("org_id", sa.String(64), nullable=False),
        sa.Column("version", sa.BigInteger, nullable=False),
        sa.Column("snapshot", sa.JSON, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_snapshots_org_id", "graph_snapshots", ["org_id"])
    op.create_index("ix_snapshots_org_version", "graph_snapshots", ["org_id", "version"])


def downgrade() -> None:
    op.drop_table("graph_snapshots")
    op.drop_table("graph_events")
    op.drop_table("graph_edges")
    op.drop_table("graph_nodes")
    op.drop_table("facts")
