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
from app.config import GENIOS_PUBLIC_URL
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


def _merge_connector_metadata(db: Session, connector_id: str, updates: dict) -> None:
    """Shallow-merge `updates` into connector_credentials.metadata (JSONB).
    Used to stamp webhook_registered_at / signing_secret / webhook_url after
    out-of-band registration with Inkbox."""
    import json as _json
    db.execute(
        text("""
            UPDATE connector_credentials
            SET metadata = COALESCE(metadata, '{}'::jsonb) || CAST(:patch AS jsonb)
            WHERE id = :id
        """),
        {"id": connector_id, "patch": _json.dumps(updates)},
    )


def _existing_org_signing_secret(db: Session, org_id: str) -> Optional[str]:
    """Return the org's stored INKBOX-minted signing secret if any active
    inkbox connector already has one. Stored under `inkbox_signing_key` —
    deliberately a separate field from the Genios-native `whk_*` HMAC
    secret that connector_crud.upsert() auto-mints into `signing_secret`.
    Mixing the two caused webhooks to be rejected because we were verifying
    Inkbox payloads against our own internal `whk_*` key (the one Inkbox
    has no knowledge of)."""
    row = db.execute(
        text("""
            SELECT metadata->>'inkbox_signing_key'
            FROM connector_credentials
            WHERE org_id = :o AND is_active = TRUE
              AND metadata->>'provider' = 'inkbox'
              AND metadata ? 'inkbox_signing_key'
            LIMIT 1
        """),
        {"o": org_id},
    ).fetchone()
    return row[0] if row and row[0] else None


