"""
Context Facts & Lifecycle API — Supports the 5-tab Context page.
Endpoints: overview stats, facts listing, commitments CRUD, lifecycle timeline.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.database import SessionLocal
from typing import Optional
import logging

logger = logging.getLogger(__name__)
router = APIRouter()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ── Tab 1: Context Overview ─────────────────────────────────────────────

@router.get("/api/org/{org_id}/context/overview")
def get_context_overview(org_id: str, db: Session = Depends(get_db)):
    """Overview health cards + activity stream for the Context page."""
    try:
        # Total facts = contacts with data
        total_facts = db.execute(
            text("SELECT COUNT(*) FROM contacts WHERE org_id = :org_id AND interaction_count > 0"),
            {"org_id": org_id},
        ).scalar() or 0

        # Average confidence
        avg_confidence = db.execute(
            text("SELECT AVG(confidence_score) FROM contacts WHERE org_id = :org_id AND confidence_score IS NOT NULL"),
            {"org_id": org_id},
        ).scalar() or 0

        # Facts decaying (freshness < 0.60)
        facts_decaying = db.execute(
            text("SELECT COUNT(*) FROM contacts WHERE org_id = :org_id AND freshness_score < 0.60 AND freshness_score IS NOT NULL"),
            {"org_id": org_id},
        ).scalar() or 0

        # Conflicts detected (consistency < 0.40)
        conflicts_detected = db.execute(
            text("SELECT COUNT(*) FROM contacts WHERE org_id = :org_id AND consistency_score < 0.40 AND consistency_score IS NOT NULL"),
            {"org_id": org_id},
        ).scalar() or 0

        # Recent context events from activity_log
        events = db.execute(
            text("""
                SELECT event_type, event_data, created_at
                FROM activity_log
                WHERE org_id = :org_id
                ORDER BY created_at DESC
                LIMIT 20
            """),
            {"org_id": org_id},
        ).fetchall()

        return {
            "health_cards": {
                "total_facts": total_facts,
                "avg_confidence": round(float(avg_confidence), 3),
                "facts_decaying": facts_decaying,
                "conflicts_detected": conflicts_detected,
            },
            "recent_events": [
                {
                    "event_type": r[0],
                    "event_data": r[1],
                    "created_at": r[2].isoformat() if r[2] else None,
                }
                for r in events
            ],
        }
    except Exception as e:
        logger.error(f"Context overview error: {e}")
        try:
            db.rollback()
        except Exception:
            pass
        raise HTTPException(status_code=500, detail=str(e))


# ── Tab 2: Active Facts ─────────────────────────────────────────────────

@router.get("/api/org/{org_id}/facts")
def get_active_facts(
    org_id: str,
    fact_type: Optional[str] = None,
    min_score: float = 0.0,
    entity_name: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
):
    """List all active facts (contacts with scored data) for the facts table."""
    try:
        where_clauses = ["c.org_id = :org_id", "c.interaction_count > 0"]
        params: dict = {"org_id": org_id, "limit": limit, "offset": offset}

        if min_score > 0:
            where_clauses.append("c.composite_score >= :min_score")
            params["min_score"] = min_score

        if entity_name:
            where_clauses.append("c.name ILIKE :entity_name")
            params["entity_name"] = f"%{entity_name}%"

        if fact_type:
            where_clauses.append("c.entity_type = :fact_type")
            params["fact_type"] = fact_type

        where_sql = " AND ".join(where_clauses)

        results = db.execute(
            text(f"""
                SELECT
                    c.id, c.name, c.email, c.company, c.entity_type,
                    c.relationship_stage, c.freshness_score, c.confidence_score,
                    c.consistency_score, c.authority_score, c.composite_score,
                    c.last_interaction_at, c.interaction_count, c.sentiment_avg,
                    c.topics_aggregate
                FROM contacts c
                WHERE {where_sql}
                ORDER BY c.composite_score DESC NULLS LAST
                LIMIT :limit OFFSET :offset
            """),
            params,
        ).fetchall()

        total = db.execute(
            text(f"SELECT COUNT(*) FROM contacts c WHERE {where_sql}"),
            {k: v for k, v in params.items() if k not in ('limit', 'offset')},
        ).scalar() or 0

        return {
            "facts": [
                {
                    "id": str(r[0]),
                    "entity": r[1],
                    "email": r[2],
                    "company": r[3],
                    "entity_type": r[4],
                    "relationship_stage": r[5],
                    "freshness": round(float(r[6] or 0), 3),
                    "confidence": round(float(r[7] or 0), 3),
                    "consistency": round(float(r[8] or 0), 3),
                    "authority": round(float(r[9] or 0), 3),
                    "composite": round(float(r[10] or 0), 3),
                    "last_confirmed": r[11].isoformat() if hasattr(r[11], 'isoformat') else str(r[11]) if r[11] else None,
                    "interaction_count": r[12] or 0,
                    "sentiment_avg": round(float(r[13] or 0), 3),
                    "topics": r[14] if r[14] else [],
                }
                for r in results
            ],
            "total": total,
            "limit": limit,
            "offset": offset,
        }
    except Exception as e:
        logger.error(f"Facts listing error: {e}")
        try:
            db.rollback()
        except Exception:
            pass
        raise HTTPException(status_code=500, detail=str(e))


# ── Tab 3: Lifecycle Activity ────────────────────────────────────────────

@router.get("/api/org/{org_id}/facts/lifecycle")
def get_lifecycle_activity(
    org_id: str,
    entity_name: Optional[str] = None,
    event_type: Optional[str] = None,
    limit: int = 50,
    db: Session = Depends(get_db),
):
    """Timeline of context lifecycle events — fact state transitions, ingestion events, etc."""
    try:
        where_clauses = ["a.org_id = :org_id"]
        params: dict = {"org_id": org_id, "limit": limit}

        if event_type:
            where_clauses.append("a.event_type = :event_type")
            params["event_type"] = event_type

        where_sql = " AND ".join(where_clauses)

        results = db.execute(
            text(f"""
                SELECT a.event_type, a.event_data, a.created_at
                FROM activity_log a
                WHERE {where_sql}
                ORDER BY a.created_at DESC
                LIMIT :limit
            """),
            params,
        ).fetchall()

        return {
            "events": [
                {
                    "event_type": r[0],
                    "event_data": r[1],
                    "created_at": r[2].isoformat() if hasattr(r[2], 'isoformat') else str(r[2]) if r[2] else None,
                }
                for r in results
            ],
        }
    except Exception as e:
        logger.error(f"Lifecycle activity error: {e}")
        try:
            db.rollback()
        except Exception:
            pass
        raise HTTPException(status_code=500, detail=str(e))


# ── Tab 4: Commitments ───────────────────────────────────────────────────

@router.get("/api/org/{org_id}/commitments")
def get_commitments(
    org_id: str,
    status: Optional[str] = None,
    limit: int = 50,
    db: Session = Depends(get_db),
):
    """List commitments grouped by status (overdue, open, fulfilled)."""
    try:
        where_clauses = ["cm.org_id = :org_id"]
        params: dict = {"org_id": org_id, "limit": limit}

        if status:
            where_clauses.append("cm.status = :status")
            params["status"] = status

        where_sql = " AND ".join(where_clauses)

        results = db.execute(
            text(f"""
                SELECT
                    cm.id, cm.commit_text, cm.owner, cm.status, cm.due_date,
                    cm.created_at, c.name as contact_name, c.company,
                    cm.priority, cm.is_blocker,
                    CASE
                        WHEN cm.due_date IS NOT NULL AND cm.due_date < NOW() AND cm.status = 'open'
                        THEN EXTRACT(DAY FROM NOW() - cm.due_date)
                        ELSE NULL
                    END as days_overdue
                FROM commitments cm
                JOIN contacts c ON cm.contact_id = c.id
                WHERE {where_sql}
                ORDER BY
                    CASE cm.status
                        WHEN 'open' THEN 1
                        WHEN 'fulfilled' THEN 2
                        ELSE 3
                    END,
                    cm.due_date ASC NULLS LAST
                LIMIT :limit
            """),
            params,
        ).fetchall()

        commitments = []
        for r in results:
            is_overdue = r[10] is not None and float(r[10]) > 0
            commitments.append({
                "id": str(r[0]),
                "text": r[1],
                "owner": r[2],
                "status": r[3],
                "due_date": r[4].isoformat() if hasattr(r[4], 'isoformat') else str(r[4]) if r[4] else None,
                "created_at": r[5].isoformat() if hasattr(r[5], 'isoformat') else str(r[5]) if r[5] else None,
                "contact_name": r[6],
                "company": r[7],
                "priority": r[8],
                "is_blocker": r[9],
                "is_overdue": is_overdue,
                "days_overdue": int(float(r[10])) if r[10] else 0,
            })

        # Group by status
        overdue = [c for c in commitments if c["is_overdue"]]
        open_items = [c for c in commitments if c["status"] == "open" and not c["is_overdue"]]
        fulfilled = [c for c in commitments if c["status"] == "fulfilled"]

        return {
            "overdue": overdue,
            "open": open_items,
            "fulfilled": fulfilled,
            "total": len(commitments),
        }
    except Exception as e:
        logger.error(f"Commitments listing error: {e}")
        try:
            db.rollback()
        except Exception:
            pass
        raise HTTPException(status_code=500, detail=str(e))


class CommitmentUpdate(BaseModel):
    status: Optional[str] = None  # "fulfilled", "not_a_commitment"
    due_date: Optional[str] = None


@router.patch("/api/org/{org_id}/commitments/{commitment_id}")
def update_commitment(
    org_id: str,
    commitment_id: str,
    update: CommitmentUpdate,
    db: Session = Depends(get_db),
):
    """Update a commitment — mark fulfilled, not a commitment, or edit due date."""
    try:
        updates = []
        params: dict = {"org_id": org_id, "commitment_id": commitment_id}

        if update.status:
            updates.append("status = :status")
            params["status"] = update.status

        if update.due_date:
            updates.append("due_date = :due_date")
            params["due_date"] = update.due_date

        if not updates:
            raise HTTPException(status_code=400, detail="No updates provided")

        db.execute(
            text(f"""
                UPDATE commitments
                SET {', '.join(updates)}
                WHERE id = :commitment_id AND org_id = :org_id
            """),
            params,
        )
        db.commit()

        return {"updated": True, "commitment_id": commitment_id}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Commitment update error: {e}")
        try:
            db.rollback()
        except Exception:
            pass
        raise HTTPException(status_code=500, detail=str(e))
