"""The L2 pass spends the day's judgments on what is live first (`reason/l2/sweep._priority`).

    pytest tests/reason/l2/test_what_is_live_is_judged_first.py -q

Nearest-due-first judged the MOST OVERDUE subject first (hours to the nearest due are signed): on the design partner's
org every judged row of 22 Oct was 2,087-4,227 hours past due, while ten a pass and the day's budget carried what had
just arrived. Pure tests of the order; the call site is pinned in `test_the_l2_pass_pg.py`.
"""
from __future__ import annotations

import pytest

from genios_engine.reason.l2.sweep import LIVE_DUE_HOURS, _priority

pytestmark = pytest.mark.unit


def _key(*, due=None, age=None, importance=None, order=0):
    measured = {}
    if due is not None:
        measured["nearest_due"] = {"hours": due}
    if age is not None:
        measured["newest_signal_age"] = age
    return _priority(measured, importance, order)


def test_months_overdue_is_never_judged_before_what_just_arrived():
    stale = _key(due=-3000, age=3100, importance=9000)
    fresh = _key(age=2, importance=1000)
    assert sorted([stale, fresh]) == [fresh, stale]


def test_a_deadline_this_week_either_side_comes_first_the_closest_first():
    tomorrow, missed_yesterday, in_five_days = _key(due=20, age=900), _key(due=-24, age=900), _key(due=120, age=900)
    fresh = _key(age=1)
    assert sorted([fresh, in_five_days, missed_yesterday, tomorrow]) == [tomorrow, missed_yesterday, in_five_days, fresh]
    assert _key(due=LIVE_DUE_HOURS, age=900)[0] == 0 and _key(due=LIVE_DUE_HOURS + 1, age=900)[0] != 0


def test_outside_a_live_deadline_the_newest_evidence_first_and_no_dated_signal_last():
    week_old, month_old, quarter_old = _key(age=24 * 7), _key(age=24 * 30), _key(age=24 * 90)
    no_dated_signal = _key()
    assert sorted([quarter_old, no_dated_signal, month_old, week_old]) == [week_old, month_old, quarter_old,
                                                                           no_dated_signal]


def test_inside_a_band_the_more_important_first_then_the_order_read():
    a, b, c = _key(age=5, importance=2000, order=0), _key(age=5, importance=8000, order=1), _key(age=5, order=2)
    assert sorted([a, b, c]) == [b, a, c]
