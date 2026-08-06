"""Layer 4 · Part 1 — the Reasoning Orchestrator.

The orchestrator is the scheduler of Layer 4, and *only* the scheduler.  It answers which units
run, in what order, which may run together, which are skipped, what happens when one fails, and
what the immutable trace of all that must say.  It never analyses a situation and it never picks a
winner: analysis belongs to the units (Part 2) and synthesis belongs to the Decision Maker
(Part 3).  Keeping those three responsibilities in three modules is what lets any one of them be
replaced without the others noticing.

Determinism is the contract, not a nicety.  The same request must produce the same plan, the same
step hashes, and the same decision on any machine at any time — that is what makes a decision
replayable months later, and what lets an audit prove a conclusion rather than assert it.  So the
orchestrator reads no clock, consults no database, and resolves every ordering to a total order.

A reasoner may fail; a capability may not.  Every declared implementation is resolved before any
evaluation begins, because a half-executable capability is a broken deployment, not a degraded
runtime.  Once running, a unit's exception becomes a typed FAILED result inside the trace rather
than an exception out of the kernel — a failure that is recorded is inspectable, a failure that
escapes is just an outage.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any

from genios_engine.contracts.reasoning import (
    DecisionCandidate,
    DecisionOutcome,
    ExecutionMode,
    FailurePolicy,
    ReasonerResult,
    ReasonerSpec,
    ReasoningDecision,
    ReasoningRequest,
    ReasoningTrace,
    ResultStatus,
    StepTrace,
)
from genios_engine.platform.canonical import semantic_hash, stable_id

from .decision_maker import DecisionMaker
from .guards import required_missing, validate_candidate_effects, validate_evidence_references
from .plan import ExecutionPlan, ReasoningPlanner
from .protocols import MissingContextError, OrchestrationError
from .registry import ReasonerRegistry
from .telemetry import ExecutionTelemetry, TelemetryRecorder, log_budget_breaches

ORCHESTRATOR_VERSION = "4.0.0"


@dataclass(frozen=True, slots=True)
class ReasoningExecution:
    """Complete semantic result of one deterministic reasoning execution."""

    request: ReasoningRequest
    ordered_results: tuple[ReasonerResult, ...]
    candidates: tuple[DecisionCandidate, ...]
    decision: ReasoningDecision
    trace: ReasoningTrace
    #: The schedule this run committed to.  Diagnostic only: it is derived from the capability,
    #: already summarised in `trace.reasoner_plan`, and deliberately excluded from the semantic
    #: hash so describing a run can never change the decision it describes.
    plan: ExecutionPlan | None = field(default=None, compare=False, repr=False)
    #: Observed cost of the run.  Also diagnostic, and for a stronger reason: a stopwatch reading
    #: varies by machine, so admitting it into the semantic hash would make the same situation
    #: irreproducible.  See `reason.telemetry`.
    #:
    #: Both are `compare=False`: identity for this type is `semantic_hash`, and a generated `__eq__`
    #: that consulted a stopwatch would report two byte-identical runs as different the moment
    #: anyone reached for `==`.  Same reason `ReasonerResult.diagnostics` is excluded.
    telemetry: ExecutionTelemetry | None = field(default=None, compare=False, repr=False)

    @property
    def result_by_id(self) -> Mapping[str, ReasonerResult]:
        return MappingProxyType({item.reasoner_id: item for item in self.ordered_results})

    @property
    def delivery_allowed(self) -> bool:
        """Only a live, successful, read-only decision may cross into the delivery layer."""
        selected = self.selected_candidate
        return self.request.mode == ExecutionMode.LIVE \
            and self.request.capability.live_delivery_enabled \
            and self.decision.outcome == DecisionOutcome.DECISION \
            and selected is not None \
            and selected.parameters.get("read_only") is True

    @property
    def authorizes_delivery(self) -> bool:
        """Named authority boundary used by delivery adapters."""
        return self.delivery_allowed

    @property
    def authorizes_external_mutation(self) -> bool:
        """GeniOS v1 may deliver intelligence or a draft, never mutate an external system."""
        return False

    @property
    def selected_candidate(self) -> DecisionCandidate | None:
        selected_id = self.decision.selected_candidate_id
        return next((item for item in self.candidates
                     if item.candidate_id == selected_id), None)

    def to_semantic_dict(self) -> dict[str, Any]:
        return {
            "request_hash": self.request.semantic_hash,
            "ordered_results": self.ordered_results,
            "candidates": self.candidates,
            "decision": self.decision,
            "trace": self.trace,
        }

    @property
    def semantic_hash(self) -> str:
        return semantic_hash(self.to_semantic_dict())


class ReasoningOrchestrator:
    """Execute a capability DAG and produce a traceable deterministic decision."""

    def __init__(self, registry: ReasonerRegistry, *, version: str = ORCHESTRATOR_VERSION,
                 decision_maker: DecisionMaker | None = None,
                 planner: ReasoningPlanner | None = None) -> None:
        self._registry = registry
        self._decision_maker = decision_maker or DecisionMaker()
        self._planner = planner or ReasoningPlanner()
        self.version = str(version).strip()
        if not self.version:
            raise ValueError("orchestrator version is required")

    def plan(self, request: ReasoningRequest) -> ExecutionPlan:
        """Commit to a schedule without executing it — for operators, tooling, and dry runs."""
        return self._planner.plan(request.capability)

    def execute(self, request: ReasoningRequest) -> ReasoningExecution:
        # Decide the whole schedule first: an unschedulable capability must be refused before any
        # unit observes the situation, not diagnosed halfway through a partially-formed decision.
        plan = self._planner.plan(request.capability)
        specs_by_id = {spec.reasoner_id: spec for spec in request.capability.reasoners}
        reasoners = self._planner.resolve(plan, self._registry, request.capability)
        play_ids = {play.play_id for play in request.capability.plays}
        initial_missing = required_missing(request, request.capability.required_fields)

        results: list[ReasonerResult] = []
        steps: list[StepTrace] = []
        prior: dict[str, ReasonerResult] = {}
        terminal: DecisionOutcome | None = None
        optional_degradations: list[str] = []
        recorder = TelemetryRecorder()

        if initial_missing:
            terminal = DecisionOutcome.INSUFFICIENT_CONTEXT

        for planned in plan.steps:
            ordinal, spec = planned.ordinal, specs_by_id[planned.reasoner_id]
            dependencies = {item: prior[item] for item in spec.dependencies if item in prior}
            input_hash = semantic_hash({
                "request_hash": request.semantic_hash,
                "spec": spec,
                "dependencies": dependencies,
            })

            if terminal is not None:
                result = _skipped_result(spec, terminal)
            else:
                missing = required_missing(request, spec.required_fields)
                if missing:
                    result = ReasonerResult(
                        reasoner_id=spec.reasoner_id,
                        reasoner_version=spec.version,
                        status=ResultStatus.INSUFFICIENT_CONTEXT,
                        missing_fields=missing,
                        reason_codes=("required_context_missing",),
                    )
                else:
                    # A reasoner can see only dependencies it declared in the capability DAG.
                    # Passing every earlier result would create hidden, order-dependent edges.
                    started_ns = recorder.now_ns()
                    result = self._evaluate(reasoners[spec.reasoner_id], spec, request,
                                            dependencies, play_ids)
                    recorder.record(
                        reasoner_id=spec.reasoner_id,
                        reasoner_version=spec.version,
                        stage=planned.stage,
                        started_ns=started_ns,
                        ended_ns=recorder.now_ns(),
                        budget_ms=spec.latency_budget_ms,
                    )

                if result.status in {ResultStatus.FAILED, ResultStatus.INSUFFICIENT_CONTEXT}:
                    if spec.failure_policy == FailurePolicy.REQUIRED:
                        terminal = (DecisionOutcome.INSUFFICIENT_CONTEXT
                                    if result.status == ResultStatus.INSUFFICIENT_CONTEXT
                                    else DecisionOutcome.FAILED)
                    else:
                        optional_degradations.append(
                            f"optional_{result.status.value}:{spec.reasoner_id}")
                elif result.status == ResultStatus.SKIPPED:
                    # Reasoner implementations may not silently skip themselves.
                    result = _failed_result(spec, "reasoner_returned_skipped")
                    if spec.failure_policy == FailurePolicy.REQUIRED:
                        terminal = DecisionOutcome.FAILED
                    else:
                        optional_degradations.append(f"optional_failed:{spec.reasoner_id}")
                elif spec.gating and result.matched is False:
                    terminal = DecisionOutcome.NO_ACTION

            prior[spec.reasoner_id] = result
            results.append(result)
            steps.append(StepTrace(
                ordinal=ordinal,
                reasoner_id=spec.reasoner_id,
                reasoner_version=spec.version,
                status=result.status,
                input_hash=input_hash,
                output_hash=result.semantic_hash,
                reason_codes=result.reason_codes,
                missing_fields=result.missing_fields,
            ))

        uncertainty = list(initial_missing)
        uncertainty.extend(optional_degradations)
        uncertainty.extend(field for result in results for field in result.missing_fields)

        synthesis = self._decision_maker.decide(
            request, results,
            terminal=terminal,
            uncertainty=uncertainty,
            degraded=bool(optional_degradations),
        )

        trace_seed = {
            "request_hash": request.semantic_hash,
            "orchestrator_version": self.version,
            "reasoner_plan": plan.reasoner_plan,
        }
        trace = ReasoningTrace(
            run_id=stable_id("run", trace_seed),
            request_hash=request.semantic_hash,
            capability_snapshot_id=request.capability.capability_snapshot_id,
            context_snapshot_id=request.context.context_snapshot_id,
            orchestrator_version=self.version,
            mode=request.mode,
            reasoner_plan=plan.reasoner_plan,
            steps=tuple(steps),
            decision_hash=synthesis.decision.semantic_hash,
        )
        telemetry = recorder.finish()
        log_budget_breaches(telemetry,
                            capability_id=request.capability.capability_id,
                            capability_version=request.capability.version)
        return ReasoningExecution(request, tuple(results), synthesis.candidates,
                                  synthesis.decision, trace, plan, telemetry)

    @staticmethod
    def _evaluate(reasoner, spec: ReasonerSpec, request: ReasoningRequest,
                  prior: Mapping[str, ReasonerResult], play_ids: set[str]) -> ReasonerResult:
        try:
            result = reasoner.evaluate(request, MappingProxyType(dict(prior)))
            if not isinstance(result, ReasonerResult):
                raise TypeError("reasoner did not return ReasonerResult")
            if (result.reasoner_id, result.reasoner_version) != (spec.reasoner_id, spec.version):
                raise ValueError("reasoner result identity does not match capability spec")
            if (spec.gating and result.status == ResultStatus.COMPLETED
                    and not isinstance(result.matched, bool)):
                raise ValueError("a completed gating reasoner must return matched=true or false")
            validate_candidate_effects(result, play_ids)
            validate_evidence_references(result, request)
            return result
        except MissingContextError as exc:
            return ReasonerResult(
                reasoner_id=spec.reasoner_id,
                reasoner_version=spec.version,
                status=ResultStatus.INSUFFICIENT_CONTEXT,
                missing_fields=exc.fields,
                reason_codes=("required_context_missing",),
            )
        except Exception as exc:  # boundary: exceptions become explicit, typed trace state
            return ReasonerResult(
                reasoner_id=spec.reasoner_id,
                reasoner_version=spec.version,
                status=ResultStatus.FAILED,
                reason_codes=("reasoner_failure",),
                diagnostics={"exception_type": type(exc).__name__, "message": str(exc)},
            )


def _failed_result(spec: ReasonerSpec, reason_code: str) -> ReasonerResult:
    return ReasonerResult(
        reasoner_id=spec.reasoner_id,
        reasoner_version=spec.version,
        status=ResultStatus.FAILED,
        reason_codes=(reason_code,),
    )


def _skipped_result(spec: ReasonerSpec, terminal: DecisionOutcome) -> ReasonerResult:
    return ReasonerResult(
        reasoner_id=spec.reasoner_id,
        reasoner_version=spec.version,
        status=ResultStatus.SKIPPED,
        reason_codes=(f"skipped_after_{terminal.value}",),
    )


__all__ = ["ORCHESTRATOR_VERSION", "OrchestrationError", "ReasoningExecution",
           "ReasoningOrchestrator"]
