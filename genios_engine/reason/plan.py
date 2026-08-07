"""Layer 4 · Part 1 — the execution plan.

Before a single unit runs, the orchestrator commits to a plan: which units execute, in what order,
which of them are independent enough to run together, which are allowed to fail, which can end the
run early, and what the whole thing is permitted to cost.  The frozen architecture asks the
orchestrator exactly those questions, and this module is where they get answered *explicitly*.

Why a plan object rather than a loop that decides as it goes.  A plan can be inspected, diffed,
hashed, and rejected before any work happens.  When a capability is misconfigured — a unit
declaring a budget the capability cannot afford, a gate placed where nothing can act on it — that
is a deployment fault, and a deployment fault should surface at plan time as a refusal, not at
runtime as a slow, half-finished decision.  It also gives operators one artifact to read when they
ask "why did it run these seven units and not those three?".

Planning is pure.  It reads the capability manifest and nothing else: no clock, no database, no
context.  The same manifest always yields the same plan and the same `plan_hash`, which is what
lets the plan be cached per capability version and compared across deployments.

**Parallelism is described here, not performed here.**  `stage` marks units that share no
dependency path and could therefore execute concurrently.  Execution remains strictly sequential
in the deterministic order below, because concurrency that could interleave results would make the
trace depend on machine timing — and a decision that changes with CPU scheduling is not replayable.
Recording the stages now means the day a scheduler wants to fan out, the safe grouping is already
proven and hashed rather than guessed at.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any

from genios_engine.contracts.reasoning import CapabilityManifest, FailurePolicy, ReasonerSpec
from genios_engine.platform.canonical import semantic_hash

from .decision_maker import CONFIDENCE_AUTHORITY_KEY, PRIORITY_AUTHORITY_KEY
from .protocols import OrchestrationError
from .registry import ReasonerRegistry

PLANNER_VERSION = "1.0.0"

#: Optional capability ceiling, in milliseconds, for the whole sequential run.  Declared in
#: `CapabilityManifest.metadata` so the budget travels with the versioned manifest and is covered
#: by its content address, rather than living in deployment configuration that no audit can see.
LATENCY_CEILING_KEY = "latency_ceiling_ms"


@dataclass(frozen=True, slots=True)
class PlannedStep:
    """One unit's scheduled place in the run."""

    ordinal: int
    stage: int
    reasoner_id: str
    reasoner_version: str
    dependencies: tuple[str, ...]
    failure_policy: FailurePolicy
    gating: bool
    required_fields: tuple[str, ...]
    latency_budget_ms: int

    @property
    def optional(self) -> bool:
        """An optional unit degrades the decision's confidence; it never stops the run."""
        return self.failure_policy == FailurePolicy.OPTIONAL

    @property
    def can_end_run(self) -> bool:
        """True when this step alone can terminate the run before later steps evaluate.

        Gating units end it by deciding the situation does not apply; required units end it by
        failing.  Naming this explicitly is what lets an operator see, from the plan alone, where a
        run is able to stop early.
        """
        return self.gating or self.failure_policy == FailurePolicy.REQUIRED

    def to_semantic_dict(self) -> dict[str, Any]:
        return {"ordinal": self.ordinal, "stage": self.stage, "reasoner_id": self.reasoner_id,
                "reasoner_version": self.reasoner_version, "dependencies": self.dependencies,
                "failure_policy": self.failure_policy, "gating": self.gating,
                "required_fields": self.required_fields,
                "latency_budget_ms": self.latency_budget_ms}


