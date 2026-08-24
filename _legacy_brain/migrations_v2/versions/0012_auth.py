"""Human-user auth schema: users + orgs + org_members.

Revision ID: 0012_auth
Revises: 0011_org_tunables
Create Date: 2026-06-02
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0012_auth"
down_revision: str | None = "0011_org_tunables"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False, unique=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "orgs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column(
            "created_by_user_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("plan", sa.String(32), nullable=False, server_default="trial"),
        sa.Column("status", sa.String(16), nullable=False, server_default="active"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    op.create_table(
        "org_members",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "org_id",
            sa.String(36),
            sa.ForeignKey("orgs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("role", sa.String(16), nullable=False, server_default="member"),
        sa.Column(
            "joined_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("org_id", "user_id", name="uq_org_members_org_user"),
    )
    op.create_index("ix_org_members_org_id", "org_members", ["org_id"])
    op.create_index("ix_org_members_user", "org_members", ["user_id"])
    op.create_index("ix_org_members_user_id", "org_members", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_org_members_user_id", table_name="org_members")
    op.drop_index("ix_org_members_user", table_name="org_members")
    op.drop_index("ix_org_members_org_id", table_name="org_members")
    op.drop_table("org_members")
    op.drop_table("orgs")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
