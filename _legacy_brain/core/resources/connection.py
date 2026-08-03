"""Ensure a per-org `connections` row exists for `manual` / `upload` sources.

ingest_subscriber resolves `org_id` from `connections.source_id` (the OAuth
adapters use addresses / workspace ids as source_id). Resources entries
don't come from any external system — we coin a synthetic source_id per
org per type so the ingest path still finds an org_id without special-
casing.

Idempotent: called on every write; a single INSERT ... ON CONFLICT
DO NOTHING keeps it cheap.
"""

from __future__ import annotations

import uuid

from sqlalchemy import text
from sqlalchemy.orm import Session


def synthetic_source_id(*, source_type: str, org_id: str) -> str:
    """The source_id we use for emit() so ingest_subscriber resolves org_id."""
    return f"{source_type}:{org_id}"


def ensure_resource_connection(session: Session, *, org_id: str, source_type: str) -> str:
    """Make sure (org, source_type) has a connection row. Returns the source_id.

    `source_type` must be one of: 'manual', 'upload'.
    """
    if source_type not in ("manual", "upload"):
        raise ValueError(f"unsupported resource source_type: {source_type}")
    src_id = synthetic_source_id(source_type=source_type, org_id=org_id)
    # created_by is NOT NULL on the connections table — for synthetic
    # Resources connections there's no human installer, so we stamp the
    # actor as 'system' (the row is owned by the org, not a person).
    session.execute(
        text(
            """
            INSERT INTO connections
              (id, org_id, source_type, source_id, status, health_status,
               created_by, created_at)
            VALUES
              (:id, :org_id, :stype, :sid, 'active', 'healthy',
               'system', NOW())
            ON CONFLICT DO NOTHING
            """
        ),
        {
            "id": str(uuid.uuid4()),
            "org_id": org_id,
            "stype": source_type,
            "sid": src_id,
        },
    )
    return src_id
