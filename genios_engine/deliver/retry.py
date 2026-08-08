"""Layer 5.2 · Phase 4 — the Retry Manager (section 5.3) and failure classification.

Pure policy. Provider *failures* climb a bounded backoff ladder and then go terminal — a channel
that never works must eventually stop being tried. Deferrals (quiet hours, meetings, quota) are
NOT failures and never spend a retry. Ambiguous outcomes (timeout, 5xx, lost ACK) must never
trigger an automatic cross-channel retry, because the first provider may already have accepted.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from enum import Enum

#: Bounded backoff in minutes; the ladder length is the attempt budget. After the last rung, the
#: next failure is terminal — four strikes, not infinite hope.
BACKOFF_MINUTES: tuple[int, ...] = (5, 30, 120, 720)


class AttemptOutcome(str, Enum):
    """How one provider call ended — the classification the recovery path branches on."""

    DELIVERED = "delivered"          # definite success
    FAILED = "failed"                # definite non-delivery — safe to advance the route / retry
    DEFERRED = "deferred"            # not a failure: quiet hours / meeting / quota
    UNKNOWN = "unknown"              # ambiguous: timeout / 5xx / lost ACK — DO NOT auto-retry
    STARTED = "started"              # in flight; a crash here becomes UNKNOWN on claim expiry


def is_terminal_failure(*, failed_attempts: int) -> bool:
    """A definite failure is terminal once the backoff ladder is spent."""
    return failed_attempts >= len(BACKOFF_MINUTES)


def next_attempt_at(*, failed_attempts: int, now: datetime,
                    retry_after_seconds: int | None = None) -> datetime | None:
    """When the next provider attempt may run after a DEFINITE failure, or None if terminal.

    ``failed_attempts`` counts prior definite failures (transport strikes), NOT deferrals. A
    provider ``Retry-After`` may push the delay out (never pull it in below the ladder), but it
    cannot resurrect an exhausted ladder — once terminal, terminal.
    """
    if is_terminal_failure(failed_attempts=failed_attempts):
        return None
    base_minutes = BACKOFF_MINUTES[failed_attempts]
    delay = timedelta(minutes=base_minutes)
    if retry_after_seconds is not None and retry_after_seconds > 0:
        delay = max(delay, timedelta(seconds=retry_after_seconds))
    return now + delay


def defer_until(*, base: datetime, hold_seconds: int) -> datetime:
    """A deferral moves the clock and nothing else — it does not touch the failure ladder."""
    return base + timedelta(seconds=max(0, hold_seconds))


def may_cross_channel_failover(outcome: AttemptOutcome) -> bool:
    """Only a DEFINITE non-delivery may advance to the next route rung.

    An UNKNOWN outcome must not fail over: the first provider may already have delivered, and a
    second channel would then be a duplicate human interruption. Ambiguity stops for reconciliation.
    """
    return outcome is AttemptOutcome.FAILED


__all__ = ["BACKOFF_MINUTES", "AttemptOutcome", "defer_until", "is_terminal_failure",
           "may_cross_channel_failover", "next_attempt_at"]
