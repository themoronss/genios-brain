from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.database import SessionLocal
from app.tasks.gmail_sync import run_gmail_sync
from datetime import datetime, timezone

router = APIRouter()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def sync_task(org_id: str):
    """Background task to sync Gmail."""
    try:
        print(f"Starting Gmail sync for org_id: {org_id}")
        run_gmail_sync(org_id, max_emails=100)  # 100 emails max as requested
        print(f"Gmail sync completed for org_id: {org_id}")
    except Exception as e:
        print(f"Error during sync: {e}")
        # Mark sync as error if the whole task crashes
        db = SessionLocal()
        try:
            db.execute(
                text(
                    "UPDATE oauth_tokens SET sync_status = 'error', sync_error = :error WHERE org_id = :org_id"
                ),
                {"org_id": org_id, "error": str(e)[:500]},
            )
            db.commit()
        finally:
            db.close()


@router.post("/api/org/{org_id}/sync")
def trigger_sync(
    org_id: str, background_tasks: BackgroundTasks, db: Session = Depends(get_db)
):
    """Trigger manual Gmail sync for organization."""

    # Check if Gmail is connected
    oauth = db.execute(
        text(
            "SELECT id, last_synced_at, sync_status FROM oauth_tokens WHERE org_id = :org_id"
        ),
        {"org_id": org_id},
    ).fetchone()

    if not oauth:
        raise HTTPException(status_code=400, detail="Gmail not connected")

    # Check if a sync is already running
    if oauth.sync_status == "running":
        raise HTTPException(
            status_code=429,
            detail="A sync is already in progress. Please wait for it to complete.",
        )

    # Trigger background sync
    background_tasks.add_task(sync_task, org_id)

    return {
        "status": "sync_started",
        "message": "Gmail sync started in background. This may take 2-5 minutes.",
        "org_id": org_id,
    }


@router.get("/api/org/{org_id}/sync/status")
def get_sync_status(org_id: str, db: Session = Depends(get_db)):
    """Get current sync status with real-time progress."""

    oauth = db.execute(
        text(
            """SELECT last_synced_at, sync_status, sync_total, sync_processed, 
                      sync_error, sync_started_at 
               FROM oauth_tokens WHERE org_id = :org_id"""
        ),
        {"org_id": org_id},
    ).fetchone()

    if not oauth:
        return {"synced": False, "last_sync": None}

    # Get counts
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

    return {
        "synced": True,
        "last_sync": oauth.last_synced_at.isoformat() if oauth.last_synced_at else None,
        "sync_status": oauth.sync_status or "idle",
        "sync_total": oauth.sync_total or 0,
        "sync_processed": oauth.sync_processed or 0,
        "sync_error": oauth.sync_error,
        "sync_started_at": (
            oauth.sync_started_at.isoformat() if oauth.sync_started_at else None
        ),
        "contacts_count": stats.contacts_count or 0,
        "interactions_count": stats.interactions_count or 0,
    }
