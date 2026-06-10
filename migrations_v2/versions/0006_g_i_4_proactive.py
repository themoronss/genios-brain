"""g-i-4 proactive analysis: insights + insight_feedback + push_budget + workflow_baselines.

Revision ID: 0006_g_i_4_proactive
Revises: 0005_g_i_5_modules
Create Date: 2026-06-02

4 tables for the push-engine state.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006_g_i_4_proactive"
down_revision: str | None = "0005_g_i_5_modules"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "insights",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("org_id", sa.String(64), nullable=False),
        sa.Column("type", sa.String(16), nullable=False),
        sa.Column("primary_entity", sa.String(255), nullable=False),
        sa.Column("root_cause_edge", sa.String(36), nullable=False, server_default=""),
        sa.Column("derivation_chain_jsonb", sa.JSON, nullable=False),
        sa.Column("foresight_jsonb", sa.JSON, nullable=True),
        sa.Column("scores_jsonb", sa.JSON, nullable=False),
        sa.Column("grounding_refs_jsonb", sa.JSON, nullable=False, server_default="[]"),
        sa.Column("signature_hash", sa.String(32), nullable=False),
        sa.Column("delivery_route", sa.String(16), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_insights_org_id", "insights", ["org_id"])
    op.create_index("ix_insights_signature_hash", "insights", ["signature_hash"])
    op.create_index("ix_insights_org_signature", "insights", ["org_id", "signature_hash"])
    op.create_index("ix_insights_org_created", "insights", ["org_id", "created_at"])

    op.create_table(
        "insight_feedback",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("org_id", sa.String(64), nullable=False),
        sa.Column("user_id", sa.String(64), nullable=False),
        sa.Column("signature_hash", sa.String(32), nullable=False),
        sa.Column("action", sa.String(16), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_feedback_org_id", "insight_feedback", ["org_id"])
    op.create_index("ix_feedback_user_id", "insight_feedback", ["user_id"])
    op.create_index("ix_feedback_signature_hash", "insight_feedback", ["signature_hash"])

    op.create_table(
        "push_budget",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("org_id", sa.String(64), nullable=False),
        sa.Column("user_id", sa.String(64), nullable=False),
        sa.Column("date", sa.String(10), nullable=False),
        sa.Column("interrupts_used", sa.Integer, nullable=False, server_default="0"),
        sa.Column("max_allowed", sa.Integer, nullable=False, server_default="5"),
    )
    op.create_index("ix_push_budget_org_id", "push_budget", ["org_id"])
    op.create_index("ix_push_budget_user_id", "push_budget", ["user_id"])
    op.create_index("ix_push_budget_user_date", "push_budget", ["user_id", "date"], unique=True)

    op.create_table(
        "workflow_baselines",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("org_id", sa.String(64), nullable=False),
        sa.Column("dim", sa.String(16), nullable=False),
        sa.Column("baseline_jsonb", sa.JSON, nullable=False),
        sa.Column("window_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("window_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_baselines_org_id", "workflow_baselines", ["org_id"])
    op.create_index("ix_baselines_org_dim", "workflow_baselines", ["org_id", "dim"])


def downgrade() -> None:
    op.drop_table("workflow_baselines")
    op.drop_table("push_budget")
    op.drop_table("insight_feedback")
    op.drop_table("insights")
