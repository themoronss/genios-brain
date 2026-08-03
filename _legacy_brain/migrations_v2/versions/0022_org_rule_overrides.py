"""Per-org rule threshold overrides — the calibration loop's write surface.

Phase 4 of the intelligence roadmap (g-i-8): module rules ship with global
default thresholds (eg. ar_firm_second_reminder fires on days_past_due > 7).
After we collect enough outcome attribution on a rule for a given org, the
threshold tuner can suggest a per-org override (eg. this customer's clients
actually need a nudge at 5 days, not 7) and write it here.

Every row carries provenance:
  * `source`        — who proposed it (tuner | ops | customer)
  * `justification` — human-readable reason audit can render
  * `sample_size`   — how many outcomes the tuner saw before recommending
  * `precision_*`   — before-vs-after precision the tuner observed
  * `status`        — pending | active | reverted | shadow

A `status=shadow` row records a suggestion that didn't meet the auto-apply
bar (improvement < 5% or sample < 20). It still surfaces in the dashboard
so the founder can opt in manually. `reverted` rows are kept (not deleted)
so the audit trail stays append-only.

Revision ID: 0022_org_rule_overrides
Revises:    0021_org_business_context
Create Date: 2026-06-12
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0022_org_rule_overrides"
down_revision: str | None = "0021_org_business_context"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS org_rule_overrides (
            id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            org_id          UUID NOT NULL,
            module_id       TEXT NOT NULL,
            rule_id         TEXT NOT NULL,
            fact_predicate  TEXT NOT NULL,
            op              TEXT NOT NULL DEFAULT '>',
            threshold_value DOUBLE PRECISION NOT NULL,
            status          TEXT NOT NULL DEFAULT 'shadow',
            source          TEXT NOT NULL DEFAULT 'tuner',
            justification   TEXT,
            sample_size     INTEGER,
            precision_before DOUBLE PRECISION,
            precision_after  DOUBLE PRECISION,
            applied_at      TIMESTAMPTZ,
            reverted_at     TIMESTAMPTZ,
            created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_org_rule_overrides_org_active
        ON org_rule_overrides (org_id, module_id, rule_id)
        WHERE status = 'active'
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_org_rule_overrides_created
        ON org_rule_overrides (org_id, created_at DESC)
        """
    )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    op.execute("DROP TABLE IF EXISTS org_rule_overrides")
