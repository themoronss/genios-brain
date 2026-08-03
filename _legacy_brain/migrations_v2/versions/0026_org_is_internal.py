"""Add orgs.is_internal — flags founder / test / demo accounts so they can be
EXCLUDED from every analytics metric (DAU/MAU, MRR, retention, funnels).

Without this, the team's own testing pollutes every number — the founder's own
Startup account shows up as ₹25k MRR and a daily-active account, etc. Analytics
that silently includes internal traffic is worse than none: it drives wrong
decisions. A PostHog cohort filters on this property so dashboards show real
customers only.

Defaults to FALSE → all existing rows + new real customers are 'external'. Mark
internal accounts explicitly:  UPDATE orgs SET is_internal = true WHERE id IN (...);

Revision ID: 0026_org_is_internal
Revises:    0025_subscription_processor
Create Date: 2026-06-25
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0026_org_is_internal"
down_revision: str | None = "0025_subscription_processor"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    op.execute(
        "ALTER TABLE orgs "
        "ADD COLUMN IF NOT EXISTS is_internal BOOLEAN NOT NULL DEFAULT false"
    )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    op.execute("ALTER TABLE orgs DROP COLUMN IF EXISTS is_internal")
