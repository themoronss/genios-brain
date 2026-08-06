"""Slack via incoming webhook — the first human channel, deliberately the simplest
thing that is real: the tenant pastes a webhook URL from Slack (no OAuth, no bot
install, no scopes conversation) and high/critical cards start arriving where they
already work.

Formatting is PURE (card fields in, message dict out) and invents nothing: every word
in the message comes from card columns that already passed the render validators.
The card link points back to the dashboard — Slack is the doorbell, not the house."""
from __future__ import annotations

from genios_engine.deliver.channels.base import ChannelResult

_BAND_ICON = {"critical": "🔴", "high": "🟠", "standard": "🔵"}


def format_card_message(card: dict, *, base_url: str = "") -> dict:
    """Pure: a card row (headline/situation/urgency_band/score/card_id) → Slack payload.
    Headline+situation already passed V-01/V-02 at render time — nothing new is said."""
    icon = _BAND_ICON.get(str(card.get("urgency_band") or "standard"), "🔵")
    head = str(card.get("headline") or "")[:150]
    situation = str(card.get("situation") or "")[:300]
    link = f"{base_url.rstrip('/')}/cards/{card.get('card_id')}" if base_url else None
    lines = [f"{icon} *{head}*", situation]
    if link:
        lines.append(f"<{link}|Open the card →>")
    return {"text": f"{icon} {head}",                       # notification fallback text
            "blocks": [{"type": "section",
                        "text": {"type": "mrkdwn", "text": "\n".join(lines)}}]}


def format_digest_message(digest: dict) -> dict:
    """Pure: the morning digest dict → one Slack message. Counted numbers only."""
    one_line = str(digest.get("one_line") or "Nothing needs you right now.")
    items = digest.get("top_items") or digest.get("items") or []
    lines = [f"☀️ *Morning brief* — {one_line}"]
    for it in items[:5]:
        entity = it.get("entity") or "—"
        reason = str(it.get("reason") or it.get("reason_code") or "").replace("_", " ")
        score = it.get("score")
        lines.append(f"• {entity}: {reason}" + (f" (S {score})" if score is not None else ""))
    return {"text": lines[0],
            "blocks": [{"type": "section",
                        "text": {"type": "mrkdwn", "text": "\n".join(lines)}}]}


def valid_webhook_url(url: str | None) -> bool:
    return bool(url) and str(url).startswith("https://hooks.slack.com/")


class SlackWebhookChannel:
    name = "slack"

    def send(self, payload: dict, config: dict) -> ChannelResult:
        url = (config or {}).get("webhook_url")
        if not valid_webhook_url(url):
            return ChannelResult(ok=False, detail="invalid or missing slack webhook_url")
        try:
            import httpx
            r = httpx.post(url, json=payload, timeout=10.0)
            if r.status_code == 200:
                return ChannelResult(ok=True)
            return ChannelResult(ok=False, detail=f"slack http {r.status_code}: {r.text[:120]}")
        except Exception as e:      # noqa: BLE001 — failure is a result; the outbox owns retry
            return ChannelResult(ok=False, detail=f"{type(e).__name__}: {str(e)[:160]}")
