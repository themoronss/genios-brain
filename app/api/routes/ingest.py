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


# ── Inkbox push webhook (signature-only, no Bearer) ──────────────────────────
# Inkbox PATCHes a single webhook URL onto each mailbox or phone number, so we
# can't rely on a per-request Bearer token. Instead the URL embeds the
# connector_credentials.id → we look up org / agent / source / signing_secret
# from that row and HMAC-verify the body. One endpoint serves all 3 event
# types (message.received, text.received, phone.incoming_call); we dispatch
# on event_type inside.
#
# `phone.incoming_call` is SYNCHRONOUS in Inkbox's API — the response body
# tells Inkbox whether to answer the call (and where to bridge audio) or
# reject it. MVP: we reject + log so the call still lands in interactions
# but no one is left talking to dead air. Voice-agent bridging is a V2.

def _apply_delivery_event(db: Session, org_id: str, source: str,
                          external_id: str, status: str, extra: dict) -> Optional[str]:
    """Merge a delivery-state event (sent/delivered/bounced/failed/forwarded)
    into the matching interaction's `delivery_state` JSONB column. Returns
    interaction_id if found, None if the underlying message hasn't landed yet
    (in which case the event will be re-applied on the next webhook hit or
    via a backfill — Inkbox can deliver events out of order)."""
    import json as _json
    patch = {"status": status, **extra}
    row = db.execute(
        text("""
            UPDATE interactions
            SET delivery_state = COALESCE(delivery_state, '{}'::jsonb) || CAST(:patch AS jsonb)
            WHERE org_id = :o AND source = :s AND external_id = :e
            RETURNING id::text
        """),
        {"o": org_id, "s": source, "e": external_id, "patch": _json.dumps(patch)},
    ).fetchone()
    return row[0] if row else None


def _mark_contact_bounced(db: Session, org_id: str, email: str, reason: str) -> None:
    """Stamp `bounced_at` + `bounce_reason` into contacts.metadata so the
    agent reasoning layer can avoid retrying a dead address."""
    import json as _json
    e = (email or "").strip().lower()
    if not e:
        return
    patch = {"bounced_at": datetime.now(timezone.utc).isoformat(),
             "bounce_reason": (reason or "")[:200]}
    db.execute(
        text("""
            UPDATE contacts
            SET metadata = COALESCE(metadata, '{}'::jsonb) || CAST(:patch AS jsonb)
            WHERE org_id = :o AND LOWER(email) = :e
        """),
        {"o": org_id, "e": e, "patch": _json.dumps(patch)},
    )


def _load_connector_for_webhook(db: Session, account_id: str):
    """Look up the active connector by id. Returns
    (org_id, agent_uuid, source, inkbox_signing_key, api_key_meta) or None.

    Note we read `inkbox_signing_key` here, NOT `signing_secret`. The latter
    is an internal Genios-native HMAC secret minted by connector_crud.upsert
    that has nothing to do with Inkbox — verifying Inkbox payloads against
    it caused every webhook to be rejected as 'BAD_SIGNATURE'."""
    row = db.execute(
        text("""
            SELECT org_id::text, agent_uuid::text, source, metadata
            FROM connector_credentials
            WHERE id = :id AND is_active = TRUE
              AND metadata->>'provider' = 'inkbox'
            LIMIT 1
        """),
        {"id": account_id},
    ).fetchone()
    if not row:
        return None
    meta = row[3] or {}
    return row[0], row[1], row[2], meta.get("inkbox_signing_key"), meta


