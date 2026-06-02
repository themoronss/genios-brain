"""ChannelAdapter protocol — every channel implements this."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from core.delivery.envelope import Envelope


class DeliveryStatus(StrEnum):
    SENT = "sent"
    FAILED = "failed"
    SUPPRESSED = "suppressed"  # e.g. user opted out


class DeliveryError(Exception):
    """Channel failed to deliver. Caller logs + retries per channel policy."""


@dataclass(frozen=True)
class DeliveryAttempt:
    """Result of one send() call. Caller persists to channel_deliveries audit table."""

    channel: str
    user_id: str
    org_id: str
    envelope_decision_id: str
    status: DeliveryStatus
    sent_at: datetime
    error: str | None = None


class ChannelAdapter(ABC):
    """One concrete channel (Slack, email, webhook out, etc.)."""

    name: str  # 'slack' | 'email' | 'webhook' | ...

    @abstractmethod
    def send(
        self,
        *,
        envelope: Envelope,
        user_id: str,
        is_digest: bool,
    ) -> DeliveryAttempt:
        """Deliver an envelope to a user. is_digest=True means batch-style (email).

        Raises DeliveryError on transport failures. Suppression (user opt-out) is
        not an error — returns DeliveryAttempt(status=SUPPRESSED).
        """
