"""Executable contract for the deterministic Layer 4 orchestrator.

API assumptions intentionally fixed by these tests:

* ``ReasoningOrchestrator(registry).execute(request)`` returns an immutable execution object with
  ``ordered_results``, ``candidates``, ``decision``, ``trace`` and ``authorizes_delivery``.
* A required failure yields ``DecisionOutcome.FAILED`` and cannot authorize delivery.
* An optional failure is represented in uncertainty, permits a degraded decision, and caps final
  confidence at 5,000 basis points.
* A false gating result stops semantic work: downstream reasoners are represented by synthetic
  ``SKIPPED`` results and the decision is ``NO_ACTION``.
* Constraints eliminate candidates before utility ranking. Eligible ties break lexically by
  ``play_id``. Shadow executions may compute a decision but never authorize delivery.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from decimal import Decimal

import pytest

from genios_engine.contracts.reasoning import (
    CandidateCheck,
    CandidateDisposition,
    CapabilityManifest,
    CheckOutcome,
    ContextSnapshot,
    DecisionOutcome,
    ExecutionMode,
    FailurePolicy,
    Goal,
    PlayDefinition,
    ReasonerResult,
    ReasonerSpec,
    ReasoningRequest,
    ResultStatus,
)
from genios_engine.reason.canonical import canonical_dumps
from genios_engine.reason.orchestrator import ReasoningOrchestrator
from genios_engine.reason.registry import ReasonerRegistry


NOW = datetime(2026, 8, 6, 12, tzinfo=timezone.utc)


class _StubReasoner:
    def __init__(self, spec: ReasonerSpec, result: ReasonerResult, calls: list[str] | None = None):
        self._spec = spec
        self._result = result
        self._calls = calls

    @property
    def spec(self) -> ReasonerSpec:
        return self._spec

    def evaluate(self, request, prior_results):
        del request, prior_results
        if self._calls is not None:
            self._calls.append(self.spec.reasoner_id)
        return self._result


class _DependencyCapturingReasoner(_StubReasoner):
    def __init__(self, spec, result, seen):
        super().__init__(spec, result)
        self._seen = seen

    def evaluate(self, request, prior_results):
        del request
        self._seen.append(tuple(prior_results))
        return self._result


def _result(spec: ReasonerSpec, *, status=ResultStatus.COMPLETED, matched=True,
            metrics=None, checks=(), reason_codes=()) -> ReasonerResult:
    return ReasonerResult(
        reasoner_id=spec.reasoner_id,
        reasoner_version=spec.version,
        status=status,
        matched=matched,
        metrics=metrics or {},
        checks=tuple(checks),
        reason_codes=tuple(reason_codes),
    )


def _play(play_id: str, *, impact=6_000, success=6_000, effort=2_000, risk=1_000,
          read_only=True) -> PlayDefinition:
    return PlayDefinition(
        play_id=play_id,
        version="1",
        label=play_id.replace("_", " ").title(),
        steps=("Prepare a grounded draft",),
        read_only=read_only,
        impact_bp=impact,
        success_probability_bp=success,
        effort_bp=effort,
        risk_bp=risk,
        success_events=("prospect_reply",),
        window_days=14,
    )


def _request(specs, *, plays=None, mode=ExecutionMode.LIVE) -> ReasoningRequest:
    capability = CapabilityManifest(
        capability_id="sales.deal_cooling",
        version="1.0.0",
        domain="sales",
        root_entity_type="deal",
        goal=Goal("restore_momentum", "Restore healthy deal momentum"),
        reasoners=tuple(specs),
        plays=tuple(plays or (_play("restore_momentum"),)),
        # Generic orchestration tests use arbitrary fake reasoners. Capability-policy enforcement
        # is covered separately with the required core.constraint boundary.
        policies=(),
    )
    context = ContextSnapshot(
        org_id="org_1",
        graph_version=17,
        root_entity_id="deal_1",
        root_entity_type="deal",
        evaluation_time=NOW,
        selector_version="selector.v1",
        facts={"deal.status": "open", "derived.engagement_bp": 4_000},
        neighbor_facts={"deal.status": "open"},
        edge_count=2,
    )
    return ReasoningRequest(
        org_id="org_1",
        capability=capability,
        context=context,
        evaluation_time=NOW,
        trigger_kind="email.received",
        trigger_ref="event_1",
        mode=mode,
        config_snapshot_id="cfg_1",
    )


def _semantic_execution(execution):
    return {
        "ordered_result_hashes": tuple(result.semantic_hash for result in execution.ordered_results),
        "candidate_hashes": tuple(candidate.semantic_hash for candidate in execution.candidates),
        "decision_hash": execution.decision.semantic_hash,
        "trace_hash": execution.trace.semantic_hash,
        "authorizes_delivery": execution.authorizes_delivery,
    }


def test_executes_reasoners_in_lexical_dag_order():
    calls: list[str] = []
    specs = (
        ReasonerSpec("gamma", "1", dependencies=("alpha",)),
        ReasonerSpec("delta", "1", dependencies=("beta",)),
        ReasonerSpec("beta", "1"),
        ReasonerSpec("alpha", "1"),
    )
    reasoners = tuple(_StubReasoner(spec, _result(spec), calls) for spec in specs)

    execution = ReasoningOrchestrator(ReasonerRegistry(reasoners)).execute(_request(specs))

    assert calls == ["alpha", "beta", "delta", "gamma"]
    assert tuple(result.reasoner_id for result in execution.ordered_results) == tuple(calls)
    assert execution.trace.reasoner_plan == tuple(calls)
    assert tuple(step.ordinal for step in execution.trace.steps) == (1, 2, 3, 4)


def test_reasoner_can_only_observe_explicitly_declared_dependencies():
    alpha = ReasonerSpec("alpha", "1")
    beta = ReasonerSpec("beta", "1")
    gamma = ReasonerSpec("gamma", "1", dependencies=("alpha",))
    seen = []
    reasoners = (
        _StubReasoner(alpha, _result(alpha)),
        _StubReasoner(beta, _result(beta)),
        _DependencyCapturingReasoner(gamma, _result(gamma), seen),
    )

    ReasoningOrchestrator(ReasonerRegistry(reasoners)).execute(
        _request((gamma, beta, alpha)))

    assert seen == [("alpha",)]


def test_non_integer_basis_point_metric_is_rejected_by_the_result_contract():
    gate = ReasonerSpec("gate", "1", gating=True)

    with pytest.raises(TypeError, match="integer basis points"):
        _result(gate, metrics={"confidence_bp": Decimal("8000.5")})


def test_failed_reasoner_cannot_smuggle_effects_into_a_degraded_decision():
    optional = ReasonerSpec("optional", "1", failure_policy=FailurePolicy.OPTIONAL)

    with pytest.raises(ValueError, match="non-completed reasoner results"):
        _result(
            optional,
            status=ResultStatus.FAILED,
            matched=None,
            metrics={"priority_override_bp": 10_000},
        )


def test_completed_gate_without_boolean_match_fails_closed():
    gate = ReasonerSpec("gate", "1", gating=True)
    reasoner = _StubReasoner(gate, _result(gate, matched=None))

    execution = ReasoningOrchestrator(ReasonerRegistry((reasoner,))).execute(
        _request((gate,)))

    assert execution.ordered_results[0].status == ResultStatus.FAILED
    assert execution.decision.outcome == DecisionOutcome.FAILED


def test_required_failure_fails_closed_without_candidates_or_authority():
    required = ReasonerSpec("required", "1", failure_policy=FailurePolicy.REQUIRED)
    reasoner = _StubReasoner(
        required,
        _result(required, status=ResultStatus.FAILED, matched=None,
                reason_codes=("required_input_invalid",)),
    )

    execution = ReasoningOrchestrator(ReasonerRegistry((reasoner,))).execute(
        _request((required,)))

    assert execution.ordered_results[0].status == ResultStatus.FAILED
    assert execution.candidates == ()
    assert execution.decision.outcome == DecisionOutcome.FAILED
    assert execution.decision.selected_candidate_id is None
    assert execution.authorizes_delivery is False


def test_required_reasoner_exception_becomes_a_typed_failed_trace():
    spec = ReasonerSpec("exploding", "1", failure_policy=FailurePolicy.REQUIRED)

    class _ExplodingReasoner:
        @property
        def spec(self):
            return spec

        def evaluate(self, request, prior_results):
            del request, prior_results
            raise RuntimeError("synthetic failure")

    execution = ReasoningOrchestrator(
        ReasonerRegistry((_ExplodingReasoner(),))).execute(_request((spec,)))

    assert execution.ordered_results[0].status == ResultStatus.FAILED
    assert execution.ordered_results[0].reason_codes == ("reasoner_failure",)
    assert execution.decision.outcome == DecisionOutcome.FAILED
    assert execution.authorizes_delivery is False


def test_optional_failure_is_explicitly_degraded_and_caps_confidence():
    gate = ReasonerSpec("gate", "1", gating=True)
    optional = ReasonerSpec(
        "optional", "1", dependencies=("gate",), failure_policy=FailurePolicy.OPTIONAL)
    reasoners = (
        _StubReasoner(gate, _result(
            gate, matched=True, metrics={"urgency_bp": 8_000, "confidence_bp": 9_000})),
        _StubReasoner(optional, _result(
            optional, status=ResultStatus.FAILED, matched=None,
            reason_codes=("optional_model_unavailable",))),
    )

    execution = ReasoningOrchestrator(ReasonerRegistry(reasoners)).execute(
        _request((optional, gate)))

    assert execution.decision.outcome == DecisionOutcome.DECISION
    assert execution.decision.confidence_bp <= 5_000
    assert any("optional" in item and "failed" in item
               for item in execution.decision.uncertainty)
    assert execution.authorizes_delivery is True


def test_false_gate_returns_no_action_and_skips_downstream_reasoners():
    calls: list[str] = []
    gate = ReasonerSpec("gate", "1", gating=True)
    downstream = ReasonerSpec("downstream", "1", dependencies=("gate",))
    reasoners = (
        _StubReasoner(gate, _result(gate, matched=False, reason_codes=("healthy",)), calls),
        _StubReasoner(downstream, _result(downstream), calls),
    )

    execution = ReasoningOrchestrator(ReasonerRegistry(reasoners)).execute(
        _request((downstream, gate)))

    assert calls == ["gate"]
    assert tuple(result.status for result in execution.ordered_results) == (
        ResultStatus.COMPLETED, ResultStatus.SKIPPED)
    assert execution.candidates == ()
    assert execution.decision.outcome == DecisionOutcome.NO_ACTION
    assert execution.decision.selected_candidate_id is None
    assert execution.authorizes_delivery is False


def test_constraints_eliminate_before_ranking_even_when_blocked_play_scores_higher():
    gate = ReasonerSpec("gate", "1", gating=True)
    constraints = ReasonerSpec("constraints", "1", dependencies=("gate",))
    blocked = _play("blocked_high_value", impact=10_000, success=10_000, effort=0, risk=0)
    allowed = _play("allowed_lower_value", impact=2_000, success=2_000, effort=8_000, risk=8_000)
    blocked_check = CandidateCheck(
        play_id=blocked.play_id,
        stage="policy",
        outcome=CheckOutcome.ELIMINATE,
        reason_code="tenant_policy_block",
        evaluator_id=constraints.reasoner_id,
        evaluator_version=constraints.version,
    )
    reasoners = (
        _StubReasoner(gate, _result(
            gate, metrics={"urgency_bp": 7_000, "confidence_bp": 8_000})),
        _StubReasoner(constraints, _result(constraints, checks=(blocked_check,))),
    )

    execution = ReasoningOrchestrator(ReasonerRegistry(reasoners)).execute(
        _request((constraints, gate), plays=(blocked, allowed)))
    by_play = {candidate.play_id: candidate for candidate in execution.candidates}

    assert by_play[blocked.play_id].disposition == CandidateDisposition.ELIMINATED
    assert by_play[allowed.play_id].disposition == CandidateDisposition.ELIGIBLE
    assert execution.decision.selected_candidate_id == by_play[allowed.play_id].candidate_id
    assert execution.decision.outcome == DecisionOutcome.DECISION


def test_equal_utility_candidates_use_play_id_as_the_total_order_tie_break():
    gate = ReasonerSpec("gate", "1", gating=True)
    reasoner = _StubReasoner(
        gate, _result(gate, metrics={"urgency_bp": 5_000, "confidence_bp": 8_000}))
    zeta = _play("zeta_play")
    alpha = _play("alpha_play")

    execution = ReasoningOrchestrator(ReasonerRegistry((reasoner,))).execute(
        _request((gate,), plays=(zeta, alpha)))
    eligible = [candidate for candidate in execution.candidates
                if candidate.disposition == CandidateDisposition.ELIGIBLE]

    assert [candidate.play_id for candidate in eligible] == ["alpha_play", "zeta_play"]
    assert [candidate.rank_position for candidate in eligible] == [1, 2]
    assert execution.decision.selected_candidate_id == eligible[0].candidate_id


def test_identical_request_replay_has_identical_semantic_output():
    gate = ReasonerSpec("gate", "1", gating=True)
    reasoner = _StubReasoner(
        gate, _result(gate, metrics={"urgency_bp": 6_000, "confidence_bp": 8_500}))
    orchestrator = ReasoningOrchestrator(ReasonerRegistry((reasoner,)))
    request = _request((gate,), plays=(_play("restore"), _play("multithread")))

    first = orchestrator.execute(request)
    second = orchestrator.execute(request)

    assert _semantic_execution(first) == _semantic_execution(second)
    assert first.decision.decision_id == second.decision.decision_id
    assert first.trace.semantic_hash == second.trace.semantic_hash


def test_shadow_mode_computes_but_never_authorizes_delivery():
    gate = ReasonerSpec("gate", "1", gating=True)
    reasoner = _StubReasoner(
        gate, _result(gate, metrics={"urgency_bp": 8_000, "confidence_bp": 9_000}))

    execution = ReasoningOrchestrator(ReasonerRegistry((reasoner,))).execute(
        _request((gate,), mode=ExecutionMode.SHADOW))

    assert execution.decision.outcome == DecisionOutcome.DECISION
    assert execution.decision.selected_candidate_id is not None
    assert execution.trace.mode == ExecutionMode.SHADOW
    assert execution.authorizes_delivery is False
    assert execution.authorizes_external_mutation is False


def test_non_read_only_winner_never_crosses_the_delivery_authority_boundary():
    gate = ReasonerSpec("gate", "1", gating=True)
    reasoner = _StubReasoner(
        gate, _result(gate, metrics={"urgency_bp": 8_000, "confidence_bp": 9_000}))
    request = _request((gate,), plays=(_play("unsafe_mutation", read_only=False),))
    request = replace(
        request,
        capability=replace(request.capability, policies=()),
        policy_snapshot_id=None,
        request_id=None,
    )

    execution = ReasoningOrchestrator(ReasonerRegistry((reasoner,))).execute(request)

    assert execution.decision.outcome == DecisionOutcome.DECISION
    assert execution.selected_candidate.parameters["read_only"] is False
    assert execution.authorizes_delivery is False
    assert execution.authorizes_external_mutation is False


def test_ranking_artifacts_use_only_integer_basis_points():
    gate = ReasonerSpec("gate", "1", gating=True)
    reasoner = _StubReasoner(
        gate, _result(gate, metrics={"urgency_bp": 6_789, "confidence_bp": 8_765}))

    execution = ReasoningOrchestrator(ReasonerRegistry((reasoner,))).execute(
        _request((gate,), plays=(_play("restore"), _play("multithread"))))

    assert type(execution.decision.confidence_bp) is int
    for candidate in execution.candidates:
        assert type(candidate.utility_bp) is int
        assert type(candidate.confidence_bp) is int
        assert all(type(value) is int for value in candidate.score_components.values())
        canonical_dumps(candidate.to_semantic_dict())  # would reject a hidden float


# ---------------------------------------------------------------------------------------------
# Fallback: a reserve unit runs only when the unit it covers could not
# ---------------------------------------------------------------------------------------------

_RICH = ReasonerSpec("core.rich", "1", failure_policy=FailurePolicy.OPTIONAL)
_RESERVE = ReasonerSpec("core.simple", "1", dependencies=("core.rich",),
                        failure_policy=FailurePolicy.OPTIONAL,
                        config={"fallback_for": "core.rich"})


def _reserve_execution(rich_result):
    calls: list[str] = []
    reasoners = (
        _StubReasoner(_RICH, rich_result, calls),
        _StubReasoner(_RESERVE, _result(_RESERVE, metrics={"confidence_bp": 4_000}), calls),
    )
    execution = ReasoningOrchestrator(ReasonerRegistry(reasoners)).execute(
        _request((_RESERVE, _RICH)))
    return execution, calls


def test_a_reserve_unit_stays_on_the_bench_when_its_primary_completes():
    execution, calls = _reserve_execution(
        _result(_RICH, metrics={"confidence_bp": 9_000}))
    by_id = execution.result_by_id

    assert calls == ["core.rich"]                       # the reserve was never evaluated
    assert by_id["core.simple"].status == ResultStatus.SKIPPED
    assert by_id["core.simple"].reason_codes == ("primary_completed:core.rich",)
    assert execution.decision.confidence_bp == 9_000
    # Standing down is not a degradation: nothing was lost.
    assert not any("optional" in item for item in execution.decision.uncertainty)


def test_a_reserve_unit_takes_over_when_its_primary_fails():
    execution, calls = _reserve_execution(
        _result(_RICH, status=ResultStatus.FAILED, matched=None,
                reason_codes=("model_unavailable",)))
    by_id = execution.result_by_id

    assert calls == ["core.rich", "core.simple"]
    assert by_id["core.simple"].status == ResultStatus.COMPLETED
    assert execution.decision.outcome == DecisionOutcome.DECISION
    # The reserve's weaker reading is what the decision now rests on...
    assert execution.decision.confidence_bp == 4_000
    # ...and the run still admits it needed one.
    assert any("optional" in item and "core.rich" in item
               for item in execution.decision.uncertainty)
