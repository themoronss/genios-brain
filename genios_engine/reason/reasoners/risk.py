from __future__ import annotations

from collections.abc import Mapping

from genios_engine.contracts.reasoning import (CandidateAdjustment, Finding, ReasonerResult,
                                               ReasonerSpec, ReasoningRequest, ResultStatus)

from .common import active_spec, basis_points, clamp_bp, divide_half_up, integer


class RiskReasoner:
    _descriptor = ReasonerSpec(reasoner_id="core.risk", version="1.0.0")

    @property
    def spec(self) -> ReasonerSpec:
        return self._descriptor

    def evaluate(self, request: ReasoningRequest, prior_results: Mapping[str, ReasonerResult]
                 ) -> ReasonerResult:
        spec = active_spec(request, self.spec.reasoner_id)
        temporal = prior_results.get(str(spec.config.get("temporal_reasoner") or "core.temporal"))
        relationship = prior_results.get(str(
            spec.config.get("relationship_reasoner") or "core.relationship"))
        drop = integer((temporal.metrics if temporal else {}).get("drop_bp", 0), "drop_bp")
        relationship_risk = integer((relationship.metrics if relationship else {}).get(
            "relationship_risk_bp", 0), "relationship_risk_bp")
        base = basis_points(spec.config.get("base_risk_bp", 1_000), "base_risk_bp")
        risk_bp = clamp_bp(base + divide_half_up(drop * 60 + relationship_risk * 40, 100))
        adjustments = []
        for play_id, reduction in dict(spec.config.get("play_risk_reduction_bp") or {}).items():
            adjustments.append(CandidateAdjustment(
                str(play_id), "risk", -basis_points(
                    reduction, f"{play_id}.risk_reduction_bp"),
                                                    "play_mitigates_detected_risk"))
        finding = Finding("risk.do_nothing", "risk", metrics={"risk_bp": risk_bp},
                          reason_codes=("deal_momentum_risk",))
        return ReasonerResult(self.spec.reasoner_id, self.spec.version, ResultStatus.COMPLETED,
                              metrics=finding.metrics, findings=(finding,),
                              adjustments=tuple(adjustments),
                              reason_codes=finding.reason_codes)
