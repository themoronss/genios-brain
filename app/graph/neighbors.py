"""Neighbor lookup used by retrieval fusion.

Returns contacts that co-occur with any of the input entities on the same
email thread or calendar event (1-hop). The `hops=2` path is a second
expansion over the results of the 1-hop set, capped to avoid blowup.

Ranking: `score = co_occurrence_count * log(1 + 1 / distance)` where
distance is 1 (direct) or 2 (indirect). Score is the input to RRF fusion.
"""
from __future__ import annotations

import logging
import math
from typing import Dict, Iterable, List

from sqlalchemy import text

logger = logging.getLogger(__name__)

_MAX_DIRECT = 50
_MAX_TOTAL = 100


def _step_direct(db, org_id: str, seed_ids: list[str]) -> dict[str, float]:
    """1-hop neighbors via shared email thread or shared calendar event."""
    if not seed_ids:
        return {}
    rows = db.execute(
        text("""
            WITH seed AS (SELECT unnest(CAST(:ids AS uuid[])) AS contact_id),
            email_pairs AS (
                SELECT i2.contact_id AS neighbor_id, COUNT(*) AS n
                FROM interactions i1
                JOIN interactions i2 ON i1.gmail_message_id = i2.gmail_message_id
                    AND i1.contact_id <> i2.contact_id
                    AND i1.org_id = i2.org_id
                JOIN seed s ON s.contact_id = i1.contact_id
                WHERE i1.org_id = :org_id AND i1.gmail_message_id IS NOT NULL
                GROUP BY i2.contact_id
            ),
            cal_pairs AS (
                SELECT i2.contact_id AS neighbor_id, COUNT(*) AS n
                FROM interactions i1
                JOIN interactions i2 ON i1.calendar_event_id = i2.calendar_event_id
                    AND i1.contact_id <> i2.contact_id
                    AND i1.org_id = i2.org_id
                JOIN seed s ON s.contact_id = i1.contact_id
                WHERE i1.org_id = :org_id AND i1.calendar_event_id IS NOT NULL
                GROUP BY i2.contact_id
            ),
            combined AS (
                SELECT neighbor_id, n FROM email_pairs
                UNION ALL
                SELECT neighbor_id, n FROM cal_pairs
            )
            SELECT neighbor_id, SUM(n) AS weight
            FROM combined
            WHERE neighbor_id NOT IN (SELECT contact_id FROM seed)
            GROUP BY neighbor_id
            ORDER BY SUM(n) DESC
            LIMIT :lim
        """),
        {"org_id": org_id, "ids": seed_ids, "lim": _MAX_DIRECT},
    ).fetchall()
    return {str(r[0]): float(r[1]) for r in rows}


def get_neighbors(
    db,
    org_id: str,
    entity_ids: Iterable[str],
    hops: int = 2,
) -> List[Dict]:
    """Return ranked neighbors. Each dict carries id, score, source='graph'."""
    seed = [str(x) for x in entity_ids if x]
    if not seed:
        return []

    direct = _step_direct(db, org_id, seed)
    merged: dict[str, float] = {cid: w * math.log(1 + 1.0) for cid, w in direct.items()}

    if hops >= 2 and direct:
        second = _step_direct(db, org_id, list(direct.keys())[:_MAX_DIRECT])
        for cid, w in second.items():
            if cid in merged or cid in seed:
                continue
            merged[cid] = w * math.log(1 + 0.5)

    ranked = sorted(
        (
            {"id": cid, "score": score, "source": "graph"}
            for cid, score in merged.items()
        ),
        key=lambda x: x["score"],
        reverse=True,
    )
    return ranked[:_MAX_TOTAL]