@router.post("/v1/webhooks/inkbox/{account_id}")
async def ingest_inkbox_webhook(account_id: str, request: Request, db: Session = Depends(get_db)):
    raw = await request.body()
    conn = _load_connector_for_webhook(db, account_id)
    if not conn:
        # Unknown / disabled connector — return 200 so Inkbox doesn't retry
        # forever, but flag it. (404 would also work; both stop retries.)
        logger.warning(f"inkbox webhook for unknown/inactive connector {account_id}")
        raise HTTPException(status_code=404, detail={"error": "UNKNOWN_CONNECTOR"})
    org_id, agent_uuid, source, signing_secret, _meta = conn

    h = request.headers
    inkbox_req_id = h.get("X-Inkbox-Request-ID") or h.get("x-inkbox-request-id")
    inkbox_ts     = h.get("X-Inkbox-Timestamp")  or h.get("x-inkbox-timestamp")
    inkbox_sig    = h.get("X-Inkbox-Signature")  or h.get("x-inkbox-signature")

    # Inkbox sends unsigned webhooks BEFORE the org's first signing key is
    # minted. After bootstrap (we mint on connect) every payload must be
    # signed. If signing_secret is set but headers are absent → reject.
    if signing_secret:
        if not (inkbox_sig and inkbox_req_id and inkbox_ts):
            _audit(db, org_id, agent_uuid, source, None, "rejected_signature",
                   error="missing inkbox signature headers", payload_bytes=len(raw))
            raise HTTPException(status_code=401, detail={"error": "MISSING_SIGNATURE"})
        if not _verify_inkbox_signature(raw, inkbox_req_id, inkbox_ts, inkbox_sig, signing_secret):
            _audit(db, org_id, agent_uuid, source, None, "rejected_signature",
                   error="HMAC mismatch", payload_bytes=len(raw))
            raise HTTPException(status_code=401, detail={"error": "BAD_SIGNATURE"})

    # Parse payload + dispatch on event_type
    try:
        body = json.loads(raw.decode() or "{}")
    except Exception as e:
        _audit(db, org_id, agent_uuid, source, None, "rejected_format",
               error=f"json: {e}"[:200], payload_bytes=len(raw))
        raise HTTPException(status_code=400, detail={"error": "INVALID_JSON"})
    if not isinstance(body, dict):
        raise HTTPException(status_code=400, detail={"error": "INVALID_PAYLOAD"})

    event_type = body.get("event_type") or ""

    # Mail delivery-lifecycle events (sent/delivered/bounced/failed/forwarded)
    # don't create new interactions — they MUTATE the existing outbound row's
    # delivery_state column. Handled BEFORE the canonical-payload normaliser
    # because normalise_webhook only knows received-type events. We try to
    # update first; if no row matches yet (rare race: lifecycle event arrives
    # before our own DB insert committed), the event is silently dropped —
    # Inkbox will redeliver, or we re-derive from the next status event.
    if event_type in ("message.sent", "message.delivered",
                       "message.bounced", "message.failed", "message.forwarded"):
        data = body.get("data") or {}
        ext_id = data.get("message_id") or data.get("id") or ""
        status = event_type.split(".", 1)[1]  # 'sent' | 'delivered' | ...
        extra: dict = {f"{status}_at": body.get("timestamp") or datetime.now(timezone.utc).isoformat()}
        if status == "bounced":
            extra["bounce_reason"] = data.get("bounce_reason") or data.get("reason") or ""
        elif status == "failed":
            extra["failure_reason"] = data.get("failure_reason") or data.get("reason") or ""
        elif status == "forwarded":
            extra["forwarded_to"] = data.get("forwarded_to") or data.get("to") or []
        iid = _apply_delivery_event(db, org_id, source, ext_id, status, extra) if ext_id else None
        # Bounce → mark contact as bounced (agent reasoning won't keep retrying)
        if status == "bounced":
            target = data.get("recipient") or data.get("to") or ""
            if isinstance(target, list):
                target = target[0] if target else ""
            _mark_contact_bounced(db, org_id, target, extra.get("bounce_reason", ""))
        try:
            db.commit()
        except Exception:
            db.rollback()
        _audit(db, org_id, agent_uuid, source, ext_id, "accepted" if iid else "duplicate",
               interaction_id=iid, payload_bytes=len(raw))
        return {"accepted": True, "event": event_type, "interaction_id": iid}

    # New-message events (received / text / call) → normalise to canonical dict
    try:
        from app.ingestion.adapters.inkbox import normalise_webhook
        canonical = normalise_webhook(body)
    except Exception as e:
        logger.warning(f"inkbox normalise_webhook failed: {e}")
        canonical = None

    if not canonical:
        _audit(db, org_id, agent_uuid, source, None, "rejected_format",
               error=f"unhandled event_type: {event_type}"[:200], payload_bytes=len(raw))
        # 200 OK so Inkbox doesn't retry an event we will never accept.
        return {"accepted": False, "reason": "unsupported_event"}

    schema_cls = insert_fn = None
    if event_type == "message.received":
        schema_cls, insert_fn = EmailIngest, _insert_email
    elif event_type == "text.received":
        # SmsIngest needs from_number/to_number; canonical from adapter has
        # remote_number/direction → translate. MMS media is preserved on the
        # interaction's `attachments` JSONB column post-insert (below).
        rn = canonical.get("remote_number") or ""
        direction = canonical.get("direction") or "inbound"
        media = canonical.get("media") or []
        canonical = {
            "external_id": canonical["external_id"],
            "from_number": rn if direction == "inbound" else "",
            "to_number":   "" if direction == "inbound" else rn,
            "body":        canonical.get("body") or "",
            "sent_at":     canonical.get("sent_at") or "",
            "direction":   direction,
            "_attachments": media,  # underscore-prefixed → not passed to schema
        }
        schema_cls, insert_fn = SmsIngest, _insert_sms
    elif event_type == "phone.incoming_call":
        # In voicemail mode (current default) Inkbox should NEVER hit this
        # branch — we don't register a call webhook URL, so calls go to
        # Inkbox's auto-transcribed voicemail and arrive via the calls poll.
        # This handler stays as a defensive fallback in case someone enables
        # webhook mode out-of-band (e.g. via Inkbox console). We log the
        # call envelope and respond with `reject` (no dead air — Inkbox
        # treats reject as a clean hang-up, not silence).
        # Voice-agent answer + WebSocket bridge will replace this in V2.
        rn = canonical.get("remote_number") or ""
        direction = canonical.get("direction") or "inbound"
        call_body_dict = {
            "external_id": canonical["external_id"],
            "from_number": rn if direction == "inbound" else "",
            "to_number":   "" if direction == "inbound" else rn,
            "duration_sec": 0,
            "transcript":   "",
            "started_at":   canonical.get("started_at") or datetime.now(timezone.utc).isoformat(),
            "direction":    direction,
        }
        try:
            call_body = CallIngest.parse_obj(call_body_dict)
            dup = _find_dup(db, org_id, source, call_body.external_id)
            if not dup:
                contact_id, interaction_id = _insert_call(db, org_id, agent_uuid, call_body)
                db.commit()
                _audit(db, org_id, agent_uuid, source, call_body.external_id, "accepted",
                       interaction_id=interaction_id, contact_id=contact_id, payload_bytes=len(raw))
            else:
                _audit(db, org_id, agent_uuid, source, call_body.external_id, "duplicate",
                       interaction_id=dup[0], contact_id=dup[1], payload_bytes=len(raw))
        except Exception as e:
            db.rollback()
            logger.warning(f"inkbox incoming_call log failed: {e}")
            _audit(db, org_id, agent_uuid, source, None, "rejected_format",
                   error=f"call log: {e}"[:200], payload_bytes=len(raw))
        # SYNCHRONOUS response — tells Inkbox to reject the call.
        return {"action": "reject"}
    else:
        _audit(db, org_id, agent_uuid, source, None, "rejected_format",
               error=f"unrouted event_type: {event_type}"[:200], payload_bytes=len(raw))
        return {"accepted": False, "reason": "unsupported_event"}

    # Email / SMS path — dedupe + insert + enqueue extraction
    attachments = canonical.pop("_attachments", None)  # MMS media, stored post-insert
    try:
        parsed = schema_cls.parse_obj(canonical)
    except Exception as e:
        _audit(db, org_id, agent_uuid, source, None, "rejected_format",
               error=str(e)[:200], payload_bytes=len(raw))
        raise HTTPException(status_code=400, detail={"error": "INVALID_PAYLOAD"})

    dup = _find_dup(db, org_id, source, parsed.external_id)
    if dup:
        _audit(db, org_id, agent_uuid, source, parsed.external_id, "duplicate",
               interaction_id=dup[0], contact_id=dup[1], payload_bytes=len(raw))
        return {"deduped": True, "interaction_id": dup[0], "contact_id": dup[1]}

    try:
        contact_id, interaction_id = insert_fn(db, org_id, agent_uuid, parsed)
        if attachments:
            db.execute(
                text("UPDATE interactions SET attachments = CAST(:a AS jsonb) WHERE id = :id"),
                {"id": interaction_id, "a": json.dumps(attachments)},
            )
        db.commit()
    except Exception as e:
        db.rollback()
        _audit(db, org_id, agent_uuid, source, parsed.external_id, "rejected_format",
               error=f"insert: {e}"[:200], payload_bytes=len(raw))
        raise HTTPException(status_code=400, detail={"error": "INSERT_FAILED"})

    try:
        connector_crud.touch_last_event(db, account_id)
        db.commit()
    except Exception:
        pass
    _enqueue_extraction(interaction_id)

    _audit(db, org_id, agent_uuid, source, parsed.external_id, "accepted",
           interaction_id=interaction_id, contact_id=contact_id, payload_bytes=len(raw))
    return {"deduped": False, "interaction_id": interaction_id, "contact_id": contact_id}


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


