"""Attach immutable receipts to every source that influenced an expertise package."""

from __future__ import annotations

from genios_engine.contracts.domain_expertise import (
    BrainKind,
    BusinessSituationObject,
    ExpertiseEvidence,
)

from .models import ExpertSlice, RuntimeBrainSnapshot


class EvidenceAggregator:
    def aggregate(self, *, situation: BusinessSituationObject, expert: ExpertSlice,
                  runtime: RuntimeBrainSnapshot) -> tuple[ExpertiseEvidence, ...]:
        authored = tuple(ExpertiseEvidence(
            brain=BrainKind.EXPERT,
            source_ref=f"expert:{source.kind}:{source.id}",
            source_version=source.version,
            content_hash=source.content_hash,
            # This measures byte/source integrity. Claim-level confidence remains on the
            # situation, inference pattern, or learned entry that owns it.
            confidence_bp=10_000,
            visibility=situation.visibility,
            metadata={
                "path": source.relative_path,
                "confidence_semantics": "source_integrity",
            },
        ) for source in expert.sources)
        return tuple(sorted((*authored, *runtime.evidence), key=lambda item: (
            item.brain.value, item.source_ref, item.content_hash)))


__all__ = ["EvidenceAggregator"]
