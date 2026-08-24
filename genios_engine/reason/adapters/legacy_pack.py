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
from genios_engine.reason.decision_maker import CONFIDENCE_FLOOR_KEY
from genios_engine.reason.rules import Rule
from genios_engine.reason.reasoners.common import integer

from .legacy_context import semantic_legacy_value

_REASONER_VERSION = "1.0.0"

#: The SHAPE this adapter produces. Bumped whenever the manifest it builds changes — a different
#: reasoner DAG, different plays, different policies — because the capability version must
#: distinguish them.
#:
#: `version` was `{pack_version}-{snapshot}-{effective_hash}`: the pack, the config snapshot and
#: the effective scoring. None of those moves when the ADAPTER changes, so widening the DAG
#: produced different manifest bytes under an identical version and the immutability guard
#: correctly refused the run. The guard was right; the version was incomplete.
#:
#: v2: + core.temporal and core.relationship (optional), + the explicit wait play, + real score
#:     components, + the pack confidence floor, + authority decoupled from cooldown.
_ADAPTER_SHAPE = "a3"  # a3: +core.alternative, +core.validation — the DAG changed, so the tag
                       # must too, or the immutability guard correctly rejects the new bytes
                       # under a version it already has different bytes on file for.


#: A prescriptive rule asserts what to DO; a predictive one warns what MAY happen. Acting on the
#: first is worth more when it is right, and the pack author already made that call per rule.
_LEVEL_IMPACT_BP = {"prescriptive": 6_500, "predictive": 4_500, "informational": 3_000}

#: Cost of the artifact the play produces, as a share of a full-effort action. A recap is
#: cheaper to act on than a competitive defence; this is the only effort signal the legacy path
#: has, and a rough true number beats an exact placeholder.
_ARTIFACT_EFFORT_BP = {
    "draft_followup": 3_000, "draft_reengage": 3_500, "draft_recap": 3_000,
    "draft_objection_reply": 6_000, "draft_advance": 5_000, "draft_multithread": 7_000,
    "draft_competitive": 7_500, "draft_deal_action": 6_000, "draft_delivery": 4_000,
}


#: How much longer a decision stays TRUE than it stays worth restating. A conclusion does not
#: stop holding the moment its card leaves the queue; treating those as the same instant is what
#: made re-firing immediate and guaranteed.
_AUTHORITY_MULTIPLIER = 3


def _wait_play(rule, window_days: int) -> PlayDefinition:
    """The explicit do-nothing option, so acting has something to beat.

    Cheap and safe by construction — that is what makes it a fair competitor: a marginal action
    on a thin signal SHOULD lose to waiting, and until waiting was on the ballot it could not.
    """
    return PlayDefinition(
        play_id=f"wait_{rule.id}",
        version=str(rule.version),
        label="Wait",
        steps=("Take no action yet; re-evaluate when the situation changes.",),
        read_only=True,
        success_events=(),
        window_days=window_days,
        # High success (doing nothing reliably does nothing), no effort, no risk, and impact
        # deliberately below any real play — waiting preserves the option, it does not advance.
        impact_bp=2_000,
        success_probability_bp=9_000,
        effort_bp=0,
        risk_bp=0,
        metadata={"legacy_play": True, "do_nothing": True,
                  "execution_boundary": "no_action",
                  "external_recipient_required": False},
    )


def _authority_hours(rule) -> int:
    """How long this decision remains authoritative.

    Derived from the pack's `cooldown_hours` — the only signal the legacy path has about how
    long the situation matters — but deliberately LONGER, so the suppression window closes well
    before authority does. Capped at a year, floored at an hour.
    """
    cooldown = integer(rule.cooldown_hours, "rule.cooldown_hours")
    return max(1, min(8_760, cooldown * _AUTHORITY_MULTIPLIER))


def _confidence_floor_bp(scoring: dict | None) -> int:
    """The pack's own `gate.c_min`, in basis points.

    Read from the EFFECTIVE scoring config the adapter is already handed, so a tenant overlay
    that raises the bar actually raises it. Returns 0 when the pack declares nothing, which
    preserves the previous behaviour exactly for any pack that has not opted in.
    """
    gate = ((scoring or {}).get("gate") or {})
    try:
        return max(0, min(10_000, int(gate.get("c_min", 0)) * 100))
    except (TypeError, ValueError):
        return 0


