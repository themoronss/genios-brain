"""
Inkbox pull adapter — verified against the Inkbox docs + OpenAPI spec
(https://inkbox.ai/docs, https://inkbox.ai/api/openapi.json).

Auth:  `X-API-Key: <api_key>`  (admin- or agent-scoped; Bearer is for console
JWTs, not us). Override the API base with `INKBOX_BASE_URL` for staging /
self-hosted Inkbox deployments.

Channels we pull (mirrors what we do for Gmail/Calendar — periodic pull, plus
Inkbox can also push via webhooks → see app/api/routes/ingest.py):

  email  GET /api/v1/mail/mailboxes/{email}/messages?limit=&cursor=&direction=
  sms    GET /api/v1/phone/numbers/{phone_number_id}/texts?limit=&cursor=
  calls  GET /api/v1/phone/numbers/{phone_number_id}/calls?limit=&cursor=
         GET /api/v1/phone/numbers/{phone_number_id}/calls/{call_id}/transcripts

Sync strategy (all channels): pull the most-recent `*_MAX_PER_SYNC` items,
paging via `cursor`, regardless of read state. We deliberately do NOT filter
by `is_read` and do NOT mark anything read/seen — the brain is a read-only
observer; mutating the customer's mailbox/inbox was wrong and also meant the
*first* sync pulled nothing if the mailbox already had read mail. Inkbox list
endpoints take no `since`; downstream idempotency on `(org_id, source,
external_id)` makes repeated polls a cheap no-op.

Field names below are read defensively (the docs and OpenAPI summaries differ
on e.g. `from` vs `from_address`, `body` vs `snippet`), so the adapter keeps
working if Inkbox renames a field.
"""

from __future__ import annotations

import logging
import os
from typing import Optional

import requests

from . import register

logger = logging.getLogger(__name__)

INKBOX_BASE = (os.getenv("INKBOX_BASE_URL", "https://inkbox.ai") or "https://inkbox.ai").rstrip("/")
TIMEOUT_SEC = 15
PAGE_SIZE = 100
MAX_PAGES = 10  # hard safety cap on pagination loops


def _env_int(name: str, default: int) -> int:
    try:
        return max(1, int(os.getenv(name, str(default))))
    except (TypeError, ValueError):
        return default


EMAIL_MAX_PER_SYNC = _env_int("INKBOX_MAX_PER_SYNC", 200)
SMS_MAX_PER_SYNC   = _env_int("INKBOX_SMS_MAX_PER_SYNC", 200)
CALL_MAX_PER_SYNC  = _env_int("INKBOX_CALL_MAX_PER_SYNC", 50)
# Back-compat alias (used to be the only knob)
MAX_PER_SYNC = EMAIL_MAX_PER_SYNC


# ── HTTP helpers ─────────────────────────────────────────────────────────────

def _headers(api_key: str) -> dict:
    return {
        "X-API-Key": api_key,
        "Accept": "application/json",
        "User-Agent": "genios-pull/1.0",
    }


def _get_json(url: str, key: str, params: Optional[dict] = None,
              not_found_ok: bool = True) -> Optional[dict]:
    """GET → parsed JSON, or None on any non-fatal failure. Raises PermissionError
    on 401/403 so the caller can flag the connector as auth_failed."""
    try:
        r = requests.get(url, headers=_headers(key), params=params or {}, timeout=TIMEOUT_SEC)
    except requests.RequestException as e:
        logger.warning(f"inkbox GET {url} failed (network): {e}")
        return None
    if r.status_code in (401, 403):
        raise PermissionError(f"inkbox {r.status_code} at {url} — API key invalid, revoked, or lacks scope")
    if r.status_code == 404:
        if not not_found_ok:
            raise PermissionError(f"inkbox 404 at {url} — resource not found")
        logger.warning(f"inkbox 404: {url}")
        return None
    if r.status_code >= 400:
        logger.warning(f"inkbox GET {url} failed: {r.status_code} {r.text[:200]}")
        return None
    try:
        return r.json()
    except ValueError:
        logger.warning(f"inkbox response not JSON: {url}")
        return None


def _items(data: Optional[dict]) -> list:
    if not isinstance(data, dict):
        return data if isinstance(data, list) else []
    return data.get("items") or data.get("data") or data.get("messages") or data.get("results") or []


def _next_cursor(data: Optional[dict]) -> Optional[str]:
    if not isinstance(data, dict):
        return None
    return data.get("cursor") or data.get("next_cursor") or data.get("next") or None


def _paginate(url: str, key: str, base_params: dict, max_items: int) -> list:
    """Follow `cursor` pages, accumulating raw items up to `max_items`."""
    out: list = []
    cursor: Optional[str] = None
    for _ in range(MAX_PAGES):
        params = dict(base_params)
        params["limit"] = PAGE_SIZE
        if cursor:
            params["cursor"] = cursor
        data = _get_json(url, key, params)
        rows = _items(data)
        out.extend(r for r in rows if r)
        cursor = _next_cursor(data)
        if not cursor or not rows or len(out) >= max_items:
            break
    return out[:max_items]


