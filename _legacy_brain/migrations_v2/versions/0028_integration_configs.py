"""Add integration_configs — per-org, per-tool UI settings (sync prefs, domain
filters, etc.) saved from the Integrations page.

WHY: the dashboard's "Save changes" on a tool (e.g. Gmail) PUT
/api/org/{org}/integrations/{tool}/config — a route that did not exist, so every
save 404'd with a red "Failed to save settings" toast. This lightweight JSON
store lets the save succeed and persist; the sync layer can later honour these
settings. Keyed (org_id, tool) so one row per tool per org, upserted.

Revision ID: 0028_integration_configs
Revises:    0027_mrr_snapshots
Create Date: 2026-07-06
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0028_integration_configs"
down_revision: str | None = "0027_mrr_snapshots"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS integration_configs (
            org_id      VARCHAR(64)  NOT NULL,
            tool        VARCHAR(64)  NOT NULL,
            config      JSONB        NOT NULL DEFAULT '{}'::jsonb,
            updated_at  TIMESTAMPTZ  NOT NULL DEFAULT now(),
            PRIMARY KEY (org_id, tool)
        )
        """
    )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    op.execute("DROP TABLE IF EXISTS integration_configs")
