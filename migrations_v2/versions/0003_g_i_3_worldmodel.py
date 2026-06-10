"""g-i-3 worldmodel: corrections + candidate_edges + candidate_rules + entity_merges.

Revision ID: 0003_g_i_3_worldmodel
Revises: 0002_g_i_3_graph
Create Date: 2026-06-02

4 worldmodel-specific tables that close the learning loop (g-i-3 §3.2):
- corrections      — structured human overrides (input → Bayesian update)
- candidate_edges  — detected via lift; NEVER reasoned on as causal until confirmed
- candidate_rules  — clustered uncovered corrections → human authors hard rule
- entity_merges    — reversible merge log (false-merge recovery)
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003_g_i_3_worldmodel"
down_revision: str | None = "0002_g_i_3_graph"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "corrections",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("org_id", sa.String(64), nullable=False),
        sa.Column("decision_id", sa.String(36), nullable=False),
        sa.Column("input_context", sa.JSON, nullable=False),
        sa.Column("engine_decision", sa.JSON, nullable=False),
        sa.Column("human_decision", sa.JSON, nullable=False),
        sa.Column("diff", sa.JSON, nullable=False),
        sa.Column("rule_ids", sa.JSON, nullable=False, server_default="[]"),
        sa.Column("edge_ids", sa.JSON, nullable=False, server_default="[]"),
        sa.Column(
            "timestamp",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("actor", sa.String(255), nullable=False),
    )
    op.create_index("ix_corrections_org_id", "corrections", ["org_id"])
    op.create_index("ix_corrections_decision_id", "corrections", ["decision_id"])
    op.create_index("ix_corrections_org_timestamp", "corrections", ["org_id", "timestamp"])

    op.create_table(
        "candidate_edges",
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
        sa.Column("signal_lift", sa.Float, nullable=False),
        sa.Column("co_occurrence_count", sa.Integer, nullable=False),
        sa.Column(
            "status",
            sa.String(16),
            nullable=False,
            server_default="proposed",
            comment="proposed | confirmed | rejected (rejected = negative memory; suppress re-proposing)",
        ),
        sa.Column(
            "proposed_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decided_by", sa.String(255), nullable=True),
    )
    op.create_index("ix_candidate_edges_org_id", "candidate_edges", ["org_id"])
    op.create_index(
        "ix_candidate_edges_org_status", "candidate_edges", ["org_id", "status"]
    )
    op.create_index(
        "ix_candidate_edges_pair", "candidate_edges", ["from_node", "to_node"]
    )

    op.create_table(
        "candidate_rules",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("org_id", sa.String(64), nullable=False),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("supporting_correction_ids", sa.JSON, nullable=False, server_default="[]"),
        sa.Column(
            "status",
            sa.String(16),
            nullable=False,
            server_default="proposed",
            comment="proposed | authored | rejected",
        ),
        sa.Column(
            "proposed_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("authored_rule_id", sa.String(255), nullable=True),
    )
    op.create_index("ix_candidate_rules_org_id", "candidate_rules", ["org_id"])
    op.create_index("ix_candidate_rules_org_status", "candidate_rules", ["org_id", "status"])

    op.create_table(
        "entity_merges",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("org_id", sa.String(64), nullable=False),
        sa.Column(
            "merged_into",
            sa.String(36),
            sa.ForeignKey("graph_nodes.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("merged_from", sa.JSON, nullable=False),
        sa.Column("merged_by", sa.String(255), nullable=False),
        sa.Column(
            "merged_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("reversed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reversed_by", sa.String(255), nullable=True),
    )
    op.create_index("ix_entity_merges_org_id", "entity_merges", ["org_id"])
    op.create_index("ix_entity_merges_merged_into", "entity_merges", ["merged_into"])


def downgrade() -> None:
    op.drop_table("entity_merges")
    op.drop_table("candidate_rules")
    op.drop_table("candidate_edges")
    op.drop_table("corrections")
