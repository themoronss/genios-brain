"""Predicate registry read API.

GET /v1/predicates   distinct predicates seen for this org + occurrence count

Plan keeps the predicate vocabulary open by design (no enum). The registry
is the feedback loop: module authors check what verbs the LLM actually
emits for their data, then write rules against the real vocabulary
instead of guessing.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.orm import Session

from core.api.deps import db_session, require_org

router = APIRouter(prefix="/v1/predicates", tags=["predicates"])


@router.get("")
def list_predicates(
    limit: int = Query(default=100, ge=1, le=1000),
    org_id: str = Depends(require_org),
    session: Session = Depends(db_session),
) -> dict:
    rows = session.execute(
        text(
            """
            SELECT predicate, occurrences,
                   first_seen, last_seen
            FROM predicate_registry
            WHERE org_id = :org
            ORDER BY occurrences DESC
            LIMIT :lim
            """
        ),
        {"org": org_id, "lim": limit},
    ).fetchall()
    total_predicates = session.execute(
        text("SELECT COUNT(*) FROM predicate_registry WHERE org_id = :org"),
        {"org": org_id},
    ).scalar() or 0
    total_occurrences = session.execute(
        text("SELECT COALESCE(SUM(occurrences),0) FROM predicate_registry WHERE org_id = :org"),
        {"org": org_id},
    ).scalar() or 0
    return {
        "predicates": [
            {
                "predicate": r.predicate,
                "occurrences": r.occurrences,
                "first_seen": r.first_seen.isoformat() if r.first_seen else None,
                "last_seen":  r.last_seen.isoformat()  if r.last_seen else None,
            }
            for r in rows
        ],
        "total_distinct": total_predicates,
        "total_occurrences": total_occurrences,
    }
