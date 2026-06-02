"""Per-org tunable overrides table.

Revision ID: 0011_org_tunables
Revises: 0010_g_i_8_foundations
Create Date: 2026-06-02
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0011_org_tunables"
down_revision: str | None = "0010_g_i_8_foundations"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "org_tunables",
        sa.Column("org_id", sa.String(64), primary_key=True),
        sa.Column("key", sa.String(64), primary_key=True),
        sa.Column("value_jsonb", sa.JSON, nullable=False),
        sa.Column("set_by", sa.String(128), nullable=False),
        sa.Column(
            "set_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("reason", sa.String(255), nullable=True),
        sa.UniqueConstraint("org_id", "key", name="uq_org_tunables_org_key"),
    )
    op.create_index("ix_org_tunables_org", "org_tunables", ["org_id"])


def downgrade() -> None:
    op.drop_index("ix_org_tunables_org", table_name="org_tunables")
    op.drop_table("org_tunables")
