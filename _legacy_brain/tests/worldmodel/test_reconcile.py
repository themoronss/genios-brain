"""Tests for core.worldmodel.reconcile - trust x recency conflict resolution."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from core.worldmodel.reconcile import Candidate, reconcile


def _now() -> datetime:
    return datetime(2026, 6, 1, tzinfo=UTC)


@pytest.mark.unit
def test_empty_candidates_flagged() -> None:
    r = reconcile([], now=_now())
    assert r.flagged_for_human is True
    assert r.winning_value is None


@pytest.mark.unit
def test_higher_trust_wins_when_recency_same() -> None:
    """CRM (trust 0.9) beats Gmail (trust 0.7) when both asserted same day."""
    candidates = [
        Candidate(value=50_000, source_type="crm", asserted_at=_now() - timedelta(days=1)),
        Candidate(value=80_000, source_type="gmail", asserted_at=_now() - timedelta(days=1)),
    ]
    r = reconcile(candidates, now=_now())
    if not r.flagged_for_human:
        assert r.winning_value == 50_000


@pytest.mark.unit
def test_recent_can_overtake_higher_trust() -> None:
    """Recent Gmail update can win over month-old CRM update via recency decay."""
    candidates = [
        Candidate(value=50_000, source_type="crm", asserted_at=_now() - timedelta(days=180)),
        Candidate(value=80_000, source_type="gmail", asserted_at=_now() - timedelta(days=1)),
    ]
    r = reconcile(candidates, now=_now())
    assert r.winning_value == 80_000


@pytest.mark.unit
def test_close_call_flagged_for_human() -> None:
    """Per MD: if top two within epsilon → flag, don't silently pick."""
    # Same trust + same recency → scores will tie
    candidates = [
        Candidate(value="A", source_type="crm", asserted_at=_now()),
        Candidate(value="B", source_type="crm", asserted_at=_now()),
    ]
    r = reconcile(candidates, now=_now())
    assert r.flagged_for_human is True
    assert r.winning_value is None


@pytest.mark.unit
def test_losing_history_preserved_in_non_flagged() -> None:
    """Non-winning values come back in losing_history for audit."""
    candidates = [
        Candidate(value=50_000, source_type="crm", asserted_at=_now() - timedelta(days=180)),
        Candidate(value=80_000, source_type="gmail", asserted_at=_now() - timedelta(days=1)),
    ]
    r = reconcile(candidates, now=_now())
    assert not r.flagged_for_human
    # Loser preserved
    loser_values = [c.value for c in r.losing_history]
    assert 50_000 in loser_values
