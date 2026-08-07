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
from datetime import datetime, timedelta
from typing import Any

from genios_engine.contracts.learning import (
    LearningEvidence,
    LearningObject,
    LearningTarget,
    LearningUnit,
)
from genios_engine.contracts.validators import (
    freeze_mapping,
    require_aware,
    require_hash64,
    require_identifier,
    require_non_negative,
)
from genios_engine.platform.canonical import canonical_dumps, semantic_hash
from genios_engine.contracts.visibility import PRIVATE, Visibility, narrowest

SUCCESS_LABELS = frozenset({"succeeded"})
FAILURE_LABELS = frozenset({"expired_untouched", "expired_in_progress", "cancelled_by_human"})
NEUTRAL_LABELS = frozenset({"completed_unproven", "cancelled_by_world", "cancelled_by_system"})
OUTCOME_LABELS = SUCCESS_LABELS | FAILURE_LABELS | NEUTRAL_LABELS
DELIVERY_STATUSES = frozenset({
    "queued", "deferred", "delivered", "viewed", "ignored", "accepted", "executed",
    "failed", "expired", "suppressed", "cancelled",
})
FEEDBACK_ACTIONS = frozenset({
    "run_play", "do_it_myself", "wrong", "accepted", "executed", "rejected",
    "cancelled", "ignored", "snooze",
})


def _private_visibility() -> Mapping[str, Any]:
    return Visibility(scope=PRIVATE, principals=[],
                      derived_from="missing:learning-input-lineage").model_dump()


def _subject_visibility(source: Mapping[str, Any], principal: str | None
                        ) -> tuple[Mapping[str, Any], bool]:
    """Intersect an explicit personal preference with its learned subject.

    A company-visible recommendation may carry one person's edit, but that does not make the
    person's preference company-visible. The derived value is always private to the resolved
    subject and is invalid when that subject could not see the source evidence.
    """
    if principal is None:
        return Visibility(
            scope=PRIVATE, principals=[],
            derived_from="preference:unresolved-subject").model_dump(), False
    source_visibility = Visibility.model_validate(dict(source))
    subject = principal.strip().lower()
    return Visibility(
        scope=PRIVATE, principals=[subject],
        derived_from=f"subject-intersection:{source_visibility.derived_from}").model_dump(), (
            source_visibility.can_view(subject, org_member=True))


