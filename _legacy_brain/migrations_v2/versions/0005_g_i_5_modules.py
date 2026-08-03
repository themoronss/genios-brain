"""g-i-5 module framework: modules + org_modules + module_activations_audit + module_golden_runs.

Revision ID: 0005_g_i_5_modules
Revises: 0004_g_i_2_decisions
Create Date: 2026-06-02

4 tables for per-org module activation + audit + golden-test record.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005_g_i_5_modules"
down_revision: str | None = "0004_g_i_2_decisions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "modules",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("module_id", sa.String(64), nullable=False),
        sa.Column("version", sa.String(32), nullable=False),
        sa.Column("manifest_jsonb", sa.JSON, nullable=False),
        sa.Column("golden_set_path", sa.String(255), nullable=False),
        sa.Column("active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("deactivated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_modules_module_version",
        "modules",
        ["module_id", "version"],
        unique=True,
    )

    op.create_table(
        "org_modules",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("org_id", sa.String(64), nullable=False),
        sa.Column(
            "module_pk",
            sa.String(36),
            sa.ForeignKey("modules.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("enabled", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("activated_by", sa.String(64), nullable=False),
        sa.Column(
            "activated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("deactivated_by", sa.String(64), nullable=True),
        sa.Column("deactivated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_org_modules_org_id", "org_modules", ["org_id"])
    op.create_index(
        "ix_org_modules_org_module", "org_modules", ["org_id", "module_pk"], unique=True
    )

    op.create_table(
        "module_activations_audit",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("org_id", sa.String(64), nullable=False),
        sa.Column("module_id", sa.String(64), nullable=False),
        sa.Column("version", sa.String(32), nullable=False),
        sa.Column("action", sa.String(16), nullable=False),
        sa.Column("actor", sa.String(64), nullable=False),
        sa.Column("reason", sa.Text, nullable=True),
        sa.Column(
            "timestamp",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_module_audit_org_id", "module_activations_audit", ["org_id"])

    op.create_table(
        "module_golden_runs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("module_id", sa.String(64), nullable=False),
        sa.Column("version", sa.String(32), nullable=False),
        sa.Column(
            "ran_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("passed", sa.Boolean, nullable=False),
        sa.Column("score", sa.Float, nullable=False),
        sa.Column("threshold", sa.Float, nullable=False),
        sa.Column("metrics_jsonb", sa.JSON, nullable=False),
    )
    op.create_index("ix_module_golden_runs_module_id", "module_golden_runs", ["module_id"])


def downgrade() -> None:
    op.drop_table("module_golden_runs")
    op.drop_table("module_activations_audit")
    op.drop_table("org_modules")
    op.drop_table("modules")
