from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal

from genios_engine.contracts.reasoning import (Finding, ReasonerResult, ReasonerSpec,
                                               ReasoningRequest, ResultStatus)

from .common import (active_spec, basis_points, clamp_bp, divide_half_up, fact_record, integer,
                     ratio_bp)


class ConfidenceReasoner:
    _descriptor = ReasonerSpec(reasoner_id="core.confidence", version="1.0.0")

    @property
    def spec(self) -> ReasonerSpec:
        return self._descriptor

    def evaluate(self, request: ReasoningRequest, prior_results: Mapping[str, ReasonerResult]
                 ) -> ReasonerResult:
        spec = active_spec(request, self.spec.reasoner_id)
        source = str(spec.config.get("source_reasoner") or "")
        if source and source in prior_results and "confidence_bp" in prior_results[source].metrics:
            confidence_bp = basis_points(
                prior_results[source].metrics["confidence_bp"], "confidence_bp")
            metrics = {"confidence_bp": confidence_bp, "source": "legacy"}
        else:
            fields = tuple(spec.required_fields or request.capability.required_fields)
            present = [field for field in fields if field in request.context.facts]
            completeness_bp = divide_half_up(len(present) * 10_000, len(fields)) if fields else 10_000
            confidences = []
            corroborations = []
            for field in present:
                record = fact_record(request, field)
                if isinstance(record, Mapping):
                    if "confidence_bp" in record:
                        confidences.append(basis_points(
                            record["confidence_bp"], f"{field}.confidence_bp"))
                    elif "confidence" in record:
                        confidences.append(ratio_bp(record["confidence"], f"{field}.confidence"))
                    groups = integer(record.get("src_count", 1), f"{field}.src_count")
                    corroborations.append(10_000 if groups >= 3 else (8_500 if groups == 2 else 6_000))
            source_bp = divide_half_up(sum(confidences), len(confidences)) if confidences else 5_000
            corroboration_bp = (divide_half_up(sum(corroborations), len(corroborations))
                                if corroborations else 5_000)
            independent_groups = {
                # Missing independence metadata is one unknown group, not proof that every field
                # came from an independent source.
                item.independence_group or "unattributed"
                for item in request.context.evidence
            }
            evidence_coverage_bp = min(10_000, len(independent_groups) * 2_500)
            confidence_bp = clamp_bp(divide_half_up(
                source_bp * 40 + completeness_bp * 30 + corroboration_bp * 20
                + evidence_coverage_bp * 10, 100))
            metrics = {"confidence_bp": confidence_bp, "source_quality_bp": source_bp,
                       "completeness_bp": completeness_bp,
                       "corroboration_bp": corroboration_bp,
                       "evidence_coverage_bp": evidence_coverage_bp,
                       "independent_evidence_groups": len(independent_groups)}
        finding = Finding("confidence.decomposition", "confidence", metrics=metrics,
                          reason_codes=("confidence_computed",))
        return ReasonerResult(self.spec.reasoner_id, self.spec.version, ResultStatus.COMPLETED,
                              metrics=metrics, findings=(finding,),
                              reason_codes=finding.reason_codes)
