"""Resource-tab storage: file upload tracking + manual entry metadata.

Per g-i-1 thin pipe, the canonical facts/entities live in `facts` and
`graph_nodes` — extracted from each Resources entry via the emit() bus
+ ingest_subscriber. These two tables only hold what the UI needs that
the fact triples don't carry: file metadata + parse status for uploads,
and the original card fields (contact name, type, summary) for manual
entries.

  resource_uploads     — one row per file; status pipeline queued →
                         extracting → indexed / failed
  manual_entries       — one row per manual-context card the user typed
                         (the same content also lives as triples in
                         `facts` keyed by source_item_id)

Both are org-scoped + indexed on (org_id, uploaded/created_at DESC) so
the dashboard list views stay cheap.

Revision ID: 0017_resource_uploads
Revises:    0016_user_model_org_scoped
Create Date: 2026-06-05
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0017_resource_uploads"
down_revision: str | None = "0016_user_model_org_scoped"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS resource_uploads (
            id              UUID PRIMARY KEY,
            org_id          UUID NOT NULL REFERENCES orgs(id) ON DELETE CASCADE,
            agent_id        VARCHAR(64),
            file_name       VARCHAR(255) NOT NULL,
            file_type       VARCHAR(20),
            file_size_bytes BIGINT,
            storage_path    TEXT NOT NULL,
            tag             VARCHAR(50),
            status          VARCHAR(20) NOT NULL DEFAULT 'queued',
            error           TEXT,
            source_item_prefix VARCHAR(120) NOT NULL,
            facts_count     INT NOT NULL DEFAULT 0,
            entities_count  INT NOT NULL DEFAULT 0,
            uploaded_by     VARCHAR(255),
            uploaded_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            processed_at    TIMESTAMPTZ,
            CONSTRAINT resource_uploads_status_ck
                CHECK (status IN ('queued','extracting','indexed','failed'))
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_resource_uploads_org_uploaded "
        "ON resource_uploads (org_id, uploaded_at DESC)"
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS manual_entries (
            id              UUID PRIMARY KEY,
            org_id          UUID NOT NULL REFERENCES orgs(id) ON DELETE CASCADE,
            agent_id        VARCHAR(64),
            contact_name    VARCHAR(255),
            contact_email   VARCHAR(255),
            context_type    VARCHAR(50),
            interaction_date TIMESTAMPTZ,
            discussion      TEXT NOT NULL,
            commitments     TEXT,
            source_item_id  VARCHAR(120) NOT NULL UNIQUE,
            facts_count     INT NOT NULL DEFAULT 0,
            entities_count  INT NOT NULL DEFAULT 0,
            created_by      VARCHAR(255),
            created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_manual_entries_org_created "
        "ON manual_entries (org_id, created_at DESC)"
    )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    op.execute("DROP TABLE IF EXISTS manual_entries")
    op.execute("DROP TABLE IF EXISTS resource_uploads")
