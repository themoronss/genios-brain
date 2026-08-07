"""Audited capability for composing several signal concerns into one deal verdict."""

from __future__ import annotations

from genios_engine.contracts.reasoning import (
    CapabilityManifest,
    FailurePolicy,
    Goal,
    PlayDefinition,
    ReasonerSpec,
)


def build_deal_health_manifest() -> CapabilityManifest:
    composition = ReasonerSpec(
        "core.signal_composition", "1.0.0",
        output_kind="compound_signal_finding",
        required_fields=("signals.open",),
        failure_policy=FailurePolicy.REQUIRED,
        gating=True,
    )
    constraint = ReasonerSpec(
        "core.constraint", "1.0.0",
        dependencies=("core.signal_composition",),
        input_kind="candidate_plays",
        output_kind="candidate_checks",
        failure_policy=FailurePolicy.REQUIRED,
    )
    priority = ReasonerSpec(
        "core.priority", "1.0.0",
        dependencies=("core.signal_composition", "core.constraint"),
        config={"source_reasoner": "core.signal_composition"},
        failure_policy=FailurePolicy.REQUIRED,
    )
    confidence = ReasonerSpec(
        "core.confidence", "1.0.0",
        dependencies=("core.signal_composition",),
        config={"source_reasoner": "core.signal_composition"},
        failure_policy=FailurePolicy.REQUIRED,
    )
    planning = ReasonerSpec(
        "core.planning", "1.0.0",
        dependencies=("core.constraint", "core.priority", "core.confidence"),
        input_kind="ranked_candidates",
        output_kind="planning_checks",
        failure_policy=FailurePolicy.REQUIRED,
    )
    review = PlayDefinition(
        "review_deal", "1.0.0", "Review the compound deal risk",
        steps=(
            "Review the independently audited concerns and their source evidence.",
            "Choose the safest next step with the deal owner.",
            "Leave any outreach or CRM update for explicit human approval.",
        ),
        read_only=True,
        impact_bp=8_000,
        success_probability_bp=6_500,
        effort_bp=2_000,
        risk_bp=1_000,
        tags=("human_approval", "review"),
        success_events=("risk_reviewed", "next_step_recorded", "stage_advanced"),
        window_days=14,
        metadata={"artifact_kind": "deal_risk_review",
                  "execution_boundary": "human_approval_required",
                  "external_recipient_required": False},
    )
    monitor = PlayDefinition(
        "monitor_deal", "1.0.0", "Monitor the verified concerns",
        steps=(
            "Confirm the concerns are still current.",
            "Set a bounded internal review window.",
            "Escalate to the deal owner if the evidence worsens.",
        ),
        read_only=True,
        impact_bp=4_500,
        success_probability_bp=4_000,
        effort_bp=500,
        risk_bp=200,
        tags=("human_approval", "monitor"),
        success_events=("risk_cleared", "risk_reviewed"),
        window_days=7,
        metadata={"artifact_kind": "deal_risk_monitor",
                  "execution_boundary": "human_approval_required",
                  "external_recipient_required": False},
    )
    return CapabilityManifest(
        capability_id="sales.deal_health",
        version="1.0.0",
        domain="sales",
        root_entity_type="deal",
        goal=Goal(
            "sales.review_compound_deal_risk",
            "Resolve a compound deal risk without losing its individual evidence trails.",
            success_criteria=("A verified next step is recorded or the compound risk clears.",),
            constraints=("Never send or mutate an external system autonomously.",),
        ),
        reasoners=(composition, constraint, priority, confidence, planning),
        plays=(review, monitor),
        required_fields=("signals.open",),
        policies=("read_only", "human_approval_required", "evidence_required"),
        live_delivery_enabled=True,
        do_nothing_consequence=(
            "Several verified concerns may compound while the deal remains unreviewed."
        ),
        expiry_hours=72,
        metadata={"schema": "capability.v1", "source": "audited_signal_composition"},
    )


DEAL_HEALTH_V1 = build_deal_health_manifest()

__all__ = ["DEAL_HEALTH_V1", "build_deal_health_manifest"]
