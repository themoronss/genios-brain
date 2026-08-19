"""Founder-facing ops alerts — one outbound webhook for events the founder needs to know about
WITHOUT opening the admin dashboard: a totally broken sync, the platform LLM spend cap. Off by
default (empty webhook = no-op, just logs). Uses the same Slack incoming-webhook JSON shape
tenants already send their own cards through (deliver/channels/slack.py) — no new integration
surface, just a second URL pointed at the founder's own workspace instead of a client's."""
from __future__ import annotations

import httpx

from genios_engine.platform.config import get_settings
from genios_engine.platform.logging import get_logger

_log = get_logger("genios.ops_alert")


def notify(event: str, **fields: object) -> None:
    """Best-effort, non-blocking. Never raises — an alert must never break the caller."""
    url = get_settings().ops_alert_webhook
    lines = "\n".join(f"*{k}*: {v}" for k, v in fields.items())
    if not url:
        _log.warning("ops alert (GENIOS_OPS_ALERT_WEBHOOK not set) — %s\n%s", event, lines)
        return
    try:
        httpx.post(url, json={"text": f"⚠️ GeniOS ops — *{event}*\n{lines}"}, timeout=5.0)
    except Exception:      # noqa: BLE001 — an alert failure must never break the caller
        _log.exception("ops alert webhook failed for event=%s", event)