# ── Outbound send (agent replies via the connected provider) ─────────────────
# These endpoints let the GeniOS reasoning layer / SDK send mail or SMS back
# through Inkbox (or any other adapter that registers `send_email` /
# `send_sms`). The outbound message is immediately persisted as a direction=
# 'outbound' interaction with delivery_state.status='queued'; the
# message.sent / message.delivered / message.bounced lifecycle webhooks
# above then mutate that row as Inkbox reports back.

class SendEmailRequest(BaseModel):
    to:                    list[str]
    subject:               Optional[str] = None
    body_text:             Optional[str] = None
    body_html:             Optional[str] = None
    cc:                    Optional[list[str]] = None
    bcc:                   Optional[list[str]] = None
    in_reply_to_external_id: Optional[str] = None
    thread_external_id:    Optional[str] = None


class SendSmsRequest(BaseModel):
    to_number:  str
    body:       str
    media_urls: Optional[list[str]] = None


def _load_send_connector(db: Session, org_id: str, agent_uuid: Optional[str], source: str):
    """Pull the active connector for outbound use. Prefers workspace-level row
    (agent_uuid IS NULL), falls back to per-agent. Returns (connector_id,
    provider, decrypted_credentials, mailbox_or_pnid_meta) or None."""
    row = db.execute(
        text("""
            SELECT id::text, metadata
            FROM connector_credentials
            WHERE org_id = :o AND source = :s AND is_active = TRUE
              AND (agent_uuid IS NULL OR agent_uuid = :a)
            ORDER BY (agent_uuid IS NULL) DESC, created_at DESC
            LIMIT 1
        """),
        {"o": org_id, "s": source, "a": agent_uuid},
    ).fetchone()
    if not row:
        return None
    meta = row[1] or {}
    provider = meta.get("provider", "custom")
    try:
        creds = connector_crud.decrypt_metadata(meta)
    except connector_crud.ConnectorDecryptError as e:
        raise HTTPException(status_code=500, detail={"error": "DECRYPT_FAILED", "message": str(e)})
    return row[0], provider, creds, meta