def _bp(part: int, whole: int) -> int:
    return (part * 10_000 // whole) if whole > 0 else 0


def _confidence(positive: int, negative: int, independent_support: int) -> int:
    """Conservative integer confidence; support caps certainty for small cohorts."""
    labelled = positive + negative
    if labelled <= 0 or independent_support <= 0:
        return 0
    agreement = _bp(max(positive, negative), labelled)
    # Neutral/open rows never increase certainty, and multiple rows from one origin count once.
    support = min(10_000, min(labelled, independent_support) * 1_000)
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
    reason: str | None = None
    preference_key: str | None = None
    preference_value: Any = None
    preference_scope: str | None = None       # user | organization
    preference_category: str | None = None
    source_ref: str | None = None
    actor_key: str | None = None
    subject_principal: str | None = None
    trace_id: str | None = None
    independence_key: str | None = None
    visibility: Mapping[str, Any] = field(default_factory=_private_visibility)
    lineage_complete: bool = False
    organization_authorized: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "feedback_id", require_identifier(self.feedback_id, "feedback id"))
        object.__setattr__(self, "subject_key", require_identifier(self.subject_key, "subject key"))
        object.__setattr__(self, "occurred_at", require_aware(self.occurred_at, "occurred_at"))
        if self.actor_key is not None:
            object.__setattr__(self, "actor_key", require_identifier(self.actor_key, "actor key"))
        if self.subject_principal is not None:
            object.__setattr__(self, "subject_principal", require_identifier(
                self.subject_principal.lower(), "subject principal"))
        if self.action not in FEEDBACK_ACTIONS:
            raise ValueError(f"unsupported feedback action: {self.action}")
        if self.reason is not None:
            object.__setattr__(self, "reason", require_identifier(self.reason, "feedback reason"))
        if self.action == "wrong" and self.reason not in {
                "not_relevant", "wrong_facts", "bad_timing"}:
            raise ValueError("wrong feedback requires a closed reason")
        if self.trace_id is not None:
            object.__setattr__(self, "trace_id", require_identifier(self.trace_id, "trace id"))
        if self.independence_key is not None:
            object.__setattr__(self, "independence_key",
                               require_identifier(self.independence_key, "independence key"))
        preference_fields = (self.preference_key, self.preference_scope, self.preference_category)
        if any(item is not None for item in preference_fields) or self.preference_value is not None:
            if not all(item is not None for item in preference_fields) or self.preference_value is None:
                raise ValueError("preference key, value, scope and category must be provided together")
            if self.preference_scope not in {"user", "organization"}:
                raise ValueError("preference scope must be user or organization")
            object.__setattr__(self, "preference_key",
                               require_identifier(self.preference_key, "preference key"))
            object.__setattr__(self, "preference_category",
                               require_identifier(self.preference_category, "preference category"))
            if self.preference_scope == "user" and self.actor_key is None:
                raise ValueError("user preference requires actor identity")
            if self.preference_scope == "organization" and not self.organization_authorized:
                raise ValueError("organization preference requires frozen owner authority")
            object.__setattr__(self, "preference_value", freeze_mapping(
                {"value": self.preference_value})["value"])
        object.__setattr__(self, "visibility", freeze_mapping(
            Visibility.model_validate(dict(self.visibility)).model_dump()))
        if not isinstance(self.lineage_complete, bool):
            raise TypeError("lineage_complete must be boolean")
        if not isinstance(self.organization_authorized, bool):
            raise TypeError("organization_authorized must be boolean")


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
    trace_id: str | None = None
    independence_key: str | None = None
    visibility: Mapping[str, Any] = field(default_factory=_private_visibility)
    lineage_complete: bool = False

    def __post_init__(self) -> None:
        setter = object.__setattr__
        for name in ("outcome_id", "capability_id", "play_id", "label"):
            setter(self, name, require_identifier(getattr(self, name), name))
        if self.label not in OUTCOME_LABELS:
            raise ValueError(f"unsupported outcome label: {self.label}")
        setter(self, "closed_at", require_aware(self.closed_at, "closed_at"))
        if not 0 <= self.progress_bp <= 10_000:
            raise ValueError("progress_bp must be between 0 and 10000")
        for name in ("reminders_sent", "escalations_fired", "seconds_to_close"):
            setter(self, name, require_non_negative(getattr(self, name), name))
        if self.trace_id is not None:
            setter(self, "trace_id", require_identifier(self.trace_id, "trace id"))
        if self.independence_key is not None:
            setter(self, "independence_key",
                   require_identifier(self.independence_key, "independence key"))
        setter(self, "visibility", freeze_mapping(
            Visibility.model_validate(dict(self.visibility)).model_dump()))
        if not isinstance(self.lineage_complete, bool):
            raise TypeError("lineage_complete must be boolean")


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
    source_confidence_bp: int = 5_000
    trace_id: str | None = None
    independence_key: str | None = None
    visibility: Mapping[str, Any] = field(default_factory=_private_visibility)
    lineage_complete: bool = False

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
        if not 0 <= self.source_confidence_bp <= 10_000:
            raise ValueError("source_confidence_bp must be between 0 and 10000")
        if self.trace_id is not None:
            setter(self, "trace_id", require_identifier(self.trace_id, "trace id"))
        if self.independence_key is not None:
            setter(self, "independence_key",
                   require_identifier(self.independence_key, "independence key"))
        setter(self, "visibility", freeze_mapping(
            Visibility.model_validate(dict(self.visibility)).model_dump()))
        if not isinstance(self.lineage_complete, bool):
            raise TypeError("lineage_complete must be boolean")


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
    lifecycle_status: str | None = None
    lifecycle_at: datetime | None = None
    viewed_at: datetime | None = None
    ignored_at: datetime | None = None
    accepted_at: datetime | None = None
    executed_at: datetime | None = None
    expired_at: datetime | None = None
    execution_id: str | None = None
    trace_id: str | None = None
    independence_key: str | None = None
    visibility: Mapping[str, Any] = field(default_factory=_private_visibility)
    lineage_complete: bool = False

    def __post_init__(self) -> None:
        setter = object.__setattr__
        for name in ("delivery_id", "channel", "status"):
            setter(self, name, require_identifier(getattr(self, name), name))
        if self.status not in DELIVERY_STATUSES:
            raise ValueError(f"unsupported delivery status: {self.status}")
        setter(self, "created_at", require_aware(self.created_at, "created_at"))
        if self.delivered_at is not None:
            setter(self, "delivered_at", require_aware(self.delivered_at, "delivered_at"))
        for name in ("lifecycle_at", "viewed_at", "ignored_at", "accepted_at", "executed_at",
                     "expired_at"):
            value = getattr(self, name)
            if value is not None:
                setter(self, name, require_aware(value, name))
        if self.delivered_at is not None and self.delivered_at < self.created_at:
            raise ValueError("delivered_at cannot be earlier than created_at")
        if self.lifecycle_status is not None:
            setter(self, "lifecycle_status",
                   require_identifier(self.lifecycle_status, "lifecycle status"))
        for name in ("attempts", "deferrals"):
            setter(self, name, require_non_negative(getattr(self, name), name))
        for name in ("execution_id", "trace_id", "independence_key"):
            value = getattr(self, name)
            if value is not None:
                setter(self, name, require_identifier(value, name.replace("_", " ")))
        setter(self, "visibility", freeze_mapping(
            Visibility.model_validate(dict(self.visibility)).model_dump()))
        if not isinstance(self.lineage_complete, bool):
            raise TypeError("lineage_complete must be boolean")


