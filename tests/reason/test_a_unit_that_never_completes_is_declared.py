r"""`R.U03` · the third kind of silence — a unit that runs and never completes.

⛔ WHAT WAS INVISIBLE. `reason/unit_health` declared two grains and a receipt read each:
`DeclaredSilence` (a unit **completes** and computes nothing) and `UnwrittenFact` (a bound fact path
nothing writes). Measured on production 2026-10-01, one unit escaped both:

    core.relationship    929 runs    708 insufficient_context    221 skipped    0 COMPLETED
    core.policy          165 runs      0                         165 skipped    0 COMPLETED

`_UNDECLARED_SILENT_UNITS_SQL` filters `where status = 'completed'` and groups by unit, so a unit
with zero completed rows is **not a row with a low share — it is not a row.** The silence receipt
was green while `core.relationship` had produced nothing in 929 attempts.

⛔ AND THE FACT WAS ALREADY WRITTEN DOWN TWICE, IN PROSE. Once in `receipts.py`, and once inside
`DECLARED_SILENT["core.impact"]`'s own reason text — *"core.relationship has NEVER completed — 708
insufficient_context, 221 skipped"* — as an argument for a **different** unit's entry. It had no
entry of its own, so nothing could read it.

> **A unit that never completes is not a quiet unit; it is an absent one, and a question asked only
> of completions cannot see it.**

⛔ WHY `core.policy` IS DELIBERATELY NOT DECLARED HERE. It also has zero completions, and it is
already accounted for at the grain that names the real mover: all four fact paths it binds are in
`DECLARED_UNWRITTEN`. `receipts.py` says it in one line — *"it is not failing, it is correctly
refusing to run on nothing, forever."* A second declaration of one fact is the drift this module
exists to prevent, so the exemption is **derived from the roster**, never listed.
"""
from __future__ import annotations

import re

import pytest

from genios_engine.platform import receipts as R
from genios_engine.reason import unit_health as U

CLAIM = "every unit that runs and never completes is a declared one"


def _receipt():
    found = [r for r in R.receipts(None) if r.claim == CLAIM]
    assert len(found) == 1, f"expected exactly one receipt asking this, got {len(found)}"
    return found[0]


# --------------------------------------------------------------------------------------------
# the one clause that is the whole difference
# --------------------------------------------------------------------------------------------

def test_the_query_does_not_filter_by_completed_status() -> None:
    """⛔ That filter is the defect this receipt exists for. If it reappears, the receipt becomes a
    duplicate of the silence receipt and the gap closes over again."""
    sql = R._UNDECLARED_NEVER_COMPLETED_SQL(None).lower()
    assert "where status" not in sql, (
        "a WHERE on status would hide exactly the units this receipt is for")
    assert "sum(case when status = 'completed'" in sql, (
        "completions must be counted inside the aggregate, not filtered before it")


def test_a_unit_with_no_runs_at_all_is_a_different_fact() -> None:
    """⛔ `having count(*) > 0` is not redundant. `core.signal_composition` has **zero** runs
    because `DEAL_HEALTH_V1` has never been swept — that is ALARM A2, a roster activation, and a
    ratio would make 0/0 and 0/929 the same number."""
    assert "having count(*) > 0" in R._UNDECLARED_NEVER_COMPLETED_SQL(None)
    assert "core.signal_composition" not in U.DECLARED_NEVER_COMPLETED_IDS
    # and the Python predicate agrees with the SQL
    assert U.undeclared_never_completed({"core.signal_composition": 0}, {}) == ()


def test_the_receipt_was_not_made_to_pass() -> None:
    expect = _receipt().expect
    assert expect(0) is True
    assert expect(1) is False, "one undeclared never-completing unit must fail the receipt"


def test_the_org_filter_still_applies() -> None:
    assert "org_id" in R._UNDECLARED_NEVER_COMPLETED_SQL("org_abc")
    assert _receipt().fleet_wide is False
    assert _receipt().layer == "L2"


# --------------------------------------------------------------------------------------------
# the exemption is derived, not listed
# --------------------------------------------------------------------------------------------

