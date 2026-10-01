"""S2 · why this tenant cannot be routed to — and the third state that makes the answer honest.

    pytest tests/executive/test_an_unroutable_tenant_says_why.py -q

⛔ WHAT THIS CLOSES. `platform/receipts.py` carried 23 receipts across every layer and NOT ONE was about
organisation data. A tenant with a compiled pack, a live activation row, a full graph and 23 green
receipts could still be completely unroutable, and nothing said so — which is the state the pilot is in
and the whole reason `executive/` "examines nothing every tick".

⛔ THE TESTS THAT MATTER ARE ABOUT `unknown`. *"Nobody has filed a reporting line"* and *"we could not
read the table"* call for opposite actions, and this programme has been caught twice by conflating
exactly those two — `no_model_wired` in L1 and the graph-revision guard in L3. The rule both produced:
**a count without its dimension is not a measurement.**
"""

from __future__ import annotations

import pytest

from genios_engine.executive.readiness import (CHANNELS, MISSING, READY, REPORTING_LINE, REQUIREMENTS,
                                               SEATS, STATES, UNKNOWN, Readiness, Requirement, assess,
                                               read)

pytestmark = pytest.mark.unit


def _ok(**over):
    counts = dict(seats=4, reporting_line=3, channels=1)
    counts.update(over)
    return assess("org_1", **counts)


# =================================================================================================
# 1 · the ordinary verdicts
# =================================================================================================
def test_a_fully_loaded_tenant_is_routable():
    r = _ok()
    assert r.routable is True
    assert r.blocked_by == () and r.unmeasured == ()
    assert "is routable" in r.explain()


@pytest.mark.parametrize("gap", REQUIREMENTS)
def test_any_single_gap_blocks_routing_and_is_named(gap):
    r = _ok(**{gap: 0})
    assert r.routable is False
    assert r.blocked_by == (gap,)
    assert gap in r.explain()


def test_every_requirement_appears_in_every_verdict():
    """A verdict missing a key is one a caller has to `.get()` carefully. All three, always."""
    assert tuple(x.name for x in _ok().requirements) == REQUIREMENTS


def test_the_requirements_are_ordered_by_what_to_fix_first():
    """⛔ Seats, then the line between them, then how to reach them. A reader who fixes channels
    before seats has fixed nothing."""
    assert REQUIREMENTS == (SEATS, REPORTING_LINE, CHANNELS)


# =================================================================================================
# 2 · ⛔ unknown is not missing
# =================================================================================================
def test_an_unreadable_count_is_unknown_never_missing():
    """⛔ THE ONE THAT MATTERS MOST. Treating an unreadable table as an empty one reports a working
    tenant as unconfigured — and somebody then "fixes" data that was already there."""
    r = _ok(seats=None)
    assert r.requirements[0].state == UNKNOWN
    assert r.unmeasured == (SEATS,)
    assert r.blocked_by == (), "unknown must not be reported as a block"


def test_unknown_still_leaves_the_tenant_unroutable():
    """We cannot claim a tenant is routable on evidence we could not read."""
    assert _ok(seats=None).routable is False


def test_zero_and_unreadable_read_differently():
    assert _ok(channels=0).requirements[2].state == MISSING
    assert _ok(channels=None).requirements[2].state == UNKNOWN


def test_a_mixed_verdict_says_both_halves_separately():
    """⛔ Folding "could not measure" into "blocked by" would claim we know something is absent."""
    r = _ok(seats=0, channels=None)
    line = r.explain()
    assert "blocked by seats" in line
    assert "could not measure channels" in line


def test_the_unknown_detail_says_it_is_not_the_same_as_absent():
    detail = _ok(reporting_line=None).requirements[1].detail
    assert "NOT the same as" in detail


# =================================================================================================
# 3 · ⛔ it names the fix, not only the gap
# =================================================================================================
@pytest.mark.parametrize("gap", REQUIREMENTS)
def test_a_missing_requirement_says_what_it_costs_and_how_to_fix_it(gap):
    """⛔ *"seats: missing"* sends somebody hunting through five tables. A readiness report nobody can
    act on is a status page."""
    detail = _ok(**{gap: 0}).requirements[REQUIREMENTS.index(gap)].detail
    assert "Fix:" in detail
    assert len(detail) > 60, "a consequence and a fix do not fit in a label"


def test_the_seats_consequence_names_what_actually_breaks():
    assert "nobody to assign" in _ok(seats=0).requirements[0].detail


def test_the_reporting_line_consequence_names_the_ladder_rung():
    """Rung 7 — `escalate → manager`. Without a line it climbs into nothing."""
    assert "rung 7" in _ok(reporting_line=0).requirements[1].detail


