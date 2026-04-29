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
  - MMR diversification (mig 079): after scoring, results are re-picked one
    at a time, penalising candidates that overlap heavily with already-picked
    items. Recovers most of what a cross-encoder rerank would give for our
    scale, without a model load or external service. Pure code.
  - Potentiated-fact boost (mig 079): when a candidate is tied to facts that
    have been potentiated by repeated Hebbian co-activation, it gets a small
    additive boost. The brain's own learning feeds back into retrieval.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import Iterable, Optional

from sqlalchemy import text

logger = logging.getLogger(__name__)

_SIMILARITY_WEIGHT = 0.15   # blend weight for vector cosine similarity
_RECENCY_BOOST     = 0.05   # max boost for interactions within 30 days
_CONTEXT_BOOST     = 0.10   # max boost per unit of contact context_score
_POTENTIATED_BOOST = 0.05   # boost when candidate's contact has potentiated facts

# MMR — λ controls relevance vs diversity. λ=1 is pure relevance (no MMR);
# λ=0 is pure diversity. 0.7 keeps relevance dominant while breaking up the
# common "5 replies in same thread" failure mode.
_MMR_LAMBDA = 0.7

_WORD_RE = re.compile(r"[A-Za-z0-9]+")


# ── Pure helpers ────────────────────────────────────────────────────────────

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


def _token_set(item: dict) -> set:
    """Bag of lowercased word tokens drawn from subject + summary + body."""
    parts = [
        item.get("subject") or "",
        item.get("summary")  or "",
        (item.get("body") or "")[:1000],   # cap to keep MMR cheap on long bodies
    ]
    text_blob = " ".join(p for p in parts if p)
    return {t.lower() for t in _WORD_RE.findall(text_blob) if len(t) >= 3}


def _jaccard(a: set, b: set) -> float:
    """Set-based similarity. Cheap, no embeddings needed at MMR time."""
    if not a or not b:
        return 0.0
    inter = len(a & b)
    if inter == 0:
        return 0.0
    return inter / len(a | b)


# ── Core fusion ─────────────────────────────────────────────────────────────

def rrf_fuse(
    result_lists: Iterable[list],
    k: int = 60,
    limit: int = 50,
    apply_mmr: bool = True,
    mmr_lambda: float = _MMR_LAMBDA,
    db=None,
    org_id: Optional[str] = None,
) -> list:
    """
    Each input list is pre-ranked (best first). Documents are matched by id.
    Returns a single ranked list enriched with `rrf_score` and `sources`.

    apply_mmr=True triggers post-fusion diversification on the top 2x results
    (we re-pick `limit` items from the top 2*limit by score). Pass
    apply_mmr=False to keep the legacy pure-RRF behavior (used by callers
    that have their own downstream rerank).

    db + org_id are optional — when supplied, candidates whose contact has
    potentiated contact_facts get a small boost. Failure here is silent so
    retrieval never breaks on a stale schema.
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

    # Potentiated-fact boost — one DB query per fuse call, contact-scoped.
    if db is not None and org_id:
        try:
            potentiated = _potentiated_contact_ids(
                db, org_id,
                contact_ids={
                    e.get("contact_id") for e in bucket.values()
                    if e.get("contact_id")
                },
            )
            if potentiated:
                for entry in bucket.values():
                    if entry.get("contact_id") in potentiated:
                        entry["rrf_score"] += _POTENTIATED_BOOST
        except Exception as e:
            logger.debug(f"potentiated boost skipped: {e}")

    fused = sorted(bucket.values(), key=lambda x: x["rrf_score"], reverse=True)

    if not apply_mmr or len(fused) <= limit:
        return fused[:limit]

    # MMR over top 2x candidates so we have headroom to diversify.
    return _mmr_pick(fused[: max(limit * 2, 20)], limit, mmr_lambda)


# ── MMR diversification ─────────────────────────────────────────────────────

def _mmr_pick(candidates: list, k: int, lam: float) -> list:
    """
    Maximal Marginal Relevance pick.

    score(d) = λ · normalised_relevance(d) − (1−λ) · max_jaccard(d, picked)

    Operates on the same `rrf_score` field so callers don't see a behaviour
    change beyond rerank order. Token sets are computed once per candidate.
    """
    if not candidates:
        return []
    # λ≈1.0 collapses MMR to pure relevance — short-circuit. We do NOT
    # short-circuit on k>=len: even when no filtering is needed, MMR still
    # reorders the list to spread duplicates apart, which is the point.
    if lam >= 0.999:
        return candidates[:k]

    # Normalise rrf_score into [0,1] so it's commensurable with Jaccard.
    scores = [c.get("rrf_score", 0.0) for c in candidates]
    smin, smax = min(scores), max(scores)
    span = smax - smin if smax > smin else 1.0
    rel = [(s - smin) / span for s in scores]

    token_sets = [_token_set(c) for c in candidates]

    picked_idx: list[int] = []
    remaining = set(range(len(candidates)))

    # Always seed with the most relevant candidate.
    best = max(remaining, key=lambda i: rel[i])
    picked_idx.append(best)
    remaining.discard(best)

    while remaining and len(picked_idx) < k:
        best_i, best_score = None, -1e9
        for i in remaining:
            max_overlap = max(
                (_jaccard(token_sets[i], token_sets[j]) for j in picked_idx),
                default=0.0,
            )
            mmr_score = lam * rel[i] - (1.0 - lam) * max_overlap
            if mmr_score > best_score:
                best_score = mmr_score
                best_i = i
        if best_i is None:
            break
        picked_idx.append(best_i)
        remaining.discard(best_i)

    return [candidates[i] for i in picked_idx]


# ── Potentiated lookup ──────────────────────────────────────────────────────

def _potentiated_contact_ids(db, org_id: str, contact_ids: set) -> set:
    """Return the subset of contact_ids that have ≥1 potentiated active fact."""
    contact_ids = {c for c in contact_ids if c}
    if not contact_ids:
        return set()
    # Section B intelligence: include both 'live' (full weight) and 'fade'
    # (still informative — fading facts carry historical signal). Excludes
    # ingest/validate (not yet ready) and dormant/archive (not active reasoning).
    rows = db.execute(
        text("""
            SELECT DISTINCT contact_id::text
            FROM contact_facts
            WHERE org_id = :oid
              AND is_potentiated = TRUE
              AND lifecycle IN ('live', 'fade')
              AND contact_id::text = ANY(:cids)
        """),
        {"oid": org_id, "cids": list(contact_ids)},
    ).fetchall()
    return {r[0] for r in rows}