@dataclass(frozen=True, slots=True)
class ExecutionPlan:
    """The orchestrator's committed answer to what will run, in what order, and at what cost."""

    capability_id: str
    capability_version: str
    planner_version: str
    steps: tuple[PlannedStep, ...]

    @property
    def reasoner_plan(self) -> tuple[str, ...]:
        """Execution order — the exact sequence the trace records."""
        return tuple(step.reasoner_id for step in self.steps)

    @property
    def specs_by_id(self) -> dict[str, PlannedStep]:
        return {step.reasoner_id: step for step in self.steps}

    @property
    def stage_count(self) -> int:
        return (max(step.stage for step in self.steps) + 1) if self.steps else 0

    @property
    def stages(self) -> tuple[tuple[PlannedStep, ...], ...]:
        """Units grouped into dependency-free waves — the safe concurrency envelope."""
        grouped: list[list[PlannedStep]] = [[] for _ in range(self.stage_count)]
        for step in self.steps:
            grouped[step.stage].append(step)
        return tuple(tuple(group) for group in grouped)

    @property
    def sequential_budget_ms(self) -> int:
        """Declared cost of the run as it actually executes today: one unit after another."""
        return sum(step.latency_budget_ms for step in self.steps)

    @property
    def critical_path_budget_ms(self) -> int:
        """Declared cost if each stage fanned out and stages ran back to back.

        This is the cost of *stage-synchronised* fan-out — every unit in a wave starts together and
        the next wave waits for the slowest. A fully dataflow scheduler, where a unit starts the
        moment its own dependencies finish, can sometimes beat this; it is never worse. Reported so
        a latency problem can be attributed correctly: when even this exceeds the ceiling,
        parallelism cannot rescue the capability and a unit has to get cheaper.
        """
        return sum(max(step.latency_budget_ms for step in stage) for stage in self.stages)

    @property
    def parallelizable(self) -> bool:
        return any(len(stage) > 1 for stage in self.stages)

    @property
    def gating_steps(self) -> tuple[PlannedStep, ...]:
        return tuple(step for step in self.steps if step.gating)

    @property
    def optional_steps(self) -> tuple[PlannedStep, ...]:
        return tuple(step for step in self.steps if step.optional)

    def to_semantic_dict(self) -> dict[str, Any]:
        return {"capability_id": self.capability_id,
                "capability_version": self.capability_version,
                "planner_version": self.planner_version,
                "steps": tuple(step.to_semantic_dict() for step in self.steps)}

    @property
    def plan_hash(self) -> str:
        return semantic_hash(self.to_semantic_dict())

    def describe(self) -> str:
        """Human-readable plan, for operators and for failure diagnostics."""
        lines = [f"{self.capability_id}@{self.capability_version} "
                 f"· {len(self.steps)} units · {self.stage_count} stages "
                 f"· budget {self.sequential_budget_ms}ms "
                 f"(critical path {self.critical_path_budget_ms}ms)"]
        for stage_index, stage in enumerate(self.stages):
            names = ", ".join(
                f"{step.reasoner_id}@{step.reasoner_version}"
                f"{' [gate]' if step.gating else ''}"
                f"{' [optional]' if step.optional else ''}"
                for step in stage)
            concurrency = " (independent)" if len(stage) > 1 else ""
            lines.append(f"  stage {stage_index}{concurrency}: {names}")
        return "\n".join(lines)


def _stage_index(specs_by_id: dict[str, ReasonerSpec], ordered: Sequence[ReasonerSpec]
                 ) -> dict[str, int]:
    """Depth of each unit in the dependency DAG.

    A unit sits one stage below its deepest dependency, so everything sharing a stage is provably
    independent.  The input is already topologically ordered, so a single forward pass suffices.
    """
    stages: dict[str, int] = {}
    for spec in ordered:
        dependencies = [stages[name] for name in spec.dependencies if name in stages]
        stages[spec.reasoner_id] = (max(dependencies) + 1) if dependencies else 0
    return stages


