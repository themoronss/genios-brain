"""Immutable cross-layer contracts for the deterministic Layer 4 reasoning kernel."""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from types import MappingProxyType
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from genios_engine.contracts.domain_expertise import (
    MAX_CITATIONS,
    require_citation,
    require_constraint_application,
)
# Wave Z0's new types import the SHARED vocabulary rather than the private copies above.
# `contracts/validators.py` says in its own docstring why this file's `_text`/`_bp`/`_identifier`
# are deliberately left where they are — their bytes are covered by decision hashes that already
# exist in audit rows — and that "every contract written after it imports from here". Everything
# added in this wave was written after it.
from genios_engine.contracts.validators import (
    require_bool,
    require_bp,
    require_identifier,
    require_non_negative,
    require_ordinal,
    require_text,
)
from genios_engine.platform.canonical import canonicalize, semantic_hash, stable_id

_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:@/-]{0,191}$")
_HASH = re.compile(r"^[0-9a-f]{64}$")
SUPPORTED_CAPABILITY_POLICIES = frozenset({
    "read_only",
    "human_approval_required",
    "evidence_required",
    "no_unverified_recipient",
})


def _text(value: Any, label: str) -> str:
    result = str(value or "").strip()
    if not result:
        raise ValueError(f"{label} is required")
    return result


def _identifier(value: Any, label: str) -> str:
    result = _text(value, label)
    if not _IDENTIFIER.fullmatch(result):
        raise ValueError(f"{label} contains unsupported characters")
    return result


def _aware(value: datetime, label: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{label} must be a timezone-aware datetime")
    return value.astimezone(timezone.utc)


def _bp(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{label} must be integer basis points")
    if not 0 <= value <= 10_000:
        raise ValueError(f"{label} must be between 0 and 10000")
    return value


def _signed_bp(value: Any, label: str) -> int:
    """A SIGNED basis-point magnitude, -10000..10000.

    Extracted from `CandidateAdjustment.delta_bp`, which has always used exactly this range, so
    `Finding.value_bp` and an adjustment cannot drift apart on what a signed magnitude is. Separate
    from `_bp` rather than a widening of it, for the reason `analytic.require_signed_bp` gives one
    layer down: every other basis-point field in this file is a magnitude where a negative value is
    meaningless, and relaxing the shared helper to admit one would silently legalise a negative
    confidence everywhere it is used.

    `ValueError` for a non-integer as well as for an out-of-range value, and not the `TypeError`
    `_bp` raises: this helper was lifted out of `CandidateAdjustment.delta_bp`, which has raised
    `ValueError` for both since it was written, and a refactor that changed the exception type of an
    existing field is a behaviour change wearing a cleanup's clothes.
    """
    if isinstance(value, bool) or not isinstance(value, int) \
            or not -10_000 <= value <= 10_000:
        raise ValueError(f"{label} must be between -10000 and 10000")
    return value


def _hash64(value: Any, label: str) -> str:
    result = _text(value, label)
    if not _HASH.fullmatch(result):
        raise ValueError(f"{label} must be a lowercase SHA-256 hash")
    return result


def _freeze(value: Any) -> Any:
    """Deep-freeze semantic configuration while retaining useful primitive types."""
    canonicalize(value)  # validate first; rejects floats and unsupported hidden state
    if isinstance(value, Mapping):
        return MappingProxyType({str(key): _freeze(item) for key, item in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(item) for item in value)
    if isinstance(value, (set, frozenset)):
        return tuple(sorted((_freeze(item) for item in value), key=lambda item: semantic_hash(item)))
    return value


def _mapping(value: Mapping[str, Any] | None) -> Mapping[str, Any]:
    return _freeze(value or {})


def _strings(values) -> tuple[str, ...]:
    result = tuple(_text(value, "list value") for value in (values or ()))
    return result


# ═════════════════════════════════════════════════════════════════════════════════════════════
# G-06 · the ranking weights — five keys summing to 100, or SIX summing to 10000
# ═════════════════════════════════════════════════════════════════════════════════════════════

#: The six utility components doc 04 names, in weight order. `importance` is FIRST and carries the
#: largest weight, and that is the whole point of this wave: L1 spent ALG-17 computing it and L2
#: spent H5 composing it, and `importance_bp` has had exactly zero readers in `reason/` — it appears
#: once, in a SQL select at `reason/domain_shadow.py:78`, and nowhere else.
UTILITY_COMPONENTS = ("importance", "impact", "urgency", "success", "effort", "risk")

#: The two components a candidate is rewarded for the ABSENCE of. Named rather than hardcoded in the
#: scorer so a seventh component cannot be added as a cost by accident — a component whose sign is
#: implicit in one function is a ranking that inverts silently when somebody reorders it.
COST_COMPONENTS = ("effort", "risk")

#: Where the formula's own answer is recorded when an override replaced it. Already written by
#: `reason/decision_maker.score_candidate`; named here because K1 is measured on the divergence
#: between this and the final utility, and a gate that reads a string literal is a gate that breaks
#: when somebody renames the key.
FORMULA_UTILITY_COMPONENT = "formula_utility"

#: The shape every capability in the tree carries today: five keys, percentage points, summing to
#: 100. Kept — old shapes still construct, which is Z0's whole acceptance condition.
RANKING_WEIGHTS_V1 = MappingProxyType({
    "impact": 35, "success": 30, "urgency": 20, "effort": 10, "risk": 5})
RANKING_WEIGHTS_V1_VERSION = "ranking_weights@1"
RANKING_WEIGHTS_V1_SCALE = 100

#: G-06's shape: six keys, integer BASIS POINTS, summing to 10000. The numbers are doc 04's table
#: and are not negotiable here — importance 2500 is the largest weight in the engine.
RANKING_WEIGHTS_V2 = MappingProxyType({
    "importance": 2_500, "impact": 2_000, "urgency": 2_000,
    "success": 1_500, "effort": 1_000, "risk": 1_000})
RANKING_WEIGHTS_V2_VERSION = "ranking_weights@2"
RANKING_WEIGHTS_V2_SCALE = 10_000

RANKING_WEIGHTS_VERSIONS = (RANKING_WEIGHTS_V1_VERSION, RANKING_WEIGHTS_V2_VERSION)

_RANKING_WEIGHT_SHAPES = (
    (frozenset(RANKING_WEIGHTS_V1), RANKING_WEIGHTS_V1_SCALE, RANKING_WEIGHTS_V1_VERSION),
    (frozenset(RANKING_WEIGHTS_V2), RANKING_WEIGHTS_V2_SCALE, RANKING_WEIGHTS_V2_VERSION),
)


def require_ranking_weights(value: Any, label: str = "ranking_weights"
                            ) -> tuple[Mapping[str, int], str]:
    """The weights, frozen, and the VERSION STRING that says which scale they are on.

    Two shapes are legal and they are told apart by their KEY SET, never by their sum: the legacy
    five (percentage points, 100) and G-06's six (basis points, 10000). Deriving the version from the
    keys rather than from a stored string is what makes an old manifest keep hashing to exactly what
    it hashed to before this wave — no field was added to carry the version, because a field would
    have widened `capability_snapshot_id` for every capability in the tree.

    THE SUM IS CHECKED AGAINST THE SHAPE'S OWN SCALE, and the scale then travels out with the
    weights, because `_weighted_utility` divides by it. Six weights summing to 10000 fed to a scorer
    that divides by 100 produces a utility a hundred times too large, clamped to 10000, and every
    candidate ties at the ceiling — which is the same "everything scores 50" failure this wave
    exists to end, arriving from the other direction.
    """
    if not isinstance(value, Mapping):
        raise TypeError(f"{label} must be a mapping")
    weights = {str(key): item for key, item in value.items()}
    keys = frozenset(weights)
    shape = next((entry for entry in _RANKING_WEIGHT_SHAPES if entry[0] == keys), None)
    if shape is None:
        raise ValueError(
            "ranking_weights require five non-negative integer weights "
            f"{tuple(RANKING_WEIGHTS_V1)} or six {tuple(RANKING_WEIGHTS_V2)}, got "
            f"{tuple(sorted(keys))}")
    _, scale, version = shape
    for key, item in weights.items():
        if isinstance(item, bool) or not isinstance(item, int) or item < 0:
            raise ValueError("ranking_weights require five non-negative integer weights")
    if sum(weights.values()) != scale:
        raise ValueError(f"ranking_weights must sum to {scale}")
    return _mapping(weights), version


def ranking_weight_scale(weights: Mapping[str, int]) -> int:
    """The divisor a weighted sum over these weights must use: 100 for v1, 10000 for v2.

    The seam Z3 imports. Reading it from the weights rather than from a constant at the call site is
    what stops a v2 manifest reaching a v1 scorer — see `require_ranking_weights`.
    """
    return RANKING_WEIGHTS_V2_SCALE if "importance" in weights else RANKING_WEIGHTS_V1_SCALE


# ═════════════════════════════════════════════════════════════════════════════════════════════
# G-02 · the two typed mappings the DecisionObject grows
# ═════════════════════════════════════════════════════════════════════════════════════════════

#: E4's closed vocabulary. `computed` means `core.cost`/`core.alternative` actually produced the
#: number; `manifest_fallback` means the manifest's static sentence was used. ALWAYS recorded, so a
#: card never implies a computation that did not happen.
DO_NOTHING_SOURCES = ("computed", "manifest_fallback")

#: The four keys E4 prints. Fixed rather than open because `source` is the honesty of the other
#: three: a mapping that could omit it would let a fallback render as a computation.
DO_NOTHING_KEYS = ("cost_bp", "horizon", "statement", "source")


def require_do_nothing(value: Any, label: str = "do_nothing") -> Mapping[str, Any]:
    """E4's computed cost of doing nothing: `{cost_bp, horizon, statement, source}`.

    `horizon` may be None and `cost_bp` may be 0 — a situation with no material date and no priced
    exposure is a real answer. `source` may not be absent, and that is the point of the type: today
    `decision_maker.py:426` copies `do_nothing_consequence` verbatim from the manifest, so every card
    says the same sentence, and nothing on the record distinguishes that from a computation. With
    `source` mandatory, the fallback is labelled everywhere it appears.
    """
    if not isinstance(value, Mapping):
        raise TypeError(f"{label} must be a mapping")
    missing = [key for key in DO_NOTHING_KEYS if key not in value]
    if missing or len(value) != len(DO_NOTHING_KEYS):
        raise ValueError(
            f"{label} carries exactly {DO_NOTHING_KEYS}, got {tuple(sorted(value))}")
    require_bp(value["cost_bp"], f"{label} cost_bp")
    if value["horizon"] is not None:
        _aware(value["horizon"], f"{label} horizon")
    require_text(value["statement"], f"{label} statement")
    if value["source"] not in DO_NOTHING_SOURCES:
        raise ValueError(f"{label} source must be one of {DO_NOTHING_SOURCES}, "
                         f"got {value['source']!r}")
    return _mapping(dict(value))


#: E2's raw material, already published by `core.confidence` and today thrown away — the Rule 11
#: composition is the only thing that was missing. A CLOSED set: Rule 11 says confidence rises only
#: with NAMED independent evidence, and a vector that accepted any key would let a fifth name be
#: invented at a call site and composed into a raise nobody can trace. A sixth input is a change to
#: this tuple and to the composition that reads it, together.
CONFIDENCE_VECTOR_KEYS = ("independent_evidence_groups", "evidence_coverage_bp",
                          "corroboration_bp", "source_quality_bp")


def require_confidence_vector(value: Any, label: str = "confidence_vector"
                              ) -> Mapping[str, int]:
    """Rule 11's inputs, carried from the BSO. A subset of `CONFIDENCE_VECTOR_KEYS`, integers only.

    A SUBSET rather than all four, because a unit that could not compute one of them must be able to
    say so by omission — substituting a neutral number for an input that does not exist is exactly
    the bug that made every card score 50, and doc 04 forbids reintroducing it under a new name.
    """
    if not isinstance(value, Mapping):
        raise TypeError(f"{label} must be a mapping")
    unknown = sorted(set(map(str, value)) - set(CONFIDENCE_VECTOR_KEYS))
    if unknown:
        raise ValueError(f"{label} accepts only {CONFIDENCE_VECTOR_KEYS}, got extra {unknown} — "
                         "Rule 11 composes NAMED inputs, so a new one is a change to "
                         "CONFIDENCE_VECTOR_KEYS and to the composition that reads it, together")
    out: dict[str, int] = {}
    for key, item in value.items():
        name = str(key)
        out[name] = (require_bp(item, f"{label} {name}") if name.endswith("_bp")
                     else require_non_negative(item, f"{label} {name}"))
    return _mapping(out)


class ExecutionMode(str, Enum):
    LIVE = "live"
    SHADOW = "shadow"
    SIMULATION = "simulation"
    REPLAY = "replay"


class FailurePolicy(str, Enum):
    REQUIRED = "required"
    OPTIONAL = "optional"


class ResultStatus(str, Enum):
    COMPLETED = "completed"
    SKIPPED = "skipped"
    FAILED = "failed"
    INSUFFICIENT_CONTEXT = "insufficient_context"


class DecisionOutcome(str, Enum):
    DECISION = "decision"
    NO_ACTION = "no_action"
    DEFER = "defer"
    INSUFFICIENT_CONTEXT = "insufficient_context"
    BLOCKED = "blocked"
    FAILED = "failed"


class CandidateDisposition(str, Enum):
    ELIGIBLE = "eligible"
    ELIMINATED = "eliminated"


class CheckOutcome(str, Enum):
    PASS = "pass"
    WARN = "warn"
    ELIMINATE = "eliminate"
    ADJUST = "adjust"


@dataclass(frozen=True, slots=True)
class Goal:
    goal_id: str
    statement: str
    success_criteria: tuple[str, ...] = ()
    constraints: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "goal_id", _identifier(self.goal_id, "goal_id"))
        object.__setattr__(self, "statement", _text(self.statement, "goal statement"))
        object.__setattr__(self, "success_criteria", _strings(self.success_criteria))
        object.__setattr__(self, "constraints", _strings(self.constraints))


@dataclass(frozen=True, slots=True)
class EvidenceRef:
    evidence_id: str
    field: str
    value: Any
    context_scope: str = "root"
    source_ref_id: str | None = None
    fact_version_id: str | None = None
    occurred_at: datetime | None = None
    confidence_bp: int = 5_000
    authority_rank: int = 1
    independence_group: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "evidence_id", _identifier(self.evidence_id, "evidence_id"))
        object.__setattr__(self, "field", _identifier(self.field, "evidence field"))
        object.__setattr__(self, "value", _freeze(self.value))
        scope = _identifier(self.context_scope, "evidence context_scope")
        if scope not in {"root", "neighbor"}:
            raise ValueError("evidence context_scope must be root or neighbor")
        object.__setattr__(self, "context_scope", scope)
        if self.occurred_at is not None:
            object.__setattr__(self, "occurred_at", _aware(self.occurred_at, "occurred_at"))
        object.__setattr__(self, "confidence_bp", _bp(self.confidence_bp, "confidence_bp"))
        if isinstance(self.authority_rank, bool) or not isinstance(self.authority_rank, int) \
                or not 1 <= self.authority_rank <= 4:
            raise ValueError("authority_rank must be between 1 and 4")


@dataclass(frozen=True, slots=True)
class ContextSnapshot:
    org_id: str
    graph_version: int
    root_entity_id: str
    root_entity_type: str
    evaluation_time: datetime
    selector_version: str
    facts: Mapping[str, Any] = field(default_factory=dict)
    observations: tuple[Mapping[str, Any], ...] = ()
    neighbor_facts: Mapping[str, Any] = field(default_factory=dict)
    neighbor_observations: tuple[str, ...] = ()
    edge_count: int = 0
    evidence: tuple[EvidenceRef, ...] = ()
    missing_fields: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "org_id", _identifier(self.org_id, "org_id"))
        object.__setattr__(self, "root_entity_id", _identifier(
            self.root_entity_id, "root_entity_id"))
        object.__setattr__(self, "root_entity_type", _identifier(
            self.root_entity_type, "root_entity_type"))
        object.__setattr__(self, "selector_version", _identifier(
            self.selector_version, "selector_version"))
        if isinstance(self.graph_version, bool) or not isinstance(self.graph_version, int) \
                or self.graph_version < 0:
            raise ValueError("graph_version must be a non-negative integer")
        if isinstance(self.edge_count, bool) or not isinstance(self.edge_count, int) \
                or self.edge_count < 0:
            raise ValueError("edge_count must be a non-negative integer")
        object.__setattr__(self, "evaluation_time", _aware(
            self.evaluation_time, "evaluation_time"))
        object.__setattr__(self, "facts", _mapping(self.facts))
        object.__setattr__(self, "observations", tuple(_mapping(item) for item in self.observations))
        object.__setattr__(self, "neighbor_facts", _mapping(self.neighbor_facts))
        object.__setattr__(self, "neighbor_observations", tuple(sorted(set(
            _strings(self.neighbor_observations)))))
        object.__setattr__(self, "evidence", tuple(sorted(self.evidence,
                                                          key=lambda item: item.evidence_id)))
        object.__setattr__(self, "missing_fields", tuple(sorted(set(
            _strings(self.missing_fields)))))
        object.__setattr__(self, "metadata", _mapping(self.metadata))
        evidence_ids = [item.evidence_id for item in self.evidence]
        if len(evidence_ids) != len(set(evidence_ids)):
            raise ValueError("duplicate evidence_id")
        for item in self.evidence:
            source = self.facts if item.context_scope == "root" else self.neighbor_facts
            if item.field not in source:
                raise ValueError(
                    f"evidence {item.evidence_id} field is absent from its context scope")
            record = source[item.field]
            if isinstance(record, Mapping) and "value" in record:
                actual = record["value"]
            elif isinstance(record, Mapping) and "value_bp" in record:
                actual = record["value_bp"]
            else:
                actual = record
            matches = semantic_hash(actual) == semantic_hash(item.value)
            if not matches and isinstance(actual, (tuple, list)):
                matches = any(semantic_hash(member) == semantic_hash(item.value)
                              for member in actual)
            if not matches:
                raise ValueError(
                    f"evidence {item.evidence_id} value does not match its context fact")

    def to_semantic_dict(self) -> dict[str, Any]:
        return {"org_id": self.org_id, "graph_version": self.graph_version,
                "root_entity_id": self.root_entity_id,
                "root_entity_type": self.root_entity_type,
                "evaluation_time": self.evaluation_time,
                "selector_version": self.selector_version, "facts": self.facts,
                "observations": self.observations, "neighbor_facts": self.neighbor_facts,
                "neighbor_observations": self.neighbor_observations,
                "edge_count": self.edge_count, "evidence": self.evidence,
                "missing_fields": self.missing_fields, "metadata": self.metadata}

    @property
    def semantic_hash(self) -> str:
        return semantic_hash(self.to_semantic_dict())

    @property
    def context_snapshot_id(self) -> str:
        return stable_id("ctx", self.to_semantic_dict())


