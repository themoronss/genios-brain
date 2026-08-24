"""Add mrr_snapshots — one row per active paying (external) org per calendar day,
recording that org's plan-derived MRR (INR/month) on that date.

WHY: exact retention metrics (NRR, GRR, expansion / contraction / churned MRR)
need the MRR of the SAME cohort at the START of a period compared to now. A
point-in-time snapshot can't produce those — you need history. This table is
that history. It is written idempotently (in-process, no Celery — Upstash
quota-safe) each time /v1/admin/metrics is read, so it self-populates.

Until ≥2 snapshot dates span the requested window, /admin/metrics returns
NRR/GRR as null (never faked). org_id is TEXT (cast from orgs.id) to match how
llm_costs stores it and to be type-agnostic on the join.

Revision ID: 0027_mrr_snapshots
Revises:    0026_org_is_internal
Create Date: 2026-07-02
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0027_mrr_snapshots"
down_revision: str | None = "0026_org_is_internal"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS mrr_snapshots (
            id            BIGSERIAL PRIMARY KEY,
            snapshot_date DATE        NOT NULL,
            org_id        TEXT        NOT NULL,
            tier          VARCHAR(32) NOT NULL,
            mrr_inr       INTEGER     NOT NULL DEFAULT 0,
            created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
            UNIQUE (snapshot_date, org_id)
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_mrr_snapshots_date "
        "ON mrr_snapshots (snapshot_date)"
    )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    op.execute("DROP TABLE IF EXISTS mrr_snapshots")
