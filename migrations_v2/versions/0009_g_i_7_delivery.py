"""g-i-7 delivery: agent_registry + agent_calls + channel_deliveries + feedback_actions.

Revision ID: 0009_g_i_7_delivery
Revises: 0008_g_i_9_usermodel
Create Date: 2026-06-02
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0009_g_i_7_delivery"
down_revision: str | None = "0008_g_i_9_usermodel"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "agent_registry",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("org_id", sa.String(64), nullable=False),
        sa.Column("agent_id", sa.String(64), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("granted_scopes_jsonb", sa.JSON, nullable=False, server_default="[]"),
        sa.Column("active_modules_jsonb", sa.JSON, nullable=False, server_default="[]"),
        sa.Column(
            "api_key_ref",
            sa.String(36),
            sa.ForeignKey("secrets_ref.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("last_seen", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_agent_registry_org_id", "agent_registry", ["org_id"])
    op.create_index(
        "ix_agent_registry_org_agent", "agent_registry", ["org_id", "agent_id"], unique=True
    )

    op.create_table(
        "agent_calls",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("org_id", sa.String(64), nullable=False),
        sa.Column("agent_id", sa.String(64), nullable=False),
        sa.Column("endpoint", sa.String(128), nullable=False),
        sa.Column("request_jsonb", sa.JSON, nullable=False),
        sa.Column("decision_id", sa.String(36), nullable=True),
        sa.Column("latency_ms", sa.Integer, nullable=False, server_default="0"),
        sa.Column("cost_usd", sa.Float, nullable=False, server_default="0"),
        sa.Column("outcome", sa.String(16), nullable=False),
        sa.Column(
            "timestamp",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_agent_calls_org_id", "agent_calls", ["org_id"])
    op.create_index("ix_agent_calls_agent_id", "agent_calls", ["agent_id"])
    op.create_index("ix_agent_calls_decision_id", "agent_calls", ["decision_id"])

    op.create_table(
        "channel_deliveries",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("org_id", sa.String(64), nullable=False),
        sa.Column("user_id", sa.String(64), nullable=False),
        sa.Column("channel", sa.String(16), nullable=False),
        sa.Column("insight_id", sa.String(36), nullable=True),
        sa.Column("decision_id", sa.String(36), nullable=True),
        sa.Column(
            "delivered_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("delivery_status", sa.String(16), nullable=False, server_default="sent"),
        sa.Column("error", sa.Text, nullable=True),
    )
    op.create_index("ix_channel_deliveries_org_id", "channel_deliveries", ["org_id"])
    op.create_index("ix_channel_deliveries_user_id", "channel_deliveries", ["user_id"])
    op.create_index("ix_channel_deliveries_insight_id", "channel_deliveries", ["insight_id"])

    op.create_table(
        "feedback_actions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("org_id", sa.String(64), nullable=False),
        sa.Column("user_id", sa.String(64), nullable=False),
        sa.Column("decision_id", sa.String(36), nullable=True),
        sa.Column("insight_id", sa.String(36), nullable=True),
        sa.Column("action", sa.String(16), nullable=False),
        sa.Column("edit_diff_jsonb", sa.JSON, nullable=True),
        sa.Column("correction_id", sa.String(36), nullable=True),
        sa.Column(
            "timestamp",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_feedback_actions_org_id", "feedback_actions", ["org_id"])
    op.create_index("ix_feedback_actions_user_id", "feedback_actions", ["user_id"])
    op.create_index("ix_feedback_actions_decision_id", "feedback_actions", ["decision_id"])
    op.create_index("ix_feedback_actions_insight_id", "feedback_actions", ["insight_id"])


def downgrade() -> None:
    op.drop_table("feedback_actions")
    op.drop_table("channel_deliveries")
    op.drop_table("agent_calls")
    op.drop_table("agent_registry")
