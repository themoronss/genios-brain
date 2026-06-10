"""g-i-9 user model: user_models + user_model_edits + user_model_proposals.

Revision ID: 0008_g_i_9_usermodel
Revises: 0007_g_i_6_artifacts
Create Date: 2026-06-02
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0008_g_i_9_usermodel"
down_revision: str | None = "0007_g_i_6_artifacts"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "user_models",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(64), nullable=False, unique=True),
        sa.Column("org_unit", sa.String(64), nullable=False),
        sa.Column("voice_jsonb", sa.JSON, nullable=False, server_default="{}"),
        sa.Column("decision_policy_jsonb", sa.JSON, nullable=False, server_default="{}"),
        sa.Column("process_habits_jsonb", sa.JSON, nullable=False, server_default="{}"),
        sa.Column("priorities_jsonb", sa.JSON, nullable=False, server_default="{}"),
        sa.Column("relationships_jsonb", sa.JSON, nullable=False, server_default="{}"),
        sa.Column("red_lines_jsonb", sa.JSON, nullable=False, server_default="[]"),
        sa.Column("field_meta_jsonb", sa.JSON, nullable=False, server_default="{}"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_user_models_user_id", "user_models", ["user_id"], unique=True)
    op.create_index("ix_user_models_org_unit", "user_models", ["org_unit"])

    op.create_table(
        "user_model_edits",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(64), nullable=False),
        sa.Column("field", sa.String(64), nullable=False),
        sa.Column("edit_diff_jsonb", sa.JSON, nullable=False),
        sa.Column("source_correction_id", sa.String(36), nullable=True),
        sa.Column("applied", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_user_model_edits_user_id", "user_model_edits", ["user_id"])
    op.create_index(
        "ix_user_model_edits_user_field", "user_model_edits", ["user_id", "field"]
    )

    op.create_table(
        "user_model_proposals",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(64), nullable=False),
        sa.Column("field", sa.String(64), nullable=False),
        sa.Column("current_value_jsonb", sa.JSON, nullable=False),
        sa.Column("proposed_value_jsonb", sa.JSON, nullable=False),
        sa.Column("signal_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("rationale", sa.Text, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decided_by", sa.String(64), nullable=True),
    )
    op.create_index("ix_user_model_proposals_user_id", "user_model_proposals", ["user_id"])


def downgrade() -> None:
    op.drop_table("user_model_proposals")
    op.drop_table("user_model_edits")
    op.drop_table("user_models")
