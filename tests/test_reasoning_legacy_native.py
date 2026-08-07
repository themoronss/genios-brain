from __future__ import annotations

import math
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from genios_engine.contracts.reasoning import (
    CandidateDisposition,
    ContextSnapshot,
    DecisionOutcome,
    EvidenceRef,
    ExecutionMode,
    ReasoningRequest,
)
from genios_engine.packs.capabilities import DEAL_COOLING_V1
from genios_engine.packs.sales_v1 import SALES_V1
from genios_engine.platform.canonical import canonicalize
from genios_engine.reason.adapters import reason_legacy_rule
from genios_engine.reason.adapters import native_context_snapshot, reason_native_capability
from genios_engine.reason.adapters.legacy_context import (
    legacy_context_snapshot,
    semantic_legacy_value,
)
from genios_engine.reason.adapters.legacy_pack import legacy_capability_manifest
from genios_engine.reason.engine import NodeContext, evaluate, score_rule
from genios_engine.reason.orchestrator import ReasoningOrchestrator
from genios_engine.reason.reasoners import default_registry
from genios_engine.reason.rules import rule_from_dict


NOW = datetime(2026, 8, 6, 12, tzinfo=timezone.utc)
SCORING = SALES_V1["scoring_defaults"]
STALLED_RULE = rule_from_dict(SALES_V1["rules"][0])


def _legacy_context(*, status: str = "open", fact_order: str = "normal") -> NodeContext:
    items = [
        ("deal.status", {
            "value": status,
            "confidence": 0.95,
            "authority_rank": 3,
            "occurred_at": NOW - timedelta(hours=1),
        }),
        ("deal.last_inbound", {
            "value": (NOW - timedelta(days=9)).isoformat(),
            "confidence": 0.9,
            "authority_rank": 2,
            "occurred_at": NOW - timedelta(days=9),
        }),
        ("deal.value", {
            "value": 200_000.0,
            "confidence": 0.8,
            "authority_rank": 3,
            "occurred_at": NOW - timedelta(days=1),
        }),
    ]
    if fact_order == "reversed":
        items.reverse()
    return NodeContext(
        node_id="deal_1",
        node_type="deal",
        facts=dict(items),
        obs=[
            {"kind": "pricing_discussed", "occurred_at": NOW - timedelta(days=3)},
            {"kind": "buying_intent", "occurred_at": NOW - timedelta(days=5)},
        ] if fact_order == "normal" else [
            {"kind": "buying_intent", "occurred_at": NOW - timedelta(days=5)},
            {"kind": "pricing_discussed", "occurred_at": NOW - timedelta(days=3)},
        ],
        baselines=(
            {"reply_cadence": 2.5, "historical_engagement": 0.75}
            if fact_order == "normal"
            else {"historical_engagement": 0.75, "reply_cadence": 2.5}
        ),
        edge_count=2,
        neighbor_obs=(
            {"competitor", "pricing_discussed"}
            if fact_order == "normal"
            else set(reversed(("competitor", "pricing_discussed")))
        ),
        neighbor_facts={"deal.status": status},
    )


def test_legacy_adapter_exactly_matches_evaluate_and_score_rule_when_rule_fires():
    context = _legacy_context()
    expected_match = evaluate(context, STALLED_RULE, NOW)
    expected_score, expected_inputs = score_rule(context, STALLED_RULE, NOW, SCORING)

    adapted = reason_legacy_rule(
        org_id="org_1",
        context=context,
        rule=STALLED_RULE,
        evaluation_time=NOW,
        scoring=SCORING,
        config_snapshot_id="cfg_sales_v1",
        pack_id="sales",
        pack_version=SALES_V1["version"],
        play_config=SALES_V1["plays"][STALLED_RULE.play],
        graph_version=11,
    )

    assert expected_match is True
    assert adapted.matched is expected_match
    assert adapted.score == expected_score
    assert adapted.score_inputs == expected_inputs
    assert adapted.execution.decision.outcome == DecisionOutcome.DECISION
    assert adapted.execution.selected_candidate.play_id == STALLED_RULE.play


def test_legacy_adapter_exactly_matches_non_match_and_does_not_manufacture_a_score():
    context = _legacy_context(status="won")
    expected_match = evaluate(context, STALLED_RULE, NOW)

    adapted = reason_legacy_rule(
        org_id="org_1",
        context=context,
        rule=STALLED_RULE,
        evaluation_time=NOW,
        scoring=SCORING,
        pack_id="sales",
        pack_version=SALES_V1["version"],
        play_config=SALES_V1["plays"][STALLED_RULE.play],
    )

    assert expected_match is False
    assert adapted.matched is expected_match
    assert adapted.score == 0
    assert adapted.score_inputs == {"U": 0, "I": 0, "R": 0, "C": 0, "terms_bp": 0}
    assert adapted.legacy_result.metrics == {}
    assert adapted.execution.candidates == ()
    assert adapted.execution.decision.outcome == DecisionOutcome.NO_ACTION
    assert adapted.execution.authorizes_delivery is False


