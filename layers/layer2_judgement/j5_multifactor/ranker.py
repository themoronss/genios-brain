"""
J5.3 — Ranker

Normalize and rank factors by weight.
Return top N driving factors.
"""

from core.contracts.judgement_report import RankedFactor


def rank_factors(
    factors: list[RankedFactor], top_n: int = 5
) -> tuple[list[RankedFactor], float]:
    """
    Sort factors by weight and return top N.

    Args:
        factors: List of extracted factors.
        top_n: Max factors to keep.

    Returns:
        Tuple of (sorted top factors, confidence score 0-1).
    """
    if not factors:
        return [], 0.0

    # Sort by weight descending
    sorted_factors = sorted(factors, key=lambda f: f.weight, reverse=True)
    top = sorted_factors[:top_n]

    # Confidence = average weight of top factors
    confidence = sum(f.weight for f in top) / len(top) if top else 0.0
    confidence = round(min(1.0, confidence), 3)

    return top, confidence