@dataclass(frozen=True, slots=True)
class IntelligenceObject:
    object_id: str
    version: str
    capability_id: str
    purpose: str
    required_context: tuple[str, ...] = ()
    relationships: Mapping[str, Any] = field(default_factory=dict)
    knowledge: Mapping[str, Any] = field(default_factory=dict)
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "object_id", _identifier(self.object_id, "object_id"))
        object.__setattr__(self, "version", _identifier(self.version, "object version"))
        object.__setattr__(self, "capability_id", _identifier(
            self.capability_id, "capability_id"))
        object.__setattr__(self, "purpose", _text(self.purpose, "object purpose"))
        object.__setattr__(self, "required_context", tuple(sorted(set(
            _strings(self.required_context)))))
        object.__setattr__(self, "relationships", _mapping(self.relationships))
        object.__setattr__(self, "knowledge", _mapping(self.knowledge))
        object.__setattr__(self, "metadata", _mapping(self.metadata))


@dataclass(frozen=True, slots=True)
class ReasonerSpec:
    reasoner_id: str
    version: str
    input_kind: str = "context_snapshot"
    output_kind: str = "finding"
    dependencies: tuple[str, ...] = ()
    required_fields: tuple[str, ...] = ()
    latency_budget_ms: int = 100
    failure_policy: FailurePolicy = FailurePolicy.REQUIRED
    gating: bool = False
    config: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "reasoner_id", _identifier(
            self.reasoner_id, "reasoner_id"))
        object.__setattr__(self, "version", _identifier(self.version, "reasoner version"))
        object.__setattr__(self, "input_kind", _identifier(self.input_kind, "input_kind"))
        object.__setattr__(self, "output_kind", _identifier(self.output_kind, "output_kind"))
        object.__setattr__(self, "dependencies", tuple(sorted(set(
            _strings(self.dependencies)))))
        object.__setattr__(self, "required_fields", tuple(sorted(set(
            _strings(self.required_fields)))))
        if isinstance(self.latency_budget_ms, bool) or not isinstance(self.latency_budget_ms, int) \
                or not 1 <= self.latency_budget_ms <= 60_000:
            raise ValueError("latency_budget_ms must be between 1 and 60000")
        if not isinstance(self.failure_policy, FailurePolicy):
            object.__setattr__(self, "failure_policy", FailurePolicy(self.failure_policy))
        if not isinstance(self.gating, bool):
            raise TypeError("gating must be boolean")
        if self.gating and self.failure_policy != FailurePolicy.REQUIRED:
            raise ValueError("gating reasoners must use required fail-closed policy")
        object.__setattr__(self, "config", _mapping(self.config))


