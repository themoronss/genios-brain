"""G9 · sync cadence and jitter — Wave W9.

Every tenant syncing on the same minute is a self-inflicted thundering herd against both the
source's rate limits and our own workers. Cadence plus deterministic per-connection jitter spreads
them, and "deterministic" is the load-bearing word: jitter derived from the connection id replays
identically, so a schedule can be reasoned about and tested. `random.random()` would make the
schedule unobservable and this file meaningless.

    pytest tests/capture/connectors tests/capture/acquire -q
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta, timezone

import pytest

from genios_engine.capture.acquire.cadence import (DEFAULT_CADENCE_POLICY, MAX_INTERVAL_SECONDS,
                                                   MIN_INTERVAL_SECONDS, CadenceRequest,
                                                   resolve_cadence)
from genios_engine.capture.acquire.jitter import DEFAULT_SPREAD_BP, JitterKey, jitter_offset
from genios_engine.capture.acquire.scheduler import ConnectionSchedule, plan_poll, select_due

WAVE = "W9"
GATE = "G9"

NOW = datetime(2026, 1, 14, 9, 0, tzinfo=timezone.utc)
GMAIL_INTERVAL = 15 * 60


def _schedule(connection_id: str, *, org: str = "org_a", source: str = "gmail",
              last: datetime | None = NOW, override: int | None = None) -> ConnectionSchedule:
    return ConnectionSchedule(org_id=org, connection_id=connection_id, source=source,
                              override_seconds=override, last_success_at=last, watermark=last)


# ---------------------------------------------------------------------------------------------
# cadence — the per-source interval, and the tenant override that may not escape the bounds
# ---------------------------------------------------------------------------------------------

@pytest.mark.parametrize("source,seconds,origin", [
    pytest.param("gmail", 15 * 60, "policy", id="gmail is the safety net behind the webhook"),
    pytest.param("gcal", 3600, "policy", id="calendar hourly"),
    pytest.param("notion", 12 * 3600, "policy", id="a quarterly-edited page does not repay hourly"),
    pytest.param("sharepoint", 6 * 3600, "default", id="an unlisted source keeps the catch-all"),
])
def test_each_source_polls_at_its_own_reviewed_cadence(source, seconds, origin):
    cadence = resolve_cadence(CadenceRequest(source), policy=DEFAULT_CADENCE_POLICY)
    assert (cadence.interval_seconds, cadence.origin) == (seconds, origin)


@pytest.mark.parametrize("wanted,expected,origin", [
    pytest.param(300, 300, "override", id="a sane override is honoured"),
    pytest.param(5, MIN_INTERVAL_SECONDS, "override_clamped", id="5s is a denial of service"),
    pytest.param(10 ** 9, MAX_INTERVAL_SECONDS, "override_clamped", id="never is not a cadence"),
])
def test_a_tenant_override_is_bounded_and_says_when_it_was_clamped(wanted, expected, origin):
    """`origin` is the whole reason the type carries more than an integer: an admin asking why a
    connection polls hourly when they configured five seconds needs the answer to be in the data."""
    cadence = resolve_cadence(CadenceRequest("gmail", wanted))
    assert (cadence.interval_seconds, cadence.origin) == (expected, origin)


# ---------------------------------------------------------------------------------------------
# jitter — deterministic, bounded, and keyed on more than the org
# ---------------------------------------------------------------------------------------------

@pytest.mark.gate
def test_the_same_connection_and_instant_always_produce_the_same_next_run():
    """The determinism gate. Two identical inputs, two identical answers — not approximately."""
    first = plan_poll(_schedule("con_1"), now=NOW)
    second = plan_poll(_schedule("con_1"), now=NOW)
    assert first.next_run_at == second.next_run_at
    assert first == second, "a schedule that cannot be recomputed cannot be reasoned about"


def test_two_sources_on_one_connection_do_not_land_together():
    """One Composio connection can back gmail and gcal. Keying jitter on the connection alone
    would put a tenant's two heaviest calls on the same second — a herd of two."""
    key = dict(interval_seconds=GMAIL_INTERVAL)
    gmail = jitter_offset(JitterKey("org_a", "con_1", "gmail"), **key)
    gcal = jitter_offset(JitterKey("org_a", "con_1", "gcal"), **key)
    assert gmail.offset_seconds != gcal.offset_seconds


