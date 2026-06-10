"""Rename v2 g-i-4 insights table to proactive_insights.

v1 has its own `insights` table (recommendations + detector fires). v2 g-i-4
also created an `insights` table for proactive engine output. Rename v2's so
v1 can recreate its native one without conflict.

Revision ID: 0014_rename_insights
Revises: 0013_revert_v2_auth
Create Date: 2026-06-03
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0014_rename_insights"
down_revision: str | None = "0013_revert_v2_auth"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Rename the table. Indices on the table get carried along by Postgres.
    op.execute("ALTER TABLE insights RENAME TO proactive_insights")
    # Some indexes were named with the `insights_` prefix — rename them too so
    # they stay descriptive after the table rename.
    op.execute(
        "ALTER INDEX IF EXISTS ix_insights_org_signature "
        "RENAME TO ix_proactive_insights_org_signature"
    )
    op.execute(
        "ALTER INDEX IF EXISTS ix_insights_org_created "
        "RENAME TO ix_proactive_insights_org_created"
    )


def downgrade() -> None:
    op.execute(
        "ALTER INDEX IF EXISTS ix_proactive_insights_org_created "
        "RENAME TO ix_insights_org_created"
    )
    op.execute(
        "ALTER INDEX IF EXISTS ix_proactive_insights_org_signature "
        "RENAME TO ix_insights_org_signature"
    )
    op.execute("ALTER TABLE proactive_insights RENAME TO insights")
