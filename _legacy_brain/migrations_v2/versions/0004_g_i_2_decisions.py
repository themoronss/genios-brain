"""g-i-2 decisions table.

Revision ID: 0004_g_i_2_decisions
Revises: 0003_g_i_3_worldmodel
Create Date: 2026-06-02

One row per emitted Decision. Used by:
- g-i-7 delivery (read decision_id -> envelope)
- g-i-2 replay (re-run symbolic chain at as_of_version)
- g-i-8 intervention_rate metric (route distribution per org per day)

NOTE: llm_costs table NOT created here — per Group 1 lock, cost tracking lives
in Redis (atomic INCRBY with daily TTL). DB table only added if persistent
ledger demanded later.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004_g_i_2_decisions"
down_revision: str | None = "0003_g_i_3_worldmodel"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "decisions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("org_id", sa.String(64), nullable=False),
        sa.Column("query_jsonb", sa.JSON, nullable=False),
        sa.Column("conclusion", sa.Text, nullable=False),
        sa.Column("derivation_chain_jsonb", sa.JSON, nullable=False),
        sa.Column("path", sa.String(16), nullable=False),
        sa.Column("confidence_score", sa.Float, nullable=False),
        sa.Column("confidence_breakdown_jsonb", sa.JSON, nullable=False),
        sa.Column("grounding_refs_jsonb", sa.JSON, nullable=False, server_default="[]"),
        sa.Column("route", sa.String(16), nullable=False),
        sa.Column("as_of_version", sa.BigInteger, nullable=False, server_default="0"),
        sa.Column("triggered_by", sa.String(16), nullable=False, server_default="query"),
        sa.Column("module_id", sa.String(64), nullable=True),
        sa.Column("user_id", sa.String(64), nullable=True),
        sa.Column("agent_id", sa.String(64), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_decisions_org_id", "decisions", ["org_id"])
    op.create_index("ix_decisions_org_created", "decisions", ["org_id", "created_at"])
    op.create_index("ix_decisions_org_route", "decisions", ["org_id", "route"])
    op.create_index("ix_decisions_org_module", "decisions", ["org_id", "module_id"])


def downgrade() -> None:
    op.drop_table("decisions")
