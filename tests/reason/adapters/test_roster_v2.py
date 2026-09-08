"""Wave Z1 · the staged roster on the compiled lane (doc 01 C1, doc 02 U1/U2/U5).

`reason/adapters/expertise.py` scheduled six units — context, risk, constraint, priority,
confidence, planning — while twenty-two ids were registered and the Unit Selector that exists to
choose between them was enabled by no manifest anywhere. Twelve units had never run for any
tenant, and the two shim units five of them read as priors had never run either, so `core.risk`
observed one of the three things it was built to observe and correctly said nothing about the
other two.

Every test here compiles a REAL package out of the shipped corpus (`conftest.compile_situation`)
and reasons over it with the real registry. A fixture-built manifest would prove the plumbing and
not the unlock, and the unlock is the whole of this wave.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from genios_engine.contracts.reasoning import ExecutionMode, FailurePolicy, ReasonerSpec
from genios_engine.reason.adapters.expertise import (
    _ACTIVE_STATUSES,
    _GATE_FIELDS,
    _ROSTER,
    ROSTER_LATENCY_CEILING_MS,
    _default_dag,
    _roster_specs,
    expertise_capability_manifest,
)
from genios_engine.reason.adapters.native import reason_native_capability
from genios_engine.reason.engine import NodeContext
from genios_engine.reason.plan import (
    CONTEXT_AWARE_SELECTION_KEY,
    LATENCY_CEILING_KEY,
    ReasoningPlanner,
)
from genios_engine.reason.protocols import OrchestrationError
from genios_engine.reason.reasoners import default_registry

from .conftest import NOW, compile_situation

#: The twelve units doc 02 records as "never running anywhere", plus the two starved shims.
NEVER_RAN = ("core.alternative", "core.cost", "core.dependency", "core.impact",
             "core.opportunity", "core.policy", "core.recommendation", "core.relationship",
             "core.resource", "core.scheduling", "core.temporal", "core.timeline",
             "core.tradeoff", "core.validation")

#: A situation with money, dates, a status and an engagement reading — everything the roster's
#: roles can bind. The gate row (">= 12 distinct units producing Findings") is measured on this.
RICH_FACTS = {
    "deal.status": "open",
    "deal.value": 250_000,
    "derived.momentum": 0.25,
    "thread.last_inbound": "2026-07-01T09:00:00+00:00",
    "deal.last_inbound": "2026-07-01T09:00:00+00:00",
    "commitment.due_at": "2026-08-10T09:00:00+00:00",
    "meeting.start_at": "2026-08-20T09:00:00+00:00",
}

#: The same expertise against a situation that carries a status and nothing else: no money, no
#: dates, no engagement. Doc 02's "a moneyless one drops both with receipts".
THIN_FACTS = {"deal.status": "open", "thread.ball_in_court": "them"}


def _manifest(facts, *, roster_v2=True):
    compiled = compile_situation(facts=facts)
    return compiled, expertise_capability_manifest(
        compiled.package, root_entity_type="company", situation=compiled.situation,
        context=compiled.context, roster_v2=roster_v2)


def _execute(facts, manifest, *, edge_count=4):
    context = NodeContext(
        node_id="node_1", node_type="company",
        facts={name: {"value": value} for name, value in facts.items()},
        obs=[{"kind": "proposal_sent", "occurred_at": "2026-07-01T09:00:00+00:00"}],
        edge_count=edge_count, neighbor_obs=set(), neighbor_facts={})
    return reason_native_capability(
        org_id="org_weld", context=context, capability=manifest, evaluation_time=NOW,
        graph_version=1, config_snapshot_id=None, mode=ExecutionMode.SHADOW)


@pytest.fixture(scope="module")
def rich():
    compiled, manifest = _manifest(RICH_FACTS)
    return manifest, _execute(RICH_FACTS, manifest)


@pytest.fixture(scope="module")
def thin():
    compiled, manifest = _manifest(THIN_FACTS)
    return manifest, _execute(THIN_FACTS, manifest)


# ── the roster is awake ───────────────────────────────────────────────────────────────────────

def test_the_awake_roster_declares_the_family_that_had_never_run(rich):
    manifest, _ = rich
    declared = {spec.reasoner_id for spec in manifest.reasoners}

    assert declared.issuperset(NEVER_RAN), sorted(set(NEVER_RAN) - declared)
    assert len(declared) >= 17


def test_an_unactivated_tenant_reasons_through_exactly_the_six_unit_dag():
    """The gate is per tenant, so an unactivated one must be byte-identical to what it is today —
    including its content-addressed version, which moves if a single manifest byte does."""
    compiled, manifest = _manifest(RICH_FACTS, roster_v2=False)
    expected = _default_dag(manifest.required_fields,
                            compiled.package.metadata.get("authored_priority_bp"),
                            blocked_play_ids=tuple(
                                manifest.metadata["weld"]["blocked_play_ids"]))

    assert manifest.reasoners == expected
    assert [spec.reasoner_id for spec in manifest.reasoners] == [
        "core.context", "core.risk", "core.constraint", "core.priority", "core.confidence",
        "core.planning"]
    assert CONTEXT_AWARE_SELECTION_KEY not in manifest.metadata
    assert LATENCY_CEILING_KEY not in manifest.metadata
    assert "roster" not in manifest.metadata


def test_the_unit_selector_is_switched_on_and_the_run_declares_a_ceiling(rich):
    manifest, _ = rich

    assert manifest.metadata[CONTEXT_AWARE_SELECTION_KEY] is True
    assert manifest.metadata[LATENCY_CEILING_KEY] == ROSTER_LATENCY_CEILING_MS
    assert manifest.metadata["roster"]["sequential_budget_ms"] <= ROSTER_LATENCY_CEILING_MS


def test_twelve_or_more_distinct_units_publish_a_finding(rich):
    """Doc 02's group gate row, on a real compiled package. It read six before this wave, and
    three of those six were reading priors that never ran."""
    _, execution = rich
    emitting = {result.reasoner_id for result in execution.ordered_results if result.findings}

    assert len(emitting) >= 12, sorted(emitting)


def test_core_risk_finally_observes_the_two_things_it_was_blind_to(rich):
    """U2. `MomentumDecayPlugin` reads `core.temporal.drop_bp` and `RelationshipHealthPlugin`
    reads `core.relationship.coverage_bp`; neither prior was ever scheduled, so both plugins were
    silent by design on every compiled decision this product has made."""
    _, execution = rich
    risk = next(r for r in execution.ordered_results if r.reasoner_id == "core.risk")
    findings = {finding.finding_id for finding in risk.findings}

    assert "risk.momentum_decay" in findings
    assert "risk.relationship_health" in findings


def test_urgency_stops_being_the_permanent_neutral_midpoint(rich):
    """U5's ladder reaches the ranking. `core.priority` resolves max-wins across its priors, which
    it can only do when no `source_reasoner` is declared — the six-unit DAG declared `core.risk`,
    a unit that publishes no `urgency_bp`, so every compiled decision read exactly 5,000."""
    manifest, execution = rich
    priority = next(spec for spec in manifest.reasoners if spec.reasoner_id == "core.priority")
    result = next(r for r in execution.ordered_results if r.reasoner_id == "core.priority")

    assert "source_reasoner" not in priority.config
    assert result.metrics["urgency_bp"] != 5_000
    assert next(r for r in execution.ordered_results
                if r.reasoner_id == "core.timeline").metrics["urgency_bp"] > 0


def test_the_three_axis_tradeoff_reads_three_axes(rich):
    """The `core.effort` ghost emptied the cost axis for the life of the unit; the roster now
    schedules `core.cost` and names it as the source."""
    _, execution = rich
    tradeoff = next(r for r in execution.ordered_results if r.reasoner_id == "core.tradeoff")

    assert tradeoff.metrics["axis_count"] == 3


# ── every silence names itself ────────────────────────────────────────────────────────────────

def test_a_situation_that_cannot_feed_a_unit_drops_it_and_names_the_absent_field(thin):
    _, execution = thin
    skipped = {step.reasoner_id: step for step in execution.plan.skipped}

    assert skipped, "a status-only situation should not be able to feed the whole roster"
    for step in skipped.values():
        assert step.reason_code in {"no_declared_input_available", "dependency_not_scheduled"}
        assert step.missing_fields, f"{step.reasoner_id} was dropped without naming why"


def test_every_declared_unit_either_ran_or_carries_a_receipt(thin):
    """100%, which is the gate row. A unit that is neither scheduled nor receipted is the state
    this whole wave exists to make impossible."""
    manifest, execution = thin
    declared = {spec.reasoner_id for spec in manifest.reasoners}
    ran = {result.reasoner_id for result in execution.ordered_results}
    receipted = {step.reasoner_id for step in execution.plan.skipped}

    assert declared == ran | receipted
    assert not ran & receipted


def test_a_unit_this_expertise_cannot_feed_at_all_is_declined_with_its_candidates():
    """Two different questions, two different receipts: the manifest declines what this EXPERTISE
    never reads; the selector drops what this SITUATION cannot supply."""
    compiled = compile_situation()
    specs, receipt = _roster_specs(
        compiled.package, gate_fields=(), available=frozenset({"thread.ball_in_court"}),
        present=frozenset({"thread.ball_in_court"}), authored_priority_bp=None,
        blocked_play_ids=())
    declined = receipt["declined"]

    assert declined, "an expertise that reads one state field cannot feed the fact-bound units"
    for unit_id, row in declined.items():
        assert row["reason"] == "no_declared_field_in_this_expertise"
        assert row["candidates"], f"{unit_id} was declined without naming what it looked for"
    assert {spec.reasoner_id for spec in specs}.isdisjoint(declined)


def test_a_pruned_source_never_reaches_the_manifest_as_a_dangling_name():
    """A declined unit cannot be left behind as a `*_source` value: the registration check refuses
    exactly that, so the roster must prune the config key with the unit."""
    compiled = compile_situation()
    specs, receipt = _roster_specs(
        compiled.package, gate_fields=(), available=frozenset({"thread.ball_in_court"}),
        present=frozenset(), authored_priority_bp=None, blocked_play_ids=())
    declared = {spec.reasoner_id for spec in specs}

    for spec in specs:
        for key, value in spec.config.items():
            if str(key).endswith(("_source", "_reasoner")) and isinstance(value, str):
                assert value in declared, f"{spec.reasoner_id}.{key} points at a dropped unit"
                assert value in spec.dependencies
    assert receipt["pruned_sources"], "this thin expertise must prune something"


# ── determinism, budgets and the contract with readers ────────────────────────────────────────

def test_the_same_situation_plans_to_the_same_hash_byte_for_byte(rich):
    manifest, execution = rich
    request = execution.request

    first = ReasoningPlanner().plan(manifest, request)
    second = ReasoningPlanner().plan(manifest, request)

    assert first.plan_hash == second.plan_hash == execution.plan.plan_hash
    assert first.to_semantic_dict() == second.to_semantic_dict()


def test_the_same_package_and_slice_build_the_same_manifest_version():
    compiled = compile_situation(facts=RICH_FACTS)
    build = lambda: expertise_capability_manifest(          # noqa: E731 - two identical calls
        compiled.package, root_entity_type="company", situation=compiled.situation,
        context=compiled.context, roster_v2=True)

    assert build().version == build().version
    assert build().reasoners == build().reasoners


def test_the_latency_refusal_still_fires_when_a_units_declared_budget_outgrows_the_ceiling(rich):
    """PRESERVE HARD (doc 01 C2): tune the budgets, never the refusal."""
    manifest, _ = rich
    fattened = replace(manifest, reasoners=tuple(
        replace(spec, latency_budget_ms=200) for spec in manifest.reasoners))

    with pytest.raises(OrchestrationError, match="ceiling"):
        ReasoningPlanner().plan(fattened)


def test_no_unit_publishes_a_metric_it_did_not_declare(rich):
    """Invariant 11: the roster has a contract with its readers, and waking a unit must not rename
    or invent what it publishes. The framework enforces this per unit; this asserts it held across
    the whole woken roster on a real package."""
    _, execution = rich
    registry = default_registry()
    published = {}
    for reasoner_id, _version in sorted(registry._reasoners):        # noqa: SLF001
        instance = registry._reasoners[(reasoner_id, _version)]      # noqa: SLF001
        published[reasoner_id] = set(getattr(instance, "publishes", ()) or ())

    from genios_engine.reason.reasoners.confidence import UNDECLARED_METRICS

    for result in execution.ordered_results:
        declared = published.get(result.reasoner_id)
        if not declared:
            continue                       # a shim that declares no publishes tuple
        # `core.confidence` emits `completeness_bp` and says in its own source why it cannot
        # declare it. Named here rather than waved through, so the exception stays one unit wide.
        allowed = declared | (set(UNDECLARED_METRICS) if result.reasoner_id == "core.confidence"
                              else set())
        assert set(result.metrics).issubset(allowed), result.reasoner_id


def test_every_axis_source_the_roster_names_actually_publishes_the_metric_its_reader_reads(rich):
    """The ghost, at the metric level. `cost_source` read `effort_bp` from a unit that does not
    exist; naming a unit that exists but publishes something else would be the same silence.

    Asserted against what the units PUBLISHED on a real package rather than against a `publishes`
    tuple, because two of the six sources are shims that declare no tuple at all — and it is the
    reading, not the declaration, that the axis consumes."""
    from genios_engine.reason.reasoners.tradeoff_unit import AXIS_SOURCES

    _, execution = rich
    metrics = {result.reasoner_id: dict(result.metrics)
               for result in execution.ordered_results}
    configured = dict(next(unit for unit in _ROSTER if unit.unit_id == "core.tradeoff").sources)
    for key, default_unit, metric in AXIS_SOURCES:
        named = configured.get(key, default_unit)
        assert named in metrics, (key, named)
        assert metric in metrics[named], (key, named, metric)


def test_the_rosters_gate_field_list_agrees_with_the_unit_that_reads_it():
    from genios_engine.reason.reasoners.dependency_unit import DEFAULT_GATE_FIELDS

    assert _GATE_FIELDS == DEFAULT_GATE_FIELDS


def test_every_fact_path_the_roster_can_bind_comes_from_somewhere_real():
    """No invented vocabulary. A candidate is a fact Layer 2 registers, a path the shipped corpus
    names, or the documented default of the unit that reads it — never a name this adapter made
    up to keep a unit busy."""
    from genios_engine.context.analytic.cohort import CORE_COHORT_FACTS

    registered = {definition.name for definition in CORE_COHORT_FACTS}
    corpus = "\n".join(path.read_text(errors="ignore")
                       for path in Path("Domain Expertise").rglob("*.yaml"))
    units = "\n".join(path.read_text() for path in
                      Path("genios_engine/reason/reasoners").glob("*.py"))

    candidates = {name for unit in _ROSTER
                  for _key, paths in (unit.roles + unit.list_roles) for name in paths}
    candidates |= set(_ACTIVE_STATUSES)
    for name in sorted(candidates):
        assert (name in registered or name in corpus or f'"{name}"' in units), name


def test_the_roster_is_gated_on_the_activation_table_and_never_on_a_global_flag():
    """Law 5. `use_domain_compiler` is the standing counterexample: a config flag set in no
    environment left 152 capabilities dark."""
    import inspect

    from genios_engine.reason import domain_shadow

    source = inspect.getsource(domain_shadow.shadow_compile)
    assert "is_l4_activated(store.engine, org_id, FEATURE_ROSTER_V2)" in source
    assert "roster_v2=roster_v2" in source


def test_required_stays_the_four_the_plan_names_plus_what_was_required_before(rich):
    """Doc 02 U1 keeps context, constraint, priority and confidence REQUIRED. `core.risk` and
    `core.planning` were required on this lane before this wave and stay so — waking a roster may
    not quietly demote a unit whose failure already stopped a run."""
    manifest, _ = rich
    required = {spec.reasoner_id for spec in manifest.reasoners
                if spec.failure_policy == FailurePolicy.REQUIRED}

    assert required == {"core.context", "core.constraint", "core.priority", "core.confidence",
                        "core.risk", "core.planning"}
    assert all(isinstance(spec, ReasonerSpec) for spec in manifest.reasoners)
