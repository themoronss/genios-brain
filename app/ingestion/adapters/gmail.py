"""
Gmail pull adapter — per-agent variant.

Reuses the existing Gmail connector helpers (`build_gmail_service`,
list/parse) but pulls credentials from `connector_credentials.metadata`
instead of the workspace-level `oauth_tokens` table.

Returns canonical email events for the generic insert pipeline.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from . import register

logger = logging.getLogger(__name__)


def _to_iso(ts) -> str:
    """Convert Gmail's epoch ms or a datetime to ISO 8601."""
    if ts is None:
        return ""
    if isinstance(ts, (int, float)):
        return datetime.fromtimestamp(ts / 1000, tz=timezone.utc).isoformat()
    if isinstance(ts, datetime):
        return ts.isoformat()
    return str(ts)


def _normalise(msg: dict, account_email: str) -> dict:
    """Map Gmail's parsed message → canonical /v1/ingest/email payload."""
    from_addr = (msg.get("from") or "").strip()
    to_field = msg.get("to") or ""
    to_list = [a.strip() for a in to_field.split(",") if a.strip()] if isinstance(to_field, str) else (to_field or [])

    return {
        "external_id":  msg.get("message_id") or msg.get("id") or "",
        "from_address": from_addr,
        "to":           to_list or ([account_email] if account_email else []),
        "subject":      msg.get("subject") or "",
        "body_text":    msg.get("snippet") or msg.get("body_text") or msg.get("body") or "",
        "sent_at":      _to_iso(msg.get("date") or msg.get("internal_date_ms")),
        "direction":    "inbound" if (account_email and account_email in (to_field or "").lower()) else "outbound",
        "thread_external_id": msg.get("thread_id"),
        "in_reply_to_external_id": msg.get("in_reply_to"),
    }


def fetch_emails(credentials: dict, since_iso: Optional[str] = None) -> list[dict]:
    """credentials shape (post-decrypt):
        {
          "access_token": "...",
          "refresh_token": "...",
          "account": "user@gmail.com",
        }
    """
    access = credentials.get("access_token")
    refresh = credentials.get("refresh_token")
    account = credentials.get("account") or credentials.get("mailbox_address") or ""
    if not access or not refresh:
        raise ValueError("gmail adapter: access_token + refresh_token required")

    try:
        from app.ingestion.gmail_connector import build_gmail_service
    except Exception as e:
        logger.error(f"gmail_connector import failed: {e}")
        return []

    try:
        service = build_gmail_service(access, refresh)
    except Exception as e:
        logger.warning(f"gmail service build failed: {e}")
        return []

    # Pull recent unread (cap at 50/sync to stay polite + within rate limits).
    try:
        result = service.users().messages().list(
            userId="me", labelIds=["INBOX", "UNREAD"], maxResults=50,
        ).execute()
    except Exception as e:
        logger.warning(f"gmail list failed: {e}")
        return []

    msg_ids = [m["id"] for m in result.get("messages", [])]
    if not msg_ids:
        return []

    # Fetch each message + parse
    try:
        from app.ingestion.gmail_connector import fetch_message
    except Exception:
        # Fallback: build minimal in-line parser below
        fetch_message = None

    parsed: list[dict] = []
    for mid in msg_ids:
        try:
            if fetch_message:
                m = fetch_message(service, mid)
            else:
                raw = service.users().messages().get(userId="me", id=mid, format="metadata",
                                                      metadataHeaders=["From", "To", "Subject", "Date", "Message-ID"]).execute()
                hd = {h["name"].lower(): h["value"] for h in (raw.get("payload", {}).get("headers") or [])}
                m = {
                    "id": raw.get("id"),
                    "message_id": hd.get("message-id"),
                    "from": hd.get("from"),
                    "to": hd.get("to"),
                    "subject": hd.get("subject"),
                    "date": hd.get("date"),
                    "internal_date_ms": int(raw.get("internalDate") or 0),
                    "snippet": raw.get("snippet"),
                    "thread_id": raw.get("threadId"),
                }
            parsed.append(_normalise(m, account))
        except Exception as e:
            logger.debug(f"gmail fetch_message {mid} failed: {e}")
            continue

    return parsed


def mark_read(credentials: dict, external_id: str) -> bool:
    """Remove UNREAD label so we don't re-fetch on next sync."""
    access = credentials.get("access_token")
    refresh = credentials.get("refresh_token")
    if not access or not refresh or not external_id:
        return False
    try:
        from app.ingestion.gmail_connector import build_gmail_service
        service = build_gmail_service(access, refresh)
        # external_id is the Message-ID header; we need Gmail's internal id.
        # Search for it; fall back to no-op if not found.
        result = service.users().messages().list(
            userId="me", q=f"rfc822msgid:{external_id}", maxResults=1,
        ).execute()
        items = result.get("messages", [])
        if not items:
            return False
        gid = items[0]["id"]
        service.users().messages().modify(
            userId="me", id=gid, body={"removeLabelIds": ["UNREAD"]},
        ).execute()
        return True
    except Exception as e:
        logger.debug(f"gmail mark_read failed: {e}")
        return False


def _register():
    register("gmail", {
        "fetch_email": fetch_emails,
        "mark_read":   mark_read,
    })


_register()
