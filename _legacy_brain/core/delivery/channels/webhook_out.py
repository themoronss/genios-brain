"""Generic outbound webhook channel — for agents that subscribe to push insights.

Used by MCP push + customer-configured webhook integrations. The full envelope
is sent as the JSON body so receivers get all moat context (derivation +
uncertainty + asOf).

HMAC-SHA256 signature added (per g-i-1 webhook security symmetry) so the
receiver can verify the call originated from GeniOS.
"""

from __future__ import annotations

import hashlib
import hmac
import json
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


WebhookPoster = Callable[[str, dict[str, str], bytes], int]
"""Signature: (url, headers, body_bytes) -> http_status. Fake-able in tests."""


class WebhookChannel(ChannelAdapter):
    """Sends envelopes as signed JSON HTTP POST to a customer-configured URL."""

    name = "webhook"

    def __init__(
        self,
        *,
        poster: WebhookPoster,
        user_id_to_webhook: Callable[[str], tuple[str, str] | None],
    ) -> None:
        """
        Args:
            poster: callable that POSTs and returns HTTP status. Inject httpx in prod.
            user_id_to_webhook: maps user_id -> (webhook_url, hmac_secret), or None if not configured.
        """
        self._post = poster
        self._lookup = user_id_to_webhook

    def send(self, *, envelope: Envelope, user_id: str, is_digest: bool) -> DeliveryAttempt:
        sent_at = datetime.now(UTC)
        target = self._lookup(user_id)
        if target is None:
            return DeliveryAttempt(
                channel=self.name,
                user_id=user_id,
                org_id=envelope.org_id,
                envelope_decision_id=envelope.decision_id,
                status=DeliveryStatus.SUPPRESSED,
                sent_at=sent_at,
                error="no webhook configured",
            )

        url, secret = target
        body_bytes = json.dumps(envelope.model_dump(mode="json"), default=str).encode("utf-8")
        signature = hmac.new(secret.encode("utf-8"), body_bytes, hashlib.sha256).hexdigest()
        headers = {
            "Content-Type": "application/json",
            "X-Genios-Signature": f"sha256={signature}",
            "X-Genios-Decision-Id": envelope.decision_id,
            "X-Genios-Is-Digest": "true" if is_digest else "false",
        }

        try:
            status = self._post(url, headers, body_bytes)
        except Exception as e:
            log.error("webhook_send_failed", user_id=user_id, error=str(e)[:200])
            raise DeliveryError(f"Webhook POST failed: {e}") from e

        if not 200 <= status < 300:
            log.warning("webhook_non_2xx", user_id=user_id, status=status)
            return DeliveryAttempt(
                channel=self.name,
                user_id=user_id,
                org_id=envelope.org_id,
                envelope_decision_id=envelope.decision_id,
                status=DeliveryStatus.FAILED,
                sent_at=sent_at,
                error=f"HTTP {status}",
            )

        return DeliveryAttempt(
            channel=self.name,
            user_id=user_id,
            org_id=envelope.org_id,
            envelope_decision_id=envelope.decision_id,
            status=DeliveryStatus.SENT,
            sent_at=sent_at,
        )


def verify_webhook_signature(*, body: bytes, signature_header: str, secret: str) -> bool:
    """Receiver-side helper. Returns True if signature matches."""
    expected = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    provided = signature_header.removeprefix("sha256=")
    return hmac.compare_digest(expected, provided)


# Used internally
_ = Any
