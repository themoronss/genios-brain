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

from genios_engine.contracts.abstention import ACTIONABLE

from genios_engine.executive.collect import counts_against_the_play, label_class
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
#: KEPT for unit 2's own wording, but no longer the arbiter. `executive.collect.label_class` is,
#: and it is the single table both units read — `_NEUTRAL` here and `n - succeeded` in unit 8
#: disagreed about `cancelled_by_world` and about `completed_unproven`, which is how one unit
#: called an ending neutral while the other charged the play for it.
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

#: The card levels whose dismissal is evidence ABOUT THE RULE. `abstention.Level` has six values;
#: only these two put an instruction in front of a person, so only these two can be wrong about
#: one. `review`, `observation`, `wait` and `suppress` are the system declining to instruct, and
#: a human closing one of those has answered it.
#:
#: Read from the contract rather than spelled here, so a seventh level cannot arrive and be
#: silently graded as a prescription.
_PRESCRIBING_LEVELS: frozenset[str] = frozenset(ACTIONABLE)


def unit_feedback_learning(batch: LearningBatch, policy: LearningPolicy,
                           now: datetime) -> list[LearningObject]:
    """Per rule: what humans actually said about its cards — the only direct quality signal.

    The seam is wired (store.py reads `card_feedback_verdicts`, the real ledger from 0034) but
    this unit still returned `[]` without looking, so the FIRST verdict a human ever gives would
    have been read, loaded into the batch, and discarded here — the second of L7-03's two
    stoppers, and the one a migration could never fix.

    Grouped by rule_id, because the verdict vocabulary is about the RULE's judgment:
    `run_play`/`do_it_myself` say the card was worth acting on; `wrong` says it was not, and its
    mandatory reason says how — `not_relevant` and `wrong_facts` are quality failures,
    `bad_timing` is a scheduling failure on a correct card and must not count against the rule's
    accuracy. Target is METRICS: this unit reports evidence; changing thresholds from it is
    calibration's job, behind its own governance.
    """
    cohorts: dict[str, dict] = defaultdict(
        lambda: {"n": 0, "acted": 0, "wrong": 0, "bad_timing": 0, "answered": 0,
                 "reasons": defaultdict(int), "first": None, "last": None})
    for v in batch.feedback:
        rule = str(v.get("rule_id") or "unknown")
        c = cohorts[rule]
        c["n"] += 1
        cause = str(v.get("cause") or "")
        # WHAT KIND OF CARD WAS THIS, and until now the unit could not ask.
        #
        # A dismissal of an `ask_decision` card is not evidence the rule was wrong. That card
        # exists BECAUSE only a person can answer it — the system said so — and a person closing
        # it has answered the question, not rejected the judgment. Same for `observation`: "here
        # is something true, nobody needs to act" cannot be right or wrong about an action it
        # never recommended.
        #
        # Counted separately rather than dropped, because the count is real information: a rule
        # whose questions are all dismissed unanswered is telling us something, just not about
        # its accuracy. `answered` is that tally, and it stays out of `wrong`.
        #
        # ABSENT LEVEL IS NOT PRESCRIPTIVE. A verdict whose card has been pruned is ungradeable,
        # and defaulting it to "instruction" is exactly how the old behaviour would come back.
        level = str(v.get("card_level") or "").strip().lower()
        graded = level in _PRESCRIBING_LEVELS
        if cause in ("run_play", "do_it_myself"):
            c["acted"] += 1
        elif cause == "wrong":
            reason = str(v.get("reason") or "unstated")
            c["reasons"][reason] += 1
            if not graded:
                c["answered"] += 1
            elif reason == "bad_timing":
                c["bad_timing"] += 1
            else:
                c["wrong"] += 1
        at = v.get("occurred_at") or v.get("created_at")
        if at:
            c["first"] = min(c["first"], at) if c["first"] else at
            c["last"] = max(c["last"], at) if c["last"] else at

    out: list[LearningObject] = []
    for rule, c in cohorts.items():
        judged = c["acted"] + c["wrong"]                 # bad_timing does not grade accuracy
        out.append(LearningObject(
            org_id=batch.org_id, unit="feedback_learning", target=LearningTarget.METRICS,
            subject=_subject("rule", rule),
            proposed_value={"verdicts": c["n"], "acted": c["acted"], "wrong": c["wrong"],
                            "bad_timing": c["bad_timing"],
                            "wrong_reasons": dict(c["reasons"]),
                            "acted_rate_bp": _bp(c["acted"], judged)},
            evidence=LearningEvidence(
                observations=c["n"], independent_refs=c["n"], distinct_days=1,
                positive=c["acted"], negative=c["wrong"],
                confidence_bp=_bp(judged, c["n"]),
                business_value_bp=_bp(c["acted"], c["n"])),
            visibility=_org_visibility(), first_seen_at=c["first"] or now,
            last_seen_at=c["last"] or now, policy_key=policy.policy_key))
    return out


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
        lambda: {"n": 0, "succeeded": 0, "neutral": 0, "failed": 0, "mechanical": 0,
                 "reminders": 0, "escalations": 0, "first": None, "last": None})
    for o in batch.outcomes:
        cap, play = o.get("capability_id") or "unknown", o.get("play_id") or "unknown"
        c = cohorts[(cap, play)]
        c["n"] += 1
        # ONE TABLE, NOT AN `else`. `label_class` is the shared answer to "is this ending
        # evidence about the recommendation"; `else: failed` was the local one, and it charged a
        # play for the world moving and for our own tooling cancelling the work.
        kind = label_class(o.get("label"))
        if kind == "positive":
            c["succeeded"] += 1
        # THE NAMED PREDICATE, not a repeated string comparison. `counts_against_the_play`
        # was built, tested five ways and called by nothing — the branch's signature shape in
        # miniature — while two sites asked the same question by spelling the label out. Two
        # spellings of "this ending is evidence the recommendation was wrong" is how they come
        # to disagree the day a sixth label is minted.
        elif counts_against_the_play(o.get("label")):
            c["failed"] += 1
        elif kind == "mechanical":
            # Counted, never charged. A play whose tooling fails every time is a real defect and
            # must stay visible; it is a defect in the machinery, not in the advice.
            c["mechanical"] += 1
        else:
            # `neutral` and `unknown` both land here. An unclassified label must not penalise a
            # play — see `label_class`.
            c["neutral"] += 1
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
                            "mechanical_failures": c["mechanical"],
                            "reminders": c["reminders"], "escalations": c["escalations"],
                            "success_rate_bp": _bp(c["succeeded"], graded)},
            evidence=LearningEvidence(
                observations=c["n"], independent_refs=c["n"], distinct_days=1,
                positive=c["succeeded"], negative=c["failed"],
                confidence_bp=_bp(graded, c["n"]), business_value_bp=_bp(c["succeeded"], c["n"])),
            visibility=_org_visibility(), first_seen_at=c["first"] or now,
            last_seen_at=c["last"] or now, policy_key=policy.policy_key))
    return out


