from __future__ import annotations

from collections.abc import Mapping
from decimal import ROUND_HALF_UP, Decimal

from genios_engine.contracts.reasoning import (CandidateAdjustment, Finding, ReasonerResult,
                                               ReasonerSpec, ReasoningRequest, ResultStatus)

from .common import (active_spec, basis_points, clamp_bp, decimal, elapsed_hours, evidence_ids,
                     fact_record, fact_value, integer)

#: `derived.engagement` is a RATIO AGAINST THIS RELATIONSHIP'S OWN HISTORY, not a fraction of one.
#: `context/derived.py::_metrics` states the scale in its own words -- "halved has to mean halved
#: for THIS account" -- and caps it at 3.0, with 1.0 meaning "no history, read neutral". So the
#: readable band is 0.0 .. 3.0 and the honest reading of 1.0 is FULL engagement, not a tenth of a
#: basis point.
#:
#: `common.ratio_bp` cannot express that. It multiplies a value in 0..1 by 10,000 and passes
#: anything ABOVE 1 through as if it were already basis points, so an account engaging at 1.4x its
#: own baseline read as 1bp -- total collapse -- and at 3.0x, the hottest reading the writer can
#: produce, as 3bp. `drop_bp` is 10,000 minus that, so every warming relationship in the system
#: published a 10,000bp drop and, through the `urgency_bp` line below, a saturated ceiling urgency.
#: Measured on a 60-decision population seeded through the production path: engagement 3.0 on all
#: 60, `urgency_bp` 10,000 on 59 of them -- a constant wearing a score's clothes, and the second
#: half of the flat-urgency defect that `core.timeline`'s dead ladder was the first half of.
#:
#: The mapping below is the writer's scale read straight: ratio x 10,000, clamped at the top of
#: the band. Under 1.0 it is arithmetically identical to what `ratio_bp` already did, so every
#: cooling reading -- the ones the unit exists to catch, and the ones `max_engagement_bp` (5,000
#: = "halved") is calibrated against -- is unchanged to the basis point.
ENGAGEMENT_FULL = 10_000


def engagement_bp_from_ratio(value, label: str) -> int:
    """A `derived.engagement` ratio as basis points on its own declared scale."""
    amount = decimal(value, label)
    if amount < 0:
        raise ValueError(f"{label} must not be negative")
    return clamp_bp(int((amount * ENGAGEMENT_FULL).quantize(
        Decimal("1"), rounding=ROUND_HALF_UP)))


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
        # A record that DECLARES basis points is taken at its word; a bare number is the
        # writer's ratio and is read on the writer's scale. Two shapes, two readings, and the
        # declaration is what separates them -- never the magnitude of the number.
        if isinstance(raw, Mapping) and "value_bp" in raw:
            engagement_bp = basis_points(raw.get("value_bp"), engagement_field)
        else:
            engagement_bp = engagement_bp_from_ratio(
                fact_value(request, engagement_field), engagement_field)
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
        # Sorted, not insertion-ordered.  Adjustment order is inside this result's semantic hash,
        # and the manifest makes a round trip through JSON on its way to the audit store — which
        # re-sorts object keys.  Iterating in whatever order the mapping arrived in would make a
        # replayed run hash differently from the original while the request hash stayed identical,
        # reporting every persisted run as non-reproducible.
        for play_id, config in sorted(dict(spec.config.get("play_adjustments") or {}).items()):
            if not isinstance(config, Mapping):
                continue
            for component, delta in sorted(config.items()):
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