def test_legacy_score_and_confidence_gate_is_a_traced_layer4_constraint():
    scoring = {**SCORING, "gate": {**SCORING["gate"], "s_min": 90}}
    adapted = reason_legacy_rule(
        org_id="org_1", context=_legacy_context(), rule=STALLED_RULE,
        evaluation_time=NOW, scoring=scoring, pack_id="sales",
        pack_version=SALES_V1["version"],
        play_config=SALES_V1["plays"][STALLED_RULE.play])

    assert adapted.matched is True
    assert adapted.execution.decision.outcome == DecisionOutcome.BLOCKED
    assert adapted.execution.authorizes_delivery is False
    assert any(check.reason_code == "legacy_score_gate_failed"
               for candidate in adapted.execution.candidates for check in candidate.checks)


def test_legacy_gate_configuration_rejects_fractional_thresholds_without_truncation():
    scoring = {**SCORING, "gate": {**SCORING["gate"], "s_min": 55.5}}

    with pytest.raises(ValueError, match="integer"):
        reason_legacy_rule(
            org_id="org_1", context=_legacy_context(), rule=STALLED_RULE,
            evaluation_time=NOW, scoring=scoring, pack_id="sales",
            pack_version=SALES_V1["version"],
            play_config=SALES_V1["plays"][STALLED_RULE.play])


def test_legacy_float_normalization_is_recursive_exact_and_canonical():
    normalized = semantic_legacy_value({
        "ratio": 0.1,
        "nested": [1.25, {"confidence": 0.9}],
        "unordered": {2.5, 1.5},
    })

    assert normalized["ratio"] == Decimal("0.1")
    assert normalized["nested"] == (
        Decimal("1.25"), {"confidence": Decimal("0.9")})
    assert normalized["unordered"] == (Decimal("1.5"), Decimal("2.5"))
    canonical = canonicalize(normalized)
    assert canonical["ratio"] == {"$decimal": "0.1"}

    with pytest.raises(ValueError, match="non-finite"):
        semantic_legacy_value(math.nan)
    with pytest.raises(ValueError, match="non-finite"):
        semantic_legacy_value(math.inf)


def _reverse_mappings(value):
    if isinstance(value, dict):
        return {key: _reverse_mappings(value[key]) for key in reversed(tuple(value))}
    if isinstance(value, list):
        return [_reverse_mappings(item) for item in value]
    return value


def test_legacy_context_and_capability_ids_ignore_mapping_set_and_observation_order():
    normal_context = legacy_context_snapshot(
        org_id="org_1", context=_legacy_context(fact_order="normal"),
        rule=STALLED_RULE, evaluation_time=NOW, graph_version=11)
    reordered_context = legacy_context_snapshot(
        org_id="org_1", context=_legacy_context(fact_order="reversed"),
        rule=STALLED_RULE, evaluation_time=NOW, graph_version=11)

    assert normal_context.context_snapshot_id == reordered_context.context_snapshot_id
    assert normal_context.semantic_hash == reordered_context.semantic_hash

    play = SALES_V1["plays"][STALLED_RULE.play]
    normal_capability = legacy_capability_manifest(
        rule=STALLED_RULE, scoring=SCORING, pack_id="sales",
        pack_version=SALES_V1["version"], play_config=play)
    reordered_capability = legacy_capability_manifest(
        rule=STALLED_RULE, scoring=_reverse_mappings(SCORING), pack_id="sales",
        pack_version=SALES_V1["version"], play_config=_reverse_mappings(play))

    assert normal_capability.capability_snapshot_id == reordered_capability.capability_snapshot_id
    assert normal_capability.semantic_hash == reordered_capability.semantic_hash


