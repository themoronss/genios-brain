"""Add `currency` to subscriptions so plan/top-up orders can be charged in the
customer's currency — INR for India (UPI works, no forex), USD for international
(Razorpay International settles INR to us). We DISPLAY USD for positioning but
SETTLE INR either way.

Defaults to 'INR' so every existing row + the domestic path is unchanged.

Revision ID: 0023_subscription_currency
Revises:    0022_org_rule_overrides
Create Date: 2026-06-17
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0023_subscription_currency"
down_revision: str | None = "0022_org_rule_overrides"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    op.execute(
        "ALTER TABLE subscriptions "
        "ADD COLUMN IF NOT EXISTS currency VARCHAR(3) NOT NULL DEFAULT 'INR'"
    )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    op.execute("ALTER TABLE subscriptions DROP COLUMN IF EXISTS currency")