def test_core_policy_is_excused_by_its_inputs_and_not_by_a_second_declaration() -> None:
    """The specific shape of drift this module exists to prevent: one fact in two places."""
    assert "core.policy" not in U.DECLARED_NEVER_COMPLETED_IDS, (
        "core.policy is declared through DECLARED_UNWRITTEN; declaring it again here would make "
        "one fact need two edits to stay true")
    assert "core.policy" in U.starved_by_declared_paths()


def test_the_exemption_is_computed_from_the_roster() -> None:
    """Every excused unit must bind at least one path, and all of its paths must be declared
    unwritten. A unit that binds nothing is not starved — it simply reads nothing."""
    bound: dict[str, set[str]] = {}
    for path, roles in U.roster_fact_paths().items():
        for role in roles:
            bound.setdefault(role.rsplit(".", 1)[0], set()).add(path)
    for unit in U.starved_by_declared_paths():
        paths = bound.get(unit, set())
        assert paths, f"{unit} is excused but binds no roster path"
        assert paths <= set(U.DECLARED_UNWRITTEN_PATHS), (
            f"{unit} is excused while {sorted(paths - set(U.DECLARED_UNWRITTEN_PATHS))} is written")


def test_both_production_units_are_accounted_for_and_a_new_one_would_not_be() -> None:
    runs = {"core.relationship": 929, "core.policy": 165, "core.cost": 1973}
    completions = {"core.cost": 1973}
    assert U.undeclared_never_completed(runs, completions) == ()
    assert U.undeclared_never_completed({**runs, "core.invented": 400}, completions) \
        == ("core.invented",)


def test_every_excused_id_is_a_unit_id() -> None:
    """The ids are interpolated into SQL, so their shape is checked before they get there."""
    for unit in U.DECLARED_NEVER_COMPLETED_IDS | U.starved_by_declared_paths():
        assert re.fullmatch(r"[a-z][a-z0-9_.]+", unit), unit


# --------------------------------------------------------------------------------------------
# the declaration itself
# --------------------------------------------------------------------------------------------

def test_the_declaration_carries_everything_a_reader_needs() -> None:
    d = U.DECLARED_NEVER_COMPLETED["core.relationship"]
    assert d.runs == 929, "the measured run count, audited on production 2026-10-01"
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", d.measured_on)
    assert "Harsh" in d.mover, "a declared absence with no named mover cannot be cleared"
    assert "deal.status" in d.reason, "the reason must name the cause, not the symptom"


def test_the_reason_does_not_contradict_the_sibling_declaration() -> None:
    """⛔ `DECLARED_SILENT["core.impact"]`'s reason already asserts that core.relationship never
    completes. Two statements of one fact in one module must agree, or the module is the drift."""
    impact = U.DECLARED_SILENT["core.impact"].reason
    assert "core.relationship" in impact and "deal.status" in impact
    assert "deal.status" in U.DECLARED_NEVER_COMPLETED["core.relationship"].reason


@pytest.mark.parametrize("field", ["reason", "mover", "measured_on"])
def test_an_incomplete_declaration_is_refused(field: str) -> None:
    kwargs = dict(reason="r", mover="m", runs=1, measured_on="2026-10-01")
    kwargs[field] = "   "
    with pytest.raises(ValueError):
        U.NeverCompleted(**kwargs)


@pytest.mark.parametrize("runs", [0, -1])
def test_a_unit_that_never_ran_cannot_be_filed_here(runs: int) -> None:
    """Refused at construction, so the 0-runs case cannot be mis-filed as a silence."""
    with pytest.raises(ValueError, match="positive"):
        U.NeverCompleted(reason="r", mover="m", runs=runs, measured_on="2026-10-01")


def test_a_unit_that_starts_completing_is_reported_as_drift() -> None:
    """The good direction, and still a thing to go and delete."""
    assert U.completed_after_all({"core.relationship": 0}) == ()
    assert U.completed_after_all({"core.relationship": 5}) == ("core.relationship",)


def test_the_declaration_is_immutable() -> None:
    with pytest.raises(TypeError):
        U.DECLARED_NEVER_COMPLETED["invented"] = U.DECLARED_NEVER_COMPLETED["core.relationship"]
