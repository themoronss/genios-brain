"""RS-1 and RS-4 — "Anisha owns the WEST region from 1 June" had nowhere to live.

    pytest tests/context/test_a_person_can_finally_have_a_scope.py -q

`org_seats` is six columns and one of them is a two-word role string — `admin | member`,
consulted in exactly two places, both asking who mans the unrouted queue. Person and
organisation were held; RESPONSIBILITY, BUSINESS SCOPE and EFFECTIVE INTERVAL had no home.

So every situation in the tenant is equally everybody's, a regional manager can be shown a
national aggregate and blamed for another region's shortfall, and an ACTING term can only be
expressed by overwriting `manager_seat_id` on 1 June and hoping somebody remembers to
overwrite it back on 1 July. Nobody does — so July's escalations still climb to her, and the
June state was DESTROYED by the July write, so nothing can even say her term was meant to end.

THE PROPERTY THAT MATTERS MOST IS THE ONE ABOUT NOT LOSING ANYTHING. A tenant that has
declared nothing must see exactly what it sees today. Scope only ever narrows on a row
somebody wrote.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from genios_engine.executive.assignment import (
    REPORTS_TO,
    Responsibility,
    StaticSeatDirectory,
)

pytestmark = pytest.mark.unit

JUNE = datetime(2026, 6, 1, tzinfo=timezone.utc)
JULY = datetime(2026, 7, 1, tzinfo=timezone.utc)
MAY = JUNE - timedelta(days=1)


def owns(kind, key, **kw):
    return Responsibility(seat_id="seat-anisha", scope_kind=kind, scope_key=key, **kw)


def directory(**seats):
    return StaticSeatDirectory(seats=seats)


# =============================================================================================
# The sentence that had nowhere to live.
# =============================================================================================
def test_a_person_can_answer_for_a_named_slice_of_the_business():
    d = directory(**{"seat-anisha": {"email": "a@acme.test", "active": True,
                                     "responsibilities": (owns("region", "west",
                                                               valid_from=JUNE),)}})

    got = d.responsibilities("seat-anisha", JULY)

    assert [(r.scope_kind, r.scope_key, r.accountability) for r in got] == [
        ("region", "west", "owns")]


def test_the_inverse_question_finds_the_person():
    """The read that lets a card about the West find its regional manager rather than the
    first admin."""
    d = directory(**{
        "seat-anisha": {"email": "a@acme.test", "active": True,
                        "responsibilities": (owns("region", "west", valid_from=JUNE),)},
        "seat-raj": {"email": "r@acme.test", "active": True,
                     "responsibilities": (owns("region", "east", valid_from=JUNE),)},
    })

    assert d.seats_for_scope("region", "west", JULY) == ("seat-anisha",)
    assert d.seats_for_scope("region", "east", JULY) == ("seat-raj",)


def test_the_scope_key_matches_however_it_was_typed():
    d = directory(**{"seat-anisha": {"email": "a@acme.test", "active": True,
                                     "responsibilities": (owns("Region", "West",
                                                               valid_from=JUNE),)}})

    assert d.seats_for_scope("region", "west", JULY) == ("seat-anisha",)


def test_an_inactive_seat_answers_for_nothing():
    d = directory(**{"seat-gone": {"email": "g@acme.test", "active": False,
                                   "responsibilities": (owns("region", "west",
                                                             valid_from=JUNE),)}})

    assert d.seats_for_scope("region", "west", JULY) == ()


# =============================================================================================
# Nothing is lost for a tenant that has said nothing.
# =============================================================================================
def test_a_tenant_that_declared_nothing_has_no_scope_at_all():
    """EMPTY IS NOT AN EMPTY SCOPE. Reading empty as "this person owns nothing" would hide
    every card from everybody on the day the table shipped."""
    d = directory(**{"seat-anisha": {"email": "a@acme.test", "active": True}})

    assert d.responsibilities("seat-anisha", JULY) == ()


def test_an_inferred_responsibility_may_not_narrow_anybodys_view():
    """"This person handles the West's mail, probably" may WIDEN a view and may never narrow
    it. Hiding a real situation from somebody on the strength of a guess about their job is a
    silent false negative, and the one failure this concept could introduce."""
    guessed = owns("region", "west", valid_from=JUNE, source="inferred")
    declared = owns("region", "west", valid_from=JUNE, source="admin_declared")
    read = owns("region", "west", valid_from=JUNE, source="discovered")

    assert guessed.narrows is False
    assert declared.narrows is True
    assert read.narrows is True, "an uploaded org chart is the company's own statement"


# =============================================================================================
# The interval, which is what makes an acting term expressible.
# =============================================================================================
def test_a_term_that_has_not_started_does_not_apply():
    assert owns("region", "north", valid_from=JUNE).applies_at(MAY) is False


def test_a_term_that_ended_stops_applying_without_anybody_deleting_a_row():
    r = owns("region", "north", valid_from=JUNE, valid_until=JULY)

    assert r.applies_at(JUNE + timedelta(days=9)) is True
    assert r.applies_at(JULY) is False, "half-open: the end instant is already outside"


def test_an_acting_manager_stops_being_one_in_july():
    """THE WHOLE POINT OF RS-4. Today this needs a human to remember; here it needs nothing."""
    d = directory(**{
        "seat-report": {"email": "r@acme.test", "active": True,
                        "manager_seat_id": "seat-standing",
                        "responsibilities": (Responsibility(
                            seat_id="seat-report", scope_kind=REPORTS_TO,
                            scope_key="seat-acting", accountability="covers",
                            valid_from=JUNE, valid_until=JULY),)},
        "seat-standing": {"email": "s@acme.test", "active": True},
        "seat-acting": {"email": "x@acme.test", "active": True},
    })

    assert d.manager_of("seat-report", JUNE + timedelta(days=9)) == "seat-acting"
    assert d.manager_of("seat-report", JULY) == "seat-standing"


def test_the_standing_line_survives_the_acting_term():
    """The June state is not destroyed by the July read — which is what makes "who was her
    manager in June?" answerable in September."""
    d = directory(**{
        "seat-report": {"email": "r@acme.test", "active": True,
                        "manager_seat_id": "seat-standing",
                        "responsibilities": (Responsibility(
                            seat_id="seat-report", scope_kind=REPORTS_TO,
                            scope_key="seat-acting", accountability="covers",
                            valid_from=JUNE, valid_until=JULY),)},
        "seat-standing": {"email": "s@acme.test", "active": True},
        "seat-acting": {"email": "x@acme.test", "active": True},
    })

    assert d.manager_of("seat-report", MAY) == "seat-standing"


def test_manager_of_still_answers_with_no_argument():
    """Every existing caller is unchanged — `at` defaults to now."""
    d = directory(**{"seat-report": {"email": "r@acme.test", "active": True,
                                     "manager_seat_id": "seat-mgr"},
                     "seat-mgr": {"email": "m@acme.test", "active": True}})

    assert d.manager_of("seat-report") == "seat-mgr"


# =============================================================================================
# What this table deliberately does not carry.
# =============================================================================================
def test_responsibility_says_nothing_about_permission():
    """`authority_rules` answers "may this person approve this", is dated and source-ranked,
    and a second table that also implied permission would be two answers to one question —
    the defect this branch has now found fifteen times. A regional manager owns the region and
    cannot sign the contract."""
    r = owns("region", "west", valid_from=JUNE)

    assert not hasattr(r, "may_approve")
    assert not hasattr(r, "threshold_minor_units")
    assert r.accountability in ("owns", "covers", "reviews", "informed")
