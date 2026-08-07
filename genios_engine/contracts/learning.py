"""The immutable Atlas Layer 6 output: a governed proposal to change learned state.

Learning never writes a mutable conclusion directly into a brain.  A ``LearningObject`` first
records the proposed value, its evidence and its destination; a separate database lifecycle then
moves that object through observed, candidate, validated, governed and publication states.  This
separation makes promotion reversible without rewriting history and gives every published value a
stable explanation.

The contract deliberately contains no Expert Brain target.  Knowledge evolution is represented by
``KNOWLEDGE_SUGGESTION`` and must go through human review; code cannot accidentally turn a drift
signal into an expert-pack edit because no such publisher vocabulary exists here.

Import rule: this module sits in ``contracts/`` and may import nothing above ``platform``.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from types import MappingProxyType
from typing import Any

from genios_engine.contracts.validators import (
    freeze_mapping,
    require_aware,
    require_bp,
    require_enum,
    require_identifier,
    require_non_negative,
    require_sorted_unique,
)
from genios_engine.platform.canonical import decanonicalize, semantic_hash, stable_id

LEARNING_VERSION = "learning.v1"


class LearningUnit(str, Enum):
    FEEDBACK = "feedback_learning"
    OUTCOME = "outcome_analysis"
    PATTERN = "pattern_learning"
    PREFERENCE = "preference_learning"
    TEMPORARY_MEMORY = "temporary_memory"
    BEHAVIOR = "behavior_evolution"
    ADAPTIVE = "adaptive_evolution"
    RECOMMENDATION = "recommendation_learning"
    PERFORMANCE = "performance_optimization"
    KNOWLEDGE = "knowledge_evolution"
    VALIDATION = "learning_validation"


class BrainTarget(str, Enum):
    """The complete write vocabulary.  Expert Brain is intentionally absent."""

    ORGANIZATION = "organization"
    BEHAVIOR = "behavior"
    ADAPTIVE = "adaptive"
    RUNTIME = "runtime"
    METRICS = "metrics"
    KNOWLEDGE_SUGGESTION = "knowledge_suggestion"


class LearningState(str, Enum):
    OBSERVED = "observed"
    CANDIDATE = "candidate"
    VALIDATED = "validated"
    GOVERNED = "governed"
    TEMPORARY = "temporary"
    HUMAN_REVIEW = "human_review"
    PROMOTED = "promoted"
    PUBLISHED = "published"
    REJECTED = "rejected"
    EXPIRED = "expired"
    SUPERSEDED = "superseded"
    ROLLED_BACK = "rolled_back"


ALLOWED_LEARNING_TRANSITIONS: MappingProxyType = MappingProxyType({
    LearningState.OBSERVED: (LearningState.CANDIDATE, LearningState.REJECTED),
    LearningState.CANDIDATE: (LearningState.VALIDATED, LearningState.REJECTED),
    LearningState.VALIDATED: (LearningState.GOVERNED, LearningState.REJECTED),
    LearningState.GOVERNED: (LearningState.TEMPORARY, LearningState.HUMAN_REVIEW,
                             LearningState.PROMOTED, LearningState.REJECTED),
    LearningState.HUMAN_REVIEW: (LearningState.PROMOTED, LearningState.REJECTED),
    LearningState.TEMPORARY: (LearningState.EXPIRED,),
    LearningState.PROMOTED: (LearningState.PUBLISHED, LearningState.REJECTED),
    LearningState.PUBLISHED: (LearningState.SUPERSEDED, LearningState.ROLLED_BACK),
    LearningState.REJECTED: (),
    LearningState.EXPIRED: (),
    LearningState.SUPERSEDED: (),
    LearningState.ROLLED_BACK: (),
})


def can_transition_learning(current: LearningState, target: LearningState) -> bool:
    return target in ALLOWED_LEARNING_TRANSITIONS.get(current, ())


@dataclass(frozen=True, slots=True)
class LearningEvidence:
    """Deterministic evidence summary used by validation and governance.

    Counts are kept separately so contradictory evidence cannot disappear inside a single score.
    ``confidence_bp`` is derived by a unit, but governance still sees the raw repetition, noise,
    conflict and freshness inputs that produced it.
    """

    observations: int
    distinct_days: int
    positive: int
    negative: int
    confidence_bp: int
    noise_bp: int = 0
    conflict_bp: int = 0
    freshness_bp: int = 10_000
    business_value_bp: int = 5_000
    source_refs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        setter = object.__setattr__
        for name in ("observations", "distinct_days", "positive", "negative"):
            setter(self, name, require_non_negative(getattr(self, name), name))
        if self.positive + self.negative > self.observations:
            raise ValueError("positive + negative cannot exceed observations")
        for name in ("confidence_bp", "noise_bp", "conflict_bp", "freshness_bp",
                     "business_value_bp"):
            setter(self, name, require_bp(getattr(self, name), name))
        setter(self, "source_refs", require_sorted_unique(self.source_refs, "source ref"))

    def to_semantic_dict(self) -> dict[str, Any]:
        return {"observations": self.observations, "distinct_days": self.distinct_days,
                "positive": self.positive, "negative": self.negative,
                "confidence_bp": self.confidence_bp, "noise_bp": self.noise_bp,
                "conflict_bp": self.conflict_bp, "freshness_bp": self.freshness_bp,
                "business_value_bp": self.business_value_bp,
                "source_refs": self.source_refs}


@dataclass(frozen=True, slots=True)
class LearningObject:
    """One replayable proposal produced by exactly one of the eleven units."""

    org_id: str
    unit: LearningUnit
    target: BrainTarget
    subject_key: str
    value: Mapping[str, Any]
    evidence: LearningEvidence
    observed_at: datetime
    policy_key: str = "default"
    expires_at: datetime | None = None
    metadata: Mapping[str, Any] = field(default_factory=lambda: MappingProxyType({}))
    schema_version: str = LEARNING_VERSION

    def __post_init__(self) -> None:
        setter = object.__setattr__
        setter(self, "org_id", require_identifier(self.org_id, "org id"))
        setter(self, "unit", require_enum(self.unit, LearningUnit, "learning unit"))
        setter(self, "target", require_enum(self.target, BrainTarget, "brain target"))
        setter(self, "subject_key", require_identifier(self.subject_key, "subject key"))
        setter(self, "value", freeze_mapping(self.value))
        if not isinstance(self.evidence, LearningEvidence):
            raise TypeError("evidence must be LearningEvidence")
        setter(self, "observed_at", require_aware(self.observed_at, "observed_at"))
        setter(self, "policy_key", require_identifier(self.policy_key, "policy key"))
        if self.expires_at is not None:
            setter(self, "expires_at", require_aware(self.expires_at, "expires_at"))
            if self.expires_at <= self.observed_at:
                raise ValueError("expires_at must be later than observed_at")
        if self.target is BrainTarget.RUNTIME and self.expires_at is None:
            raise ValueError("runtime learning requires expires_at")
        if self.target is not BrainTarget.RUNTIME and self.expires_at is not None:
            raise ValueError("only runtime learning may carry expires_at")
        if self.unit is LearningUnit.KNOWLEDGE and self.target is not BrainTarget.KNOWLEDGE_SUGGESTION:
            raise ValueError("knowledge evolution can only create a knowledge suggestion")
        setter(self, "metadata", freeze_mapping(self.metadata))
        setter(self, "schema_version",
               require_identifier(self.schema_version, "learning schema version"))

    def to_semantic_dict(self) -> dict[str, Any]:
        return {"schema_version": self.schema_version, "org_id": self.org_id,
                "unit": self.unit.value, "target": self.target.value,
                "subject_key": self.subject_key, "value": self.value,
                "evidence": self.evidence.to_semantic_dict(),
                "observed_at": self.observed_at, "policy_key": self.policy_key,
                "expires_at": self.expires_at, "metadata": self.metadata}

    @property
    def semantic_hash(self) -> str:
        return semantic_hash(self.to_semantic_dict())

    @property
    def learning_id(self) -> str:
        return stable_id("learn", self.to_semantic_dict())

    @classmethod
    def from_semantic_dict(cls, payload: Mapping[str, Any]) -> LearningObject:
        data = decanonicalize(dict(payload))
        evidence = data["evidence"]
        return cls(
            org_id=data["org_id"], unit=LearningUnit(data["unit"]),
            target=BrainTarget(data["target"]), subject_key=data["subject_key"],
            value=data["value"],
            evidence=LearningEvidence(
                observations=evidence["observations"], distinct_days=evidence["distinct_days"],
                positive=evidence["positive"], negative=evidence["negative"],
                confidence_bp=evidence["confidence_bp"], noise_bp=evidence["noise_bp"],
                conflict_bp=evidence["conflict_bp"], freshness_bp=evidence["freshness_bp"],
                business_value_bp=evidence["business_value_bp"],
                source_refs=tuple(evidence.get("source_refs") or ())),
            observed_at=data["observed_at"], policy_key=data.get("policy_key", "default"),
            expires_at=data.get("expires_at"), metadata=data.get("metadata") or {},
            schema_version=data.get("schema_version", LEARNING_VERSION))

    def verify_round_trip(self) -> None:
        restored = self.from_semantic_dict(self.to_semantic_dict())
        if restored.semantic_hash != self.semantic_hash:
            raise ValueError(f"learning object does not round-trip: {self.learning_id}")


__all__ = ["ALLOWED_LEARNING_TRANSITIONS", "LEARNING_VERSION", "BrainTarget",
           "LearningEvidence", "LearningObject", "LearningState", "LearningUnit",
           "can_transition_learning"]
