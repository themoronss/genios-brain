"""Lifecycle-aware confidence modifier for Section B priority scoring.

A recommendation's confidence should reflect the freshness of the facts it
was built on. Live facts → trust as-is. Fading facts → hedge. The modifier
is multiplicative on priority — applied once after scorer.score() and before
the push gate. Returns 1.0 when no facts are found (don't penalize unknown).

Weights match the spec's lifecycle×intelligence matrix:
  live   →  1.0
  fade   →  0.6
  invalid→  0.2  (contradicted by newer evidence — kept as historical signal)
"""
from __future__ import annotations

import logging

from sqlalchemy import text

logger = logging.getLogger(__name__)

_LIVE_WEIGHT = 1.0
_FADE_WEIGHT = 0.6
_DEFAULT_MODIFIER = 1.0  # no facts → no penalty (preserve current behavior)


def lifecycle_modifier(db, org_id: str, contact_id: str) -> float:
    """Return a multiplier in (0,1] reflecting lifecycle freshness of the
    contact's reasoning facts. Excludes ingest/validate (not yet ready) and
    dormant/archive (not used in active recommendations).
    """
    if not org_id or not contact_id:
        return _DEFAULT_MODIFIER
    try:
        row = db.execute(
            text("""
                SELECT
                    COUNT(*) FILTER (WHERE lifecycle = 'live') AS live_n,
                    COUNT(*) FILTER (WHERE lifecycle = 'fade') AS fade_n,
                    COUNT(*) AS total_n
                FROM contact_facts
                WHERE org_id = :oid
                  AND contact_id::text = :cid
                  AND lifecycle IN ('live', 'fade')
            """),
            {"oid": org_id, "cid": str(contact_id)},
        ).fetchone()
    except Exception as e:
        logger.debug(f"lifecycle_modifier query failed: {e}")
        return _DEFAULT_MODIFIER

    if not row or not row.total_n:
        return _DEFAULT_MODIFIER

    live_n = int(row.live_n or 0)
    fade_n = int(row.fade_n or 0)
    total = live_n + fade_n
    if total <= 0:
        return _DEFAULT_MODIFIER

    weighted = (live_n * _LIVE_WEIGHT + fade_n * _FADE_WEIGHT) / total
    return max(0.0, min(1.0, weighted))
