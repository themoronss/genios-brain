"""Layer 6 · Phase 3 — the eleven analysis units (Part 5).

Each unit reads the ``LearningBatch`` and emits immutable ``LearningObject`` proposals. The units
CALCULATE; they never write brain state and no LLM has any authority in scoring or target
selection. Scores are integer basis points; neutral observations never inflate confidence; a unit
whose seam is empty emits nothing. ``ALL_ANALYSIS_UNITS`` is the fixed canonical order the
orchestrator runs.
"""
from __future__ import annotations

import re
from collections import defaultdict
from datetime import datetime
from typing import Callable

from genios_engine.contracts.learning import (
    LearningEvidence,
    LearningObject,
    LearningPolicy,
    LearningTarget,
    Visibility,
    VisibilityScope,
)
from genios_engine.feedback.store import LearningBatch

# The only positive outcome label; everything else is neutral or negative (Part 2 / Unit 1-2).
_SUCCESS = "succeeded"
_NEUTRAL = {"completed_unproven", "expired_in_progress"}


_UNSAFE = re.compile(r"[^A-Za-z0-9_.:@/-]")


def _subject(*parts: str) -> str:
    """A valid structured subject key from source-supplied parts.

    Source ids (a capability, a play, a channel) come from other layers and may carry characters
    the identifier contract forbids. Sanitising here isolates a malformed value into a well-formed
    key rather than crashing the whole run — the spec's "isolate, do not fail the run" rule.
    """
    cleaned = [_UNSAFE.sub("_", str(p)) or "unknown" for p in parts]
    key = ":".join(cleaned)
    return key if key[:1].isalnum() else f"x:{key}"


def _org_visibility() -> Visibility:
    return Visibility(scope=VisibilityScope.ORGANIZATION)


def _bp(numerator: int, denominator: int) -> int:
    """A rate as integer basis points, clamped — arithmetic over stored truth, never a float guess."""
    if denominator <= 0:
        return 0
    return max(0, min(10000, round(numerator * 10000 / denominator)))


# ---- units 1,4,5: explicit-input units — nothing to emit until their seams carry data -------

def unit_feedback_learning(batch: LearningBatch, policy: LearningPolicy,
                           now: datetime) -> list[LearningObject]:
    """Positive/negative/timing/neutral from terminal verdicts. Empty until the verdict ledger lands."""
    return []  # batch.feedback is empty until the canonical verdict ledger is wired


def unit_preference_learning(batch: LearningBatch, policy: LearningPolicy,
                             now: datetime) -> list[LearningObject]:
    """Explicit structured key/value only — never inferred from prose. Empty until the inbox lands."""
    return []


def unit_temporary_memory(batch: LearningBatch, policy: LearningPolicy,
                          now: datetime) -> list[LearningObject]:
    """Explicit directive → a Runtime lease with a mandatory expiry. Empty until the inbox lands."""
    return []


# ---- unit 2: Outcome Analysis (Layer 5 outcomes) --------------------------------------------

def unit_outcome_analysis(batch: LearningBatch, policy: LearningPolicy,
                          now: datetime) -> list[LearningObject]:
    """Per (capability, play): success / neutral / negative counts + attention cost → a metric."""
    cohorts: dict[tuple[str, str], dict] = defaultdict(
        lambda: {"n": 0, "succeeded": 0, "neutral": 0, "failed": 0,
                 "reminders": 0, "escalations": 0, "first": None, "last": None})
    for o in batch.outcomes:
        cap, play = o.get("capability_id") or "unknown", o.get("play_id") or "unknown"
        c = cohorts[(cap, play)]
        c["n"] += 1
        label = o.get("label") or ""
        if label == _SUCCESS:
            c["succeeded"] += 1
        elif label in _NEUTRAL:
            c["neutral"] += 1
        else:
            c["failed"] += 1
        c["reminders"] += int(o.get("reminders_sent") or 0)
        c["escalations"] += int(o.get("escalations_fired") or 0)
        at = o.get("closed_at")
        if at:
            c["first"] = min(c["first"], at) if c["first"] else at
            c["last"] = max(c["last"], at) if c["last"] else at

    out: list[LearningObject] = []
    for (cap, play), c in cohorts.items():
        graded = c["succeeded"] + c["failed"]           # neutral does not inflate confidence
        out.append(LearningObject(
            org_id=batch.org_id, unit="outcome_analysis", target=LearningTarget.METRICS,
            subject=_subject(cap, play),
            proposed_value={"observations": c["n"], "succeeded": c["succeeded"],
                            "neutral_unproven": c["neutral"], "failed": c["failed"],
                            "reminders": c["reminders"], "escalations": c["escalations"],
                            "success_rate_bp": _bp(c["succeeded"], graded)},
            evidence=LearningEvidence(
                observations=c["n"], independent_refs=c["n"], distinct_days=1,
                positive=c["succeeded"], negative=c["failed"],
                confidence_bp=_bp(graded, c["n"]), business_value_bp=_bp(c["succeeded"], c["n"])),
            visibility=_org_visibility(), first_seen_at=c["first"] or now,
            last_seen_at=c["last"] or now, policy_key=policy.policy_key))
    return out


