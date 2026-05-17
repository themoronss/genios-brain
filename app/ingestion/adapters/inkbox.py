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
import re
from typing import Optional

import requests

from . import register

# Inkbox API keys are pure ASCII (ApiKey_<uuid>.<token>). Pasting from the
# console sometimes drags in NBSP, zero-width space, or smart quotes — those
# blow up `requests` later with `UnicodeEncodeError: latin-1 codec can't
# encode...` when set on the X-API-Key header. Strip anything outside the
# printable-ASCII range up front.
_NON_PRINTABLE_ASCII = re.compile(r"[^\x21-\x7e]")


def _clean_key(k: Optional[str]) -> str:
    return _NON_PRINTABLE_ASCII.sub("", k or "")

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


def _request_json(method: str, url: str, key: str, body: Optional[dict] = None) -> tuple[int, Optional[dict]]:
    """POST/PATCH helper. Returns (status_code, parsed_json|None). Never raises
    on HTTP errors — webhook-registration callers want to log + continue, not
    crash the connect flow."""
    try:
        r = requests.request(
            method, url, headers={**_headers(key), "Content-Type": "application/json"},
            json=body or {}, timeout=TIMEOUT_SEC,
        )
    except requests.RequestException as e:
        logger.warning(f"inkbox {method} {url} failed (network): {e}")
        return 0, None
    if r.status_code in (401, 403):
        raise PermissionError(f"inkbox {r.status_code} at {url} — API key invalid, revoked, or lacks scope")
    payload: Optional[dict] = None
    try:
        payload = r.json() if r.content else None
    except ValueError:
        payload = None
    if r.status_code >= 400:
        logger.warning(f"inkbox {method} {url} → {r.status_code} {r.text[:200]}")
    return r.status_code, payload


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
    key = _clean_key(credentials.get("api_key"))
    mailbox = _clean_key(credentials.get("mailbox_address") or credentials.get("account")).lower()
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
    pnid = _clean_key(credentials.get("phone_number_id") or credentials.get("phone_id"))
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
    key = _clean_key(credentials.get("api_key"))
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
    key = _clean_key(credentials.get("api_key"))
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
    """Map an Inkbox webhook (mail / text / phone) → canonical ingest event.

    Handled event_type values:
      - message.received       → email path (uses _normalise_email)
      - text.received          → SMS path (uses _normalise_sms)
      - phone.incoming_call    → voice path (uses _normalise_call w/o transcript)

    Returns None for anything else; the caller (ingest.py) then falls back to
    treating the payload as already-canonical."""
    if not isinstance(payload, dict):
        return None
    et = payload.get("event_type") or ""
    data = payload.get("data") or {}

    if et == "message.received":
        if not (data.get("id") or data.get("message_id")):
            return None
        return _normalise_email(data, "")

    if et == "text.received":
        # Inkbox docs: data contains the stored inbound text record. Pull-endpoint
        # response shape (used by _normalise_sms) is the same record, so reuse.
        raw = data.get("text_message") or data
        if not isinstance(raw, dict):
            return None
        return _normalise_sms(raw)

    if et == "phone.incoming_call":
        # Inbound call notification. Transcripts arrive on completion (pull-only),
        # so for the push event we just record the call envelope.
        raw = data.get("call") or data
        if not isinstance(raw, dict):
            return None
        return _normalise_call(raw, transcript="")

    return None


def verify_credentials(credentials: dict) -> tuple[bool, str]:
    """Connect-time check: GET /mailboxes/{email} confirms the API key is valid,
    the mailbox exists, and the key can access it. Returns (ok, message)."""
    raw_key = (credentials.get("api_key") or "").strip()
    key = _clean_key(raw_key)
    mailbox = _clean_key(credentials.get("mailbox_address")).lower()
    if not key:
        return False, "API key is required"
    if not mailbox:
        return False, "Mailbox address is required"
    if key != raw_key:
        # Heuristic: smart quotes / NBSP / ZWSP got pasted in. Tell the user
        # before we even hit Inkbox — otherwise requests crashes on header encode.
        return False, "API key has hidden characters (smart quotes / non-breaking spaces). Re-copy from Inkbox console into a plain field."
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


# ── OUTBOUND SEND ────────────────────────────────────────────────────────────
# Read-side adapters above pull data INTO Genios. These send adapters are
# how an agent (or the reasoning layer) replies BACK through Inkbox. Each
# returns a dict: {ok: bool, external_id: <inkbox-id-or-None>, error: str?}
# so the API caller can persist an outbound interaction immediately and
# track its delivery_state lifecycle via the webhook handler.

