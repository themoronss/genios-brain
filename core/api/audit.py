"""Audit log read-side route.

GET /v1/audit/events    paginated audit query with filters
GET /v1/audit/actions   list of action types the backend currently emits

Audit rows are immutable + always org-scoped. The trigger blocks UPDATE/DELETE
at the DB layer; this route only reads.
"""

from __future__ import annotations

import typing
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from core.api.deps import db_session, require_org
from core.foundations import audit

router = APIRouter(prefix="/v1/audit", tags=["audit"])


@router.get("/actions")
def list_action_types() -> list[str]:
    """Return every action string the backend may emit (the Action Literal).

    The dashboard's filter dropdown reads this so it stays in sync with the
    backend: add a new action to core.foundations.audit.Action and it shows
    up in the UI on the next page load — no frontend deploy needed.
    """
    return list(typing.get_args(audit.Action))


@router.get("/events")
def list_events(
    action: str | None = Query(default=None),
    target_type: str | None = Query(default=None),
    target_id: str | None = Query(default=None),
    actor_id: str | None = Query(default=None),
    since: datetime | None = Query(default=None),
    until: datetime | None = Query(default=None),
    limit: int = Query(default=200, ge=1, le=1000),
    org_id: str = Depends(require_org),
    session: Session = Depends(db_session),
) -> list[dict[str, Any]]:
    rows = audit.query_events(
        session,
        org_id=org_id,
        action=action,  # type: ignore[arg-type]
        target_type=target_type,
        target_id=target_id,
        actor_id=actor_id,
        since=since,
        until=until,
        limit=limit,
    )
    return [
        {
            "id": r.id,
            "actor_type": r.actor_type,
            "actor_id": r.actor_id,
            "action": r.action,
            "target_type": r.target_type,
            "target_id": r.target_id,
            "metadata": r.metadata_jsonb,
            "timestamp": r.timestamp.isoformat(),
        }
        for r in rows
    ]
