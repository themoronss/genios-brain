"""Allow status='partial' on resource_uploads so the upload path can flag
a file that exhausted credits mid-extraction.

Previously the CHECK constraint only knew (queued|extracting|indexed|
failed). Once per-chunk billing lands, an upload can legitimately end up
in a state where some chunks landed and the rest didn't because the org
ran out of credits — that's not 'failed' (the file parsed fine, our
billing layer stopped us mid-flight) and it's not 'indexed' (we didn't
finish). 'partial' carries that meaning + the error column tells the
user how to recover.

Revision ID: 0020_upload_status_partial
Revises:    0019_llm_costs
Create Date: 2026-06-09
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0020_upload_status_partial"
down_revision: str | None = "0019_llm_costs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    op.execute(
        "ALTER TABLE resource_uploads "
        "DROP CONSTRAINT IF EXISTS resource_uploads_status_ck"
    )
    op.execute(
        "ALTER TABLE resource_uploads "
        "ADD CONSTRAINT resource_uploads_status_ck "
        "CHECK (status IN ('queued','extracting','indexed','failed','partial'))"
    )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    op.execute(
        "ALTER TABLE resource_uploads "
        "DROP CONSTRAINT IF EXISTS resource_uploads_status_ck"
    )
    op.execute(
        "ALTER TABLE resource_uploads "
        "ADD CONSTRAINT resource_uploads_status_ck "
        "CHECK (status IN ('queued','extracting','indexed','failed'))"
    )
