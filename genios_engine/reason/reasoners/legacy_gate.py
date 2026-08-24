"""Candidate gate preserving legacy score/confidence thresholds inside Layer 4."""

from __future__ import annotations

from collections.abc import Mapping

from genios_engine.contracts.reasoning import (CandidateCheck, CheckOutcome, ReasonerResult,
                                               ReasonerSpec, ReasoningRequest, ResultStatus)

from .common import active_spec, integer


class LegacyScoreGateReasoner:
    _descriptor = ReasonerSpec(reasoner_id="legacy.score_gate", version="1.0.0")

    @property
    def spec(self) -> ReasonerSpec:
        return self._descriptor

    def evaluate(self, request: ReasoningRequest, prior_results: Mapping[str, ReasonerResult]
                 ) -> ReasonerResult:
        spec = active_spec(request, self.spec.reasoner_id)
        source = prior_results.get("legacy.rule")
        if source is None:
            raise ValueError("legacy.score_gate requires legacy.rule")
        score = integer(source.metrics.get("legacy_score", 0), "legacy_score")
        confidence_bp = integer(source.metrics.get("confidence_bp", 0), "confidence_bp")
        score_min = integer(spec.config.get("score_min", 55), "score_min")
        confidence_min = integer(spec.config.get("confidence_min", 60), "confidence_min")
        if not 0 <= score_min <= 100 or not 0 <= confidence_min <= 100:
            raise ValueError("legacy gate thresholds must be between 0 and 100")
        passed = score >= score_min and confidence_bp >= confidence_min * 100
        checks = tuple(CandidateCheck(
            play.play_id,
            "precondition",
            CheckOutcome.PASS if passed else CheckOutcome.ELIMINATE,
            "legacy_score_gate_pass" if passed else "legacy_score_gate_failed",
            self.spec.reasoner_id,
            self.spec.version,
            detail={"score": score, "score_min": score_min,
                    "confidence_bp": confidence_bp,
                    "confidence_min_bp": confidence_min * 100},
        ) for play in request.capability.plays)
        return ReasonerResult(
            self.spec.reasoner_id,
            self.spec.version,
            ResultStatus.COMPLETED,
            metrics={"score": score, "score_min": score_min,
                     "confidence_bp": confidence_bp,
                     "confidence_min_bp": confidence_min * 100},
            checks=checks,
            reason_codes=(("legacy_score_gate_pass",) if passed
                          else ("legacy_score_gate_failed",)),
        )


__all__ = ["LegacyScoreGateReasoner"]
