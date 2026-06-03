import json

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.config import PROCESSING_VERSION
from app.database import SessionLocal

router = APIRouter()


def _run_in_background(background_tasks, celery_task, *args, fallback_fn=None, **kwargs):
    """Try Celery first. If unavailable, fall back to BackgroundTasks."""
    try:
        celery_task.delay(*args, **kwargs)
    except Exception:
        if fallback_fn:
            background_tasks.add_task(fallback_fn, *args, **kwargs)


def _sync_fallback(org_id: str, max_emails=None, account_email=None):
    """BackgroundTasks fallback — routes to v2 thin pipe per g-i-1 plan.
    Walks v2 Connection rows for this org+account_email and runs sync_runner.
    """
    try:
        from sqlalchemy import select as _sel

        from core.foundations.db import get_session as _v2s
        from core.memory.store import Connection
        from core.memory.sync_runner import run_sync_for_connection

        with _v2s() as s:
            q = _sel(Connection).where(Connection.org_id == org_id).where(Connection.status == "active")
            if account_email:
                q = q.where(Connection.source_id == account_email)
            for conn in s.execute(q).scalars():
                run_sync_for_connection(s, connection_id=conn.id, limit=max_emails or 50)
    except Exception as e:
        db = SessionLocal()
        try:
            db.execute(
                text("UPDATE oauth_tokens SET sync_status = 'error', sync_error = :err WHERE org_id = :oid"),
                {"oid": org_id, "err": str(e)[:500]},
            )
            db.commit()
        finally:
            db.close()


