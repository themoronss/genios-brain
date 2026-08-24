"""Add orgs.business_context — one-sentence org description used by the
LLM noise gate to decide what's relevant per vertical.

Without this column the gate either over-blocks (drops bank statements
for a fintech) or under-blocks (keeps bank statements for a sales SaaS).
Single short text field, set at signup and editable in Settings.

Revision ID: 0021_org_business_context
Revises:    0020_upload_status_partial
Create Date: 2026-06-10
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0021_org_business_context"
down_revision: str | None = "0020_upload_status_partial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    op.execute(
        "ALTER TABLE orgs "
        "ADD COLUMN IF NOT EXISTS business_context TEXT"
    )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    op.execute("ALTER TABLE orgs DROP COLUMN IF EXISTS business_context")
