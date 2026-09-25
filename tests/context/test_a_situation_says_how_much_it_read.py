"""L3-02b · a situation that rests on a partly-read window must say so.

`unmet_source_families` answers "which system of record is not connected at all" — 18 pilot
situations were held on exactly that and 0 of 18 named the family. THE QUANTITATIVE VERSION IS
WORSE, because it does not hold anything: a sweep that read 8% of a mailbox and exhausted nothing
produces situations that look exactly like a sweep that read all of it. On 23 Sept one assistant
read about 18 threads of roughly 465 and reported "18 of 18".
"""
from __future__ import annotations

import inspect
from datetime import datetime, timedelta, timezone

from genios_engine.context.situations import window_coverage_gaps

T0 = datetime(2026, 9, 1, tzinfo=timezone.utc)
NOW = T0 + timedelta(days=30)


class _Conn:
    """Two shapes of read: the distinct-sources list, then one coverage query per source."""

    def __init__(self, sources, rows_by_source):
        self._sources, self._rows, self._last = sources, rows_by_source, None

    def execute(self, stmt, params=None):
        self._last = ("sources" if "distinct source" in str(stmt) else params.get("s"))
        return self

    def fetchall(self):
        if self._last == "sources":
            return [type("R", (), {"source": s})() for s in self._sources]
        return self._rows.get(self._last, [])


def _row(**kw):
    base = dict(scanned=0, claimed_total=None, claimed_is_estimate=False,
                cursor_exhausted=True, page_budget_spent=False, error=None)
    return type("R", (), {**base, **kw})()


def _gaps(sources, rows) -> tuple[str, ...]:
    return window_coverage_gaps(_Conn(sources, rows), "org", since=T0, until=NOW)


# =================================================================================================
# 1 · ⛔ SILENT WHEN THERE IS NOTHING TO SAY
# =================================================================================================

def test_a_window_that_can_bear_an_absence_claim_adds_no_sentence():
    """A gap list that grows on every situation is a gap list nobody reads. Only the windows that
    cannot support the claim contribute."""
    assert _gaps(["gmail"], {"gmail": [_row(scanned=465, claimed_total=465)]}) == ()


def test_a_broken_read_is_silent_rather_than_noisy():
    """`unmet_source_families`'s own rule, kept: "a sentence is never worth the sweep"."""
    class _Broken:
        def execute(self, *_a, **_k): raise RuntimeError("no such table")
    assert window_coverage_gaps(_Broken(), "org", since=T0, until=NOW) == ()


# =================================================================================================
# 2 · ⛔ THE FOUR FAILURES ARE FOUR DIFFERENT SENTENCES
# =================================================================================================

def test_a_failed_sync_says_it_rules_nothing_out():
    (g,) = _gaps(["gmail"], {"gmail": [_row(error="429 rate limited")]})
    assert "failed" in g and "rules anything out" in g


def test_a_partial_sweep_names_the_tail():
    (g,) = _gaps(["gmail"], {"gmail": [_row(scanned=37, claimed_total=465, cursor_exhausted=False)]})
    assert "did not finish" in g and "tail" in g


def test_an_empty_read_is_not_an_empty_world():
    """⛔ FX-08 reaching the surface. `scanned=0` with no error and no denominator is what a rate
    limit returns, and it is also what an empty mailbox returns."""
    (g,) = _gaps(["gmail"], {"gmail": [_row(scanned=0)]})
    assert "not the same as none existing" in g


def test_a_missing_denominator_says_how_many_of_how_few():
    (g,) = _gaps(["gmail"], {"gmail": [_row(scanned=37)]})
    assert "gave no total" in g and "37 of an unknown number" in g


def test_a_source_with_no_runs_in_the_window_is_not_reported_as_a_gap():
    """It is not in the distinct-source list, so it contributes nothing. A sentence about a source
    the tenant never connected belongs to `unmet_source_families`, not here — two readers, two
    questions, and neither answering for the other."""
    assert _gaps([], {}) == ()


# =================================================================================================
# 3 · ⛔ ONE SENTENCE PER SOURCE, ORDERED
# =================================================================================================

def test_each_bad_source_contributes_exactly_one_sentence_in_a_stable_order():
    """Unstable ordering would make a situation's own account of itself change between two sweeps
    over identical data — the property `refresh_situations` is rebuilt from scratch to preserve.

    ⛔ THE SOURCES ARE FED UNSORTED ON PURPOSE. The first draft passed them already in order, so
    deleting `sorted()` changed nothing observable and the mutation probe stayed green — a test
    that asserts an ordering must supply an input that is not already in it, or it is asserting
    the fixture rather than the code. Same family as the blunt greps at L1-14, L1-18, L2-6 and
    L3-00: the assertion looked right and could not fail.
    """
    gaps = _gaps(["gmail", "gcal"], {"gmail": [_row(error="boom")],
                                     "gcal": [_row(scanned=1, claimed_total=1, cursor_exhausted=False)]})
    assert len(gaps) == 2
    assert gaps[0].startswith("the gcal sweep"), "gcal must sort before gmail regardless of read order"
    assert "gmail sync failed" in gaps[1]


def test_a_healthy_source_beside_a_broken_one_stays_silent():
    gaps = _gaps(["gcal", "gmail"], {"gmail": [_row(error="boom")],
                                     "gcal": [_row(scanned=7, claimed_total=7)]})
    assert len(gaps) == 1 and "gmail" in gaps[0]


# =================================================================================================
# 4 · ⛔ THE WIRING — the window is the situation's own span, not a constant
# =================================================================================================

def test_both_producers_pass_the_findings_own_span_and_never_a_constant():
    """⛔ A fixed lookback would attach a sentence about the wrong days, which is a more confident
    error than saying nothing. Read from the call sites so a later 'simplification' to a constant
    is a build failure."""
    for mod, span in (("outreach_situations", "since=_first"),
                      ("support_situations", "since=f.first_seen_at")):
        src = inspect.getsource(__import__(f"genios_engine.context.{mod}", fromlist=["x"]))
        assert "window_coverage_gaps" in src, f"{mod} no longer asks how much it read"
        assert span in src, f"{mod} must pass the finding's own span, not a constant window"


def test_both_producers_skip_rather_than_guess_when_there_is_no_span():
    """Evidence with no times cannot be asked the question. Guessing a window here would put a
    sentence about days nobody observed onto a card."""
    for mod, guard in (("outreach_situations", "if _first is not None:"),
                       ("support_situations", "if f.first_seen_at is not None:")):
        src = inspect.getsource(__import__(f"genios_engine.context.{mod}", fromlist=["x"]))
        assert guard in src, f"{mod} must skip the question when the span is unknown"


def test_the_memo_is_keyed_on_the_span_and_not_the_domain():
    """Two domains over one span share the read; one domain over two spans must not. Keying on
    `domain` — the obvious copy of the line above it — would give every situation in a sweep the
    first situation's coverage sentence."""
    for mod in ("outreach_situations", "support_situations"):
        src = inspect.getsource(__import__(f"genios_engine.context.{mod}", fromlist=["x"]))
        assert "_cov_gaps.setdefault(" in src
        assert "_cov_gaps.setdefault(\n                            domain" not in src
