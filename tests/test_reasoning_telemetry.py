"""Executable contract for Layer 4 · Part 1 — execution telemetry.

A unit declares what it should cost; this proves we now notice when it lies. The load-bearing
property, though, is the *negative* one: timing is observed and never consulted. A decision made
on a loaded production box must be byte-identical to the same decision made on an idle laptop,
because a decision that changes with CPU scheduling cannot be replayed and therefore cannot be
audited. These tests pin that separation from both directions.
"""

from __future__ import annotations

import time
from dataclasses import replace
from datetime import datetime, timezone

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
from genios_engine.reason.registry import ReasonerRegistry
from genios_engine.reason.telemetry import (
    ExecutionTelemetry,
    StepTiming,
    TelemetryRecorder,
    aggregate,
    slowest_first,
)

NOW = datetime(2026, 8, 6, 12, tzinfo=timezone.utc)


class _StubReasoner:
    def __init__(self, spec: ReasonerSpec, *, sleep_s: float = 0.0):
        self._spec = spec
        self._sleep_s = sleep_s

    @property
    def spec(self) -> ReasonerSpec:
        return self._spec

    def evaluate(self, request, prior_results):
        del request, prior_results
        if self._sleep_s:
            time.sleep(self._sleep_s)
        return ReasonerResult(
            reasoner_id=self._spec.reasoner_id,
            reasoner_version=self._spec.version,
            status=ResultStatus.COMPLETED,
            matched=True,
        )


def _request(specs, *, required_fields=()) -> ReasoningRequest:
    capability = CapabilityManifest(
        capability_id="sales.deal_cooling",
        version="1.0.0",
        domain="sales",
        root_entity_type="deal",
        goal=Goal("restore_momentum", "Restore healthy deal momentum"),
        reasoners=tuple(specs),
        plays=(PlayDefinition(play_id="restore_momentum", version="1", label="Restore",
                              steps=("Prepare a grounded draft",)),),
        policies=(),
        required_fields=tuple(required_fields),
    )
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


# ---------------------------------------------------------------------------------------------
# The separation: observed, never consulted
# ---------------------------------------------------------------------------------------------

def test_a_slow_unit_produces_an_identical_decision():
    """The whole point. Same inputs, wildly different runtimes, same decision bytes."""
    spec = ReasonerSpec("core.slow", "1", latency_budget_ms=1)
    request = _request((spec,))

    fast = ReasoningOrchestrator(ReasonerRegistry((_StubReasoner(spec),))).execute(request)
    slow = ReasoningOrchestrator(
        ReasonerRegistry((_StubReasoner(spec, sleep_s=0.02),))).execute(request)

    assert slow.telemetry.elapsed_us > fast.telemetry.elapsed_us
    assert slow.decision.semantic_hash == fast.decision.semantic_hash
    assert slow.trace.semantic_hash == fast.trace.semantic_hash
    assert slow.semantic_hash == fast.semantic_hash


def test_telemetry_is_outside_the_semantic_identity_of_a_run():
    spec = ReasonerSpec("core.unit", "1")
    execution = ReasoningOrchestrator(
        ReasonerRegistry((_StubReasoner(spec),))).execute(_request((spec,)))

    assert "telemetry" not in execution.to_semantic_dict()
    assert execution.semantic_hash == replace(execution, telemetry=None).semantic_hash


def test_an_overrun_is_detected_and_attributed():
    spec = ReasonerSpec("core.slow", "1", latency_budget_ms=1)
    execution = ReasoningOrchestrator(
        ReasonerRegistry((_StubReasoner(spec, sleep_s=0.02),))).execute(_request((spec,)))

    breaches = execution.telemetry.breaches

    assert [item.reasoner_id for item in breaches] == ["core.slow"]
    assert execution.telemetry.slowest.reasoner_id == "core.slow"
    assert "OVER BUDGET" in execution.telemetry.describe()


