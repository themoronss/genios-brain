"""`resolve_floor` said what the number is and who owns it. Not what it does.

The module's own docstring makes the argument — *"a startup's $8K renewal is its quarter; a
bank's is noise"* — and `DEFAULT_FLOOR_BP` is documented as "the value a tenant with no row gets,
never the value every tenant gets". Measured 2026-09-17: `org_qualification_floors` holds ZERO
rows, so every tenant is on that default, and the same 2500 keeps 45.4% of one tenant's scored
signals and 35.7% of another's. Ten points of difference in how much of their own mail reaches
them, from one number nobody chose for either of them.

NO RECOMMENDED FLOOR, and that is the point rather than an omission. This module is emphatic that
a floor is a row with an `owner` and an append-only changelog, because a threshold that moves
without a person behind it is how one gets changed by a deploy with no date attached. So the
profile reports the tenant's own distribution and what each decile of it would keep; the human
picks one through `PUT /qualification/floor`.

BOTH HALVES OF THE DISTRIBUTION. `qualified_signals` alone is what the floor already let through,
so reading it would measure the floor with the floor. `qualification_drops` carries the same
`importance_bp` for everything it refused, and the union is what ALG-17 actually produced.
"""
from __future__ import annotations

import pytest

from genios_engine.capture.esqe.qualification import (
    MIN_PROFILE_SAMPLE,
    floor_profile,
)

TEN = [400, 800, 1200, 1600, 2000, 2400, 2800, 3200, 3600, 4000]


# =============================================================================================
# what the number is doing
# =============================================================================================
def test_it_says_how_much_of_this_tenants_traffic_survives():
    p = floor_profile(TEN, 2500)

    assert p["scored"] == 10
    assert p["kept"] == 4                    # 2800, 3200, 3600, 4000
    assert p["kept_bp"] == 4000              # 40.00%


def test_the_same_floor_reads_differently_on_two_tenants():
    """The whole reason the item exists: one number, two answers."""
    generous = floor_profile([3000, 3200, 3400, 3600], 2500)
    harsh = floor_profile([400, 600, 800, 1000], 2500)

    assert generous["kept_bp"] == 10_000
    assert harsh["kept_bp"] == 0


def test_a_floor_at_or_below_the_minimum_keeps_everything():
    """`>=`, not `>`. A signal exactly at the floor is admitted — `qualification_drops` carries
    `check (importance_bp < floor_bp)`, so the boundary belongs to the kept side."""
    assert floor_profile(TEN, 400)["kept"] == 10


def test_a_floor_above_the_maximum_keeps_nothing():
    assert floor_profile(TEN, 99_999)["kept"] == 0


# =============================================================================================
# the options, which come from the tenant and not from a list
# =============================================================================================
def test_every_candidate_floor_is_a_value_this_tenant_actually_produced():
    """A suggested 3000 on a tenant whose scores top out at 1200 is a number that means nothing
    to them. Percentile_DISC, never an interpolation between two points."""
    p = floor_profile(TEN, 2500)

    for row in p["deciles"]:
        assert row["floor_bp"] in TEN


def test_the_candidates_only_ever_keep_less_as_they_rise():
    p = floor_profile(TEN, 2500)
    keeps = [row["would_keep"] for row in p["deciles"]]

    assert keeps == sorted(keeps, reverse=True), "a higher floor cannot admit more"


def test_each_candidate_reports_what_it_would_actually_keep():
    p = floor_profile(TEN, 2500)

    for row in p["deciles"]:
        assert row["would_keep"] == sum(1 for v in TEN if v >= row["floor_bp"])


# =============================================================================================
# refusing to read three points as a distribution
# =============================================================================================
def test_a_tenant_with_almost_no_signals_is_told_so():
    """One live org carries three scored signals. Percentiles over three points are a number with
    a decimal place and no evidence, and reporting them without saying so is how a tenant gets
    tuned onto noise."""
    assert floor_profile([3465, 3465, 3465], 2500)["enough_to_read"] is False
    assert floor_profile(list(range(MIN_PROFILE_SAMPLE)), 0)["enough_to_read"] is True


def test_a_tenant_with_nothing_scored_is_not_a_crash():
    p = floor_profile([], 2500)

    assert p["scored"] == 0 and p["kept"] == 0
    assert p["kept_bp"] is None, "0/0 is not 0%, and printing 0% would read as 'we drop everything'"
    assert p["deciles"] == []


def test_the_order_values_arrive_in_changes_nothing():
    import random
    shuffled = TEN[:]
    random.Random(7).shuffle(shuffled)

    assert floor_profile(shuffled, 2500) == floor_profile(TEN, 2500)


# =============================================================================================
# the call site
# =============================================================================================
def test_the_floor_route_reports_the_profile():
    """`resolve_floor` alone answers "what is it and who owns it" and the owner's actual question
    goes unanswered — which is the state this closes."""
    import ast
    import inspect

    from genios_engine.api import routes

    fn = next(n for n in ast.walk(ast.parse(inspect.getsource(routes)))
              if isinstance(n, ast.FunctionDef) and n.name == "get_qualification_floor")
    src = ast.unparse(fn)

    assert "floor_profile(" in src, "the floor route no longer says what the floor does"
    assert "qualification_drops" in src, (
        "the profile reads only what the floor admitted — measuring the floor with the floor")