def _native_context(*, alternate_stakeholder_verified: bool = True,
                    mapping_order: str = "normal") -> ContextSnapshot:
    facts = [
        ("deal.status", {"value": "open", "confidence_bp": 9_500, "src_count": 2}),
        ("deal.value", {"value": 500_000, "confidence_bp": 9_500, "src_count": 2}),
        ("derived.engagement", {"value_bp": 4_000, "confidence_bp": 8_500,
                                "src_count": 2}),
        ("thread.last_inbound", {"value": (NOW - timedelta(days=10)).isoformat(),
                                 "confidence_bp": 9_000, "src_count": 2}),
        ("relationship.verified_stakeholder_count", {"value": 2}),
    ]
    neighbors = [
        ("contact.verified_recipient", True),
        ("account.alternate_stakeholder_verified", alternate_stakeholder_verified),
    ]
    evidence = [
        EvidenceRef("ev_status", "deal.status", "open", confidence_bp=9_500,
                    authority_rank=3),
        EvidenceRef("ev_engagement", "derived.engagement", 4_000, confidence_bp=8_500,
                    authority_rank=2),
        EvidenceRef("ev_inbound", "thread.last_inbound",
                    (NOW - timedelta(days=10)).isoformat(), confidence_bp=9_000,
                    authority_rank=2),
    ]
    if mapping_order == "reversed":
        facts.reverse()
        neighbors.reverse()
        evidence.reverse()
    return ContextSnapshot(
        org_id="org_1",
        graph_version=21,
        root_entity_id="deal_1",
        root_entity_type="deal",
        evaluation_time=NOW,
        selector_version="deal_cooling.selector.v1",
        facts=dict(facts),
        neighbor_facts=dict(neighbors),
        neighbor_observations=(
            ("pricing_discussed", "buying_intent")
            if mapping_order == "normal" else ("buying_intent", "pricing_discussed")
        ),
        edge_count=2,
        evidence=tuple(evidence),
    )


def _native_request(*, context=None, mode=ExecutionMode.SHADOW) -> ReasoningRequest:
    return ReasoningRequest(
        org_id="org_1",
        capability=DEAL_COOLING_V1,
        context=context or _native_context(),
        evaluation_time=NOW,
        trigger_kind="email.received",
        trigger_ref="event_1",
        mode=mode,
        config_snapshot_id="cfg_deal_cooling_v1",
    )


def test_native_context_id_ignores_mapping_evidence_and_set_like_order():
    normal = _native_context(mapping_order="normal")
    reordered = _native_context(mapping_order="reversed")

    assert normal.context_snapshot_id == reordered.context_snapshot_id
    assert normal.semantic_hash == reordered.semantic_hash


def test_native_deal_cooling_produces_three_constrained_ranked_plays_in_shadow():
    orchestrator = ReasoningOrchestrator(default_registry())
    request = _native_request()

    first = orchestrator.execute(request)
    replay = orchestrator.execute(request)

    assert first.semantic_hash == replay.semantic_hash
    assert first.decision.outcome == DecisionOutcome.DECISION
    assert first.trace.mode == ExecutionMode.SHADOW
    assert first.authorizes_delivery is False
    assert len(first.candidates) == 3
    assert {candidate.play_id for candidate in first.candidates} == {
        "restore_momentum", "multithread_account", "clarify_next_step"}
    assert all(candidate.disposition == CandidateDisposition.ELIGIBLE
               for candidate in first.candidates)
    assert [candidate.rank_position for candidate in first.candidates] == [1, 2, 3]
    assert [candidate.utility_bp for candidate in first.candidates] == sorted(
        (candidate.utility_bp for candidate in first.candidates), reverse=True)
    assert first.selected_candidate == first.candidates[0]
    assert first.selected_candidate.play_id == "restore_momentum"
    assert all(candidate.checks for candidate in first.candidates)
    assert all(check.outcome.value in {"pass", "warn"}
               for candidate in first.candidates for check in candidate.checks)
    assert all(type(candidate.utility_bp) is int for candidate in first.candidates)
    confidence = first.result_by_id["core.confidence"]
    assert confidence.metrics["independent_evidence_groups"] == 1
    assert confidence.metrics["evidence_coverage_bp"] == 2_500


def test_native_constraint_eliminates_an_ineligible_play_before_ranking():
    execution = ReasoningOrchestrator(default_registry()).execute(_native_request(
        context=_native_context(alternate_stakeholder_verified=False)))
    by_play = {candidate.play_id: candidate for candidate in execution.candidates}

    blocked = by_play["multithread_account"]
    assert blocked.disposition == CandidateDisposition.ELIMINATED
    assert blocked.rank_position is None
    assert any(check.reason_code == "precondition_failed"
               and check.outcome.value == "eliminate" for check in blocked.checks)
    assert execution.selected_candidate.play_id != blocked.play_id
    assert execution.authorizes_delivery is False