# ---- unit 2b: Actor Outcome Analysis (per person, not per org) ------------------------------

def unit_actor_outcome_analysis(batch: LearningBatch, policy: LearningPolicy,
                                now: datetime) -> list[LearningObject]:
    """Per PERSON: how their own work actually ended, addressed only to them.

    THE SENTENCE THAT HAD NO ADDRESSEE. "Rohit, the way you wrote that was not working" cannot be
    said by a system in which every rate is org-scoped. Harsh's plays close 80% of the time and
    Sneha's 20%; `run_calibration` mutes or loosens the rule for BOTH on the pooled average, and
    neither is ever told one thing about their own pattern. `execution_outcomes.assignee` has
    existed since `0041_l5_execution.sql:241` and no unit had ever read it.

    EVERYTHING DOWNSTREAM WAS ALREADY BUILT FOR THIS and only the number was missing:
    `learning_objects.subject_principal`, the contract's cap to `Visibility(PRIVATE,
    principals=(subject,))`, the `actor` address token — *"the user a preference belongs to, for
    Adaptive leases that are per-person"* — and the tenant's own floors in `learning_policies`.

    PRIVATE, AND THE CONTRACT ENFORCES IT. `LearningObject.__post_init__` refuses a
    subject-scoped object that is not private and refuses one whose principals are anything but
    that single subject. So a per-person rate cannot become a leaderboard by accident: it is
    visible to its subject and to nobody else, including their manager. That is not a courtesy —
    a rate one person can read about another is a performance judgment the evidence cannot
    support, and `FX-36` forbids exactly that inference.

    IT MEASURES ENDINGS, NOT PEOPLE, and the distinction is the whole of its honesty. It reuses
    `label_class` and `counts_against_the_play` unchanged, so a play cancelled by the world or
    killed by our own tooling is counted and NOT charged — the same rule
    `unit_outcome_analysis` follows. A person whose outcomes are mostly mechanical failures has a
    tooling problem, and a number that called that their failure would be a lie with a decimal
    point on it.

    AN UNASSIGNED OUTCOME IS SKIPPED, not bucketed under "unknown". `unit_outcome_analysis` can
    honestly say `capability_id or "unknown"` because a capability-less outcome is still an
    outcome about the machinery. A person-less outcome is not evidence about any person, and an
    "unknown" bucket here would be a private learning object addressed to nobody — which the
    contract would reject anyway, one layer too late to be a good error.
    """
    cohorts: dict[str, dict] = defaultdict(
        lambda: {"n": 0, "succeeded": 0, "neutral": 0, "failed": 0, "mechanical": 0,
                 "reminders": 0, "escalations": 0, "first": None, "last": None})
    for o in batch.outcomes:
        assignee = str(o.get("assignee") or "").strip()
        if not assignee:
            continue
        c = cohorts[assignee]
        c["n"] += 1
        kind = label_class(o.get("label"))
        if kind == "positive":
            c["succeeded"] += 1
        elif counts_against_the_play(o.get("label")):
            c["failed"] += 1
        elif kind == "mechanical":
            c["mechanical"] += 1
        else:
            c["neutral"] += 1
        c["reminders"] += int(o.get("reminders_sent") or 0)
        c["escalations"] += int(o.get("escalations_fired") or 0)
        at = o.get("closed_at")
        if at:
            c["first"] = min(c["first"], at) if c["first"] else at
            c["last"] = max(c["last"], at) if c["last"] else at

    out: list[LearningObject] = []
    for assignee, c in cohorts.items():
        graded = c["succeeded"] + c["failed"]
        subject = _subject("actor", assignee)
        out.append(LearningObject(
            org_id=batch.org_id, unit="actor_outcome_analysis", target=LearningTarget.METRICS,
            subject=subject,
            proposed_value={"observations": c["n"], "succeeded": c["succeeded"],
                            "neutral_unproven": c["neutral"], "failed": c["failed"],
                            "mechanical_failures": c["mechanical"],
                            "reminders": c["reminders"], "escalations": c["escalations"],
                            "success_rate_bp": _bp(c["succeeded"], graded)},
            evidence=LearningEvidence(
                observations=c["n"], independent_refs=c["n"], distinct_days=1,
                positive=c["succeeded"], negative=c["failed"],
                confidence_bp=_bp(graded, c["n"]),
                business_value_bp=_bp(c["succeeded"], c["n"])),
            # THE SANITISED KEY IS THE PRINCIPAL, not the raw assignee. `_subject` may rewrite a
            # character the identifier contract forbids, and the contract requires the object's
            # principals to equal `subject_principal` exactly — passing the raw string here would
            # raise on precisely the ids that needed sanitising, which is the worst time to fail.
            subject_principal=_subject(assignee),
            visibility=Visibility(scope=VisibilityScope.PRIVATE,
                                  principals=(_subject(assignee),)),
            first_seen_at=c["first"] or now,
            last_seen_at=c["last"] or now, policy_key=policy.policy_key))
    return out


