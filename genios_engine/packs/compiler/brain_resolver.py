"""Pin the Expert and three tenant brains into one reproducible snapshot."""

from __future__ import annotations

from datetime import datetime

# ⛔ THE ADMITTED OBJECT, NOT THE CANDIDATE. `domain_shadow.py:881` passes
# `publication.situation`, which `PublicationResult` types as this class — the compiler
# never sees an unadmitted one. This import said `contracts.domain_expertise` until L2-1,
# naming a 16-field candidate while receiving a 28-field admitted object; it survived
# because the two spelled the same and v2 carries v1-named compatibility properties.
from genios_engine.contracts.situation import BusinessSituationObject
from genios_engine.platform.canonical import stable_id

from .authoring import ExpertBrainCatalog
from .knowledge_retriever import RetrievedKnowledge
from .models import ExpertSlice, RoutePlan, RuntimeBrainSnapshot, SourceDocument
from .object_resolver import ResolvedObjects
from .runtime_brains import RuntimeBrains


class BrainResolver:
    def __init__(self, catalog: ExpertBrainCatalog, runtime_brains: RuntimeBrains) -> None:
        self.catalog = catalog
        self.runtime_brains = runtime_brains

    def resolve(self, *, situation: BusinessSituationObject, plan: RoutePlan,
                objects: ResolvedObjects, knowledge: RetrievedKnowledge,
                eval_time: datetime | None = None) \
            -> tuple[ExpertSlice, RuntimeBrainSnapshot, str]:
        situation_sources = tuple(
            self.catalog.domain(domain_id).situations[situation_id]
            for domain_id in plan.domain_ids
            for situation_id in plan.situation_ids
            if situation_id in self.catalog.domain(domain_id).situations)
        domain_sources = tuple(self.catalog.domain(domain_id).domain
                               for domain_id in plan.domain_ids)
        sources = tuple(sorted({
            (item.kind, item.id, item.content_hash): item
            for item in (
                *domain_sources,
                *situation_sources,
                *knowledge.capabilities,
                *knowledge.source_manifests,
                *objects.documents,
                *knowledge.artifacts,
                *knowledge.variants,
            )
        }.values(), key=lambda item: (item.kind, item.id, item.content_hash)))
        expert_snapshot_id = stable_id("expert_brain", {
            "sources": [{
                "kind": item.kind,
                "id": item.id,
                "version": item.version,
                "content_hash": item.content_hash,
            } for item in sources]
        })

        total = (len(plan.required_object_ids) + len(plan.optional_object_ids)
                 + len(knowledge.artifacts) + len(knowledge.missing_artifacts))
        present = len(objects.documents) + len(knowledge.artifacts)
        coverage_bp = 10_000 if total == 0 else present * 10_000 // total
        expert = ExpertSlice(
            capabilities=knowledge.capabilities,
            objects=objects.documents,
            artifacts=knowledge.artifacts,
            variants=knowledge.variants,
            sources=sources,
            missing_optional=objects.missing_optional,
            missing_artifacts=knowledge.missing_artifacts,
            coverage_bp=min(objects.coverage_bp, coverage_bp),
            snapshot_id=expert_snapshot_id,
            unresolved_variants=tuple(getattr(knowledge, "unresolved_variants", ()) or ()),
        )
        runtime = self.runtime_brains.snapshot(
            situation=situation,
            plan=plan,
            object_ids=tuple(item.id for item in objects.documents),
            # The sweep's frozen clock, threaded rather than re-read. An Adaptive lease has a TTL
            # and a package must be reproducible; those two facts together mean the expiry has to
            # be judged against the time the decision was taken, not the time anyone replays it.
            eval_time=eval_time,
        )
        combined = stable_id("brains", {
            "expert": expert.snapshot_id,
            "runtime": runtime.snapshot_id,
        })
        return expert, runtime, combined


__all__ = ["BrainResolver"]
