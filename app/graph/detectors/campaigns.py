"""
Campaign / user-side pattern detectors.

Contact-side detectors answer "what's wrong with contact X?". This module is
the first of the user-side category — it answers "what is the operator
*doing* right now?" Concretely: when the same topic goes out to 2+ distinct
contacts in a short window, that's an active outreach campaign. Surfacing it
lets the agent treat the next contact on that topic as a continuation, not
a cold ask ("you already sent similar to A, B — reuse the framing").

Flag-gated via GENIOS_CAMPAIGN_DETECTORS_ENABLED so the registry can opt in
per-org or globally without a redeploy.
"""

import os
from typing import List, Dict
from sqlalchemy import text


def _enabled() -> bool:
    # Default-on as of Phase 3 Task 3.2 — campaign awareness is part of the
    # core "brain notices what you're doing" promise. Set the env var to
    # "false" to opt a tenant out without a redeploy.
    return os.getenv("GENIOS_CAMPAIGN_DETECTORS_ENABLED", "true").lower() in ("1", "true", "yes")


def _detect_active_outbound_campaign(db, org_id: str) -> List[Dict]:
    """
    Active campaign: same topic sent to >=2 distinct contacts in last 72h.

    Emits one insight per detected campaign-topic. Ordered by recipient count
    desc — larger campaigns surface first.
    """
    if not _enabled():
        return []

    try:
        rows = db.execute(
            text("""
                WITH outbound_72h AS (
                    SELECT i.contact_id, i.interaction_at, i.subject,
                           UNNEST(COALESCE(i.topics, ARRAY[]::text[])) AS topic
                    FROM interactions i
                    WHERE i.org_id = :org_id
                      AND i.direction = 'outbound'
                      AND i.interaction_at > NOW() - INTERVAL '72 hours'
                ),
                grouped AS (
                    SELECT
                        topic,
                        COUNT(DISTINCT contact_id) AS recipient_count,
                        COUNT(*) AS message_count,
                        MIN(interaction_at) AS first_sent,
                        MAX(interaction_at) AS last_sent,
                        ARRAY_AGG(DISTINCT contact_id) AS contact_ids
                    FROM outbound_72h
                    WHERE topic IS NOT NULL AND topic <> ''
                    GROUP BY topic
                    HAVING COUNT(DISTINCT contact_id) >= 2
                )
                SELECT
                    g.topic, g.recipient_count, g.message_count,
                    g.first_sent, g.last_sent, g.contact_ids,
                    (SELECT ARRAY_AGG(c.name)
                     FROM contacts c
                     WHERE c.id = ANY(g.contact_ids)
                       AND COALESCE(c.disclosure_level, 'public') = 'public'
                     LIMIT 5) AS recipient_names
                FROM grouped g
                ORDER BY g.recipient_count DESC, g.last_sent DESC
                LIMIT 10
            """),
            {"org_id": org_id},
        ).fetchall()
    except Exception:
        # Detector failures must never poison the insight run.
        try:
            db.rollback()
        except Exception:
            pass
        return []

    insights: List[Dict] = []
    for r in rows:
        topic = r[0]
        recipient_count = int(r[1] or 0)
        message_count = int(r[2] or 0)
        names = [n for n in (r[6] or []) if n]
        preview = ", ".join(names[:3])
        if recipient_count > 3:
            preview += f" +{recipient_count - 3} more"

        insights.append({
            "insight_type": "user_pattern",
            "priority": "P2",
            "category": "active_campaign",
            "title": f"Active campaign: '{topic}' — {recipient_count} contact(s) reached",
            "detail": (
                f"You sent about '{topic}' to {recipient_count} contact(s) in the last 72h: "
                f"{preview}. Next outreach on this topic will be treated as continuation."
            ),
            # Org-level insight — no single contact owns this pattern.
            "contact_id": None,
            "contact_name": None,
            "metadata": {
                "topic": topic,
                "recipient_count": recipient_count,
                "message_count": message_count,
                "first_sent": r[3].isoformat() if r[3] else None,
                "last_sent": r[4].isoformat() if r[4] else None,
                "recipient_names_preview": names[:5],
            },
        })

    return insights


CAMPAIGN_DETECTORS = [
    _detect_active_outbound_campaign,
]