# ---- unit 3: Pattern Learning (enterprise events) -------------------------------------------

def unit_pattern_learning(batch: LearningBatch, policy: LearningPolicy,
                          now: datetime) -> list[LearningObject]:
    """Repeated (object_type, internal_kind) over independent sources and distinct days."""
    groups: dict[tuple[str, str], dict] = defaultdict(
        lambda: {"n": 0, "sources": set(), "days": set()})
    for e in batch.enterprise:
        key = (e.get("object_type") or "?", e.get("internal_kind") or "?")
        g = groups[key]
        g["n"] += 1
        g["sources"].add(e.get("independence_group") or e.get("source_ref_id"))
        at = e.get("occurred_at")
        if at:
            g["days"].add(at.date())

    out: list[LearningObject] = []
    for (obj_type, kind), g in groups.items():
        if len(g["sources"]) < policy.min_observations or len(g["days"]) < policy.min_distinct_days:
            continue                                    # not yet a pattern
        out.append(LearningObject(
            org_id=batch.org_id, unit="pattern_learning", target=LearningTarget.ORGANIZATION,
            subject=_subject("pattern", obj_type, kind),
            proposed_value={"object_type": obj_type, "kind": kind, "occurrences": g["n"]},
            evidence=LearningEvidence(
                observations=g["n"], independent_refs=len(g["sources"]),
                distinct_days=len(g["days"]), positive=g["n"], negative=0,
                confidence_bp=_bp(len(g["sources"]), g["n"])),
            visibility=_org_visibility(), first_seen_at=now, last_seen_at=now,
            policy_key=policy.policy_key))
    return out


# ---- units 6,7: Behavior / Adaptive evolution (candidates derived from outcome cohorts) -----

def _cohort_candidate(batch, policy, now, *, unit, target, subject_prefix, source):
    return []  # derived candidates require a stable parent cohort; wired as cohorts accumulate


def unit_behavior_evolution(batch: LearningBatch, policy: LearningPolicy,
                            now: datetime) -> list[LearningObject]:
    return _cohort_candidate(batch, policy, now, unit="behavior_evolution",
                             target=LearningTarget.BEHAVIOR, subject_prefix="behavior",
                             source="outcomes")


def unit_adaptive_evolution(batch: LearningBatch, policy: LearningPolicy,
                            now: datetime) -> list[LearningObject]:
    return _cohort_candidate(batch, policy, now, unit="adaptive_evolution",
                             target=LearningTarget.ADAPTIVE, subject_prefix="adaptive",
                             source="delivery")


# ---- unit 8: Recommendation Learning (efficacy incl. attention cost) ------------------------

