"""Merge the four brain slices into the one Layer 3 boundary object."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from genios_engine.contracts.domain_expertise import (
    BrainKind,
    BusinessSituationObject,
    ExpertiseEvidence,
    ExpertisePackage,
    SituationContextSlice,
    expertise_id,
)

from .context_adapter import ContextAdapter
from .models import ExpertSlice, RoutePlan, RuntimeBrainEntry, RuntimeBrainSnapshot

COMPILER_VERSION = "domain-compiler.v1"


def _authored(document, *, bindings: Mapping[str, tuple[str, ...]] | None = None) \
        -> dict[str, Any]:
    result = {
        "id": document.id,
        "kind": document.kind,
        "version": document.version,
        "definition": document.content,
    }
    if bindings is not None:
        result["entity_bindings"] = bindings.get(document.id, ())
    return result


def _runtime(entry: RuntimeBrainEntry) -> dict[str, Any]:
    return {
        "entry_id": entry.entry_id,
        "subject_key": entry.subject_key,
        "version": entry.version,
        "value": entry.value,
        "confidence_bp": entry.confidence_bp,
        "learning_id": entry.learning_id,
        "effective_at": entry.effective_at,
        "trace_id": entry.trace_id,
    }


class ExpertiseBuilder:
    def build(self, *, situation: BusinessSituationObject, plan: RoutePlan,
              expert: ExpertSlice, runtime: RuntimeBrainSnapshot,
              brain_snapshot_id: str, evidence: tuple[ExpertiseEvidence, ...],
              context: SituationContextSlice | None = None) \
            -> ExpertisePackage:
        bindings = ContextAdapter(situation, context).bind_objects(expert.objects)
        by_brain: dict[BrainKind, list[RuntimeBrainEntry]] = {
            BrainKind.ORGANIZATION: [],
            BrainKind.BEHAVIOR: [],
            BrainKind.ADAPTIVE: [],
        }
        for entry in runtime.entries:
            by_brain[entry.brain].append(entry)

        capabilities = tuple(_authored(item) for item in expert.capabilities)
        objects = tuple(_authored(item, bindings=bindings) for item in expert.objects)
        expert_rules = tuple(_authored(item) for item in (
            *expert.artifacts, *expert.variants))
        organization = tuple(_runtime(item) for item in by_brain[BrainKind.ORGANIZATION])
        behavior = tuple(_runtime(item) for item in by_brain[BrainKind.BEHAVIOR])
        adaptive = tuple(_runtime(item) for item in by_brain[BrainKind.ADAPTIVE])
        confidence_bp = min(situation.confidence_bp, expert.coverage_bp)
        metadata = {
            "compiler_version": COMPILER_VERSION,
            "situation_type": situation.type,
            "situation_hash": situation.semantic_hash,
            "domain_ids": plan.domain_ids,
            "matched_situation_ids": plan.situation_ids,
            "required_object_ids": plan.required_object_ids,
            "optional_object_ids": plan.optional_object_ids,
            "never_object_ids": plan.never_object_ids,
            "missing_optional_object_ids": expert.missing_optional,
            "missing_artifact_ids": expert.missing_artifacts,
            "unresolved_route_predicates": plan.unresolved_predicates,
            "skipped_capability_ids": plan.skipped_capability_ids,
            # What the abstention gate downstream reads. `accepted` ONLY when every routed
            # capability cleared admission (stable + approved by a named reviewer + accepted
            # hash matching the routed bytes); a measurement compile over drafts says `draft`
            # here and everything built from it stays non-prescriptive at the card layer.
            "review_state": "accepted" if plan.admitted else "draft",
            "admission_gaps": plan.admission_gaps,
            # How much of this answer came from placeholders. Deliberately NOT folded into
            # `review_state`: a thin capability is a content gap, an unadmitted one is an
            # authority gap, and one number cannot mean both.
            "hollow_capability_ids": plan.hollow_capability_ids,
            "excluded_runtime_entry_ids": runtime.excluded_entry_ids,
            "shadowed_runtime_entry_ids": runtime.shadowed_entry_ids,
            "runtime_conflict_resolutions": runtime.conflict_resolutions,
            "object_coverage_bp": expert.coverage_bp,
            "importance_bp": situation.importance_bp,
            "context_bindings": bindings,
            "expert_snapshot_id": expert.snapshot_id,
            "runtime_snapshot_id": runtime.snapshot_id,
            "context_slice_id": context.id if context is not None else None,
            "context_slice_hash": context.semantic_hash if context is not None else None,
            "context_graph_version": context.graph_version if context is not None else None,
            "context_selector_version": context.selector_version if context is not None else None,
            # The authored card copy, and which situation it came from. Carried on the package so
            # it is hashed into the manifest with the rest of the knowledge: rewording a headline
            # mints a new capability version rather than silently changing what an already-audited
            # card claimed.
            "render": plan.render,
            "render_situation_id": plan.render_situation_id,
            # The authored priority, carried for the same reason and hashed the same way. It is a
            # property of the SITUATION, not of this evaluation, so it is stable across compiles
            # and does not churn the content address the way `trace_id` did.
            "authored_priority_bp": plan.priority_bp,
            "priority_situation_id": plan.priority_situation_id,
        }
        body = {
            "org_id": situation.org_id,
            "schema_version": "expertise-package.v1",
            "trace_id": situation.trace_id,
            "visibility": situation.visibility,
            "situation_id": situation.id,
            "brain_snapshot_id": brain_snapshot_id,
            "capabilities": capabilities,
            "objects": objects,
            "expert_rules": expert_rules,
            "organization_rules": organization,
            "behavior_patterns": behavior,
            "adaptive_preferences": adaptive,
            "confidence_bp": confidence_bp,
            "evidence": evidence,
            "metadata": metadata,
        }
        return ExpertisePackage(id=expertise_id(body), **body)


__all__ = ["COMPILER_VERSION", "ExpertiseBuilder"]