def _impact_bp(rule) -> int:
    """What acting on this is worth if it is right."""
    base = _LEVEL_IMPACT_BP.get(str(getattr(rule, "level", "") or "").lower(), 5_000)
    # A rule the pack marked deal-linked concerns revenue rather than hygiene.
    if getattr(rule, "linked_deal", False):
        base = min(10_000, base + 1_000)
    return base


def _success_bp(rule, window_days: int) -> int:
    """How likely the play is to produce its declared success event.

    A rule with no success event cannot succeed by its own definition, and saying so is more
    useful than assigning it a confident-looking 5000. A longer window is more forgiving.
    """
    if not getattr(rule, "success_signal", None):
        return 3_000
    return 5_000 + min(2_500, max(0, int(window_days)) * 250)


def _effort_bp(artifact: str) -> int:
    return _ARTIFACT_EFFORT_BP.get(str(artifact), 5_000)


def _risk_bp(rule) -> int:
    """Risk of acting wrongly. Every legacy play is read-only and human-approved, so the floor is
    low; a predictive rule carries more risk because it acts on something that has not happened.
    """
    return 3_500 if str(getattr(rule, "level", "")).lower() == "predictive" else 2_000


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
    # Two of the seventeen dark units, and only two. Seventeen reasoners existed and none was
    # ever declared by this manifest, so they never ran for any tenant — but mass-activating them
    # would change every score at once with no way to attribute a regression. These two first
    # because they produce the answers the card contract needs and cannot currently fill:
    # `temporal` computes why-now from the engagement trajectory, `relationship` computes the
    # counterparty's standing rather than the channel's.
    #
    # OPTIONAL, deliberately. Both return INSUFFICIENT_CONTEXT when their input fact is absent,
    # which for a tenant with no CRM is most subjects — and a REQUIRED policy would turn every
    # one of those into a failed decision. Optional means they enrich when they can and are
    # silent when they cannot, which is the only safe way to widen a live DAG.
    temporal = ReasonerSpec(
        reasoner_id="core.temporal",
        version=_REASONER_VERSION,
        dependencies=("legacy.rule",),
        failure_policy=FailurePolicy.OPTIONAL,
        config={"timestamp_field": str(rule.urgency.get("path") or "thread.last_inbound")},
    )
    relationship = ReasonerSpec(
        reasoner_id="core.relationship",
        version=_REASONER_VERSION,
        dependencies=("legacy.rule",),
        failure_policy=FailurePolicy.OPTIONAL,
    )
    planning = ReasonerSpec(
        reasoner_id="core.planning",
        version=_REASONER_VERSION,
        input_kind="ranked_candidates",
        output_kind="planning_checks",
        dependencies=("core.constraint", "core.priority", "core.confidence"),
        failure_policy=FailurePolicy.REQUIRED,
    )
    # The two Decision Support units the audit found named only by the LOCK-1-excluded native
    # manifest — "the four comparison/challenge units have never executed" — and the two of the
    # four that need no domain fact this adapter does not already have. `core.alternative` reads
    # `request.capability.plays` (the primary play + the wait play, always present) and the
    # eliminations `core.constraint` already ruled on; `core.validation` reads what every OTHER
    # unit above just published and reports where it fails to hold together — a contradiction
    # between two units, a claim with no cited evidence, a conclusion resting on stale facts. Both
    # are pure analysis: they emit no adjustment and no check, so adding them cannot change a
    # score, only what a reviewer can see about how it was reached.
    alternative = ReasonerSpec(
        reasoner_id="core.alternative",
        version=_REASONER_VERSION,
        dependencies=("core.constraint",),
        failure_policy=FailurePolicy.OPTIONAL,
    )
    validation = ReasonerSpec(
        reasoner_id="core.validation",
        version=_REASONER_VERSION,
        dependencies=("core.constraint", "core.priority", "core.confidence",
                     "core.temporal", "core.relationship"),
        failure_policy=FailurePolicy.OPTIONAL,
    )
    play = PlayDefinition(
        play_id=play_id,
        version=str(rule.version),
        label=play_id.replace("_", " ").title(),
        steps=(f"Prepare {artifact.replace('_', ' ')} for human review.",),
        read_only=True,
        success_events=((str(success),) if success else ()),
        window_days=window_days,
        # Real components instead of the dataclass defaults. Leaving them unset meant every one
        # of this org's 144 candidates carried {impact 5000, success 5000, effort 5000, risk 5000}
        # — four of the five inputs to the ranking formula frozen at the same placeholder, which
        # makes any unit that adjusts them a no-op and makes the persisted score_components read
        # as measurements when nothing was measured.
        impact_bp=_impact_bp(rule),
        success_probability_bp=_success_bp(rule, window_days),
        effort_bp=_effort_bp(artifact),
        risk_bp=_risk_bp(rule),
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
        # Everything that can change the manifest BYTES has to appear here, or two different
        # capabilities share one version and the immutability guard cannot tell them apart.
        # Tenant overlays change effective scoring without a new pack (hence effective_hash);
        # the adapter itself changes the DAG without either (hence _ADAPTER_SHAPE).
        version=f"{pack_version}-{_ADAPTER_SHAPE}-{snapshot_marker}-{effective_hash}",
        domain=str(pack_id),
        root_entity_type=rule.scope,
        goal=Goal(
            goal_id=f"legacy.{rule.id}.goal",
            statement=f"Resolve the verified {rule.reason_code.replace('_', ' ')} condition.",
            success_criteria=((f"Observe {success} inside the declared window.",)
                              if success else ()),
            constraints=("Produce a read-only recommendation; do not execute it.",),
        ),
        reasoners=(legacy, score_gate, constraint, priority, confidence,
                   temporal, relationship, planning, alternative, validation),
        # TWO plays: the recommended move and an explicit WAIT. A capability offering one option
        # is not making a choice — it produces exactly one candidate per run, nothing is ever
        # eliminated, and every card reads as the only possible answer. The design already asks
        # for "primary + fallback + explicit do-nothing"; the legacy adapter passed `(play,)`, so
        # `decision.alternative` and `.stop_condition` had no producer at all and the card
        # contract's fields for them were permanently empty.
        #
        # Waiting is a real decision, and it is often the right one on a thread where nothing has
        # changed but the clock. Making it a ranked candidate rather than an absence means the
        # trace can show it LOST, which is the difference between a system that chose to act and
        # one that could only act.
        plays=(play, _wait_play(rule, window_days)),
        policies=("read_only", "human_approval_required"),
        do_nothing_consequence=(
            f"The {rule.reason_code.replace('_', ' ')} condition may remain unresolved."
        ),
        # THREE clocks, not one. `publication.py` documents them as distinct — "a decision can
        # remain true long after it stops being worth repeating" — and this adapter collapsed
        # them, feeding `cooldown_hours` straight into `expiry_hours`. The effect was a loop that
        # could not settle: a card's visible life and the rule's suppression window became the
        # same interval, so the instant one lapsed the other unlocked, and the next sweep minted
        # a fresh card for an unchanged fact. Every duplicate pair in the queue came from this.
        #
        # Authority now outlasts the repeat window, so there is a real quiet period in which the
        # decision is still true and nobody is told again.
        expiry_hours=_authority_hours(rule),
        metadata={
            "adapter": "legacy.rule.v1",
            "pack_id": str(pack_id),
            "pack_version": str(pack_version),
            "config_snapshot_id": str(config_snapshot_id or ""),
            "rule_id": rule.id,
            "effective_reasoning_hash": effective_hash,
            # The pack has always declared a confidence floor — `scoring_defaults.gate.c_min`,
            # 50 percent — and the adapter never carried it, so every live manifest omitted
            # `confidence_floor_bp`, the decision maker read its default of 0, and
            # `confidence_bp < 0` was never true. The system has therefore never once abstained
            # in its entire history: it can BLOCK a candidate (a suppression row nobody sees) but
            # it has no way to SAY it does not know, which is a different and more honest output.
            CONFIDENCE_FLOOR_KEY: _confidence_floor_bp(scoring),
        },
    )


__all__ = ["legacy_capability_manifest"]
