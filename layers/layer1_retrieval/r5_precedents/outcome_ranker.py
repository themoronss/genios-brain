"""
R5.3 — Outcome Ranker

Re-rank precedents:
- Prefer positive outcomes
- Penalize policy-violating or failed ones
- Boost recent ones

Produces PrecedentContext with source refs.
"""

from core.contracts.context_bundle import PrecedentContext, SourceRef


def rank_precedents(
    precedents: list[dict],
) -> tuple[PrecedentContext, list[SourceRef]]:
    """
    Rank and filter precedents by outcome quality and recency.

    Args:
        precedents: Raw decision log dicts.

    Returns:
        Tuple of (PrecedentContext, list of SourceRefs).
    """
    sources = []

    # Score each precedent
    scored = []
    for p in precedents:
        score = _compute_score(p)
        scored.append((score, p))

    # Sort by score descending
    scored.sort(key=lambda x: x[0], reverse=True)

    past_decisions = []
    for score, p in scored:
        decision_entry = {
            "id": p.get("id", "unknown"),
            "intent_type": p.get("intent_type", ""),
            "decision_summary": p.get("decision_summary", ""),
            "outcome": p.get("outcome", "unknown"),
            "outcome_score": p.get("outcome_score", 0.0),
            "rank_score": round(score, 3),
            "created_at": p.get("created_at", ""),
        }
        past_decisions.append(decision_entry)

        sources.append(SourceRef(
            source_type="precedent",
            source_id=str(p.get("id", "unknown")),
            confidence=min(1.0, score),
        ))

    return PrecedentContext(
        past_decisions=past_decisions,
    ), sources


def _compute_score(precedent: dict) -> float:
    """
    Compute ranking score for a precedent.

    Factors:
        - outcome_score (0–1): direct quality
        - outcome == 'success': bonus
        - outcome == 'failure': penalty
    """
    base_score = precedent.get("outcome_score", 0.5)

    outcome = precedent.get("outcome", "unknown")
    if outcome == "success":
        base_score += 0.1
    elif outcome == "failure":
        base_score -= 0.3

    return max(0.0, min(1.0, base_score))
