"""
GET /v1/messages/search — user-side message search.

Answers "what have I sent lately about X?" across the org's own interactions.
Scoped strictly to the caller's org_id (enforced at SQL); respects contact
disclosure_level the same way bundle builder does.

Flag-gated via GENIOS_SEARCH_MESSAGES_API_ENABLED. When disabled the route
returns 503 so consumers can detect rollout state.
"""

import logging
import os
from typing import Optional, List, Dict

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.deps import get_db, verify_api_key

logger = logging.getLogger(__name__)
router = APIRouter()


def _enabled() -> bool:
    return os.getenv("GENIOS_SEARCH_MESSAGES_API_ENABLED", "false").lower() in ("1", "true", "yes")


@router.get("/v1/messages/search")
def search_messages(
    q: Optional[str] = Query(None, description="Keyword/phrase — matches subject + body via full-text."),
    direction: Optional[str] = Query(None, description="outbound | inbound. Omit for both."),
    days: int = Query(14, ge=1, le=365, description="Recency window in days."),
    limit: int = Query(10, ge=1, le=50),
    contact_id: Optional[str] = Query(None, description="Scope to a single contact."),
    db: Session = Depends(get_db),
    org_id: str = Depends(verify_api_key),
) -> Dict:
    """
    Hybrid search over interactions table:
      - if `q` provided: ts_rank over search_tsv (migration 063 FTS column)
      - otherwise: recency-ordered listing with filters applied

    Result rows are privacy-filtered (disclosure_level='public' only).
    """
    if not _enabled():
        raise HTTPException(
            status_code=503,
            detail={"error": "FEATURE_DISABLED", "message": "messages.search is not enabled for this deployment."},
        )

    if direction and direction not in ("outbound", "inbound"):
        raise HTTPException(
            status_code=400,
            detail={"error": "INVALID_DIRECTION", "message": "direction must be 'outbound' or 'inbound'."},
        )

    use_fts = bool(q and q.strip())
    params: Dict = {
        "org_id": org_id,
        "days": str(days),
        "limit": limit,
        "direction": direction,
        "contact_id": contact_id,
    }

    if use_fts:
        params["q"] = q.strip()
        sql = """
            SELECT
                i.id, i.contact_id, c.name AS contact_name,
                i.subject, i.raw_snippet, i.summary, i.topics,
                i.direction, i.interaction_at,
                ts_rank(i.search_tsv, plainto_tsquery('english', :q)) AS rank
            FROM interactions i
            JOIN contacts c ON c.id = i.contact_id
            WHERE i.org_id = :org_id
              AND i.interaction_at > NOW() - (:days || ' days')::interval
              AND (:direction IS NULL OR i.direction = :direction)
              AND (:contact_id IS NULL OR i.contact_id = CAST(:contact_id AS uuid))
              AND COALESCE(c.disclosure_level, 'public') = 'public'
              AND i.search_tsv @@ plainto_tsquery('english', :q)
            ORDER BY rank DESC, i.interaction_at DESC
            LIMIT :limit
        """
    else:
        sql = """
            SELECT
                i.id, i.contact_id, c.name AS contact_name,
                i.subject, i.raw_snippet, i.summary, i.topics,
                i.direction, i.interaction_at,
                NULL::float AS rank
            FROM interactions i
            JOIN contacts c ON c.id = i.contact_id
            WHERE i.org_id = :org_id
              AND i.interaction_at > NOW() - (:days || ' days')::interval
              AND (:direction IS NULL OR i.direction = :direction)
              AND (:contact_id IS NULL OR i.contact_id = CAST(:contact_id AS uuid))
              AND COALESCE(c.disclosure_level, 'public') = 'public'
            ORDER BY i.interaction_at DESC
            LIMIT :limit
        """

    try:
        rows = db.execute(text(sql), params).fetchall()
    except Exception as e:
        logger.warning(f"messages.search query failed: {e}")
        try:
            db.rollback()
        except Exception:
            pass
        raise HTTPException(
            status_code=500,
            detail={"error": "QUERY_FAILED", "message": "Search query failed."},
        )

    results: List[Dict] = []
    for r in rows:
        excerpt_src = r.raw_snippet or r.summary or ""
        excerpt = excerpt_src[:300].strip()
        if len(excerpt_src) > 300:
            excerpt += "…"
        results.append({
            "id": str(r.id) if r.id else None,
            "contact_id": str(r.contact_id) if r.contact_id else None,
            "contact_name": r.contact_name,
            "subject": r.subject,
            "excerpt": excerpt,
            "topics": list(r.topics or []),
            "direction": r.direction,
            "interaction_at": r.interaction_at.isoformat() if r.interaction_at else None,
            "rank": float(r.rank) if r.rank is not None else None,
        })

    return {
        "query": q,
        "direction": direction,
        "days": days,
        "count": len(results),
        "results": results,
    }
