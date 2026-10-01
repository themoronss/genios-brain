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

Planning is pure.  It reads the capability manifest, and — when the capability opts into
context-aware selection — the frozen context snapshot: no clock, no database, no network.  The
same inputs always yield the same plan and the same `plan_hash`, which is what lets a plan be
compared across deployments and what keeps selection itself replayable.

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
from .guards import required_missing
from .protocols import OrchestrationError
from .registry import ReasonerRegistry, validate_capability_sources

PLANNER_VERSION = "1.1.0"

#: Capability metadata opting into context-aware selection.  Off by default: with it absent the
#: plan is exactly the capability's declared unit list, which is what every existing capability
#: expects.  Turned on, an *optional* unit whose declared inputs are entirely absent from this
#: situation is dropped from the schedule instead of being run to produce a foregone
#: `insufficient_context` result.  Required units are never dropped — a required input that is
#: missing must fail the run loudly, not vanish from it.
CONTEXT_AWARE_SELECTION_KEY = "context_aware_selection"

#: Reasoner config key naming the unit this one stands in for.  A reserve unit runs only when its
#: primary failed to complete, and is recorded as skipped when the primary succeeded.  This is what
#: "fallback strategy" means in a deterministic kernel: retrying a pure function would reproduce the
#: same failure, so the only useful fallback is a *different, simpler* analysis of the same
#: situation — typically one needing fewer inputs.
FALLBACK_FOR_KEY = "fallback_for"

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
    fallback_for: str | None = None

    @property
    def is_reserve(self) -> bool:
        """True when this unit exists only to stand in for another that failed."""
        return self.fallback_for is not None

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
                "latency_budget_ms": self.latency_budget_ms,
                "fallback_for": self.fallback_for}


@dataclass(frozen=True, slots=True)
class SkippedStep:
    """A unit the planner deliberately left out, and the reason it did.

    Recorded rather than silently omitted: "this unit did not run" and "this unit was never
    considered" are different facts, and an operator reading a trace needs to tell them apart.
    """

    reasoner_id: str
    reasoner_version: str
    reason_code: str
    missing_fields: tuple[str, ...] = ()

    def to_semantic_dict(self) -> dict[str, Any]:
        return {"reasoner_id": self.reasoner_id, "reasoner_version": self.reasoner_version,
                "reason_code": self.reason_code, "missing_fields": self.missing_fields}


