"""Compile one legacy pack rule into a versioned Layer 4 capability."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from genios_engine.contracts.reasoning import (
    CapabilityManifest,
    FailurePolicy,
    Goal,
    PlayDefinition,
    ReasonerSpec,
)
from genios_engine.platform.canonical import semantic_hash
from genios_engine.reason.rules import Rule
from genios_engine.reason.reasoners.common import integer

from .legacy_context import semantic_legacy_value

_REASONER_VERSION = "1.0.0"


def legacy_capability_manifest(*, rule: Rule, scoring: dict[str, Any],
                               pack_id: str = "legacy", pack_version: str = "1",
                               play_config: dict[str, Any] | None = None,
                               config_snapshot_id: str | None = None) -> CapabilityManifest:
    """Create a safe strangler capability while preserving the legacy match/score semantics."""
    play_id = str(rule.play or f"review_{rule.id}")
    play_data = play_config or {}
    rule_config = semantic_legacy_value(asdict(rule))
    scoring_config = semantic_legacy_value(scoring)
    effective_hash = semantic_hash({
        "rule": rule_config,
        "scoring": scoring_config,
        "play": semantic_legacy_value(play_data),
    })
    snapshot_marker = (semantic_hash(config_snapshot_id)[:16]
                       if config_snapshot_id else "base")
    artifact = str(play_data.get("artifact") or play_id)
    success = play_data.get("success_signal")
    window_days = integer(play_data.get("window_days", 7), "play.window_days")
    legacy = ReasonerSpec(
        reasoner_id="legacy.rule",
        version=_REASONER_VERSION,
        output_kind="legacy_rule_finding",
        latency_budget_ms=50,
        failure_policy=FailurePolicy.REQUIRED,
        gating=True,
        config={
            "rule": rule_config,
            "scoring": scoring_config,
        },
    )
    gate_config = scoring_config.get("gate") or {}
    offsets = scoring_config.get("rule_offsets") or {}
    base_score_min = integer(gate_config.get("s_min", 55), "gate.s_min")
    score_min = max(40, min(90, base_score_min + integer(
        offsets.get(rule.id, 0), f"rule_offsets.{rule.id}")))
    score_gate = ReasonerSpec(
        reasoner_id="legacy.score_gate",
        version=_REASONER_VERSION,
        input_kind="reasoner_results",
        output_kind="candidate_checks",
        dependencies=("legacy.rule",),
        failure_policy=FailurePolicy.REQUIRED,
        config={"score_min": score_min,
                "confidence_min": integer(gate_config.get("c_min", 60), "gate.c_min")},
    )
    constraint = ReasonerSpec(
        reasoner_id="core.constraint",
        version=_REASONER_VERSION,
        input_kind="candidate_plays",
        output_kind="candidate_checks",
        dependencies=("legacy.rule", "legacy.score_gate"),
        failure_policy=FailurePolicy.REQUIRED,
    )
    priority = ReasonerSpec(
        reasoner_id="core.priority",
        version=_REASONER_VERSION,
        dependencies=("legacy.rule", "core.constraint"),
        failure_policy=FailurePolicy.REQUIRED,
        config={"source_reasoner": "legacy.rule"},
    )
    confidence = ReasonerSpec(
        reasoner_id="core.confidence",
        version=_REASONER_VERSION,
        dependencies=("legacy.rule",),
        failure_policy=FailurePolicy.REQUIRED,
        config={"source_reasoner": "legacy.rule"},
    )
    planning = ReasonerSpec(
        reasoner_id="core.planning",
        version=_REASONER_VERSION,
        input_kind="ranked_candidates",
        output_kind="planning_checks",
        dependencies=("core.constraint", "core.priority", "core.confidence"),
        failure_policy=FailurePolicy.REQUIRED,
    )
    play = PlayDefinition(
        play_id=play_id,
        version=str(rule.version),
        label=play_id.replace("_", " ").title(),
        steps=(f"Prepare {artifact.replace('_', ' ')} for human review.",),
        read_only=True,
        success_events=((str(success),) if success else ()),
        window_days=window_days,
        metadata={
            "artifact_kind": artifact,
            "legacy_play": True,
            "execution_boundary": "human_approval_required",
            # This adapter creates a review artifact only; delivery owns recipient selection.
            "external_recipient_required": False,
        },
    )
    return CapabilityManifest(
        capability_id=f"legacy.{pack_id}.{rule.id}",
        # Tenant overlays may change effective scoring without publishing a new pack.  Binding the
        # effective config snapshot into the adapter version preserves immutable capability bytes.
        version=f"{pack_version}-{snapshot_marker}-{effective_hash}",
        domain=str(pack_id),
        root_entity_type=rule.scope,
        goal=Goal(
            goal_id=f"legacy.{rule.id}.goal",
            statement=f"Resolve the verified {rule.reason_code.replace('_', ' ')} condition.",
            success_criteria=((f"Observe {success} inside the declared window.",)
                              if success else ()),
            constraints=("Produce a read-only recommendation; do not execute it.",),
        ),
        reasoners=(legacy, score_gate, constraint, priority, confidence, planning),
        plays=(play,),
        policies=("read_only", "human_approval_required"),
        do_nothing_consequence=(
            f"The {rule.reason_code.replace('_', ' ')} condition may remain unresolved."
        ),
        expiry_hours=max(1, min(8_760, integer(rule.cooldown_hours, "rule.cooldown_hours"))),
        metadata={
            "adapter": "legacy.rule.v1",
            "pack_id": str(pack_id),
            "pack_version": str(pack_version),
            "config_snapshot_id": str(config_snapshot_id or ""),
            "rule_id": rule.id,
            "effective_reasoning_hash": effective_hash,
        },
    )


__all__ = ["legacy_capability_manifest"]