@dataclass(frozen=True, slots=True)
class InputRejection:
    source_kind: str
    source_ref: str
    reason_code: str
    payload_hash: str

    def __post_init__(self) -> None:
        setter = object.__setattr__
        for name in ("source_kind", "source_ref", "reason_code", "payload_hash"):
            validator = require_hash64 if name == "payload_hash" else require_identifier
            setter(self, name, validator(getattr(self, name), name.replace("_", " ")))


@dataclass(frozen=True, slots=True)
class LearningBatch:
    org_id: str
    evaluated_at: datetime
    feedback: tuple[FeedbackFact, ...] = ()
    outcomes: tuple[OutcomeFact, ...] = ()
    events: tuple[EnterpriseFact, ...] = ()
    deliveries: tuple[DeliveryFact, ...] = ()
    rejections: tuple[InputRejection, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "org_id", require_identifier(self.org_id, "org id"))
        object.__setattr__(self, "evaluated_at", require_aware(self.evaluated_at, "evaluated_at"))


def _moments(values: Iterable[datetime]) -> tuple[datetime, ...]:
    return tuple(sorted(require_aware(value, "evidence time") for value in values))


def _visibility(values: Iterable[Mapping[str, Any]]) -> Mapping[str, Any]:
    parsed = [Visibility.model_validate(dict(value)) for value in values]
    return freeze_mapping(narrowest(*parsed).model_dump())


def _audience_suffix(visibility: Mapping[str, Any]) -> str:
    """Keep aggregates from different ACL cohorts from colliding in one metric/brain slot."""
    return semantic_hash(dict(visibility))[:16]


def _trace_ids(values: Iterable[str | None]) -> tuple[str, ...]:
    return tuple(sorted({str(value) for value in values if value}))


def _independence(values: Iterable[str | None], fallbacks: Iterable[str]) -> tuple[str, ...]:
    pairs = zip(values, fallbacks, strict=True)
    return tuple(sorted({str(value or fallback) for value, fallback in pairs}))


