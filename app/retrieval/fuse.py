"""
Reciprocal Rank Fusion — merges multiple ranked lists into one.

RRF is robust to score-scale differences between retrievers (bm25 rank vs
cosine similarity vs graph walk score). No normalisation needed.

  rrf_score(doc) = sum over lists of 1 / (k + rank_in_list)

Enhancements over vanilla RRF:
  - Vector similarity bonus: when a candidate carries a `similarity` score
    (from pgvector), it is blended in so semantically close hits rise above
    rank-equal alternatives.
  - Recency decay: interactions from the last 30 days get a small boost so
    freshness is rewarded within the same relevance tier.
  - Context score boost: candidates from contacts with a high `context_score`
    are promoted, letting relationship importance surface automatically.
"""

from datetime import datetime, timezone
from typing import Iterable

_SIMILARITY_WEIGHT = 0.15   # blend weight for vector cosine similarity
_RECENCY_BOOST     = 0.05   # max boost for interactions within 30 days
_CONTEXT_BOOST     = 0.10   # max boost per unit of contact context_score


def _recency_boost(item: dict) -> float:
    """Linear decay: full boost at 0 days, zero at 30 days."""
    sent_at = item.get("sent_at") or item.get("interaction_at")
    if not sent_at:
        return 0.0
    try:
        if isinstance(sent_at, str):
            sent_at = datetime.fromisoformat(sent_at.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        if sent_at.tzinfo is None:
            sent_at = sent_at.replace(tzinfo=timezone.utc)
        age_days = (now - sent_at).total_seconds() / 86400
        if age_days >= 30:
            return 0.0
        return _RECENCY_BOOST * (1.0 - age_days / 30.0)
    except Exception:
        return 0.0


def rrf_fuse(
    result_lists: Iterable[list],
    k: int = 60,
    limit: int = 50,
) -> list:
    """
    Each input list is pre-ranked (best first). Documents are matched by id.
    Returns a single ranked list enriched with `rrf_score` and `sources`.
    """
    bucket: dict = {}
    for ranked in result_lists:
        for rank, item in enumerate(ranked, start=1):
            doc_id = item.get("id")
            if not doc_id:
                continue
            entry = bucket.setdefault(
                doc_id,
                {**item, "rrf_score": 0.0, "sources": []},
            )
            base = 1.0 / (k + rank)

            # Blend in vector similarity when available
            sim = item.get("similarity")
            if sim is not None:
                base += _SIMILARITY_WEIGHT * float(sim)

            entry["rrf_score"] += base
            src = item.get("source")
            if src and src not in entry["sources"]:
                entry["sources"].append(src)

    # Post-fusion boosts (applied once per doc, not per list)
    for entry in bucket.values():
        entry["rrf_score"] += _recency_boost(entry)
        ctx = entry.get("context_score") or entry.get("score_composite")
        if ctx:
            entry["rrf_score"] += _CONTEXT_BOOST * min(float(ctx), 1.0)

    fused = sorted(bucket.values(), key=lambda x: x["rrf_score"], reverse=True)
    return fused[:limit]
