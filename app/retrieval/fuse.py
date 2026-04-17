"""
Reciprocal Rank Fusion — merges multiple ranked lists into one.

RRF is robust to score-scale differences between retrievers (bm25 rank vs
cosine similarity vs graph walk score). No normalisation needed.

  rrf_score(doc) = sum over lists of 1 / (k + rank_in_list)
"""

from typing import Iterable


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
            entry["rrf_score"] += 1.0 / (k + rank)
            src = item.get("source")
            if src and src not in entry["sources"]:
                entry["sources"].append(src)

    fused = sorted(bucket.values(), key=lambda x: x["rrf_score"], reverse=True)
    return fused[:limit]
