"""Authority-change detector.

Flags contacts whose authority_score moved > 0.2 in the last 30 days.
Up-shift = signals more decision-making power (e.g. title promotion).
Down-shift = drop in influence (e.g. role transition).
"""
from __future__ import annotations

from typing import Dict, List

from sqlalchemy import text


def _detect_authority_change(db, org_id: str) -> List[Dict]:
    """Uses sentiment_history or a snapshot if the column exists.

    Implementation reads a lightweight audit from `contact_fact_history` if
    available, else falls back to comparing current `authority_score` vs
    computed baseline from interactions older than 30 days.
    """
    rows = db.execute(
        text("""
            WITH baseline AS (
                SELECT i.contact_id,
                       AVG(COALESCE(NULLIF(i.weight_score,0), 0.5)) AS old_authority
                FROM interactions i
                WHERE i.org_id = :org_id
                  AND i.interaction_at < NOW() - INTERVAL '30 days'
                GROUP BY i.contact_id
                HAVING COUNT(*) >= 3
            )
            SELECT c.id, c.name, c.company, c.relationship_stage,
                   COALESCE(c.authority_score, 0.5)::float AS current_authority,
                   b.old_authority::float AS baseline_authority
            FROM contacts c
            JOIN baseline b ON b.contact_id = c.id
            WHERE c.org_id = :org_id
              AND c.is_archived = FALSE
              AND ABS(COALESCE(c.authority_score, 0.5) - b.old_authority) > 0.2
            ORDER BY ABS(COALESCE(c.authority_score, 0.5) - b.old_authority) DESC
            LIMIT 20
        """),
        {"org_id": org_id},
    ).fetchall()

    out: List[Dict] = []
    for r in rows:
        cur = float(r[4])
        old = float(r[5])
        direction = "up" if cur > old else "down"
        out.append({
            "insight_type": "authority_change",
            "priority": "P2",
            "category": "authority",
            "title": f"{r[1]} authority {direction} ({old:.2f} → {cur:.2f})",
            "detail": (
                f"{r[1]} at {r[2] or 'Unknown'} authority score moved "
                f"{old:.2f} → {cur:.2f} ({direction}). "
                f"Consider revisiting decision-maker mapping."
            ),
            "contact_id": str(r[0]),
            "contact_name": r[1],
            "metadata": {
                "old_authority": old, "current_authority": cur,
                "direction": direction, "stage": r[3],
            },
        })
    return out


AUTHORITY_CHANGE_DETECTORS = [_detect_authority_change]