class InkboxSendError(RuntimeError):
    """Raised when Inkbox refuses a send (rate limit, invalid recipient, key
    lacks scope, etc.). API layer should surface the .detail string to the
    caller — these are USER-correctable errors, not bugs."""
    def __init__(self, detail: str, status: int = 0):
        super().__init__(detail)
        self.detail = detail
        self.status = status


def send_email(credentials: dict, to: list[str], subject: str, body_text: str,
               body_html: Optional[str] = None,
               in_reply_to_external_id: Optional[str] = None,
               thread_external_id: Optional[str] = None,
               cc: Optional[list[str]] = None,
               bcc: Optional[list[str]] = None) -> dict:
    """Send mail through the connected Inkbox mailbox. Threading hints
    (in_reply_to / thread_id) are passed through so replies actually thread
    on the recipient's side. Returns {ok, external_id, error?}."""
    key = _clean_key(credentials.get("api_key"))
    mailbox = _clean_key(credentials.get("mailbox_address")).lower()
    if not key:
        return {"ok": False, "external_id": None, "error": "api_key required"}
    if not mailbox:
        return {"ok": False, "external_id": None, "error": "mailbox_address required"}
    if not to:
        return {"ok": False, "external_id": None, "error": "at least one recipient required"}
    payload: dict = {
        "to": [a for a in (a.strip() for a in to) if a],
        "subject": (subject or "")[:998],
        "body_text": body_text or "",
    }
    if body_html:
        payload["body_html"] = body_html
    if in_reply_to_external_id:
        payload["in_reply_to"] = in_reply_to_external_id
    if thread_external_id:
        payload["thread_id"] = thread_external_id
    if cc:
        payload["cc"] = [a for a in (a.strip() for a in cc) if a]
    if bcc:
        payload["bcc"] = [a for a in (a.strip() for a in bcc) if a]
    url = f"{INKBOX_BASE}/api/v1/mail/mailboxes/{mailbox}/messages"
    status, body = _request_json("POST", url, key, body=payload)
    if status >= 400:
        detail = (body or {}).get("error") or (body or {}).get("message") or f"inkbox returned {status}"
        return {"ok": False, "external_id": None, "error": detail, "status": status}
    ext = (body or {}).get("message_id") or (body or {}).get("id") or None
    return {"ok": True, "external_id": str(ext) if ext else None, "raw": body}


def send_sms(credentials: dict, to_number: str, body: str,
             media_urls: Optional[list[str]] = None) -> dict:
    """Send SMS / MMS through the connected Inkbox phone number. Pass
    `media_urls` (list of HTTPS URLs Inkbox can fetch) for MMS. Returns
    {ok, external_id, error?}."""
    key = _clean_key(credentials.get("api_key"))
    if not key:
        return {"ok": False, "external_id": None, "error": "api_key required"}
    pnid = _resolve_phone_number_id(credentials, key)
    if not pnid:
        return {"ok": False, "external_id": None, "error": "no phone_number_id resolvable from credentials"}
    to_clean = (to_number or "").strip()
    if not to_clean:
        return {"ok": False, "external_id": None, "error": "to_number required"}
    payload: dict = {"to_number": to_clean, "body": body or ""}
    if media_urls:
        payload["media"] = [u.strip() for u in media_urls if u and u.strip()]
    url = f"{INKBOX_BASE}/api/v1/phone/numbers/{pnid}/texts"
    status, resp = _request_json("POST", url, key, body=payload)
    if status >= 400:
        detail = (resp or {}).get("error") or (resp or {}).get("message") or f"inkbox returned {status}"
        return {"ok": False, "external_id": None, "error": detail, "status": status}
    ext = (resp or {}).get("id") or (resp or {}).get("text_id") or None
    return {"ok": True, "external_id": str(ext) if ext else None, "raw": resp}


# ── WEBHOOK REGISTRATION ─────────────────────────────────────────────────────
# Inkbox has no webhook CRUD API. The webhook URL is a field on each resource:
#   • Mailbox    PATCH /api/v1/mail/mailboxes/{email}       body: {"webhook_url": ...}
#   • PhoneNum   PATCH /api/v1/phone/numbers/{phone_id}     body: {"incoming_text_webhook_url",
#                                                                   "incoming_call_webhook_url",
#                                                                   "incoming_call_action": "webhook"}
# Signing keys are org-wide and created via POST /api/v1/signing-keys. The
# plaintext is returned ONLY ONCE — store immediately.

