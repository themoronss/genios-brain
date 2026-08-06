from __future__ import annotations

from collections.abc import Mapping

from genios_engine.contracts.reasoning import (CandidateAdjustment, Finding, ReasonerResult,
                                               ReasonerSpec, ReasoningRequest, ResultStatus)

from .common import (active_spec, basis_points, clamp_bp, elapsed_hours, evidence_ids, fact_record,
                     fact_value, integer, ratio_bp)


class TemporalReasoner:
    _descriptor = ReasonerSpec(reasoner_id="core.temporal", version="1.0.0")

    @property
    def spec(self) -> ReasonerSpec:
        return self._descriptor

    def evaluate(self, request: ReasoningRequest, prior_results: Mapping[str, ReasonerResult]
                 ) -> ReasonerResult:
        del prior_results
        spec = active_spec(request, self.spec.reasoner_id)
        engagement_field = str(spec.config.get("engagement_field") or "derived.engagement")
        timestamp_field = str(spec.config.get("timestamp_field") or "thread.last_inbound")
        raw = fact_record(request, engagement_field)
        if raw is None:
            return ReasonerResult(self.spec.reasoner_id, self.spec.version,
                                  ResultStatus.INSUFFICIENT_CONTEXT,
                                  missing_fields=(engagement_field,),
                                  reason_codes=("temporal_engagement_missing",))
        value = raw.get("value_bp") if isinstance(raw, Mapping) and "value_bp" in raw \
            else fact_value(request, engagement_field)
        engagement_bp = ratio_bp(value, engagement_field)
        maximum = basis_points(spec.config.get("max_engagement_bp", 5_000),
                               "max_engagement_bp")
        matched = engagement_bp <= maximum
        hours = 0
        timestamp_missing = timestamp_field not in request.context.facts
        if not timestamp_missing:
            try:
                hours = elapsed_hours(request, timestamp_field)
            except ValueError:
                return ReasonerResult(self.spec.reasoner_id, self.spec.version,
                                      ResultStatus.INSUFFICIENT_CONTEXT,
                                      missing_fields=(timestamp_field,),
                                      reason_codes=("temporal_timestamp_invalid",))
        drop_bp = clamp_bp(10_000 - engagement_bp)
        urgency_bp = clamp_bp(drop_bp + min(hours, 168) * 20)
        fields = (engagement_field,) + (() if timestamp_missing else (timestamp_field,))
        ev = evidence_ids(request, *fields)
        adjustments = []
        for play_id, config in dict(spec.config.get("play_adjustments") or {}).items():
            if not isinstance(config, Mapping):
                continue
            for component, delta in config.items():
                adjustments.append(CandidateAdjustment(
                    play_id=str(play_id), component=str(component),
                    delta_bp=integer(delta, f"play_adjustments.{play_id}.{component}"),
                    reason_code="temporal_cooling_adjustment", evidence_ids=ev))
        finding = Finding("temporal.cooling", "temporal", matched=matched,
                          metrics={"engagement_bp": engagement_bp, "drop_bp": drop_bp,
                                   "elapsed_hours": hours, "urgency_bp": urgency_bp},
                          evidence_ids=ev,
                          reason_codes=(("engagement_below_threshold",) if matched
                                        else ("engagement_healthy",)))
        return ReasonerResult(self.spec.reasoner_id, self.spec.version, ResultStatus.COMPLETED,
                              matched=matched, metrics=finding.metrics, findings=(finding,),
                              adjustments=tuple(adjustments), evidence_ids=ev,
                              reason_codes=finding.reason_codes)