# ── Address coercion (Inkbox returns strings *or* {email,name} dicts) ────────

def _addr(x) -> str:
    if isinstance(x, dict):
        return (x.get("email") or x.get("address") or x.get("value") or "").strip()
    if isinstance(x, str):
        return x.strip()
    return ""


def _addr_list(x) -> list[str]:
    if isinstance(x, list):
        return [a for a in (_addr(i) for i in x) if a]
    a = _addr(x)
    return [a] if a else []


def _first(*vals):
    for v in vals:
        if v not in (None, "", [], {}):
            return v
    return None


# ── EMAIL ────────────────────────────────────────────────────────────────────

def _normalise_email(raw: dict, mailbox_address: str) -> dict:
    return {
        "external_id":  _first(raw.get("message_id"), raw.get("rfc822_message_id"), raw.get("id")) or "",
        "from_address": _addr(_first(raw.get("from"), raw.get("from_address"), raw.get("sender"))),
        "to":           _addr_list(_first(raw.get("to"), raw.get("to_addresses"))) or ([mailbox_address] if mailbox_address else []),
        "subject":      raw.get("subject") or "",
        "body_text":    _first(raw.get("body_text"), raw.get("body"), raw.get("text"),
                               raw.get("body_html"), raw.get("html"), raw.get("snippet")) or "",
        "sent_at":      _first(raw.get("sent_at"), raw.get("created_at"), raw.get("date")) or "",
        "direction":    raw.get("direction") or "inbound",
        "thread_external_id":      _first(raw.get("thread_id"), raw.get("thread_external_id")),
        "in_reply_to_external_id": _first(raw.get("reply_to"), raw.get("in_reply_to"),
                                          raw.get("in_reply_to_message_id")),
    }


def fetch_emails(credentials: dict, since_iso: Optional[str] = None) -> list[dict]:
    """Pull recent inbound messages for an Inkbox mailbox.
    credentials: { api_key, mailbox_address }."""
    key = (credentials.get("api_key") or "").strip()
    mailbox = (credentials.get("mailbox_address") or credentials.get("account") or "").strip().lower()
    if not key:
        raise ValueError("inkbox adapter: api_key required in credentials")
    if not mailbox:
        raise ValueError("inkbox adapter: mailbox_address required in credentials")
    url = f"{INKBOX_BASE}/api/v1/mail/mailboxes/{mailbox}/messages"
    rows = _paginate(url, key, {"direction": "inbound"}, EMAIL_MAX_PER_SYNC)
    return [_normalise_email(r, mailbox) for r in rows]


# ── PHONE NUMBER RESOLUTION ──────────────────────────────────────────────────

def _resolve_phone_number_id(credentials: dict, key: str) -> Optional[str]:
    """Use the stored phone_number_id, else discover the agent's first number."""
    pnid = (credentials.get("phone_number_id") or credentials.get("phone_id") or "").strip()
    if pnid:
        return pnid
    data = _get_json(f"{INKBOX_BASE}/api/v1/phone/numbers", key)
    for row in _items(data):
        rid = (row or {}).get("id") or (row or {}).get("phone_number_id")
        if rid:
            return str(rid)
    return None


# ── SMS / MMS ────────────────────────────────────────────────────────────────

def _normalise_sms(raw: dict) -> Optional[dict]:
    if raw.get("is_blocked"):
        return None
    ext = _first(raw.get("id"), raw.get("text_id"), raw.get("message_id"))
    if not ext:
        return None
    return {
        "external_id":   str(ext),
        "direction":     raw.get("direction") or "inbound",
        "remote_number": _first(raw.get("remote_number"), raw.get("from_number"),
                                raw.get("to_number"), raw.get("from"), raw.get("to")) or "",
        "body":          _first(raw.get("body"), raw.get("text"), raw.get("message")) or "",
        "sent_at":       _first(raw.get("created_at"), raw.get("sent_at"), raw.get("timestamp")) or "",
        "media":         raw.get("media") or raw.get("attachments") or [],
    }


def fetch_sms(credentials: dict, since_iso: Optional[str] = None) -> list[dict]:
    """Pull recent SMS/MMS for an Inkbox phone number.
    credentials: { api_key, phone_number_id? } — number is auto-discovered if absent."""
    key = (credentials.get("api_key") or "").strip()
    if not key:
        raise ValueError("inkbox adapter: api_key required in credentials")
    pnid = _resolve_phone_number_id(credentials, key)
    if not pnid:
        raise PermissionError("inkbox: no phone number available for this API key")
    url = f"{INKBOX_BASE}/api/v1/phone/numbers/{pnid}/texts"
    rows = _paginate(url, key, {}, SMS_MAX_PER_SYNC)
    out = []
    for r in rows:
        ev = _normalise_sms(r)
        if ev:
            out.append(ev)
    return out


# ── VOICE CALLS (+ transcripts) ──────────────────────────────────────────────

def _party_label(p) -> str:
    return {"local": "Agent", "remote": "Caller"}.get((p or "").lower(), (p or "speaker"))