@dataclass(frozen=True, slots=True)
class DegradedStep:
    """A unit that RAN, and ran on fewer inputs than it declared.

    ⛔ THE GAP THIS FILLS IS ASSERTED, IN THE POSITIVE, BY A PASSING TEST IN THIS REPOSITORY —
    `tests/reason/test_selector_and_registration.py:86`:

        assert "core.tension" in plan.reasoner_plan                            # KEPT
        assert [step.reasoner_id for step in plan.skipped] == ["core.money"]   # only core.money

    `core.tension` was kept, it lost `core.money`, and the plan's `skipped` list mentions only
    `core.money`. Nothing anywhere recorded that `core.tension` is now reasoning over two sources
    instead of three. Its reading is then computed over a narrower set of inputs than it declared and
    reported as if it read them all — the same shape as `not_carried`, and as the coverage defect one
    layer down.

    ⛔ A RECEIPT, NEVER A REFUSAL. `_select` keeps a partially-fed unit on purpose, and `_select`'s own
    docstring records why the stricter rule was removed: under it *"six units lost to one absent
    fact"*. This class adds the missing fact without touching that decision. `speedrun008/YCW27/
    layer-2-reasoning/02-PLAN.md` §S2 has the full argument.

    ⛔ AND IT NAMES WHAT IT KEPT, NOT ONLY WHAT IT LOST. *"lost core.cost"* does not say whether three
    sources remained or none, and those are different readings.

    ⛔ NONE REMAINING IS POSSIBLE, AND IT IS THE LOUDEST THING THIS RECEIPT CAN SAY. The starvation
    rule applies to OPTIONAL units only — `_select`: *"a required unit's missing input is a fact the
    decision must confront, not one the schedule may hide."* So:

        OPTIONAL, every source gone  ->  dropped, and `skipped` receipts it
        REQUIRED, every source gone  ->  KEPT, running on nothing, and only `starved` says so

    The first version of this class refused an empty `available_sources` on the theory that such a unit
    is always skipped. `test_a_required_dependent_survives_the_loss_of_every_source` — which predates
    this work — proved otherwise by failing: `core.risk` is required, its only source drops, and it
    runs. **The constructor was rejecting the single most important case the receipt exists to
    record.**
    """

    reasoner_id: str
    reasoner_version: str
    #: Everything the unit declared as a dependency.
    declared_sources: tuple[str, ...]
    #: The declared sources that are still scheduled. Never empty — see `__post_init__`.
    available_sources: tuple[str, ...]
    #: The declared sources that were dropped. Never empty, or this step is not degraded.
    lost_sources: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.lost_sources:
            raise ValueError(
                f"{self.reasoner_id} lost nothing, so it is not degraded — a receipt for an intact "
                f"unit would make 'how many units ran on full input?' unanswerable")
        if set(self.available_sources) | set(self.lost_sources) != set(self.declared_sources):
            raise ValueError(
                f"{self.reasoner_id}: kept + lost must account for every declared source, or the "
                f"receipt describes a plan that was not made")

    @property
    def starved(self) -> bool:
        """⛔ Every declared source went and the unit ran anyway — only a REQUIRED unit reaches this.

        Distinct from ordinary degradation and worth a separate name: *"ran on 2 of 3"* is a reading
        over less; *"ran on 0 of 1"* is a unit asserting something with none of the input it said it
        needed. A consumer that treated the two alike would rank them the same.
        """
        return not self.available_sources

    @property
    def share_lost_bp(self) -> int:
        """How much of the declared input went, in basis points. Integer, like every ratio here."""
        return (len(self.lost_sources) * 10_000) // len(self.declared_sources)

    def explain(self) -> str:
        """One line for a card or an operator. Says both halves, always."""
        if self.starved:
            return (f"{self.reasoner_id} ran on NONE of its {len(self.declared_sources)} declared "
                    f"sources; lost {', '.join(self.lost_sources)}")
        return (f"{self.reasoner_id} ran on {len(self.available_sources)} of "
                f"{len(self.declared_sources)} declared sources; lost "
                f"{', '.join(self.lost_sources)}")

    def to_semantic_dict(self) -> dict[str, Any]:
        return {"reasoner_id": self.reasoner_id, "reasoner_version": self.reasoner_version,
                "declared_sources": self.declared_sources,
                "available_sources": self.available_sources,
                "lost_sources": self.lost_sources,
                # Derived, and stored anyway: a reader of the persisted trace must not have to know
                # that "available is empty" is the interesting case.
                "starved": self.starved}


@dataclass(frozen=True, slots=True)
class ExecutionPlan:
    """The orchestrator's committed answer to what will run, in what order, and at what cost."""

    capability_id: str
    capability_version: str
    planner_version: str
    steps: tuple[PlannedStep, ...]
    skipped: tuple[SkippedStep, ...] = ()
    #: ⛔ Units that RAN on fewer inputs than they declared. Separate from `skipped` because a skipped
    #: unit produced NOTHING and a degraded one produced a reading — folding them into one list would
    #: make "how many units ran?" unanswerable, and a consumer counting `skipped` would start counting
    #: units that did run.
    degraded: tuple[DegradedStep, ...] = ()

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
                "steps": tuple(step.to_semantic_dict() for step in self.steps),
                "skipped": tuple(step.to_semantic_dict() for step in self.skipped),
                # ⛔ PRESENT ONLY WHEN SOMETHING DEGRADED, and that is deliberate. A degraded plan IS a
                # different plan and belongs in the hash — but adding `"degraded": ()` to every plan
                # would change `plan_hash` for every plan ever computed, breaking replay verification
                # and audit continuity for runs where nothing degraded at all. An absent key and an
                # empty tuple mean the same thing here; only one of them costs the trail.
                **({"degraded": tuple(step.to_semantic_dict() for step in self.degraded)}
                   if self.degraded else {})}

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
        for step in self.skipped:
            lines.append(f"  not scheduled: {step.reasoner_id}@{step.reasoner_version} "
                         f"({step.reason_code})")
        return "\n".join(lines)