def test_native_runtime_adapter_uses_root_deal_status_and_never_requires_a_duplicate_neighbor():
    node = NodeContext(
        node_id="deal_1",
        node_type="deal",
        facts={
            "deal.status": {"value": "open", "confidence": 0.95},
            "deal.value": {"value": 500_000, "confidence": 0.95},
            "derived.engagement": {"value": 0.4, "confidence": 0.85},
            "thread.last_inbound": {
                "value": (NOW - timedelta(days=10)).isoformat(), "confidence": 0.9},
            "relationship.verified_stakeholder_count": {"value": 2, "confidence": 1},
        },
        neighbor_facts={
            "contact.verified_recipient": True,
            "account.alternate_stakeholder_verified": True,
        },
        edge_count=2,
    )

    snapshot = native_context_snapshot(
        org_id="org_1", context=node, capability=DEAL_COOLING_V1,
        evaluation_time=NOW, graph_version=22)
    execution = reason_native_capability(
        org_id="org_1", context=node, capability=DEAL_COOLING_V1,
        evaluation_time=NOW, graph_version=22,
        config_snapshot_id="cfg_sales", mode=ExecutionMode.SHADOW)

    assert snapshot.facts["deal.status"]["value"] == "open"
    assert "deal.status" not in snapshot.neighbor_facts
    assert execution.decision.outcome == DecisionOutcome.DECISION
    assert execution.authorizes_delivery is False


def test_native_evidence_policy_eliminates_every_play_when_no_evidence_exists():
    context = _native_context()
    context = ContextSnapshot(
        org_id=context.org_id, graph_version=context.graph_version,
        root_entity_id=context.root_entity_id, root_entity_type=context.root_entity_type,
        evaluation_time=context.evaluation_time, selector_version=context.selector_version,
        facts=context.facts, neighbor_facts=context.neighbor_facts,
        neighbor_observations=context.neighbor_observations, edge_count=context.edge_count,
        evidence=(),
    )

    execution = ReasoningOrchestrator(default_registry()).execute(
        _native_request(context=context))

    assert execution.decision.outcome == DecisionOutcome.BLOCKED
    assert all(candidate.disposition == CandidateDisposition.ELIMINATED
               for candidate in execution.candidates)


def test_native_evidence_policy_rejects_unrelated_uncited_evidence():
    base = _native_context()
    context = ContextSnapshot(
        org_id=base.org_id, graph_version=base.graph_version,
        root_entity_id=base.root_entity_id, root_entity_type=base.root_entity_type,
        evaluation_time=base.evaluation_time, selector_version=base.selector_version,
        facts={**base.facts, "totally.unrelated": "noise"},
        neighbor_facts=base.neighbor_facts,
        neighbor_observations=base.neighbor_observations, edge_count=base.edge_count,
        evidence=(EvidenceRef("ev_unrelated", "totally.unrelated", "noise"),),
    )

    execution = ReasoningOrchestrator(default_registry()).execute(
        _native_request(context=context))

    assert execution.decision.outcome == DecisionOutcome.BLOCKED
    assert all(candidate.evidence_ids == () for candidate in execution.candidates)
    assert all(any(check.reason_code == "evidence_required"
                   for check in candidate.checks) for candidate in execution.candidates)
    assert all(any(check.reason_code == "evidence_required" for check in candidate.checks)
               for candidate in execution.candidates)


def test_native_recipient_policy_eliminates_a_play_without_a_verification_guard():
    restore, *others = DEAL_COOLING_V1.plays
    unsafe_restore = replace(
        restore,
        preconditions=tuple(condition for condition in restore.preconditions
                            if "verified" not in str(condition.get("field") or "")),
    )
    capability = replace(DEAL_COOLING_V1, plays=(unsafe_restore, *others))
    request = ReasoningRequest(
        org_id="org_1", capability=capability, context=_native_context(),
        evaluation_time=NOW, trigger_kind="email.received", mode=ExecutionMode.SHADOW)

    execution = ReasoningOrchestrator(default_registry()).execute(request)
    candidate = next(item for item in execution.candidates
                     if item.play_id == "restore_momentum")

    assert candidate.disposition == CandidateDisposition.ELIMINATED
    assert any(check.reason_code == "verified_recipient_guard_missing"
               for check in candidate.checks)


def test_native_recipient_policy_rejects_a_missing_effect_declaration_at_load():
    restore, *others = DEAL_COOLING_V1.plays
    unsafe_restore = replace(
        restore,
        metadata={key: value for key, value in restore.metadata.items()
                  if key != "external_recipient_required"},
    )

    with pytest.raises(ValueError, match="external_recipient_required"):
        replace(DEAL_COOLING_V1, plays=(unsafe_restore, *others))
