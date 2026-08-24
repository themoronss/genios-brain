"""Layer 5.2 · Phase 4 — Retry Manager policy (pure)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from genios_engine.deliver.retry import (
    BACKOFF_MINUTES,
    AttemptOutcome,
    defer_until,
    is_terminal_failure,
    may_cross_channel_failover,
    next_attempt_at,
)

NOW = datetime(2026, 8, 8, 12, 0, tzinfo=timezone.utc)


def test_backoff_climbs_then_goes_terminal():
    delays = [next_attempt_at(failed_attempts=i, now=NOW) for i in range(len(BACKOFF_MINUTES))]
    assert delays == [NOW + timedelta(minutes=m) for m in BACKOFF_MINUTES]
    assert next_attempt_at(failed_attempts=len(BACKOFF_MINUTES), now=NOW) is None
    assert is_terminal_failure(failed_attempts=len(BACKOFF_MINUTES))


def test_retry_after_can_push_out_but_not_pull_in():
    # a large Retry-After overrides the small base delay
    pushed = next_attempt_at(failed_attempts=0, now=NOW, retry_after_seconds=3600)
    assert pushed == NOW + timedelta(seconds=3600)
    # a tiny Retry-After never shortens the ladder's own backoff
    kept = next_attempt_at(failed_attempts=1, now=NOW, retry_after_seconds=1)
    assert kept == NOW + timedelta(minutes=BACKOFF_MINUTES[1])


def test_retry_after_cannot_resurrect_an_exhausted_ladder():
    assert next_attempt_at(failed_attempts=len(BACKOFF_MINUTES), now=NOW,
                           retry_after_seconds=10) is None


def test_deferral_moves_the_clock_only():
    assert defer_until(base=NOW, hold_seconds=3600) == NOW + timedelta(hours=1)
    assert defer_until(base=NOW, hold_seconds=-5) == NOW              # never goes backwards


def test_only_a_definite_failure_may_cross_channel():
    assert may_cross_channel_failover(AttemptOutcome.FAILED) is True
    for ambiguous in (AttemptOutcome.UNKNOWN, AttemptOutcome.DEFERRED,
                      AttemptOutcome.STARTED, AttemptOutcome.DELIVERED):
        assert may_cross_channel_failover(ambiguous) is False
