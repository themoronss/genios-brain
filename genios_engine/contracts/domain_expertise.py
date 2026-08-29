"""Typed Layer 2 -> Layer 3 -> Layer 4 contracts.

The Domain Expertise compiler is deliberately a packaging boundary, not a reasoning surface.
It receives one already-qualified business situation, binds the smallest relevant authored and
runtime knowledge slice, and emits one immutable expertise package. The common Atlas envelope is
present under the same four names on both Layer 2 inputs and the Layer 3 output.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from genios_engine.contracts.validators import (
    freeze_mapping,
    require_bp,
    require_hash64,
    require_identifier,
    require_aware,
    require_sorted_unique,
)
from genios_engine.contracts.visibility import Visibility
from genios_engine.platform.canonical import semantic_hash, stable_id

BUSINESS_SITUATION_VERSION = "business-situation.v1"
SITUATION_CONTEXT_VERSION = "situation-context.v1"
EXPERTISE_PACKAGE_VERSION = "expertise-package.v1"


def _records(values: Any, label: str) -> tuple[Mapping[str, Any], ...]:
    records: list[Mapping[str, Any]] = []
    for value in values or ():
        if not isinstance(value, Mapping):
            raise TypeError(f"{label} entries must be mappings")
        records.append(freeze_mapping(value))
    return tuple(records)


def _visibility(value: Visibility | Mapping[str, Any]) -> Mapping[str, Any]:
    parsed = value if isinstance(value, Visibility) else Visibility.model_validate(dict(value))
    return freeze_mapping(parsed.model_dump())


class BrainKind(str, Enum):
    EXPERT = "expert"
    ORGANIZATION = "organization"
    BEHAVIOR = "behavior"
    ADAPTIVE = "adaptive"


@dataclass(frozen=True, slots=True)
class BusinessSituationObject:
    """Layer 2's complete, immutable output to the Domain Expertise compiler."""

    org_id: str
    trace_id: str
    visibility: Visibility | Mapping[str, Any]
    id: str
    signal_ids: tuple[str, ...]
    type: str
    confidence_bp: int
    importance_bp: int
    evidence: tuple[Mapping[str, Any], ...]
    entities: tuple[Mapping[str, Any], ...] = ()
    relationships: tuple[Mapping[str, Any], ...] = ()
    timeline: tuple[Mapping[str, Any], ...] = ()
    dependencies: tuple[Mapping[str, Any], ...] = ()
    state: str = "active"
    metadata: Mapping[str, Any] = field(default_factory=dict)
    schema_version: str = BUSINESS_SITUATION_VERSION

    def __post_init__(self) -> None:
        setter = object.__setattr__
        setter(self, "org_id", require_identifier(self.org_id, "org id"))
        setter(self, "trace_id", require_identifier(self.trace_id, "trace id"))
        setter(self, "schema_version", require_identifier(
            self.schema_version, "business situation schema version"))
        if self.schema_version != BUSINESS_SITUATION_VERSION:
            raise ValueError(f"unsupported business situation schema {self.schema_version!r}")
        setter(self, "visibility", _visibility(self.visibility))
        setter(self, "id", require_identifier(self.id, "situation id"))
        setter(self, "signal_ids", require_sorted_unique(self.signal_ids, "signal id"))
        if not self.signal_ids:
            raise ValueError("a business situation requires at least one qualified signal")
        setter(self, "type", require_identifier(self.type, "situation type"))
        setter(self, "confidence_bp", require_bp(self.confidence_bp, "confidence_bp"))
        setter(self, "importance_bp", require_bp(self.importance_bp, "importance_bp"))
        setter(self, "evidence", _records(self.evidence, "situation evidence"))
        if not self.evidence:
            raise ValueError("a business situation requires evidence")
        setter(self, "entities", _records(self.entities, "situation entity"))
        setter(self, "relationships", _records(
            self.relationships, "situation relationship"))
        setter(self, "timeline", _records(self.timeline, "situation timeline"))
        setter(self, "dependencies", _records(self.dependencies, "situation dependency"))
        setter(self, "state", require_identifier(self.state, "situation state"))
        setter(self, "metadata", freeze_mapping(self.metadata))

    def to_semantic_dict(self) -> dict[str, Any]:
        """The package's CONTENT — what `expertise_id` and `semantic_hash` address.

        `trace_id` is deliberately absent, and its absence is the whole point of the method.
        A trace id identifies one OBSERVATION of a package, not the package: `domain_shadow`
        mints a fresh `new_id("trace")` per situation per sweep, so including it made every
        compile content-address to a brand-new id even when the situation, the knowledge, the
        graph version and every capability were byte-identical. The publisher's
        `on conflict (org_id, expertise_id) do nothing` then never fired, and each sweep wrote a
        fresh ~238 kB row per situation. On the design partner's database that reached 4,086 rows
        and 995 MB — 67% of the entire database, on a table holding 127 distinct situations — and
        the project crossed its disk quota into read-only, which stops every write the product
        makes, not just this one.

        The determinism test that should have caught this passes a CONSTANT `trace_id` from its
        fixture, so it proved the compiler deterministic in everything except the one field that
        is never constant in production. `test_a_repeat_compile_does_not_mint_a_new_package` drives
        it the way `domain_shadow` does, with a different trace id each time.

        The trace id is still stored — it has its own column, and it is what ties a package back to
        the sweep that observed it. It just does not participate in the content address, which is
        what "content-addressed" means.
        """
        return {
            "org_id": self.org_id,
            "schema_version": self.schema_version,
            "visibility": self.visibility,
            "id": self.id,
            "signal_ids": self.signal_ids,
            "type": self.type,
            "entities": self.entities,
            "relationships": self.relationships,
            "timeline": self.timeline,
            "dependencies": self.dependencies,
            "confidence_bp": self.confidence_bp,
            "importance_bp": self.importance_bp,
            "evidence": self.evidence,
            "state": self.state,
            "metadata": self.metadata,
        }

    @property
    def semantic_hash(self) -> str:
        return semantic_hash(self.to_semantic_dict())

    @property
    def domain_hints(self) -> tuple[str, ...]:
        raw = (self.metadata.get("domain_ids") or self.metadata.get("domains")
               or self.metadata.get("domain_id") or self.metadata.get("domain") or ())
        if isinstance(raw, str):
            raw = (raw,)
        return require_sorted_unique(raw, "domain hint")

    @property
    def brain_subject_keys(self) -> tuple[str, ...]:
        raw = self.metadata.get("brain_subject_keys") or ()
        return require_sorted_unique(raw, "brain subject key")


