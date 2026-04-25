"""Priority scorer (spec §8.4 — guide-aligned).

priority = 0.30·urgency + 0.25·actionability + 0.20·novelty
         + 0.15·user_fit + 0.10·confidence

  urgency      = reason_result.time_urgency (LLM-emitted)
  actionability= reason_result.actionability (LLM-emitted, default 0.5)
  novelty      = reason_result.novelty
  user_fit     = per-org per-type 90d acted-rate (uniform 0.5 below 30 samples)
  confidence   = reason_result.confidence (sanity floor)

Note: subject_importance is no longer in the formula — it's already implicit
in the candidate's upstream context_score / authority weight, so reusing it
here was double-counting. Kept on ReasonResult for downstream observability.
"""
from __future__ import annotations

from app.brain.reasoner import ReasonResult
from app.brain import user_fit as user_fit_mod


def score(result: ReasonResult, *, org_id: str = "", insight_type: str = "") -> float:
    """Clamp the weighted sum to [0,1]. Weights sum to 1.0."""
    uf = user_fit_mod.get(org_id, insight_type) if (org_id and insight_type) else 0.5
    p = (
        0.30 * result.time_urgency
        + 0.25 * result.actionability
        + 0.20 * result.novelty
        + 0.15 * uf
        + 0.10 * result.confidence
    )
    return max(0.0, min(1.0, p))