@dataclass(frozen=True, slots=True)
class PlayDefinition:
    play_id: str
    version: str
    label: str
    steps: tuple[str, ...]
    preconditions: tuple[Mapping[str, Any], ...] = ()
    read_only: bool = True
    impact_bp: int = 5_000
    success_probability_bp: int = 5_000
    effort_bp: int = 5_000
    risk_bp: int = 5_000
    tags: tuple[str, ...] = ()
    success_events: tuple[str, ...] = ()
    window_days: int = 7
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "play_id", _identifier(self.play_id, "play_id"))
        object.__setattr__(self, "version", _identifier(self.version, "play version"))
        object.__setattr__(self, "label", _text(self.label, "play label"))
        object.__setattr__(self, "steps", _strings(self.steps))
        if not self.steps:
            raise ValueError("a play requires at least one step")
        object.__setattr__(self, "preconditions", tuple(_mapping(item)
                                                         for item in self.preconditions))
        if not isinstance(self.read_only, bool):
            raise TypeError("read_only must be boolean")
        for name in ("impact_bp", "success_probability_bp", "effort_bp", "risk_bp"):
            object.__setattr__(self, name, _bp(getattr(self, name), name))
        object.__setattr__(self, "tags", tuple(sorted(set(_strings(self.tags)))))
        object.__setattr__(self, "success_events", tuple(sorted(set(
            _strings(self.success_events)))))
        if isinstance(self.window_days, bool) or not isinstance(self.window_days, int) \
                or not 1 <= self.window_days <= 365:
            raise ValueError("window_days must be between 1 and 365")
        object.__setattr__(self, "metadata", _mapping(self.metadata))


@dataclass(frozen=True, slots=True)
class CapabilityManifest:
    capability_id: str
    version: str
    domain: str
    root_entity_type: str
    goal: Goal
    reasoners: tuple[ReasonerSpec, ...]
    plays: tuple[PlayDefinition, ...]
    required_fields: tuple[str, ...] = ()
    #: Fields to PULL into the snapshot, when that is wider than what gates the decision.
    #: `required_fields` answers "without this, nothing can run"; this answers "fetch it if it is
    #: there". Merging them let one value-dependent inference pattern veto an entire capability,
    #: and narrowing the merged value to fix that emptied the selector too — leaving a snapshot
    #: with no facts, hence no evidence, hence an `evidence_required` policy that eliminated every
    #: candidate. They are two questions and now have two answers.
    selection_fields: tuple[str, ...] = ()
    intelligence_objects: tuple[IntelligenceObject, ...] = ()
    ranking_weights: Mapping[str, int] = field(default_factory=lambda: {
        "impact": 35, "success": 30, "urgency": 20, "effort": 10, "risk": 5})
    policies: tuple[str, ...] = ("read_only",)
    live_delivery_enabled: bool = True
    do_nothing_consequence: str = "The condition may remain unresolved."
    expiry_hours: int = 168
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "capability_id", _identifier(
            self.capability_id, "capability_id"))
        object.__setattr__(self, "version", _identifier(self.version, "capability version"))
        object.__setattr__(self, "domain", _identifier(self.domain, "domain"))
        object.__setattr__(self, "root_entity_type", _identifier(
            self.root_entity_type, "root_entity_type"))
        object.__setattr__(self, "reasoners", tuple(self.reasoners))
        object.__setattr__(self, "plays", tuple(self.plays))
        object.__setattr__(self, "intelligence_objects", tuple(self.intelligence_objects))
        if not self.reasoners:
            raise ValueError("capability requires at least one reasoner")
        if not self.plays:
            raise ValueError("capability requires at least one play")
        for obj in self.intelligence_objects:
            if obj.capability_id != self.capability_id:
                raise ValueError("intelligence object belongs to another capability")
        reasoner_ids = [item.reasoner_id for item in self.reasoners]
        play_ids = [item.play_id for item in self.plays]
        object_ids = [item.object_id for item in self.intelligence_objects]
        if len(reasoner_ids) != len(set(reasoner_ids)):
            raise ValueError("duplicate reasoner in capability")
        if len(play_ids) != len(set(play_ids)):
            raise ValueError("duplicate play in capability")
        if len(object_ids) != len(set(object_ids)):
            raise ValueError("duplicate intelligence object")
        object.__setattr__(self, "required_fields", tuple(sorted(set(
            _strings(self.required_fields)))))
        object.__setattr__(self, "selection_fields", tuple(sorted(set(
            _strings(self.selection_fields)))))
        weights, _weights_version = require_ranking_weights(self.ranking_weights)
        object.__setattr__(self, "ranking_weights", weights)
        policies = tuple(sorted(set(_strings(self.policies))))
        unknown_policies = sorted(set(policies) - SUPPORTED_CAPABILITY_POLICIES)
        if unknown_policies:
            raise ValueError(
                "unsupported capability policies: " + ", ".join(unknown_policies))
        requires_constraint = bool(policies) or any(play.preconditions for play in self.plays)
        constraint_spec = next((item for item in self.reasoners
                                if item.reasoner_id == "core.constraint"), None)
        if (requires_constraint and (constraint_spec is None
                                     or constraint_spec.failure_policy != FailurePolicy.REQUIRED)):
            raise ValueError(
                "capability policies and play preconditions require a required core.constraint")
        if "no_unverified_recipient" in policies:
            for play in self.plays:
                if ("external_recipient_required" not in play.metadata
                        or not isinstance(play.metadata["external_recipient_required"], bool)):
                    raise ValueError(
                        "no_unverified_recipient requires every play to declare the boolean "
                        f"external_recipient_required effect: {play.play_id}")
        object.__setattr__(self, "policies", policies)
        if not isinstance(self.live_delivery_enabled, bool):
            raise TypeError("live_delivery_enabled must be boolean")
        object.__setattr__(self, "do_nothing_consequence", _text(
            self.do_nothing_consequence, "do_nothing_consequence"))
        if isinstance(self.expiry_hours, bool) or not isinstance(self.expiry_hours, int) \
                or not 1 <= self.expiry_hours <= 8_760:
            raise ValueError("expiry_hours must be between 1 and 8760")
        object.__setattr__(self, "metadata", _mapping(self.metadata))

    def to_semantic_dict(self) -> dict[str, Any]:
        return {"capability_id": self.capability_id, "version": self.version,
                "domain": self.domain, "root_entity_type": self.root_entity_type,
                "goal": self.goal, "reasoners": self.reasoners, "plays": self.plays,
                "required_fields": self.required_fields,
                # Must be here as well as on the dataclass: the audit store hashes the
                # RAW fields while `capability_snapshot_id` hashes this dict, and a
                # field present in one and absent from the other makes every manifest
                # fail "capability_snapshot_id does not match manifest content".
                "selection_fields": self.selection_fields,
                "intelligence_objects": self.intelligence_objects,
                "ranking_weights": self.ranking_weights, "policies": self.policies,
                "live_delivery_enabled": self.live_delivery_enabled,
                "do_nothing_consequence": self.do_nothing_consequence,
                "expiry_hours": self.expiry_hours, "metadata": self.metadata}

    @property
    def semantic_hash(self) -> str:
        return semantic_hash(self.to_semantic_dict())

    @property
    def capability_snapshot_id(self) -> str:
        return stable_id("cap", self.to_semantic_dict())

    # ── G-06 · the version and the scale, DERIVED ────────────────────────────────────────────
    #
    # Properties, not fields, and that is the whole reason old capabilities still address to the
    # same bytes: a stored `ranking_weights_version` column would have entered
    # `to_semantic_dict`, changed `capability_snapshot_id` for every capability in the tree, and
    # invalidated the `reasoning_capability_snapshots` rows replay is verified against — in
    # exchange for a string the key set already determines.

    @property
    def ranking_weights_version(self) -> str:
        """`ranking_weights@1` for the legacy five, `ranking_weights@2` for G-06's six."""
        return require_ranking_weights(self.ranking_weights)[1]

    @property
    def ranking_weight_scale(self) -> int:
        """The divisor a weighted sum over these weights must use. See `ranking_weight_scale`."""
        return ranking_weight_scale(self.ranking_weights)


@dataclass(frozen=True, slots=True)
class ReasoningRequest:
    org_id: str
    capability: CapabilityManifest
    context: ContextSnapshot
    evaluation_time: datetime
    trigger_kind: str
    trigger_ref: str | None = None
    mode: ExecutionMode = ExecutionMode.LIVE
    config_snapshot_id: str | None = None
    policy_snapshot_id: str | None = None
    request_id: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "org_id", _identifier(self.org_id, "org_id"))
        object.__setattr__(self, "trigger_kind", _identifier(self.trigger_kind, "trigger_kind"))
        object.__setattr__(self, "evaluation_time", _aware(
            self.evaluation_time, "evaluation_time"))
        if self.org_id != self.context.org_id:
            raise ValueError("request and context org_id differ")
        if self.evaluation_time != self.context.evaluation_time:
            raise ValueError("request and context evaluation_time differ")
        if self.capability.root_entity_type != self.context.root_entity_type:
            raise ValueError("capability root type does not match context")
        if not isinstance(self.mode, ExecutionMode):
            object.__setattr__(self, "mode", ExecutionMode(self.mode))
        for name in ("trigger_ref", "config_snapshot_id"):
            if getattr(self, name) is not None:
                object.__setattr__(self, name, _identifier(getattr(self, name), name))
        # Policies are capability-local in v1. Their exact bytes already live inside the immutable
        # manifest, so derive a content address instead of accepting an opaque, unverifiable ID.
        expected_policy_id = stable_id("policy", {
            "capability_id": self.capability.capability_id,
            "capability_version": self.capability.version,
            "policies": self.capability.policies,
        })
        if self.policy_snapshot_id is None:
            object.__setattr__(self, "policy_snapshot_id", expected_policy_id)
        else:
            supplied_policy_id = _identifier(self.policy_snapshot_id, "policy_snapshot_id")
            if supplied_policy_id != expected_policy_id:
                raise ValueError("policy_snapshot_id does not match capability policy bytes")
            object.__setattr__(self, "policy_snapshot_id", supplied_policy_id)
        expected_request_id = stable_id("req", self.to_semantic_dict())
        if self.request_id is None:
            object.__setattr__(self, "request_id", expected_request_id)
        else:
            supplied_request_id = _identifier(self.request_id, "request_id")
            if supplied_request_id != expected_request_id:
                raise ValueError("request_id does not match request content")
            object.__setattr__(self, "request_id", supplied_request_id)

    def to_semantic_dict(self) -> dict[str, Any]:
        return {"org_id": self.org_id,
                "capability_snapshot_id": self.capability.capability_snapshot_id,
                "context_snapshot_id": self.context.context_snapshot_id,
                "evaluation_time": self.evaluation_time, "trigger_kind": self.trigger_kind,
                "trigger_ref": self.trigger_ref, "mode": self.mode,
                "config_snapshot_id": self.config_snapshot_id,
                "policy_snapshot_id": self.policy_snapshot_id}

    @property
    def semantic_hash(self) -> str:
        return semantic_hash(self.to_semantic_dict())