def test_only_units_that_actually_ran_are_timed():
    """A unit skipped after a terminal outcome consumed no time and must not be reported as fast."""
    gate = ReasonerSpec("gate", "1", gating=True, failure_policy=FailurePolicy.REQUIRED)
    downstream = ReasonerSpec("downstream", "1", dependencies=("gate",))

    class _FalseGate(_StubReasoner):
        def evaluate(self, request, prior_results):
            del request, prior_results
            return ReasonerResult("gate", "1", ResultStatus.COMPLETED, matched=False)

    registry = ReasonerRegistry((_FalseGate(gate), _StubReasoner(downstream)))
    execution = ReasoningOrchestrator(registry).execute(_request((downstream, gate)))

    assert [item.reasoner_id for item in execution.telemetry.timings] == ["gate"]


def test_a_unit_blocked_on_missing_context_is_not_timed():
    spec = ReasonerSpec("core.unit", "1", required_fields=("deal.owner",))
    execution = ReasoningOrchestrator(
        ReasonerRegistry((_StubReasoner(spec),))).execute(_request((spec,)))

    assert execution.telemetry.timings == ()
    assert execution.ordered_results[0].status == ResultStatus.INSUFFICIENT_CONTEXT


def test_timings_are_recorded_per_unit_with_its_declared_budget():
    specs = (ReasonerSpec("alpha", "1", latency_budget_ms=40),
             ReasonerSpec("beta", "1", dependencies=("alpha",), latency_budget_ms=70))
    registry = ReasonerRegistry(tuple(_StubReasoner(spec) for spec in specs))

    execution = ReasoningOrchestrator(registry).execute(_request(specs))
    by_id = {item.reasoner_id: item for item in execution.telemetry.timings}

    assert by_id["alpha"].budget_ms == 40
    assert by_id["beta"].budget_ms == 70
    assert by_id["alpha"].stage == 0
    assert by_id["beta"].stage == 1


# ---------------------------------------------------------------------------------------------
# Pure arithmetic — no clock involved
# ---------------------------------------------------------------------------------------------

def test_budget_arithmetic_is_pure():
    timing = StepTiming(reasoner_id="core.risk", reasoner_version="1", stage=0,
                        elapsed_us=25_000, budget_ms=100)

    assert timing.elapsed_ms == 25
    assert timing.over_budget is False
    assert timing.budget_used_bp == 2_500


def test_a_sub_millisecond_unit_is_not_reported_as_free():
    timing = StepTiming(reasoner_id="core.fast", reasoner_version="1", stage=0,
                        elapsed_us=400, budget_ms=100)

    assert timing.elapsed_ms == 0
    assert timing.elapsed_us == 400          # the real signal survives the rounding
    assert timing.budget_used_bp == 40


def test_a_zero_budget_unit_is_always_over_budget():
    timing = StepTiming(reasoner_id="core.unbudgeted", reasoner_version="1", stage=0,
                        elapsed_us=1, budget_ms=0)

    assert timing.over_budget is True
    assert timing.budget_used_bp == 10_000


def test_a_backwards_clock_cannot_produce_a_negative_duration():
    recorder = TelemetryRecorder()
    recorder.record(reasoner_id="core.unit", reasoner_version="1", stage=0,
                    started_ns=5_000_000, ended_ns=1_000_000, budget_ms=10)

    assert recorder.finish().timings[0].elapsed_us == 0


def test_aggregate_keeps_the_worst_observed_cost_per_unit():
    runs = [
        ExecutionTelemetry((StepTiming("core.risk", "1", 0, 10_000, 100),)),
        ExecutionTelemetry((StepTiming("core.risk", "1", 0, 30_000, 100),
                            StepTiming("core.priority", "1", 1, 5_000, 100),)),
    ]

    assert aggregate(runs) == {"core.risk": 30_000, "core.priority": 5_000}


def test_slowest_first_is_a_total_order():
    timings = (StepTiming("beta", "1", 0, 500, 10), StepTiming("alpha", "1", 0, 500, 10))

    assert [item.reasoner_id for item in slowest_first(timings)] == ["alpha", "beta"]


def test_an_empty_run_describes_itself_without_crashing():
    telemetry = ExecutionTelemetry()

    assert telemetry.describe() == "no units executed"
    assert telemetry.slowest is None
    assert telemetry.elapsed_ms == 0