def _register_inkbox_webhooks(
    db: Session, org_id: str, api_key: str,
    email_connector_id: Optional[str],
    mailbox_address: Optional[str],
    phone_connector_ids: list[str],
) -> None:
    """After connector rows exist, mint a signing key (if org doesn't have one
    yet) and PATCH each Inkbox resource with our webhook URL. Stamps
    `webhook_registered_at` + `signing_secret` + `webhook_url` onto the
    connector metadata. Entirely best-effort — if Inkbox is down or the API
    key lacks scope, polling stays as the fallback."""
    if not GENIOS_PUBLIC_URL:
        logger.warning("inkbox webhooks not registered: GENIOS_PUBLIC_URL is unset")
        return

    from app.ingestion.adapters import inkbox as _inkbox
    now_iso = datetime.now(timezone.utc).isoformat()

    # ── 1. Signing key (org-wide, plaintext returned only on first POST) ──
    secret = _existing_org_signing_secret(db, org_id)
    if not secret:
        try:
            secret = _inkbox.bootstrap_signing_key(api_key)
        except Exception as e:
            logger.warning(f"inkbox signing key bootstrap failed: {e}")
            secret = None
    if not secret:
        logger.warning("inkbox webhooks not registered: no signing secret available")
        return

    # ── 2. Mailbox webhook ──
    if email_connector_id and mailbox_address:
        webhook_url = f"{GENIOS_PUBLIC_URL}/v1/webhooks/inkbox/{email_connector_id}"
        try:
            ok = _inkbox.register_mail_webhook(api_key, mailbox_address, webhook_url)
        except PermissionError as pe:
            logger.warning(f"inkbox mail webhook 401/403: {pe}")
            ok = False
        except Exception as e:
            logger.warning(f"inkbox mail webhook register failed: {e}")
            ok = False
        if ok:
            _merge_connector_metadata(db, email_connector_id, {
                "inkbox_signing_key": secret,
                "webhook_url": webhook_url,
                "webhook_registered_at": now_iso,
            })

    # ── 3. Phone-number webhooks (SMS + call URLs on the same number) ──
    # phone_connector_ids has up to 2 rows per number: one source='sms', one
    # source='phone'. We PATCH the number ONCE per phone_number_id with both
    # URLs so Inkbox knows where to push texts vs incoming calls.
    by_pnid: dict[str, dict[str, str]] = {}  # pnid -> {"sms": cid, "phone": cid}
    for cid in phone_connector_ids:
        row = db.execute(
            text("SELECT source, metadata->>'phone_number_id' FROM connector_credentials WHERE id = :id"),
            {"id": cid},
        ).fetchone()
        if not row:
            continue
        src, pnid = row[0], row[1]
        if not pnid or src not in ("sms", "phone"):
            continue
        by_pnid.setdefault(pnid, {})[src] = cid

    for pnid, srcs in by_pnid.items():
        sms_cid = srcs.get("sms")
        call_cid = srcs.get("phone")
        sms_url  = f"{GENIOS_PUBLIC_URL}/v1/webhooks/inkbox/{sms_cid}" if sms_cid else None
        # NOTE: we deliberately do NOT register a call webhook URL — Inkbox's
        # `phone.incoming_call` is a synchronous handshake (must answer +
        # bridge audio or reject), and rejecting drops the call. Instead we
        # leave `incoming_call_action='voicemail'` so callers leave a message
        # that Inkbox auto-transcribes; we pick that up via the existing
        # calls poll. Voicemail-mode = graceful degradation, no dead air.
        # Stamp the phone connector row with webhook_registered_at anyway so
        # we don't double-PATCH on reconnect — voicemail mode is a deliberate
        # registered state, not "not yet registered".
        try:
            ok = _inkbox.register_phone_webhook(api_key, pnid,
                                                 sms_webhook_url=sms_url,
                                                 call_webhook_url=None)
        except PermissionError as pe:
            logger.warning(f"inkbox phone webhook 401/403 ({pnid}): {pe}")
            ok = False
        except Exception as e:
            logger.warning(f"inkbox phone webhook register failed ({pnid}): {e}")
            ok = False
        if ok:
            if sms_cid:
                _merge_connector_metadata(db, sms_cid, {
                    "inkbox_signing_key": secret,
                    "webhook_url": sms_url,
                    "webhook_registered_at": now_iso,
                })
            if call_cid:
                _merge_connector_metadata(db, call_cid, {
                    "inkbox_signing_key": secret,
                    # 'inkbox_managed' = whatever was already set on the
                    # phone number in Inkbox console (we don't override).
                    # Will flip to 'webhook' once voice-agent stack lands.
                    "call_mode": "inkbox_managed",
                    "webhook_registered_at": now_iso,
                })
    db.commit()


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
        webhook_at = r[10] if len(r) > 10 else None
        call_mode  = r[11] if len(r) > 11 else None
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
            # Push-mode visibility: UI renders green "Real-time" badge if set,
            # else "Polling every 5 min". For phone rows, call_mode reveals
            # voicemail vs webhook-answer mode.
            "webhook_registered_at": webhook_at,
            "delivery_mode":         "webhook" if webhook_at else "poll",
            "call_mode":             call_mode,  # 'voicemail' | 'webhook' | None
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

    # Switch to push mode: mint the org-wide Inkbox signing key (once) and
    # PATCH each mailbox / phone-number resource with our webhook URL. On
    # success, polling for email + SMS is automatically skipped downstream
    # (sync_connector.py looks at metadata.webhook_registered_at). Calls keep
    # polling because Inkbox exposes no `call.completed` / `transcript.ready`
    # event — transcripts are pull-only.
    background_tasks.add_task(
        _register_inkbox_webhooks_bg, org_id, metadata["api_key"],
        conn_id, metadata["mailbox_address"], list(phone_conn_ids),
    )

    return {
        "account_id":   conn_id,
        "account_kind": "connector",
        "tool":         "inkbox",
        "phone_channels": len(phone_conn_ids) // 2 if phone_conn_ids else 0,
        "label":        metadata["mailbox_address"],
        "initial_sync_enqueued": True,
    }


