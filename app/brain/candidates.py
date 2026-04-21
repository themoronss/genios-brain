"""Candidate generator — runs all detectors for one org, returns their union.

Phase 2 uses the existing detector registry. When called from the router
after a debounce flush we pass `subject_entity_ids` to narrow the result,
otherwise we take everything the detectors produced.
"""
from __future__ import annotations

import logging
from typing import Dict, Iterable, List

from app.graph.detectors import ALL_DETECTORS

logger = logging.getLogger(__name__)


def generate(
    db,
    org_id: str,
    subject_entity_ids: Iterable[str] | None = None,
) -> List[Dict]:
    """Run every registered detector and return candidates.

    subject_entity_ids: optional filter; if provided, only candidates whose
    contact_id matches are returned.
    """
    ids = set(str(x) for x in subject_entity_ids) if subject_entity_ids else None

    candidates: List[Dict] = []
    for detector in ALL_DETECTORS:
        try:
            found = detector(db, org_id) or []
        except Exception as e:
            logger.warning(f"detector {detector.__name__} failed: {e}")
            continue
        for cand in found:
            if ids is None or str(cand.get("contact_id")) in ids:
                cand["detector"] = detector.__name__
                candidates.append(cand)
    return candidates
