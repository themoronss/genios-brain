"""Context page API — v2 thin-pipe sources.

All endpoints read from the v2 schema (facts, graph_nodes, graph_edges,
decisions, proactive_insights). The dropped v1 tables (contacts,
activity_log, commitments) are NOT touched.

  GET    /api/org/{id}/context/overview      health cards + activity stream
  GET    /api/org/{id}/facts                 list S-P-O facts
  GET    /api/org/{id}/facts/lifecycle       fact creation timeline
  GET    /api/org/{id}/commitments           open commitments derived from facts
  PATCH  /api/org/{id}/commitments/{cid}     mark fulfilled / not-a-commitment
"""

from __future__ import annotations

import json
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.deps import get_db

logger = logging.getLogger(__name__)
router = APIRouter()


# ── Tab 1: Context Overview ─────────────────────────────────────────────

@router.get("/api/org/{org_id}/context/overview")
def get_context_overview(org_id: str, db: Session = Depends(get_db)):
    """Health cards + recent activity stream for the Context page.

    v2 numbers:
      total_facts        — count of S-P-O facts asserted for this org
      avg_confidence     — mean facts.confidence (source-asserted = 1.0)
      facts_decaying     — count where confidence < 0.60 (Hebbian decay)
      conflicts_detected — count of distinct (subject, predicate) pairs that
                           have multiple distinct objects (contradictions)
    """
    totals = db.execute(
        text("""
            SELECT
                (SELECT COUNT(*) FROM facts WHERE org_id = :oid)                              AS total_facts,
                (SELECT AVG(confidence) FROM facts WHERE org_id = :oid)                       AS avg_conf,
                (SELECT COUNT(*) FROM facts WHERE org_id = :oid AND confidence < 0.60)        AS facts_decaying,
                (SELECT COUNT(*) FROM (
                    SELECT subject, predicate FROM facts
                    WHERE org_id = :oid
                    GROUP BY subject, predicate HAVING COUNT(DISTINCT object) > 1
                ) x)                                                                          AS conflicts
        """),
        {"oid": org_id},
    ).fetchone()

    # Recent ingest events derived from facts.created_at (latest 20 facts as
    # the activity stream — every fact corresponds to a memory event).
    events = db.execute(
        text("""
            SELECT subject, predicate, object, source_item_id, created_at
            FROM facts
            WHERE org_id = :oid
            ORDER BY created_at DESC
            LIMIT 20
        """),
        {"oid": org_id},
    ).fetchall()

    return {
        "health_cards": {
            "total_facts": int(totals[0] or 0),
            "avg_confidence": round(float(totals[1] or 0), 3),
            "facts_decaying": int(totals[2] or 0),
            "conflicts_detected": int(totals[3] or 0),
        },
        "recent_events": [
            {
                "event_type": "fact_asserted",
                "event_data": {
                    "subject": r[0],
                    "predicate": r[1],
                    "object": r[2],
                    "source": (r[3] or "").split(":")[0] if r[3] else "unknown",
                },
                "created_at": r[4].isoformat() if r[4] else None,
            }
            for r in events
        ],
    }


# ── Tab 2: Active Facts ─────────────────────────────────────────────────

@router.get("/api/org/{org_id}/facts")
def get_active_facts(
    org_id: str,
    fact_type: str | None = None,
    min_score: float = 0.0,  # accepted for back-compat; v2 facts don't carry composite score
    entity_name: str | None = None,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
    request: Request = None,
):
    """v2 S-P-O facts list — scope-enforced if a per-agent policy is attached
    to the caller's API key (via `agent_scopes.policy_json`)."""
    from core.api.deps import require_org_and_policy
    from core.foundations.db import get_session as _v2s
    from core.graph.views import list_facts as _v2_list_facts

    # Resolve scope via core.api.deps so this endpoint honors both v1 dashboard
    # JWT (unrestricted) AND scoped Bearer api_keys.
    ctx = require_org_and_policy(request=request, session=db,
                                  authorization=request.headers.get("authorization"),
                                  x_dev_org=request.headers.get("X-Dev-Org"))
    if ctx["org_id"] != org_id:
        raise HTTPException(status_code=403, detail="cross-org access denied")

    with _v2s() as s:
        return _v2_list_facts(
            s,
            org_id=org_id,
            subject=entity_name,
            predicate=fact_type,
            policy=ctx.get("policy"),
            limit=limit,
            offset=offset,
        )


# ── Tab 3: Lifecycle ─────────────────────────────────────────────────────

