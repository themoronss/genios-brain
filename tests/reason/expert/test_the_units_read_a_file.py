"""STEP-13b · the Reasoning Expertise of a file — the twelve situation-level units, in shadow.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… .venv/bin/python -m pytest -q tests/reason/expert/test_the_units_read_a_file.py

Tree `yc2_w27_s13b · M37.C2.L-logic.V1.U03`. `reason/expert/file_units.units_for` runs the twelve
situation-level units (Context, Timeline, Dependency, Constraint, Risk, Opportunity, Impact,
Priority, Confidence, Temporal, Relationship, SignalComposition) over a file's own `ContextSnapshot`
— no admitted L2 situation needed, no decision, nothing persisted, no model. `units_for_node` is the
one DB-touching wrapper: `reason/runner._load_context`, as the module docstring names.
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

import pytest

from genios_engine.contracts import engine_read as E
from genios_engine.contracts.expert_review import LEVELS
from genios_engine.contracts.reasoning import (ContextSnapshot, EvidenceRef, ReasonerResult,
                                               ResultStatus)
from genios_engine.reason.expert import file_units as FU

pytestmark = pytest.mark.unit

NOW = datetime(2026, 9, 20, 12, 0, tzinfo=timezone.utc)
PAST = NOW - timedelta(days=3)


def _ctx(facts=None, **kw) -> ContextSnapshot:
    return ContextSnapshot(org_id="org_x", graph_version=1, root_entity_id="node_1",
                           root_entity_type="thread", evaluation_time=NOW, selector_version="v1",
                           facts=facts or {}, **kw)


def _fact(value) -> dict:
    return {"value": value}


# ── the roster: every unit named once, in an order every dependency respects ──────────────────

def test_every_situation_level_unit_is_named_once():
    read = FU.units_for(_ctx())
    refs = [line.ref for line in read.lines]
    assert refs == [f"ru:{u}" for u in FU.RUN_ORDER] + ["ru:not_run"]
    assert len(refs) == len(set(refs)), "one line per unit"


def test_the_run_order_respects_every_dependency():
    """Each unit's own roster dependencies (where it has a roster entry) appear earlier."""
    from genios_engine.reason.adapters.expertise import _ROSTER
    position = {unit_id: i for i, unit_id in enumerate(FU.RUN_ORDER)}
    for roster_unit in _ROSTER:
        if roster_unit.unit_id not in position:
            continue
        for dep in roster_unit.dependencies:
            if dep in position:
                assert position[dep] < position[roster_unit.unit_id], (
                    f"{roster_unit.unit_id} depends on {dep} but runs no later")


def test_the_nine_candidate_level_units_are_named_once_not_run():
    read = FU.units_for(_ctx())
    line = read.by_ref["ru:not_run"]
    assert all(unit_id in line.words for unit_id in FU.NOT_RUN)
    assert len(FU.NOT_RUN) == 9
    assert set(FU.NOT_RUN).isdisjoint(FU.RUN_ORDER), "no unit is both run and named not-run"


def test_a_unit_line_is_measured_never_reviewed():
    for line in FU.units_for(_ctx()).lines:
        assert line.family == E.UNIT and line.origin == "measured"
        assert line.reviewed is False and line.label is None


# ── completed, insufficient context, and a unit's own fault ───────────────────────────────────

def test_a_unit_with_nothing_essential_present_reads_as_insufficient_context_before_it_runs():
    read = FU.units_for(_ctx())  # no facts at all
    assert "insufficient context" in read.by_ref["ru:core.timeline"].words
    assert "timeline_fields" in read.by_ref["ru:core.timeline"].words
    assert "insufficient context" in read.by_ref["ru:core.opportunity"].words
    assert "insufficient context" in read.by_ref["ru:core.temporal"].words
    assert "insufficient context" in read.by_ref["ru:core.signal_composition"].words
    assert "signals.open" in read.by_ref["ru:core.signal_composition"].words


def test_an_always_unit_runs_with_no_facts_at_all():
    """Context, Dependency, Constraint, Risk, Impact, Priority, Confidence never drop for want
    of a fact (the roster's own `always` rationale) — they complete even on an empty file."""
    read = FU.units_for(_ctx())
    for unit_id in ("core.context", "core.dependency", "core.constraint", "core.risk",
                   "core.impact", "core.priority", "core.confidence"):
        line = read.by_ref[f"ru:{unit_id}"]
        assert "insufficient context" not in line.words and "failed" not in line.words, line.words


def test_a_rich_file_completes_every_situation_level_unit():
    facts = {
        "thread.ball_in_court": _fact("us"), "deal.status": _fact("open"),
        "derived.engagement": _fact(7000), "thread.last_inbound": _fact(PAST.isoformat()),
        "thread.last_outbound": _fact(PAST.isoformat()), "commitment.due_at": _fact(PAST.isoformat()),
        "deal.owner": _fact("arjun"), "deal.value": _fact(500_000),
        "signals.open": [{"signal_id": "s1", "reason_code": "r1", "reasoning_run_id": "run1"},
                         {"signal_id": "s2", "reason_code": "r2", "reasoning_run_id": "run2"}],
    }
    read = FU.units_for(_ctx(facts))
    for unit_id in FU.RUN_ORDER:
        line = read.by_ref[f"ru:{unit_id}"]
        assert "insufficient context" not in line.words and "failed" not in line.words, (
            f"{unit_id}: {line.words}")


