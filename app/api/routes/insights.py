"""
Insights & Activity Feed API — Signal detection results and activity stream.
"""
from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.api.deps import get_db

router = APIRouter()


@router.get("/api/org/{org_id}/insights")
def get_insights(org_id: str, priority: str = None, limit: int = 20, db: Session = Depends(get_db)):
    """Get active insights for an org, optionally filtered by priority."""
    conditions = ["org_id = :org_id", "is_dismissed = FALSE"]
    params = {"org_id": org_id, "limit": min(limit, 50)}

    if priority:
        conditions.append("priority = :priority")
        params["priority"] = priority

    where_clause = " AND ".join(conditions)

    results = db.execute(
        text(f"""
            SELECT id, insight_type, priority, category, title, detail,
                contact_id, contact_name, metadata, generated_at
            FROM insights
            WHERE {where_clause}
            ORDER BY
                CASE priority WHEN 'P1' THEN 0 WHEN 'P2' THEN 1 ELSE 2 END,
                generated_at DESC
            LIMIT :limit
        """),
        params
    ).fetchall()

    return {
        "insights": [
            {
                "id": str(r[0]), "insight_type": r[1], "priority": r[2],
                "category": r[3], "title": r[4], "detail": r[5],
                "contact_id": str(r[6]) if r[6] else None,
                "contact_name": r[7],
                "metadata": r[8] if isinstance(r[8], dict) else {},
                "generated_at": r[9].isoformat() if r[9] else None,
            } for r in results
        ],
        "total": len(results),
    }


@router.post("/api/org/{org_id}/insights/{insight_id}/dismiss")
def dismiss_insight(org_id: str, insight_id: str, db: Session = Depends(get_db)):
    """Dismiss an insight so it doesn't show again."""
    db.execute(
        text("UPDATE insights SET is_dismissed = TRUE WHERE id = :id AND org_id = :org_id"),
        {"id": insight_id, "org_id": org_id}
    )
    db.commit()
    return {"dismissed": True}


@router.get("/activity")
def get_activity_feed(org_id: str, limit: int = 20, db: Session = Depends(get_db)):
    """Recent activity events for the activity feed."""
    events = db.execute(
        text("""
            SELECT event_type, event_data, created_at
            FROM activity_log
            WHERE org_id = :org_id
            ORDER BY created_at DESC
            LIMIT :limit
        """),
        {"org_id": org_id, "limit": min(limit, 50)}
    ).fetchall()

    return {
        "events": [
            {
                "event_type": e[0],
                "event_data": e[1] if isinstance(e[1], dict) else {},
                "created_at": e[2].isoformat() if e[2] else None,
            }
            for e in events
        ],
        "total": len(events),
    }
