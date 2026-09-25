"""L3-02 · the coverage read — the numbers existed, the sentence could not be said.

Migration 0178 added cursor_exhausted / page_budget_spent / claimed_total / claimed_is_estimate to
`l1_sync_runs`; `api/routes.py` writes them on every sync; NO SELECT IN THE ENGINE READ THEM BACK.
So "read 37 of about 465" — the one sentence that separates this product from an assistant with a
context window — could not be produced by anything, however carefully it had been measured.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import pytest

from genios_engine.capture.coverage.window import (ABSENCE_CAPABLE, SYNC_HEALTHS, SyncHealth,
                                                   WindowCoverage, coverage_for_window)

T0 = datetime(2026, 9, 1, tzinfo=timezone.utc)
T1 = T0 + timedelta(days=30)


@dataclass
class _Row:
    scanned: int = 0
    claimed_total: int | None = None
    claimed_is_estimate: bool = False
    cursor_exhausted: bool | None = True
    page_budget_spent: bool = False
    error: str | None = None


class _Conn:
    def __init__(self, rows): self._rows = rows
    def execute(self, *_a, **_k): return self
    def fetchall(self): return self._rows


def _cov(*rows) -> WindowCoverage:
    return coverage_for_window(_Conn(list(rows)), org_id="o", source="gmail", since=T0, until=T1)


# =================================================================================================
# 1 · ⛔ THE VOCABULARY IS CLOSED, BOTH WAYS
# =================================================================================================

def test_sync_health_vocabulary_is_total_in_both_directions():
    assert set(SYNC_HEALTHS) == set(SyncHealth), (
        "SYNC_HEALTHS and SyncHealth disagree — a member in one and not the other is a state that "
        "either cannot be produced or cannot be handled")
    assert len(SYNC_HEALTHS) == len(set(SYNC_HEALTHS)), "duplicate member in SYNC_HEALTHS"


def test_only_a_healthy_window_can_support_an_absence_claim():
    """⛔ SUCCESS_EMPTY IS DELIBERATELY NOT ABSENCE-CAPABLE.

    A sweep that found nothing and did not exhaust its cursor has established that IT saw nothing.
    Reading that as "there is none" is the substitution this module exists to prevent, and it is
    the one the 23 Sept benchmark caught in public.
    """
    assert ABSENCE_CAPABLE == {SyncHealth.HEALTHY}
    for h in SYNC_HEALTHS:
        if h is not SyncHealth.HEALTHY:
            assert h not in ABSENCE_CAPABLE, f"{h} must not license an absence claim"


# =================================================================================================
# 2 · ⛔ THE DENOMINATOR
# =================================================================================================

def test_no_denominator_means_no_ratio_not_one_hundred_percent():
    """`None` rather than 10000 is the whole point. A confident 100% over an unmeasured slice is
    exactly what "18 of 18" was."""
    assert _cov(_Row(scanned=37)).completeness_bp is None


def test_the_denominator_is_a_max_not_a_sum():
    """Consecutive sweeps of one source each report the provider's total FOR THE SAME CORPUS.
    Summing them multiplies the mailbox by the number of times we looked at it — and the ratio
    then shrinks every sweep while the mailbox stands still."""
    cov = _cov(_Row(scanned=20, claimed_total=465), _Row(scanned=17, claimed_total=465))
    assert cov.indexed == 37
    assert cov.claimed_total == 465
    assert cov.completeness_bp == 796              # 37/465 in basis points, integer


def test_an_estimate_label_only_ever_widens():
    """One estimate anywhere makes the whole figure an estimate. An estimate stored without its
    label becomes a fact at the first reader."""
    assert _cov(_Row(claimed_total=10), _Row(claimed_total=465, claimed_is_estimate=True)).is_estimate
    assert not _cov(_Row(claimed_total=10), _Row(claimed_total=20)).is_estimate


def test_reading_more_than_claimed_is_legal_and_clamps():
    """Gmail's resultSizeEstimate runs low routinely. A checker that treated the excess as an error
    would fire on a perfectly correct sweep."""
    cov = _cov(_Row(scanned=500, claimed_total=465, claimed_is_estimate=True))
    assert cov.completeness_bp == 10000


def test_a_zero_denominator_is_unknowable_not_complete():
    assert _cov(_Row(scanned=0, claimed_total=0)).completeness_bp is None


# =================================================================================================
# 3 · ⛔ FX-08 · AN OUTAGE AND AN EMPTY MAILBOX ARE NOT THE SAME VALUE
# =================================================================================================

def test_a_failed_sweep_is_not_an_empty_one():
    """The case the specs name FX-08: "a rate limit produces an empty adapter result instead of an
    error". Both land scanned=0. Only `error` separates them, and it had never been read."""
    failed = _cov(_Row(scanned=0, error="429 rate limited"))
    empty = _cov(_Row(scanned=0, claimed_total=0))
    assert failed.health is SyncHealth.FAILED
    assert empty.health is SyncHealth.SUCCESS_EMPTY
    assert not failed.can_support_absence and not empty.can_support_absence