@dataclass(frozen=True, slots=True)
class SituationContextSlice:
    """The relevant Layer 2 graph slice supplied to Layer 3; never fetched by Layer 3."""

    org_id: str
    trace_id: str
    visibility: Visibility | Mapping[str, Any]
    id: str
    graph_version: int
    selector_version: str
    evaluation_time: datetime
    root_entity_ids: tuple[str, ...]
    facts: Mapping[str, Any] = field(default_factory=dict)
    observations: tuple[Mapping[str, Any], ...] = ()
    neighbor_facts: Mapping[str, Any] = field(default_factory=dict)
    neighbor_observations: tuple[str, ...] = ()
    edge_count: int = 0
    evidence: tuple[Mapping[str, Any], ...] = ()
    missing_fields: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)
    schema_version: str = SITUATION_CONTEXT_VERSION

    def __post_init__(self) -> None:
        setter = object.__setattr__
        setter(self, "org_id", require_identifier(self.org_id, "context org id"))
        setter(self, "trace_id", require_identifier(self.trace_id, "context trace id"))
        setter(self, "schema_version", require_identifier(
            self.schema_version, "situation context schema version"))
        if self.schema_version != SITUATION_CONTEXT_VERSION:
            raise ValueError(f"unsupported situation context schema {self.schema_version!r}")
        setter(self, "visibility", _visibility(self.visibility))
        setter(self, "id", require_identifier(self.id, "context slice id"))
        if isinstance(self.graph_version, bool) or not isinstance(self.graph_version, int) \
                or self.graph_version < 0:
            raise ValueError("context graph_version must be a non-negative integer")
        setter(self, "selector_version", require_identifier(
            self.selector_version, "context selector version"))
        setter(self, "evaluation_time", require_aware(
            self.evaluation_time, "context evaluation_time"))
        setter(self, "root_entity_ids", require_sorted_unique(
            self.root_entity_ids, "context root entity id"))
        if not self.root_entity_ids:
            raise ValueError("a context slice requires at least one root entity")
        setter(self, "facts", freeze_mapping(self.facts))
        setter(self, "observations", _records(self.observations, "context observation"))
        setter(self, "neighbor_facts", freeze_mapping(self.neighbor_facts))
        setter(self, "neighbor_observations", require_sorted_unique(
            self.neighbor_observations, "context neighbor observation"))
        if isinstance(self.edge_count, bool) or not isinstance(self.edge_count, int) \
                or self.edge_count < 0:
            raise ValueError("context edge_count must be a non-negative integer")
        setter(self, "evidence", _records(self.evidence, "context evidence"))
        setter(self, "missing_fields", require_sorted_unique(
            self.missing_fields, "context missing field"))
        setter(self, "metadata", freeze_mapping(self.metadata))

    def to_semantic_dict(self) -> dict[str, Any]:
        """The slice's CONTENT — what `semantic_hash` addresses.

        Two fields the dataclass carries are deliberately absent, and both are observation
        metadata rather than content: `trace_id` (which sweep looked) and `evaluation_time`
        (when it looked). What the slice IS — the facts, observations, neighbours and edges of one
        anchor — is pinned exactly by `graph_version` and `selector_version`, which are here. Two
        sweeps over an unchanged graph see the same slice, and should hash to the same slice.

        This is not a cosmetic distinction. `context_slice_hash` is carried in the expertise
        package's metadata, so it feeds the PACKAGE's content address: while these two fields were
        hashed in, every sweep minted a new package id for unchanged knowledge, the publisher's
        `on conflict do nothing` never fired, and each sweep wrote a fresh ~238 kB row per
        situation. On the design partner's database that reached 4,086 rows and 995 MB — 67% of the
        whole database for 127 distinct situations — and the project crossed its disk quota into
        read-only, which stops every write the product makes, not only this one.

        Removing the clock from the slice's identity does NOT make reasoning time-blind: the
        evaluation time is passed to the reasoner in its own right, decisions and audit bundles are
        written per run, and the field remains on the dataclass for anyone reading a slice. It just
        does not decide whether this is the same slice.
        """
        return {
            "org_id": self.org_id,
            "schema_version": self.schema_version,
            "visibility": self.visibility,
            "id": self.id,
            "graph_version": self.graph_version,
            "selector_version": self.selector_version,
            "root_entity_ids": self.root_entity_ids,
            "facts": self.facts,
            "observations": self.observations,
            "neighbor_facts": self.neighbor_facts,
            "neighbor_observations": self.neighbor_observations,
            "edge_count": self.edge_count,
            "evidence": self.evidence,
            "missing_fields": self.missing_fields,
            "metadata": self.metadata,
        }

    @property
    def semantic_hash(self) -> str:
        return semantic_hash(self.to_semantic_dict())


