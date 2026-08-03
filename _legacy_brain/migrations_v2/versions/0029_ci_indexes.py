"""Case-insensitive functional indexes for context/search lookups.

WHY: `/v1/context` fact lookups and entity resolution match `LOWER(subject)` /
`LOWER(canonical_name)` (case + alias insensitive — see the context.py subject
casing fix), but the existing btree indexes are case-sensitive, so these lookups
sequential-scan the org's rows. Fine at small scale, slow at enterprise graph
size. Functional indexes on the lowercased expression let Postgres use an index
for the case-insensitive `= ANY` / `=` lookups.

Revision ID: 0029_ci_indexes
Revises:    0028_integration_configs
Create Date: 2026-07-06
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0029_ci_indexes"
down_revision: str | None = "0028_integration_configs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_facts_org_lower_subject "
        "ON facts (org_id, LOWER(subject))"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_nodes_org_lower_canonical "
        "ON graph_nodes (org_id, LOWER(canonical_name))"
    )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    op.execute("DROP INDEX IF EXISTS ix_facts_org_lower_subject")
    op.execute("DROP INDEX IF EXISTS ix_nodes_org_lower_canonical")