def test_one_failure_poisons_the_window_even_beside_nine_clean_runs():
    """A window containing a failure is not healthy: the failure is exactly where the missing mail
    would be. Order of the health checks is the design, not an accident of writing."""
    rows = [_Row(scanned=10, claimed_total=100) for _ in range(9)] + [_Row(error="boom")]
    assert _cov(*rows).health is SyncHealth.FAILED


def test_an_unfinished_cursor_is_partial_even_when_everything_succeeded():
    assert _cov(_Row(scanned=10, claimed_total=100, cursor_exhausted=False)).health is SyncHealth.PARTIAL


def test_a_run_written_before_0178_cannot_vouch_for_itself():
    """`cursor_exhausted` is NULL on every row written before the migration. Treating silence as
    completion is the fabricated 100% in a different costume."""
    assert _cov(_Row(scanned=10, claimed_total=100, cursor_exhausted=None)).health is SyncHealth.PARTIAL


def test_no_runs_at_all_is_unknown_and_never_complete():
    cov = _cov()
    assert cov.health is SyncHealth.UNKNOWN
    assert cov.completeness_bp is None and not cov.can_support_absence


def test_a_missing_table_is_unknown_rather_than_an_error():
    """A tenant whose migrations have not run has not proven anything about their mailbox."""
    class _Broken:
        def execute(self, *_a, **_k): raise RuntimeError("relation l1_sync_runs does not exist")
    cov = coverage_for_window(_Broken(), org_id="o", source="gmail", since=T0, until=T1)
    assert cov.health is SyncHealth.UNKNOWN


# =================================================================================================
# 4 · ⛔ HEALTH ALONE IS NOT A LICENCE
# =================================================================================================

def test_a_healthy_window_without_a_denominator_still_cannot_claim_absence():
    """It read everything it was OFFERED. That is not everything that EXISTS."""
    cov = _cov(_Row(scanned=37))
    assert cov.cursor_exhausted and cov.health is SyncHealth.HEALTHY
    assert cov.completeness_bp is None
    assert not cov.can_support_absence


def test_healthy_with_a_denominator_is_the_only_combination_that_licenses_it():
    assert _cov(_Row(scanned=37, claimed_total=465)).can_support_absence


# =================================================================================================
# 5 · THE SENTENCE
# =================================================================================================

@pytest.mark.parametrize("rows,expected", [
    ((_Row(scanned=37, claimed_total=465, claimed_is_estimate=True),),
     "read 37 of about 465 from gmail"),
    ((_Row(scanned=37, claimed_total=465),), "read 37 of 465 from gmail"),
    ((_Row(scanned=37),), "read 37 from gmail; the provider gave no total"),
    ((), "no gmail sync covers this window"),
    ((_Row(error="boom"),), "gmail sync failed in this window — coverage unknown"),
])
def test_the_sentence_never_hides_a_missing_denominator(rows, expected):
    """A missing denominator that reads as a complete answer is the failure being prevented, so the
    unknown cases say so in words rather than omitting the clause."""
    assert _cov(*rows).describe() == expected


def test_an_incomplete_window_says_so_in_the_sentence():
    assert "(incomplete — a tail was never read)" in _cov(
        _Row(scanned=37, claimed_total=465, cursor_exhausted=False)).describe()