@dataclass(frozen=True, slots=True)
class ExpertiseEvidence:
    """One receipt proving where a compiled knowledge item came from."""

    brain: BrainKind
    source_ref: str
    source_version: str
    content_hash: str
    confidence_bp: int
    visibility: Visibility | Mapping[str, Any]
    trace_ids: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        setter = object.__setattr__
        if not isinstance(self.brain, BrainKind):
            setter(self, "brain", BrainKind(self.brain))
        setter(self, "source_ref", require_identifier(self.source_ref, "evidence source ref"))
        setter(self, "source_version", require_identifier(
            self.source_version, "evidence source version"))
        setter(self, "content_hash", require_hash64(self.content_hash, "evidence content hash"))
        setter(self, "confidence_bp", require_bp(self.confidence_bp, "evidence confidence_bp"))
        setter(self, "visibility", _visibility(self.visibility))
        setter(self, "trace_ids", require_sorted_unique(self.trace_ids, "source trace id"))
        setter(self, "metadata", freeze_mapping(self.metadata))

    def to_semantic_dict(self) -> dict[str, Any]:
        return {
            "brain": self.brain,
            "source_ref": self.source_ref,
            "source_version": self.source_version,
            "content_hash": self.content_hash,
            "confidence_bp": self.confidence_bp,
            "visibility": self.visibility,
            "trace_ids": self.trace_ids,
            "metadata": self.metadata,
        }


