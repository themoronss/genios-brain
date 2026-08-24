"""``sales.deal_cooling`` — the first native GeniOS capability.

This manifest contains expertise and deterministic parameters only.  It does
not perform graph IO, invoke an LLM, register itself globally, send a message,
or mutate a CRM.  The Layer 4 orchestrator selects the declared reasoners and
the Layer 5 boundary may turn the winning read-only play into a human-approved
draft or handoff.
"""

from __future__ import annotations

from genios_engine.contracts.reasoning import (
    CapabilityManifest,
    FailurePolicy,
    Goal,
    IntelligenceObject,
    PlayDefinition,
    ReasonerSpec,
)


CAPABILITY_ID = "sales.deal_cooling"
CAPABILITY_VERSION = "1.0.0"
REASONER_VERSION = "1.0.0"
PLAY_VERSION = "1.0.0"


def _intelligence_objects() -> tuple[IntelligenceObject, ...]:
    """Compiled expertise slices loaded only for this capability."""

    return (
        IntelligenceObject(
            object_id="sales.cadence_deviation",
            version="1.0.0",
            capability_id=CAPABILITY_ID,
            purpose=(
                "Determine whether current two-way deal engagement is materially below "
                "the relationship's established cadence."
            ),
            required_context=("derived.engagement", "thread.last_inbound"),
            relationships={
                "influences": ("sales.deal_momentum_risk", "sales.next_step_quality"),
            },
            knowledge={
                "universal": {
                    "cooling_threshold_bp": 5_000,
                    "maximum_observation_window_days": 28,
                },
                "organization_overlay": {"source": "tenant_policy_snapshot"},
                "behavioral_overlay": {"source": "owner_cadence_baseline"},
                "adaptive_overlay": {
                    "source": "observed_outcomes",
                    "minimum_samples_before_override": 20,
                },
            },
            metadata={"reasoner": "core.temporal", "value_scale": "basis_points"},
        ),
        IntelligenceObject(
            object_id="sales.stakeholder_coverage",
            version="1.0.0",
            capability_id=CAPABILITY_ID,
            purpose=(
                "Measure whether an open deal depends on too few verified customer "
                "relationships and identify concentration risk."
            ),
            required_context=("deal.status", "relationship.verified_stakeholder_count"),
            relationships={"influences": ("sales.deal_momentum_risk",)},
            knowledge={
                "universal": {
                    "target_verified_relationships": 3,
                    "single_threaded_count": 1,
                },
                "organization_overlay": {"source": "tenant_sales_process"},
                "behavioral_overlay": {"source": "owner_relationship_history"},
                "adaptive_overlay": {
                    "source": "observed_outcomes",
                    "minimum_samples_before_override": 20,
                },
            },
            metadata={"reasoner": "core.relationship"},
        ),
        IntelligenceObject(
            object_id="sales.deal_momentum_risk",
            version="1.0.0",
            capability_id=CAPABILITY_ID,
            purpose=(
                "Combine cadence loss and stakeholder concentration into an explicit, "
                "bounded do-nothing risk."
            ),
            required_context=("derived.engagement", "deal.status", "deal.value"),
            relationships={
                "depends_on": (
                    "sales.cadence_deviation",
                    "sales.stakeholder_coverage",
                )
            },
            knowledge={
                "universal": {
                    "base_risk_bp": 1_000,
                    "cadence_weight_bp": 6_000,
                    "relationship_weight_bp": 4_000,
                },
                "organization_overlay": {"source": "tenant_deal_policy"},
                "adaptive_overlay": {"source": "observed_outcomes"},
            },
            metadata={"reasoner": "core.risk", "value_scale": "basis_points"},
        ),
        IntelligenceObject(
            object_id="sales.next_step_quality",
            version="1.0.0",
            capability_id=CAPABILITY_ID,
            purpose=(
                "Determine whether the deal has a concrete next action with an owner and "
                "date, without confusing a vague intention for a committed next step."
            ),
            required_context=("deal.next_step", "calendar.next_meeting_at"),
            relationships={"influences": ("sales.deal_momentum_risk",)},
            knowledge={
                "universal": {
                    "required_components": ("action", "owner", "date"),
                },
                "organization_overlay": {"source": "tenant_sales_process"},
                "behavioral_overlay": {"source": "owner_working_style"},
                "adaptive_overlay": {"source": "observed_outcomes"},
            },
            metadata={"reasoner": "core.planning"},
        ),
    )