@dataclass(frozen=True, slots=True)
class Finding:
    """S1 · one unit's emission about one fact. Globe's evidence schema is `unit_ref, claim, value`.

    `kind` is the claim and `metrics` has always been able to carry numbers, but there was no field
    that said *how big the thing is* — so a unit that found a 25-point engagement drop and one that
    found a 2-point drop emitted the same shape, and a reader had to know which key of `metrics` was
    the magnitude for that particular unit. `value_bp` is that field, and it is the same field for
    every unit.

    **`unit_ref` DERIVES; it is not stored.** Globe's third column is the unit that emitted the
    finding, and that is already unambiguous: a `Finding` only ever reaches anything inside the
    `ReasonerResult` its unit returned, and that result carries `reasoner_id`. Storing it again would
    create a second copy that can disagree with the first, and a disagreement between an evidence
    row and the unit that wrote it is unresolvable after the fact. `unit_ref()` below is the one
    resolution, and it CHECKS membership rather than trusting the caller to pass a matching pair.
    """

    finding_id: str
    kind: str
    matched: bool | None = None
    metrics: Mapping[str, Any] = field(default_factory=dict)
    evidence_ids: tuple[str, ...] = ()
    reason_codes: tuple[str, ...] = ()
    #: G-03 · the magnitude of what this finding found, in SIGNED basis points. Optional, because
    #: plenty of findings are pure predicates ("the constraint holds") with no magnitude at all, and
    #: a magnitude defaulted to 0 would read as "found nothing" rather than "measured nothing".
    #: Appended LAST so every positional construction in the tree keeps meaning what it meant.
    value_bp: int | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "finding_id", _identifier(self.finding_id, "finding_id"))
        object.__setattr__(self, "kind", _identifier(self.kind, "finding kind"))
        if self.matched is not None and not isinstance(self.matched, bool):
            raise TypeError("finding matched must be boolean or None")
        object.__setattr__(self, "metrics", _mapping(self.metrics))
        for name, value in self.metrics.items():
            if name.endswith("_bp"):
                _bp(value, f"finding metrics.{name}")
        object.__setattr__(self, "evidence_ids", tuple(sorted(set(
            _strings(self.evidence_ids)))))
        object.__setattr__(self, "reason_codes", tuple(sorted(set(
            _strings(self.reason_codes)))))
        if self.value_bp is not None:
            object.__setattr__(self, "value_bp", _signed_bp(self.value_bp, "finding value_bp"))

    def to_semantic_dict(self) -> dict[str, Any]:
        """The six original keys, plus `value_bp` ONLY when it was measured.

        This method exists solely so that adding a field did not change a single stored hash. Without
        it `canonicalize` walks the dataclass fields, `"value_bp": null` enters the canonical JSON of
        every finding ever emitted, and that propagates through `ReasonerResult.semantic_hash` into
        `StepTrace.output_hash` — so every trace in `reasoning_runs` would fail replay verification
        against a run that computed the identical result. The same conditional-inclusion rule the
        decision's `citations` already uses, for the same reason.
        """
        body: dict[str, Any] = {
            "finding_id": self.finding_id, "kind": self.kind, "matched": self.matched,
            "metrics": self.metrics, "evidence_ids": self.evidence_ids,
            "reason_codes": self.reason_codes}
        if self.value_bp is not None:
            body["value_bp"] = self.value_bp
        return body

    @property
    def semantic_hash(self) -> str:
        return semantic_hash(self.to_semantic_dict())


def unit_ref(result: ReasonerResult, finding: Finding) -> str:
    """DLG-11 · which unit emitted this finding. The one resolution of Globe's `unit_ref`.

    Membership is CHECKED, not assumed. The whole argument for deriving rather than storing is that
    a derived value cannot disagree with its source — and a function that returned
    `result.reasoner_id` for any pair handed to it would reintroduce exactly the disagreement it
    exists to prevent, one call site at a time.
    """
    if not any(item.finding_id == finding.finding_id for item in result.findings):
        raise ValueError(
            f"finding {finding.finding_id} was not emitted by {result.reasoner_id} — a unit_ref "
            "that names a unit which did not emit the finding is a receipt that reads correctly "
            "and is false")
    return result.reasoner_id


@dataclass(frozen=True, slots=True)
class CandidateAdjustment:
    play_id: str
    component: str
    delta_bp: int
    reason_code: str
    evidence_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "play_id", _identifier(self.play_id, "play_id"))
        object.__setattr__(self, "component", _identifier(self.component, "component"))
        object.__setattr__(self, "delta_bp", _signed_bp(self.delta_bp, "delta_bp"))
        object.__setattr__(self, "reason_code", _identifier(
            self.reason_code, "reason_code"))
        object.__setattr__(self, "evidence_ids", tuple(sorted(set(
            _strings(self.evidence_ids)))))


@dataclass(frozen=True, slots=True)
class CandidateCheck:
    play_id: str
    stage: str
    outcome: CheckOutcome
    reason_code: str
    evaluator_id: str
    evaluator_version: str
    detail: Mapping[str, Any] = field(default_factory=dict)
    score_before_bp: int | None = None
    score_after_bp: int | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "play_id", _identifier(self.play_id, "play_id"))
        object.__setattr__(self, "stage", _identifier(self.stage, "check stage"))
        if not isinstance(self.outcome, CheckOutcome):
            object.__setattr__(self, "outcome", CheckOutcome(self.outcome))
        object.__setattr__(self, "reason_code", _identifier(
            self.reason_code, "reason_code"))
        object.__setattr__(self, "evaluator_id", _identifier(
            self.evaluator_id, "evaluator_id"))
        object.__setattr__(self, "evaluator_version", _identifier(
            self.evaluator_version, "evaluator_version"))
        object.__setattr__(self, "detail", _mapping(self.detail))
        for name in ("score_before_bp", "score_after_bp"):
            if getattr(self, name) is not None:
                object.__setattr__(self, name, _bp(getattr(self, name), name))


@dataclass(frozen=True, slots=True)
class ReasonerResult:
    reasoner_id: str
    reasoner_version: str
    status: ResultStatus
    matched: bool | None = None
    metrics: Mapping[str, Any] = field(default_factory=dict)
    findings: tuple[Finding, ...] = ()
    adjustments: tuple[CandidateAdjustment, ...] = ()
    checks: tuple[CandidateCheck, ...] = ()
    evidence_ids: tuple[str, ...] = ()
    missing_fields: tuple[str, ...] = ()
    reason_codes: tuple[str, ...] = ()
    diagnostics: Mapping[str, Any] = field(default_factory=dict, compare=False, repr=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "reasoner_id", _identifier(
            self.reasoner_id, "reasoner_id"))
        object.__setattr__(self, "reasoner_version", _identifier(
            self.reasoner_version, "reasoner_version"))
        if not isinstance(self.status, ResultStatus):
            object.__setattr__(self, "status", ResultStatus(self.status))
        if self.matched is not None and not isinstance(self.matched, bool):
            raise TypeError("reasoner matched must be boolean or None")
        object.__setattr__(self, "metrics", _mapping(self.metrics))
        for name, value in self.metrics.items():
            if name.endswith("_bp"):
                _bp(value, f"reasoner metrics.{name}")
        object.__setattr__(self, "findings", tuple(self.findings))
        object.__setattr__(self, "adjustments", tuple(self.adjustments))
        object.__setattr__(self, "checks", tuple(self.checks))
        object.__setattr__(self, "evidence_ids", tuple(sorted(set(
            _strings(self.evidence_ids)))))
        object.__setattr__(self, "missing_fields", tuple(sorted(set(
            _strings(self.missing_fields)))))
        object.__setattr__(self, "reason_codes", tuple(sorted(set(
            _strings(self.reason_codes)))))
        object.__setattr__(self, "diagnostics", _mapping(self.diagnostics))
        if self.status != ResultStatus.COMPLETED and (
                self.matched is not None or self.metrics or self.findings or self.adjustments
                or self.checks or self.evidence_ids):
            raise ValueError(
                "non-completed reasoner results cannot carry decision effects or evidence")

    def to_semantic_dict(self) -> dict[str, Any]:
        return {"reasoner_id": self.reasoner_id, "reasoner_version": self.reasoner_version,
                "status": self.status, "matched": self.matched, "metrics": self.metrics,
                "findings": self.findings, "adjustments": self.adjustments,
                "checks": self.checks, "evidence_ids": self.evidence_ids,
                "missing_fields": self.missing_fields, "reason_codes": self.reason_codes}

    @property
    def semantic_hash(self) -> str:
        return semantic_hash(self.to_semantic_dict())

    def unit_ref_for(self, finding_id: str) -> str:
        """`unit_ref` addressed by id — the shape a store that holds findings and results apart
        needs. Same check, same refusal; see `unit_ref`."""
        finding = next((item for item in self.findings if item.finding_id == finding_id), None)
        if finding is None:
            raise ValueError(f"finding {finding_id} was not emitted by {self.reasoner_id}")
        return self.reasoner_id