def _select(ordered: Sequence[ReasonerSpec], capability: CapabilityManifest,
            request: Any) -> tuple[tuple[ReasonerSpec, ...], tuple[SkippedStep, ...],
                                   tuple[DegradedStep, ...]]:
    """Choose which declared units this run will actually schedule.

    Three rules keep this honest. Only *optional* units are ever dropped, because a required unit's
    missing input is a fact the decision must confront, not one the schedule may hide. A unit is
    dropped only when **every** field it declared is unavailable — a partially-fed unit still has
    something to say. And a unit whose declared inputs have *all* gone is dropped with them, since
    running a unit whose every input never arrived just relocates the failure.

    **THE STARVATION RULE IS THE SAME ON BOTH KINDS OF INPUT, AND IT DID NOT USED TO BE.** A unit
    draws inputs from two places — the situation's facts and the units it declared as
    dependencies — and this pass applied opposite rules to them: *every* declared field had to be
    absent before a unit was dropped, but *any* dropped dependency dropped its dependent. On a
    six-unit hardcoded lane the asymmetry never showed. On the staged roster it is the difference
    between a roster and a rumour: `core.tradeoff` declares four evaluative sources, and under the
    any-rule a single unfed one (an expertise that names no money fact, so `core.cost` drops)
    removed tradeoff, then `core.alternative`, then `core.validation` and `core.recommendation`
    behind it — six units lost to one absent fact, each one receipted, none of them starved.

    So the rule is stated once and applied to both: a unit is dropped when it has NOTHING left to
    read. Three of four sources still reporting is three readings, exactly as one of two declared
    fields present is one reading. What a partially-fed unit does with the gap is the unit's own
    business, and every unit here already answers a missing prior with an explicit absent sentinel
    rather than a zero — that is why the number it publishes cannot quietly move when a source is
    missing, and why keeping it scheduled cannot manufacture a reading.
    """
    if request is None or not capability.metadata.get(CONTEXT_AWARE_SELECTION_KEY):
        # Nothing was selected away, so nothing can be degraded. Not "we did not look" — there was
        # nothing to look at, and the empty tuple says so for both.
        return tuple(ordered), (), ()

    kept: list[ReasonerSpec] = []
    skipped: list[SkippedStep] = []
    degraded: list[DegradedStep] = []
    dropped: set[str] = set()
    for spec in ordered:
        declared = set(spec.dependencies)
        orphaned = tuple(sorted(declared & dropped))
        if (declared and len(orphaned) == len(declared)
                and spec.failure_policy == FailurePolicy.OPTIONAL):
            dropped.add(spec.reasoner_id)
            skipped.append(SkippedStep(spec.reasoner_id, spec.version,
                                       "dependency_not_scheduled", orphaned))
            continue
        missing = required_missing(request, spec.required_fields)
        if (spec.required_fields and len(missing) == len(spec.required_fields)
                and spec.failure_policy == FailurePolicy.OPTIONAL):
            dropped.add(spec.reasoner_id)
            skipped.append(SkippedStep(spec.reasoner_id, spec.version,
                                       "no_declared_input_available", missing))
            continue

        # ⛔ THE ONLY NEW BEHAVIOUR IN THIS FUNCTION, AND IT IS A RECORD, NOT A DECISION. Every branch
        # above is untouched: the same units are kept and dropped as before, which
        # `test_the_receipt_changes_nothing_about_what_is_kept_or_dropped` asserts directly. What was
        # missing is that a unit kept with SOME of its sources gone said nothing about it — see
        # `DegradedStep`.
        lost = tuple(sorted(declared & dropped))
        if lost:
            degraded.append(DegradedStep(
                reasoner_id=spec.reasoner_id, reasoner_version=spec.version,
                declared_sources=tuple(sorted(declared)),
                available_sources=tuple(sorted(declared - dropped)),
                lost_sources=lost))

        kept.append(spec)
    return tuple(kept), tuple(skipped), tuple(degraded)