def _fetch_transcript(base_url: str, key: str, call_id: str) -> str:
    data = _get_json(f"{base_url}/calls/{call_id}/transcripts", key)
    segs = _items(data)
    if not segs:
        return ""
    try:
        segs = sorted(segs, key=lambda s: (s or {}).get("start_time") or 0)
    except Exception:
        pass
    lines = []
    for s in segs:
        s = s or {}
        txt = (s.get("text") or s.get("transcript") or "").strip()
        if txt:
            lines.append(f"{_party_label(s.get('party'))}: {txt}")
    return "\n".join(lines)


def _normalise_call(raw: dict, transcript: str) -> Optional[dict]:
    if raw.get("is_blocked"):
        return None
    ext = _first(raw.get("id"), raw.get("call_id"))
    if not ext:
        return None
    try:
        dur = int(_first(raw.get("duration_seconds"), raw.get("duration_sec"), raw.get("duration")) or 0)
    except (TypeError, ValueError):
        dur = 0
    return {
        "external_id":   str(ext),
        "direction":     raw.get("direction") or "inbound",
        "remote_number": _first(raw.get("remote_number"), raw.get("from_number"), raw.get("to_number")) or "",
        "duration_sec":  dur,
        "transcript":    transcript or "",
        "started_at":    _first(raw.get("created_at"), raw.get("started_at"), raw.get("start_time")) or "",
    }


def fetch_calls(credentials: dict, since_iso: Optional[str] = None) -> list[dict]:
    """Pull recent voice calls (with transcripts) for an Inkbox phone number.
    credentials: { api_key, phone_number_id? }."""
    key = (credentials.get("api_key") or "").strip()
    if not key:
        raise ValueError("inkbox adapter: api_key required in credentials")
    pnid = _resolve_phone_number_id(credentials, key)
    if not pnid:
        raise PermissionError("inkbox: no phone number available for this API key")
    base_url = f"{INKBOX_BASE}/api/v1/phone/numbers/{pnid}"
    rows = _paginate(f"{base_url}/calls", key, {}, CALL_MAX_PER_SYNC)
    out = []
    for r in rows:
        if not r or r.get("is_blocked"):
            continue
        call_id = _first(r.get("id"), r.get("call_id"))
        transcript = _fetch_transcript(base_url, key, str(call_id)) if call_id else ""
        ev = _normalise_call(r, transcript)
        if ev:
            out.append(ev)
    return out


# ── Webhook payload normaliser (push mode — see ingest.py) ───────────────────
# Inkbox sends: {event_type, timestamp, data: {...}}.
def normalise_webhook(payload: dict) -> Optional[dict]:
    """Map an Inkbox mail webhook → canonical email ingest event. Returns None
    for non-(mail-received) events (SMS/call webhooks arrive on their own routes)."""
    if not isinstance(payload, dict):
        return None
    if payload.get("event_type") not in ("message.received",):
        return None
    data = payload.get("data") or {}
    if not (data.get("id") or data.get("message_id")):
        return None
    return _normalise_email(data, "")


def verify_credentials(credentials: dict) -> tuple[bool, str]:
    """Connect-time check: GET /mailboxes/{email} confirms the API key is valid,
    the mailbox exists, and the key can access it. Returns (ok, message)."""
    key = (credentials.get("api_key") or "").strip()
    mailbox = (credentials.get("mailbox_address") or "").strip().lower()
    if not key:
        return False, "API key is required"
    if not mailbox:
        return False, "Mailbox address is required"
    try:
        r = requests.get(
            f"{INKBOX_BASE}/api/v1/mail/mailboxes/{mailbox}",
            headers=_headers(key), timeout=TIMEOUT_SEC,
        )
    except requests.RequestException as e:
        return False, f"Inkbox unreachable: {e}"
    if r.status_code in (401, 403):
        return False, "Invalid Inkbox API key"
    if r.status_code == 404:
        return False, f"Mailbox '{mailbox}' not found in your Inkbox org"
    if r.status_code >= 400:
        return False, f"Inkbox error {r.status_code}: {r.text[:120]}"
    return True, mailbox


def list_phone_numbers(credentials: dict) -> list[dict]:
    """Best-effort: return the phone numbers this API key can see (id + number).
    Empty if the key has no phone scope. Used to auto-provision sms/call pull."""
    key = (credentials.get("api_key") or "").strip()
    if not key:
        return []
    try:
        data = _get_json(f"{INKBOX_BASE}/api/v1/phone/numbers", key)
    except PermissionError:
        return []
    out = []
    for row in _items(data):
        row = row or {}
        rid = row.get("id") or row.get("phone_number_id")
        if rid:
            out.append({"phone_number_id": str(rid),
                        "phone_number": row.get("phone_number") or row.get("number") or row.get("e164") or ""})
    return out


def _register():
    # No mark_read / mark_seen: the brain is a read-only observer — we never
    # mutate the customer's mailbox/inbox. Dedup is the external_id unique index.
    ops = {
        "fetch_email":       fetch_emails,
        "fetch_sms":         fetch_sms,
        "fetch_calls":       fetch_calls,
        "normalise_webhook": normalise_webhook,
        "verify":            verify_credentials,
    }
    register("inkbox", ops)


_register()
