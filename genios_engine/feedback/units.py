"""The eleven deterministic Atlas learning units.

Units consume normalized facts, never raw prose, and return immutable ``LearningObject`` values.
The optional LLM seam described by the Atlas belongs before these types: once a preference or
correction is structured, every count, score, validation and target choice below is integer-only
and replayable.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from genios_engine.contracts.learning import (
    BrainTarget,
    LearningEvidence,
    LearningObject,
    LearningUnit,
)
from genios_engine.contracts.validators import (
    freeze_mapping,
    require_aware,
    require_identifier,
    require_non_negative,
)
from genios_engine.platform.canonical import canonical_dumps

WINDOW_DAYS = 28
SUCCESS_LABELS = frozenset({"succeeded"})
FAILURE_LABELS = frozenset({"expired_untouched", "expired_in_progress", "cancelled_by_human"})
NEUTRAL_LABELS = frozenset({"completed_unproven", "cancelled_by_world", "cancelled_by_system"})


def _bp(part: int, whole: int) -> int:
    return (part * 10_000 // whole) if whole > 0 else 0


def _confidence(positive: int, negative: int, observations: int) -> int:
    """Conservative integer confidence; support caps certainty for small cohorts."""
    labelled = positive + negative
    if labelled <= 0 or observations <= 0:
        return 0
    agreement = _bp(max(positive, negative), labelled)
    support = min(10_000, observations * 1_000)  # ten observations can earn full support
    return agreement * support // 10_000


def _day_count(moments: Iterable[datetime]) -> int:
    return len({require_aware(moment, "evidence time").date() for moment in moments})


@dataclass(frozen=True, slots=True)
class FeedbackFact:
    feedback_id: str
    subject_key: str
    action: str
    occurred_at: datetime
    explicit: bool = True
    preference_key: str | None = None
    preference_value: Any = None
    preference_scope: str | None = None       # user | organization
    preference_category: str | None = None
    source_ref: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "feedback_id", require_identifier(self.feedback_id, "feedback id"))
        object.__setattr__(self, "subject_key", require_identifier(self.subject_key, "subject key"))
        object.__setattr__(self, "occurred_at", require_aware(self.occurred_at, "occurred_at"))


@dataclass(frozen=True, slots=True)
class OutcomeFact:
    outcome_id: str
    capability_id: str
    play_id: str
    label: str
    closed_at: datetime
    progress_bp: int
    reminders_sent: int = 0
    escalations_fired: int = 0
    seconds_to_close: int = 0

    def __post_init__(self) -> None:
        setter = object.__setattr__
        for name in ("outcome_id", "capability_id", "play_id", "label"):
            setter(self, name, require_identifier(getattr(self, name), name))
        setter(self, "closed_at", require_aware(self.closed_at, "closed_at"))
        if not 0 <= self.progress_bp <= 10_000:
            raise ValueError("progress_bp must be between 0 and 10000")
        for name in ("reminders_sent", "escalations_fired", "seconds_to_close"):
            setter(self, name, require_non_negative(getattr(self, name), name))


@dataclass(frozen=True, slots=True)
class EnterpriseFact:
    event_id: str
    pattern_key: str
    kind: str
    occurred_at: datetime
    actor_key: str | None = None
    value: Mapping[str, Any] = field(default_factory=dict)
    explicit_memory: bool = False
    expires_at: datetime | None = None

    def __post_init__(self) -> None:
        setter = object.__setattr__
        for name in ("event_id", "pattern_key", "kind"):
            setter(self, name, require_identifier(getattr(self, name), name))
        setter(self, "occurred_at", require_aware(self.occurred_at, "occurred_at"))
        if self.actor_key is not None:
            setter(self, "actor_key", require_identifier(self.actor_key, "actor key"))
        setter(self, "value", freeze_mapping(self.value))
        if self.expires_at is not None:
            setter(self, "expires_at", require_aware(self.expires_at, "expires_at"))


@dataclass(frozen=True, slots=True)
class DeliveryFact:
    delivery_id: str
    channel: str
    status: str
    created_at: datetime
    delivered_at: datetime | None = None
    attempts: int = 0
    deferrals: int = 0
    reason_code: str | None = None

    def __post_init__(self) -> None:
        setter = object.__setattr__
        for name in ("delivery_id", "channel", "status"):
            setter(self, name, require_identifier(getattr(self, name), name))
        setter(self, "created_at", require_aware(self.created_at, "created_at"))
        if self.delivered_at is not None:
            setter(self, "delivered_at", require_aware(self.delivered_at, "delivered_at"))
        for name in ("attempts", "deferrals"):
            setter(self, name, require_non_negative(getattr(self, name), name))


@dataclass(frozen=True, slots=True)
class LearningBatch:
    org_id: str
    evaluated_at: datetime
    feedback: tuple[FeedbackFact, ...] = ()
    outcomes: tuple[OutcomeFact, ...] = ()
    events: tuple[EnterpriseFact, ...] = ()
    deliveries: tuple[DeliveryFact, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "org_id", require_identifier(self.org_id, "org id"))
        object.__setattr__(self, "evaluated_at", require_aware(self.evaluated_at, "evaluated_at"))


def _evidence(*, refs: Iterable[str], moments: Iterable[datetime], positive: int,
              negative: int, observations: int, business_value_bp: int = 5_000,
              noise: int = 0, conflict: int = 0) -> LearningEvidence:
    return LearningEvidence(
        observations=observations, distinct_days=_day_count(moments), positive=positive,
        negative=negative, confidence_bp=_confidence(positive, negative, observations),
        noise_bp=_bp(noise, observations), conflict_bp=_bp(conflict, observations),
        business_value_bp=business_value_bp, source_refs=tuple(refs))


def feedback_learning(batch: LearningBatch) -> list[LearningObject]:
    """Unit 1: explicit feedback taxonomy.  Silence is never turned into a label."""
    groups: dict[str, list[FeedbackFact]] = defaultdict(list)
    for fact in batch.feedback:
        if fact.explicit:
            groups[fact.subject_key].append(fact)
    out: list[LearningObject] = []
    positive_actions = {"accepted", "executed", "run_play", "do_it_myself"}
    negative_actions = {"rejected", "cancelled", "wrong"}
    for key, facts in sorted(groups.items()):
        positive = sum(item.action in positive_actions for item in facts)
        negative = sum(item.action in negative_actions for item in facts)
        out.append(LearningObject(
            org_id=batch.org_id, unit=LearningUnit.FEEDBACK, target=BrainTarget.METRICS,
            subject_key=f"feedback:{key}",
            value={"accepted": positive, "rejected": negative,
                   "neutral": len(facts) - positive - negative},
            evidence=_evidence(refs=(f.source_ref or f.feedback_id for f in facts),
                               moments=(f.occurred_at for f in facts), positive=positive,
                               negative=negative, observations=len(facts)),
            observed_at=batch.evaluated_at))
    return out


def _outcome_groups(batch: LearningBatch) -> dict[tuple[str, str], list[OutcomeFact]]:
    groups: dict[tuple[str, str], list[OutcomeFact]] = defaultdict(list)
    for fact in batch.outcomes:
        groups[(fact.capability_id, fact.play_id)].append(fact)
    return groups


def outcome_analysis(batch: LearningBatch) -> list[LearningObject]:
    """Unit 2: effectiveness and attention cost from the durable ExecutionOutcome seam."""
    out: list[LearningObject] = []
    for (capability, play), facts in sorted(_outcome_groups(batch).items()):
        positive = sum(f.label in SUCCESS_LABELS for f in facts)
        negative = sum(f.label in FAILURE_LABELS for f in facts)
        neutral = sum(f.label in NEUTRAL_LABELS for f in facts)
        labelled = positive + negative
        reminders = sum(f.reminders_sent for f in facts)
        escalations = sum(f.escalations_fired for f in facts)
        value = {"capability_id": capability, "play_id": play, "outcomes": len(facts),
                 "successes": positive, "failures": negative, "unproven": neutral,
                 "success_bp": _bp(positive, labelled),
                 "average_progress_bp": sum(f.progress_bp for f in facts) // len(facts),
                 "attention_cost_bp": min(10_000, _bp(
                     reminders + 2 * escalations, max(1, len(facts) * 4))),
                 "average_seconds_to_close": sum(f.seconds_to_close for f in facts) // len(facts)}
        out.append(LearningObject(
            org_id=batch.org_id, unit=LearningUnit.OUTCOME, target=BrainTarget.METRICS,
            subject_key=f"outcome:{capability}:{play}", value=value,
            evidence=_evidence(refs=(f.outcome_id for f in facts),
                               moments=(f.closed_at for f in facts), positive=positive,
                               negative=negative, observations=len(facts),
                               business_value_bp=8_000), observed_at=batch.evaluated_at))
    return out


def pattern_learning(batch: LearningBatch) -> list[LearningObject]:
    """Unit 3: repeated normalized enterprise events; no semantic guessing from prose."""
    groups: dict[tuple[str, str], list[EnterpriseFact]] = defaultdict(list)
    for fact in batch.events:
        if not fact.explicit_memory:
            groups[(fact.pattern_key, fact.kind)].append(fact)
    out: list[LearningObject] = []
    for (key, kind), facts in sorted(groups.items()):
        days = _day_count(f.occurred_at for f in facts)
        evidence = LearningEvidence(
            observations=len(facts), distinct_days=days, positive=len(facts), negative=0,
            confidence_bp=min(9_500, 4_000 + len(facts) * 750 + days * 250),
            business_value_bp=6_000, source_refs=tuple(f.event_id for f in facts))
        out.append(LearningObject(
            org_id=batch.org_id, unit=LearningUnit.PATTERN, target=BrainTarget.ORGANIZATION,
            subject_key=f"pattern:{key}:{kind}",
            value={"pattern_key": key, "kind": kind, "occurrences": len(facts),
                   "distinct_days": days}, evidence=evidence, observed_at=batch.evaluated_at))
    return out


def preference_learning(batch: LearningBatch) -> list[LearningObject]:
    """Unit 4: structured, explicit preferences only. Repetition still governs permanence."""
    groups: dict[tuple[str, str, str], list[FeedbackFact]] = defaultdict(list)
    for fact in batch.feedback:
        if (fact.explicit and fact.preference_key and fact.preference_scope
                and fact.preference_value is not None):
            value_key = canonical_dumps(fact.preference_value)
            groups[(fact.preference_scope, fact.preference_key, value_key)].append(fact)
    out: list[LearningObject] = []
    for (scope, key, _), facts in sorted(groups.items()):
        target = BrainTarget.BEHAVIOR if scope == "user" else BrainTarget.ORGANIZATION
        out.append(LearningObject(
            org_id=batch.org_id, unit=LearningUnit.PREFERENCE, target=target,
            subject_key=f"preference:{scope}:{key}",
            value={"key": key, "value": facts[0].preference_value, "scope": scope,
                   "category": facts[0].preference_category},
            evidence=_evidence(refs=(f.feedback_id for f in facts),
                               moments=(f.occurred_at for f in facts), positive=len(facts),
                               negative=0, observations=len(facts), business_value_bp=7_000),
            observed_at=batch.evaluated_at))
    return out


def temporary_memory(batch: LearningBatch) -> list[LearningObject]:
    """Unit 5: only an explicit memory directive can create leased runtime context."""
    out: list[LearningObject] = []
    for fact in sorted(batch.events, key=lambda item: item.event_id):
        if not fact.explicit_memory or fact.expires_at is None or fact.expires_at <= batch.evaluated_at:
            continue
        out.append(LearningObject(
            org_id=batch.org_id, unit=LearningUnit.TEMPORARY_MEMORY,
            target=BrainTarget.RUNTIME, subject_key=f"memory:{fact.pattern_key}",
            value=fact.value,
            evidence=LearningEvidence(
                observations=1, distinct_days=1, positive=1, negative=0,
                confidence_bp=10_000, business_value_bp=7_000,
                source_refs=(fact.event_id,)),
            observed_at=fact.occurred_at, expires_at=fact.expires_at,
            metadata={"explicit": True}))
    return out


_BEHAVIOR_CATEGORIES = frozenset({
    "communication_style", "decision_style", "meeting_habit", "execution_habit",
    "relationship_pattern"})


def behavior_evolution(batch: LearningBatch) -> list[LearningObject]:
    """Unit 6: behavior-shaped preference evidence, kept separate for brain provenance."""
    return [LearningObject(
        org_id=item.org_id, unit=LearningUnit.BEHAVIOR, target=BrainTarget.BEHAVIOR,
        subject_key=item.subject_key.replace("preference:", "behavior:", 1), value=item.value,
        evidence=item.evidence, observed_at=item.observed_at, metadata={"derived_from": item.learning_id})
        for item in preference_learning(batch)
        if item.value.get("category") in _BEHAVIOR_CATEGORIES]


_ADAPTIVE_CATEGORIES = frozenset({
    "current_priority", "notification_style", "execution_preference", "runtime_personalization"})


def adaptive_evolution(batch: LearningBatch) -> list[LearningObject]:
    """Unit 7: current operating preferences, not stable personality claims."""
    return [LearningObject(
        org_id=item.org_id, unit=LearningUnit.ADAPTIVE, target=BrainTarget.ADAPTIVE,
        subject_key=item.subject_key.replace("preference:", "adaptive:", 1), value=item.value,
        evidence=item.evidence, observed_at=item.observed_at, metadata={"derived_from": item.learning_id})
        for item in preference_learning(batch)
        if item.value.get("category") in _ADAPTIVE_CATEGORIES]


def recommendation_learning(batch: LearningBatch) -> list[LearningObject]:
    """Unit 8: publish play efficacy to the Adaptive Brain after governed validation."""
    return [LearningObject(
        org_id=item.org_id, unit=LearningUnit.RECOMMENDATION, target=BrainTarget.ADAPTIVE,
        subject_key=item.subject_key.replace("outcome:", "recommendation:", 1),
        value=item.value, evidence=item.evidence, observed_at=item.observed_at,
        metadata={"derived_from": item.learning_id}) for item in outcome_analysis(batch)]


def performance_optimization(batch: LearningBatch) -> list[LearningObject]:
    """Unit 9: transport performance; open/deferred work is not guessed to be failure."""
    groups: dict[str, list[DeliveryFact]] = defaultdict(list)
    for fact in batch.deliveries:
        groups[fact.channel].append(fact)
    out: list[LearningObject] = []
    for channel, facts in sorted(groups.items()):
        delivered = sum(f.status == "delivered" for f in facts)
        failed = sum(f.status in {"failed", "failed_terminal"} for f in facts)
        terminal = delivered + failed
        latencies = sorted(int((f.delivered_at - f.created_at).total_seconds() * 1000)
                           for f in facts if f.delivered_at is not None)
        out.append(LearningObject(
            org_id=batch.org_id, unit=LearningUnit.PERFORMANCE, target=BrainTarget.METRICS,
            subject_key=f"performance:delivery:{channel}",
            value={"channel": channel, "total": len(facts), "delivered": delivered,
                   "failed": failed, "open_or_suppressed": len(facts) - terminal,
                   "delivered_bp": _bp(delivered, terminal),
                   "attempts": sum(f.attempts for f in facts),
                   "deferrals": sum(f.deferrals for f in facts),
                   "latency_p50_ms": latencies[(len(latencies) - 1) // 2] if latencies else None},
            evidence=_evidence(refs=(f.delivery_id for f in facts),
                               moments=(f.created_at for f in facts), positive=delivered,
                               negative=failed, observations=len(facts),
                               business_value_bp=5_000), observed_at=batch.evaluated_at))
    return out


def knowledge_evolution(batch: LearningBatch) -> list[LearningObject]:
    """Unit 10: sustained poor play outcomes become review suggestions, never Expert writes."""
    out: list[LearningObject] = []
    for item in outcome_analysis(batch):
        value = item.value
        labelled = int(value["successes"]) + int(value["failures"])
        if labelled < 8 or int(value["success_bp"]) >= 4_000:
            continue
        out.append(LearningObject(
            org_id=batch.org_id, unit=LearningUnit.KNOWLEDGE,
            target=BrainTarget.KNOWLEDGE_SUGGESTION,
            subject_key=item.subject_key.replace("outcome:", "knowledge:review:", 1),
            value={"suggestion_type": "review_play", "reason": "sustained_low_outcome_rate",
                   "cohort": value}, evidence=item.evidence, observed_at=item.observed_at,
            metadata={"human_review_required": True, "derived_from": item.learning_id}))
    return out


ALL_ANALYSIS_UNITS = (
    feedback_learning, outcome_analysis, pattern_learning, preference_learning, temporary_memory,
    behavior_evolution, adaptive_evolution, recommendation_learning, performance_optimization,
    knowledge_evolution,
)


def run_units(batch: LearningBatch) -> list[LearningObject]:
    """Selector + planner: only units with relevant inputs return objects; order is canonical."""
    objects = [obj for unit in ALL_ANALYSIS_UNITS for obj in unit(batch)]
    return sorted(objects, key=lambda item: (item.unit.value, item.target.value,
                                             item.subject_key, item.learning_id))


__all__ = ["ALL_ANALYSIS_UNITS", "DeliveryFact", "EnterpriseFact", "FeedbackFact",
           "LearningBatch", "OutcomeFact", "adaptive_evolution", "behavior_evolution",
           "feedback_learning", "knowledge_evolution", "outcome_analysis", "pattern_learning",
           "performance_optimization", "preference_learning", "recommendation_learning",
           "run_units", "temporary_memory"]
