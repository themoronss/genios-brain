"""72% of this tenant's cards carry no citation, and nothing failed.

    pytest tests/reason/test_a_lane_that_can_never_cite_says_so.py -q

`citations = 0` on a signal reads identically whether the lane never had a corpus to quote or
whether its corpus resolved to nothing and the binding died quietly. The L3 funnel reports the
same number either way. Measured on the pilot 2026-09-16: 53 of 74 signals — 51 of 72 delivered
cards — came from the `general` pack with zero citations, and the honest reason is that there is
no `general` corpus and there must not be one. That is a boundary. It had never been written down,
so it was reachable only by reading four modules and running three queries.

THIS FILE MAKES IT FAIL INSTEAD. A pack lane that publishes signals and cites on none of them must
be named in `reason/uncited_lanes.UNCITED_LANES` with a measurement and a MOVES WHEN. The check
runs in BOTH directions — the rule `patterns/routing` and `context/lane_health` already hold to —
so a lane that starts citing must have its entry removed and the list cannot rot into a record of
things that used to be true.

WHAT THIS DOES NOT CLAIM. Not citing is not the same as not reasoning. Every `general`-pack signal
runs the full reasoner and carries a real versioned capability through `reasoning_runs`, which is
where `reason/authority.AUDITED_CARD_JUDGMENTS_CTES` reads `capability_id` from — so calibration
can still attribute these cards. A test that conflated the two would report a working lane as
broken.
"""
from __future__ import annotations

import pytest

from genios_engine.reason.uncited_lanes import UNCITED_LANES, now_citing, undeclared

pytestmark = pytest.mark.unit


def test_an_uncited_lane_that_is_not_declared_is_reported() -> None:
    """The case that hid the boundary: a lane delivering cards, citing on none, unexplained."""
    assert undeclared({"general": (53, 0), "admin": (13, 13)}) == ()
    assert undeclared({"fundraising": (9, 0), "admin": (13, 13)}) == ("fundraising",)


def test_a_lane_that_publishes_nothing_is_not_an_uncited_lane() -> None:
    """Zero signals asks whether the lane RAN. Reporting it here merges two failures under one
    name — the precise conflation `lane_health` had to separate one layer down."""
    assert undeclared({"customer_support": (0, 0)}) == ()


def test_a_declared_lane_that_starts_citing_is_reported() -> None:
    """The other direction. An entry saying `general` cannot cite, on a run where it did, is a
    lie in the file readers trust to explain the zero."""
    assert now_citing({"general": (53, 0)}) == ()
    assert now_citing({"general": (53, 4)}) == ("general",)


def test_the_team_lane_publishes_under_no_pack_and_is_declared_that_way() -> None:
    """`reason/team/emit.py` writes signals with no `pack_id`; the reader hands that over as "".
    An entry keyed `None` or `"team"` would never match and the lane would read undeclared."""
    assert "" in UNCITED_LANES
    assert undeclared({"": (3, 0)}) == ()


@pytest.mark.parametrize("lane", sorted(UNCITED_LANES))
def test_every_entry_names_a_measurement_and_a_mover(lane: str) -> None:
    """A permanent exception list is a way to never fix anything. Both halves are structural —
    a date-stamped measurement, and the clause that would end the entry."""
    reason = UNCITED_LANES[lane]
    assert "MOVES WHEN:" in reason, f"{lane!r} declares no mover"
    assert "Measured 2026-" in reason, f"{lane!r} declares no measurement"