class ReasoningPlanner:
    """Turns a capability manifest into a validated, hashable execution plan."""

    def __init__(self, *, version: str = PLANNER_VERSION) -> None:
        self.version = str(version).strip()
        if not self.version:
            raise ValueError("planner version is required")

    def plan(self, capability: CapabilityManifest) -> ExecutionPlan:
        ordered = ReasonerRegistry.topological_order(capability.reasoners)
        specs_by_id = {spec.reasoner_id: spec for spec in ordered}
        stages = _stage_index(specs_by_id, ordered)
        steps = tuple(
            PlannedStep(
                ordinal=ordinal,
                stage=stages[spec.reasoner_id],
                reasoner_id=spec.reasoner_id,
                reasoner_version=spec.version,
                dependencies=spec.dependencies,
                failure_policy=spec.failure_policy,
                gating=spec.gating,
                required_fields=spec.required_fields,
                latency_budget_ms=spec.latency_budget_ms,
            )
            for ordinal, spec in enumerate(ordered, start=1)
        )
        plan = ExecutionPlan(
            capability_id=capability.capability_id,
            capability_version=capability.version,
            planner_version=self.version,
            steps=steps,
        )
        _validate_budget(plan, capability)
        _validate_metric_authorities(plan, capability)
        return plan

    def resolve(self, plan: ExecutionPlan, registry: ReasonerRegistry,
                capability: CapabilityManifest) -> Any:
        """Bind every planned step to its implementation before any of them run.

        A capability that can only partly execute is a broken deployment, so this refuses the whole
        plan rather than discovering the gap halfway through and emitting a decision built on the
        units that happened to exist.
        """
        by_id = {spec.reasoner_id: spec for spec in capability.reasoners}
        return MappingProxyType({
            step.reasoner_id: registry.get(by_id[step.reasoner_id]) for step in plan.steps})


def _validate_budget(plan: ExecutionPlan, capability: CapabilityManifest) -> None:
    """Refuse a plan that cannot meet a ceiling the capability itself declared.

    This is a static comparison of declared budgets, never a measurement: it must reach the same
    verdict on a laptop and in production, and it must not put a stopwatch anywhere near a
    decision.  Observed timings are telemetry; only declarations are allowed to block a run.
    """
    ceiling = capability.metadata.get(LATENCY_CEILING_KEY)
    if ceiling is None:
        return
    if isinstance(ceiling, bool) or not isinstance(ceiling, int) or ceiling <= 0:
        raise OrchestrationError(
            f"capability metadata {LATENCY_CEILING_KEY} must be a positive integer")
    if plan.sequential_budget_ms > ceiling:
        raise OrchestrationError(
            f"capability {capability.capability_id}@{capability.version} declares a "
            f"{ceiling}ms ceiling but its units declare {plan.sequential_budget_ms}ms")


def _validate_metric_authorities(plan: ExecutionPlan, capability: CapabilityManifest) -> None:
    """A capability may not appoint a metric authority that will never run.

    Confidence and priority each have exactly one publisher.  If a manifest names a unit that is
    not in its own DAG, the value would silently fall back to "last emitter wins" — the precise
    order-dependence the authority exists to remove — so the manifest is rejected instead.
    """
    scheduled = set(plan.reasoner_plan)
    for key in (CONFIDENCE_AUTHORITY_KEY, PRIORITY_AUTHORITY_KEY):
        if key not in capability.metadata:
            continue                       # the default authority is optional; absence is legal
        # Presence with a null value is a malformed manifest, not an omission — the Decision Maker
        # rejects it, so the planner must reject it too rather than deferring the same fault to
        # after every unit has already run.
        named = capability.metadata[key]
        if not isinstance(named, str) or not named.strip():
            raise OrchestrationError(f"capability metadata {key} must name a reasoner")
        if named.strip() not in scheduled:
            raise OrchestrationError(
                f"capability {capability.capability_id}@{capability.version} names "
                f"{key}={named.strip()}, which it never schedules")


def plan_capability(capability: CapabilityManifest, *,
                    planner: ReasoningPlanner | None = None) -> ExecutionPlan:
    """Convenience entry point for tooling that wants a plan without holding a planner."""
    return (planner or ReasoningPlanner()).plan(capability)


def describe_plans(capabilities: Iterable[CapabilityManifest]) -> str:
    planner = ReasoningPlanner()
    return "\n".join(planner.plan(capability).describe() for capability in capabilities)


__all__ = ["LATENCY_CEILING_KEY", "PLANNER_VERSION", "ExecutionPlan", "PlannedStep",
           "ReasoningPlanner", "describe_plans", "plan_capability"]
