"""Retrieve only the authored artifacts and business-model overlays a route names."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from genios_engine.contracts.domain_expertise import BusinessSituationObject

from .authoring import ExpertBrainCatalog
from .errors import AuthoringIntegrityError
from .models import RoutePlan, SourceDocument

_KNOWLEDGE_KEYS = ("playbooks", "heuristics", "mental_models", "rules",
                   "decision_frameworks")


@dataclass(frozen=True, slots=True)
class RetrievedKnowledge:
    capabilities: tuple[SourceDocument, ...]
    artifacts: tuple[SourceDocument, ...]
    variants: tuple[SourceDocument, ...]
    source_manifests: tuple[SourceDocument, ...]
    missing_artifacts: tuple[str, ...]


def _values(raw) -> tuple[str, ...]:
    if not raw:
        return ()
    if isinstance(raw, str):
        return (raw,)
    return tuple(str(value) for value in raw)


class KnowledgeRetriever:
    def __init__(self, catalog: ExpertBrainCatalog) -> None:
        self.catalog = catalog

    @staticmethod
    def _refs(manifest: dict) -> set[str]:
        refs: set[str] = set()
        for key in _KNOWLEDGE_KEYS:
            block = manifest.get(key) or {}
            refs.update(block.get("core") or ())
            refs.update(block.get("scoped") or ())
        if manifest.get("primary_framework"):
            refs.add(manifest["primary_framework"])
        return refs

    def _resolve_variants(self, plan: RoutePlan, situation: BusinessSituationObject) \
            -> tuple[SourceDocument, ...]:
        metadata = situation.metadata
        requested = set(_values(metadata.get("model_ids") or metadata.get("business_models")
                                or metadata.get("models")))
        requested.update(_values(metadata.get("offering_ids") or metadata.get("offerings")))
        if not requested:
            return ()
        resolved: list[SourceDocument] = []
        missing: list[str] = []
        for request in sorted(requested):
            matches: list[SourceDocument] = []
            for domain_id in plan.domain_ids:
                for identifier, document in self.catalog.domain(domain_id).variants.items():
                    identity = document.content.get("identity") or {}
                    aliases = {
                        identifier,
                        identifier.rsplit(".", 1)[-1],
                        str(identity.get("name") or "").strip().lower().replace(" ", "_"),
                    }
                    if request in aliases:
                        matches.append(document)
            if len(matches) > 1:
                raise AuthoringIntegrityError(
                    f"business model/offering hint {request!r} is ambiguous; use the full id")
            if not matches:
                missing.append(request)
            else:
                resolved.append(matches[0])
        if missing:
            raise AuthoringIntegrityError(
                f"requested business model/offering definitions are missing: {missing}")
        return tuple(sorted(resolved, key=lambda item: item.id))

    def retrieve(self, plan: RoutePlan, situation: BusinessSituationObject) \
            -> RetrievedKnowledge:
        capabilities: list[SourceDocument] = []
        manifests: list[SourceDocument] = []
        refs: set[str] = set()
        for capability_id in plan.capability_ids:
            matches = [(domain_id, self.catalog.domain(domain_id).capabilities[capability_id])
                       for domain_id in plan.domain_ids
                       if capability_id in self.catalog.domain(domain_id).capabilities]
            if len(matches) != 1:
                raise AuthoringIntegrityError(
                    f"capability {capability_id!r} resolved {len(matches)} times")
            domain_id, capability = matches[0]
            domain = self.catalog.domain(domain_id)
            capabilities.append(capability)
            object_manifest = domain.object_manifests[capability_id]
            knowledge_manifest = domain.knowledge_manifests[capability_id]
            manifests.extend((object_manifest, knowledge_manifest))
            refs.update(self._refs(dict(knowledge_manifest.content)))

        artifacts: list[SourceDocument] = []
        missing: list[str] = []
        for artifact_id in sorted(refs):
            matches = [self.catalog.domain(domain_id).artifacts[artifact_id]
                       for domain_id in plan.domain_ids
                       if artifact_id in self.catalog.domain(domain_id).artifacts]
            if len(matches) > 1:
                raise AuthoringIntegrityError(
                    f"artifact {artifact_id!r} resolves in more than one domain")
            if not matches:
                missing.append(artifact_id)
            else:
                artifacts.append(matches[0])

        return RetrievedKnowledge(
            capabilities=tuple(sorted(capabilities, key=lambda item: item.id)),
            artifacts=tuple(sorted(artifacts, key=lambda item: item.id)),
            variants=self._resolve_variants(plan, situation),
            source_manifests=tuple(sorted(
                manifests, key=lambda item: (item.id, item.kind))),
            missing_artifacts=tuple(sorted(missing)),
        )


__all__ = ["KnowledgeRetriever", "RetrievedKnowledge"]