def _evidence(*, refs: Iterable[str], moments: Iterable[datetime], positive: int,
              negative: int, observations: int, evaluated_at: datetime,
              independent_refs: Iterable[str] = (), trace_ids: Iterable[str] = (),
              business_value_bp: int = 5_000, noise: int = 0,
              conflict: int = 0) -> LearningEvidence:
    refs_tuple = tuple(refs)
    require_aware(evaluated_at, "evaluated_at")
    independent_tuple = tuple(independent_refs) or refs_tuple
    moments_tuple = _moments(moments)
    return LearningEvidence(
        observations=observations, distinct_days=_day_count(moments_tuple), positive=positive,
        negative=negative,
        confidence_bp=_confidence(positive, negative, len(set(independent_tuple))),
        noise_bp=_bp(noise, observations), conflict_bp=_bp(conflict, observations),
        # Stored identity describes the evidence at its last observation. Current freshness is
        # recomputed by governance from ``last_seen_at`` and the review/evaluation clock, so a
        # retry tomorrow cannot mint a different LearningObject from identical source facts.
        freshness_bp=10_000,
        business_value_bp=business_value_bp, source_refs=refs_tuple,
        independent_refs=independent_tuple, trace_ids=tuple(trace_ids))


def _object_times(moments: Iterable[datetime]) -> tuple[datetime, datetime]:
    values = _moments(moments)
    if not values:
        raise ValueError("learning evidence needs at least one timestamp")
    return values[0], values[-1]


def feedback_learning(batch: LearningBatch) -> list[LearningObject]:
    """Unit 1: explicit feedback taxonomy.  Silence is never turned into a label."""
    groups: dict[tuple[str, str], list[FeedbackFact]] = defaultdict(list)
    for fact in batch.feedback:
        if fact.explicit:
            groups[(fact.subject_key, canonical_dumps(fact.visibility))].append(fact)
    out: list[LearningObject] = []
    positive_actions = {"accepted", "executed", "run_play", "do_it_myself"}
    negative_actions = {"rejected", "cancelled"}
    for (key, _visibility_key), facts in sorted(groups.items()):
        positive = sum(item.action in positive_actions for item in facts)
        negative = sum(item.action in negative_actions or (
            item.action == "wrong" and item.reason in {"not_relevant", "wrong_facts"})
                       for item in facts)
        timing = sum(item.action == "snooze" or (
            item.action == "wrong" and item.reason == "bad_timing") for item in facts)
        moments = tuple(f.occurred_at for f in facts)
        first_seen, last_seen = _object_times(moments)
        refs = tuple(f.source_ref or f.feedback_id for f in facts)
        visibility = _visibility(f.visibility for f in facts)
        out.append(LearningObject(
            org_id=batch.org_id, unit=LearningUnit.FEEDBACK, target=LearningTarget.METRICS,
            subject_key=f"feedback:{key}:audience:{_audience_suffix(visibility)}",
            value={"accepted": positive, "rejected": negative, "timing": timing,
                   "neutral": len(facts) - positive - negative},
            evidence=_evidence(
                refs=refs, moments=moments, positive=positive, negative=negative,
                observations=len(facts), evaluated_at=batch.evaluated_at,
                independent_refs=_independence(
                    (f.independence_key for f in facts), refs),
                trace_ids=_trace_ids(f.trace_id for f in facts),
                noise=len(facts) - positive - negative),
            observed_at=last_seen, first_seen_at=first_seen, last_seen_at=last_seen,
            visibility=visibility,
            lineage_complete=all(f.lineage_complete for f in facts)))
    return out


def _outcome_groups(batch: LearningBatch) -> dict[tuple[str, str, str], list[OutcomeFact]]:
    groups: dict[tuple[str, str, str], list[OutcomeFact]] = defaultdict(list)
    for fact in batch.outcomes:
        groups[(fact.capability_id, fact.play_id, canonical_dumps(fact.visibility))].append(fact)
    return groups


