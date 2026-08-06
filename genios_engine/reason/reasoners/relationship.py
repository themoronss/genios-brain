from __future__ import annotations

from collections.abc import Mapping

from genios_engine.contracts.reasoning import (CandidateAdjustment, Finding, ReasonerResult,
                                               ReasonerSpec, ReasoningRequest, ResultStatus)

from .common import active_spec, clamp_bp, evidence_ids, fact_value, integer


class RelationshipReasoner:
    _descriptor = ReasonerSpec(reasoner_id="core.relationship", version="1.0.0")

    @property
    def spec(self) -> ReasonerSpec:
        return self._descriptor

    def evaluate(self, request: ReasoningRequest, prior_results: Mapping[str, ReasonerResult]
                 ) -> ReasonerResult:
        del prior_results
        spec = active_spec(request, self.spec.reasoner_id)
        # Native deal reasoning anchors on the root deal. The explicit location preserves support
        # for capabilities that intentionally inspect a neighbouring deal without forcing callers
        # to duplicate root facts into the neighbour partition.
        status_field = str(spec.config.get("status_field")
                           or spec.config.get("neighbor_status_field") or "deal.status")
        location = str(spec.config.get("status_location") or
                       ("neighbor" if "neighbor_status_field" in spec.config else "root"))
        if location not in {"root", "neighbor"}:
            raise ValueError("status_location must be root or neighbor")
        expected = spec.config.get("status_value",
                                   spec.config.get("neighbor_status_value", "open"))
        actual = fact_value(request, status_field, neighbor=location == "neighbor")
        if actual is None:
            return ReasonerResult(self.spec.reasoner_id, self.spec.version,
                                  ResultStatus.INSUFFICIENT_CONTEXT,
                                  missing_fields=((f"neighbor:{status_field}"
                                                   if location == "neighbor" else status_field),),
                                  reason_codes=("relationship_anchor_missing",))
        matched = actual == expected
        count_field = str(spec.config.get("relationship_count_field") or "").strip()
        if count_field:
            count_value = fact_value(request, count_field)
            if count_value is None:
                return ReasonerResult(
                    self.spec.reasoner_id, self.spec.version,
                    ResultStatus.INSUFFICIENT_CONTEXT,
                    missing_fields=(count_field,),
                    reason_codes=("verified_relationship_count_missing",),
                )
            relationship_count = integer(count_value, "verified relationship count")
            if relationship_count < 0:
                raise ValueError("verified relationship count must be non-negative")
        else:
            relationship_count = request.context.edge_count
        target = max(1, integer(spec.config.get("target_relationships", 3),
                                "target_relationships"))
        coverage_bp = clamp_bp(relationship_count * 10_000 // target)
        concentration_risk_bp = 10_000 - coverage_bp
        adjustments = []
        if relationship_count < target:
            play_id = spec.config.get("multithread_play_id")
            if play_id:
                adjustments.extend((
                    CandidateAdjustment(str(play_id), "impact", concentration_risk_bp // 4,
                                        "relationship_concentration_risk"),
                    CandidateAdjustment(str(play_id), "success", concentration_risk_bp // 8,
                                        "relationship_concentration_risk"),
                ))
        ev = evidence_ids(request, status_field, count_field) if count_field \
            else evidence_ids(request, status_field)
        finding = Finding("relationship.coverage", "relationship", matched=matched,
                          metrics={"relationship_count": relationship_count,
                                   "coverage_bp": coverage_bp,
                                   "relationship_risk_bp": concentration_risk_bp},
                          evidence_ids=ev,
                          reason_codes=(("linked_open_deal",) if matched
                                        else ("linked_deal_not_open",)))
        return ReasonerResult(self.spec.reasoner_id, self.spec.version, ResultStatus.COMPLETED,
                              matched=matched, metrics=finding.metrics, findings=(finding,),
                              adjustments=tuple(adjustments), evidence_ids=ev,
                              reason_codes=finding.reason_codes)