def test_a_units_own_fault_costs_only_its_line(monkeypatch):
    def _boom(self, request, prior):
        raise ValueError("a unit's own bug")
    monkeypatch.setattr(FU._UNITS["core.risk"].__class__, "evaluate", _boom)
    read = FU.units_for(_ctx())
    assert read.by_ref["ru:core.risk"].words == "failed — ValueError"
    # every OTHER unit still ran — one unit's fault did not take the file's read down with it
    assert "failed" not in read.by_ref["ru:core.context"].words
    assert "failed" not in read.by_ref["ru:core.confidence"].words


# ── levels, not scores ─────────────────────────────────────────────────────────────────────────

def test_a_level_is_one_of_the_three_words_never_a_number():
    read = FU.units_for(_ctx({"thread.ball_in_court": _fact("us"), "deal.status": _fact("open")}))
    for line in read.lines:
        if line.ref == "ru:not_run":
            continue  # names the nine unrun units and a decision id (06 D-s13b-3) — no metric here
        for token in line.words.split("; "):
            if ":" in token and token.split(":")[0].strip() in (
                    "completeness", "risk", "confidence", "impact", "corroboration"):
                level = token.split(":", 1)[1].strip()
                assert level in LEVELS, f"{token!r} is not a level"
        assert not any(ch.isdigit() for ch in line.words), (
            f"a unit's own line carries a digit: {line.words!r}")


def test_the_three_bands_are_low_medium_high_at_simple_thirds():
    assert FU._level(0) == "low" and FU._level(3_333) == "low"
    assert FU._level(3_334) == "medium" and FU._level(6_666) == "medium"
    assert FU._level(6_667) == "high" and FU._level(10_000) == "high"


# ── findings cite the evidence they rest on ────────────────────────────────────────────────────

def test_a_completed_line_cites_the_evidence_its_findings_rest_on():
    evidence = (EvidenceRef(evidence_id="ev1", field="thread.ball_in_court", value="us"),
               EvidenceRef(evidence_id="ev2", field="deal.status", value="open"))
    read = FU.units_for(_ctx({"thread.ball_in_court": _fact("us"), "deal.status": _fact("open")},
                             evidence=evidence))
    assert read.by_ref["ru:core.context"].cites == ("ev1", "ev2")
    assert read.by_ref["ru:core.relationship"].cites == ("ev2",)


def test_a_line_with_no_finding_cites_nothing():
    read = FU.units_for(_ctx())
    assert read.by_ref["ru:core.constraint"].cites == ()


# ── the wiring is real: priority and confidence read risk's own prior result ──────────────────

def test_priority_reads_temporal_s_own_urgency_not_a_fixed_default():
    """`core.priority`'s declared source is `core.temporal` (`priority.py`'s own worked example:
    `core.risk` publishes `risk_bp`, never `urgency_bp`, so sourcing from it would silently read
    the plugin's neutral default every time — verified against the running code before this was
    written). With no temporal reading at all, priority falls back to the loudest prior urgency
    (here, 0 — nothing else publishes one); with a long-silent, fully-disengaged thread, temporal's
    own urgency is pinned at the ceiling, and priority carries that forward."""
    thin = FU.units_for(_ctx())
    stale = {"derived.engagement": _fact(0), "thread.last_inbound": _fact(
        (NOW - timedelta(hours=200)).isoformat())}
    urgent = FU.units_for(_ctx(stale))
    assert "urgency: low" in thin.by_ref["ru:core.priority"].words
    assert "urgency: high" in urgent.by_ref["ru:core.priority"].words, (
        urgent.by_ref["ru:core.priority"].words)


def test_matched_is_shown_only_when_the_unit_states_one():
    """`core.context` never judges (`matched` is always `None` by design); `core.relationship`
    does, and says which way."""
    facts = {"thread.ball_in_court": _fact("us"), "deal.status": _fact("open")}
    read = FU.units_for(_ctx(facts))
    assert "matched:" not in read.by_ref["ru:core.context"].words
    assert "matched: yes" in read.by_ref["ru:core.relationship"].words


def test_a_skipped_result_reads_as_skipped():
    """No situation-level unit returns SKIPPED against a bare `ContextSnapshot` today — this
    holds `_result_line`'s own rendering of that status directly, as `ReasonerResult` allows it."""
    result = ReasonerResult("core.context", "1.0.0", ResultStatus.SKIPPED,
                            reason_codes=("already_decided",))
    line = FU._result_line("core.context", result)
    assert line.words == "skipped — already_decided"


