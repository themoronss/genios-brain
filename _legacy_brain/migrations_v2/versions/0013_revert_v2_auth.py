"""Revert v2 auth tables — v1 stack handles auth via orgs.password_hash.

v2's 0012 created `users`, `orgs`, `org_members`. v1 already had its own
orgs (with email/password_hash inline) + org_members + api_keys schema, and
those will be reinstated when v1 migrations are re-applied. To avoid table
name collisions we drop v2's auth tables here so v1 can recreate its versions
without conflict.

After this migration:
- Human auth is owned by v1 backend (POST /auth/login, /auth/register on v1)
- v2 brain only validates Bearer API keys (via SecretRef → AgentRegistry) +
  X-Dev-Org header
- The org_id string FK that v2 brain uses everywhere now points to v1's
  orgs.id (UUID) — no schema change needed since v2 brain treats org_id as
  a free-form string.

Revision ID: 0013_revert_v2_auth
Revises: 0012_auth
Create Date: 2026-06-03
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0013_revert_v2_auth"
down_revision: str | None = "0012_auth"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Drop in reverse-FK order
    op.execute("DROP TABLE IF EXISTS org_members CASCADE")
    op.execute("DROP TABLE IF EXISTS orgs CASCADE")
    op.execute("DROP TABLE IF EXISTS users CASCADE")


def downgrade() -> None:
    # Recreate the v2 auth tables (mirror of 0012). Used only if we ever
    # decide to swap auth back; v1 schema MUST be dropped first.
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