@dataclass(frozen=True, slots=True)
class DecisionCandidate:
    play_id: str
    play_version: str
    disposition: CandidateDisposition
    utility_bp: int
    confidence_bp: int
    score_components: Mapping[str, int]
    rank_position: int | None = None
    checks: tuple[CandidateCheck, ...] = ()
    evidence_ids: tuple[str, ...] = ()
    parameters: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "play_id", _identifier(self.play_id, "play_id"))
        object.__setattr__(self, "play_version", _identifier(
            self.play_version, "play_version"))
        if not isinstance(self.disposition, CandidateDisposition):
            object.__setattr__(self, "disposition", CandidateDisposition(self.disposition))
        object.__setattr__(self, "utility_bp", _bp(self.utility_bp, "utility_bp"))
        object.__setattr__(self, "confidence_bp", _bp(self.confidence_bp, "confidence_bp"))
        components = dict(self.score_components)
        for key, value in components.items():
            components[key] = _bp(value, f"score_components.{key}")
        object.__setattr__(self, "score_components", _mapping(components))
        object.__setattr__(self, "checks", tuple(self.checks))
        if any(check.play_id != self.play_id for check in self.checks):
            raise ValueError("candidate checks must reference their candidate play")
        if self.rank_position is not None and (isinstance(self.rank_position, bool)
                                               or not isinstance(self.rank_position, int)
                                               or self.rank_position <= 0):
            raise ValueError("rank_position must be positive")
        if (self.disposition == CandidateDisposition.ELIMINATED
                and self.rank_position is not None):
            raise ValueError("eliminated candidates cannot have a rank")
        object.__setattr__(self, "evidence_ids", tuple(sorted(set(
            _strings(self.evidence_ids)))))
        object.__setattr__(self, "parameters", _mapping(self.parameters))

    def to_semantic_dict(self) -> dict[str, Any]:
        return {"play_id": self.play_id, "play_version": self.play_version,
                "disposition": self.disposition, "utility_bp": self.utility_bp,
                "confidence_bp": self.confidence_bp,
                "score_components": self.score_components,
                "rank_position": self.rank_position, "checks": self.checks,
                "evidence_ids": self.evidence_ids, "parameters": self.parameters}

    @property
    def candidate_id(self) -> str:
        return stable_id("cand", self.to_semantic_dict())

    # ── G-02 · the divergence K1 is measured on ──────────────────────────────────────────────
    #
    # Read, not stored. `reason/decision_maker.score_candidate` ALREADY writes the formula's own
    # answer into `score_components["formula_utility"]` on every branch — the number K1 needs has
    # been on the record all along with no typed way to ask for it, so a gate would have had to
    # read a string literal out of a mapping. A second field holding the same integer could
    # disagree with the first; a property cannot.

    @property
    def formula_utility_bp(self) -> int | None:
        """What the weighted formula scored this candidate, whether or not an override replaced it.

        None only for a candidate built by something that never ran the formula. On the compiled
        lane the override is present for EVERY candidate — which is why the formula has never once
        decided anything, and why this number and `utility_bp` being equal is itself the K1 signal
        that the override changed nothing.
        """
        value = self.score_components.get(FORMULA_UTILITY_COMPONENT)
        return int(value) if value is not None else None

    @property
    def utility_divergence_bp(self) -> int | None:
        """`utility_bp - formula_utility_bp`: by how much the override disagreed with the model.

        Signed and unclamped on purpose. It is a difference between two clamped numbers, so it lives
        in -10000..10000, and its SIGN is the finding — an override that consistently ranks a play
        below the formula is a different piece of evidence from one that consistently ranks it above.
        """
        formula = self.formula_utility_bp
        return None if formula is None else self.utility_bp - formula

    @property
    def semantic_hash(self) -> str:
        return semantic_hash(self.to_semantic_dict())


@dataclass(frozen=True, slots=True)
class StepTrace:
    ordinal: int
    reasoner_id: str
    reasoner_version: str
    status: ResultStatus
    input_hash: str
    output_hash: str
    reason_codes: tuple[str, ...] = ()
    missing_fields: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if isinstance(self.ordinal, bool) or not isinstance(self.ordinal, int) or self.ordinal <= 0:
            raise ValueError("trace ordinal must be a positive integer")
        object.__setattr__(self, "reasoner_id", _identifier(self.reasoner_id, "reasoner_id"))
        object.__setattr__(self, "reasoner_version", _identifier(
            self.reasoner_version, "reasoner_version"))
        if not isinstance(self.status, ResultStatus):
            object.__setattr__(self, "status", ResultStatus(self.status))
        object.__setattr__(self, "input_hash", _hash64(self.input_hash, "input_hash"))
        object.__setattr__(self, "output_hash", _hash64(self.output_hash, "output_hash"))
        object.__setattr__(self, "reason_codes", tuple(sorted(set(
            _strings(self.reason_codes)))))
        object.__setattr__(self, "missing_fields", tuple(sorted(set(
            _strings(self.missing_fields)))))


# ═════════════════════════════════════════════════════════════════════════════════════════════
# G-01 · the ReasoningBundle — Group L4.5, the voice
# ═════════════════════════════════════════════════════════════════════════════════════════════

#: The only two generations that exist. `template_fallback` is the deterministic plain version doc
#: 05 §6 prints — "plainer, never less true, and labelled, so nobody mistakes a fallback for a
#: narrative". A closed vocabulary because K4 measures the fallback RATE, and a rate over a free-text
#: column is a rate over whatever strings happened to be typed.
TEMPLATE_FALLBACK = "template_fallback"
_GENERATION = re.compile(r"^llm:[A-Za-z0-9][A-Za-z0-9._-]{0,63}@[A-Za-z0-9][A-Za-z0-9._+-]{0,31}$")

#: A placeholder is `{lower_snake_case}`. Narrow on purpose: `{Cost}`, `{cost }` and `{2}` are NOT
#: placeholders, so a model that writes one of them fails V-4/V-5 loudly instead of shipping a brace
#: to a customer's card.
_PLACEHOLDER = re.compile(r"\{([a-z][a-z0-9_]{0,63})\}")
_DIGITS = re.compile(r"\d+")

#: V-7's caps, per field. Generous enough that a real narrative never trips them — the point is to
#: refuse a runaway generation, not to compress the founder's card back into one sentence, which is
#: the wall this whole group exists to remove.
BUNDLE_FIELD_CAPS = MappingProxyType({
    "headline": 90,                       # doc 05 §2 prints this one; the card title
    "situation_summary": 400,
    "why_it_matters": 600,
    "root_cause": 600,
    "recommendation_rationale": 800,
    "expected_effect": 600,
    "alternatives_narrative": 800,
})

#: Every prose field, in the order the card renders them. `alternatives_narrative` is last and is
#: the only optional one — R-3 is an on-demand site (card expand), so a bundle without it is a
#: complete bundle rather than a degraded one.
BUNDLE_PROSE_FIELDS = tuple(BUNDLE_FIELD_CAPS)


def placeholders(text: Any) -> tuple[str, ...]:
    """Every `{placeholder}` in one prose field, first occurrence order, de-duplicated."""
    return tuple(dict.fromkeys(_PLACEHOLDER.findall(str(text or ""))))


def bare_numbers(text: Any) -> tuple[str, ...]:
    """V-4's detector: every digit run that is NOT inside a placeholder.

    Exposed as a function, not only enforced in the constructor, because doc 05 §4 runs the gauntlet
    in ORDER and records every outcome on the trace — so Z4 needs to be able to ASK "does this
    generation contain a bare number" and answer the model with the digits it typed, before any
    object exists. The constructor then refuses the same thing, so a bundle that skipped the gauntlet
    cannot exist either.
    """
    return tuple(dict.fromkeys(_DIGITS.findall(_PLACEHOLDER.sub(" ", str(text or "")))))


def require_generation(value: Any, label: str = "generation") -> str:
    """`llm:<model>@<version>` or `template_fallback`. Nothing else."""
    result = require_text(value, label)
    if result != TEMPLATE_FALLBACK and not _GENERATION.fullmatch(result):
        raise ValueError(
            f"{label} must be {TEMPLATE_FALLBACK!r} or 'llm:<model>@<version>', got {result!r}")
    return result


