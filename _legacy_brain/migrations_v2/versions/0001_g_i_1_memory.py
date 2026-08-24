"""g-i-1 memory layer: connections, secrets_ref, cursors, source_mappings, scope_grants.

Revision ID: 0001_g_i_1_memory
Revises:
Create Date: 2026-06-02

5 tables, all org-scoped. No content stored.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0001_g_i_1_memory"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "connections",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("org_id", sa.String(64), nullable=False),
        sa.Column("source_type", sa.String(64), nullable=False),
        sa.Column("source_id", sa.String(255), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("health_status", sa.String(16), nullable=False, server_default="green"),
        sa.Column("created_by", sa.String(64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("last_health_check_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text, nullable=True),
    )
    op.create_index("ix_connections_org_id", "connections", ["org_id"])
    op.create_index("ix_connections_org_source", "connections", ["org_id", "source_type"])

    op.create_table(
        "secrets_ref",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "connection_id",
            sa.String(36),
            sa.ForeignKey("connections.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("org_id", sa.String(64), nullable=False),
        sa.Column("secret_type", sa.String(32), nullable=False),
        sa.Column("encrypted_value", sa.Text, nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("rotated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_secrets_ref_connection_id", "secrets_ref", ["connection_id"])
    op.create_index("ix_secrets_ref_org_id", "secrets_ref", ["org_id"])

    op.create_table(
        "cursors",
        sa.Column(
            "connection_id",
            sa.String(36),
            sa.ForeignKey("connections.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("org_id", sa.String(64), nullable=False),
        sa.Column("cursor_value", sa.Text, nullable=False),
        sa.Column("strategy", sa.String(16), nullable=False),
        sa.Column(
            "last_sync_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("items_pulled_count", sa.Integer, nullable=False, server_default="0"),
    )
    op.create_index("ix_cursors_org_id", "cursors", ["org_id"])

    op.create_table(
        "source_mappings",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "connection_id",
            sa.String(36),
            sa.ForeignKey("connections.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("org_id", sa.String(64), nullable=False),
        sa.Column("mapping_json", sa.JSON, nullable=False),
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
        sa.Column("confirmed_by", sa.String(64), nullable=False),
        sa.Column(
            "confirmed_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("source_confidence", sa.Float, nullable=False, server_default="1.0"),
    )
    op.create_index("ix_source_mappings_connection_id", "source_mappings", ["connection_id"])
    op.create_index("ix_source_mappings_org_id", "source_mappings", ["org_id"])

    op.create_table(
        "scope_grants",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "connection_id",
            sa.String(36),
            sa.ForeignKey("connections.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("org_id", sa.String(64), nullable=False),
        sa.Column("scope_json", sa.JSON, nullable=False),
        sa.Column("granted_by", sa.String(64), nullable=False),
        sa.Column(
            "granted_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("scope_drops_count", sa.Integer, nullable=False, server_default="0"),
    )
    op.create_index("ix_scope_grants_connection_id", "scope_grants", ["connection_id"])
    op.create_index("ix_scope_grants_org_id", "scope_grants", ["org_id"])


def downgrade() -> None:
    op.drop_table("scope_grants")
    op.drop_table("source_mappings")
    op.drop_table("cursors")
    op.drop_table("secrets_ref")
    op.drop_table("connections")