def _persist_outbound(db, org_id, agent_uuid, source, external_id, *,
                      subject="", body="", recipient="", in_reply_to=None,
                      thread=None, attachments=None) -> tuple[Optional[str], Optional[str]]:
    """Insert a direction='outbound' interaction so the UI shows the agent's
    own message immediately. Returns (contact_id, interaction_id). delivery_state
    starts as {status: 'queued'}; the message.sent/delivered webhook flips it
    to 'sent' / 'delivered'."""
    import json as _json
    try:
        if source == "email":
            contact_id = _upsert_contact_by_email(db, org_id, recipient)
            account_id = _resolve_account_id_for_ingest(db, org_id, agent_uuid, "email")
            iid = db.execute(
                text("""
                    INSERT INTO interactions
                        (org_id, contact_id, agent_uuid, account_id, direction,
                         subject, summary, raw_snippet, interaction_at, source,
                         external_id, thread_external_id, interaction_kind,
                         attachments, delivery_state)
                    VALUES (:o, :c, :a, :acct, 'outbound', :subj, :sum, :raw,
                            NOW(), 'email', :ext, :thr, 'email', CAST(:att AS jsonb),
                            CAST(:ds AS jsonb))
                    RETURNING id::text
                """),
                {"o": org_id, "c": contact_id, "a": agent_uuid, "acct": account_id,
                 "subj": (subject or "")[:500], "sum": (body or "")[:2000],
                 "raw": (body or "")[:5000], "ext": external_id or "",
                 "thr": thread or in_reply_to,
                 "att": _json.dumps(attachments or []),
                 "ds": _json.dumps({"status": "queued"})},
            ).scalar()
        elif source == "sms":
            contact_id = _upsert_contact_by_phone(db, org_id, recipient)
            account_id = _resolve_account_id_for_ingest(db, org_id, agent_uuid, "sms")
            iid = db.execute(
                text("""
                    INSERT INTO interactions
                        (org_id, contact_id, agent_uuid, account_id, direction,
                         summary, raw_snippet, interaction_at, source, external_id,
                         interaction_kind, attachments, delivery_state)
                    VALUES (:o, :c, :a, :acct, 'outbound', :sum, :raw, NOW(),
                            'sms', :ext, 'sms', CAST(:att AS jsonb), CAST(:ds AS jsonb))
                    RETURNING id::text
                """),
                {"o": org_id, "c": contact_id, "a": agent_uuid, "acct": account_id,
                 "sum": (body or "")[:2000], "raw": (body or "")[:5000],
                 "ext": external_id or "",
                 "att": _json.dumps(attachments or []),
                 "ds": _json.dumps({"status": "queued"})},
            ).scalar()
        else:
            return None, None
        return contact_id, iid
    except Exception as e:
        logger.warning(f"outbound persist failed ({source}): {e}")
        return None, None


