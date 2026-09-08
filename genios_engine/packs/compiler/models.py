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


def entity_fields(entity: Any) -> Mapping[str, Any]:
    """One situation entity as a plain mapping, whatever shape the caller was handed.

    TWO SHAPES REACH THE COMPILER and only one of them ever did. The v1 lane put free mappings on
    `BusinessSituationObject.entities`; L2's admission gate now hands `shadow_compile` the
    UPGRADED strict object, whose entities are frozen `SituationEntity` models — attributes, no
    `.get`. Every dict read on one raises AttributeError inside `DomainCompiler.compile`, which
    `shadow_compile` catches PER SITUATION: so an admitted situation counted as `error`, the
    compiled lane produced nothing at all, and the sweep still reported a clean `admission_admit`.

    Resolved ONCE, here, rather than at each reader: two call sites coercing the same object their
    own way is how one idea becomes two vocabularies that disagree later. A mapping is returned
    unchanged so the v1 lane keeps its exact keys, including the ones the model does not name
    (`entity_id`, `object_type`, `kind`).
    """
    if isinstance(entity, Mapping):
        return entity
    dump = getattr(entity, "model_dump", None)
    if callable(dump):
        return dump()
    return {}


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
    #: L3.1-U2 · the generated registry's OPTIONAL `patterns:` section — L2.6 `pattern_id` to the
    #: same route shape `routes` carries. Empty for every domain today, which is exactly the
    #: migration property doc 01 asks for: the anchor-type route below keeps working, unchanged,
    #: until a tenant's patterns are activated and the registry names them.
    pattern_routes: Mapping[str, Any]
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
    #: True only when EVERY routed capability passed the admission gate (stable + approved by a
    #: named reviewer + accepted hash matching the routed bytes). A shadow compile may carry
    #: unadmitted content; this flag is what keeps that content forever non-prescriptive
    #: downstream (deliver's abstention gate reads the package review_state).
    admitted: bool = True
    admission_gaps: tuple[str, ...] = ()
    #: Routed capabilities that are admitted and say nothing — no outcomes, kpis, handoffs or
    #: failure modes, only a name, a sentence and a question. Separate from `admission_gaps`
    #: because thinness is not an authority failure: this must be countable without deciding
    #: whether the package may instruct.
    hollow_capability_ids: tuple[str, ...] = ()
    #: The authored card copy for this route — `artifact_kind`, `render_hint` and the
    #: deterministic `fallback` — lifted from the winning situation file.
    #:
    #: It travels on the PLAN rather than being looked up at delivery time because the copy is
    #: part of the expertise: it is what the situation says a reader must be told, it is admitted
    #: with the rest of the file, and hashing it into the manifest means changing the wording
    #: mints a new capability version instead of silently altering what already-audited cards
    #: claimed. `None` means the situation authored none, and the delivery layer falls back to
    #: the tenant pack's template exactly as the legacy lane does.
    render: Mapping[str, Any] | None = None
    #: Which situation the copy came from — a package can match several, and "whose words are
    #: these" must be answerable from the package alone.
    render_situation_id: str | None = None
    #: The authored `priority_bp` of the highest-priority situation on this route.
    #:
    #: It travels for the same reason `render` does — it is authored expertise, not a runtime
    #: reading. Until it did, the corpus's 30 distinct priorities (3000–9600 across 48 situations)
    #: were used to SORT the route and then discarded, so the Decision Maker saw no declared
    #: priority, fell back to a neutral 5000, and every compiled signal scored
    #: (5000 + 50) / 100 = 50. On the design partner's org that was 193 of 223 signals and 104 of
    #: 115 cards at exactly the same score, in one urgency band — a ranked product that had never
    #: ranked anything.
    priority_bp: int | None = None
    #: Which situation the priority came from, for the same reason `render_situation_id` exists.
    priority_situation_id: str | None = None
    #: L3.1-U2 · the L2.6 `pattern_id` that selected this route, or None when the anchor-derived
    #: situation type did. A route is a claim about which expertise this situation gets, and a
    #: claim with no receipt cannot be audited — this is the receipt, and it reaches the package's
    #: metadata whenever it is not None.
    #:
    #: PRECISELY: set when AT LEAST ONE domain's route was chosen by the pattern rather than by
    #: the anchor type. A situation may name several domains, and a pattern route in one of them
    #: does not stop another from routing on its type; `situation_ids` is what says which
    #: situations actually came back, and reading this field as "every situation here came from
    #: the pattern" would be an overclaim in that case.
    pattern_route_id: str | None = None
    #: WHY the pattern did not route, when a fire was present and did not. Three values and no
    #: fourth: `routed` (an activated fire matched an authored pattern route), `shadow` (a fire
    #: matched but the tenant has not activated the pattern, so it may annotate and not route —
    #: `context/patterns/store.py`'s own migration rule), `unregistered` (an activated fire whose
    #: pattern_id no registry names yet). None means no fire reached this compile at all, which
    #: is every tenant until X6 lands for them.
    pattern_route_state: str | None = None


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
    "entity_fields",
    "DomainRecord",
    "ExpertSlice",
    "RoutePlan",
    "RuntimeBrainEntry",
    "RuntimeBrainSnapshot",
    "SourceDocument",
]
