"""Inbound webhook handling: verify signature, parse payload, route to adapter.

Hard rule (g-i-1 §1.1.2): forged / unsigned payloads MUST be rejected.

Flow:
1. HTTP route receives webhook POST
2. Look up connection by source-issued webhook_id
3. Adapter's verifier checks the provider's signature scheme (HMAC, etc.)
4. Adapter parses payload into RecordRef[] (no full content yet)
5. Each ref is fetched via adapter.fetch_record (in-flight only)
6. Pipeline: scope-gate → normalize → emit (handled by caller)
"""

from __future__ import annotations

import hashlib
import hmac
from abc import ABC, abstractmethod
from collections.abc import Mapping

from core.foundations import audit
from core.foundations.telemetry import get_logger

log = get_logger(__name__)


class WebhookVerificationError(Exception):
    """Signature mismatch / replay / unsigned payload — reject."""


class WebhookVerifier(ABC):
    """Adapters implement their provider's signature scheme."""

    @abstractmethod
    def verify(self, *, body: bytes, headers: Mapping[str, str], secret: str) -> None:
        """Raise WebhookVerificationError on failure. Return None on success."""


class HmacSha256Verifier(WebhookVerifier):
    """Common scheme: HMAC-SHA256 of body, hex-encoded, compared to a header.

    Works for: Slack, GitHub, Stripe (variant), Notion, many internal webhooks.
    Configure header_name + optional prefix (e.g. 'sha256=').
    """

    def __init__(self, header_name: str, prefix: str = "") -> None:
        self._header_name = header_name
        self._prefix = prefix

    def verify(self, *, body: bytes, headers: Mapping[str, str], secret: str) -> None:
        signature_header = headers.get(self._header_name) or headers.get(self._header_name.lower())
        if not signature_header:
            raise WebhookVerificationError(f"Missing signature header: {self._header_name}")

        expected = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
        provided = signature_header[len(self._prefix) :] if self._prefix else signature_header

        # constant-time compare to prevent timing attacks
        if not hmac.compare_digest(expected, provided):
            raise WebhookVerificationError("Signature mismatch")


def receive(
    *,
    verifier: WebhookVerifier,
    secret: str,
    body: bytes,
    headers: Mapping[str, str],
    connection_id: str,
    org_id: str,
) -> bool:
    """Verify an inbound webhook. Returns True on accept, False on reject.

    All rejects are audit-logged (forged-payload visibility for security review).
    """
    try:
        verifier.verify(body=body, headers=headers, secret=secret)
    except WebhookVerificationError as e:
        log.warning(
            "webhook_rejected",
            connection_id=connection_id,
            org_id=org_id,
            reason=str(e),
        )
        audit.record(
            org_id=org_id,
            actor_type="system",
            actor_id="webhook_receiver",
            action="data_accessed",
            target_type="webhook",
            target_id=connection_id,
            metadata={"outcome": "rejected", "reason": str(e), "body_bytes": len(body)},
        )
        return False

    audit.record(
        org_id=org_id,
        actor_type="system",
        actor_id="webhook_receiver",
        action="data_accessed",
        target_type="webhook",
        target_id=connection_id,
        metadata={"outcome": "accepted", "body_bytes": len(body)},
    )
    return True
