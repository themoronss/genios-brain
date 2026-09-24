"""Attach immutable receipts to every source that influenced an expertise package."""

from __future__ import annotations

from genios_engine.contracts.domain_expertise import (
    BrainKind,
    ExpertiseEvidence,
)
# ⛔ THE ADMITTED OBJECT, NOT THE CANDIDATE. `domain_shadow.py:881` passes
# `publication.situation`, which `PublicationResult` types as this class — the compiler
# never sees an unadmitted one. This import said `contracts.domain_expertise` until L2-1,
# naming a 16-field candidate while receiving a 28-field admitted object; it survived
# because the two spelled the same and v2 carries v1-named compatibility properties.
from genios_engine.contracts.situation import BusinessSituationObject

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
