"""
Workspace-level custom integrations (Phase 12).

Inkbox / IMAP / Phone / SMS — anything that is NOT Google OAuth — gets
managed here at workspace level. Google OAuth (Gmail, Calendar) keeps its
existing flow in `integrations_auth.py` (multiple accounts already supported
via `oauth_tokens.account_email`).

Routes:
    GET    /api/org/{org_id}/integrations/accounts           — list ALL connected accounts (oauth + connector)
    POST   /api/org/{org_id}/integrations/inkbox/accounts    — connect a new Inkbox mailbox
    POST   /api/org/{org_id}/integrations/imap/accounts      — connect a new IMAP account
    DELETE /api/org/{org_id}/integrations/accounts/{kind}/{id} — disconnect any account
    POST   /api/org/{org_id}/integrations/accounts/{kind}/{id}/sync — manual pull trigger
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.ingestion import adapters
from app.policy import connector_crud, grants_crud

logger = logging.getLogger(__name__)
router = APIRouter()


def _http(detail, status=400):
    return HTTPException(status_code=status, detail=detail)


def _run_connector_sync(connector_id: str) -> None:
    """Run a connector pull *inline* (FastAPI BackgroundTask), independent of
    the Celery worker.

    Why: the manual "sync" button and the connect-time initial sync used to
    only `.delay()` onto the `low_priority` Celery queue. If the worker is
    down/not deployed, the job sits in Redis forever — the account stays
    `never_synced` and the dashboard never updates (exactly what Inkbox
    reported). Running it in the API process makes the button a sure shot:
    as long as the API is up, the pull happens. `task_sync_connector` opens
    its own DB session, writes `last_sync_status` on every outcome, and is
    idempotent (duplicate emails skipped via the external_id unique index),
    so this is safe even if the 5-min Celery beat also picks it up later.
    """
    try:
        from app.tasks.sync_connector import task_sync_connector
        task_sync_connector.apply(args=[connector_id])  # eager, no broker needed
    except Exception as e:  # never let a background pull crash anything
        logger.warning(f"inline connector sync {connector_id} failed: {e}")


# Cap how many phone numbers we auto-provision pull connectors for (an
# admin-scoped key may see the whole org; agent-scoped keys see ~1).
_MAX_AUTO_PHONE_NUMBERS = 5


def _maybe_provision_inkbox_phone(db: Session, org_id: str, api_key: str) -> list[str]:
    """If `api_key` has phone scope, create (idempotently) `sms` and `phone`
    pull connectors for the agent's number(s). Returns the new connector ids.
    Entirely best-effort — an email-only key just yields []."""
    new_ids: list[str] = []
    try:
        from app.ingestion.adapters import inkbox as _inkbox
        numbers = _inkbox.list_phone_numbers({"api_key": api_key})[:_MAX_AUTO_PHONE_NUMBERS]
    except Exception as e:
        logger.debug(f"inkbox phone discovery skipped: {e}")
        return new_ids

    for entry in numbers:
        pnid = (entry or {}).get("phone_number_id")
        if not pnid:
            continue
        for src in ("sms", "phone"):
            try:
                # Skip if an active pull connector already exists for this number.
                exists = db.execute(
                    text("""
                        SELECT 1 FROM connector_credentials
                        WHERE org_id = :o AND source = :s AND is_active = TRUE
                          AND metadata->>'provider' = 'inkbox'
                          AND metadata->>'phone_number_id' = :p
                        LIMIT 1
                    """),
                    {"o": org_id, "s": src, "p": str(pnid)},
                ).fetchone()
                if exists:
                    continue
                md = {"provider": "inkbox", "api_key": api_key, "phone_number_id": str(pnid)}
                if entry.get("phone_number"):
                    md["phone_number"] = entry["phone_number"]
                cid, _ = connector_crud.upsert(db, org_id, agent_uuid=None, source=src, metadata=md)
                db.execute(
                    text("UPDATE connector_credentials SET last_sync_status='never_synced' WHERE id=:id"),
                    {"id": cid},
                )
                db.commit()
                new_ids.append(cid)
            except Exception as e:
                db.rollback()
                logger.warning(f"inkbox phone connector provision failed ({src}/{pnid}): {e}")
    return new_ids


class InkboxConnectRequest(BaseModel):
    mailbox_address: str
    api_key:         str


class ImapConnectRequest(BaseModel):
    mailbox_address: str
    host:            str
    username:        str
    password:        str
    port:            Optional[int] = None
    ssl:             bool = True


# ── List all workspace accounts across tools ────────────────────────────────
@router.get("/api/org/{org_id}/integrations/accounts")
def list_accounts(org_id: str, db: Session = Depends(get_db)):
    """One source of truth for the Integrations dashboard page. Returns
    every connected account grouped by tool with display label + last sync."""
    rows = grants_crud.list_workspace_accounts(db, org_id)
    grouped: dict[str, list[dict]] = {}
    for r in rows:
        tool = r[2] or "unknown"
        grouped.setdefault(tool, []).append({
            "account_id":            r[0],
            "account_kind":          r[1],
            "channel":               r[3],   # email / sms / phone / calendar
            "label":                 r[4],
            "last_event_at":         r[5].isoformat() if r[5] else None,
            "sync_status":           r[6],
            "sync_error":            r[7],
            "last_sync_at":          r[8].isoformat() if r[8] else None,
            "consecutive_failures":  r[9] or 0,
        })
    return {"tools": grouped}


# ── Inkbox: connect a workspace-level Inkbox mailbox ────────────────────────
@router.post("/api/org/{org_id}/integrations/inkbox/accounts", status_code=201)
def connect_inkbox(org_id: str, req: InkboxConnectRequest,
                   background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    if not req.mailbox_address.strip() or not req.api_key.strip():
        raise _http({"error": "INVALID_PAYLOAD", "message": "mailbox_address and api_key required"}, 400)

    metadata = {
        "provider": "inkbox",
        "mailbox_address": req.mailbox_address.strip().lower(),
        "api_key": req.api_key.strip(),
    }

    # Phase 12 polish: pre-flight verify the credentials BEFORE storing.
    # Catches typos, revoked keys, wrong mailbox in real time so the customer
    # sees a red error in the modal instead of "no events yet" 5 min later.
    ops = adapters.get("inkbox") or {}
    verify = ops.get("verify")
    if verify:
        try:
            ok, msg = verify({"api_key": metadata["api_key"], "mailbox_address": metadata["mailbox_address"]})
        except UnicodeEncodeError:
            # Smart quotes / NBSP / ZWSP in pasted key would crash the HTTP layer.
            # Surface a clean modal error instead of a generic "Failed to fetch".
            raise _http({"error": "INVALID_KEY_CHARS", "message": "API key has hidden characters (smart quotes / non-breaking spaces). Re-copy from Inkbox console."}, 400)
        if not ok:
            raise _http({"error": "VERIFY_FAILED", "message": msg}, 400)

    try:
        conn_id, _ = connector_crud.upsert(
            db, org_id, agent_uuid=None, source="email", metadata=metadata,
        )
        # Mark initial state — sync task will overwrite on first run
        db.execute(
            text("""
                UPDATE connector_credentials
                SET last_sync_status = 'never_synced'
                WHERE id = :id
            """),
            {"id": conn_id},
        )
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"connect_inkbox failed: {e}")
        raise _http("Connect failed", 500)

    # Initial sync — runs in the API process, not dependent on the Celery worker.
    background_tasks.add_task(_run_connector_sync, conn_id)

    # Best-effort: if this API key can also see the agent's phone number(s),
    # provision sms + voice-call pull connectors so we sync those channels too
    # (mirrors how Gmail+Calendar both light up from one Google connection).
    phone_conn_ids = _maybe_provision_inkbox_phone(db, org_id, metadata["api_key"])
    for cid in phone_conn_ids:
        background_tasks.add_task(_run_connector_sync, cid)

    return {
        "account_id":   conn_id,
        "account_kind": "connector",
        "tool":         "inkbox",
        "phone_channels": len(phone_conn_ids) // 2 if phone_conn_ids else 0,
        "label":        metadata["mailbox_address"],
        "initial_sync_enqueued": True,
    }


# ── IMAP: connect a self-hosted email mailbox ───────────────────────────────
@router.post("/api/org/{org_id}/integrations/imap/accounts", status_code=201)
def connect_imap(org_id: str, req: ImapConnectRequest,
                 background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    if not (req.mailbox_address and req.host and req.username and req.password):
        raise _http({"error": "INVALID_PAYLOAD", "message": "mailbox_address/host/username/password required"}, 400)

    metadata = {
        "provider": "imap",
        "mailbox_address": req.mailbox_address.strip().lower(),
        "host":     req.host.strip(),
        "username": req.username.strip(),
        "password": req.password,
        "port":     req.port,
        "ssl":      req.ssl,
    }

    # Pre-flight: actually try IMAP login before storing
    ops = adapters.get("imap") or {}
    verify = ops.get("verify")
    if verify:
        ok, msg = verify(metadata)
        if not ok:
            raise _http({"error": "VERIFY_FAILED", "message": msg}, 400)

    try:
        conn_id, _ = connector_crud.upsert(
            db, org_id, agent_uuid=None, source="email", metadata=metadata,
        )
        db.execute(
            text("UPDATE connector_credentials SET last_sync_status = 'never_synced' WHERE id = :id"),
            {"id": conn_id},
        )
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"connect_imap failed: {e}")
        raise _http("Connect failed", 500)

    # Initial sync — runs in the API process, not dependent on the Celery worker.
    background_tasks.add_task(_run_connector_sync, conn_id)

    return {
        "account_id":   conn_id,
        "account_kind": "connector",
        "tool":         "imap",
        "label":        metadata["mailbox_address"],
        "initial_sync_enqueued": True,
    }


# ── Disconnect any account (oauth or connector) ─────────────────────────────
@router.delete("/api/org/{org_id}/integrations/accounts/{kind}/{account_id}")
def disconnect_account(org_id: str, kind: str, account_id: str, db: Session = Depends(get_db)):
    if kind == "connector":
        res = db.execute(
            text("""
                UPDATE connector_credentials
                SET is_active = FALSE
                WHERE id = :id AND org_id = :o AND is_active = TRUE
                RETURNING 1
            """),
            {"id": account_id, "o": org_id},
        ).fetchone()
    elif kind == "oauth":
        res = db.execute(
            text("""
                DELETE FROM oauth_tokens
                WHERE id = :id AND org_id = :o
                RETURNING 1
            """),
            {"id": account_id, "o": org_id},
        ).fetchone()
    else:
        raise _http({"error": "INVALID_KIND"}, 400)
    if not res:
        raise _http({"error": "ACCOUNT_NOT_FOUND"}, 404)
    # Also clean up any agent grants pointing to this account
    db.execute(
        text("DELETE FROM agent_account_grants WHERE org_id = :o AND account_id = :id AND account_kind = :k"),
        {"o": org_id, "id": account_id, "k": kind},
    )
    db.commit()
    return {"account_id": account_id, "disconnected": True}


# ── Manual sync trigger for any account ─────────────────────────────────────
@router.post("/api/org/{org_id}/integrations/accounts/{kind}/{account_id}/sync", status_code=202)
def sync_account(org_id: str, kind: str, account_id: str,
                 background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    if kind != "connector":
        # OAuth (Gmail/Calendar) syncs are kicked through their existing flows
        raise _http({"error": "USE_OAUTH_SYNC_ENDPOINT", "message": "For OAuth-managed tools use existing Gmail/Calendar sync routes."}, 400)
    exists = db.execute(
        text("SELECT 1 FROM connector_credentials WHERE id = :id AND org_id = :o AND is_active = TRUE"),
        {"id": account_id, "o": org_id},
    ).fetchone()
    if not exists:
        raise _http({"error": "ACCOUNT_NOT_FOUND"}, 404)
    # Flip to 'syncing' synchronously so the dashboard reflects it on the very
    # next poll, then run the pull in-process (no Celery worker dependency).
    db.execute(
        text("UPDATE connector_credentials SET last_sync_status = 'syncing' WHERE id = :id"),
        {"id": account_id},
    )
    db.commit()
    background_tasks.add_task(_run_connector_sync, account_id)
    return {"account_id": account_id, "status": "syncing"}
