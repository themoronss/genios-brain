"""Minimal Inkbox HTTP client used by workspace_integrations.

Replaces the deleted v1 module. Only the functions actually called from
workspace_integrations.py are implemented. All calls are best-effort: if
Inkbox is down or the API key lacks scope, the helpers return safe defaults
and the dashboard falls back to scheduled polling.

Env:
  INKBOX_API_BASE — defaults to https://api.inkbox.com (override for dev)
"""

from __future__ import annotations

import logging
import os
import secrets
from typing import Any

import requests

log = logging.getLogger(__name__)
_BASE = os.getenv("INKBOX_API_BASE", "https://api.inkbox.com").rstrip("/")
_TIMEOUT = 8.0


def _headers(api_key: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}


def bootstrap_signing_key(api_key: str) -> str | None:
    """Ask Inkbox to mint a webhook signing key for this account.
    Falls back to a locally-generated key if the endpoint is unreachable —
    the local key is still useful for HMAC verification against later events
    once it's registered with Inkbox out-of-band."""
    try:
        r = requests.post(
            f"{_BASE}/v1/webhooks/signing_keys",
            headers=_headers(api_key), timeout=_TIMEOUT,
        )
        if r.ok:
            data = r.json() or {}
            return data.get("signing_key") or data.get("secret")
    except Exception as e:
        log.warning(f"inkbox.bootstrap_signing_key remote call failed: {e}")
    # Fall back to a locally-minted key so the connector still has something to verify against.
    return secrets.token_urlsafe(32)


def register_mail_webhook(api_key: str, mailbox_address: str, webhook_url: str) -> bool:
    try:
        r = requests.post(
            f"{_BASE}/v1/mailboxes/{mailbox_address}/webhook",
            headers=_headers(api_key),
            json={"url": webhook_url, "events": ["message.received"]},
            timeout=_TIMEOUT,
        )
        return r.ok
    except Exception as e:
        log.warning(f"inkbox.register_mail_webhook failed for {mailbox_address}: {e}")
        return False


def deregister_mail_webhook(api_key: str, mailbox_address: str) -> bool:
    try:
        r = requests.delete(
            f"{_BASE}/v1/mailboxes/{mailbox_address}/webhook",
            headers=_headers(api_key), timeout=_TIMEOUT,
        )
        return r.ok
    except Exception as e:
        log.warning(f"inkbox.deregister_mail_webhook failed for {mailbox_address}: {e}")
        return False


def register_phone_webhook(api_key: str, phone_number_id: str, webhook_url: str,
                            events: list[str] | None = None) -> bool:
    try:
        r = requests.post(
            f"{_BASE}/v1/phone_numbers/{phone_number_id}/webhook",
            headers=_headers(api_key),
            json={"url": webhook_url,
                  "events": events or ["text.received", "phone.incoming_call"]},
            timeout=_TIMEOUT,
        )
        return r.ok
    except Exception as e:
        log.warning(f"inkbox.register_phone_webhook failed for {phone_number_id}: {e}")
        return False


def deregister_phone_webhook(api_key: str, phone_number_id: str) -> bool:
    try:
        r = requests.delete(
            f"{_BASE}/v1/phone_numbers/{phone_number_id}/webhook",
            headers=_headers(api_key), timeout=_TIMEOUT,
        )
        return r.ok
    except Exception as e:
        log.warning(f"inkbox.deregister_phone_webhook failed for {phone_number_id}: {e}")
        return False


def list_phone_numbers(creds: dict[str, Any]) -> list[dict[str, Any]]:
    """Return [{phone_number_id, e164, ...}, ...] for the given credentials."""
    api_key = creds.get("api_key")
    if not api_key:
        return []
    try:
        r = requests.get(
            f"{_BASE}/v1/phone_numbers",
            headers=_headers(api_key), timeout=_TIMEOUT,
        )
        if not r.ok:
            return []
        data = r.json() or {}
        return data.get("phone_numbers") or data.get("data") or []
    except Exception as e:
        log.warning(f"inkbox.list_phone_numbers failed: {e}")
        return []