@router.post("/v1/send/email", status_code=202)
async def send_email_route(req: SendEmailRequest,
                            db: Session = Depends(get_db),
                            auth: AuthCtx = Depends(get_auth_ctx)):
    if not auth.org_id:
        raise HTTPException(status_code=401, detail={"error": "AUTH_REQUIRED"})
    if not req.to:
        raise HTTPException(status_code=400, detail={"error": "INVALID_PAYLOAD", "message": "at least one recipient required"})
    if not (req.body_text or req.body_html):
        raise HTTPException(status_code=400, detail={"error": "INVALID_PAYLOAD", "message": "body_text or body_html required"})

    conn = _load_send_connector(db, auth.org_id, auth.agent_uuid, "email")
    if not conn:
        raise HTTPException(status_code=400, detail={"error": "NO_EMAIL_CONNECTOR", "message": "no active email connector for this org"})
    connector_id, provider, creds, _meta = conn

    from app.ingestion import adapters
    ops = adapters.get(provider) or {}
    send_fn = ops.get("send_email")
    if not send_fn:
        raise HTTPException(status_code=501, detail={"error": "PROVIDER_NO_SEND", "message": f"provider '{provider}' does not support outbound send"})

    result = send_fn(
        creds, to=req.to, subject=req.subject or "", body_text=req.body_text or "",
        body_html=req.body_html, in_reply_to_external_id=req.in_reply_to_external_id,
        thread_external_id=req.thread_external_id, cc=req.cc, bcc=req.bcc,
    )

    # Persist the outbound interaction regardless of send result so the agent's
    # action appears in the timeline. delivery_state.status reflects outcome.
    contact_id, iid = _persist_outbound(
        db, auth.org_id, auth.agent_uuid, "email",
        external_id=result.get("external_id") or "",
        subject=req.subject or "", body=req.body_text or req.body_html or "",
        recipient=req.to[0], in_reply_to=req.in_reply_to_external_id,
        thread=req.thread_external_id,
    )
    if iid:
        import json as _json
        final_state = {"status": "sent" if result.get("ok") else "send_failed",
                       "queued_at": datetime.now(timezone.utc).isoformat()}
        if not result.get("ok"):
            final_state["error"] = result.get("error") or "unknown"
        db.execute(
            text("UPDATE interactions SET delivery_state = CAST(:ds AS jsonb) WHERE id = :id"),
            {"id": iid, "ds": _json.dumps(final_state)},
        )
        db.commit()

    if not result.get("ok"):
        raise HTTPException(status_code=502, detail={"error": "SEND_FAILED", "message": result.get("error") or "unknown",
                                                       "provider": provider, "interaction_id": iid})
    return {"interaction_id": iid, "contact_id": contact_id,
            "external_id": result.get("external_id"), "provider": provider}