def _reasoners() -> tuple[ReasonerSpec, ...]:
    """The capability's complete, version-pinned reasoning DAG."""

    temporal = ReasonerSpec(
        reasoner_id="core.temporal",
        version=REASONER_VERSION,
        input_kind="context_snapshot",
        output_kind="temporal_finding",
        required_fields=("derived.engagement", "thread.last_inbound"),
        latency_budget_ms=25,
        failure_policy=FailurePolicy.REQUIRED,
        gating=True,
        config={
            "engagement_field": "derived.engagement",
            "timestamp_field": "thread.last_inbound",
            "max_engagement_bp": 5_000,
            "play_adjustments": {
                "restore_momentum": {"urgency": 1_200, "success": 600},
                "clarify_next_step": {"urgency": 500},
            },
        },
    )
    relationship = ReasonerSpec(
        reasoner_id="core.relationship",
        version=REASONER_VERSION,
        input_kind="context_snapshot",
        output_kind="relationship_finding",
        required_fields=("deal.status", "relationship.verified_stakeholder_count"),
        latency_budget_ms=25,
        failure_policy=FailurePolicy.REQUIRED,
        gating=True,
        config={
            "status_field": "deal.status",
            "status_location": "root",
            "status_value": "open",
            "relationship_count_field": "relationship.verified_stakeholder_count",
            "target_relationships": 3,
            "multithread_play_id": "multithread_account",
        },
    )
    risk = ReasonerSpec(
        reasoner_id="core.risk",
        version=REASONER_VERSION,
        input_kind="reasoner_results",
        output_kind="risk_finding",
        dependencies=("core.temporal", "core.relationship"),
        latency_budget_ms=20,
        failure_policy=FailurePolicy.REQUIRED,
        config={
            "temporal_reasoner": "core.temporal",
            "relationship_reasoner": "core.relationship",
            "base_risk_bp": 1_000,
            "play_risk_reduction_bp": {
                "restore_momentum": 1_800,
                "multithread_account": 1_600,
                "clarify_next_step": 1_200,
            },
        },
    )
    constraint = ReasonerSpec(
        reasoner_id="core.constraint",
        version=REASONER_VERSION,
        input_kind="candidate_plays",
        output_kind="candidate_checks",
        dependencies=("core.temporal", "core.relationship"),
        latency_budget_ms=25,
        failure_policy=FailurePolicy.REQUIRED,
        config={"blocked_play_ids": ()},
    )
    priority = ReasonerSpec(
        reasoner_id="core.priority",
        version=REASONER_VERSION,
        input_kind="reasoner_results",
        output_kind="priority_inputs",
        dependencies=("core.temporal", "core.risk", "core.constraint"),
        latency_budget_ms=20,
        failure_policy=FailurePolicy.REQUIRED,
        config={"source_reasoner": "core.temporal"},
    )
    confidence = ReasonerSpec(
        reasoner_id="core.confidence",
        version=REASONER_VERSION,
        input_kind="context_and_results",
        output_kind="confidence_decomposition",
        dependencies=("core.risk",),
        required_fields=(
            "deal.status",
            "deal.value",
            "derived.engagement",
            "thread.last_inbound",
        ),
        latency_budget_ms=25,
        failure_policy=FailurePolicy.REQUIRED,
        config={},
    )
    planning = ReasonerSpec(
        reasoner_id="core.planning",
        version=REASONER_VERSION,
        input_kind="ranked_candidates",
        output_kind="planning_checks",
        dependencies=("core.constraint", "core.priority", "core.confidence"),
        latency_budget_ms=20,
        failure_policy=FailurePolicy.REQUIRED,
        config={},
    )
    return temporal, relationship, risk, constraint, priority, confidence, planning