def _register_inkbox_webhooks_bg(org_id: str, api_key: str,
                                   email_connector_id: Optional[str],
                                   mailbox_address: Optional[str],
                                   phone_connector_ids: list[str]) -> None:
    """BackgroundTask wrapper — needs its own DB session because the request
    session closes when the response is sent."""
    from app.database import SessionLocal
    db = SessionLocal()
    try:
        _register_inkbox_webhooks(
            db, org_id, api_key,
            email_connector_id=email_connector_id,
            mailbox_address=mailbox_address,
            phone_connector_ids=phone_connector_ids,
        )
    except Exception as e:
        logger.warning(f"inkbox webhook registration background task failed: {e}")
    finally:
        db.close()


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


# ── Backfill Inkbox webhook registration for existing customers ─────────────
# When the webhook feature shipped, already-connected orgs hadn't had their
# mailboxes / phone numbers PATCHed with our webhook URLs. Rather than force
# every customer to reconnect, this endpoint sweeps every active inkbox
# connector for the org and registers webhooks idempotently. Safe to re-run.
@router.post("/api/org/{org_id}/integrations/inkbox/webhooks/register", status_code=202)
def backfill_inkbox_webhooks(org_id: str, background_tasks: BackgroundTasks,
                              db: Session = Depends(get_db)):
    rows = db.execute(
        text("""
            SELECT id::text, source, metadata
            FROM connector_credentials
            WHERE org_id = :o AND is_active = TRUE
              AND metadata->>'provider' = 'inkbox'
            ORDER BY source
        """),
        {"o": org_id},
    ).fetchall()
    if not rows:
        raise _http({"error": "NO_INKBOX_ACCOUNTS", "message": "no active Inkbox connectors for this org"}, 404)

    # Find the email connector to get the canonical api_key + mailbox.
    email_row = next((r for r in rows if r[1] == "email"), None)
    if not email_row:
        raise _http({"error": "NO_EMAIL_CONNECTOR", "message": "Inkbox email connector required for backfill"}, 400)

    try:
        email_creds = connector_crud.decrypt_metadata(email_row[2])
    except connector_crud.ConnectorDecryptError as e:
        raise _http({"error": "DECRYPT_FAILED", "message": str(e)}, 500)

    api_key = email_creds.get("api_key") or ""
    mailbox = email_creds.get("mailbox_address") or ""
    phone_ids = [r[0] for r in rows if r[1] in ("sms", "phone")]

    if not api_key:
        raise _http({"error": "MISSING_API_KEY", "message": "stored Inkbox API key is empty"}, 400)

    background_tasks.add_task(
        _register_inkbox_webhooks_bg, org_id, api_key,
        email_row[0], mailbox, phone_ids,
    )
    return {
        "org_id": org_id,
        "email_connector_id": email_row[0],
        "phone_connector_count": len(phone_ids),
        "registration_enqueued": True,
    }


# ── Disconnect any account (oauth or connector) ─────────────────────────────
@router.delete("/api/org/{org_id}/integrations/accounts/{kind}/{account_id}")
def disconnect_account(org_id: str, kind: str, account_id: str, db: Session = Depends(get_db)):
    if kind == "connector":
        # Pull encrypted metadata so we can deregister any Inkbox webhook
        # before flipping is_active off. Best-effort — never blocks disconnect.
        meta_row = db.execute(
            text("SELECT metadata, source FROM connector_credentials WHERE id = :id AND org_id = :o"),
            {"id": account_id, "o": org_id},
        ).fetchone()
        if meta_row and meta_row[0] and (meta_row[0] or {}).get("provider") == "inkbox":
            try:
                creds = connector_crud.decrypt_metadata(meta_row[0])
                from app.ingestion.adapters import inkbox as _inkbox
                api_key = creds.get("api_key") or ""
                if api_key:
                    if meta_row[1] == "email" and creds.get("mailbox_address"):
                        _inkbox.deregister_mail_webhook(api_key, creds["mailbox_address"])
                    elif meta_row[1] in ("sms", "phone") and creds.get("phone_number_id"):
                        _inkbox.deregister_phone_webhook(
                            api_key, creds["phone_number_id"],
                            clear_sms=(meta_row[1] == "sms"),
                            clear_call=(meta_row[1] == "phone"),
                        )
            except Exception as e:
                logger.warning(f"inkbox webhook deregister on disconnect failed: {e}")

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