@dataclass(frozen=True, slots=True)
class ReasoningBundle:
    """R-2's output: the customer-facing reasoning narrative, generated AFTER the decision is fixed.

    **Law 2 lives here.** `action_id` must equal the action the decision committed to, and a mismatch
    is a CONSTRUCTOR ERROR, not a review nit — enforced twice, because there are two ways to get one
    wrong. `for_decision()` DERIVES both ids from the decision so they cannot be typed at all, and
    `ReasoningDecision.__post_init__` re-checks any bundle attached to it. That is what lets a model
    write freely here without ever being able to change what the company does.

    **`numbers_used` is the mechanism, not a note.** The model writes `"{do_nothing_cost}"`, never
    `"$84,000"`; code substitutes from computed values after generation (`render()`). A model that
    types a digit fails V-4 in the constructor. This is why the prose fields carry PLACEHOLDERS ONLY:
    a number in a narrative is a claim, and the only claims allowed here are ones the deterministic
    half already computed.

    **What this type does NOT enforce, and where it is enforced instead.** V-1's per-claim grounding
    and V-6's scope check both need the situation the bundle was written about, which is not part of
    the bundle; V-2's byte-identity is enforced on each citation by `require_citation`. So the
    constructor holds the structural half of the gauntlet — V-3, V-4, V-5, V-7, and the weaker
    "grounded by something" half of V-1 — and Z4's gauntlet runs the rest in order, recording each
    outcome on the trace. The split is deliberate: everything checkable from the object alone is
    checked BY the object, so no code path can produce an unchecked one.
    """

    decision_id: str
    #: V-3. The action the decision committed to — `ReasoningDecision.action_id`.
    action_id: str
    headline: str
    situation_summary: str
    why_it_matters: str
    root_cause: str
    recommendation_rationale: str
    expected_effect: str
    alternatives_narrative: str | None = None
    #: L3 corpus spans, byte-identical. Re-checked here by `require_citation` rather than trusted
    #: from the package, because this is the object a card renders from and the render is where a
    #: paraphrase would finally become visible to a customer.
    citations: tuple[Mapping[str, Any], ...] = ()
    evidence_refs: tuple[str, ...] = ()
    #: placeholder name -> the computed value code substitutes. Integers only, per the doctrine.
    numbers_used: Mapping[str, int] = field(default_factory=dict)
    generation: str = TEMPLATE_FALLBACK
    #: Content address over everything above. Derived when omitted; VERIFIED when supplied, so a
    #: bundle rehydrated from a store cannot come back with prose that does not match its hash.
    bundle_hash: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "decision_id", _identifier(self.decision_id, "decision_id"))
        object.__setattr__(self, "action_id", _identifier(self.action_id, "bundle action_id"))

        # ── V-7 · length and shape ──────────────────────────────────────────────────────────
        for name in BUNDLE_PROSE_FIELDS:
            raw = getattr(self, name)
            if raw is None:
                if name != "alternatives_narrative":
                    raise ValueError(f"bundle {name} is required")
                continue
            text = _text(raw, f"bundle {name}")
            cap = BUNDLE_FIELD_CAPS[name]
            if len(text) > cap:
                raise ValueError(
                    f"bundle {name} is {len(text)} characters, cap is {cap} (V-7)")
            object.__setattr__(self, name, text)

        # ── numbers_used, then V-4 and V-5 against it ───────────────────────────────────────
        numbers: dict[str, int] = {}
        for key, value in dict(self.numbers_used or {}).items():
            name = str(key)
            if not _PLACEHOLDER.fullmatch("{" + name + "}"):
                raise ValueError(
                    f"numbers_used key {name!r} is not a legal placeholder name — placeholders are "
                    "lower_snake_case, so a key nothing can reference is a computed number the card "
                    "will never show")
            if isinstance(value, bool) or not isinstance(value, int):
                raise TypeError(
                    f"numbers_used[{name!r}] must be an integer — the doctrine is integer basis "
                    "points and whole units; a float here is a rounded number on a customer's card")
            numbers[name] = value
        object.__setattr__(self, "numbers_used", _mapping(numbers))

        used: set[str] = set()
        for name in BUNDLE_PROSE_FIELDS:
            text = getattr(self, name)
            if text is None:
                continue
            # V-4 · no raw numbers. A digit outside a placeholder is a number the model generated
            # rather than one the deterministic half computed, and there is no way to tell from the
            # string which one it was — so the string is refused.
            bare = bare_numbers(text)
            if bare:
                raise ValueError(
                    f"bundle {name} contains bare number(s) {bare} (V-4) — numbers are TEMPLATED, "
                    "never generated: write '{placeholder}' and put the computed value in "
                    "numbers_used")
            # A brace that survived placeholder removal is a MALFORMED placeholder — `{ cost }`,
            # `{Cost}`, an unclosed `{`. Silently rendering it would ship a brace to a card, and
            # treating it as prose would let V-5 pass over a number that never resolves.
            residue = _PLACEHOLDER.sub("", text)
            if "{" in residue or "}" in residue:
                raise ValueError(
                    f"bundle {name} contains a malformed placeholder — placeholders are "
                    "{lower_snake_case} with no spaces")
            found = placeholders(text)
            # V-5 · placeholder resolution.
            unresolved = [item for item in found if item not in numbers]
            if unresolved:
                raise ValueError(
                    f"bundle {name} uses placeholder(s) {tuple(unresolved)} with no entry in "
                    "numbers_used (V-5)")
            used.update(found)
        unused = sorted(set(numbers) - used)
        if unused:
            raise ValueError(
                f"numbers_used carries {tuple(unused)} which no prose field references — a number "
                "computed and never shown is either a missing sentence or a stale substitution, and "
                "which one is not visible from the record")

        # ── V-1's structural half, V-2, and the generation vocabulary ───────────────────────
        object.__setattr__(self, "citations", tuple(
            require_citation(citation, "bundle citation") for citation in self.citations))
        if len(self.citations) > MAX_CITATIONS:
            raise ValueError(
                f"a bundle carries at most {MAX_CITATIONS} citations, got {len(self.citations)}")
        object.__setattr__(self, "evidence_refs", tuple(sorted(set(
            _strings(self.evidence_refs)))))
        if not self.evidence_refs and not self.citations:
            raise ValueError(
                "a bundle carries at least one evidence_ref or citation (V-1) — a narrative grounded "
                "in nothing is the ungrounded explanation this group exists to replace")
        object.__setattr__(self, "generation", require_generation(self.generation))

        derived = semantic_hash(self.to_semantic_dict())
        if self.bundle_hash is None:
            object.__setattr__(self, "bundle_hash", derived)
        elif _hash64(self.bundle_hash, "bundle_hash") != derived:
            raise ValueError("bundle_hash does not match bundle content")

    def to_semantic_dict(self) -> dict[str, Any]:
        """Everything except `bundle_hash`, which is the hash OF this."""
        return {"decision_id": self.decision_id, "action_id": self.action_id,
                "headline": self.headline, "situation_summary": self.situation_summary,
                "why_it_matters": self.why_it_matters, "root_cause": self.root_cause,
                "recommendation_rationale": self.recommendation_rationale,
                "expected_effect": self.expected_effect,
                "alternatives_narrative": self.alternatives_narrative,
                "citations": self.citations, "evidence_refs": self.evidence_refs,
                "numbers_used": self.numbers_used, "generation": self.generation}

    @property
    def semantic_hash(self) -> str:
        return semantic_hash(self.to_semantic_dict())

    @classmethod
    def for_decision(cls, decision: ReasoningDecision, **fields: Any) -> ReasoningBundle:
        """Mint a bundle FOR a decision. The only sanctioned way to obtain one.

        `decision_id` and `action_id` are DERIVED, never accepted: V-3 cannot be violated by a caller
        that never gets to type either id. Passing one anyway is refused rather than ignored — a
        caller that believes it is setting the action id and is being overruled is a caller that will
        eventually be right and unheard.

        Refuses a decision with no action. Doc 05 §7: bundles are generated only for published
        decisions, and a DEFER, a NO_ACTION or a BLOCKED outcome has no action for a narrative to be
        `about` — narrating one would mean inventing an action id, which is the one thing Law 2 is
        written to prevent. Silence stays reason-coded and unnarrated; widening this is a decision
        for the wave that has evidence a DEFER card needs prose, not a default taken here.
        """
        overreach = sorted({"decision_id", "action_id"} & set(fields))
        if overreach:
            raise ValueError(
                f"{overreach} are derived from the decision and cannot be supplied — V-3 is "
                "enforced by never letting the narrative name its own action")
        action_id = decision.action_id
        if action_id is None:
            raise ValueError(
                f"decision outcome {decision.outcome.value!r} committed to no action, so there is "
                "nothing for a bundle to narrate — bundles are minted for published decisions that "
                "chose something")
        return cls(decision_id=decision.decision_id, action_id=action_id, **fields)

    def render(self) -> Mapping[str, str | None]:
        """The customer-facing text: every placeholder replaced by its computed value.

        THIS is the substitution doc 05 calls the mechanism. It happens in code, after generation,
        over a mapping the deterministic half filled — so the digits a customer reads are the engine's
        digits, and there is no code path by which a model's digits reach a card.
        """
        out: dict[str, str | None] = {}
        for name in BUNDLE_PROSE_FIELDS:
            text = getattr(self, name)
            if text is None:
                out[name] = None
                continue
            out[name] = _PLACEHOLDER.sub(
                lambda match: str(self.numbers_used[match.group(1)]), text)
        return MappingProxyType(out)


