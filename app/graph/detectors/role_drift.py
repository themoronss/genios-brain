"""Role-drift detector.

Fires when the contact_role extracted from recent interactions (last 30d)
disagrees with the historical majority. Signals a change like
"was a lead, now an advisor" or "was a vendor, now a customer".
"""
from __future__ import annotations

from typing import Dict, List

from sqlalchemy import text


def _detect_role_drift(db, org_id: str) -> List[Dict]:
    """Candidates: contacts whose recent role differs from historical majority."""
    rows = db.execute(
        text("""
            WITH historical AS (
                SELECT contact_id, contact_role,
                       COUNT(*) FILTER (
                         WHERE interaction_at < NOW() - INTERVAL '30 days'
                       ) AS old_count
                FROM interactions
                WHERE org_id = :org_id AND contact_role IS NOT NULL
                GROUP BY contact_id, contact_role
            ),
            old_majority AS (
                SELECT DISTINCT ON (contact_id) contact_id, contact_role AS old_role, old_count
                FROM historical
                WHERE old_count > 0
                ORDER BY contact_id, old_count DESC
            ),
            recent AS (
                SELECT contact_id, contact_role,
                       COUNT(*) AS recent_count
                FROM interactions
                WHERE org_id = :org_id
                  AND contact_role IS NOT NULL
                  AND interaction_at >= NOW() - INTERVAL '30 days'
                GROUP BY contact_id, contact_role
            ),
            recent_majority AS (
                SELECT DISTINCT ON (contact_id) contact_id, contact_role AS new_role, recent_count
                FROM recent
                WHERE recent_count >= 2
                ORDER BY contact_id, recent_count DESC
            )
            SELECT c.id, c.name, c.company, c.relationship_stage,
                   om.old_role, rm.new_role, om.old_count, rm.recent_count
            FROM recent_majority rm
            JOIN old_majority    om USING (contact_id)
            JOIN contacts         c ON c.id = rm.contact_id
            WHERE rm.new_role <> om.old_role
              AND c.is_archived = FALSE
            LIMIT 20
        """),
        {"org_id": org_id},
    ).fetchall()

    return [
        {
            "insight_type": "role_drift",
            "priority": "P2",
            "category": "role_change",
            "title": f"{r[1]} role shifted: {r[4]} → {r[5]}",
            "detail": (
                f"{r[1]} at {r[2] or 'Unknown'} now reads as {r[5]} in recent emails "
                f"({r[7]} signals in 30d); historically {r[4]} ({r[6]} prior signals). "
                f"Reclassify relationship if intentional."
            ),
            "contact_id": str(r[0]),
            "contact_name": r[1],
            "metadata": {
                "old_role": r[4], "new_role": r[5],
                "old_count": r[6], "recent_count": r[7],
                "stage": r[3],
            },
        }
        for r in rows
    ]


ROLE_DRIFT_DETECTORS = [_detect_role_drift]