@router.post("/api/org/{org_id}/sync")
def trigger_sync(
    org_id: str, background_tasks: BackgroundTasks, db: Session = Depends(get_db)
):
    """Trigger a manual sync of all connected sources for this org.

    Per g-i-1 plan: walks every v2 Connection for this org and runs the thin
    sync_runner (pull → normalize → emit → subscriber extracts to graph).
    Replaces the v1 heavy gmail_sync path; the v1 oauth_tokens table is
    written by OAuth callback for legacy/observability but is NOT the source
    of truth for sync anymore.
    """

    from core.foundations.db import get_session as _v2_session
    from core.memory.store import Connection
    from core.memory.sync_runner import run_sync_for_connection

    # List active v2 connections for this org
    with _v2_session() as s:
        rows: list[Connection] = (
            s.query(Connection)
            .filter(Connection.org_id == org_id)
            .filter(Connection.status == "active")
            .all()
        )
        connection_ids = [c.id for c in rows]

    if not connection_ids:
        raise HTTPException(
            status_code=400,
            detail="No active sources connected. Connect Gmail or another source first.",
        )

    def _run_all() -> None:
        import logging
        log = logging.getLogger(__name__)
        for cid in connection_ids:
            try:
                with _v2_session() as inner:
                    r = run_sync_for_connection(inner, connection_id=cid, limit=50)
                    log.info(
                        f"sync done conn={cid[:8]} emitted={r.items_emitted} dropped={r.items_dropped_scope}"
                    )
            except Exception as e:
                log.exception(f"sync failed conn={cid[:8]}: {e}")

    background_tasks.add_task(_run_all)

    return {
        "status": "sync_started",
        "connections_count": len(connection_ids),
        "message": "Sync started across all connected sources.",
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
                 AND account_email NOT LIKE 'gcal:%%'
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

    from app.celery_app import task_gmail_sync
    from app.config import SYNC_MAX_EMAILS
    _run_in_background(
        background_tasks, task_gmail_sync,
        org_id, max_emails=SYNC_MAX_EMAILS, account_email=account_email,
        fallback_fn=_sync_fallback,
    )

    return {
        "status": "sync_started",
        "account_email": account_email,
        "message": f"Sync started for {account_email}. This may take 2-5 minutes.",
    }


@router.put("/api/org/{org_id}/sync/interval/{hours}")
def set_sync_interval(org_id: str, hours: int, db: Session = Depends(get_db)):
    """Set the sync interval in hours (6, 12, 18, or 24)."""
    if hours not in (6, 12, 18, 24):
        raise HTTPException(status_code=400, detail="Interval must be 6, 12, 18, or 24 hours")

    db.execute(
        text("UPDATE orgs SET sync_interval_hours = :hours WHERE id = :org_id"),
        {"hours": hours, "org_id": org_id},
    )
    db.commit()
    return {"status": "updated", "sync_interval_hours": hours}


@router.get("/api/org/{org_id}/sync/interval")
def get_sync_interval(org_id: str, db: Session = Depends(get_db)):
    """Get current sync interval setting."""
    result = db.execute(
        text("SELECT sync_interval_hours FROM orgs WHERE id = :org_id"),
        {"org_id": org_id},
    ).fetchone()
    if not result:
        raise HTTPException(status_code=404, detail="Org not found")
    return {"sync_interval_hours": result.sync_interval_hours or 24}


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


# ── Recompute / Re-extract endpoints ────────────────────────────────────────


def _get_recompute_meta(db, org_id: str) -> dict:
    """Read recompute status — tries dedicated columns, falls back to idle defaults."""
    try:
        row = db.execute(
            text("SELECT recompute_status FROM orgs WHERE id = :org_id"),
            {"org_id": org_id},
        ).fetchone()
        if not row:
            return {"exists": False}
        return {"exists": True, "status": row[0] or "idle"}
    except Exception:
        db.rollback()
        # Columns not migrated yet — check org exists, return idle
        row = db.execute(
            text("SELECT id FROM orgs WHERE id = :org_id"),
            {"org_id": org_id},
        ).fetchone()
        if not row:
            return {"exists": False}
        return {"exists": True, "status": "idle"}


def _set_recompute_meta(db, org_id: str, **kwargs):
    """Write recompute status — tries dedicated columns, silently skips if not migrated."""
    try:
        set_parts = []
        params = {"org_id": org_id}
        for key, value in kwargs.items():
            col = f"recompute_{key}" if not key.startswith("recompute_") else key
            set_parts.append(f"{col} = :{col}")
            params[col] = value
        db.execute(text(f"UPDATE orgs SET {', '.join(set_parts)} WHERE id = :org_id"), params)
        db.commit()
    except Exception:
        db.rollback()  # Columns don't exist yet — skip silently


@router.post("/api/org/{org_id}/recompute")
def trigger_recompute(
    org_id: str, background_tasks: BackgroundTasks, db: Session = Depends(get_db)
):
    """
    Tier 1: Rebuild all scores, stages, and relationship graph from existing data.
    No LLM calls, no API calls — pure recalculation. Safe to run anytime.
    """
    meta = _get_recompute_meta(db, org_id)
    if not meta["exists"]:
        raise HTTPException(status_code=404, detail="Org not found")
    if meta["status"] == "running":
        raise HTTPException(status_code=429, detail="A recompute job is already running. Please wait.")

    # Per g-i-1 plan there is no recompute concept — extract runs on emit().
    # Endpoint kept for frontend back-compat; returns immediately as no-op.
    _set_recompute_meta(db, org_id, status="idle")
    return {
        "status": "recompute_noop",
        "tier": 1,
        "message": "Recompute is no longer required (v2 thin pipe extracts inline). Trigger a sync to refresh data.",
    }


@router.post("/api/org/{org_id}/reextract")
def trigger_reextract(
    org_id: str, background_tasks: BackgroundTasks, db: Session = Depends(get_db)
):
    """
    Tier 2: Re-fetch email bodies from Gmail, re-run LLM extraction on stale
    interactions, then rebuild all scores. Uses API credits.
    Only reprocesses interactions with processed_version < PROCESSING_VERSION.
    """
    meta = _get_recompute_meta(db, org_id)
    if not meta["exists"]:
        raise HTTPException(status_code=404, detail="Org not found")
    if meta["status"] == "running":
        raise HTTPException(status_code=429, detail="A recompute/reextract job is already running. Please wait.")

    # Per g-i-1 plan there is no reextract concept — extract runs inline on emit().
    # Endpoint kept for frontend back-compat; returns immediately as no-op.
    _set_recompute_meta(db, org_id, status="idle")
    return {
        "status": "reextract_noop",
        "tier": 2,
        "message": "Re-extract is no longer required (v2 thin pipe extracts inline). Trigger a sync to refresh data.",
    }


@router.get("/api/org/{org_id}/recompute/status")
def get_recompute_status(org_id: str, db: Session = Depends(get_db)):
    """Get current recompute/reextract job status."""
    # Try dedicated columns first
    try:
        result = db.execute(
            text("""
                SELECT recompute_status, recompute_started_at,
                       recompute_completed_at, recompute_error, recompute_progress
                FROM orgs WHERE id = :org_id
            """),
            {"org_id": org_id},
        ).fetchone()

        if not result:
            raise HTTPException(status_code=404, detail="Org not found")

        progress = None
        if result[4]:
            try:
                progress = json.loads(result[4]) if isinstance(result[4], str) else result[4]
            except (json.JSONDecodeError, TypeError):
                progress = None

        return {
            "status": result[0] or "idle",
            "started_at": result[1].isoformat() if result[1] else None,
            "completed_at": result[2].isoformat() if result[2] else None,
            "error": result[3],
            "progress": progress,
            "current_processing_version": PROCESSING_VERSION,
        }
    except HTTPException:
        raise
    except Exception:
        db.rollback()
        # Columns not migrated yet — return idle defaults
        row = db.execute(
            text("SELECT id FROM orgs WHERE id = :org_id"),
            {"org_id": org_id},
        ).fetchone()

        if not row:
            raise HTTPException(status_code=404, detail="Org not found")

        return {
            "status": "idle",
            "started_at": None,
            "completed_at": None,
            "error": None,
            "progress": None,
            "current_processing_version": PROCESSING_VERSION,
        }

