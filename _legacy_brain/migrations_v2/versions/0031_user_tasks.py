"""User tasks — the Manager Mode ledger ("remember: msg Isha next week").

One row per task the founder gives GeniOS (or GeniOS extracts). The nag loop
reads open+overdue rows into the morning brief / extension Today section:
"you said you'd do this — N days, still not done."

Revision ID: 0031_user_tasks
Revises:    0030_signals
Create Date: 2026-07-23
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0031_user_tasks"
down_revision: str | None = "0030_signals"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


TABLE_SQL = """
CREATE TABLE IF NOT EXISTS user_tasks (
    id            TEXT PRIMARY KEY,
    org_id        VARCHAR(64) NOT NULL,
    user_id       VARCHAR(64),
    text          TEXT        NOT NULL,
    target_entity TEXT,
    due_at        TIMESTAMPTZ,
    status        VARCHAR(16) NOT NULL DEFAULT 'open',  -- open | done | snoozed | dropped
    source        VARCHAR(16) NOT NULL DEFAULT 'user',  -- user | auto
    snoozed_until TIMESTAMPTZ,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_user_tasks_org_status
    ON user_tasks (org_id, status, due_at);
"""


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    op.execute(TABLE_SQL)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS user_tasks")
