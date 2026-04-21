"""Priority scorer (spec §8.4).

priority = 0.35·reason_conf + 0.25·subject_importance + 0.25·time_urgency + 0.15·novelty
"""
from __future__ import annotations

from app.brain.reasoner import ReasonResult


def score(result: ReasonResult) -> float:
    """Clamp the weighted sum to [0,1]. All weights sum to 1.0."""
    p = (
        0.35 * result.confidence
        + 0.25 * result.subject_importance
        + 0.25 * result.time_urgency
        + 0.15 * result.novelty
    )
    return max(0.0, min(1.0, p))