# ---- unit 3: Pattern Learning (enterprise events) -------------------------------------------

def unit_pattern_learning(batch: LearningBatch, policy: LearningPolicy,
                          now: datetime) -> list[LearningObject]:
    """Repeated (object_type, internal_kind) over independent sources and distinct days.

    A generalized ORGANIZATION-brain pattern is a claim about the tenant's world, not about one
    entity in it — so it also tracks how many DISTINCT entities (companies/people, via each ref's
    ``entity_id``) contributed. ``min_observations`` alone can't catch "10 emails from the same
    one account" masquerading as a pattern; ``validate_learning`` gates on entity count too.
    """
    groups: dict[tuple[str, str], dict] = defaultdict(
        lambda: {"n": 0, "sources": set(), "days": set(), "entities": set()})
    for e in batch.enterprise:
        key = (e.get("object_type") or "?", e.get("internal_kind") or "?")
        g = groups[key]
        g["n"] += 1
        g["sources"].add(e.get("independence_group") or e.get("source_ref_id"))
        entity_id = e.get("entity_id")
        if entity_id:
            g["entities"].add(entity_id)
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
                confidence_bp=_bp(len(g["sources"]), g["n"]),
                distinct_entities=len(g["entities"])),
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
        lambda: {"n": 0, "succeeded": 0, "graded": 0, "excluded": 0, "attention": 0})
    for o in batch.outcomes:
        play = o.get("play_id") or "unknown"
        c = cohorts[play]
        c["n"] += 1
        # THE UNIT THAT CHANGES THE BRAIN. Its target is ADAPTIVE, not METRICS, and it counted
        # `negative = n - succeeded` — so a play was penalised for `completed_unproven` (it worked
        # and no source can prove it), for `expired_in_progress` (somebody was actively working on
        # it), for `cancelled_by_world` (the situation resolved itself) and for
        # `cancelled_by_system` (our own tooling cancelled it). The last two are the inventory's
        # LRN-07; the first is LRN-01. Only a GRADED ending may move a play's efficacy.
        kind = label_class(o.get("label"))
        if kind == "positive":
            c["succeeded"] += 1
            c["graded"] += 1
        # THE NAMED PREDICATE, not a repeated string comparison. `counts_against_the_play`
        # was built, tested five ways and called by nothing — the branch's signature shape in
        # miniature — while two sites asked the same question by spelling the label out. Two
        # spellings of "this ending is evidence the recommendation was wrong" is how they come
        # to disagree the day a sixth label is minted.
        elif counts_against_the_play(o.get("label")):
            c["graded"] += 1
        else:
            c["excluded"] += 1
        c["attention"] += int(o.get("reminders_sent") or 0) + int(o.get("escalations_fired") or 0)

    out: list[LearningObject] = []
    for play, c in cohorts.items():
        # THE FLOOR IS ON GRADED ENDINGS, not on how many times the play ran. A play that ran
        # twenty times and was cancelled by the world on every one has twenty observations and
        # nothing to learn from, and admitting it would let an unmeasured play rewrite the brain.
        if c["graded"] < policy.min_observations:
            continue
        # efficacy = success rate discounted by attention spent per outcome. Both terms are taken
        # over GRADED endings so an excluded one neither raises nor lowers the score.
        per_outcome_attention_bp = _bp(c["attention"], c["graded"])
        efficacy_bp = max(0, _bp(c["succeeded"], c["graded"]) - per_outcome_attention_bp // 4)
        out.append(LearningObject(
            org_id=batch.org_id, unit="recommendation_learning", target=LearningTarget.ADAPTIVE,
            subject=_subject("play", play),
            proposed_value={"play": play, "success_rate_bp": _bp(c["succeeded"], c["graded"]),
                            "attention_per_outcome_bp": per_outcome_attention_bp,
                            "graded_endings": c["graded"], "ungraded_endings": c["excluded"],
                            "efficacy_bp": efficacy_bp},
            evidence=LearningEvidence(
                observations=c["graded"], independent_refs=c["graded"], distinct_days=1,
                positive=c["succeeded"], negative=c["graded"] - c["succeeded"],
                confidence_bp=efficacy_bp,
                business_value_bp=_bp(c["succeeded"], c["graded"])),
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
    # k-anonymity: a generalized ORGANIZATION pattern derived from too few distinct entities
    # effectively identifies them. Other targets don't generalize across entities this way.
    if obj.target is LearningTarget.ORGANIZATION and e.distinct_entities < policy.min_distinct_entities:
        return (False, "insufficient_distinct_entities")
    if e.confidence_bp < policy.min_confidence_bp:
        return (False, "below_confidence_floor")
    if e.noise_bp > policy.max_noise_bp:
        return (False, "too_noisy")
    if e.conflict_bp > policy.max_conflict_bp:
        return (False, "conflicted")
    if e.business_value_bp < policy.min_business_value_bp:
        return (False, "below_value_floor")
    return (True, "validated")


#: The fixed canonical order the orchestrator runs. Eleven analysis units; validation is applied
#: after. `actor_outcome_analysis` sits beside `outcome_analysis` because it asks the same
#: question of the same rows with a different group-by — per person rather than per play — and
#: running them apart would let the two drift on what an ending MEANS.
ALL_ANALYSIS_UNITS: tuple[Callable[..., list[LearningObject]], ...] = (
    unit_feedback_learning,          # 1
    unit_outcome_analysis,           # 2
    unit_actor_outcome_analysis,     # 2b — same rows, grouped by person, private to them
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