def _plays() -> tuple[PlayDefinition, ...]:
    """Safe alternatives with observable outcomes—not interaction proxies."""

    return (
        PlayDefinition(
            play_id="restore_momentum",
            version=PLAY_VERSION,
            label="Restore momentum with a value-led follow-up",
            steps=(
                "Review the latest verified customer priority and cooling evidence.",
                "Draft a concise value-led follow-up grounded in that priority.",
                "Propose one concrete next step and leave the draft for human approval.",
            ),
            preconditions=(
                {"field": "deal.status", "op": "=", "value": "open"},
                {
                    "field": "contact.verified_recipient",
                    "neighbor": True,
                    "op": "=",
                    "value": True,
                },
            ),
            read_only=True,
            impact_bp=8_000,
            success_probability_bp=5_500,
            effort_bp=2_000,
            risk_bp=1_000,
            tags=("draft", "human_approval", "re_engagement"),
            success_events=("prospect_reply", "meeting_booked", "stage_advanced"),
            window_days=14,
            metadata={
                "artifact_kind": "draft_reengagement_email",
                "execution_boundary": "human_approval_required",
                "external_recipient_required": True,
            },
        ),
        PlayDefinition(
            play_id="multithread_account",
            version=PLAY_VERSION,
            label="Build a second verified stakeholder path",
            steps=(
                "Identify one relevant, verified stakeholder connected to the deal.",
                "Draft a context-preserving introduction request or warm outreach note.",
                "Present the draft and evidence to the deal owner for approval.",
            ),
            preconditions=(
                {"field": "deal.status", "op": "=", "value": "open"},
                {
                    "field": "account.alternate_stakeholder_verified",
                    "neighbor": True,
                    "op": "=",
                    "value": True,
                },
            ),
            read_only=True,
            impact_bp=7_500,
            success_probability_bp=4_000,
            effort_bp=4_000,
            risk_bp=2_500,
            tags=("draft", "human_approval", "relationship"),
            success_events=("stakeholder_added", "prospect_reply", "meeting_booked"),
            window_days=21,
            metadata={
                "artifact_kind": "draft_multithread_outreach",
                "execution_boundary": "human_approval_required",
                "external_recipient_required": True,
            },
        ),
        PlayDefinition(
            play_id="clarify_next_step",
            version=PLAY_VERSION,
            label="Clarify the next step, owner, and date",
            steps=(
                "Summarize the last mutually verified agreement and unresolved item.",
                "Draft a specific next step with a proposed owner and date.",
                "Leave the draft and structured CRM suggestion for human approval.",
            ),
            preconditions=(
                {"field": "deal.status", "op": "=", "value": "open"},
                {"field": "deal.next_step", "op": "absent"},
            ),
            read_only=True,
            impact_bp=6_500,
            success_probability_bp=6_000,
            effort_bp=1_500,
            risk_bp=700,
            tags=("draft", "human_approval", "next_step"),
            success_events=("next_step_recorded", "meeting_booked", "stage_advanced"),
            window_days=7,
            metadata={
                "artifact_kind": "draft_next_step_confirmation",
                "execution_boundary": "human_approval_required",
                "external_recipient_required": False,
            },
        ),
    )


def build_deal_cooling_manifest() -> CapabilityManifest:
    """Construct and validate a fresh immutable manifest instance."""

    return CapabilityManifest(
        capability_id=CAPABILITY_ID,
        version=CAPABILITY_VERSION,
        domain="sales",
        root_entity_type="deal",
        goal=Goal(
            goal_id="sales.restore_healthy_deal_momentum",
            statement=(
                "Restore healthy momentum on a valuable open deal using the safest "
                "evidence-backed next action."
            ),
            success_criteria=(
                "A prospect replies, a meeting is booked, a next step is recorded, or the deal advances.",
                "The observed outcome is linked to the selected play inside its declared window.",
            ),
            constraints=(
                "No external message is sent without human approval.",
                "No recipient, date, amount, or customer claim may be inferred without evidence.",
            ),
        ),
        reasoners=_reasoners(),
        plays=_plays(),
        required_fields=(
            "deal.status",
            "deal.value",
            "derived.engagement",
            "thread.last_inbound",
        ),
        intelligence_objects=_intelligence_objects(),
        ranking_weights={
            "impact": 35,
            "success": 30,
            "urgency": 20,
            "effort": 10,
            "risk": 5,
        },
        policies=(
            "read_only",
            "human_approval_required",
            "evidence_required",
            "no_unverified_recipient",
        ),
        live_delivery_enabled=False,
        do_nothing_consequence=(
            "The deal may continue losing momentum, become more dependent on one contact, "
            "and slip before the team receives another explicit customer signal."
        ),
        expiry_hours=72,
        metadata={
            "schema": "capability.v1",
            "activation": "shadow_first",
            "triggers": (
                "email.received",
                "crm.deal.updated",
                "calendar.event.changed",
                "schedule.daily",
            ),
            "context_selector": {
                "root": "deal",
                "max_hops": 2,
                "max_nodes": 50,
                "relationships": ("account", "owner", "contacts", "meetings"),
                "optional_fields": (
                    "deal.next_step",
                    "calendar.next_meeting_at",
                    "contact.verified_recipient",
                ),
            },
            "outcome_semantics": {
                "interaction_is_not_outcome": True,
                "allowed_statuses": (
                    "success",
                    "failure",
                    "partial",
                    "ambiguous",
                    "expired",
                ),
            },
            "numeric_scale": "integer_basis_points",
        },
    )


DEAL_COOLING_V1 = build_deal_cooling_manifest()
DEAL_COOLING_CAPABILITY = DEAL_COOLING_V1


__all__ = [
    "CAPABILITY_ID",
    "CAPABILITY_VERSION",
    "DEAL_COOLING_CAPABILITY",
    "DEAL_COOLING_V1",
    "build_deal_cooling_manifest",
]
