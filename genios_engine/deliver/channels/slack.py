"""Slack via incoming webhook — the first human channel, deliberately the simplest
thing that is real: the tenant pastes a webhook URL from Slack (no OAuth, no bot
install, no scopes conversation) and high/critical cards start arriving where they
already work.

Formatting is PURE (card fields in, message dict out) and invents nothing: every word
in the message comes from card columns that already passed the render validators.
The card link points back to the dashboard — Slack is the doorbell, not the house."""
from __future__ import annotations

from genios_engine.contracts.abstention import is_actionable
from genios_engine.deliver.channels.base import ChannelResult

_BAND_ICON = {"critical": "🔴", "high": "🟠", "standard": "🔵"}


def format_card_message(card: dict, *, base_url: str = "") -> dict:
    """Pure: a card row (headline/situation/urgency_band/score/card_id) → Slack payload.
    Headline+situation already passed V-01/V-02 at render time — nothing new is said.

    THE ABSTENTION USED TO VANISH HERE. `contracts/abstention` says an abstention with no stated
    cause is indistinguishable from an opinion, and `cards.abstained_because` exists to carry
    that cause. This function rendered headline and situation only, so on the surface a founder
    actually gets pinged on, the reason a card declined to advise was simply absent — and now
    that ASK_DECISION interrupts, a card whose whole content is a question would have arrived
    looking like an instruction.

    Both fields are ADDED, never substituted. The headline already carries its frame from
    `render.state_not_command`; this says why underneath it, in the counterparty's absence of
    evidence rather than in a label.
    """
    icon = _BAND_ICON.get(str(card.get("urgency_band") or "standard"), "🔵")
    head = str(card.get("headline") or "")[:150]
    situation = str(card.get("situation") or "")[:300]
    link = f"{base_url.rstrip('/')}/cards/{card.get('card_id')}" if base_url else None
    lines = [f"{icon} *{head}*", situation]
    because = str(card.get("abstained_because") or "").strip()
    if because and not is_actionable(card.get("level")):
        # Italic and last-but-one: it is context for the sentence above, not a second headline.
        lines.append(f"_{because[:200]}_")
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


_URGENCY_ICON = {"urgent": "🔴", "firm": "🟠", "gentle": "🔵"}


def format_reminder_message(payload: dict, *, base_url: str = "") -> dict:
    """Pure: a Layer 5 commitment reminder → Slack payload.

    Every value here was put in the payload by ``deliver/executive_bridge.format_reminder``,
    which in turn only copies the grounded fact corpus Layer 5 attached to the reminder event.
    The adapter adds punctuation and an icon and nothing else — same law as the card path.

    The consequence line is what makes this a reminder rather than a nag: "the Acme deal slips
    past quarter end" is a reason to act; "this is still open" is an accusation.
    """
    icon = _URGENCY_ICON.get(str(payload.get("urgency") or "gentle"), "🔵")
    head = str(payload.get("headline") or "")[:150]
    # AN ESCALATION SAYS SO, and this prefixed all four rungs of the ladder with "Still open —".
    # `executive_bridge` parses the rung out of Layer 5's reason code and sets `kind` and
    # `escalation_action` for exactly this — and had ZERO consumers, so the rung that widens the
    # audience and interrupts reached a human looking like the first gentle nudge. The bridge
    # already frames the HEADLINE for the two rungs that escalate; this stops overwriting it.
    escalating = str(payload.get("kind") or "") == "execution_escalation"
    lines = [f"{icon} *{head}*" if escalating else f"{icon} *Still open — {head}*"]
    situation = str(payload.get("situation") or "")
    if situation:
        lines.append(situation)
    consequence = str(payload.get("consequence") or "")
    if consequence:
        lines.append(f"_{consequence[:300]}_")
    next_action = str(payload.get("next_action") or "")
    if next_action:
        lines.append(f"Next: {next_action[:200]}")
    card_id = payload.get("card_id")
    if base_url and card_id:
        lines.append(f"<{base_url.rstrip('/')}/cards/{card_id}|Open the card →>")
    return {"text": (f"{icon} {head}" if escalating else f"{icon} Still open — {head}"),
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
