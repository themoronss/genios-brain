"""Immutable cross-layer contracts for the deterministic Layer 4 reasoning kernel."""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from types import MappingProxyType
from typing import Any

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
        weights = dict(self.ranking_weights)
        required = {"impact", "success", "urgency", "effort", "risk"}
        if set(weights) != required or any(isinstance(v, bool) or not isinstance(v, int)
                                           or v < 0 for v in weights.values()):
            raise ValueError("ranking_weights require five non-negative integer weights")
        if sum(weights.values()) != 100:
            raise ValueError("ranking_weights must sum to 100")
        object.__setattr__(self, "ranking_weights", _mapping(weights))
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
    finding_id: str
    kind: str
    matched: bool | None = None
    metrics: Mapping[str, Any] = field(default_factory=dict)
    evidence_ids: tuple[str, ...] = ()
    reason_codes: tuple[str, ...] = ()

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
        if isinstance(self.delta_bp, bool) or not isinstance(self.delta_bp, int) \
                or not -10_000 <= self.delta_bp <= 10_000:
            raise ValueError("delta_bp must be between -10000 and 10000")
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

    def to_semantic_dict(self) -> dict[str, Any]:
        return {"outcome": self.outcome, "capability_id": self.capability_id,
                "capability_version": self.capability_version,
                "context_snapshot_id": self.context_snapshot_id,
                "candidates": self.candidates,
                "selected_candidate_id": self.selected_candidate_id,
                "confidence_bp": self.confidence_bp, "uncertainty": self.uncertainty,
                "do_nothing_consequence": self.do_nothing_consequence,
                "expires_at": self.expires_at,
                "outcome_window_days": self.outcome_window_days}

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
