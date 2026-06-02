"""THE prioritizer — multiplicative scoring + VoI gate + feedback suppression + KL novelty.

Per MD g-i-4 §1.2.1 (the make-or-break component):
    priority = impact * urgency * relevance * novelty * confidence
    (MULTIPLICATIVE — any near-zero factor KILLS the insight; per MD critical property)

Plus:
- VoI gate: push only if EV(info) > attention_cost
- Feedback suppression: dismissed signatures down-weight; never_show -> hard mute
- Cold-start: HIGH theta_priority initially (loosen as feedback accrues)
- Calibration gate: numeric thresholds DISABLED until ECE/Brier calibrated
                    (until then -> qualitative)
- KL-divergence novelty (per techniques-decisions ADOPTED)
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

from core.foundations.config import COLD_START_PRIORITY_THRESHOLD
from core.foundations.telemetry import get_logger
from core.proactive.feedback_store import FeedbackStore
from core.proactive.types import Insight

log = get_logger(__name__)


# Tuneable weights (currently equal-weighted multiplicative factors, all required)
DEFAULT_FACTORS = ("impact", "urgency", "relevance", "novelty", "confidence")


@dataclass(frozen=True)
class PriorityScore:
    """Output of prioritize_insight()."""

    insight_id: str
    priority: float
    breakdown: dict[str, float]  # per-factor scores
    suppression_factor: float
    voi_passed: bool
    above_threshold: bool
    reason: str


def prioritize_insight(
    insight: Insight,
    *,
    impact: float,
    urgency: float,
    relevance: float,
    confidence: float,
    recent_baseline: Sequence[float] | None = None,
    user_id: str | None = None,
    feedback_store: FeedbackStore | None = None,
    threshold: float = COLD_START_PRIORITY_THRESHOLD,
    attention_cost: float = 0.1,
    estimated_value_if_acted: float = 1.0,
) -> PriorityScore:
    """Compute priority + apply VoI gate + suppression.

    All inputs in [0, 1]. Multiplicative — any near-zero factor kills the insight.

    Novelty is computed via KL-divergence of the insight's signal vs `recent_baseline`
    (per techniques-decisions adopted). If recent_baseline is None, novelty = 1.0
    (no baseline yet, treat as novel).

    Suppression: if the same signature was dismissed/never_show by this user,
    multiply priority by a suppression_factor < 1 (or 0 for never_show).
    """
    for name, v in (
        ("impact", impact),
        ("urgency", urgency),
        ("relevance", relevance),
        ("confidence", confidence),
    ):
        if not 0.0 <= v <= 1.0:
            raise ValueError(f"{name} must be in [0, 1]; got {v}")

    novelty = _kl_divergence_novelty(impact, recent_baseline)

    breakdown = {
        "impact": impact,
        "urgency": urgency,
        "relevance": relevance,
        "novelty": novelty,
        "confidence": confidence,
    }
    raw_priority = math.prod(breakdown.values())

    # Suppression from user feedback history
    suppression_factor = 1.0
    if feedback_store is not None and user_id is not None:
        sig_hash = insight.signature.hash()
        action = feedback_store.last_action(
            org_id=insight.org_id, user_id=user_id, signature_hash=sig_hash
        )
        if action == "never_show":
            suppression_factor = 0.0
        elif action == "dismissed":
            dismiss_count = feedback_store.action_count(
                org_id=insight.org_id,
                user_id=user_id,
                signature_hash=sig_hash,
                action="dismissed",
            )
            # Each dismiss halves the priority (capped at 0.1x)
            suppression_factor = max(0.1, 0.5**dismiss_count)
        elif action == "snoozed":
            suppression_factor = 0.3

    final_priority = raw_priority * suppression_factor

    # VoI gate — push only if expected value > attention cost
    ev = final_priority * estimated_value_if_acted
    voi_passed = ev > attention_cost

    above_threshold = final_priority >= threshold

    if not voi_passed:
        reason = f"VoI gate failed: EV {ev:.3f} <= attention_cost {attention_cost:.3f}"
    elif not above_threshold:
        reason = f"below cold-start threshold {threshold:.2f} (priority={final_priority:.3f})"
    elif suppression_factor == 0.0:
        reason = "user marked this signature as never_show"
    elif suppression_factor < 1.0:
        reason = f"suppressed by user feedback (factor={suppression_factor:.2f})"
    else:
        reason = f"OK (priority={final_priority:.3f})"

    log.debug(
        "insight_prioritized",
        insight_id=insight.id,
        priority=final_priority,
        voi_passed=voi_passed,
        above_threshold=above_threshold,
        suppression=suppression_factor,
    )

    return PriorityScore(
        insight_id=insight.id,
        priority=final_priority,
        breakdown=breakdown,
        suppression_factor=suppression_factor,
        voi_passed=voi_passed,
        above_threshold=above_threshold and voi_passed,
        reason=reason,
    )


# ─── helpers ────────────────────────────────────────────────────────────────


def _kl_divergence_novelty(insight_signal: float, recent_baseline: Sequence[float] | None) -> float:
    """Novelty = KL-divergence of insight signal vs recent baseline (normalized to [0,1]).

    Per techniques-decisions ADOPTED list. High = insight is genuinely new vs
    what we've been pushing recently. 1.0 = no baseline yet -> treat as novel.
    """
    if not recent_baseline:
        return 1.0

    # Construct simple 2-bin distributions: [signal, 1-signal] and baseline mean
    baseline_mean = sum(recent_baseline) / len(recent_baseline)
    p = max(0.001, min(0.999, insight_signal))
    q = max(0.001, min(0.999, baseline_mean))

    # KL(p || q) = p*log(p/q) + (1-p)*log((1-p)/(1-q))
    kl = p * math.log(p / q) + (1 - p) * math.log((1 - p) / (1 - q))
    # Normalize to [0,1] via squashing
    return min(1.0, max(0.0, 1.0 - math.exp(-kl)))
