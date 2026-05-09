"""
Inkbox pull adapter — verified against the actual Inkbox OpenAPI spec
(https://inkbox.ai/api/openapi.json).

Auth:    `X-API-Key: <api_key>`         (Bearer is for console JWTs, not us)
List:    GET /api/v1/mail/mailboxes/{email}/messages?limit=50&direction=inbound
Mark:    PATCH /api/v1/mail/mailboxes/{email}/messages/{id} {"is_read": true}

Message fields from MessageResponse:
  id, mailbox_id, thread_id, message_id, from_address, to_addresses[],
  cc_addresses, subject, snippet, direction (inbound|outbound),
  status, is_read, is_starred, has_attachments, reply_to,
  created_at, sending_domain_warning

Note: list endpoint returns `snippet` (preview) — for full body we'd need to
GET the message-detail endpoint per-id. For ingest we use snippet to keep
sync fast; rich body can be a separate enrichment pass.
"""

from __future__ import annotations

import logging
from typing import Optional

import requests

from . import register

logger = logging.getLogger(__name__)

INKBOX_BASE = "https://inkbox.ai"
TIMEOUT_SEC = 15
MAX_PER_SYNC = 100  # cap to be polite + within rate limits


def _headers(api_key: str) -> dict:
    return {
        "X-API-Key": api_key,
        "Accept": "application/json",
        "User-Agent": "genios-pull/1.0",
    }


def _normalise_email(raw: dict, mailbox_address: str) -> dict:
    """Map Inkbox MessageResponse → canonical /v1/ingest/email payload.

    Phase 12 polish: keeps Inkbox's internal `id` (UUID) as `_inkbox_id` so
    `mark_read` can PATCH directly without re-listing to find the UUID.
    """
    return {
        "external_id":  raw.get("message_id") or raw.get("id") or "",
        "from_address": raw.get("from_address") or "",
        "to":           raw.get("to_addresses") or ([mailbox_address] if mailbox_address else []),
        "subject":      raw.get("subject") or "",
        "body_text":    raw.get("snippet") or "",
        "sent_at":      raw.get("created_at") or "",
        "direction":    raw.get("direction") or "inbound",
        "thread_external_id":      raw.get("thread_id"),
        "in_reply_to_external_id": raw.get("reply_to"),
        # Out-of-band: not part of canonical schema, used only by mark_read
        "_inkbox_id": raw.get("id"),
    }


def fetch_emails(credentials: dict, since_iso: Optional[str] = None) -> list[dict]:
    """Pull recent unread inbound messages for an Inkbox mailbox.

    `credentials` shape:
        { "api_key": "...", "mailbox_address": "agent@inkboxmail.com" }

    The list endpoint doesn't take `since` — it pages by `cursor`. We pull
    the first page (up to 50) and let server-side idempotency (external_id)
    skip already-stored messages.
    """
    key = (credentials.get("api_key") or "").strip()
    mailbox = (credentials.get("mailbox_address") or credentials.get("account") or "").strip().lower()
    if not key:
        raise ValueError("inkbox adapter: api_key required in credentials")
    if not mailbox:
        raise ValueError("inkbox adapter: mailbox_address required in credentials")

    url = f"{INKBOX_BASE}/api/v1/mail/mailboxes/{mailbox}/messages"
    params = {"limit": min(MAX_PER_SYNC, 100), "direction": "inbound"}

    try:
        r = requests.get(url, headers=_headers(key), params=params, timeout=TIMEOUT_SEC)
    except requests.RequestException as e:
        logger.warning(f"inkbox fetch failed (network): {e}")
        return []

    if r.status_code == 401 or r.status_code == 403:
        raise PermissionError(f"inkbox: {r.status_code} — API key invalid or revoked")
    if r.status_code == 404:
        logger.warning(f"inkbox mailbox not found: {mailbox}")
        return []
    if r.status_code >= 400:
        logger.warning(f"inkbox fetch failed: {r.status_code} {r.text[:200]}")
        return []

    try:
        data = r.json()
    except ValueError:
        logger.warning("inkbox response not JSON")
        return []

    # CursorPage response: {"items": [...], "cursor": "..."}
    rows = data.get("items") or data.get("data") or data.get("messages") or []
    return [
        _normalise_email(row, mailbox)
        for row in rows
        if row and not row.get("is_read")  # skip already-read
    ]


