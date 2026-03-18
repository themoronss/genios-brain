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


def sync_task(org_id: str, account_email: str = None):
    """Background task to sync Gmail (one or all accounts)."""
    try:
        from app.config import SYNC_MAX_EMAILS
        label = f"account={account_email}" if account_email else "all accounts"
        print(f"Starting Gmail sync for org_id={org_id} [{label}] with max_emails={SYNC_MAX_EMAILS}")
        run_gmail_sync(org_id, max_emails=SYNC_MAX_EMAILS, account_email=account_email)
        print(f"Gmail sync completed for org_id={org_id} [{label}]")
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
    """Trigger manual Gmail sync for organization (syncs all connected accounts)."""

    # Check if at least one Gmail account is connected
    oauth = db.execute(
        text(
            """SELECT id, last_synced_at, sync_status
               FROM oauth_tokens WHERE org_id = :org_id
               LIMIT 1"""
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

    # Set status to running synchronously so frontend correctly sees it on immediate refetch
    db.execute(
        text("UPDATE oauth_tokens SET sync_status = 'running' WHERE org_id = :org_id"),
        {"org_id": org_id},
    )
    db.commit()

    # Trigger background sync for all accounts
    background_tasks.add_task(sync_task, org_id, None)

    return {
        "status": "sync_started",
        "message": "Gmail sync started in background. This may take 2-5 minutes.",
        "org_id": org_id,
    }


@router.get("/api/org/{org_id}/sync/status")
def get_sync_status(org_id: str, db: Session = Depends(get_db)):
    """
    Get current sync status with real-time progress.
    Update 4: Returns per-account sync status for all connected Gmail accounts.
    """

    # Fetch all tokens for the org (supports multiple Gmail accounts)
    all_tokens = db.execute(
        text(
            """SELECT last_synced_at, sync_status, sync_total, sync_processed,
                      sync_error, sync_started_at,
                      COALESCE(account_email, 'default') AS account_email
               FROM oauth_tokens WHERE org_id = :org_id"""
        ),
        {"org_id": org_id},
    ).fetchall()

    if not all_tokens:
        return {"synced": False, "last_sync": None, "accounts": []}

    # Aggregate stats across all accounts
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

    # Build per-account status list
    accounts_status = []
    for token in all_tokens:
        accounts_status.append({
            "account_email": token.account_email,
            "sync_status": token.sync_status or "idle",
            "sync_total": token.sync_total or 0,
            "sync_processed": token.sync_processed or 0,
            "sync_error": token.sync_error,
            "last_sync": token.last_synced_at.isoformat() if token.last_synced_at else None,
            "sync_started_at": (
                token.sync_started_at.isoformat() if token.sync_started_at else None
            ),
        })

    # Use the most recent sync time across all accounts as the overall last_sync
    last_sync_times = [
        t.last_synced_at for t in all_tokens if t.last_synced_at
    ]
    overall_last_sync = max(last_sync_times).isoformat() if last_sync_times else None

    # Overall status: running if any account is running, else completed if all done
    statuses = [t.sync_status or "idle" for t in all_tokens]
    if "running" in statuses:
        overall_status = "running"
    elif "error" in statuses:
        overall_status = "error"
    elif all(s == "completed" for s in statuses):
        overall_status = "completed"
    else:
        overall_status = "idle"

    # Pick a representative token for backwards-compat flat fields
    primary = all_tokens[0]

    return {
        "synced": True,
        "last_sync": overall_last_sync,
        "sync_status": overall_status,
        # Legacy flat fields (uses primary/first account for compatibility)
        "sync_total": primary.sync_total or 0,
        "sync_processed": primary.sync_processed or 0,
        "sync_error": primary.sync_error,
        "sync_started_at": (
            primary.sync_started_at.isoformat() if primary.sync_started_at else None
        ),
        "contacts_count": stats.contacts_count or 0,
        "interactions_count": stats.interactions_count or 0,
        # Update 4: per-account breakdown
        "accounts": accounts_status,
    }


# ── Update 4: Multi-account management endpoints ──────────────────────────────

@router.get("/api/org/{org_id}/gmail/accounts")
def list_connected_accounts(org_id: str, db: Session = Depends(get_db)):
    """
    List all Gmail accounts connected to this organization.
    Update 4: Supports multiple Gmail accounts per org.
    """
    tokens = db.execute(
        text(
            """SELECT COALESCE(account_email, 'unknown') AS account_email,
                      last_synced_at, sync_status, sync_total, sync_processed,
                      sync_error, created_at
               FROM oauth_tokens
               WHERE org_id = :org_id
               ORDER BY created_at ASC"""
        ),
        {"org_id": org_id},
    ).fetchall()

    if not tokens:
        return {"accounts": [], "count": 0}

    return {
        "accounts": [
            {
                "account_email": t.account_email,
                "last_synced_at": t.last_synced_at.isoformat() if t.last_synced_at else None,
                "sync_status": t.sync_status or "idle",
                "sync_total": t.sync_total or 0,
                "sync_processed": t.sync_processed or 0,
                "sync_error": t.sync_error,
                "connected_at": t.created_at.isoformat() if t.created_at else None,
            }
            for t in tokens
        ],
        "count": len(tokens),
    }


@router.delete("/api/org/{org_id}/gmail/accounts/{account_email}")
def disconnect_account(
    org_id: str,
    account_email: str,
    db: Session = Depends(get_db),
):
    """
    Disconnect a specific Gmail account from this organization.
    Update 4: Deletes only the token for the given account_email, leaving
              other connected accounts intact.
    """
    result = db.execute(
        text(
            """DELETE FROM oauth_tokens
               WHERE org_id = :org_id AND account_email = :account_email
               RETURNING id"""
        ),
        {"org_id": org_id, "account_email": account_email},
    ).fetchone()

    if not result:
        raise HTTPException(
            status_code=404,
            detail=f"No connected Gmail account found for {account_email}",
        )

    db.commit()
    return {
        "status": "disconnected",
        "account_email": account_email,
        "message": f"Gmail account {account_email} has been disconnected.",
    }


@router.post("/api/org/{org_id}/gmail/accounts/{account_email}/sync")
def trigger_account_sync(
    org_id: str,
    account_email: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """
    Trigger a sync for a specific connected Gmail account.
    Update 4: Allows per-account sync in addition to the bulk org sync.
    """
    token = db.execute(
        text(
            """SELECT sync_status FROM oauth_tokens
               WHERE org_id = :org_id AND account_email = :account_email"""
        ),
        {"org_id": org_id, "account_email": account_email},
    ).fetchone()

    if not token:
        raise HTTPException(
            status_code=404,
            detail=f"No connected Gmail account found for {account_email}",
        )

    if token.sync_status == "running":
        raise HTTPException(
            status_code=429,
            detail=f"Sync already running for {account_email}. Please wait.",
        )

    # Set status to running synchronously so frontend picks it up immediately
    db.execute(
        text(
            "UPDATE oauth_tokens SET sync_status = 'running' "
            "WHERE org_id = :org_id AND account_email = :account_email"
        ),
        {"org_id": org_id, "account_email": account_email},
    )
    db.commit()

    background_tasks.add_task(sync_task, org_id, account_email)

    return {
        "status": "sync_started",
        "account_email": account_email,
        "message": f"Sync started for {account_email}. This may take 2-5 minutes.",
    }


@router.post("/api/org/{org_id}/reset")
def reset_org_data(org_id: str, db: Session = Depends(get_db)):
    """Wipe all graph data (interactions, contacts) but keep connected accounts.
       Resets the sync progress to idle. Used for testing/debugging.
    """
    try:
        # 1. Delete commitments first (foreign key to interactions)
        db.execute(text("DELETE FROM commitments WHERE org_id = :oid"), {"oid": org_id})
        
        # 2. Delete interactions
        db.execute(text("DELETE FROM interactions WHERE org_id = :oid"), {"oid": org_id})
        
        # 2. Delete contacts
        db.execute(text("DELETE FROM contacts WHERE org_id = :oid"), {"oid": org_id})
        
        # 3. Reset sync progress in oauth_tokens
        db.execute(
            text("""
                UPDATE oauth_tokens
                SET sync_status = 'idle',
                    sync_total = 0,
                    sync_processed = 0,
                    sync_error = NULL,
                    sync_started_at = NULL,
                    last_synced_at = NULL
                WHERE org_id = :oid
            """),
            {"oid": org_id}
        )
        db.commit()
        return {"status": "success", "message": "Graph data completely wiped."}
    except Exception as e:
        db.rollback()
        from fastapi import HTTPException
        raise HTTPException(status_code=500, detail=str(e))