def test_every_always_unit_declares_no_gates_so_required_fields_never_differs():
    """The `always`/gated ternary in `_manifest` picks between `()` and `_declared_field(...)`;
    for every `always` unit in today's roster `_declared_field` already returns `()` on its own
    (none of the seven declares a `gates_on` role), so the ternary's direction is unobservable —
    verified here directly rather than left as an unexplained mutation survivor. A roster change
    that gives one of them a gate would fail this first, which is the point of pinning it."""
    from genios_engine.reason.adapters.expertise import _ROSTER
    roster_by_id = {u.unit_id: u for u in _ROSTER}
    for unit_id in FU.RUN_ORDER:
        roster = roster_by_id.get(unit_id)
        if roster is not None and roster.always:
            assert roster.gates_on == (), (
                f"{unit_id} now gates on something — the ternary needs a real test, not this one")


def test_sanitized_facts_leaves_a_record_with_no_confidence_key_untouched():
    out = FU._sanitized_facts({"a": {"value": 1}, "b": "bare_scalar"})
    assert out["a"] == {"value": 1} and out["b"] == "bare_scalar"


def test_sanitized_facts_converts_a_float_confidence_to_basis_points():
    out = FU._sanitized_facts({"x": {"value": 1, "confidence": 0.9}})
    assert out["x"] == {"value": 1, "confidence_bp": 9_000}


def test_sanitized_facts_passes_through_a_non_float_confidence():
    out = FU._sanitized_facts({"x": {"value": 1, "confidence": 5_000}})
    assert out["x"] == {"value": 1, "confidence_bp": 5_000}


def test_sanitized_facts_drops_a_none_confidence_rather_than_inventing_one():
    out = FU._sanitized_facts({"x": {"value": 1, "confidence": None}})
    assert out["x"] == {"value": 1}


# ── version and purity ─────────────────────────────────────────────────────────────────────────

def test_the_same_file_reads_the_same_units():
    facts = {"thread.ball_in_court": _fact("us")}
    one, two = FU.units_for(_ctx(facts)), FU.units_for(_ctx(facts))
    assert one.version == two.version and one.version.startswith("eng-")


def test_units_for_is_pure():
    """No database, no clock, no model."""
    import ast
    from pathlib import Path
    tree = ast.parse(Path(FU.__file__).read_text())
    impure = {"units_for_node", "_sanitized_facts"}
    excluded = {node for top in ast.walk(tree) if isinstance(top, ast.FunctionDef)
               and top.name in impure for node in ast.walk(top)}
    calls = {node.func.attr for node in ast.walk(tree)
            if node not in excluded and isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)}
    assert not calls & {"now", "utcnow", "today", "execute", "messages", "create"}, calls


# ── the one DB-touching wrapper ─────────────────────────────────────────────────────────────────

ORG = "org_file_units_test"


def _wipe(c) -> None:
    from sqlalchemy import text
    c.execute(text("delete from graph_facts where org_id = :o"), {"o": ORG})
    c.execute(text("delete from graph_nodes where org_id = :o"), {"o": ORG})
    c.execute(text("delete from orgs where id = :o"), {"o": ORG})


@pytest.fixture
def db():
    url = os.environ.get("GENIOS_TEST_DATABASE_URL")
    if not url:
        pytest.skip("GENIOS_TEST_DATABASE_URL not set — units_for_node reads Postgres")
    from genios_engine.context.graph_store import GraphStore
    store = GraphStore(url)
    from sqlalchemy import text
    with store.engine.begin() as c:
        _wipe(c)
        c.execute(text("insert into orgs (id, name) values (:o, 'Test')"), {"o": ORG})
    yield store
    with store.engine.begin() as c:
        _wipe(c)


@pytest.mark.pg
def test_units_for_node_reads_the_graph_and_sanitizes_the_float_confidence(db):
    with db.engine.begin() as c:
        node = db.find_or_create_node(c, org_id=ORG, node_type="thread", canonical_key="t1",
                                      display_name="Thread 1", event_id="e1")
        db.write_fact(c, org_id=ORG, subject_node_id=node, field="thread.ball_in_court",
                      value="us", value_type="string", confidence=0.9, occurred_at=NOW,
                      event_id="e1", evidence={}, source="gmail")
        db.write_fact(c, org_id=ORG, subject_node_id=node, field="deal.status",
                      value="open", value_type="string", confidence=0.9, occurred_at=NOW,
                      event_id="e1", evidence={}, source="gmail")
    read = FU.units_for_node(db, ORG, node, "thread", evaluation_time=NOW)
    assert "insufficient context" not in read.by_ref["ru:core.relationship"].words
    assert "linked_open_deal" in read.by_ref["ru:core.relationship"].words


@pytest.mark.pg
def test_units_for_node_on_an_unknown_node_reads_insufficient_context_not_a_crash(db):
    read = FU.units_for_node(db, ORG, "node_does_not_exist", "thread", evaluation_time=NOW)
    assert read.by_ref["ru:core.timeline"].words.startswith("insufficient context")
