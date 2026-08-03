"""Signal Layer — derived, typed, temporal signals about graph nodes.

Foundation of the 2nd-brain intelligence (INTELLIGENCE_2ND_BRAIN_PLAN.md +
INTELLIGENCE_PHASE_A_SIGNALS.md). A `signal` is a typed, provenance-linked,
optionally-decaying value about a subject node — ball_in_court, momentum,
importance, sentiment, buying_intent, stage, domain, ... — computed by symbolic
detectors (on tick) or neural ones (cached from the ingest extract() call).

Current-value-only: one row per (org, subject, signal_type), detectors UPSERT.
History is a later phase. Decay (half_life_days) is applied on read.

NOTE: down_revision is 0029_ci_indexes (the real head) — NOT 0027 as the older
draft plan said; 0028/0029 were already taken by other migrations.

Revision ID: 0030_signals
Revises:    0029_ci_indexes
Create Date: 2026-07-17
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0030_signals"
down_revision: str | None = "0029_ci_indexes"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS signals (
            id               TEXT PRIMARY KEY,
            org_id           VARCHAR(64)  NOT NULL,
            subject_node_id  VARCHAR(36)  NOT NULL,
            subject_name     VARCHAR(255) NOT NULL,
            signal_type      VARCHAR(64)  NOT NULL,
            value_num        DOUBLE PRECISION,
            value_cat        VARCHAR(64),
            confidence       DOUBLE PRECISION NOT NULL DEFAULT 1.0,
            produced_by      VARCHAR(128) NOT NULL,
            evidence         JSONB NOT NULL DEFAULT '[]'::jsonb,
            as_of_version    BIGINT,
            half_life_days   DOUBLE PRECISION,
            computed_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT uq_signals_subject_type
                UNIQUE (org_id, subject_node_id, signal_type)
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_signals_org_subject "
        "ON signals (org_id, subject_node_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_signals_org_type "
        "ON signals (org_id, signal_type)"
    )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    op.execute("DROP TABLE IF EXISTS signals")
