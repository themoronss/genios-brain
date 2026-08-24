"""Email channel — non-urgent digests via AWS SES.

Per Group 3 lock: SES (cheapest, acceptable AWS lock). Real boto3 call lives
behind `_send_email()` for fake-ability in tests.

Email is the DIGEST channel — urgent goes to Slack; this is the batch-style sender.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from core.delivery.channels.base import (
    ChannelAdapter,
    DeliveryAttempt,
    DeliveryError,
    DeliveryStatus,
)
from core.delivery.envelope import Envelope
from core.foundations.config import EMAIL_RATE_PER_USER_PER_MIN
from core.foundations.telemetry import get_logger

log = get_logger(__name__)


@dataclass(frozen=True)
class EmailMessage:
    """Shape passed to the real-or-fake email sender."""

    to_email: str
    subject: str
    text_body: str
    html_body: str | None = None


EmailSender = Callable[[EmailMessage], dict[str, Any]]
"""Sends an EmailMessage; returns provider response. Fake-able in tests."""


class EmailChannel(ChannelAdapter):
    """Sends envelopes (single or digest) via email."""

    name = "email"

    def __init__(
        self,
        *,
        sender: EmailSender,
        user_id_to_email: Callable[[str], str | None],
        rate_per_min: int = EMAIL_RATE_PER_USER_PER_MIN,
    ) -> None:
        self._send = sender
        self._lookup_email = user_id_to_email
        self._rate_per_min = rate_per_min
        # In-memory rate window per (user, minute). Replace with Redis when distributed.
        self._sent_this_minute: dict[tuple[str, str], int] = {}

    def send(self, *, envelope: Envelope, user_id: str, is_digest: bool) -> DeliveryAttempt:
        sent_at = datetime.now(UTC)
        to = self._lookup_email(user_id)
        if to is None:
            return DeliveryAttempt(
                channel=self.name,
                user_id=user_id,
                org_id=envelope.org_id,
                envelope_decision_id=envelope.decision_id,
                status=DeliveryStatus.SUPPRESSED,
                sent_at=sent_at,
                error="no email mapping",
            )

        if self._rate_limited(user_id, sent_at):
            return DeliveryAttempt(
                channel=self.name,
                user_id=user_id,
                org_id=envelope.org_id,
                envelope_decision_id=envelope.decision_id,
                status=DeliveryStatus.SUPPRESSED,
                sent_at=sent_at,
                error="email rate limit",
            )

        msg = _format_envelope_email(envelope, to=to, is_digest=is_digest)
        try:
            self._send(msg)
        except Exception as e:
            log.error("email_send_failed", user_id=user_id, error=str(e)[:200])
            raise DeliveryError(f"Email send failed: {e}") from e

        self._record_send(user_id, sent_at)
        return DeliveryAttempt(
            channel=self.name,
            user_id=user_id,
            org_id=envelope.org_id,
            envelope_decision_id=envelope.decision_id,
            status=DeliveryStatus.SENT,
            sent_at=sent_at,
        )

    # ── rate limiting ─────────────────────────────────────────────────────

    def _rate_limited(self, user_id: str, now: datetime) -> bool:
        bucket = (user_id, now.strftime("%Y%m%d%H%M"))
        return self._sent_this_minute.get(bucket, 0) >= self._rate_per_min

    def _record_send(self, user_id: str, now: datetime) -> None:
        bucket = (user_id, now.strftime("%Y%m%d%H%M"))
        self._sent_this_minute[bucket] = self._sent_this_minute.get(bucket, 0) + 1


def _format_envelope_email(envelope: Envelope, *, to: str, is_digest: bool) -> EmailMessage:
    rec = envelope.recommendation
    headline = rec.get("title") or rec.get("conclusion") or "GeniOS Intelligence Update"
    subject = f"[GeniOS] {headline}" if not is_digest else f"[GeniOS Digest] {headline}"
    body_lines = [
        headline,
        "",
        f"Confidence: {envelope.confidence.value}",
        f"Route: {envelope.route.value}",
        "",
    ]
    if rec.get("recommend"):
        body_lines.append(f"Recommendation: {rec['recommend']}")
        body_lines.append("")
    if envelope.uncertainty:
        body_lines.append(f"{len(envelope.uncertainty)} uncertainty flag(s):")
        for u in envelope.uncertainty:
            body_lines.append(f"  - {u.get('detail', u.get('kind', 'unknown'))}")
        body_lines.append("")
    body_lines.append(
        f"Decision id: {envelope.decision_id} (asOf graph v{envelope.as_of.graph_version})"
    )
    return EmailMessage(to_email=to, subject=subject, text_body="\n".join(body_lines))
