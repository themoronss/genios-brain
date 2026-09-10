"""REASON-01 · REASON-02 — the reasoning angles and the facts they bind to were a sales
vocabulary in a Python tuple.

    pytest tests/reason/adapters/test_reasoning_is_not_only_sales.py -q

`_OWNER` is `("deal.owner",)`. `_DEADLINES` is `("commitment.due_at", "deal.close_date")`.
`_RELATIONSHIP_STATUS` is `("deal.status",)`. A support desk's owner is `ticket.assignee` and
its deadline is `sla.breach_at`; a clinic's are `episode.clinician` and
`appointment.starts_at`. None of those appears in any tuple, so `_bind_role` returned None, the
unit's essential role was unbound, and the unit was DECLINED with a receipt reading "no
declared field in this expertise" — true, and it reads as the corpus's fault rather than the
vocabulary's.

And the set of angles itself was a tuple plus a class import list: adding one meant a
`ReasoningUnit` subclass, a registry entry and a `_RosterUnit` row — three Python edits and a
deploy, per angle, per customer.
"""

from __future__ import annotations

import pathlib
import textwrap

import pytest

from genios_engine.reason.adapters.expertise import (
    _ROSTER,
    _authored_roster,
    _bind_role,
    authored_role_paths,
)

pytestmark = pytest.mark.unit


@pytest.fixture
def clinic(tmp_path, monkeypatch):
    """A corpus with one domain, so nothing here reads the real one."""
    def write(body: str):
        root = tmp_path / "Clinic Expertise"
        root.mkdir(exist_ok=True)
        (root / "domain.yaml").write_text(textwrap.dedent(
            "identity: {id: clinic, name: Clinic, version: 0.1.0}\n") + textwrap.dedent(body))
        monkeypatch.setattr("genios_engine.platform.corpus.corpus_root", lambda: tmp_path)
    return write


# =============================================================================================
# REASON-02 — the facts a role may bind to.
# =============================================================================================
def test_a_domain_that_declares_nothing_keeps_the_shipped_paths():
    assert authored_role_paths("sales") == {}


def test_a_desk_can_name_its_own_owner_and_deadline(clinic):
    clinic("""
        roles:
          owner_field:    [ticket.assignee]
          deadline_field: [sla.breach_at]
    """)

    got = authored_role_paths("clinic")

    assert got["owner_field"] == ("ticket.assignee",)
    assert got["deadline_field"] == ("sla.breach_at",)


def test_an_authored_path_is_preferred_over_the_sales_one():
    """A domain that names its own owner means it."""
    bound = _bind_role(("ticket.assignee", "deal.owner"),
                       available=frozenset({"ticket.assignee", "deal.owner"}),
                       present=frozenset({"ticket.assignee", "deal.owner"}))

    assert bound == "ticket.assignee"


def test_the_two_filters_are_unchanged():
    """A path must still be one the EXPERTISE reads, and a path the SITUATION carries still
    wins — so an authored name that nothing writes binds nothing, exactly as an unwritten
    shipped name does."""
    assert _bind_role(("ticket.assignee",), available=frozenset(), present=frozenset()) is None
    assert _bind_role(("a", "b"), available=frozenset({"a", "b"}),
                      present=frozenset({"b"})) == "b"


def test_an_empty_declaration_is_not_a_binding(clinic):
    clinic("roles:\n  owner_field: []\n")

    assert "owner_field" not in authored_role_paths("clinic")


# =============================================================================================
# REASON-01 — which angles run, and how long they may take.
# =============================================================================================
def test_a_domain_that_declares_nothing_gets_the_shipped_roster():
    assert _authored_roster("sales") == _ROSTER
    assert _authored_roster("") is _ROSTER


def test_a_clinic_can_decline_an_angle_that_does_not_apply(clinic):
    """A clinic has no pipeline; declining `core.opportunity` on every situation is noise in
    every receipt."""
    clinic("reasoning:\n  - {unit: core.opportunity, enabled: false}\n")

    ids = {u.unit_id for u in _authored_roster("clinic")}

    assert "core.opportunity" not in ids
    assert len(ids) == len(_ROSTER) - 1


def test_a_domain_can_buy_more_time_for_a_deep_chain(clinic):
    clinic("reasoning:\n  - {unit: core.dependency, latency_budget_ms: 80}\n")

    by_id = {u.unit_id: u for u in _authored_roster("clinic")}

    assert by_id["core.dependency"].latency_budget_ms == 80


def test_a_required_unit_cannot_be_switched_off(clinic):
    """A plan that skips validation hides a missing prerequisite behind a confident answer —
    the orchestrator's own failure table calls that dangerous."""
    clinic("reasoning:\n  - {unit: core.context, enabled: false}\n")

    assert "core.context" in {u.unit_id for u in _authored_roster("clinic")}


def test_a_unit_that_does_not_exist_is_skipped(clinic):
    """There is no computation behind the name; scheduling it would be scheduling nothing."""
    clinic("reasoning:\n  - {unit: core.astrology, latency_budget_ms: 10}\n")

    assert _authored_roster("clinic") == _ROSTER


@pytest.mark.parametrize("budget", [0, -5, "soon", None])
def test_a_budget_that_is_not_a_positive_number_is_ignored(clinic, budget):
    """Zero is not "fast", it is "never runs" — and a domain that wanted a unit off has
    `enabled: false` to say so plainly."""
    clinic(f"reasoning:\n  - {{unit: core.dependency, latency_budget_ms: {budget}}}\n")

    by_id = {u.unit_id: u for u in _authored_roster("clinic")}
    shipped = {u.unit_id: u for u in _ROSTER}

    assert by_id["core.dependency"].latency_budget_ms == \
        shipped["core.dependency"].latency_budget_ms


def test_an_essential_role_the_unit_does_not_have_is_refused(clinic):
    """Essential against a key that can never be bound is a unit that never runs and never
    says why."""
    clinic("reasoning:\n  - {unit: core.dependency, essential: [nonexistent_role]}\n")

    by_id = {u.unit_id: u for u in _authored_roster("clinic")}
    shipped = {u.unit_id: u for u in _ROSTER}

    assert by_id["core.dependency"].essential == shipped["core.dependency"].essential


def test_an_essential_role_the_unit_does_have_is_taken(clinic):
    unit = next(u for u in _ROSTER if u.roles)
    key = unit.roles[0][0]
    clinic(f"reasoning:\n  - {{unit: {unit.unit_id}, essential: [{key}]}}\n")

    by_id = {u.unit_id: u for u in _authored_roster("clinic")}

    assert by_id[unit.unit_id].essential == (key,)


def test_the_shipped_roster_is_never_mutated(clinic):
    """`replace()` returns a new record; editing in place would leak one tenant's tuning into
    every other tenant in the process."""
    before = [(u.unit_id, u.latency_budget_ms) for u in _ROSTER]
    clinic("reasoning:\n  - {unit: core.dependency, latency_budget_ms: 999}\n")

    _authored_roster("clinic")

    assert [(u.unit_id, u.latency_budget_ms) for u in _ROSTER] == before
