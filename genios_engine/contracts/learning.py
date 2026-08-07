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
    require_bool,
    require_enum,
    require_identifier,
    require_non_negative,
    require_sorted_unique,
)
from genios_engine.contracts.visibility import PRIVATE, Visibility
from genios_engine.platform.canonical import decanonicalize, semantic_hash, stable_id

LEARNING_VERSION = "learning.v2"


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
    """The four Atlas brains. Expert Brain is intentionally absent."""

    ORGANIZATION = "organization"
    BEHAVIOR = "behavior"
    ADAPTIVE = "adaptive"
    RUNTIME = "runtime"


class LearningTarget(str, Enum):
    """Every publication seam, keeping non-brain artifacts out of ``BrainTarget``."""

    ORGANIZATION = BrainTarget.ORGANIZATION.value
    BEHAVIOR = BrainTarget.BEHAVIOR.value
    ADAPTIVE = BrainTarget.ADAPTIVE.value
    RUNTIME = BrainTarget.RUNTIME.value
    METRICS = "metrics"
    KNOWLEDGE_SUGGESTION = "knowledge_suggestion"


BRAIN_TARGETS = frozenset({
    LearningTarget.ORGANIZATION,
    LearningTarget.BEHAVIOR,
    LearningTarget.ADAPTIVE,
    LearningTarget.RUNTIME,
})


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
    # A human rollback may restore the exact predecessor after the bad successor is removed.
    # The transition ledger retains both publications; the object payload itself never changes.
    LearningState.SUPERSEDED: (LearningState.PUBLISHED,),
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
    independent_refs: tuple[str, ...] = ()
    trace_ids: tuple[str, ...] = ()

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
        independent = self.independent_refs or self.source_refs
        setter(self, "independent_refs", require_sorted_unique(independent, "independent ref"))
        if len(self.independent_refs) > self.observations:
            raise ValueError("independent evidence cannot exceed observations")
        setter(self, "trace_ids", require_sorted_unique(self.trace_ids, "trace id"))

    @property
    def independent_observations(self) -> int:
        """Evidence support, after repeated rows from one origin have been collapsed."""
        return len(self.independent_refs)

    def to_semantic_dict(self, *, schema_version: str = LEARNING_VERSION) -> dict[str, Any]:
        result = {"observations": self.observations, "distinct_days": self.distinct_days,
                "positive": self.positive, "negative": self.negative,
                "confidence_bp": self.confidence_bp, "noise_bp": self.noise_bp,
                "conflict_bp": self.conflict_bp, "freshness_bp": self.freshness_bp,
                "business_value_bp": self.business_value_bp,
                "source_refs": self.source_refs}
        if schema_version != "learning.v1":
            result["independent_refs"] = self.independent_refs
            result["trace_ids"] = self.trace_ids
        return result


