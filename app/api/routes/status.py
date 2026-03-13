from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.database import SessionLocal
from datetime import datetime, timezone

router = APIRouter()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.get("/api/org/{org_id}/status")
def get_org_status(org_id: str, db: Session = Depends(get_db)):
    """Get organization ingestion status."""

    # Check if Gmail connected (include new sync columns)
    oauth = db.execute(
        text(
            """SELECT last_synced_at, sync_status, sync_total, sync_processed, sync_error 
               FROM oauth_tokens WHERE org_id = :org_id"""
        ),
        {"org_id": org_id},
    ).fetchone()

    # Count contacts and interactions
    stats = db.execute(
        text(
            """
            SELECT 
                COUNT(DISTINCT c.id) as contacts_count,
                COUNT(i.id) as interactions_count
            FROM contacts c
            LEFT JOIN interactions i ON i.contact_id = c.id
            WHERE c.org_id = :org_id
        """
        ),
        {"org_id": org_id},
    ).fetchone()

    # Count unstaged contacts (ingestion in progress)
    unstaged = db.execute(
        text(
            """
            SELECT COUNT(*) FROM contacts 
            WHERE org_id = :org_id 
            AND (relationship_stage IS NULL OR relationship_stage = 'unknown')
        """
        ),
        {"org_id": org_id},
    ).fetchone()[0]

    contacts_count = stats.contacts_count or 0
    interactions_count = stats.interactions_count or 0
    ingestion_complete = contacts_count > 0 and unstaged == 0

    progress = (
        100
        if ingestion_complete
        else (int((contacts_count - unstaged) / max(contacts_count, 1) * 100))
    )

    # Sync progress from DB
    sync_status = "idle"
    sync_total = 0
    sync_processed = 0
    sync_error = None
    if oauth:
        sync_status = oauth.sync_status or "idle"
        sync_total = oauth.sync_total or 0
        sync_processed = oauth.sync_processed or 0
        sync_error = oauth.sync_error

    return {
        "gmail_connected": oauth is not None,
        "last_sync": oauth.last_synced_at if oauth else None,
        "contacts_count": contacts_count,
        "interactions_count": interactions_count,
        "ingestion_complete": ingestion_complete,
        "ingestion_progress": progress,
        "sync_status": sync_status,
        "sync_total": sync_total,
        "sync_processed": sync_processed,
        "sync_error": sync_error,
    }


@router.get("/api/org/{org_id}/graph")
def get_graph_data(org_id: str, db: Session = Depends(get_db)):
    """Get relationship graph data for visualization."""

    # Get all contacts
    contacts = db.execute(
        text(
            """
            SELECT 
                id,
                name,
                email,
                company,
                relationship_stage,
                sentiment_avg,
                interaction_count,
                last_interaction_at
            FROM contacts
            WHERE org_id = :org_id
            AND relationship_stage IS NOT NULL
            AND relationship_stage != 'unknown'
            ORDER BY interaction_count DESC
        """
        ),
        {"org_id": org_id},
    ).fetchall()

    nodes = []
    for c in contacts:
        # Calculate days since last interaction
        if c.last_interaction_at:
            days_ago = (datetime.now(timezone.utc) - c.last_interaction_at).days
        else:
            days_ago = 999

        nodes.append(
            {
                "id": str(c.id),
                "name": c.name or c.email,
                "company": c.company,
                "relationship_stage": c.relationship_stage,
                "last_interaction_days": days_ago,
                "sentiment_avg": float(c.sentiment_avg or 0),
                "interaction_count": c.interaction_count,
                "email": c.email,
            }
        )

    # Create links (simple star topology - all contacts linked to org)
    links = []
    for node in nodes:
        links.append(
            {
                "source": org_id,
                "target": node["id"],
                "strength": min(node["interaction_count"] / 10.0, 1.0),
            }
        )

    # Add org as center node
    org_node = {
        "id": org_id,
        "name": "YOU",
        "company": None,
        "relationship_stage": "ACTIVE",
        "last_interaction_days": 0,
        "sentiment_avg": 1.0,
        "interaction_count": 0,
        "email": "",
    }
    nodes.insert(0, org_node)

    return {"nodes": nodes, "links": links}


@router.get("/api/org/{org_id}/contacts")
def get_contacts(
    org_id: str, limit: int = 100, offset: int = 0, db: Session = Depends(get_db)
):
    """Get list of contacts."""

    contacts = db.execute(
        text(
            """
            SELECT 
                id, name, email, company, 
                relationship_stage, last_interaction_at,
                interaction_count, sentiment_avg
            FROM contacts
            WHERE org_id = :org_id
            ORDER BY interaction_count DESC
            LIMIT :limit OFFSET :offset
        """
        ),
        {"org_id": org_id, "limit": limit, "offset": offset},
    ).fetchall()

    total = db.execute(
        text("SELECT COUNT(*) FROM contacts WHERE org_id = :org_id"), {"org_id": org_id}
    ).fetchone()[0]

    return {
        "contacts": [
            {
                "id": str(c.id),
                "name": c.name or c.email,
                "email": c.email,
                "company": c.company,
                "relationship_stage": c.relationship_stage,
                "last_interaction_at": (
                    c.last_interaction_at.isoformat() if c.last_interaction_at else None
                ),
                "interaction_count": c.interaction_count,
                "sentiment_avg": float(c.sentiment_avg or 0),
            }
            for c in contacts
        ],
        "total": total,
        "limit": limit,
        "offset": offset,
    }
