"""Microsoft Teams webhook/Workflow adapter with grounded Adaptive Card payloads."""
from __future__ import annotations

from urllib.parse import urlparse

from genios_engine.deliver.channels.base import ChannelResult


def _host_is(host: str, suffix: str) -> bool:
    return host == suffix or host.endswith(f".{suffix}")


def valid_teams_webhook_url(url: str | None) -> bool:
    if not url:
        return False
    parsed = urlparse(str(url))
    host = (parsed.hostname or "").lower()
    return (parsed.scheme == "https" and bool(host) and not parsed.username and not parsed.password
            and (_host_is(host, "webhook.office.com")
                 or _host_is(host, "logic.azure.com")
                 or _host_is(host, "environment.api.powerplatform.com")
                 or _host_is(host, "powerautomate.com")))


def _text(payload: dict) -> str:
    if payload.get("text"):
        return str(payload["text"])[:4000]
    head = str(payload.get("headline") or payload.get("kind") or "GeniOS")
    situation = str(payload.get("situation") or "")
    return (head + (f"\n{situation}" if situation else ""))[:4000]


def format_teams_payload(payload: dict) -> dict:
    """The schema accepted by both Teams Incoming Webhooks and Workflow triggers."""
    return {
        "type": "message",
        "attachments": [{
            "contentType": "application/vnd.microsoft.card.adaptive",
            "content": {
                "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
                "type": "AdaptiveCard",
                "version": "1.2",
                "body": [{"type": "TextBlock", "text": _text(payload), "wrap": True}],
            },
        }],
    }


class TeamsWebhookChannel:
    name = "teams"

    def send(self, payload: dict, config: dict) -> ChannelResult:
        url = (config or {}).get("webhook_url")
        if not valid_teams_webhook_url(url):
            return ChannelResult(ok=False, detail="invalid or missing Teams webhook_url")
        try:
            import httpx
            response = httpx.post(str(url), json=format_teams_payload(payload), timeout=10.0)
            if 200 <= response.status_code < 300:
                return ChannelResult(ok=True)
            return ChannelResult(ok=False,
                                 detail=f"teams http {response.status_code}: {response.text[:120]}")
        except Exception as exc:  # noqa: BLE001 — the outbox owns retry policy
            return ChannelResult(ok=False, detail=f"{type(exc).__name__}: {str(exc)[:160]}")


__all__ = ["TeamsWebhookChannel", "format_teams_payload", "valid_teams_webhook_url"]
