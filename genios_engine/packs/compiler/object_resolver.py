"""Capability plan -> exact authored object slice."""

from __future__ import annotations

from dataclasses import dataclass

from genios_engine.contracts.validators import require_bp

from .authoring import ExpertBrainCatalog
from .errors import RequiredKnowledgeMissing
from .models import RoutePlan, SourceDocument


@dataclass(frozen=True, slots=True)
class ResolvedObjects:
    documents: tuple[SourceDocument, ...]
    missing_optional: tuple[str, ...]
    coverage_bp: int


class ObjectResolver:
    def __init__(self, catalog: ExpertBrainCatalog) -> None:
        self.catalog = catalog

    def _find(self, object_id: str, domains: tuple[str, ...]) -> SourceDocument | None:
        found = [self.catalog.domain(domain_id).objects[object_id]
                 for domain_id in domains
                 if object_id in self.catalog.domain(domain_id).objects]
        if len(found) > 1:
            raise RequiredKnowledgeMissing(
                f"object {object_id!r} resolves in more than one domain")
        return found[0] if found else None

    def resolve(self, plan: RoutePlan) -> ResolvedObjects:
        documents: list[SourceDocument] = []
        missing_required: list[str] = []
        missing_optional: list[str] = []
        for object_id in plan.required_object_ids:
            document = self._find(object_id, plan.domain_ids)
            if document is None:
                missing_required.append(object_id)
            else:
                documents.append(document)
        if missing_required:
            raise RequiredKnowledgeMissing(
                f"required authored objects are missing: {sorted(missing_required)}")
        for object_id in plan.optional_object_ids:
            document = self._find(object_id, plan.domain_ids)
            if document is None:
                missing_optional.append(object_id)
            else:
                documents.append(document)

        denominator = len(plan.required_object_ids) + len(plan.optional_object_ids)
        coverage_bp = 10_000 if denominator == 0 else (
            len(documents) * 10_000 // denominator)
        require_bp(coverage_bp, "object coverage_bp")
        return ResolvedObjects(
            documents=tuple(sorted(documents, key=lambda item: item.id)),
            missing_optional=tuple(sorted(missing_optional)),
            coverage_bp=coverage_bp,
        )


__all__ = ["ObjectResolver", "ResolvedObjects"]
