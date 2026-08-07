"""Executable contract for Layer 4 · Part 1 — the execution plan.

The orchestrator must commit to a schedule *before* any unit observes the situation, and that
schedule must be inspectable rather than implied by a loop. These tests fix:

* the plan's order is exactly the order the trace records — one schedule, not two;
* stages express provable independence: a unit never shares a stage with anything it depends on;
* the plan is a pure function of the manifest, so it hashes stably and diffs meaningfully;
* budgets are declared arithmetic, never measurements — a capability that cannot afford its own
  units is refused at plan time, before a single reasoner runs;
* an unresolvable capability fails closed for the same reason;
* the plan is diagnostic: describing a run may never change the decision it describes.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone

import pytest

from genios_engine.contracts.reasoning import (
    CapabilityManifest,
    ContextSnapshot,
    FailurePolicy,
    Goal,
    PlayDefinition,
    ReasonerResult,
    ReasonerSpec,
    ReasoningRequest,
    ResultStatus,
)
from genios_engine.reason.orchestrator import ReasoningOrchestrator
from genios_engine.reason.plan import (
    LATENCY_CEILING_KEY,
    ExecutionPlan,
    ReasoningPlanner,
    plan_capability,
)
from genios_engine.reason.protocols import OrchestrationError
from genios_engine.reason.registry import ReasonerRegistry, UnknownReasoner

NOW = datetime(2026, 8, 6, 12, tzinfo=timezone.utc)


class _StubReasoner:
    def __init__(self, spec: ReasonerSpec, calls: list[str] | None = None):
        self._spec = spec
        self._calls = calls

    @property
    def spec(self) -> ReasonerSpec:
        return self._spec

    def evaluate(self, request, prior_results):
        del request, prior_results
        if self._calls is not None:
            self._calls.append(self.spec.reasoner_id)
        return ReasonerResult(
            reasoner_id=self._spec.reasoner_id,
            reasoner_version=self._spec.version,
            status=ResultStatus.COMPLETED,
            matched=True,
        )


def _capability(specs, *, metadata=None) -> CapabilityManifest:
    return CapabilityManifest(
        capability_id="sales.deal_cooling",
        version="1.0.0",
        domain="sales",
        root_entity_type="deal",
        goal=Goal("restore_momentum", "Restore healthy deal momentum"),
        reasoners=tuple(specs),
        plays=(PlayDefinition(
            play_id="restore_momentum",
            version="1",
            label="Restore Momentum",
            steps=("Prepare a grounded draft",),
        ),),
        policies=(),
        metadata=metadata or {},
    )


def _request(capability: CapabilityManifest) -> ReasoningRequest:
    context = ContextSnapshot(
        org_id="org_1",
        graph_version=17,
        root_entity_id="deal_1",
        root_entity_type="deal",
        evaluation_time=NOW,
        selector_version="selector.v1",
        facts={"deal.status": "open"},
    )
    return ReasoningRequest(
        org_id="org_1",
        capability=capability,
        context=context,
        evaluation_time=NOW,
        trigger_kind="email.received",
        config_snapshot_id="cfg_1",
    )


# A diamond: alpha feeds both beta and gamma, which both feed delta. beta and gamma are
# independent of each other and must therefore be schedulable together.
DIAMOND = (
    ReasonerSpec("delta", "1", dependencies=("beta", "gamma")),
    ReasonerSpec("gamma", "1", dependencies=("alpha",)),
    ReasonerSpec("beta", "1", dependencies=("alpha",)),
    ReasonerSpec("alpha", "1"),
)


def test_plan_order_is_the_order_the_trace_records():
    """One schedule, not two. A plan that disagreed with execution would make the trace fiction."""
    capability = _capability(DIAMOND)
    calls: list[str] = []
    registry = ReasonerRegistry(tuple(_StubReasoner(spec, calls) for spec in DIAMOND))

    execution = ReasoningOrchestrator(registry).execute(_request(capability))

    assert execution.plan is not None
    assert execution.plan.reasoner_plan == tuple(calls)
    assert execution.trace.reasoner_plan == execution.plan.reasoner_plan
    assert tuple(step.reasoner_id for step in execution.trace.steps) == tuple(calls)


def test_stages_group_only_provably_independent_units():
    plan = plan_capability(_capability(DIAMOND))
    stage_of = {step.reasoner_id: step.stage for step in plan.steps}

    assert stage_of == {"alpha": 0, "beta": 1, "gamma": 1, "delta": 2}
    assert plan.stage_count == 3
    assert [len(stage) for stage in plan.stages] == [1, 2, 1]
    assert plan.parallelizable is True
    for step in plan.steps:
        for dependency in step.dependencies:
            assert stage_of[dependency] < step.stage


def test_a_linear_capability_offers_no_concurrency():
    chain = (
        ReasonerSpec("second", "1", dependencies=("first",)),
        ReasonerSpec("first", "1"),
    )
    plan = plan_capability(_capability(chain))

    assert plan.parallelizable is False
    assert plan.stage_count == 2
    assert plan.critical_path_budget_ms == plan.sequential_budget_ms


def test_critical_path_budget_credits_only_real_independence():
    specs = (
        ReasonerSpec("alpha", "1", latency_budget_ms=40),
        ReasonerSpec("beta", "1", dependencies=("alpha",), latency_budget_ms=30),
        ReasonerSpec("gamma", "1", dependencies=("alpha",), latency_budget_ms=70),
        ReasonerSpec("delta", "1", dependencies=("beta", "gamma"), latency_budget_ms=10),
    )
    plan = plan_capability(_capability(specs))

    assert plan.sequential_budget_ms == 150            # what it costs today, one after another
    assert plan.critical_path_budget_ms == 120         # 40 + max(30, 70) + 10
    assert plan.critical_path_budget_ms <= plan.sequential_budget_ms


def test_stage_synchronised_cost_can_exceed_a_pure_dataflow_schedule():
    """An honest reading of the number: it prices waves, not a per-unit dataflow scheduler.

    `slow` blocks nothing, but a stage barrier still makes the next wave wait for it, so the
    reported figure (110) sits above the longest dependency path (100). Documented rather than
    silently treated as a lower bound.
    """
    specs = (
        ReasonerSpec("alpha", "1", latency_budget_ms=10),
        ReasonerSpec("slow", "1", latency_budget_ms=100),          # depends on nothing
        ReasonerSpec("gamma", "1", dependencies=("alpha",), latency_budget_ms=10),
    )
    plan = plan_capability(_capability(specs))

    assert plan.critical_path_budget_ms == 110         # max(10, 100) + 10
    assert plan.sequential_budget_ms == 120


def test_capability_that_cannot_afford_its_units_is_refused_before_any_of_them_run():
    """A declared ceiling is a deployment contract; breaking it is a build error, not a slow run."""
    specs = (ReasonerSpec("alpha", "1", latency_budget_ms=100),
             ReasonerSpec("beta", "1", latency_budget_ms=100))
    capability = _capability(specs, metadata={LATENCY_CEILING_KEY: 150})
    calls: list[str] = []
    registry = ReasonerRegistry(tuple(_StubReasoner(spec, calls) for spec in specs))

    with pytest.raises(OrchestrationError, match="150ms ceiling"):
        ReasoningOrchestrator(registry).execute(_request(capability))

    assert calls == []


def test_a_ceiling_the_units_fit_inside_is_accepted():
    specs = (ReasonerSpec("alpha", "1", latency_budget_ms=100),
             ReasonerSpec("beta", "1", latency_budget_ms=100))
    capability = _capability(specs, metadata={LATENCY_CEILING_KEY: 200})

    assert plan_capability(capability).sequential_budget_ms == 200


def test_a_non_integer_ceiling_is_a_manifest_fault():
    capability = _capability((ReasonerSpec("alpha", "1"),),
                             metadata={LATENCY_CEILING_KEY: 0})

    with pytest.raises(OrchestrationError, match="positive integer"):
        plan_capability(capability)


def test_missing_implementation_fails_closed_before_evaluation():
    """A partly-executable capability is a broken deployment, never a degraded decision."""
    specs = (ReasonerSpec("alpha", "1"), ReasonerSpec("absent", "1", dependencies=("alpha",)))
    calls: list[str] = []
    registry = ReasonerRegistry((_StubReasoner(specs[0], calls),))

    with pytest.raises(UnknownReasoner, match="absent"):
        ReasoningOrchestrator(registry).execute(_request(_capability(specs)))

    assert calls == []


def test_plan_is_a_pure_function_of_the_manifest():
    capability = _capability(DIAMOND)
    planner = ReasoningPlanner()

    first, second = planner.plan(capability), planner.plan(capability)

    assert first.plan_hash == second.plan_hash
    assert first == second


def test_relaxing_a_dependency_promotes_the_freed_unit_and_changes_the_plan():
    """Dropping an edge is not cosmetic: the freed unit becomes ready earlier and moves up a
    stage, and the plan hash changes so the difference is visible in an audit."""
    baseline = plan_capability(_capability(DIAMOND))
    rewired = plan_capability(_capability((
        ReasonerSpec("delta", "1", dependencies=("beta",)),      # gamma no longer gates delta
        ReasonerSpec("gamma", "1", dependencies=("alpha",)),
        ReasonerSpec("beta", "1", dependencies=("alpha",)),
        ReasonerSpec("alpha", "1"),
    )))

    assert baseline.plan_hash != rewired.plan_hash
    assert baseline.reasoner_plan == ("alpha", "beta", "gamma", "delta")
    assert rewired.reasoner_plan == ("alpha", "beta", "delta", "gamma")
    assert baseline.specs_by_id["delta"].stage == 2
    assert rewired.specs_by_id["delta"].stage == 2       # still behind beta
    assert rewired.specs_by_id["gamma"].stage == 1
    assert [len(stage) for stage in rewired.stages] == [1, 2, 1]


def test_plan_names_where_a_run_can_stop_early_and_where_it_only_degrades():
    specs = (
        ReasonerSpec("gate", "1", gating=True),
        ReasonerSpec("enrich", "1", dependencies=("gate",),
                     failure_policy=FailurePolicy.OPTIONAL),
        ReasonerSpec("core", "1", dependencies=("gate",)),
    )
    plan = plan_capability(_capability(specs))
    by_id = plan.specs_by_id

    assert tuple(step.reasoner_id for step in plan.gating_steps) == ("gate",)
    assert tuple(step.reasoner_id for step in plan.optional_steps) == ("enrich",)
    assert by_id["gate"].can_end_run is True
    assert by_id["core"].can_end_run is True             # required: its failure ends the run
    assert by_id["enrich"].can_end_run is False          # optional: degrades, never terminates
    assert by_id["enrich"].optional is True


def test_describing_a_run_cannot_change_it():
    """The plan is diagnostic. It is excluded from the semantic identity of the execution."""
    capability = _capability(DIAMOND)
    registry = ReasonerRegistry(tuple(_StubReasoner(spec) for spec in DIAMOND))
    orchestrator = ReasoningOrchestrator(registry)
    request = _request(capability)

    execution = orchestrator.execute(request)

    assert "plan" not in execution.to_semantic_dict()
    assert execution.semantic_hash == replace(execution, plan=None).semantic_hash
    assert "stage 1 (independent)" in execution.plan.describe()


def test_a_named_authority_the_capability_never_schedules_is_refused():
    capability = _capability((ReasonerSpec("core.confidence", "1"),),
                             metadata={"confidence_authority": "core.momentum"})

    with pytest.raises(OrchestrationError, match="never schedules"):
        plan_capability(capability)


def test_a_null_authority_is_refused_at_plan_time_not_after_the_units_run():
    """Present-but-null is a malformed manifest. The planner and the Decision Maker must agree."""
    capability = _capability((ReasonerSpec("core.confidence", "1"),),
                             metadata={"confidence_authority": None})

    with pytest.raises(OrchestrationError, match="must name a reasoner"):
        plan_capability(capability)


def test_planning_does_not_execute():
    capability = _capability(DIAMOND)
    calls: list[str] = []
    registry = ReasonerRegistry(tuple(_StubReasoner(spec, calls) for spec in DIAMOND))

    plan = ReasoningOrchestrator(registry).plan(_request(capability))

    assert isinstance(plan, ExecutionPlan)
    assert calls == []