@router.post("/v1/send/sms", status_code=202)
async def send_sms_route(req: SendSmsRequest,
                          db: Session = Depends(get_db),
                          auth: AuthCtx = Depends(get_auth_ctx)):
    if not auth.org_id:
        raise HTTPException(status_code=401, detail={"error": "AUTH_REQUIRED"})
    if not (req.to_number and req.body):
        raise HTTPException(status_code=400, detail={"error": "INVALID_PAYLOAD", "message": "to_number and body required"})

    conn = _load_send_connector(db, auth.org_id, auth.agent_uuid, "sms")
    if not conn:
        raise HTTPException(status_code=400, detail={"error": "NO_SMS_CONNECTOR", "message": "no active SMS connector for this org"})
    connector_id, provider, creds, _meta = conn

    from app.ingestion import adapters
    ops = adapters.get(provider) or {}
    send_fn = ops.get("send_sms")
    if not send_fn:
        raise HTTPException(status_code=501, detail={"error": "PROVIDER_NO_SEND", "message": f"provider '{provider}' does not support outbound SMS"})

    result = send_fn(creds, to_number=req.to_number, body=req.body, media_urls=req.media_urls)

    attachments = [{"url": u, "content_type": "unknown"} for u in (req.media_urls or [])]
    contact_id, iid = _persist_outbound(
        db, auth.org_id, auth.agent_uuid, "sms",
        external_id=result.get("external_id") or "",
        body=req.body, recipient=req.to_number, attachments=attachments,
    )
    if iid:
        import json as _json
        final_state = {"status": "sent" if result.get("ok") else "send_failed",
                       "queued_at": datetime.now(timezone.utc).isoformat()}
        if not result.get("ok"):
            final_state["error"] = result.get("error") or "unknown"
        db.execute(
            text("UPDATE interactions SET delivery_state = CAST(:ds AS jsonb) WHERE id = :id"),
            {"id": iid, "ds": _json.dumps(final_state)},
        )
        db.commit()

    if not result.get("ok"):
        raise HTTPException(status_code=502, detail={"error": "SEND_FAILED", "message": result.get("error") or "unknown",
                                                       "provider": provider, "interaction_id": iid})
    return {"interaction_id": iid, "contact_id": contact_id,
            "external_id": result.get("external_id"), "provider": provider}
