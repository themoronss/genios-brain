"""
Precedent Graph API — PDF spec: Past decisions + outcomes for pattern matching.

Stores what was done in past situations and what happened.
After 200+ precedents, enables pattern matching to guide future actions.
12-month decay: precedents older than 12 months get lower weight.

Endpoints:
  POST /v1/precedent/{org_id}              — record a new precedent/decision
  GET  /v1/precedent/{org_id}              — list precedents (filtered)
  GET  /v1/precedent/{org_id}/match        — find similar precedents for a situation
  PATCH /v1/precedent/{org_id}/{id}/outcome — record outcome of a decision
  GET  /v1/precedent/{org_id}/stats        — summary stats
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.database import SessionLocal
from datetime import datetime, timezone
from typing import Optional, List
import uuid

router = APIRouter()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ── Pydantic Models ────────────────────────────────────────────────────────

class CreatePrecedentRequest(BaseModel):
    situation_type: str           # "investor_followup", "cold_reactivation", etc.
    context_summary: Optional[str] = None
    action_taken: str
    related_tags: Optional[List[str]] = None
    contact_id: Optional[str] = None


class RecordOutcomeRequest(BaseModel):
    outcome_type: str             # "positive", "negative", "neutral"
    outcome_quality: float        # -1.0 to 1.0
    approval_status: str = "approved"


# ── Decay weight computation ──────────────────────────────────────────────

def _compute_decay_weight(created_at) -> float:
    """PDF spec: 12-month decay formula: 0.5 ^ (months_ago / 12)"""
    if not created_at:
        return 1.0
    now = datetime.now(timezone.utc)
    if hasattr(created_at, 'replace'):
        created_at = created_at.replace(tzinfo=timezone.utc)
    months_ago = (now - created_at).days / 30.0
    return 0.5 ** (months_ago / 12.0)


# ── Routes ─────────────────────────────────────────────────────────────────

@router.post("/v1/precedent/{org_id}")
def record_precedent(org_id: str, req: CreatePrecedentRequest, db: Session = Depends(get_db)):
    """Record a new decision/action as a precedent."""
    pid = str(uuid.uuid4())
    try:
        db.execute(
            text("""
                INSERT INTO precedent_graph
                    (id, org_id, situation_type, context_summary, action_taken,
                     related_tags, contact_id, decay_weight)
                VALUES (:id, :org_id, :situation_type, :context_summary, :action_taken,
                        :related_tags, :contact_id, 1.0)
            """),
            {
                "id": pid,
                "org_id": org_id,
                "situation_type": req.situation_type,
                "context_summary": req.context_summary,
                "action_taken": req.action_taken,
                "related_tags": req.related_tags or [],
                "contact_id": req.contact_id,
            }
        )
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

    return {"id": pid, "status": "recorded"}


@router.get("/v1/precedent/{org_id}")
def list_precedents(
    org_id: str,
    situation_type: Optional[str] = Query(None),
    outcome_type: Optional[str] = Query(None),
    limit: int = Query(20, le=100),
    db: Session = Depends(get_db),
):
    """List precedents with optional filters."""
    filters = ["org_id = :org_id"]
    params = {"org_id": org_id, "limit": limit}

    if situation_type:
        filters.append("situation_type = :situation_type")
        params["situation_type"] = situation_type

    if outcome_type:
        filters.append("outcome_type = :outcome_type")
        params["outcome_type"] = outcome_type

    where = " AND ".join(filters)

    rows = db.execute(
        text(f"""
            SELECT id, situation_type, context_summary, action_taken,
                outcome_type, outcome_quality, decay_weight, related_tags,
                created_at, outcome_recorded_at
            FROM precedent_graph
            WHERE {where}
            ORDER BY decay_weight DESC, created_at DESC
            LIMIT :limit
        """),
        params
    ).fetchall()

    return {"precedents": [
        {
            "id": str(r[0]),
            "situation_type": r[1],
            "context_summary": r[2],
            "action_taken": r[3],
            "outcome_type": r[4],
            "outcome_quality": float(r[5]) if r[5] is not None else None,
            "decay_weight": float(r[6]) if r[6] is not None else 1.0,
            "related_tags": r[7] or [],
            "created_at": str(r[8]),
            "outcome_recorded_at": str(r[9]) if r[9] else None,
        }
        for r in rows
    ]}


@router.get("/v1/precedent/{org_id}/match")
def match_precedents(
    org_id: str,
    situation_type: str = Query(...),
    tags: Optional[str] = Query(None, description="comma-separated tags"),
    limit: int = Query(5, le=20),
    db: Session = Depends(get_db),
):
    """
    Find similar precedents for a given situation.
    Matches by situation_type first, then overlapping tags.
    Weighted by decay_weight * outcome_quality.
    PDF spec: enables pattern matching after 200+ precedents.
    """
    tag_list = [t.strip() for t in tags.split(",")] if tags else []

    rows = db.execute(
        text("""
            SELECT id, situation_type, context_summary, action_taken,
                outcome_type, outcome_quality, decay_weight, related_tags,
                created_at,
                -- relevance score: tag overlap + recency decay
                COALESCE(outcome_quality, 0) * decay_weight AS relevance_score
            FROM precedent_graph
            WHERE org_id = :org_id
            AND situation_type = :situation_type
            AND outcome_type IN ('positive', 'neutral')
            AND approval_status = 'approved'
            ORDER BY relevance_score DESC, created_at DESC
            LIMIT :limit
        """),
        {"org_id": org_id, "situation_type": situation_type, "limit": limit * 2}
    ).fetchall()

    # If tags provided, re-rank by tag overlap
    if tag_list and rows:
        def tag_overlap_score(row):
            row_tags = row[7] or []
            overlap = len(set(row_tags) & set(tag_list))
            relevance = float(row[9] or 0)
            return relevance + (overlap * 0.1)

        rows = sorted(rows, key=tag_overlap_score, reverse=True)[:limit]

    return {"matches": [
        {
            "id": str(r[0]),
            "situation_type": r[1],
            "context_summary": r[2],
            "action_taken": r[3],
            "outcome_type": r[4],
            "outcome_quality": float(r[5]) if r[5] is not None else None,
            "decay_weight": float(r[6]) if r[6] is not None else 1.0,
            "related_tags": r[7] or [],
            "created_at": str(r[8]),
        }
        for r in rows[:limit]
    ]}


@router.patch("/v1/precedent/{org_id}/{precedent_id}/outcome")
def record_outcome(
    org_id: str,
    precedent_id: str,
    req: RecordOutcomeRequest,
    db: Session = Depends(get_db),
):
    """Record the outcome of a previously recorded precedent."""
    # Get the precedent to compute fresh decay weight
    row = db.execute(
        text("SELECT id, created_at FROM precedent_graph WHERE id = :id AND org_id = :org_id"),
        {"id": precedent_id, "org_id": org_id}
    ).fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="Precedent not found")

    decay_weight = _compute_decay_weight(row[1])

    try:
        db.execute(
            text("""
                UPDATE precedent_graph SET
                    outcome_type = :outcome_type,
                    outcome_quality = :outcome_quality,
                    approval_status = :approval_status,
                    decay_weight = :decay_weight,
                    outcome_recorded_at = NOW()
                WHERE id = :id AND org_id = :org_id
            """),
            {
                "id": precedent_id,
                "org_id": org_id,
                "outcome_type": req.outcome_type,
                "outcome_quality": req.outcome_quality,
                "approval_status": req.approval_status,
                "decay_weight": decay_weight,
            }
        )
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

    return {"status": "outcome_recorded", "decay_weight": decay_weight}


@router.get("/v1/precedent/{org_id}/stats")
def precedent_stats(org_id: str, db: Session = Depends(get_db)):
    """Summary statistics for the precedent graph."""
    result = db.execute(
        text("""
            SELECT
                COUNT(*) AS total,
                COUNT(*) FILTER (WHERE outcome_type = 'positive') AS positive,
                COUNT(*) FILTER (WHERE outcome_type = 'negative') AS negative,
                COUNT(*) FILTER (WHERE outcome_type = 'neutral') AS neutral,
                COUNT(*) FILTER (WHERE outcome_type IS NULL) AS pending,
                COUNT(DISTINCT situation_type) AS situation_types,
                AVG(outcome_quality) FILTER (WHERE outcome_quality IS NOT NULL) AS avg_quality
            FROM precedent_graph
            WHERE org_id = :org_id
        """),
        {"org_id": org_id}
    ).fetchone()

    total = int(result[0]) if result else 0
    pattern_matching_ready = total >= 200

    return {
        "total": total,
        "positive": int(result[1] or 0),
        "negative": int(result[2] or 0),
        "neutral": int(result[3] or 0),
        "pending_outcome": int(result[4] or 0),
        "situation_types": int(result[5] or 0),
        "avg_quality": round(float(result[6]), 3) if result[6] else None,
        "pattern_matching_ready": pattern_matching_ready,
        "pattern_matching_threshold": 200,
    }
