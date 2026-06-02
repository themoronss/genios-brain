"""External confidence scoring — NEVER asks the LLM "how confident are you".

Per MD g-i-2 §2.2.2:
    confidence = w1 * constraint_pass        # HARD GATE (if 0, confidence = 0)
               + w2 * grounding_score        # fraction of claims tied to a real Fact
               + w3 * consistency_score      # agreement across n LLM samples
               + w4 * symbolic_support       # 1 if a symbolic rule corroborates

Weights from core.foundations.config.CONFIDENCE_WEIGHTS (3 components — grounding,
consistency, symbolic). `constraint_pass` is the HARD GATE multiplier (not weighted).

constraint_pass == 0 -> overall confidence = 0 regardless of other components.
This is the safety property: a constraint-violating output CANNOT have non-zero confidence.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from core.foundations.config import CONFIDENCE_WEIGHTS


@dataclass(frozen=True)
class ConfidenceBreakdown:
    """Per-component breakdown — surfaced in Decision.confidence_breakdown for g-i-6."""

    overall: float  # final score in [0, 1]
    constraint_pass: bool  # the HARD GATE
    grounding_score: float  # in [0, 1]
    consistency_score: float  # in [0, 1]
    symbolic_support: float  # in {0.0, 1.0}
    weights: dict[str, float]  # the weights actually used (for reproducibility)


class ConfidenceScorer:
    """Pure functional scorer. No I/O. Construct once, score many."""

    def __init__(self, weights: dict[str, float] | None = None) -> None:
        self._weights = weights or CONFIDENCE_WEIGHTS
        self._validate_weights()

    def score(
        self,
        *,
        constraint_pass: bool,
        grounding_score: float,
        consistency_score: float,
        symbolic_support: bool,
    ) -> ConfidenceBreakdown:
        """Compute overall confidence. constraint_pass acts as hard gate."""
        _check_unit(grounding_score, "grounding_score")
        _check_unit(consistency_score, "consistency_score")

        if not constraint_pass:
            return ConfidenceBreakdown(
                overall=0.0,
                constraint_pass=False,
                grounding_score=grounding_score,
                consistency_score=consistency_score,
                symbolic_support=1.0 if symbolic_support else 0.0,
                weights=dict(self._weights),
            )

        sym_val = 1.0 if symbolic_support else 0.0
        overall = (
            self._weights["grounding"] * grounding_score
            + self._weights["consistency"] * consistency_score
            + self._weights["symbolic"] * sym_val
        )
        # Clamp due to float drift
        overall = max(0.0, min(1.0, overall))
        return ConfidenceBreakdown(
            overall=overall,
            constraint_pass=True,
            grounding_score=grounding_score,
            consistency_score=consistency_score,
            symbolic_support=sym_val,
            weights=dict(self._weights),
        )

    def _validate_weights(self) -> None:
        for k in ("grounding", "consistency", "symbolic"):
            if k not in self._weights:
                raise ValueError(f"Confidence weights missing required key: {k}")
        total = sum(self._weights.values())
        if not 0.99 <= total <= 1.01:
            raise ValueError(
                f"Confidence weights must sum to ~1.0; got {total:.4f} from {self._weights}"
            )


# ─────────────────────────────────────────────────────────────────────────────
# Consistency helper — agreement across N LLM samples
# ─────────────────────────────────────────────────────────────────────────────


def consistency_from_samples(samples: Sequence[str]) -> float:
    """Compute consistency_score = fraction of samples that agree with the modal answer.

    For sampled LLM outputs: how often does the "winning" answer appear?
    1.0 = all samples agree; 1/n = no agreement (each unique).
    """
    if not samples:
        return 0.0
    # Normalize trivially (strip whitespace + lower)
    normalized = [s.strip().lower() for s in samples]
    counts: dict[str, int] = {}
    for s in normalized:
        counts[s] = counts.get(s, 0) + 1
    modal = max(counts.values())
    return modal / len(normalized)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────


def _check_unit(v: float, name: str) -> None:
    if not 0.0 <= v <= 1.0:
        raise ValueError(f"{name} must be in [0, 1]; got {v}")
