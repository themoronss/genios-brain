"""Predicate registry — tracks distinct predicates seen across extraction,
per org. Lets ops/module-authors see what verbs the LLM actually emits so
they can standardize rules against the real vocabulary (the plan keeps
predicates open by design, so this is the consistency feedback loop).

  predicate_registry  — (org_id, predicate) → first_seen, last_seen, count

Cheap; updated lazily by the ingest path via an UPSERT.

Revision ID: 0018_predicate_registry
Revises:    0017_resource_uploads
Create Date: 2026-06-05
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0018_predicate_registry"
down_revision: str | None = "0017_resource_uploads"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS predicate_registry (
            id          BIGSERIAL PRIMARY KEY,
            org_id      VARCHAR(64) NOT NULL,
            predicate   VARCHAR(128) NOT NULL,
            occurrences INT NOT NULL DEFAULT 1,
            first_seen  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            last_seen   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT predicate_registry_org_pred_key UNIQUE (org_id, predicate)
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_predicate_registry_org_count "
        "ON predicate_registry (org_id, occurrences DESC)"
    )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    op.execute("DROP TABLE IF EXISTS predicate_registry")
