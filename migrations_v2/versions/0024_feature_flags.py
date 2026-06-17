"""Re-create `feature_flags` — the emergency kill-switch table.

It was dropped in 0015 (v1 content cleanup), but app/api/deps.py:check_kill_switch()
still queries `SELECT enabled FROM feature_flags WHERE key='kill_switch_all'` on
every request. Missing table => the check throws (fails open, but logs a WARNING
on every request) AND the kill-switch safety feature is dead.

Re-create it (key, enabled). With no row present the check fails OPEN (requests
allowed) — same as today, but quiet. INSERT ('kill_switch_all', false) to take
the whole API offline in an emergency.

Revision ID: 0024_feature_flags
Revises:    0023_subscription_currency
Create Date: 2026-06-17
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0024_feature_flags"
down_revision: str | None = "0023_subscription_currency"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    op.execute(
        "CREATE TABLE IF NOT EXISTS feature_flags ("
        "  key VARCHAR(64) PRIMARY KEY,"
        "  enabled BOOLEAN NOT NULL DEFAULT TRUE,"
        "  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()"
        ")"
    )
    # Seed the kill switch as ON (enabled=true => requests allowed).
    op.execute(
        "INSERT INTO feature_flags (key, enabled) VALUES ('kill_switch_all', true) "
        "ON CONFLICT (key) DO NOTHING"
    )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    op.execute("DROP TABLE IF EXISTS feature_flags")
