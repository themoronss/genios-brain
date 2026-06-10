"""Convergence scoring for Section B candidates.

A senior account manager doesn't act on one weak signal — they act when
multiple weak signals point the same direction simultaneously. Convergence
captures that intuition: per contact, count how many independent detector
categories fired in the window, weight by their priorities, and produce a
single 0..1 score.

This module ANNOTATES candidates with their convergence score; it does NOT
filter or skip any candidate. Filtering would risk dropping legitimate
single-signal insights before we have outcome data to validate the gate.
A future Sprint 3 task can use these annotations to drive a hard skip when
data confirms low-convergence candidates are noise.

Score interpretation:
  0.00 - 0.25 : isolated signal — handle with caution
  0.25 - 0.50 : moderate corroboration
  0.50 - 0.75 : strong convergence — high-confidence territory
  0.75 - 1.00 : very strong — multiple categories agree
"""
from __future__ import annotations

import logging
from collections import defaultdict
from typing import Dict, Iterable, List

logger = logging.getLogger(__name__)

# Map P1/P2/P3 → numeric weights so we can roll multiple signals into one score.
_PRIORITY_WEIGHTS = {"P1": 1.0, "P2": 0.6, "P3": 0.3}
_DEFAULT_WEIGHT = 0.4  # untyped or unknown priority


def _candidate_weight(cand: Dict) -> float:
    p = (cand.get("priority") or "").upper()
    return _PRIORITY_WEIGHTS.get(p, _DEFAULT_WEIGHT)


def _candidate_category(cand: Dict) -> str:
    """Group key for "independent" signals — detector category, falling back
    to insight_type. We dedup multiple firings within the same category so
    one detector firing 3 sub-rules doesn't masquerade as 3 categories.
    """
    return str(
        cand.get("category")
        or cand.get("insight_type")
        or cand.get("detector")
        or "unknown"
    )


def convergence_for_candidates(candidates: Iterable[Dict]) -> Dict[str, dict]:
    """Group candidates by contact, compute a convergence score per contact.

    Returns: {contact_id: {"score": float, "categories": [...], "n": int}}.
    """
    by_contact: dict[str, list[Dict]] = defaultdict(list)
    for cand in candidates:
        cid = str(cand.get("contact_id") or "")
        if not cid:
            continue
        by_contact[cid].append(cand)

    out: Dict[str, dict] = {}
    for cid, cands in by_contact.items():
        # One vote per unique category — prevents same-detector spam.
        cat_to_weight: dict[str, float] = {}
        for c in cands:
            cat = _candidate_category(c)
            w = _candidate_weight(c)
            if cat not in cat_to_weight or w > cat_to_weight[cat]:
                cat_to_weight[cat] = w
        if not cat_to_weight:
            continue
        n = len(cat_to_weight)
        # Score = average of category weights, scaled by a coverage factor
        # that rewards more independent categories firing.
        avg_weight = sum(cat_to_weight.values()) / n
        coverage = min(1.0, n / 4.0)  # 4+ independent categories saturates
        score = max(0.0, min(1.0, avg_weight * (0.5 + 0.5 * coverage)))
        out[cid] = {
            "score": round(score, 3),
            "categories": sorted(cat_to_weight.keys()),
            "n": n,
        }
    return out


def annotate(candidates: List[Dict]) -> List[Dict]:
    """Enrich each candidate's metadata with its contact's convergence info.
    Mutates and returns the same list. No filtering.
    """
    if not candidates:
        return candidates
    scores = convergence_for_candidates(candidates)
    for cand in candidates:
        cid = str(cand.get("contact_id") or "")
        info = scores.get(cid)
        if not info:
            continue
        meta = cand.setdefault("metadata", {})
        if not isinstance(meta, dict):
            continue
        meta["convergence"] = info
    return candidates
