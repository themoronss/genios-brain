"""Add `processor` to subscriptions so we can route payments per region:
India → Razorpay (UPI, no forex), international → Stripe (cards). The column
disambiguates which gateway owns a row's order_id/payment_id.

Defaults to 'razorpay' so every existing row + the domestic path is unchanged.

Revision ID: 0025_subscription_processor
Revises:    0024_feature_flags
Create Date: 2026-06-20
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0025_subscription_processor"
down_revision: str | None = "0024_feature_flags"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    op.execute(
        "ALTER TABLE subscriptions "
        "ADD COLUMN IF NOT EXISTS processor VARCHAR(16) NOT NULL DEFAULT 'razorpay'"
    )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    op.execute("ALTER TABLE subscriptions DROP COLUMN IF EXISTS processor")
