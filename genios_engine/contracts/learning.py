"""Layer 6 boundary contract — the immutable LearningObject v2 and its vocabulary.

Layer 6 learns from *outcomes*, records a *proposal* before it changes any state, lets governance
override confidence, expires temporary memory, and can never edit the Expert Brain. Every unit emits
a content-addressed, round-trip-verified ``LearningObject``: what it proposes, the integer evidence
behind it, whose ACL it inherits, and the exact policy it was judged under. Lifecycle state lives in
a *separate* row (never on the object) so a transition can never rewrite the evidence or the identity
the object was hashed on.

Hard rules encoded here: scores are integer basis points; neutral observations never inflate
confidence; there is no ``expert`` target in any enum; a user-scoped preference is capped to
``private + [one resolved subject]``; identity uses the source-observation time so a retry clock
cannot mint a new proposal id.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from types import MappingProxyType
from typing import Any

from genios_engine.contracts.validators import (
    freeze_mapping,
    require_aware,
    require_bool,
    require_enum,
    require_identifier,
)
from genios_engine.platform.canonical import canonical_dumps

LEARNING_VERSION = "learning.v2"


class BrainTarget(str, Enum):
    """The four real brains Layer 6 may publish learned state to. No ``expert`` — ever."""

    ORGANIZATION = "organization"
    BEHAVIOR = "behavior"
    ADAPTIVE = "adaptive"
    RUNTIME = "runtime"


class LearningTarget(str, Enum):
    """Every publish destination: the four brains plus two artifact sinks. Still no ``expert``.

    Metrics and knowledge suggestions are artifacts, not brains — a metric is a measurement and a
    knowledge suggestion stops at human review; neither is a place a decision is read from.
    """

    ORGANIZATION = "organization"
    BEHAVIOR = "behavior"
    ADAPTIVE = "adaptive"
    RUNTIME = "runtime"
    METRICS = "metrics"
    KNOWLEDGE_SUGGESTION = "knowledge_suggestion"


class VisibilityScope(str, Enum):
    """Narrowest first. A proposal inherits the narrowest source visibility it was derived from."""

    PRIVATE = "private"
    PARTICIPANTS = "participants"
    ORGANIZATION = "organization"
    PUBLIC = "public"


class LearningState(str, Enum):
    """The promotion lifecycle (Part 7). State lives in a row that points at the immutable object."""

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
    ARCHIVED = "archived"


#: Observed → Candidate → Validated → Governed → {Temporary→Expired | HumanReview→Promoted→Published
#: | Promoted→Published | Rejected}; Published → {Superseded | RolledBack}. Candidate is a monotonic
#: floor: it never falls back to Observed. Terminals go only to Archived.
ALLOWED_LEARNING_TRANSITIONS: MappingProxyType = MappingProxyType({
    LearningState.OBSERVED:    (LearningState.CANDIDATE, LearningState.REJECTED),
    LearningState.CANDIDATE:   (LearningState.VALIDATED, LearningState.REJECTED),
    LearningState.VALIDATED:   (LearningState.GOVERNED, LearningState.REJECTED),
    LearningState.GOVERNED:    (LearningState.TEMPORARY, LearningState.HUMAN_REVIEW,
                                LearningState.PROMOTED, LearningState.REJECTED),
    LearningState.TEMPORARY:   (LearningState.EXPIRED, LearningState.ARCHIVED),
    LearningState.HUMAN_REVIEW: (LearningState.PROMOTED, LearningState.REJECTED),
    LearningState.PROMOTED:    (LearningState.PUBLISHED,),
    LearningState.PUBLISHED:   (LearningState.SUPERSEDED, LearningState.ROLLED_BACK,
                                LearningState.ARCHIVED),
    LearningState.REJECTED:    (LearningState.ARCHIVED,),
    LearningState.EXPIRED:     (LearningState.ARCHIVED,),
    LearningState.SUPERSEDED:  (LearningState.PUBLISHED, LearningState.ARCHIVED),  # rollback restore
    LearningState.ROLLED_BACK: (LearningState.ARCHIVED,),
    LearningState.ARCHIVED:    (),
})

TERMINAL_LEARNING_STATES: frozenset[LearningState] = frozenset({
    LearningState.REJECTED, LearningState.EXPIRED, LearningState.ROLLED_BACK,
    LearningState.ARCHIVED})


def learning_can_transition(current: LearningState, target: LearningState) -> bool:
    return target in ALLOWED_LEARNING_TRANSITIONS.get(current, ())


@dataclass(frozen=True, slots=True)
class Visibility:
    """The ACL envelope a proposal inherits. Missing lineage fails closed to private+incomplete."""

    scope: VisibilityScope
    principals: tuple[str, ...] = ()
    derived_from: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        s = object.__setattr__
        s(self, "scope", require_enum(self.scope, VisibilityScope, "visibility scope"))
        s(self, "principals", tuple(self.principals))
        s(self, "derived_from", tuple(self.derived_from))

    def to_semantic_dict(self) -> dict[str, Any]:
        return {"scope": self.scope.value, "principals": list(self.principals),
                "derived_from": list(self.derived_from)}


def _bp(value: Any, label: str) -> int:
    """An integer basis-points score in [0, 10000]. No floats — a score is arithmetic, not a guess."""
    if not isinstance(value, int) or isinstance(value, bool) or not (0 <= value <= 10000):
        raise ValueError(f"{label} must be an integer basis-points value in [0, 10000]")
    return value


@dataclass(frozen=True, slots=True)
class LearningEvidence:
    """The integer evidence a proposal stands on. Neutral observations never raise confidence."""

    observations: int
    independent_refs: int
    distinct_days: int
    positive: int
    negative: int
    confidence_bp: int
    noise_bp: int = 0
    conflict_bp: int = 0
    freshness_bp: int = 10000
    business_value_bp: int = 0
    distinct_entities: int = 0               # k-anonymity: 0 = not measured for this unit
    source_refs: tuple[str, ...] = ()
    source_trace_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        s = object.__setattr__
        for name in ("observations", "independent_refs", "distinct_days", "positive", "negative",
                     "distinct_entities"):
            v = getattr(self, name)
            if not isinstance(v, int) or isinstance(v, bool) or v < 0:
                raise ValueError(f"{name} must be a non-negative integer")
        for name in ("confidence_bp", "noise_bp", "conflict_bp", "freshness_bp", "business_value_bp"):
            s(self, name, _bp(getattr(self, name), name))
        s(self, "source_refs", tuple(self.source_refs))
        s(self, "source_trace_ids", tuple(self.source_trace_ids))

    def to_semantic_dict(self) -> dict[str, Any]:
        return {"observations": self.observations, "independent_refs": self.independent_refs,
                "distinct_days": self.distinct_days, "positive": self.positive,
                "negative": self.negative, "confidence_bp": self.confidence_bp,
                "noise_bp": self.noise_bp, "conflict_bp": self.conflict_bp,
                "freshness_bp": self.freshness_bp, "business_value_bp": self.business_value_bp,
                "distinct_entities": self.distinct_entities,
                "source_refs": list(self.source_refs),
                "source_trace_ids": list(self.source_trace_ids)}


@dataclass(frozen=True, slots=True)
class LearningObject:
    """One immutable, content-addressed learning proposal (Part 4). Lifecycle lives elsewhere."""

    org_id: str
    unit: str                                # the analysis unit that emitted it
    target: LearningTarget
    subject: str                             # what the learning is about (rule/play/person/…)
    proposed_value: dict[str, Any]           # canonical deep-frozen finite JSON
    evidence: LearningEvidence
    visibility: Visibility
    first_seen_at: datetime
    last_seen_at: datetime
    policy_key: str
    lineage_complete: bool = True
    subject_principal: str | None = None     # the single ACL-resolved subject for a user preference
    expires_at: datetime | None = None       # Runtime target only
    schema_version: str = LEARNING_VERSION

    def __post_init__(self) -> None:
        s = object.__setattr__
        s(self, "org_id", require_identifier(self.org_id, "org id"))
        s(self, "unit", require_identifier(self.unit, "unit"))
        s(self, "target", require_enum(self.target, LearningTarget, "target"))
        s(self, "subject", require_identifier(self.subject, "subject"))
        if not isinstance(self.proposed_value, dict):
            raise TypeError("proposed_value must be a JSON object")
        s(self, "proposed_value", freeze_mapping(self.proposed_value))
        if not isinstance(self.evidence, LearningEvidence):
            raise TypeError("evidence must be a LearningEvidence")
        if not isinstance(self.visibility, Visibility):
            raise TypeError("visibility must be a Visibility")
        s(self, "first_seen_at", require_aware(self.first_seen_at, "first_seen_at"))
        s(self, "last_seen_at", require_aware(self.last_seen_at, "last_seen_at"))
        s(self, "policy_key", require_identifier(self.policy_key, "policy key"))
        s(self, "lineage_complete", require_bool(self.lineage_complete, "lineage_complete"))
        if self.subject_principal is not None:
            s(self, "subject_principal",
              require_identifier(self.subject_principal, "subject principal"))
        # Only a Runtime lease may carry an expiry; everything else is durable-or-nothing.
        if self.expires_at is not None:
            s(self, "expires_at", require_aware(self.expires_at, "expires_at"))
            if self.target is not LearningTarget.RUNTIME:
                raise ValueError("only a Runtime target may carry an expiry")
        s(self, "schema_version", require_identifier(self.schema_version, "schema version"))

        # A user-scoped preference is capped to private + exactly one resolved subject.
        if self.subject_principal is not None:
            if self.visibility.scope is not VisibilityScope.PRIVATE:
                raise ValueError("a subject-scoped preference must be private")
            if tuple(self.visibility.principals) != (self.subject_principal,):
                raise ValueError("a subject-scoped preference is capped to its one subject principal")

    @property
    def identity(self) -> Mapping[str, Any]:
        """The content-addressed identity: org, unit, target, subject, value, evidence, visibility.

        Uses the source-observation time implicitly through the frozen value/evidence — never the
        wall clock — so a retry or a later evaluation cannot manufacture a new proposal id.
        """
        return MappingProxyType({
            "schema_version": self.schema_version, "org_id": self.org_id, "unit": self.unit,
            "target": self.target.value, "subject": self.subject,
            "proposed_value": dict(self.proposed_value),
            "evidence": self.evidence.to_semantic_dict(),
            "visibility": self.visibility.to_semantic_dict(),
            "subject_principal": self.subject_principal})

    def semantic_hash(self) -> str:
        return hashlib.sha256(canonical_dumps(dict(self.identity)).encode()).hexdigest()

    @property
    def learning_id(self) -> str:
        """Stable id derived from the content hash — same evidence next week ⇒ same object."""
        return f"lo_{self.semantic_hash()[:24]}"

    def to_semantic_dict(self) -> dict[str, Any]:
        return {**dict(self.identity), "policy_key": self.policy_key,
                "lineage_complete": self.lineage_complete,
                "first_seen_at": self.first_seen_at, "last_seen_at": self.last_seen_at,
                "expires_at": self.expires_at}


@dataclass(frozen=True, slots=True)
class LearningPolicy:
    """Versioned governance authority. Defaults are protective; a tenant can only narrow them."""

    org_id: str
    revision: int
    min_observations: int = 3
    min_distinct_days: int = 2
    min_distinct_entities: int = 3           # k-anonymity floor for cross-entity patterns
    min_confidence_bp: int = 6000
    max_noise_bp: int = 4000
    max_conflict_bp: int = 3000
    min_business_value_bp: int = 0
    max_runtime_ttl_seconds: int = 7 * 24 * 3600
    organization_requires_review: bool = True
    knowledge_requires_review: bool = True          # mandatory; cannot be removed
    learning_enabled: bool = True
    blocked_targets: tuple[str, ...] = ()
    blocked_subject_prefixes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        s = object.__setattr__
        s(self, "org_id", require_identifier(self.org_id, "org id"))
        if not isinstance(self.revision, int) or self.revision < 1:
            raise ValueError("policy revision must be a positive integer")
        for name in ("min_confidence_bp", "max_noise_bp", "max_conflict_bp", "min_business_value_bp"):
            _bp(getattr(self, name), name)
        # Knowledge review can never be switched off — a hard invariant, not a default.
        if not self.knowledge_requires_review:
            raise ValueError("knowledge_requires_review cannot be disabled")
        s(self, "blocked_targets", tuple(self.blocked_targets))
        s(self, "blocked_subject_prefixes", tuple(self.blocked_subject_prefixes))

    @property
    def policy_key(self) -> str:
        return f"policy:{self.org_id}:{self.revision}"


# Late import to avoid a cycle at module top; Mapping is only used in annotations/returns.
from collections.abc import Mapping  # noqa: E402

__all__ = ["ALLOWED_LEARNING_TRANSITIONS", "LEARNING_VERSION", "TERMINAL_LEARNING_STATES",
           "BrainTarget", "LearningEvidence", "LearningObject", "LearningPolicy", "LearningState",
           "LearningTarget", "Visibility", "VisibilityScope", "learning_can_transition"]