def unit_recommendation_learning(batch: LearningBatch, policy: LearningPolicy,
                                 now: datetime) -> list[LearningObject]:
    """Capability/play success weighed against the attention it cost (reminders + escalations)."""
    cohorts: dict[str, dict] = defaultdict(
        lambda: {"n": 0, "succeeded": 0, "attention": 0})
    for o in batch.outcomes:
        play = o.get("play_id") or "unknown"
        c = cohorts[play]
        c["n"] += 1
        if (o.get("label") or "") == _SUCCESS:
            c["succeeded"] += 1
        c["attention"] += int(o.get("reminders_sent") or 0) + int(o.get("escalations_fired") or 0)

    out: list[LearningObject] = []
    for play, c in cohorts.items():
        if c["n"] < policy.min_observations:
            continue
        # efficacy = success rate discounted by attention spent per outcome
        per_outcome_attention_bp = _bp(c["attention"], c["n"])
        efficacy_bp = max(0, _bp(c["succeeded"], c["n"]) - per_outcome_attention_bp // 4)
        out.append(LearningObject(
            org_id=batch.org_id, unit="recommendation_learning", target=LearningTarget.ADAPTIVE,
            subject=_subject("play", play),
            proposed_value={"play": play, "success_rate_bp": _bp(c["succeeded"], c["n"]),
                            "attention_per_outcome_bp": per_outcome_attention_bp,
                            "efficacy_bp": efficacy_bp},
            evidence=LearningEvidence(
                observations=c["n"], independent_refs=c["n"], distinct_days=1,
                positive=c["succeeded"], negative=c["n"] - c["succeeded"],
                confidence_bp=efficacy_bp, business_value_bp=_bp(c["succeeded"], c["n"])),
            visibility=_org_visibility(), first_seen_at=now, last_seen_at=now,
            policy_key=policy.policy_key))
    return out


# ---- unit 9: Performance Optimization (delivery facts) --------------------------------------

def unit_performance_optimization(batch: LearningBatch, policy: LearningPolicy,
                                  now: datetime) -> list[LearningObject]:
    """Attempts, pre-delivery failures and receipts per channel — a metric only, never a brain."""
    by_channel: dict[str, dict] = defaultdict(
        lambda: {"n": 0, "delivered": 0, "pre_delivery_fail": 0, "attempts": 0, "engaged": 0})
    for f in batch.delivery:
        c = by_channel[f.channel]
        c["n"] += 1
        c["attempts"] += f.attempts
        if f.is_impression:
            c["delivered"] += 1
        if f.pre_delivery_failure:
            c["pre_delivery_fail"] += 1        # only a failure BEFORE first delivery is transport-negative
        if f.engaged:
            c["engaged"] += 1

    out: list[LearningObject] = []
    for channel, c in by_channel.items():
        out.append(LearningObject(
            org_id=batch.org_id, unit="performance_optimization", target=LearningTarget.METRICS,
            subject=_subject("channel", channel),
            proposed_value={"channel": channel, "deliveries": c["n"], "delivered": c["delivered"],
                            "pre_delivery_failures": c["pre_delivery_fail"],
                            "avg_attempts_bp": _bp(c["attempts"], c["n"]),
                            "engagement_rate_bp": _bp(c["engaged"], c["delivered"])},
            evidence=LearningEvidence(
                observations=c["n"], independent_refs=c["n"], distinct_days=1,
                positive=c["delivered"], negative=c["pre_delivery_fail"],
                confidence_bp=_bp(c["delivered"], c["n"])),
            visibility=_org_visibility(), first_seen_at=now, last_seen_at=now,
            policy_key=policy.policy_key))
    return out


# ---- unit 10: Knowledge Evolution (human-review suggestion, never an Expert write) ----------

def unit_knowledge_evolution(batch: LearningBatch, policy: LearningPolicy,
                             now: datetime) -> list[LearningObject]:
    """A play that consistently produces poor labelled outcomes → a human-review suggestion."""
    cohorts: dict[str, dict] = defaultdict(lambda: {"n": 0, "failed": 0})
    for o in batch.outcomes:
        play = o.get("play_id") or "unknown"
        c = cohorts[play]
        c["n"] += 1
        if (o.get("label") or "") not in (_SUCCESS, *_NEUTRAL):
            c["failed"] += 1

    out: list[LearningObject] = []
    for play, c in cohorts.items():
        if c["n"] < policy.min_observations:
            continue
        fail_bp = _bp(c["failed"], c["n"])
        if fail_bp < 6000:                     # only SUSTAINED poor outcomes escalate to a human
            continue
        out.append(LearningObject(
            org_id=batch.org_id, unit="knowledge_evolution",
            target=LearningTarget.KNOWLEDGE_SUGGESTION, subject=_subject("play", play),
            proposed_value={"play": play, "failure_rate_bp": fail_bp, "observations": c["n"],
                            "suggestion": "review this play — sustained poor outcomes"},
            evidence=LearningEvidence(
                observations=c["n"], independent_refs=c["n"], distinct_days=1,
                positive=0, negative=c["failed"], confidence_bp=fail_bp),
            visibility=_org_visibility(), first_seen_at=now, last_seen_at=now,
            policy_key=policy.policy_key))
    return out


# ---- unit 11: Learning Validation (the gate) ------------------------------------------------

def validate_learning(obj: LearningObject, policy: LearningPolicy) -> tuple[bool, str]:
    """Does the evidence support this proposal under the pinned policy? Returns (ok, reason).

    Metrics and knowledge suggestions are artifacts, not brains, so they bypass the confidence
    floor — a measurement is not a claim to be believed, and a knowledge suggestion is gated by
    human review, not by confidence. Everything else must clear support / days / confidence /
    noise / conflict.
    """
    e = obj.evidence
    if obj.target in (LearningTarget.METRICS, LearningTarget.KNOWLEDGE_SUGGESTION):
        return (True, "artifact")
    if e.observations < policy.min_observations:
        return (False, "insufficient_observations")
    if e.distinct_days < policy.min_distinct_days:
        return (False, "insufficient_distinct_days")
    if e.confidence_bp < policy.min_confidence_bp:
        return (False, "below_confidence_floor")
    if e.noise_bp > policy.max_noise_bp:
        return (False, "too_noisy")
    if e.conflict_bp > policy.max_conflict_bp:
        return (False, "conflicted")
    if e.business_value_bp < policy.min_business_value_bp:
        return (False, "below_value_floor")
    return (True, "validated")


#: The fixed canonical order the orchestrator runs. Ten analysis units; validation is applied after.
ALL_ANALYSIS_UNITS: tuple[Callable[..., list[LearningObject]], ...] = (
    unit_feedback_learning,          # 1
    unit_outcome_analysis,           # 2
    unit_pattern_learning,           # 3
    unit_preference_learning,        # 4
    unit_temporary_memory,           # 5
    unit_behavior_evolution,         # 6
    unit_adaptive_evolution,         # 7
    unit_recommendation_learning,    # 8
    unit_performance_optimization,   # 9
    unit_knowledge_evolution,        # 10
)


def run_all_units(batch: LearningBatch, policy: LearningPolicy,
                  now: datetime) -> list[LearningObject]:
    """Run the ten analysis units in canonical order and collect every proposal."""
    proposals: list[LearningObject] = []
    for unit in ALL_ANALYSIS_UNITS:
        proposals.extend(unit(batch, policy, now))
    return proposals


__all__ = ["ALL_ANALYSIS_UNITS", "run_all_units", "validate_learning"]
