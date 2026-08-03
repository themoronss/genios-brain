"""Make user_models uniqueness composite (user_id, org_unit).

The same email can be a member of multiple orgs and carry a separate
persona per org per the multi-tenant contract. The original schema had
a single-column UNIQUE on user_id which blocked the second org's seed
with a 500 IntegrityError, surfaced to the dashboard as
"profile belongs to a different org".

Drops user_models_user_id_key, adds user_models_user_id_org_unit_key.

Revision ID: 0016_user_model_org_scoped
Revises:    0015_drop_v1_content_tables
Create Date: 2026-06-04
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0016_user_model_org_scoped"
down_revision: str | None = "0015_drop_v1_content_tables"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    op.execute(
        "ALTER TABLE user_models DROP CONSTRAINT IF EXISTS user_models_user_id_key"
    )
    # The SQLAlchemy model also declared user_id as unique=True, which created
    # a separate UNIQUE INDEX (ix_user_models_user_id) that the ADD CONSTRAINT
    # above didn't touch. Drop it too, then add the composite unique.
    op.execute(
        "DROP INDEX IF EXISTS ix_user_models_user_id"
    )
    # Recreate user_id as a non-unique index so per-user lookups stay fast.
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_user_models_user_id ON user_models (user_id)"
    )
    op.execute(
        "ALTER TABLE user_models ADD CONSTRAINT user_models_user_id_org_unit_key "
        "UNIQUE (user_id, org_unit)"
    )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    op.execute(
        "ALTER TABLE user_models DROP CONSTRAINT IF EXISTS user_models_user_id_org_unit_key"
    )
    # Recreating the single-column unique would break the multi-tenant data
    # already present. Reject downgrade outright to avoid silent loss.
    raise NotImplementedError(
        "Downgrade not supported — restoring user_id UNIQUE would conflict "
        "with multi-tenant persona rows."
    )