@dataclass(frozen=True, slots=True)
class ExpertisePackage:
    """Layer 3's entire output.  Structured expertise only; no recommendation or decision."""

    org_id: str
    trace_id: str
    visibility: Visibility | Mapping[str, Any]
    id: str
    situation_id: str
    brain_snapshot_id: str
    capabilities: tuple[Mapping[str, Any], ...]
    objects: tuple[Mapping[str, Any], ...]
    expert_rules: tuple[Mapping[str, Any], ...]
    organization_rules: tuple[Mapping[str, Any], ...]
    behavior_patterns: tuple[Mapping[str, Any], ...]
    adaptive_preferences: tuple[Mapping[str, Any], ...]
    confidence_bp: int
    evidence: tuple[ExpertiseEvidence, ...]
    metadata: Mapping[str, Any] = field(default_factory=dict)
    schema_version: str = EXPERTISE_PACKAGE_VERSION

    def __post_init__(self) -> None:
        setter = object.__setattr__
        setter(self, "org_id", require_identifier(self.org_id, "org id"))
        setter(self, "trace_id", require_identifier(self.trace_id, "trace id"))
        setter(self, "schema_version", require_identifier(
            self.schema_version, "expertise package schema version"))
        if self.schema_version != EXPERTISE_PACKAGE_VERSION:
            raise ValueError(f"unsupported expertise package schema {self.schema_version!r}")
        setter(self, "visibility", _visibility(self.visibility))
        setter(self, "id", require_identifier(self.id, "expertise id"))
        setter(self, "situation_id", require_identifier(self.situation_id, "situation id"))
        setter(self, "brain_snapshot_id", require_identifier(
            self.brain_snapshot_id, "brain snapshot id"))
        for name in ("capabilities", "objects", "expert_rules", "organization_rules",
                     "behavior_patterns", "adaptive_preferences"):
            setter(self, name, _records(getattr(self, name), name.replace("_", " ")))
        if not self.capabilities:
            raise ValueError("an expertise package requires at least one capability")
        if not self.objects:
            raise ValueError("an expertise package requires at least one knowledge object")
        setter(self, "confidence_bp", require_bp(self.confidence_bp, "confidence_bp"))
        setter(self, "evidence", tuple(sorted(self.evidence, key=lambda item: (
            item.brain.value, item.source_ref, item.content_hash))))
        if not self.evidence:
            raise ValueError("an expertise package requires evidence")
        setter(self, "metadata", freeze_mapping(self.metadata))

    def to_semantic_dict(self) -> dict[str, Any]:
        """The package's CONTENT — what `expertise_id` and `semantic_hash` address.

        `trace_id` is deliberately absent, and its absence is the whole point of the method.
        A trace id identifies one OBSERVATION of a package, not the package: `domain_shadow`
        mints a fresh `new_id("trace")` per situation per sweep, so including it made every
        compile content-address to a brand-new id even when the situation, the knowledge, the
        graph version and every capability were byte-identical. The publisher's
        `on conflict (org_id, expertise_id) do nothing` then never fired, and each sweep wrote a
        fresh ~238 kB row per situation. On the design partner's database that reached 4,086 rows
        and 995 MB — 67% of the entire database, on a table holding 127 distinct situations — and
        the project crossed its disk quota into read-only, which stops every write the product
        makes, not just this one.

        The determinism test that should have caught this passes a CONSTANT `trace_id` from its
        fixture, so it proved the compiler deterministic in everything except the one field that
        is never constant in production. `test_a_repeat_compile_does_not_mint_a_new_package` drives
        it the way `domain_shadow` does, with a different trace id each time.

        The trace id is still stored — it has its own column, and it is what ties a package back to
        the sweep that observed it. It just does not participate in the content address, which is
        what "content-addressed" means.
        """
        return {
            "org_id": self.org_id,
            "schema_version": self.schema_version,
            "visibility": self.visibility,
            "id": self.id,
            "situation_id": self.situation_id,
            "brain_snapshot_id": self.brain_snapshot_id,
            "capabilities": self.capabilities,
            "objects": self.objects,
            "expert_rules": self.expert_rules,
            "organization_rules": self.organization_rules,
            "behavior_patterns": self.behavior_patterns,
            "adaptive_preferences": self.adaptive_preferences,
            "confidence_bp": self.confidence_bp,
            "evidence": self.evidence,
            "metadata": self.metadata,
        }

    @property
    def semantic_hash(self) -> str:
        return semantic_hash(self.to_semantic_dict())


def expertise_id(body: Mapping[str, Any]) -> str:
    """Content-address a package body before the id field itself exists.

    `trace_id` is dropped here rather than by the caller, because this is the ONE place every
    caller passes through and the builder's `body` is a hand-written dict that will be edited
    again. `ExpertisePackage.to_semantic_dict` makes the same exclusion for the same reason; the
    two must agree, or the id and the hash disagree about what the package is and the publisher's
    immutability check rejects a package identical to the one it already holds.

    See `to_semantic_dict` for what this cost: a fresh trace id per sweep meant a fresh id per
    sweep, `on conflict (org_id, expertise_id) do nothing` never fired, and unchanged knowledge
    was rewritten at ~238 kB a situation until the database went read-only.
    """
    return stable_id("expertise", {k: v for k, v in body.items() if k != "trace_id"})


__all__ = [
    "BUSINESS_SITUATION_VERSION",
    "SITUATION_CONTEXT_VERSION",
    "EXPERTISE_PACKAGE_VERSION",
    "BrainKind",
    "BusinessSituationObject",
    "ExpertiseEvidence",
    "ExpertisePackage",
    "SituationContextSlice",
    "expertise_id",
]