@dataclass(frozen=True, slots=True)
class ReasoningDecision:
    outcome: DecisionOutcome
    capability_id: str
    capability_version: str
    context_snapshot_id: str
    candidates: tuple[DecisionCandidate, ...]
    selected_candidate_id: str | None
    confidence_bp: int
    uncertainty: tuple[str, ...]
    do_nothing_consequence: str
    expires_at: datetime
    outcome_window_days: int | None = None

    # ── E-02 · what Layer 3's corpus contributed to THIS decision ───────────────────────────
    #
    # Both default empty and both are additive: every decision written before this wave still
    # constructs, and `to_semantic_dict` omits them when empty so an old-shaped decision keeps
    # the exact `decision_hash` already sitting in its audit row.  Widening the hash for content
    # that does not exist would invalidate replay for every stored decision in exchange for
    # nothing.
    #
    #: Carried through from the ExpertisePackage — the authored claims this decision rests on,
    #: QUOTED.  `require_citation` re-checks byte-identity here rather than trusting the package,
    #: because this is the object a card renders from and the render is where a paraphrase would
    #: finally become visible to a customer.
    citations: tuple[Mapping[str, Any], ...] = ()
    #: Which compiled corpus rules fired, were satisfied, or could not be evaluated — the last of
    #: those naming what was UNKNOWN.  A blocking rule that fired names the candidates it
    #: eliminated, and those ids must be eliminated candidates ON THIS DECISION, which is what
    #: makes E5's "why not X?" answerable from the record instead of from a re-run.
    constraints_applied: tuple[Mapping[str, Any], ...] = ()

    # ── G-02 · what wave Z0 adds. All defaulted; every old shape still constructs, and every one
    # of these is omitted from `to_semantic_dict` when empty so a decision that gained none of it
    # keeps the exact `decision_hash` already sitting in its `reasoning_runs` row.
    #
    #: R-2's narrative, attached AFTER this decision exists. Deliberately NOT part of the semantic
    #: dict, and that is a correctness requirement rather than a hash-stability nicety: the bundle
    #: names `decision_id`, `decision_id` is the content address of this dict, so a bundle inside
    #: the dict would change the id it claims to carry. Excluding it is also Law 2 restated in the
    #: hash — the decision is fixed before any narrative exists, so no narrative can alter it.
    reasoning_bundle: ReasoningBundle | None = None
    #: E2 · Rule 11's named inputs, carried from the BSO. See `require_confidence_vector`.
    confidence_vector: Mapping[str, int] = field(default_factory=dict)
    #: G-06 · which weight scale ranked these candidates. Recorded on the decision rather than
    #: inferred from the capability at read time, because the capability can be re-versioned and the
    #: question "how was THIS decision ranked" must survive that.
    ranking_weights_version: str | None = None
    #: E4 · `{cost_bp, horizon, statement, source}`. See `require_do_nothing`.
    do_nothing: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.outcome, DecisionOutcome):
            object.__setattr__(self, "outcome", DecisionOutcome(self.outcome))
        object.__setattr__(self, "capability_id", _identifier(
            self.capability_id, "capability_id"))
        object.__setattr__(self, "capability_version", _identifier(
            self.capability_version, "capability_version"))
        object.__setattr__(self, "context_snapshot_id", _identifier(
            self.context_snapshot_id, "context_snapshot_id"))
        object.__setattr__(self, "candidates", tuple(self.candidates))
        if self.selected_candidate_id is not None:
            object.__setattr__(self, "selected_candidate_id", _identifier(
                self.selected_candidate_id, "selected_candidate_id"))
        object.__setattr__(self, "confidence_bp", _bp(self.confidence_bp, "confidence_bp"))
        object.__setattr__(self, "uncertainty", tuple(sorted(set(_strings(self.uncertainty)))))
        object.__setattr__(self, "do_nothing_consequence", _text(
            self.do_nothing_consequence, "do_nothing_consequence"))
        object.__setattr__(self, "expires_at", _aware(self.expires_at, "expires_at"))
        if self.outcome_window_days is not None and (
                isinstance(self.outcome_window_days, bool)
                or not isinstance(self.outcome_window_days, int)
                or not 1 <= self.outcome_window_days <= 365):
            raise ValueError("outcome_window_days must be between 1 and 365")
        ids = [candidate.candidate_id for candidate in self.candidates]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate decision candidate")
        eligible = [candidate for candidate in self.candidates
                    if candidate.disposition == CandidateDisposition.ELIGIBLE]
        ranks = [candidate.rank_position for candidate in eligible]
        if any(rank is None for rank in ranks) or sorted(ranks) != list(
                range(1, len(ranks) + 1)):
            raise ValueError("eligible candidate ranks must be contiguous from one")
        if self.outcome == DecisionOutcome.DECISION:
            if self.selected_candidate_id is None or self.selected_candidate_id not in ids:
                raise ValueError("decision outcome requires a selected eligible candidate")
            selected = next(c for c in self.candidates if c.candidate_id == self.selected_candidate_id)
            if selected.disposition != CandidateDisposition.ELIGIBLE:
                raise ValueError("selected candidate must be eligible")
            if selected.rank_position != 1:
                raise ValueError("selected candidate must be ranked first")
        elif self.selected_candidate_id is not None:
            raise ValueError("non-decision outcome cannot select a candidate")
        if self.outcome == DecisionOutcome.BLOCKED and eligible:
            raise ValueError("blocked outcome cannot contain eligible candidates")
        if self.outcome in {DecisionOutcome.NO_ACTION, DecisionOutcome.INSUFFICIENT_CONTEXT,
                            DecisionOutcome.FAILED} and self.candidates:
            raise ValueError(f"{self.outcome.value} outcome cannot contain candidates")
        object.__setattr__(self, "citations", tuple(
            require_citation(citation, "decision citation") for citation in self.citations))
        if len(self.citations) > MAX_CITATIONS:
            raise ValueError(
                f"a decision carries at most {MAX_CITATIONS} citations, got {len(self.citations)} "
                "— CLG-08 caps and RECEIPTS the truncation rather than letting a card grow a "
                "bibliography")
        object.__setattr__(self, "constraints_applied", tuple(
            require_constraint_application(applied, "constraint applied")
            for applied in self.constraints_applied))
        applied_ids = [applied["rule_id"] for applied in self.constraints_applied]
        if len(applied_ids) != len(set(applied_ids)):
            raise ValueError("a compiled rule is applied once per decision; a duplicate rule_id "
                             "means two records disagree about what the same rule did")
        # An elimination has to name a candidate that IS here and IS eliminated.  Naming an absent
        # or surviving candidate is a receipt that reads correctly and is false, which is worse
        # than no receipt at all: it is what `alternatives_rejected` renders straight onto a card.
        eliminated_here = {c.candidate_id for c in self.candidates
                           if c.disposition == CandidateDisposition.ELIMINATED}
        for applied in self.constraints_applied:
            for candidate_id in applied.get("eliminated_candidate_ids", ()):
                if candidate_id not in eliminated_here:
                    raise ValueError(
                        f"rule {applied['rule_id']} claims to have eliminated candidate "
                        f"{candidate_id}, which is not an eliminated candidate on this decision")
        object.__setattr__(self, "confidence_vector",
                           require_confidence_vector(self.confidence_vector))
        if self.ranking_weights_version is not None:
            version = _identifier(self.ranking_weights_version, "ranking_weights_version")
            if version not in RANKING_WEIGHTS_VERSIONS:
                raise ValueError(
                    f"ranking_weights_version must be one of {RANKING_WEIGHTS_VERSIONS}, "
                    f"got {version!r}")
            object.__setattr__(self, "ranking_weights_version", version)
        if self.do_nothing:
            object.__setattr__(self, "do_nothing", require_do_nothing(self.do_nothing))
        else:
            object.__setattr__(self, "do_nothing", _mapping({}))
        # ── V-3, at construction ────────────────────────────────────────────────────────────
        #
        # The second of the two enforcement points. `ReasoningBundle.for_decision` makes a mismatch
        # untypable on the way in; this makes it unattachable on the way in from anywhere else — a
        # bundle rehydrated from a store, one moved between decisions by a caller that meant well,
        # one regenerated against a decision that has since been recomputed. Law 2 says this is a
        # constructor error, so it is raised here rather than validated by a later pass that a
        # publication path could skip.
        if self.reasoning_bundle is not None:
            if not isinstance(self.reasoning_bundle, ReasoningBundle):
                raise TypeError("reasoning_bundle must be a ReasoningBundle")
            action_id = self.action_id
            if action_id is None:
                raise ValueError(
                    f"a {self.outcome.value} decision committed to no action and cannot carry a "
                    "narrative about one (V-3)")
            if self.reasoning_bundle.action_id != action_id:
                raise ValueError(
                    f"bundle action_id {self.reasoning_bundle.action_id!r} does not match the "
                    f"decision's action {action_id!r} (V-3) — a narrative that contradicts its "
                    "decision is a constructor error, not a review nit")
            if self.reasoning_bundle.decision_id != self.decision_id:
                raise ValueError(
                    f"bundle decision_id {self.reasoning_bundle.decision_id!r} belongs to another "
                    f"decision ({self.decision_id!r}) (V-3)")

    @property
    def action_id(self) -> str | None:
        """WHAT THIS DECISION COMMITTED TO — the play id of the selected candidate.

        The play, not the candidate id: `candidate_id` is a content address over the candidate's
        scores and checks, so it changes when a re-run scores the same action differently, and an
        action id that changes when nothing about the action changed is not an action id. `None` for
        every non-DECISION outcome, which is what makes "this decision has no action to narrate"
        answerable rather than assumed.
        """
        if self.outcome != DecisionOutcome.DECISION or self.selected_candidate_id is None:
            return None
        selected = next((c for c in self.candidates
                         if c.candidate_id == self.selected_candidate_id), None)
        return selected.play_id if selected is not None else None

    @property
    def formula_utility_bp(self) -> int | None:
        """The weighted formula's own score for the SELECTED candidate — K1's left-hand number."""
        if self.selected_candidate_id is None:
            return None
        selected = next((c for c in self.candidates
                         if c.candidate_id == self.selected_candidate_id), None)
        return selected.formula_utility_bp if selected is not None else None

    @property
    def utility_divergence_bp(self) -> int | None:
        """By how much an override disagreed with the formula on the action that won. K1's measure."""
        if self.selected_candidate_id is None:
            return None
        selected = next((c for c in self.candidates
                         if c.candidate_id == self.selected_candidate_id), None)
        return selected.utility_divergence_bp if selected is not None else None

    def with_bundle(self, bundle: ReasoningBundle) -> ReasoningDecision:
        """Attach a narrative to a FIXED decision, re-entering this constructor.

        `dataclasses.replace` rather than `object.__setattr__`, so V-3 runs — the pydantic
        `model_copy` hole L2 found on `MetricCorrelation` has a frozen-dataclass twin, and it is
        `object.__setattr__` on a slotted frozen instance. Every sanctioned attach goes through here.

        `decision_id` is unchanged by this call, by construction: the bundle is not in the semantic
        dict. That is what makes attaching a narrative safe to do after publication.
        """
        from dataclasses import replace
        return replace(self, reasoning_bundle=bundle)

    def to_semantic_dict(self) -> dict[str, Any]:
        body: dict[str, Any] = {
                "outcome": self.outcome, "capability_id": self.capability_id,
                "capability_version": self.capability_version,
                "context_snapshot_id": self.context_snapshot_id,
                "candidates": self.candidates,
                "selected_candidate_id": self.selected_candidate_id,
                "confidence_bp": self.confidence_bp, "uncertainty": self.uncertainty,
                "do_nothing_consequence": self.do_nothing_consequence,
                "expires_at": self.expires_at,
                "outcome_window_days": self.outcome_window_days}
        # Present only when carried — see the field comments.  `decision_hash` is stored in
        # `reasoning_runs` and compared on replay, so a decision that gained no corpus content must
        # hash to what it hashed to before this wave existed.
        if self.citations:
            body["citations"] = self.citations
        if self.constraints_applied:
            body["constraints_applied"] = self.constraints_applied
        # Z0's three additions, on the same terms and for the same reason. `reasoning_bundle` is
        # absent unconditionally — see its field comment; it is the narrative, and the narrative
        # cannot be part of the thing it narrates.
        if self.confidence_vector:
            body["confidence_vector"] = self.confidence_vector
        if self.ranking_weights_version:
            body["ranking_weights_version"] = self.ranking_weights_version
        if self.do_nothing:
            body["do_nothing"] = self.do_nothing
        return body

    @property
    def semantic_hash(self) -> str:
        return semantic_hash(self.to_semantic_dict())

    @property
    def decision_id(self) -> str:
        return stable_id("decision", self.to_semantic_dict())


@dataclass(frozen=True, slots=True)
class ReasoningTrace:
    run_id: str
    request_hash: str
    capability_snapshot_id: str
    context_snapshot_id: str
    orchestrator_version: str
    mode: ExecutionMode
    reasoner_plan: tuple[str, ...]
    steps: tuple[StepTrace, ...]
    decision_hash: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "run_id", _identifier(self.run_id, "run_id"))
        object.__setattr__(self, "request_hash", _hash64(self.request_hash, "request_hash"))
        object.__setattr__(self, "capability_snapshot_id", _identifier(
            self.capability_snapshot_id, "capability_snapshot_id"))
        object.__setattr__(self, "context_snapshot_id", _identifier(
            self.context_snapshot_id, "context_snapshot_id"))
        object.__setattr__(self, "orchestrator_version", _identifier(
            self.orchestrator_version, "orchestrator_version"))
        if not isinstance(self.mode, ExecutionMode):
            object.__setattr__(self, "mode", ExecutionMode(self.mode))
        object.__setattr__(self, "reasoner_plan", tuple(_strings(self.reasoner_plan)))
        object.__setattr__(self, "steps", tuple(self.steps))
        object.__setattr__(self, "decision_hash", _hash64(
            self.decision_hash, "decision_hash"))
        if tuple(step.ordinal for step in self.steps) != tuple(range(1, len(self.steps) + 1)):
            raise ValueError("trace step ordinals must be contiguous from one")
        if tuple(step.reasoner_id for step in self.steps) != self.reasoner_plan:
            raise ValueError("trace steps must match the declared reasoner plan")

    def to_semantic_dict(self) -> dict[str, Any]:
        return {"request_hash": self.request_hash,
                "capability_snapshot_id": self.capability_snapshot_id,
                "context_snapshot_id": self.context_snapshot_id,
                "orchestrator_version": self.orchestrator_version,
                "mode": self.mode, "reasoner_plan": self.reasoner_plan,
                "steps": self.steps, "decision_hash": self.decision_hash}

    @property
    def semantic_hash(self) -> str:
        return semantic_hash(self.to_semantic_dict())


# ═════════════════════════════════════════════════════════════════════════════════════════════
# G-04 / G-05 · the two OUTBOUND seams — critique (E1) and the book-level brief (E3)
#
# These are pydantic models, unlike everything above, because doc 07 prints them as pydantic models
# and because both cross a request boundary: an ExternalCandidate arrives as JSON from somebody
# else's agent, and a BriefRanking is serialised to a card surface. The frozen dataclasses above are
# internal artifacts that are content-addressed; these two are wire shapes that are validated.
# ═════════════════════════════════════════════════════════════════════════════════════════════