def outcome_analysis(batch: LearningBatch) -> list[LearningObject]:
    """Unit 2: effectiveness and attention cost from the durable ExecutionOutcome seam."""
    out: list[LearningObject] = []
    for (capability, play, _visibility_key), facts in sorted(_outcome_groups(batch).items()):
        positive = sum(f.label in SUCCESS_LABELS for f in facts)
        negative = sum(f.label in FAILURE_LABELS for f in facts)
        neutral = sum(f.label in NEUTRAL_LABELS for f in facts)
        labelled = positive + negative
        reminders = sum(f.reminders_sent for f in facts)
        escalations = sum(f.escalations_fired for f in facts)
        moments = tuple(f.closed_at for f in facts)
        first_seen, last_seen = _object_times(moments)
        refs = tuple(f.outcome_id for f in facts)
        value = {"capability_id": capability, "play_id": play, "outcomes": len(facts),
                 "successes": positive, "failures": negative, "unproven": neutral,
                 "success_bp": _bp(positive, labelled),
                 "average_progress_bp": sum(f.progress_bp for f in facts) // len(facts),
                 "attention_cost_bp": min(10_000, _bp(
                     reminders + 2 * escalations, max(1, len(facts) * 4))),
                 "average_seconds_to_close": sum(f.seconds_to_close for f in facts) // len(facts)}
        visibility = _visibility(f.visibility for f in facts)
        out.append(LearningObject(
            org_id=batch.org_id, unit=LearningUnit.OUTCOME, target=LearningTarget.METRICS,
            subject_key=(f"outcome:{capability}:{play}:audience:"
                         f"{_audience_suffix(visibility)}"), value=value,
            evidence=_evidence(
                refs=refs, moments=moments, positive=positive, negative=negative,
                observations=len(facts), evaluated_at=batch.evaluated_at,
                independent_refs=_independence(
                    (f.independence_key for f in facts), refs),
                trace_ids=_trace_ids(f.trace_id for f in facts),
                business_value_bp=8_000),
            observed_at=last_seen, first_seen_at=first_seen, last_seen_at=last_seen,
            visibility=visibility,
            lineage_complete=all(f.lineage_complete for f in facts)))
    return out


def pattern_learning(batch: LearningBatch) -> list[LearningObject]:
    """Unit 3: repeated normalized enterprise events; no semantic guessing from prose."""
    groups: dict[tuple[str, str, str], list[EnterpriseFact]] = defaultdict(list)
    for fact in batch.events:
        if not fact.explicit_memory:
            groups[(fact.pattern_key, fact.kind, canonical_dumps(fact.visibility))].append(fact)
    out: list[LearningObject] = []
    for (key, kind, _visibility_key), facts in sorted(groups.items()):
        days = _day_count(f.occurred_at for f in facts)
        refs = tuple(f.event_id for f in facts)
        independent = _independence((f.independence_key for f in facts), refs)
        moments = tuple(f.occurred_at for f in facts)
        first_seen, last_seen = _object_times(moments)
        average_source_confidence = sum(f.source_confidence_bp for f in facts) // len(facts)
        support = min(10_000, len(independent) * 1_000)
        visibility = _visibility(f.visibility for f in facts)
        evidence = LearningEvidence(
            observations=len(facts), distinct_days=days, positive=len(facts), negative=0,
            confidence_bp=average_source_confidence * support // 10_000,
            freshness_bp=10_000,
            business_value_bp=6_000, source_refs=refs, independent_refs=independent,
            trace_ids=_trace_ids(f.trace_id for f in facts))
        out.append(LearningObject(
            org_id=batch.org_id, unit=LearningUnit.PATTERN, target=LearningTarget.ORGANIZATION,
            subject_key=(f"pattern:{key}:{kind}:audience:"
                         f"{_audience_suffix(visibility)}"),
            value={"pattern_key": key, "kind": kind, "occurrences": len(facts),
                   "distinct_days": days}, evidence=evidence, observed_at=last_seen,
            first_seen_at=first_seen, last_seen_at=last_seen,
            visibility=visibility,
            lineage_complete=all(f.lineage_complete for f in facts)))
    return out


def preference_learning(batch: LearningBatch) -> list[LearningObject]:
    """Unit 4: structured, explicit preferences only. Repetition still governs permanence."""
    groups: dict[tuple[str, str, str, str], list[FeedbackFact]] = defaultdict(list)
    for fact in batch.feedback:
        if (fact.explicit and fact.preference_key and fact.preference_scope
                and fact.preference_value is not None):
            principal = fact.actor_key if fact.preference_scope == "user" else "organization"
            groups[(fact.preference_scope, str(principal), fact.preference_key,
                    str(fact.preference_category))].append(fact)
    out: list[LearningObject] = []
    for (scope, principal, key, category), facts in sorted(groups.items()):
        values: dict[str, list[FeedbackFact]] = defaultdict(list)
        for fact in facts:
            values[canonical_dumps(fact.preference_value)].append(fact)
        winner_key, winner_facts = sorted(values.items(), key=lambda pair: (-len(pair[1]), pair[0]))[0]
        del winner_key
        winner = winner_facts[0].preference_value
        positive = len(winner_facts)
        negative = len(facts) - positive
        refs = tuple(f.source_ref or f.feedback_id for f in facts)
        moments = tuple(f.occurred_at for f in facts)
        first_seen, last_seen = _object_times(moments)
        target = (LearningTarget.BEHAVIOR if scope == "user"
                  else LearningTarget.ORGANIZATION)
        subject = (f"preference:user:{principal}:{key}" if scope == "user"
                   else f"preference:organization:{key}")
        subject_principals = sorted({f.subject_principal for f in facts
                                     if f.subject_principal is not None})
        source_visibility = _visibility(f.visibility for f in facts)
        subject_principal = (subject_principals[0]
                             if scope == "user" and len(subject_principals) == 1 else None)
        visibility = source_visibility
        subject_visible = True
        if scope == "user":
            visibility, subject_visible = _subject_visibility(
                source_visibility, subject_principal)
        out.append(LearningObject(
            org_id=batch.org_id, unit=LearningUnit.PREFERENCE, target=target,
            subject_key=subject,
            value={"key": key, "value": winner, "scope": scope, "category": category,
                   "support": positive, "competing": negative},
            evidence=_evidence(
                refs=refs, moments=moments, positive=positive, negative=negative,
                observations=len(facts), evaluated_at=batch.evaluated_at,
                independent_refs=_independence(
                    (f.independence_key for f in facts), refs),
                trace_ids=_trace_ids(f.trace_id for f in facts),
                business_value_bp=7_000, conflict=negative),
            observed_at=last_seen, first_seen_at=first_seen, last_seen_at=last_seen,
            visibility=visibility,
            lineage_complete=(all(f.lineage_complete for f in facts) and subject_visible),
            subject_principal=subject_principal))
    return out


def temporary_memory(batch: LearningBatch) -> list[LearningObject]:
    """Unit 5: only an explicit memory directive can create leased runtime context."""
    out: list[LearningObject] = []
    for fact in sorted(batch.events, key=lambda item: item.event_id):
        if not fact.explicit_memory or fact.expires_at is None or fact.expires_at <= batch.evaluated_at:
            continue
        out.append(LearningObject(
            org_id=batch.org_id, unit=LearningUnit.TEMPORARY_MEMORY,
            target=LearningTarget.RUNTIME, subject_key=f"memory:{fact.pattern_key}",
            value=fact.value,
            evidence=LearningEvidence(
                observations=1, distinct_days=1, positive=1, negative=0,
                confidence_bp=10_000, business_value_bp=7_000,
                source_refs=(fact.event_id,),
                independent_refs=(fact.independence_key or fact.event_id,),
                trace_ids=_trace_ids((fact.trace_id,))),
            observed_at=fact.occurred_at, expires_at=fact.expires_at,
            first_seen_at=fact.occurred_at, last_seen_at=fact.occurred_at,
            visibility=fact.visibility, lineage_complete=fact.lineage_complete,
            subject_principal=fact.actor_key,
            metadata={"explicit": True}))
    return out


_BEHAVIOR_CATEGORIES = frozenset({
    "communication_style", "decision_style", "meeting_habit", "execution_habit",
    "relationship_pattern"})


def behavior_evolution(batch: LearningBatch) -> list[LearningObject]:
    """Unit 6: behavior-shaped preference evidence, kept separate for brain provenance."""
    return [LearningObject(
        org_id=item.org_id, unit=LearningUnit.BEHAVIOR, target=LearningTarget.BEHAVIOR,
        subject_key=item.subject_key.replace("preference:", "behavior:", 1), value=item.value,
        evidence=item.evidence, observed_at=item.observed_at,
        first_seen_at=item.first_seen_at, last_seen_at=item.last_seen_at,
        trace_id=item.trace_id, visibility=item.visibility,
        lineage_complete=item.lineage_complete, subject_principal=item.subject_principal,
        metadata={"derived_from": item.learning_id})
        for item in preference_learning(batch)
        if item.value.get("category") in _BEHAVIOR_CATEGORIES]


_ADAPTIVE_CATEGORIES = frozenset({
    "current_priority", "notification_style", "execution_preference", "runtime_personalization"})


def adaptive_evolution(batch: LearningBatch) -> list[LearningObject]:
    """Unit 7: current operating preferences, not stable personality claims."""
    return [LearningObject(
        org_id=item.org_id, unit=LearningUnit.ADAPTIVE, target=LearningTarget.ADAPTIVE,
        subject_key=item.subject_key.replace("preference:", "adaptive:", 1), value=item.value,
        evidence=item.evidence, observed_at=item.observed_at,
        first_seen_at=item.first_seen_at, last_seen_at=item.last_seen_at,
        trace_id=item.trace_id, visibility=item.visibility,
        lineage_complete=item.lineage_complete, subject_principal=item.subject_principal,
        metadata={"derived_from": item.learning_id})
        for item in preference_learning(batch)
        if item.value.get("category") in _ADAPTIVE_CATEGORIES]


def recommendation_learning(batch: LearningBatch) -> list[LearningObject]:
    """Unit 8: publish play efficacy to the Adaptive Brain after governed validation."""
    return [LearningObject(
        org_id=item.org_id, unit=LearningUnit.RECOMMENDATION, target=LearningTarget.ADAPTIVE,
        subject_key=item.subject_key.replace("outcome:", "recommendation:", 1),
        value=item.value, evidence=item.evidence, observed_at=item.observed_at,
        first_seen_at=item.first_seen_at, last_seen_at=item.last_seen_at,
        trace_id=item.trace_id, visibility=item.visibility,
        lineage_complete=item.lineage_complete,
        metadata={"derived_from": item.learning_id}) for item in outcome_analysis(batch)]


def performance_optimization(batch: LearningBatch) -> list[LearningObject]:
    """Unit 9: separate transport and lifecycle endings without inventing outcomes."""
    groups: dict[tuple[str, str], list[DeliveryFact]] = defaultdict(list)
    for fact in batch.deliveries:
        groups[(fact.channel, canonical_dumps(fact.visibility))].append(fact)
    out: list[LearningObject] = []
    for (channel, _visibility_key), facts in sorted(groups.items()):
        delivered = sum(f.status in {"delivered", "viewed", "ignored", "accepted", "executed"}
                        or f.delivered_at is not None for f in facts)
        # A tracker may move ACCEPTED -> FAILED when downstream execution fails.  Transport was
        # still successful in that case; only a failure before the first delivered receipt is a
        # transport failure.  Business/execution failure belongs in outcomes, not this metric.
        failed = sum(f.status == "failed" and f.delivered_at is None for f in facts)
        queued = sum(f.status == "queued" for f in facts)
        deferred = sum(f.status == "deferred" for f in facts)
        suppressed = sum(f.status == "suppressed" for f in facts)
        cancelled = sum(f.status == "cancelled" for f in facts)
        expired = sum(f.status == "expired" for f in facts)
        terminal_transport = delivered + failed
        latencies = sorted(int((f.delivered_at - f.created_at).total_seconds() * 1000)
                           for f in facts if f.delivered_at is not None)
        moments = tuple(max(filter(None, (
            f.executed_at, f.accepted_at, f.ignored_at, f.viewed_at, f.expired_at,
            f.delivered_at, f.lifecycle_at, f.created_at))) for f in facts)
        first_seen, last_seen = _object_times(moments)
        refs = tuple(f.delivery_id for f in facts)
        visibility = _visibility(f.visibility for f in facts)
        out.append(LearningObject(
            org_id=batch.org_id, unit=LearningUnit.PERFORMANCE, target=LearningTarget.METRICS,
            subject_key=(f"performance:delivery:{channel}:audience:"
                         f"{_audience_suffix(visibility)}"),
            value={"channel": channel, "total": len(facts), "delivered": delivered,
                   "failed": failed, "queued": queued, "deferred": deferred,
                   "suppressed": suppressed, "cancelled": cancelled, "expired": expired,
                   "open": queued + deferred,
                   "delivered_bp": _bp(delivered, terminal_transport),
                   "viewed": sum(f.viewed_at is not None for f in facts),
                   "ignored": sum(f.ignored_at is not None for f in facts),
                   "accepted": sum(f.accepted_at is not None or f.executed_at is not None
                                   for f in facts),
                   "executed": sum(f.executed_at is not None for f in facts),
                   "attempts": sum(f.attempts for f in facts),
                   "deferrals": sum(f.deferrals for f in facts),
                   "latency_p50_ms": latencies[(len(latencies) - 1) // 2] if latencies else None},
            evidence=_evidence(
                refs=refs, moments=moments, positive=delivered, negative=failed,
                observations=len(facts), evaluated_at=batch.evaluated_at,
                independent_refs=_independence(
                    (f.independence_key or f.execution_id for f in facts), refs),
                trace_ids=_trace_ids(f.trace_id for f in facts),
                business_value_bp=5_000),
            observed_at=last_seen, first_seen_at=first_seen, last_seen_at=last_seen,
            visibility=visibility,
            lineage_complete=all(f.lineage_complete for f in facts)))
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
            target=LearningTarget.KNOWLEDGE_SUGGESTION,
            subject_key=item.subject_key.replace("outcome:", "knowledge:review:", 1),
            value={"suggestion_type": "review_play", "reason": "sustained_low_outcome_rate",
                   "cohort": value}, evidence=item.evidence, observed_at=item.observed_at,
            first_seen_at=item.first_seen_at, last_seen_at=item.last_seen_at,
            trace_id=item.trace_id, visibility=item.visibility,
            lineage_complete=item.lineage_complete,
            metadata={"human_review_required": True, "derived_from": item.learning_id}))
    return out


ALL_ANALYSIS_UNITS = (
    feedback_learning, outcome_analysis, pattern_learning, preference_learning, temporary_memory,
    behavior_evolution, adaptive_evolution, recommendation_learning, performance_optimization,
    knowledge_evolution,
)


def run_units(batch: LearningBatch) -> list[LearningObject]:
    """Selector + planner: only units with relevant inputs return objects; order is canonical."""
    # The tuple is the Atlas plan. Each unit sorts its own cohorts; a final alphabetical sort would
    # silently replace the declared plan with enum spelling.
    return [obj for unit in ALL_ANALYSIS_UNITS for obj in unit(batch)]


__all__ = ["ALL_ANALYSIS_UNITS", "DeliveryFact", "EnterpriseFact", "FeedbackFact",
           "InputRejection", "LearningBatch", "OutcomeFact", "adaptive_evolution", "behavior_evolution",
           "feedback_learning", "knowledge_evolution", "outcome_analysis", "pattern_learning",
           "performance_optimization", "preference_learning", "recommendation_learning",
           "run_units", "temporary_memory"]