def _fallback_for(spec: ReasonerSpec) -> str | None:
    value = spec.config.get(FALLBACK_FOR_KEY)
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise OrchestrationError(
            f"{spec.reasoner_id} declares a non-empty string {FALLBACK_FOR_KEY} or none at all")
    return value.strip()


def _validate_fallbacks(plan: ExecutionPlan) -> None:
    """A reserve unit must be scheduled after the unit it covers, and must not end the run.

    Depending on its primary is what guarantees ordering: without that edge the reserve could be
    scheduled first and would have nothing to stand in for.  And a reserve may not gate, because a
    substitute deciding the whole situation does not apply would let a failure masquerade as a
    considered "no action".
    """
    by_id = plan.specs_by_id
    for step in plan.steps:
        primary = step.fallback_for
        if primary is None:
            continue
        if primary == step.reasoner_id:
            raise OrchestrationError(f"{step.reasoner_id} cannot be its own fallback")
        if primary not in by_id:
            raise OrchestrationError(
                f"{step.reasoner_id} falls back for {primary}, which is not scheduled")
        if primary not in step.dependencies:
            raise OrchestrationError(
                f"{step.reasoner_id} must depend on {primary} to stand in for it")
        if step.gating:
            raise OrchestrationError(f"{step.reasoner_id} is a reserve and may not gate the run")


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

    def plan(self, capability: CapabilityManifest, request: Any = None) -> ExecutionPlan:
        """Select and schedule the units for one run.

        `request` is optional. Without it the plan is the capability's full declared roster — the
        compile-time answer, and the one every existing capability relies on. With it, and only
        when the capability opts in, the planner additionally drops optional units this particular
        situation cannot feed. That is the blueprint's "run Risk and Priority, not Pricing" made
        deterministic: selection follows from declared inputs, never from a guess about intent.
        """
        ordered = ReasonerRegistry.topological_order(capability.reasoners)
        ordered, skipped, degraded = _select(ordered, capability, request)
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
                fallback_for=_fallback_for(spec),
            )
            for ordinal, spec in enumerate(ordered, start=1)
        )
        plan = ExecutionPlan(
            capability_id=capability.capability_id,
            capability_version=capability.version,
            planner_version=self.version,
            steps=steps,
            skipped=skipped,
            degraded=degraded,
        )
        _validate_budget(plan, capability)
        _validate_metric_authorities(plan, capability)
        # A source this manifest names must be a unit it declares AND made visible. Structural
        # only — whether the named unit was ever WRITTEN is the registry's half, asked in
        # `resolve` — but it is asked here so a manifest that configures an impossible read is
        # refused wherever a plan is built, including by tooling that holds no registry.
        validate_capability_sources(capability)
        _validate_fallbacks(plan)
        return plan

    def resolve(self, plan: ExecutionPlan, registry: ReasonerRegistry,
                capability: CapabilityManifest) -> Any:
        """Bind every planned step to its implementation before any of them run.

        A capability that can only partly execute is a broken deployment, so this refuses the whole
        plan rather than discovering the gap halfway through and emitting a decision built on the
        units that happened to exist.

        The registry is asked about every unit the manifest DECLARES, not only the ones this
        situation scheduled. Selection drops units, and a dropped unit is never resolved — so
        without this the first tenant whose facts happened to schedule an unregistered unit would
        be the one to discover it, in production, as a failed run.
        """
        registry.validate_capability(capability)
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


__all__ = ["CONTEXT_AWARE_SELECTION_KEY", "FALLBACK_FOR_KEY", "LATENCY_CEILING_KEY",
           "PLANNER_VERSION",
           "DegradedStep", "ExecutionPlan", "PlannedStep", "ReasoningPlanner", "SkippedStep",
           "describe_plans", "plan_capability"]
