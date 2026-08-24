"""Slack channel — urgent interrupts via DM.

Per Group 3 lock: single org-installed Slack app + customer OAuth per workspace.
Real Slack SDK call lives behind `_slack_post()` which is fake-able for tests.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from core.delivery.channels.base import (
    ChannelAdapter,
    DeliveryAttempt,
    DeliveryError,
    DeliveryStatus,
)
from core.delivery.envelope import Envelope
from core.foundations.telemetry import get_logger

log = get_logger(__name__)

SlackPoster = Callable[[str, dict[str, Any]], dict[str, Any]]
"""Signature: (slack_user_id, message_payload) -> Slack API response dict.

In tests/dev we inject a fake. In prod the wired implementation calls slack-sdk's
WebClient.chat_postMessage. We never inline the SDK call here — adapters stay
swappable + testable without API keys.
"""


class SlackChannel(ChannelAdapter):
    """Sends envelopes as Slack DMs with a compact human-readable summary."""

    name = "slack"

    def __init__(
        self,
        *,
        poster: SlackPoster,
        user_id_to_slack_id: Callable[[str], str | None],
    ) -> None:
        self._post = poster
        self._lookup_slack_id = user_id_to_slack_id

    def send(self, *, envelope: Envelope, user_id: str, is_digest: bool) -> DeliveryAttempt:
        sent_at = datetime.now(UTC)
        slack_id = self._lookup_slack_id(user_id)
        if slack_id is None:
            log.info("slack_no_mapping", user_id=user_id, org_id=envelope.org_id)
            return DeliveryAttempt(
                channel=self.name,
                user_id=user_id,
                org_id=envelope.org_id,
                envelope_decision_id=envelope.decision_id,
                status=DeliveryStatus.SUPPRESSED,
                sent_at=sent_at,
                error="no slack_user_id mapping",
            )

        message = _format_envelope_for_slack(envelope, is_digest=is_digest)

        try:
            self._post(slack_id, message)
        except Exception as e:
            log.error(
                "slack_send_failed",
                user_id=user_id,
                org_id=envelope.org_id,
                error=str(e)[:200],
            )
            raise DeliveryError(f"Slack send failed: {e}") from e

        return DeliveryAttempt(
            channel=self.name,
            user_id=user_id,
            org_id=envelope.org_id,
            envelope_decision_id=envelope.decision_id,
            status=DeliveryStatus.SENT,
            sent_at=sent_at,
        )


# ─── helpers ────────────────────────────────────────────────────────────────


def _format_envelope_for_slack(envelope: Envelope, *, is_digest: bool) -> dict[str, Any]:
    """Build a compact Slack message. Keeps the envelope contract visible
    (confidence + route + uncertainty count) without dumping the full proof."""
    rec = envelope.recommendation
    headline = rec.get("title") or rec.get("conclusion") or "Intelligence update"
    blocks: list[dict[str, Any]] = [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*{headline}*\n"
                f"_confidence {envelope.confidence.value} · route `{envelope.route.value}`_",
            },
        }
    ]
    if rec.get("recommend"):
        blocks.append(
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"Recommendation: {rec['recommend']}"},
            }
        )
    if envelope.uncertainty:
        blocks.append(
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": f"⚠ {len(envelope.uncertainty)} uncertainty flag(s) — open in app",
                    }
                ],
            }
        )
    blocks.append(
        {
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "👍 Act"},
                    "value": f"act:{envelope.decision_id}",
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "👎 Wrong"},
                    "value": f"down:{envelope.decision_id}",
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Snooze"},
                    "value": f"snooze:{envelope.decision_id}",
                },
            ],
        }
    )
    return {"blocks": blocks, "text": headline, "is_digest": is_digest}