def test_the_channel_consequence_claims_only_what_the_schema_supports():
    """⛔ `org_channels` is keyed `(org_id, channel)` and there is NO per-seat channel — `org_seats`
    has no such column (0008, and 0041 added only `manager_seat_id`). My first version said "no active
    seat has a channel", which the data cannot support."""
    detail = _ok(channels=0).requirements[2].detail
    assert "the tenant has no active channel" in detail
    assert "seat" not in detail.lower()


# =================================================================================================
# 4 · the contract refuses an incoherent verdict
# =================================================================================================
def test_a_state_outside_the_three_is_refused():
    with pytest.raises(ValueError, match="not a readiness state"):
        Requirement("seats", "probably", "something")


def test_a_verdict_with_no_detail_is_refused():
    """⛔ A state with no sentence is a status page entry, which is what this module exists not to be."""
    with pytest.raises(ValueError, match="must say something"):
        Requirement("seats", READY, "   ")


def test_a_verdict_belongs_to_a_tenant():
    with pytest.raises(ValueError, match="belongs to a tenant"):
        assess("  ", seats=1, reporting_line=1, channels=1)


def test_the_states_are_exactly_three():
    assert STATES == (READY, MISSING, UNKNOWN)


def test_a_verdict_is_frozen():
    r = _ok()
    with pytest.raises(Exception):
        r.requirements = ()


# =================================================================================================
# 5 · ⛔ pure, and one bad count does not poison the others
# =================================================================================================
def test_assess_touches_no_database_no_clock_no_network():
    """A readiness check that could itself fail on the network is one more thing to diagnose at the
    moment somebody is already diagnosing something."""
    import ast
    import inspect

    from genios_engine.executive import readiness

    tree = ast.parse(inspect.getsource(readiness))
    top = {a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
    top |= {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module
            and not isinstance(getattr(n, "parent", None), ast.FunctionDef)}
    for forbidden in ("datetime", "time", "random", "requests"):
        assert forbidden not in top


def test_one_unreadable_count_does_not_turn_the_others_unknown():
    """⛔ A per-row seam: `read` catches each count on its own, so one unreadable table does not make
    the whole verdict unmeasurable — the same rule this codebase applies to a batch."""
    class _Conn:
        def execute(self, statement, params=None):
            if "org_channels" in str(statement):
                raise RuntimeError("relation does not exist")
            return type("R", (), {"scalar": lambda s: 7})()

    r = read(_Conn(), "org_1")
    assert r.requirements[0].state == READY
    assert r.requirements[1].state == READY
    assert r.requirements[2].state == UNKNOWN


def test_read_never_raises_on_a_dead_connection():
    class _Dead:
        def execute(self, *a, **k):
            raise RuntimeError("connection closed")

    r = read(_Dead(), "org_1")
    assert set(x.state for x in r.requirements) == {UNKNOWN}
    assert r.routable is False


# =================================================================================================
# 6 · ⛔ one definition of "ready", two surfaces
# =================================================================================================
def test_the_sql_lives_in_the_floor_so_both_callers_read_the_same_thing():
    """⛔ Duplicating the three queries would let the receipt and the readiness page drift about what
    "ready" means. Putting them in `executive/` would have made the floor import a layer — which the
    topology test does not catch, because `platform` is cross-cutting and exempt."""
    from genios_engine.platform import org_readiness_sql
    from genios_engine.executive import readiness

    assert readiness.COUNT_SQL is org_readiness_sql.COUNT_SQL


def test_every_tenant_scoped_count_is_actually_tenant_scoped():
    """⛔ An unfiltered count would report one tenant's seats on another's readiness page — the exact
    failure `Receipt.fleet_wide` was declared to prevent."""
    from genios_engine.platform.org_readiness_sql import COUNT_SQL

    for name, sql in COUNT_SQL.items():
        assert ":org" in sql, name


def test_the_fleet_wide_variants_are_separate_constants_not_string_surgery():
    """⛔ A filter removed by `.replace()` is a filter nobody can see was removed."""
    from genios_engine.platform.org_readiness_sql import COUNT_SQL, COUNT_SQL_FLEET

    assert set(COUNT_SQL) == set(COUNT_SQL_FLEET)
    for sql in COUNT_SQL_FLEET.values():
        assert ":org" not in sql


def test_the_two_new_receipts_exist_and_the_channel_one_was_not_duplicated():
    """⛔ A channel receipt already existed over the same table. Two receipts answering one question
    disagree the first time somebody tunes one."""
    from genios_engine.platform import receipts as R

    claims = [r.claim for r in R.receipts("org_1")]
    assert "the tenant has at least one active seat" in claims
    assert "at least one seat has a manager" in claims
    assert sum("channel" in c for c in claims) == 1


def test_the_new_receipts_are_never_fleet_wide():
    """Every one of them is a question about a TENANT."""
    from genios_engine.platform import receipts as R

    for r in R.receipts("org_1"):
        if r.claim in ("the tenant has at least one active seat", "at least one seat has a manager"):
            assert r.fleet_wide is False
