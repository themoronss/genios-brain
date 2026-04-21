"""Contradiction detector.

Flags contacts where recent extracted facts contradict each other. Two
current rules:
  1. Opposing contact_role labels in the last 14 days (e.g. 'lead' and 'customer').
  2. Sharp sentiment flip in 7 days (avg flips sign across consecutive windows).
"""
from __future__ import annotations

from typing import Dict, List

from sqlalchemy import text


def _detect_role_contradiction(db, org_id: str) -> List[Dict]:
    rows = db.execute(
        text("""
            WITH recent_roles AS (
                SELECT contact_id, contact_role, COUNT(*) AS n
                FROM interactions
                WHERE org_id = :org_id
                  AND contact_role IS NOT NULL
                  AND interaction_at >= NOW() - INTERVAL '14 days'
                GROUP BY contact_id, contact_role
                HAVING COUNT(*) >= 2
            ),
            conflicts AS (
                SELECT contact_id,
                       ARRAY_AGG(contact_role ORDER BY n DESC) AS roles,
                       COUNT(DISTINCT contact_role) AS role_count
                FROM recent_roles
                GROUP BY contact_id
                HAVING COUNT(DISTINCT contact_role) >= 2
            )
            SELECT c.id, c.name, c.company, cf.roles
            FROM conflicts cf
            JOIN contacts c ON c.id = cf.contact_id
            WHERE c.is_archived = FALSE
            LIMIT 20
        """),
        {"org_id": org_id},
    ).fetchall()

    return [
        {
            "insight_type": "contradiction",
            "priority": "P2",
            "category": "data_inconsistency",
            "title": f"{r[1]} has conflicting roles: {', '.join(r[3])}",
            "detail": (
                f"{r[1]} at {r[2] or 'Unknown'} produced multiple distinct "
                f"contact_role labels in the last 14 days: {', '.join(r[3])}. "
                f"Extraction may be noisy or role truly changed."
            ),
            "contact_id": str(r[0]),
            "contact_name": r[1],
            "metadata": {"conflicting_roles": list(r[3])},
        }
        for r in rows
    ]


def _detect_sentiment_flip(db, org_id: str) -> List[Dict]:
    rows = db.execute(
        text("""
            WITH w AS (
                SELECT contact_id,
                       AVG(sentiment) FILTER (
                         WHERE interaction_at >= NOW() - INTERVAL '7 days'
                       ) AS recent_sent,
                       AVG(sentiment) FILTER (
                         WHERE interaction_at < NOW() - INTERVAL '7 days'
                           AND interaction_at >= NOW() - INTERVAL '30 days'
                       ) AS prior_sent,
                       COUNT(*) FILTER (
                         WHERE interaction_at >= NOW() - INTERVAL '7 days'
                       ) AS recent_n
                FROM interactions
                WHERE org_id = :org_id AND sentiment IS NOT NULL
                GROUP BY contact_id
            )
            SELECT c.id, c.name, c.company,
                   w.prior_sent::float AS prior_sent,
                   w.recent_sent::float AS recent_sent
            FROM w
            JOIN contacts c ON c.id = w.contact_id
            WHERE w.recent_n >= 2
              AND w.prior_sent IS NOT NULL
              AND w.recent_sent IS NOT NULL
              AND SIGN(w.prior_sent) <> SIGN(w.recent_sent)
              AND ABS(w.prior_sent - w.recent_sent) > 0.5
              AND c.is_archived = FALSE
            LIMIT 20
        """),
        {"org_id": org_id},
    ).fetchall()

    return [
        {
            "insight_type": "contradiction",
            "priority": "P2",
            "category": "sentiment_flip",
            "title": f"{r[1]} sentiment flipped {r[3]:+.2f} → {r[4]:+.2f}",
            "detail": (
                f"{r[1]} at {r[2] or 'Unknown'} went from {r[3]:+.2f} (prior 30d) "
                f"to {r[4]:+.2f} (last 7d). Investigate trigger."
            ),
            "contact_id": str(r[0]),
            "contact_name": r[1],
            "metadata": {"prior_sentiment": r[3], "recent_sentiment": r[4]},
        }
        for r in rows
    ]


CONTRADICTION_DETECTORS = [_detect_role_contradiction, _detect_sentiment_flip]
