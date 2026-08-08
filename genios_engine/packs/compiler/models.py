"""Internal immutable compiler plans.  None of these cross a product-layer boundary."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from genios_engine.contracts.domain_expertise import BrainKind, ExpertiseEvidence
from genios_engine.contracts.visibility import Visibility
from genios_engine.contracts.validators import (
    freeze_mapping,
    require_aware,
    require_bp,
    require_identifier,
)


@dataclass(frozen=True, slots=True)
class SourceDocument:
    kind: str
    id: str
    domain_id: str
    version: str
    relative_path: str
    content: Mapping[str, Any]
    content_hash: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "content", freeze_mapping(self.content))


@dataclass(frozen=True, slots=True)
class DomainRecord:
    domain: SourceDocument
    routes: Mapping[str, Any]
    capabilities: Mapping[str, SourceDocument]
    situations: Mapping[str, SourceDocument]
    objects: Mapping[str, SourceDocument]
    artifacts: Mapping[str, SourceDocument]
    variants: Mapping[str, SourceDocument]
    object_manifests: Mapping[str, SourceDocument]
    knowledge_manifests: Mapping[str, SourceDocument]


@dataclass(frozen=True, slots=True)
class RoutePlan:
    domain_ids: tuple[str, ...]
    situation_ids: tuple[str, ...]
    capability_ids: tuple[str, ...]
    required_object_ids: tuple[str, ...]
    optional_object_ids: tuple[str, ...]
    never_object_ids: tuple[str, ...]
    unresolved_predicates: tuple[str, ...] = ()
    skipped_capability_ids: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ExpertSlice:
    capabilities: tuple[SourceDocument, ...]
    objects: tuple[SourceDocument, ...]
    artifacts: tuple[SourceDocument, ...]
    variants: tuple[SourceDocument, ...]
    sources: tuple[SourceDocument, ...]
    missing_optional: tuple[str, ...]
    missing_artifacts: tuple[str, ...]
    coverage_bp: int
    snapshot_id: str


@dataclass(frozen=True, slots=True)
class RuntimeBrainEntry:
    org_id: str
    brain: BrainKind
    entry_id: str
    subject_key: str
    version: int
    value: Mapping[str, Any]
    confidence_bp: int
    learning_id: str
    effective_at: datetime
    visibility: Mapping[str, Any]
    trace_id: str
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "org_id", require_identifier(self.org_id, "org id"))
        if not isinstance(self.brain, BrainKind):
            object.__setattr__(self, "brain", BrainKind(self.brain))
        object.__setattr__(self, "entry_id", require_identifier(self.entry_id, "brain entry id"))
        object.__setattr__(self, "subject_key", require_identifier(
            self.subject_key, "brain subject key"))
        if isinstance(self.version, bool) or not isinstance(self.version, int) or self.version <= 0:
            raise ValueError("brain entry version must be a positive integer")
        object.__setattr__(self, "value", freeze_mapping(self.value))
        conflict_key = self.value.get("conflict_key")
        if conflict_key is not None:
            normalized = require_identifier(conflict_key, "brain conflict key")
            if not isinstance(conflict_key, str) or conflict_key != normalized:
                raise ValueError("brain conflict key must be a normalized string identifier")
        object.__setattr__(self, "confidence_bp", require_bp(
            self.confidence_bp, "brain confidence_bp"))
        object.__setattr__(self, "learning_id", require_identifier(
            self.learning_id, "learning id"))
        object.__setattr__(self, "effective_at", require_aware(
            self.effective_at, "brain effective_at"))
        parsed_visibility = Visibility.model_validate(dict(self.visibility))
        object.__setattr__(self, "visibility", freeze_mapping(parsed_visibility.model_dump()))
        object.__setattr__(self, "trace_id", require_identifier(self.trace_id, "trace id"))
        object.__setattr__(self, "metadata", freeze_mapping(self.metadata))


@dataclass(frozen=True, slots=True)
class RuntimeBrainSnapshot:
    entries: tuple[RuntimeBrainEntry, ...]
    evidence: tuple[ExpertiseEvidence, ...]
    snapshot_id: str
    excluded_entry_ids: tuple[str, ...] = ()
    shadowed_entry_ids: tuple[str, ...] = ()
    conflict_resolutions: tuple[Mapping[str, Any], ...] = ()


__all__ = [
    "DomainRecord",
    "ExpertSlice",
    "RoutePlan",
    "RuntimeBrainEntry",
    "RuntimeBrainSnapshot",
    "SourceDocument",
]
