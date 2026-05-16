"""
Ingest endpoints — Inkbox & friends push email/call/SMS into Genios.

Auth: Bearer key (server-derived agent identity).
Optional HMAC: if connector_credentials row exists for (agent, source),
verify X-Genios-Signature against the raw body.
Idempotency: external_id (Inkbox message_id / call_id / sms_id).

Each accepted ingest:
  • upsert contact (by email or phone)
  • insert interaction (tagged agent_uuid + source + external_id)
  • enqueue extraction (Celery — async, fail-soft)
  • write ingest_events audit row
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Optional, Callable

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel, validator
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.deps import get_auth_ctx, get_db
from app.policy import connector_crud, trust_crud
from app.policy.scope_loader import AuthCtx

logger = logging.getLogger(__name__)
router = APIRouter()


# ── Pydantic schemas ─────────────────────────────────────────────────────────
class _DirMixin:
    @classmethod
    def _v_dir(cls, v):
        v = (v or "").lower()
        if v not in ("inbound", "outbound"):
            raise ValueError("direction must be 'inbound' or 'outbound'")
        return v


class EmailIngest(BaseModel, _DirMixin):
    external_id:           str
    from_address:          str
    to:                    list[str]
    subject:               Optional[str] = None
    body_text:             Optional[str] = None
    body_html:             Optional[str] = None
    sent_at:               str
    direction:             str = "inbound"
    in_reply_to_external_id: Optional[str] = None
    thread_external_id:    Optional[str] = None

    @validator("direction")
    def _vd(cls, v): return cls._v_dir(v)


class CallIngest(BaseModel, _DirMixin):
    external_id:  str
    from_number:  str
    to_number:    str
    duration_sec: int = 0
    transcript:   Optional[str] = None
    started_at:   str
    direction:    str = "inbound"

    @validator("direction")
    def _vd(cls, v): return cls._v_dir(v)


class SmsIngest(BaseModel, _DirMixin):
    external_id: str
    from_number: str
    to_number:   str
    body:        str
    sent_at:     str
    direction:   str = "inbound"

    @validator("direction")
    def _vd(cls, v): return cls._v_dir(v)


# ── Helpers ──────────────────────────────────────────────────────────────────
def _parse_ts(s: str) -> datetime:
    try:
        return datetime.fromisoformat((s or "").replace("Z", "+00:00"))
    except Exception:
        return datetime.now(timezone.utc)


def _resolve_account_id_for_ingest(db, org_id: str, agent_uuid: Optional[str], source: str) -> Optional[str]:
    """Phase 12: ingested data carries the source-account UUID so scoped agents
    can be filtered by their grants. We look up the active workspace-level
    connector for this source (agent_uuid IS NULL) — falling back to the
    legacy per-agent row if it still exists."""
    row = db.execute(
        text("""
            SELECT id::text FROM connector_credentials
            WHERE org_id = :o AND source = :s AND is_active = TRUE
              AND (agent_uuid IS NULL OR agent_uuid = :a)
            ORDER BY (agent_uuid IS NULL) DESC, created_at DESC
            LIMIT 1
        """),
        {"o": org_id, "s": source, "a": agent_uuid},
    ).fetchone()
    return row[0] if row else None


def _audit(db, org_id, agent_uuid, source, external_id, outcome,
           interaction_id=None, contact_id=None, error=None, payload_bytes=0):
    try:
        db.execute(
            text("""
                INSERT INTO ingest_events
                    (org_id, agent_uuid, source, external_id, outcome,
                     interaction_id, contact_id, error_detail, payload_bytes)
                VALUES (:o, :a, :s, :e, :out, :iid, :cid, :err, :bytes)
            """),
            {"o": org_id, "a": agent_uuid, "s": source, "e": external_id,
             "out": outcome, "iid": interaction_id, "cid": contact_id,
             "err": error, "bytes": payload_bytes},
        )
        db.commit()
    except Exception as e:
        logger.warning(f"ingest_events log failed: {e}")


def _verify_inkbox_signature(raw_body, request_id, timestamp, signature, signing_key, tolerance_sec=300):
    """Inkbox webhook signature: HMAC-SHA256({request_id}.{timestamp}.{body}, signing_key).
    Header format: X-Inkbox-Signature: sha256=<hex>. Timestamp tolerance 300s."""
    import hashlib, hmac as _hmac, time
    if not (request_id and timestamp and signature and signing_key):
        return False
    try:
        if abs(time.time() - int(timestamp)) > tolerance_sec:
            return False
    except (ValueError, TypeError):
        return False
    message = f"{request_id}.{timestamp}.{raw_body.decode('utf-8', errors='replace')}".encode()
    expected = _hmac.new(signing_key.encode(), message, hashlib.sha256).hexdigest()
    provided = signature.removeprefix("sha256=").strip()
    return _hmac.compare_digest(expected, provided)


def _verify_hmac_or_bootstrap(db, agent_uuid, source, raw_body, signature,
                              inkbox_request_id=None, inkbox_timestamp=None,
                              inkbox_signature=None):
    """Returns (ok, mode) where mode is 'hmac' | 'inkbox_hmac' | 'bootstrap' | 'reject'.

    Two signature paths:
      1. Inkbox-native: X-Inkbox-Signature with {req_id}.{ts}.{body} HMAC
      2. Genios-native: X-Genios-Signature with {body}-only HMAC (legacy)
    """
    # Prefer Inkbox-native signature if those headers are present
    if inkbox_signature and inkbox_request_id and inkbox_timestamp:
        secret = connector_crud.get_signing_secret(db, agent_uuid, source)
        if secret is None:
            # No signing key registered yet — accept (bootstrap) but log
            return True, "bootstrap"
        ok = _verify_inkbox_signature(raw_body, inkbox_request_id, inkbox_timestamp,
                                       inkbox_signature, secret)
        return ok, "inkbox_hmac" if ok else "reject"

    # Legacy / Genios-native path
    secret = connector_crud.get_signing_secret(db, agent_uuid, source)
    if secret is None:
        return True, "bootstrap"
    if not signature:
        return False, "reject"
    ok = connector_crud.verify_signature(raw_body, signature, "", raw_secret=secret)
    return ok, "hmac" if ok else "reject"


def _find_dup(db, org_id, source, external_id):
    return db.execute(
        text("""
            SELECT id::text, contact_id::text FROM interactions
            WHERE org_id = :o AND source = :s AND external_id = :e
            LIMIT 1
        """),
        {"o": org_id, "s": source, "e": external_id},
    ).fetchone()


def _upsert_contact_by_email(db, org_id, email, name=None) -> str:
    e = (email or "").strip().lower()
    if not e:
        raise ValueError("empty email")
    row = db.execute(
        text("SELECT id::text FROM contacts WHERE org_id=:o AND LOWER(email)=:e"),
        {"o": org_id, "e": e},
    ).fetchone()
    if row:
        return row[0]
    return db.execute(
        text("""
            INSERT INTO contacts (org_id, email, name, segment_source)
            VALUES (:o, :e, :n, 'auto')
            RETURNING id::text
        """),
        {"o": org_id, "e": e, "n": name or e.split("@")[0]},
    ).scalar()


def _upsert_contact_by_phone(db, org_id, phone) -> str:
    p = (phone or "").strip()
    if not p:
        raise ValueError("empty phone")
    row = db.execute(
        text("""
            SELECT id::text FROM contacts
            WHERE org_id = :o AND metadata @> CAST(:m AS jsonb) LIMIT 1
        """),
        {"o": org_id, "m": json.dumps({"phone": p})},
    ).fetchone()
    if row:
        return row[0]
    return db.execute(
        text("""
            INSERT INTO contacts (org_id, email, name, metadata, segment_source)
            VALUES (:o, '', :n, CAST(:m AS jsonb), 'auto')
            RETURNING id::text
        """),
        {"o": org_id, "n": p, "m": json.dumps({"phone": p})},
    ).scalar()


def _enqueue_extraction(interaction_id: str) -> None:
    """Best-effort enqueue. Fails open if extractor task not registered yet."""
    try:
        from app.celery_app import celery
        celery.send_task(
            "app.celery_app.task_extract_interaction",
            args=[interaction_id],
            queue="high_priority",
        )
    except Exception as e:
        logger.debug(f"extraction enqueue skipped: {e}")


def _maybe_normalise_vendor_payload(raw: bytes, source: str) -> bytes:
    """Auto-detect known vendor webhook shapes (Inkbox MailWebhookPayload,
    Twilio SMS webhook, etc.) and normalise to our canonical schema before
    pydantic parsing. Returns the (possibly rewritten) bytes."""
    try:
        body = json.loads(raw.decode())
    except Exception:
        return raw
    if not isinstance(body, dict):
        return raw

    # Inkbox shape: {event_type, timestamp, data: ...}. Same normaliser handles
    # mail (message.received), SMS (text.received), and voice (phone.incoming_call)
    # — dispatching on event_type internally.
    et = body.get("event_type", "")
    inkbox_event_for_source = (
        (source == "email" and et.startswith("message.")) or
        (source == "sms"   and et == "text.received") or
        (source == "phone" and et == "phone.incoming_call")
    )
    if inkbox_event_for_source and isinstance(body.get("data"), dict):
        try:
            from app.ingestion.adapters.inkbox import normalise_webhook
            canonical = normalise_webhook(body)
            if canonical:
                return json.dumps(canonical).encode()
        except Exception as e:
            logger.debug(f"inkbox webhook normalise failed: {e}")
    return raw


async def _common_ingest(
    request: Request,
    db: Session,
    auth: AuthCtx,
    signature: Optional[str],
    source: str,
    schema_cls: type,
    insert_fn: Callable,
):
    """Single chokepoint for all three ingest endpoints."""
    raw = await request.body()
    org_id, agent_uuid = auth.org_id, auth.agent_uuid
    if not org_id:
        _audit(db, None, None, source, None, "rejected_unknown_agent",
               error="org not resolved", payload_bytes=len(raw))
        raise HTTPException(status_code=401, detail={"error": "AUTH_REQUIRED"})

    # Phase 12 polish: detect Inkbox-native signature headers if present
    h = request.headers
    inkbox_req_id = h.get("X-Inkbox-Request-ID") or h.get("x-inkbox-request-id")
    inkbox_ts     = h.get("X-Inkbox-Timestamp")  or h.get("x-inkbox-timestamp")
    inkbox_sig    = h.get("X-Inkbox-Signature")  or h.get("x-inkbox-signature")

    ok, mode = _verify_hmac_or_bootstrap(
        db, agent_uuid, source, raw, signature,
        inkbox_request_id=inkbox_req_id, inkbox_timestamp=inkbox_ts,
        inkbox_signature=inkbox_sig,
    )
    if not ok:
        _audit(db, org_id, agent_uuid, source, None, "rejected_signature",
               error="HMAC mismatch", payload_bytes=len(raw))
        raise HTTPException(status_code=401, detail={"error": "BAD_SIGNATURE"})

    # Normalise vendor-specific webhook shapes (Inkbox etc.) to canonical
    raw_for_parse = _maybe_normalise_vendor_payload(raw, source)

    try:
        body = schema_cls.parse_raw(raw_for_parse)
    except Exception as e:
        _audit(db, org_id, agent_uuid, source, None, "rejected_format",
               error=str(e)[:200], payload_bytes=len(raw))
        raise HTTPException(status_code=400, detail={"error": "INVALID_PAYLOAD", "message": str(e)[:200]})

    dup = _find_dup(db, org_id, source, body.external_id)
    if dup:
        _audit(db, org_id, agent_uuid, source, body.external_id, "duplicate",
               interaction_id=dup[0], contact_id=dup[1], payload_bytes=len(raw))
        return {"deduped": True, "interaction_id": dup[0], "contact_id": dup[1]}

    try:
        contact_id, interaction_id = insert_fn(db, org_id, agent_uuid, body)
        db.commit()
    except Exception as e:
        db.rollback()
        _audit(db, org_id, agent_uuid, source, body.external_id, "rejected_format",
               error=f"insert failed: {e}"[:200], payload_bytes=len(raw))
        raise HTTPException(status_code=400, detail={"error": "INSERT_FAILED"})

    try:
        conn = connector_crud.find_for_ingest(db, agent_uuid, source)
        if conn:
            connector_crud.touch_last_event(db, conn[0])
            db.commit()
    except Exception:
        pass
    _enqueue_extraction(interaction_id)

    _audit(db, org_id, agent_uuid, source, body.external_id, "accepted",
           interaction_id=interaction_id, contact_id=contact_id, payload_bytes=len(raw))
    return {"deduped": False, "interaction_id": interaction_id, "contact_id": contact_id, "auth_mode": mode}


# ── Per-source insert functions ──────────────────────────────────────────────
# Phase 12: each interaction is tagged with the source-account UUID so
# read-time scope filter can join against agent_account_grants. Trust list
# is now resolved AT READ TIME against any agent that's granted this account
# — at ingest we still tag the inserting-agent if known (for audit only).

def _insert_email(db, org_id, agent_uuid, b: EmailIngest):
    counterparty = b.from_address if b.direction == "inbound" else (b.to[0] if b.to else "")
    contact_id = _upsert_contact_by_email(db, org_id, counterparty)
    account_id = _resolve_account_id_for_ingest(db, org_id, agent_uuid, "email")
    trusted = trust_crud.is_trusted(
        db, agent_uuid, sender_email=counterparty, contact_id=contact_id,
    ) if agent_uuid else False
    iid = db.execute(
        text("""
            INSERT INTO interactions
                (org_id, contact_id, agent_uuid, account_id, direction,
                 subject, summary, raw_snippet, interaction_at, source,
                 external_id, thread_external_id, interaction_kind, trusted_sender)
            VALUES (:o, :c, :a, :acct, :dir, :subj, :sum, :raw, :at, :src, :ext, :thr, 'email', :trust)
            RETURNING id::text
        """),
        {
            "o": org_id, "c": contact_id, "a": agent_uuid, "acct": account_id,
            "dir": b.direction, "subj": (b.subject or "")[:500],
            "sum": (b.body_text or b.body_html or "")[:2000],
            "raw": (b.body_text or b.body_html or "")[:5000],
            "at": _parse_ts(b.sent_at),
            "src": "email", "ext": b.external_id,
            "thr": b.thread_external_id or b.in_reply_to_external_id,
            "trust": trusted,
        },
    ).scalar()
    return contact_id, iid


def _insert_call(db, org_id, agent_uuid, b: CallIngest):
    counterparty = b.from_number if b.direction == "inbound" else b.to_number
    contact_id = _upsert_contact_by_phone(db, org_id, counterparty)
    account_id = _resolve_account_id_for_ingest(db, org_id, agent_uuid, "phone")
    trusted = trust_crud.is_trusted(
        db, agent_uuid, sender_phone=counterparty, contact_id=contact_id,
    ) if agent_uuid else False
    iid = db.execute(
        text("""
            INSERT INTO interactions
                (org_id, contact_id, agent_uuid, account_id, direction,
                 summary, raw_snippet, interaction_at, source, external_id,
                 interaction_kind, duration_sec, transcript, trusted_sender)
            VALUES (:o, :c, :a, :acct, :dir, :sum, :raw, :at, :src, :ext, 'call', :dur, :tr, :trust)
            RETURNING id::text
        """),
        {
            "o": org_id, "c": contact_id, "a": agent_uuid, "acct": account_id,
            "dir": b.direction,
            "sum": (b.transcript or f"Call {b.duration_sec}s")[:2000],
            "raw": (b.transcript or "")[:5000],
            "at": _parse_ts(b.started_at),
            "src": "phone", "ext": b.external_id,
            "dur": b.duration_sec, "tr": b.transcript,
            "trust": trusted,
        },
    ).scalar()
    return contact_id, iid


def _insert_sms(db, org_id, agent_uuid, b: SmsIngest):
    counterparty = b.from_number if b.direction == "inbound" else b.to_number
    contact_id = _upsert_contact_by_phone(db, org_id, counterparty)
    account_id = _resolve_account_id_for_ingest(db, org_id, agent_uuid, "sms")
    trusted = trust_crud.is_trusted(
        db, agent_uuid, sender_phone=counterparty, contact_id=contact_id,
    ) if agent_uuid else False
    iid = db.execute(
        text("""
            INSERT INTO interactions
                (org_id, contact_id, agent_uuid, account_id, direction,
                 summary, raw_snippet, interaction_at, source, external_id,
                 interaction_kind, trusted_sender)
            VALUES (:o, :c, :a, :acct, :dir, :sum, :raw, :at, :src, :ext, 'sms', :trust)
            RETURNING id::text
        """),
        {
            "o": org_id, "c": contact_id, "a": agent_uuid, "acct": account_id,
            "dir": b.direction,
            "sum": (b.body or "")[:2000],
            "raw": (b.body or "")[:5000],
            "at": _parse_ts(b.sent_at),
            "src": "sms", "ext": b.external_id,
            "trust": trusted,
        },
    ).scalar()
    return contact_id, iid


# ── Routes ───────────────────────────────────────────────────────────────────
# Genios is generic — any provider (Inkbox, Postmark, custom email server,
# Twilio, etc.) can push to the same canonical endpoints. The
# `connector_credentials.metadata.provider` tag lets the dashboard render
# branded labels without baking vendor names into the API surface.

@router.post("/v1/ingest/email", status_code=202)
async def ingest_email(
    request: Request,
    db: Session = Depends(get_db),
    auth: AuthCtx = Depends(get_auth_ctx),
    signature: Optional[str] = Header(None, alias="X-Genios-Signature"),
):
    return await _common_ingest(request, db, auth, signature, "email", EmailIngest, _insert_email)


@router.post("/v1/ingest/call", status_code=202)
async def ingest_call(
    request: Request,
    db: Session = Depends(get_db),
    auth: AuthCtx = Depends(get_auth_ctx),
    signature: Optional[str] = Header(None, alias="X-Genios-Signature"),
):
    return await _common_ingest(request, db, auth, signature, "phone", CallIngest, _insert_call)


@router.post("/v1/ingest/sms", status_code=202)
async def ingest_sms(
    request: Request,
    db: Session = Depends(get_db),
    auth: AuthCtx = Depends(get_auth_ctx),
    signature: Optional[str] = Header(None, alias="X-Genios-Signature"),
):
    return await _common_ingest(request, db, auth, signature, "sms", SmsIngest, _insert_sms)


# ── Deprecated Inkbox-prefixed aliases — kept for back-compat ────────────────
# These were the original Phase 6 paths. New integrations should target
# the canonical paths above. Aliases will be removed in a later cleanup.

@router.post("/v1/ingest/inkbox/email", status_code=202, deprecated=True)
async def _ingest_email_alias(
    request: Request,
    db: Session = Depends(get_db),
    auth: AuthCtx = Depends(get_auth_ctx),
    signature: Optional[str] = Header(None, alias="X-Genios-Signature"),
):
    return await _common_ingest(request, db, auth, signature, "email", EmailIngest, _insert_email)


@router.post("/v1/ingest/inkbox/call", status_code=202, deprecated=True)
async def _ingest_call_alias(
    request: Request,
    db: Session = Depends(get_db),
    auth: AuthCtx = Depends(get_auth_ctx),
    signature: Optional[str] = Header(None, alias="X-Genios-Signature"),
):
    return await _common_ingest(request, db, auth, signature, "phone", CallIngest, _insert_call)


@router.post("/v1/ingest/inkbox/sms", status_code=202, deprecated=True)
async def _ingest_sms_alias(
    request: Request,
    db: Session = Depends(get_db),
    auth: AuthCtx = Depends(get_auth_ctx),
    signature: Optional[str] = Header(None, alias="X-Genios-Signature"),
):
    return await _common_ingest(request, db, auth, signature, "sms", SmsIngest, _insert_sms)


@router.get("/v1/ingest/events")
def list_ingest_events(
    limit: int = 50,
    db: Session = Depends(get_db),
    auth: AuthCtx = Depends(get_auth_ctx),
):
    limit = max(1, min(200, int(limit)))
    rows = db.execute(
        text("""
            SELECT received_at, source, external_id, outcome, error_detail, payload_bytes
            FROM ingest_events
            WHERE org_id = :o AND (agent_uuid = :a OR :a IS NULL)
            ORDER BY received_at DESC LIMIT :l
        """),
        {"o": auth.org_id, "a": auth.agent_uuid, "l": limit},
    ).fetchall()
    return {
        "events": [
            {
                "at": r[0].isoformat() if r[0] else None,
                "source": r[1], "external_id": r[2], "outcome": r[3],
                "error": r[4], "bytes": r[5],
            } for r in rows
        ]
    }