@router.get("/api/org/{org_id}/facts/lifecycle")
def get_lifecycle_activity(
    org_id: str,
    entity_name: Optional[str] = None,
    event_type: Optional[str] = None,
    limit: int = 50,
    db: Session = Depends(get_db),
):
    """Timeline of fact + node lifecycle events.

    v2 doesn't have a dedicated activity_log; we derive the timeline from
    facts (creation) + graph_nodes (first_seen / last_seen) joined by entity.
    """
    where = ["org_id = :org_id"]
    params: dict = {"org_id": org_id, "limit": limit}
    if entity_name:
        where.append("(subject = :ent OR object = :ent)")
        params["ent"] = entity_name

    where_sql = " AND ".join(where)

    rows = db.execute(
        text(f"""
            SELECT subject, predicate, object, source_item_id, confidence, created_at
            FROM facts
            WHERE {where_sql}
            ORDER BY created_at DESC
            LIMIT :limit
        """),
        params,
    ).fetchall()

    return {
        "events": [
            {
                "event_type": "fact_created",
                "event_data": {
                    "subject": r[0],
                    "predicate": r[1],
                    "object": r[2],
                    "source": (r[3] or "").split(":")[0] if r[3] else "unknown",
                    "confidence": float(r[4] or 0),
                },
                "created_at": r[5].isoformat() if r[5] else None,
            }
            for r in rows
        ],
    }


# ── Tab 4: Commitments ───────────────────────────────────────────────────

@router.get("/api/org/{org_id}/commitments")
def get_commitments(
    org_id: str,
    status: Optional[str] = None,
    limit: int = 50,
    db: Session = Depends(get_db),
):
    """Commitments derived from v2 facts where predicate is action-shaped
    (committed_to / will_do / promised / agreed_to / follow_up / scheduled).

    v1 had a dedicated `commitments` table; v2 surfaces them straight from
    the same fact triples the engine uses, so there's no drift.
    """
    COMMIT_PREDS = (
        "committed_to", "will_do", "promised", "agreed_to",
        "follow_up", "scheduled", "due", "should_do",
    )
    rows = db.execute(
        text("""
            SELECT id, subject, object, predicate, source_item_id, confidence, created_at
            FROM facts
            WHERE org_id = :oid
              AND predicate = ANY(:preds)
            ORDER BY created_at DESC
            LIMIT :limit
        """),
        {"oid": org_id, "preds": list(COMMIT_PREDS), "limit": limit},
    ).fetchall()

    items = []
    for r in rows:
        items.append({
            "id": str(r[0]),
            "text": f"{r[1]} {r[3].replace('_', ' ')} {r[2]}",
            "owner": r[1],
            "status": "open",  # v2 doesn't track fulfillment yet; UI may flip via PATCH
            "due_date": None,
            "created_at": r[6].isoformat() if r[6] else None,
            "contact_name": r[1],
            "company": None,
            "priority": "normal",
            "is_blocker": False,
            "is_overdue": False,
            "days_overdue": 0,
            "source": (r[4] or "").split(":")[0] if r[4] else "unknown",
        })

    # Honor optional status filter the frontend may send.
    if status:
        items = [c for c in items if c["status"] == status]

    return {
        "overdue": [c for c in items if c["is_overdue"]],
        "open":     [c for c in items if c["status"] == "open" and not c["is_overdue"]],
        "fulfilled":[c for c in items if c["status"] == "fulfilled"],
        "total": len(items),
    }


class CommitmentUpdate(BaseModel):
    status: Optional[str] = None
    due_date: Optional[str] = None


@router.patch("/api/org/{org_id}/commitments/{commitment_id}")
def update_commitment(org_id: str, commitment_id: str, update: CommitmentUpdate,
                      db: Session = Depends(get_db)):
    """Mark a commitment-shaped fact fulfilled or not-a-commitment.

    v2 stores this as an `insight_feedback` row (signature_hash = fact id) so
    the engine knows to suppress / re-rank that triple in future decisions.
    """
    sig = commitment_id  # use the fact id as the suppression key
    db.execute(
        text("""
            INSERT INTO insight_feedback (id, org_id, user_id, signature_hash, action, created_at)
            VALUES (gen_random_uuid()::text, :oid, :uid, :sig, :a, NOW())
        """),
        {"oid": org_id, "uid": "__org__", "sig": sig,
         "a": "acted" if update.status == "fulfilled" else "dismissed"},
    )
    db.commit()
    return {"updated": True, "commitment_id": commitment_id}
