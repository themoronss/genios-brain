"""g-i-6 artifacts: artifacts + ungrounded_rejections.

Revision ID: 0007_g_i_6_artifacts
Revises: 0006_g_i_4_proactive
Create Date: 2026-06-02
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007_g_i_6_artifacts"
down_revision: str | None = "0006_g_i_4_proactive"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "artifacts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("org_id", sa.String(64), nullable=False),
        sa.Column("decision_id", sa.String(36), nullable=False),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("body", sa.Text, nullable=False),
        sa.Column("trace_jsonb", sa.JSON, nullable=False),
        sa.Column("counterfactuals_jsonb", sa.JSON, nullable=False, server_default="[]"),
        sa.Column("uncertainty_summary", sa.Text, nullable=False, server_default=""),
        sa.Column(
            "generated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("generated_by_module", sa.String(64), nullable=True),
    )
    op.create_index("ix_artifacts_org_id", "artifacts", ["org_id"])
    op.create_index("ix_artifacts_decision_id", "artifacts", ["decision_id"])
    op.create_index("ix_artifacts_org_decision", "artifacts", ["org_id", "decision_id"])
    op.create_index("ix_artifacts_org_generated", "artifacts", ["org_id", "generated_at"])

    op.create_table(
        "ungrounded_rejections",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("org_id", sa.String(64), nullable=False),
        sa.Column("decision_id", sa.String(36), nullable=False),
        sa.Column("rejected_claim", sa.Text, nullable=False),
        sa.Column("reason", sa.String(255), nullable=False),
        sa.Column("retry_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column(
            "timestamp",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_rejections_org_id", "ungrounded_rejections", ["org_id"])
    op.create_index("ix_rejections_decision_id", "ungrounded_rejections", ["decision_id"])


def downgrade() -> None:
    op.drop_table("ungrounded_rejections")
    op.drop_table("artifacts")