@dataclass(frozen=True, slots=True)
class LearningObject:
    """One replayable proposal produced by exactly one of the eleven units."""

    org_id: str
    unit: LearningUnit
    target: LearningTarget
    subject_key: str
    value: Mapping[str, Any]
    evidence: LearningEvidence
    observed_at: datetime
    first_seen_at: datetime | None = None
    last_seen_at: datetime | None = None
    trace_id: str | None = None
    visibility: Mapping[str, Any] = field(default_factory=lambda: Visibility(
        scope=PRIVATE, principals=[], derived_from="missing:learning-lineage").model_dump())
    lineage_complete: bool = False
    subject_principal: str | None = None
    policy_key: str = "default"
    expires_at: datetime | None = None
    metadata: Mapping[str, Any] = field(default_factory=lambda: MappingProxyType({}))
    schema_version: str = LEARNING_VERSION

    def __post_init__(self) -> None:
        setter = object.__setattr__
        setter(self, "org_id", require_identifier(self.org_id, "org id"))
        setter(self, "unit", require_enum(self.unit, LearningUnit, "learning unit"))
        setter(self, "target", require_enum(self.target, LearningTarget, "learning target"))
        setter(self, "subject_key", require_identifier(self.subject_key, "subject key"))
        setter(self, "value", freeze_mapping(self.value))
        if not isinstance(self.evidence, LearningEvidence):
            raise TypeError("evidence must be LearningEvidence")
        setter(self, "observed_at", require_aware(self.observed_at, "observed_at"))
        first_seen = require_aware(
            self.first_seen_at or self.observed_at, "first_seen_at")
        last_seen = require_aware(self.last_seen_at or self.observed_at, "last_seen_at")
        if first_seen > last_seen:
            raise ValueError("first_seen_at cannot be later than last_seen_at")
        if self.observed_at != last_seen:
            raise ValueError("observed_at must equal last_seen_at")
        setter(self, "first_seen_at", first_seen)
        setter(self, "last_seen_at", last_seen)
        source_traces = self.evidence.trace_ids or self.evidence.source_refs
        trace_id = self.trace_id
        if trace_id is None:
            trace_id = (source_traces[0] if len(source_traces) == 1 else stable_id(
                "ltrace", {"org_id": self.org_id, "source_trace_ids": source_traces}))
        setter(self, "trace_id", require_identifier(trace_id, "trace id"))
        raw_visibility = dict(self.visibility or {})
        if (self.schema_version != "learning.v1"
                and not {"scope", "principals", "derived_from"} <= set(raw_visibility)):
            raise ValueError("learning.v2 visibility requires scope, principals and derived_from")
        try:
            visibility = Visibility.model_validate(raw_visibility)
        except (TypeError, ValueError) as exc:
            raise ValueError("visibility must be a valid source visibility") from exc
        derived_from = str(visibility.derived_from or "").strip()
        if not derived_from:
            raise ValueError("visibility derived_from is required")
        visibility = Visibility(
            scope=visibility.scope,
            principals=sorted({str(value).strip().lower() for value in visibility.principals
                               if str(value).strip()}),
            derived_from=derived_from,
        )
        setter(self, "visibility", freeze_mapping(visibility.model_dump()))
        setter(self, "lineage_complete", require_bool(self.lineage_complete,
                                                       "lineage_complete"))
        if self.subject_principal is not None:
            setter(self, "subject_principal",
                   require_identifier(self.subject_principal, "subject principal"))
        setter(self, "policy_key", require_identifier(self.policy_key, "policy key"))
        if self.expires_at is not None:
            setter(self, "expires_at", require_aware(self.expires_at, "expires_at"))
            if self.expires_at <= self.observed_at:
                raise ValueError("expires_at must be later than observed_at")
        if self.target is LearningTarget.RUNTIME and self.expires_at is None:
            raise ValueError("runtime learning requires expires_at")
        if self.target is not LearningTarget.RUNTIME and self.expires_at is not None:
            raise ValueError("only runtime learning may carry expires_at")
        if (self.unit is LearningUnit.KNOWLEDGE
                and self.target is not LearningTarget.KNOWLEDGE_SUGGESTION):
            raise ValueError("knowledge evolution can only create a knowledge suggestion")
        setter(self, "metadata", freeze_mapping(self.metadata))
        setter(self, "schema_version",
               require_identifier(self.schema_version, "learning schema version"))
        if self.schema_version not in {"learning.v1", LEARNING_VERSION}:
            raise ValueError(f"unsupported learning schema version: {self.schema_version}")

    def to_semantic_dict(self) -> dict[str, Any]:
        result = {"schema_version": self.schema_version, "org_id": self.org_id,
                "unit": self.unit.value, "target": self.target.value,
                "subject_key": self.subject_key, "value": self.value,
                "evidence": self.evidence.to_semantic_dict(schema_version=self.schema_version),
                "observed_at": self.observed_at, "policy_key": self.policy_key,
                "expires_at": self.expires_at, "metadata": self.metadata}
        # Keep v1 hashes byte-for-byte compatible with already-persisted objects. New fields are
        # part of every v2 identity and therefore cannot be changed after observation.
        if self.schema_version != "learning.v1":
            result.update({"first_seen_at": self.first_seen_at,
                           "last_seen_at": self.last_seen_at,
                           "trace_id": self.trace_id,
                           "visibility": self.visibility,
                           "lineage_complete": self.lineage_complete,
                           "subject_principal": self.subject_principal})
        return result

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
            target=LearningTarget(data["target"]), subject_key=data["subject_key"],
            value=data["value"],
            evidence=LearningEvidence(
                observations=evidence["observations"], distinct_days=evidence["distinct_days"],
                positive=evidence["positive"], negative=evidence["negative"],
                confidence_bp=evidence["confidence_bp"], noise_bp=evidence["noise_bp"],
                conflict_bp=evidence["conflict_bp"], freshness_bp=evidence["freshness_bp"],
                business_value_bp=evidence["business_value_bp"],
                source_refs=tuple(evidence.get("source_refs") or ()),
                independent_refs=tuple(evidence.get("independent_refs") or ()),
                trace_ids=tuple(evidence.get("trace_ids") or ())),
            observed_at=data["observed_at"],
            first_seen_at=data.get("first_seen_at"), last_seen_at=data.get("last_seen_at"),
            trace_id=data.get("trace_id"), visibility=data.get("visibility") or Visibility(
                scope=PRIVATE, principals=[], derived_from="legacy:learning-v1").model_dump(),
            lineage_complete=bool(data.get("lineage_complete", False)),
            subject_principal=data.get("subject_principal"),
            policy_key=data.get("policy_key", "default"),
            expires_at=data.get("expires_at"), metadata=data.get("metadata") or {},
            schema_version=data.get("schema_version", "learning.v1"))

    def verify_round_trip(self) -> None:
        restored = self.from_semantic_dict(self.to_semantic_dict())
        if restored.semantic_hash != self.semantic_hash:
            raise ValueError(f"learning object does not round-trip: {self.learning_id}")


__all__ = ["ALLOWED_LEARNING_TRANSITIONS", "BRAIN_TARGETS", "LEARNING_VERSION", "BrainTarget",
           "LearningEvidence", "LearningObject", "LearningState", "LearningTarget",
           "LearningUnit", "can_transition_learning"]
