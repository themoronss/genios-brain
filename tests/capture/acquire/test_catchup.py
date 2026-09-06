"""L1.2.6-U3 · catch-up windows.

The failure this unit prevents is invisible by construction: after an outage the connection
resumes, pulls its normal page budget, advances the watermark to the newest thing it saw, and
reports success — while the middle of the gap is never requested again. So the assertions here
are about the two boundaries of the fix. It must not re-read anything BEFORE the stored
watermark (that is a backfill wearing a catch-up's clothes, paid for at the provider and at the
LLM gate), and it must not treat every late tick as an outage (a deploy pushes one interval).

`now` is a parameter in every row below; nothing here reads a clock.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from genios_engine.capture.acquire.catchup import (
    CATCH_UP_INTERVAL_MULTIPLE,
    MAX_CATCH_UP_LOOKBACK_SECONDS,
    MAX_CATCH_UP_PAGES,
    CatchUpRequest,
    plan_catch_up,
)

NOW = datetime(2026, 1, 14, 9, 0, tzinfo=timezone.utc)
GMAIL = 15 * 60
BUDGET = 20


def _plan(*, ago_seconds=None, watermark=None, interval=GMAIL, budget=BUDGET, now=NOW):
    return plan_catch_up(CatchUpRequest(
        now=now,
        last_success_at=None if ago_seconds is None else now - timedelta(seconds=ago_seconds),
        watermark=watermark, interval_seconds=interval, base_page_budget=budget))


@pytest.mark.parametrize("ago_seconds,expect_catch_up,expect_reason", [
    (None, False, "first_run"),                      # never polled: backfill's job, not ours
    (0, False, "current"),
    (GMAIL, False, "current"),                       # one interval — an ordinary tick
    (2 * GMAIL, False, "current"),
    (CATCH_UP_INTERVAL_MULTIPLE * GMAIL, False, "current"),        # exactly at the line
    (CATCH_UP_INTERVAL_MULTIPLE * GMAIL + 1, True, "gap"),         # one second past it
    (24 * 3600, True, "gap"),                        # the plan's worked example
])
def test_only_a_real_gap_is_a_catch_up(ago_seconds, expect_catch_up, expect_reason):
    plan = _plan(ago_seconds=ago_seconds, watermark=NOW - timedelta(days=1))
    assert (plan.catch_up, plan.reason) == (expect_catch_up, expect_reason)


def test_twenty_four_hour_gap_extends_the_page_budget_and_is_capped():
    plan = _plan(ago_seconds=24 * 3600, watermark=NOW - timedelta(hours=24))
    assert plan.catch_up is True
    assert plan.missed_intervals == 96              # 24h of 15-minute cadences
    assert plan.max_pages == MAX_CATCH_UP_PAGES     # 20 * 96 would be a self-inflicted outage
    assert plan.gap_seconds == 24 * 3600


def test_page_budget_scales_with_the_gap_below_the_cap():
    plan = _plan(ago_seconds=5 * GMAIL, watermark=NOW - timedelta(hours=2), budget=3)
    assert (plan.catch_up, plan.missed_intervals, plan.max_pages) == (True, 5, 15)


def test_catch_up_resumes_from_the_watermark_and_never_before_it():
    """The whole point: pay for more pages, not for re-reading history."""
    watermark = NOW - timedelta(hours=20)
    plan = _plan(ago_seconds=24 * 3600, watermark=watermark)
    assert plan.since == watermark


def test_a_healthy_run_keeps_its_normal_budget_and_resume_point():
    watermark = NOW - timedelta(minutes=20)
    plan = _plan(ago_seconds=GMAIL, watermark=watermark)
    assert (plan.max_pages, plan.since) == (BUDGET, watermark)


def test_gap_without_a_watermark_covers_the_gap_itself():
    """No watermark to resume from — the window must still cover the missed time, so nothing in
    the gap is skipped."""
    plan = _plan(ago_seconds=24 * 3600, watermark=None)
    assert plan.since == NOW - timedelta(hours=24)


def test_lookback_without_a_watermark_is_bounded():
    """A connection down for a year must not turn one poll into a full-history backfill."""
    plan = _plan(ago_seconds=365 * 24 * 3600, watermark=None)
    assert plan.since == NOW - timedelta(seconds=MAX_CATCH_UP_LOOKBACK_SECONDS)
    assert plan.max_pages == MAX_CATCH_UP_PAGES


def test_a_future_last_success_is_clamped_not_negative():
    """Clock skew or a restored backup; a negative gap would produce a negative page budget."""
    plan = plan_catch_up(CatchUpRequest(
        now=NOW, last_success_at=NOW + timedelta(hours=3), watermark=None,
        interval_seconds=GMAIL, base_page_budget=BUDGET))
    assert (plan.gap_seconds, plan.catch_up, plan.max_pages) == (0, False, BUDGET)


def test_naive_timestamps_are_read_as_utc_rather_than_crashing_the_sweep():
    plan = plan_catch_up(CatchUpRequest(
        now=NOW, last_success_at=(NOW - timedelta(hours=24)).replace(tzinfo=None),
        watermark=(NOW - timedelta(hours=24)).replace(tzinfo=None),
        interval_seconds=GMAIL, base_page_budget=BUDGET))
    assert plan.catch_up is True and plan.since.tzinfo is not None


def test_catch_up_budget_is_never_below_a_normal_run():
    """A source whose cadence is longer than its gap-in-intervals arithmetic (missed==0 cannot
    reach here, but a rounding change must not silently starve the recovery run)."""
    plan = _plan(ago_seconds=CATCH_UP_INTERVAL_MULTIPLE * 3600 + 60, interval=3600, budget=7)
    assert plan.catch_up is True and plan.max_pages >= 7


@pytest.mark.parametrize("interval,budget", [(0, 20), (-60, 20), (GMAIL, 0), (GMAIL, -1)])
def test_invalid_inputs_raise(interval, budget):
    with pytest.raises(ValueError):
        plan_catch_up(CatchUpRequest(now=NOW, last_success_at=NOW, watermark=None,
                                     interval_seconds=interval, base_page_budget=budget))
