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

from fastapi import APIRouter, Depends, HTTPException
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
            "label":                 r[3],
            "last_event_at":         r[4].isoformat() if r[4] else None,
            "sync_status":           r[5],
            "sync_error":            r[6],
            "last_sync_at":          r[7].isoformat() if r[7] else None,
            "consecutive_failures":  r[8] or 0,
        })
    return {"tools": grouped}


# ── Inkbox: connect a workspace-level Inkbox mailbox ────────────────────────
@router.post("/api/org/{org_id}/integrations/inkbox/accounts", status_code=201)
def connect_inkbox(org_id: str, req: InkboxConnectRequest, db: Session = Depends(get_db)):
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
        ok, msg = verify({"api_key": metadata["api_key"], "mailbox_address": metadata["mailbox_address"]})
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

    # Initial sync
    try:
        from app.tasks.sync_connector import task_sync_connector
        task_sync_connector.delay(conn_id)
    except Exception:
        pass

    return {
        "account_id":   conn_id,
        "account_kind": "connector",
        "tool":         "inkbox",
        "label":        metadata["mailbox_address"],
        "initial_sync_enqueued": True,
    }


# ── IMAP: connect a self-hosted email mailbox ───────────────────────────────
@router.post("/api/org/{org_id}/integrations/imap/accounts", status_code=201)
def connect_imap(org_id: str, req: ImapConnectRequest, db: Session = Depends(get_db)):
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

    try:
        from app.tasks.sync_connector import task_sync_connector
        task_sync_connector.delay(conn_id)
    except Exception:
        pass

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
def sync_account(org_id: str, kind: str, account_id: str, db: Session = Depends(get_db)):
    if kind != "connector":
        # OAuth (Gmail/Calendar) syncs are kicked through their existing flows
        raise _http({"error": "USE_OAUTH_SYNC_ENDPOINT", "message": "For OAuth-managed tools use existing Gmail/Calendar sync routes."}, 400)
    exists = db.execute(
        text("SELECT 1 FROM connector_credentials WHERE id = :id AND org_id = :o AND is_active = TRUE"),
        {"id": account_id, "o": org_id},
    ).fetchone()
    if not exists:
        raise _http({"error": "ACCOUNT_NOT_FOUND"}, 404)
    try:
        from app.tasks.sync_connector import task_sync_connector
        task_sync_connector.delay(account_id)
    except Exception as e:
        logger.warning(f"sync dispatch failed: {e}")
        raise _http({"error": "SYNC_DISPATCH_FAILED"}, 503)
    return {"account_id": account_id, "status": "enqueued"}
