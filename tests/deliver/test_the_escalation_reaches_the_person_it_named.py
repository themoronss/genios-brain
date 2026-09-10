"""The ladder resolved the manager, recorded the manager, and messaged the owner.

    pytest tests/deliver/test_the_escalation_reaches_the_person_it_named.py -q

The default ladder is day 7 → audience MANAGER, day 14 → audience EXECUTIVE.
`resolve_escalation_target` correctly climbs `manager_of(owner)` and
`execution_escalations.target_seat` records who that was — the column's own comment says
"resolved at fire time, not plan time", and `tests/test_executive_sweep.py:360` already
asserts the resolution is right.

Then `enqueue_executive_messages` bound `:seat` from `x.assignee`. So the Slack message
arrived in the OWNER's own DM reading "Escalated — <goal>": the manager learned nothing, and
the owner was told they had been escalated to somebody who was never contacted. Everything
about the escalation was correct except who received it.
"""

from __future__ import annotations

import inspect

import pytest

from genios_engine.deliver import executive_bridge as bridge

pytestmark = pytest.mark.unit


def test_the_enqueue_reads_the_seat_the_ladder_resolved():
    source = inspect.getsource(bridge.enqueue_executive_messages)

    assert "esc.target_seat" in source
    assert 'left join execution_escalations esc' in source


def test_the_owner_is_the_fallback_and_not_the_default():
    """`resolve_escalation_target` already degrades explicitly — manager, then admins, then the
    owner with a reason code that says so — so a null target means the ladder itself decided
    the owner is right. That is a fallback, not a guess."""
    source = inspect.getsource(bridge.enqueue_executive_messages)

    assert 'row["target_seat"] or row["assignee"]' in source


def test_a_plain_reminder_still_reaches_the_owner():
    """The join is LEFT for a reason: a `remind` event has no escalation row at all, and
    delivering it to the owner is correct."""
    source = inspect.getsource(bridge.enqueue_executive_messages)

    assert "left join execution_escalations" in source


def test_the_join_never_casts_a_string_to_an_integer():
    """A BUG THIS FIX NEARLY INTRODUCED. `detail` is jsonb written by several producers, and
    `cast('abc' as int)` RAISES in Postgres — one malformed `escalation_day` would have taken
    down the whole enqueue for the tenant, turning a corrupt field into a delivery outage.
    `day_offset` is an int column, so casting it the other way always succeeds."""
    source = inspect.getsource(bridge.enqueue_executive_messages)

    assert "cast(esc.day_offset as text)" in source
    # THE SQL LINES ONLY. A first draft asserted `"as int)" not in source` and matched the
    # COMMENT above the fix, which quotes the dangerous cast to explain it — a test that reads
    # prose as code is a test that goes red for the right words in the wrong place.
    sql_lines = [line for line in source.split("\n")
                 if line.lstrip().startswith('"') and "--" not in line]

    assert not any("as int)" in line for line in sql_lines)


def test_the_ladder_still_resolves_the_manager():
    """The half that was always right, pinned so a change to the delivery seam cannot quietly
    move it."""
    from genios_engine.executive.assignment import (
        AudienceClass,
        StaticSeatDirectory,
        resolve_escalation_target,
    )

    directory = StaticSeatDirectory(seats={
        "seat-owner": {"email": "owner@acme.test", "active": True,
                       "manager_seat_id": "seat-mgr"},
        "seat-mgr": {"email": "mgr@acme.test", "active": True},
    })

    got = resolve_escalation_target(audience=AudienceClass.MANAGER,
                                    owner_seat="seat-owner", directory=directory)

    assert got.seat_id == "seat-mgr"


def test_an_owner_with_no_manager_degrades_rather_than_escalating_to_nobody():
    from genios_engine.executive.assignment import (
        AudienceClass,
        StaticSeatDirectory,
        resolve_escalation_target,
    )

    directory = StaticSeatDirectory(seats={
        "seat-owner": {"email": "owner@acme.test", "active": True},
        "seat-admin": {"email": "ops@acme.test", "active": True, "role": "admin"},
    })

    got = resolve_escalation_target(audience=AudienceClass.MANAGER,
                                    owner_seat="seat-owner", directory=directory)

    assert got.seat_id is not None, "escalating to nobody is not escalating"