def mark_read(credentials: dict, external_id_or_event: object) -> bool:
    """PATCH the message to set is_read=true so next sync skips it.

    Accepts either:
      * the canonical event dict (preferred — has `_inkbox_id` for direct PATCH)
      * the raw external_id string (fallback — does a list+search to find UUID)
    """
    key = (credentials.get("api_key") or "").strip()
    mailbox = (credentials.get("mailbox_address") or "").strip().lower()
    if not (key and mailbox):
        return False

    # Path A: direct PATCH using the internal id we already have
    if isinstance(external_id_or_event, dict):
        internal_id = external_id_or_event.get("_inkbox_id")
        if internal_id:
            try:
                rp = requests.patch(
                    f"{INKBOX_BASE}/api/v1/mail/mailboxes/{mailbox}/messages/{internal_id}",
                    headers={**_headers(key), "Content-Type": "application/json"},
                    json={"is_read": True}, timeout=TIMEOUT_SEC,
                )
                return rp.status_code < 400
            except requests.RequestException:
                return False
        external_id = external_id_or_event.get("external_id")
    else:
        external_id = external_id_or_event

    if not external_id:
        return False

    # Path B (fallback): re-list and search by message_id — slower
    try:
        list_url = f"{INKBOX_BASE}/api/v1/mail/mailboxes/{mailbox}/messages"
        r = requests.get(list_url, headers=_headers(key), params={"limit": 50}, timeout=TIMEOUT_SEC)
        if r.status_code != 200:
            return False
        items = (r.json() or {}).get("items") or []
        match = next((m for m in items if m.get("message_id") == external_id), None)
        if not match:
            return False
        internal_id = match.get("id")
        rp = requests.patch(
            f"{INKBOX_BASE}/api/v1/mail/mailboxes/{mailbox}/messages/{internal_id}",
            headers={**_headers(key), "Content-Type": "application/json"},
            json={"is_read": True}, timeout=TIMEOUT_SEC,
        )
        return rp.status_code < 400
    except requests.RequestException:
        return False


# ── Webhook payload normaliser ───────────────────────────────────────────────
# Inkbox sends: {event_type, timestamp, data: MailWebhookMessageData}
# Used by the /v1/ingest webhook receiver when integration uses push instead.
def normalise_webhook(payload: dict) -> Optional[dict]:
    """Map an Inkbox MailWebhookPayload → canonical ingest event.
    Returns None for non-email events."""
    if not isinstance(payload, dict):
        return None
    if payload.get("event_type") not in ("message.received",):
        return None
    data = payload.get("data") or {}
    if not data.get("id"):
        return None
    return {
        "external_id":  data.get("message_id") or data.get("id"),
        "from_address": data.get("from_address") or "",
        "to":           data.get("to_addresses") or [],
        "subject":      data.get("subject") or "",
        "body_text":    data.get("snippet") or "",
        "sent_at":      data.get("created_at") or "",
        "direction":    data.get("direction") or "inbound",
        "thread_external_id": data.get("thread_id"),
    }


def verify_credentials(credentials: dict) -> tuple[bool, str]:
    """Pre-flight check called at connect-time. Hits GET /mailboxes/{email}
    to confirm (a) API key is valid, (b) mailbox exists, (c) key has access.

    Returns (ok, message). On success, message is the verified mailbox label.
    On failure, message is a human-readable error suitable for surfacing in
    the dashboard ("Invalid API key", "Mailbox not found", etc.).
    """
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


def _register():
    register("inkbox", {
        "fetch_email":       fetch_emails,
        "mark_read":         mark_read,
        "normalise_webhook": normalise_webhook,
        "verify":            verify_credentials,
    })


_register()