def bootstrap_signing_key(api_key: str) -> Optional[str]:
    """Mint a new org-wide Inkbox signing key. Returns the plaintext secret
    (caller must persist immediately — Inkbox never reveals it again), or None
    on failure. Idempotency is the caller's responsibility: don't call this if
    the org already has a stored signing secret."""
    key = _clean_key(api_key)
    if not key:
        return None
    url = f"{INKBOX_BASE}/api/v1/signing-keys"
    status, body = _request_json("POST", url, key, body={"description": "genios-brain webhook signer"})
    if status >= 400 or not isinstance(body, dict):
        return None
    return body.get("plaintext") or body.get("secret") or body.get("key") or body.get("signing_key")


def register_mail_webhook(api_key: str, mailbox_address: str, webhook_url: str) -> bool:
    """PATCH the mailbox to install a webhook URL for inbound mail events.
    Returns True on success."""
    key = _clean_key(api_key)
    mailbox = _clean_key(mailbox_address).lower()
    if not (key and mailbox and webhook_url):
        return False
    url = f"{INKBOX_BASE}/api/v1/mail/mailboxes/{mailbox}"
    status, _ = _request_json("PATCH", url, key, body={"webhook_url": webhook_url})
    return 200 <= status < 300


def register_phone_webhook(api_key: str, phone_number_id: str,
                           sms_webhook_url: Optional[str] = None,
                           call_webhook_url: Optional[str] = None) -> bool:
    """PATCH a phone number to install SMS and/or incoming-call webhook URLs.

    SMS: setting `sms_webhook_url` enables real-time inbound text delivery.

    Incoming calls: we DO NOT set `incoming_call_webhook_url` by default
    because `phone.incoming_call` is a SYNCHRONOUS handshake — our endpoint
    must answer the call (bridge audio over WebSocket) or reject it.
    Rejecting drops the call entirely (caller hears dead air). Until the AI
    voice-agent stack is in place we keep `incoming_call_action='voicemail'`
    so callers leave a message that Inkbox auto-transcribes; we pull those
    transcripts via the existing calls poll. This is graceful degradation
    rather than dropped calls. When a voice agent is ready, pass
    `call_webhook_url=...` and we'll PATCH it on + flip the action.

    Returns True if at least one URL was successfully installed."""
    key = _clean_key(api_key)
    pnid = _clean_key(phone_number_id)
    if not (key and pnid and (sms_webhook_url or call_webhook_url)):
        return False
    body: dict = {}
    if sms_webhook_url:
        body["incoming_text_webhook_url"] = sms_webhook_url
    if call_webhook_url:
        # Caller has opted in to AI call-answer mode.
        body["incoming_call_webhook_url"] = call_webhook_url
        body["incoming_call_action"] = "webhook"
    else:
        # Explicitly keep voicemail as the default so callers never hit dead air.
        body["incoming_call_action"] = "voicemail"
    url = f"{INKBOX_BASE}/api/v1/phone/numbers/{pnid}"
    status, _ = _request_json("PATCH", url, key, body=body)
    return 200 <= status < 300


def deregister_mail_webhook(api_key: str, mailbox_address: str) -> bool:
    """Clear the mailbox webhook URL (PATCH to null). Used on disconnect."""
    key = _clean_key(api_key)
    mailbox = _clean_key(mailbox_address).lower()
    if not (key and mailbox):
        return False
    url = f"{INKBOX_BASE}/api/v1/mail/mailboxes/{mailbox}"
    status, _ = _request_json("PATCH", url, key, body={"webhook_url": None})
    return 200 <= status < 300


def deregister_phone_webhook(api_key: str, phone_number_id: str,
                             clear_sms: bool = True, clear_call: bool = True) -> bool:
    """Clear SMS and/or call webhook URLs on a phone number."""
    key = _clean_key(api_key)
    pnid = _clean_key(phone_number_id)
    if not (key and pnid):
        return False
    body: dict = {}
    if clear_sms:
        body["incoming_text_webhook_url"] = None
    if clear_call:
        body["incoming_call_webhook_url"] = None
        body["incoming_call_action"] = "voicemail"
    if not body:
        return False
    url = f"{INKBOX_BASE}/api/v1/phone/numbers/{pnid}"
    status, _ = _request_json("PATCH", url, key, body=body)
    return 200 <= status < 300


def list_phone_numbers(credentials: dict) -> list[dict]:
    """Best-effort: return the phone numbers this API key can see (id + number).
    Empty if the key has no phone scope. Used to auto-provision sms/call pull."""
    key = _clean_key(credentials.get("api_key"))
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
        # Outbound — agent replies / new sends via Inkbox.
        "send_email":        send_email,
        "send_sms":          send_sms,
    }
    register("inkbox", ops)


_register()