def test_the_offset_never_leaves_the_declared_spread():
    """±10% of the interval. A "15 minute" cadence has to keep meaning roughly 15 minutes, so the
    smear that fixes the herd must not become a schedule nobody predicted."""
    bound = GMAIL_INTERVAL * DEFAULT_SPREAD_BP // 10_000
    for i in range(500):
        offset = jitter_offset(JitterKey("org_a", f"con_{i}", "gmail"),
                               interval_seconds=GMAIL_INTERVAL)
        assert -bound <= offset.offset_seconds <= bound
        assert -DEFAULT_SPREAD_BP <= offset.fraction_bp <= DEFAULT_SPREAD_BP


def test_zero_spread_reproduces_the_herd_this_unit_exists_to_remove():
    """The control. With the spread turned off, 500 connections that last synced together fire on
    ONE instant — which is the failure, stated as a measurement rather than as a worry."""
    schedules = [_schedule(f"con_{i}") for i in range(500)]
    instants = {plan_poll(s, now=NOW, spread_bp=0).next_run_at for s in schedules}
    assert len(instants) == 1


@pytest.mark.gate
def test_a_large_set_of_connections_is_smeared_across_the_whole_spread():
    """The herd gate, against the same 500 connections the control above collapses to one instant.

    The offset is an integer number of seconds inside ±90s of a 15-minute cadence, so 181 distinct
    instants is the ceiling arithmetic allows — asserting "no two share a minute" would be
    asserting something the range cannot deliver. What CAN be asserted, and is what the unit
    promises, is that the set is spread across essentially all of them and that no single second
    carries a meaningful share of the fleet.
    """
    schedules = [_schedule(f"con_{i}") for i in range(500)]
    runs = [plan_poll(s, now=NOW).next_run_at for s in schedules]
    per_instant = Counter(runs)

    assert len(per_instant) >= 150, (
        f"only {len(per_instant)} distinct instants out of a possible 181 — the offsets are "
        "clustering, so the herd has been moved rather than removed")
    assert max(per_instant.values()) <= 25, (
        "one instant carries more than 5% of the fleet, which is the herd in miniature")
    spread = max(runs) - min(runs)
    assert spread >= timedelta(seconds=170), f"the smear is only {spread}, not the declared ±10%"


# ---------------------------------------------------------------------------------------------
# the decision the sweep actually consumes
# ---------------------------------------------------------------------------------------------

def test_a_connection_that_has_never_synced_is_due_immediately_and_unjittered():
    """Jittering the FIRST poll delays a tenant's very first data for no benefit — the herd this
    guards against is the recurring one, not the connect moment."""
    decision = plan_poll(_schedule("con_new", last=None), now=NOW)
    assert decision.due is True
    assert decision.next_run_at == NOW


@pytest.mark.parametrize("elapsed,due", [
    pytest.param(timedelta(minutes=1), False, id="a minute after a sync is not its turn again"),
    pytest.param(timedelta(hours=2), True, id="two hours later it certainly is"),
])
def test_due_is_decided_against_the_last_success_not_the_wall_clock_alone(elapsed, due):
    schedule = _schedule("con_1", last=NOW)
    assert plan_poll(schedule, now=NOW + elapsed).due is due


def test_select_due_returns_the_longest_waiting_first():
    """Fairness, not cosmetics: a sweep with a wall-clock budget that runs its list in store order
    starves whatever sorts last, and the connection waiting longest is closest to a catch-up."""
    schedules = [_schedule("con_recent", last=NOW - timedelta(hours=1)),
                 _schedule("con_old", last=NOW - timedelta(days=2)),
                 _schedule("con_fresh", last=NOW)]
    due = select_due(schedules, now=NOW + timedelta(minutes=1))
    assert [d.connection_id for d in due] == ["con_old", "con_recent"]
    assert all(d.due for d in due)
