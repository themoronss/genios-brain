"""The agent webhook as a CHANNEL adapter — so an agent delivery is an outbox row, not an
inline POST from the card build.

`deliver/push.py` did its HTTP synchronously inside `build_cards_for_org`, which is the exact
anti-pattern the outbox module's own docstring names as its reason to exist: one slow client
endpoint degrades the card build for the whole org, and the send appears in no outbox, no retry
schedule, no dead letter, and no analytics. Routing it here gives an agent push the same
lifecycle every human delivery already has — claimed, retried on the bounded backoff ladder,
terminal with a recorded reason — and the drain's authority recheck replaces push.py's
hand-rolled pre-send projection comparison.

Same wire format as before: HMAC-SHA256 over the exact body, mirrored by
`platform/auth.verify_webhook_hmac`, so no client changes.
"""
from __future__ import annotations

import hashlib
import hmac
import json

from genios_engine.platform.logging import get_logger

_TIMEOUT_S = 4.0
_log = get_logger("genios.deliver.channels.agent")


class AgentWebhookChannel:
    """POST one payload to one agent's webhook. cfg = one agent_registry row."""

    name = "agent_push"

    def send(self, payload: dict, cfg: dict) -> bool:
        try:
            import httpx
        except Exception:      # pragma: no cover — httpx ships transitively
            _log.warning("httpx unavailable; agent delivery skipped")
            return False
        url = (cfg or {}).get("webhook_url")
        if not url:
            return False
        body = json.dumps(payload, default=str).encode()
        secret = str((cfg or {}).get("webhook_secret") or "")
        sig = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
        try:
            resp = httpx.post(url, content=body, timeout=_TIMEOUT_S, headers={
                "Content-Type": "application/json",
                "X-Genios-Signature": f"sha256={sig}",
                "X-Genios-Event": str(payload.get("type") or "signal.created"),
                "X-Genios-Agent-Id": str((cfg or {}).get("agent_id") or ""),
            })
            return 200 <= resp.status_code < 300
        except Exception as e:      # noqa: BLE001 — a failed send is a retry, never a crash
            _log.warning("agent delivery failed url=%s: %s", url, e)
            return False


__all__ = ["AgentWebhookChannel"]
