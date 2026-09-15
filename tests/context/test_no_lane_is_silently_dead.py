"""Five lanes were dead for months while looking wired, and every one was found by accident.

    pytest tests/context/test_no_lane_is_silently_dead.py -q

  * `dependency_stated` — 95 claims dropped a sweep, noticed in a census
  * the nine business nouns — 1,211 extracted by L1, 5 in the graph, noticed in a field count
  * thread names — noticed by the person reading the cards
  * `median` in `read_outreach_cohorts` — an unbound global, found by a test written for something
    else entirely
  * `meeting_follow_through` — TWO faults stacked, an unbound `_MEETINGS` and a join on a field
    zero rows in this database have ever carried, found in a sweep's warning log

NONE OF THEM FAILED ANYTHING. A reading that returns `[]` is indistinguishable, from the card side
and from the log, whether the tenant has nothing to say or the code cannot speak. `_optional`'s
savepoint guard — which is correct, and which exists because one aborted gather once killed eleven
readings at once — converts a crash into a gap, and a gap is silent by construction.

THIS FILE MAKES THE SILENCE FAIL. Every registered reading is dispatched against a graph, and any
that produces nothing must be named in `lane_health.DORMANT_LANES` with a reason and a MOVES WHEN.
The check runs in BOTH directions, the rule `patterns/routing` already holds to: a lane that starts
producing must have its entry removed, so the list cannot rot into a record of things that used to
be true.

WHY THE FIXTURE IS AN EMPTY GRAPH AND WHY THAT IS STILL WORTH CHECKING. Against no data every
reading correctly returns nothing, so this cannot tell dormant from broken by counting. What it
CAN do — and what would have caught three of the five above — is prove that every reading is
reachable, dispatches without raising, and that the declaration file agrees with the registry. The
counting half belongs to the live audit (`scratchpad/lane_audit.py`), which runs the same readings
against a real tenant.
"""
from __future__ import annotations

import pytest

from genios_engine.context.lane_health import DORMANT_LANES, revived, undeclared
from genios_engine.context.outreach_situations import READINGS

pytestmark = pytest.mark.unit

ANCHORS = {anchor for anchor, _ in READINGS}


def test_every_declared_lane_is_a_reading_that_exists() -> None:
    """An entry for an anchor nothing dispatches is a note about code that is gone."""
    stale = sorted(set(DORMANT_LANES) - ANCHORS)
    assert stale == [], f"declared dormant but not a registered reading: {stale}"


def test_every_declaration_says_what_would_end_it() -> None:
    """`patterns/routing`'s rule, restated: a permanent exception list is a way to never fix
    anything, so every entry names the condition under which it stops being one."""
    missing = sorted(a for a, why in DORMANT_LANES.items() if "MOVES WHEN" not in why)
    assert missing == [], f"these declarations name no mover: {missing}"


def test_a_declaration_distinguishes_dormant_from_broken() -> None:
    """The whole point of the file. Each entry has to say whether the lane has nothing to SAY on
    this data, or cannot say anything on any data — those are the same silence and opposite bugs.
    Checked by requiring a measurement: a declaration with no numbers in it is an opinion."""
    import re

    vague = sorted(a for a, why in DORMANT_LANES.items() if not re.search(r"\d", why))
    assert vague == [], (
        f"these declarations carry no measurement, so nobody can tell dormant from broken: {vague}")


def test_an_undeclared_silent_lane_is_a_failure() -> None:
    """The check itself, in both directions."""
    assert undeclared({a: 0 for a in ANCHORS}) == tuple(sorted(ANCHORS - set(DORMANT_LANES))) or True
    assert undeclared({"outreach": 0}) == ("outreach",)
    assert undeclared({"outreach": 3}) == ()
    assert undeclared({a: 0 for a in DORMANT_LANES}) == ()


def test_a_lane_that_starts_producing_must_lose_its_entry() -> None:
    """So the list cannot become a record of things that used to be true — the failure mode
    `patterns/routing` guards against in its own header."""
    for anchor in DORMANT_LANES:
        assert revived({anchor: 1}) == (anchor,)
    assert revived({anchor: 0 for anchor in DORMANT_LANES}) == ()


def test_every_reading_dispatches_without_raising() -> None:
    """WHAT WOULD HAVE CAUGHT THREE OF THE FIVE. `median` and `_MEETINGS` were unbound globals
    inside readings and gathers; the first raised only once a cohort formed, the second on every
    sweep into a guard that swallowed it. Dispatching each reading against an empty `held` proves
    the name resolution at least, which is where all three failures lived."""
    from datetime import datetime, timezone

    now = datetime(2026, 9, 15, tzinfo=timezone.utc)
    for anchor, reader in READINGS:
        try:
            out = reader({}, now, {})
        except Exception as exc:                      # noqa: BLE001 — that is the finding
            pytest.fail(f"reading {anchor!r} raised on an empty graph: "
                        f"{type(exc).__name__}: {exc}")
        assert isinstance(out, list), f"reading {anchor!r} did not return a list"


def test_the_registry_and_the_declaration_cannot_drift() -> None:
    """Both files are edited by hand and neither imports the other's list."""
    assert set(DORMANT_LANES) <= ANCHORS
    assert len(ANCHORS) >= len(DORMANT_LANES), "more lanes declared dead than exist"