class RevalidatedModel(BaseModel):
    """Frozen, closed, and REVALIDATED ON COPY — L2's `Measurement` pattern, not a new idea.

    `model_copy(update=...)` runs NO validator in pydantic v2. L2 found that on a plain frozen model
    the single line `correlation.model_copy(update={"is_causal": True})` produced a well-typed object
    carrying the causal claim its V-7 exists to make unconstructible, and closed it with a base that
    re-enters the constructor on any copy WITH an update. The identical hole exists here and it is
    aimed at the identical kind of field: `CritiqueVerdict.advisory` is the safety property of the
    whole critique seam, and `advisory=True` enforced only in a validator that a copy skips is
    `advisory=True` enforced nowhere.

    **Why this is not `contracts.analytic.Measurement` itself.** Reusing that class is the obvious
    move and it is wrong twice. `test_l2_contracts.test_every_measurement_subclass_re_enters_its_
    constructor_on_copy` asserts the EXACT set of its subclasses, so a Layer 4 type inheriting from
    it turns an L2 law into a red test the moment this module is imported; and a critique verdict is
    not a measurement, so the base would be carrying two meanings. The mechanism is copied verbatim —
    the same override, the same "a copy with no update is the same fields and skips the work", the
    same deliberate decision to leave `model_construct` alone as pydantic's documented "I know what I
    am doing" door.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    def model_copy(self, *, update: Mapping[str, Any] | None = None, deep: bool = False):
        copied = super().model_copy(update=dict(update) if update else None, deep=deep)
        if not update:
            return copied
        return type(self).model_validate(dict(copied.__dict__))


#: E1's closed enum. An agent proposes one of four kinds of thing; anything else is refused at the
#: boundary rather than scored as an unknown and returned a verdict about.
EXTERNAL_CANDIDATE_KINDS = ("email_draft", "sequence", "task", "crm_change")

#: How much text an agent may hand us to critique. A cap, not a judgement about drafts: an
#: unbounded field on a request boundary is a memory limit expressed as a hope.
MAX_EXTERNAL_DRAFT_CHARS = 20_000


class ExternalCandidate(RevalidatedModel):
    """E1 · an action ANOTHER agent proposes to take, submitted to GeniOS for scoring.

    GeniOS never executes this and never modifies it. It scores it against the same corpus rules and
    the same utility formula its own candidates face, and returns a `CritiqueVerdict`. `target_ref`
    is required for exactly that reason: a proposal with no target cannot be checked against the
    situation it claims to be about, and an unscoped critique is an opinion.
    """

    proposal_id: str
    agent_id: str
    kind: str
    draft: str
    params: Mapping[str, Any] = Field(default_factory=dict)
    target_ref: str

    @field_validator("proposal_id", "agent_id", "target_ref", mode="before")
    @classmethod
    def _ids(cls, value: Any, info) -> str:
        return require_identifier(value, info.field_name or "id")

    @field_validator("kind", mode="before")
    @classmethod
    def _kind(cls, value: Any) -> str:
        text = require_text(value, "kind")
        if text not in EXTERNAL_CANDIDATE_KINDS:
            raise ValueError(f"kind must be one of {EXTERNAL_CANDIDATE_KINDS}, got {text!r}")
        return text

    @field_validator("draft", mode="before")
    @classmethod
    def _draft(cls, value: Any) -> str:
        text = require_text(value, "draft")
        if len(text) > MAX_EXTERNAL_DRAFT_CHARS:
            raise ValueError(f"draft is {len(text)} characters, cap is {MAX_EXTERNAL_DRAFT_CHARS}")
        return text

    @field_validator("params", mode="after")
    @classmethod
    def _params(cls, value: Any) -> Mapping[str, Any]:
        """Frozen through `canonicalize`, which is also what rejects the float.

        A proposal's params reach a scorer that is integer-only by doctrine, so a `0.87` arriving as
        JSON has to be refused at the boundary — coerced to `0` three frames later it is a silently
        wrong parameter on somebody else's email.

        `mode="after"`, not `"before"`: pydantic re-coerces a `Mapping` annotation back to a plain
        dict, so a proxy returned before validation is unwrapped again and the deep-freeze is lost.
        Run after, the returned proxy is what the field keeps."""
        return _mapping(value or {})


#: The three things a critique can say. Closed, and none of them is "do it": GeniOS scores, the
#: agent executes.
CRITIQUE_VERDICTS = ("proceed", "modify", "hold")


class CritiqueVerdict(RevalidatedModel):
    """E1's answer. **`advisory` is True and cannot be constructed False.**

    That is the safety property of the entire critique seam, and it is a structural one rather than a
    documented one for the reason L2's `is_causal` is: an assertion in a docstring gets re-litigated
    by the first caller who wants the other value. GeniOS scores; the agent executes. A verdict that
    could be made binding would make GeniOS the operator of somebody else's system, on evidence it
    does not own, through an API that was sold as an opinion.

    The field exists in order to be True, which is the same argument `is_causal` makes for existing
    in order to be False: without it, "does this verdict claim authority?" has no answer in the data,
    so every consumer is free to supply its own — and the first executor that treats `hold` as a
    block is indistinguishable from one that read a real binding claim.
    """

    verdict: str
    #: ALWAYS True. See the class docstring.
    advisory: bool = True
    failing_checks: tuple[str, ...] = ()
    winning_alternative: str | None = None
    utility_bp: int
    confidence_bp: int
    #: R-3-narrated and evidence-bound. Prose, because it is read by a human deciding whether to
    #: overrule us — the one place in this seam where a sentence is the product.
    rationale: str

    @field_validator("verdict", mode="before")
    @classmethod
    def _verdict(cls, value: Any) -> str:
        text = require_text(value, "verdict")
        if text not in CRITIQUE_VERDICTS:
            raise ValueError(f"verdict must be one of {CRITIQUE_VERDICTS}, got {text!r}")
        return text

    @field_validator("advisory", mode="before")
    @classmethod
    def _advisory_flag(cls, value: Any) -> bool:
        """A literal bool. Truthiness is exactly how a `0` from a jsonb column would become a
        binding verdict nobody typed."""
        return require_bool(value, "advisory")

    @field_validator("failing_checks", mode="before")
    @classmethod
    def _checks(cls, value: Any) -> tuple[str, ...]:
        return tuple(sorted(set(require_identifier(item, "failing check")
                                for item in (value or ()))))

    @field_validator("winning_alternative", mode="before")
    @classmethod
    def _alternative(cls, value: Any) -> str | None:
        return None if value is None else require_identifier(value, "winning_alternative")

    @field_validator("utility_bp", "confidence_bp", mode="before")
    @classmethod
    def _bps(cls, value: Any, info) -> int:
        return require_bp(value, info.field_name or "bp")

    @field_validator("rationale", mode="before")
    @classmethod
    def _rationale(cls, value: Any) -> str:
        return require_text(value, "rationale")

    @model_validator(mode="after")
    def _always_advisory(self) -> CritiqueVerdict:
        """The refusal. Always, with no override, and reachable from no copy — see `RevalidatedModel`.

        A `hold` with no failing check is refused in the same breath: "hold" is a claim that something
        is wrong, and a claim with no receipt is the thing this codebase does not ship.
        """
        if not self.advisory:
            raise ValueError(
                "advisory must be True — GeniOS scores and the agent executes; the field exists so "
                "the absence of a binding claim is explicit in every verdict that crosses the seam")
        if self.verdict == "hold" and not self.failing_checks:
            raise ValueError(
                "a 'hold' verdict names the checks that failed — a hold with no failing check is a "
                "refusal whose reason cannot be shown to the agent that asked")
        return self


class BriefEntry(RevalidatedModel):
    """One decision's place in today's brief, WITH the components that put it there.

    `rank_components` is required and must be non-empty: doc 07 says *"why #1 today" is data, not
    narrative*, and an entry carrying only a rank and a score can answer "what is first" but not
    "why", so the answer would have to be regenerated as prose — which is a model explaining a
    ranking it cannot see, i.e. the failure mode this whole layer is being rebuilt to remove.
    """

    decision_id: str
    rank: int
    book_score_bp: int
    #: Annotated `Any`-valued and validated to integer bp below, not `Mapping[str, int]`: pydantic's
    #: lax mode turns a `1.0` into a `1` and stores it, so the annotation that looks stricter is the
    #: one that lets a float through. `require_bp` refuses it.
    rank_components: Mapping[str, Any]

    @field_validator("decision_id", mode="before")
    @classmethod
    def _decision(cls, value: Any) -> str:
        return require_identifier(value, "decision_id")

    @field_validator("rank", mode="before")
    @classmethod
    def _rank(cls, value: Any) -> int:
        return require_ordinal(value, "rank")

    @field_validator("book_score_bp", mode="before")
    @classmethod
    def _score(cls, value: Any) -> int:
        return require_bp(value, "book_score_bp")

    @field_validator("rank_components", mode="after")
    @classmethod
    def _components(cls, value: Any) -> Mapping[str, int]:
        if not isinstance(value, Mapping) or not value:
            raise ValueError(
                "rank_components is required and non-empty — 'why #1 today' is data, not narrative")
        return _mapping({str(k): require_bp(v, f"rank_components.{k}") for k, v in value.items()})


class BriefRanking(RevalidatedModel):
    """E3 · the book-level daily re-rank for ONE tenant.

    Ranks are contiguous from one and decision ids are unique, checked here rather than by the
    producer: a brief with two #2s and no #3 renders in an order nobody chose, and a brief naming the
    same decision twice double-counts one situation's importance against every other.
    """

    org_id: str
    #: `YYYY-MM-DD`, the tenant's brief day. A date KEY rather than a timestamp because the brief is
    #: a daily artifact and "which brief" must not depend on what hour it was assembled.
    brief_date_key: str
    entries: tuple[BriefEntry, ...] = ()

    @field_validator("org_id", mode="before")
    @classmethod
    def _org(cls, value: Any) -> str:
        return require_identifier(value, "org_id")

    @field_validator("brief_date_key", mode="before")
    @classmethod
    def _date_key(cls, value: Any) -> str:
        text = require_text(value, "brief_date_key")
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
            raise ValueError(f"brief_date_key must be YYYY-MM-DD, got {text!r}")
        return text

    @model_validator(mode="after")
    def _contiguous(self) -> BriefRanking:
        ranks = [entry.rank for entry in self.entries]
        if sorted(ranks) != list(range(1, len(ranks) + 1)):
            raise ValueError(
                f"brief ranks must be contiguous from one, got {sorted(ranks)}")
        ids = [entry.decision_id for entry in self.entries]
        if len(ids) != len(set(ids)):
            raise ValueError("a decision appears once in a brief")
        return self
