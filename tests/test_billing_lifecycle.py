"""A trial has to actually end.

Before this, NOTHING in the product wrote `plan_status='expired'` or set `grace_until`. A 15-day
trial kept answering questions on day 400 until its credits ran out; the dashboard's expired-plan
banner rendered a state the backend could not produce; and `subscription.in_grace` was
permanently false because the column it reads was never written.

The pure state machine is tested here. The tick and the refusal are exercised against real
Postgres in `test_billing.py`.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from genios_engine.platform import billing as B

pytestmark = pytest.mark.unit

NOW = datetime(2026, 9, 9, 12, 0, tzinfo=timezone.utc)
DAY = timedelta(days=1)


def state(status, expires, grace):
    return B.expiry_state(status, expires, grace, now=NOW)


def test_a_live_trial_is_active():
    assert state("trial", NOW + 5 * DAY, None) == "active"


def test_a_plan_with_no_expiry_recorded_is_active():
    """Enterprise and anything hand-provisioned carries no `plan_expires_at`. A missing date must
    not read as a lapsed one."""
    assert state("active", None, None) == "active"


def test_the_day_it_lapses_it_enters_grace():
    assert state("trial", NOW - DAY, NOW + 6 * DAY) == "grace"


def test_grace_is_read_from_the_dates_not_the_status():
    """A row the tick has not reached yet is already past due, and must be treated as such."""
    assert state("trial", NOW - DAY, NOW + 6 * DAY) == "grace"
    assert state("active", NOW - DAY, None) == "expired"


def test_when_grace_runs_out_it_is_expired():
    assert state("expired", NOW - 30 * DAY, NOW - DAY) == "expired"


def test_grace_that_has_not_been_set_is_not_grace():
    assert state("expired", NOW - DAY, None) == "expired"


def test_suspended_and_cancelled_are_expired_whatever_the_dates_say():
    assert state("suspended", NOW + 100 * DAY, NOW + 100 * DAY) == "expired"
    assert state("cancelled", NOW + 100 * DAY, None) == "expired"


def test_the_grace_window_is_a_real_number_of_days():
    assert B.GRACE_DAYS > 0


def test_the_expiry_check_does_not_care_about_the_balance():
    """Plan boundary and empty wallet are different refusals pointing at different buttons; the
    state machine must not conflate them."""
    assert state("trial", NOW - DAY, None) == "expired"     # regardless of any credits left
