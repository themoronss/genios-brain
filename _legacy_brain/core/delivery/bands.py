"""Confidence bands — the customer-facing, qualitative view of confidence.

Per GENIOS_BRIEFING_CTO_AND_AGENT.md §5 Gate 1 / §8 Task 2:
    Until confidence is calibrated (ECE/Brier over ~50-100 real outcome pairs),
    uncalibrated numeric thresholds "fire randomly" and MUST NOT be presented to
    customers as if they were probabilities. Customer-facing surfaces show a BAND
    (high / medium / low); the raw float stays INTERNAL (DecisionRow.confidence_score,
    proactive_insights rows) so it's available for calibration later.

Band cutoffs reuse the routing thresholds so the band a customer sees lines up
with how the engine actually routed the decision:
    >= theta_act  (0.75) -> high
    >= theta_flag (0.45) -> medium
    else                 -> low
"""

from __future__ import annotations

from enum import StrEnum

from core.reflection.human_flag import DEFAULT_THETA_ACT, DEFAULT_THETA_FLAG


class ConfidenceBand(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


def to_band(
    score: float | None,
    *,
    theta_act: float = DEFAULT_THETA_ACT,
    theta_flag: float = DEFAULT_THETA_FLAG,
) -> ConfidenceBand:
    """Map a raw confidence float to its customer-facing qualitative band.

    None / unparseable scores fall through to LOW (never raises — a delivery
    surface must not crash on a missing confidence).
    """
    try:
        c = float(score) if score is not None else 0.0
    except (TypeError, ValueError):
        c = 0.0
    if c >= theta_act:
        return ConfidenceBand.HIGH
    if c >= theta_flag:
        return ConfidenceBand.MEDIUM
    return ConfidenceBand.LOW
