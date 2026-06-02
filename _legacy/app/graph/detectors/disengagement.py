"""
Cross-source disengagement detectors.

Fires when negative signals accumulate across multiple sources (email + calendar)
within a short window, indicating a contact is actively disengaging.

These are compound signals — each individual signal might be P2/P3,
but 2+ combined within 14 days = P1.
"""

from sqlalchemy import text
from typing import List, Dict


def _detect_disengagement_pattern(db, org_id: str) -> List[Dict]:
    """
    Detect contacts with 2+ negative signals from different sources within 14 days.

    Negative signals:
      - Calendar: declined meeting, cancelled meeting, no-show (sentiment < 0)
      - Email: 3+ consecutive outbound with zero inbound in 14 days
      - Email: attachment sent with no reply within 7 days

    Triggers immediate P1 insight: "Contact is disengaging".
    """
    results = db.execute(
        text("""
            WITH email_signals AS (
                -- Contacts with 3+ recent outbound and zero inbound in 14 days
                SELECT contact_id, 'email_silence' AS signal_type
                FROM interactions
                WHERE org_id = :org_id
                AND interaction_at > NOW() - INTERVAL '14 days'
                GROUP BY contact_id
                HAVING COUNT(*) FILTER (WHERE direction = 'outbound') >= 3
                   AND COUNT(*) FILTER (WHERE direction = 'inbound') = 0
            ),
            attachment_signals AS (
                -- Sent attachment but no reply in 7 days
                SELECT i.contact_id, 'attachment_ignored' AS signal_type
                FROM interactions i
                WHERE i.org_id = :org_id
                AND i.direction = 'outbound'
                AND i.has_attachment = TRUE
                AND i.interaction_at > NOW() - INTERVAL '14 days'
                AND NOT EXISTS (
                    SELECT 1 FROM interactions i2
                    WHERE i2.contact_id = i.contact_id
                    AND i2.direction = 'inbound'
                    AND i2.interaction_at > i.interaction_at
                    AND i2.interaction_at < i.interaction_at + INTERVAL '7 days'
                )
            ),
            calendar_signals AS (
                -- Declined or cancelled meetings in last 14 days
                SELECT i.contact_id, 'meeting_negative' AS signal_type
                FROM interactions i
                WHERE i.org_id = :org_id
                AND i.source = 'calendar'
                AND i.interaction_at > NOW() - INTERVAL '14 days'
                AND (i.rsvp_status = 'declined' OR i.sentiment < 0)
            ),
            all_signals AS (
                SELECT * FROM email_signals
                UNION ALL
                SELECT * FROM attachment_signals
                UNION ALL
                SELECT * FROM calendar_signals
            ),
            disengaging AS (
                SELECT contact_id,
                       COUNT(DISTINCT signal_type) AS signal_count,
                       array_agg(DISTINCT signal_type) AS signal_types
                FROM all_signals
                GROUP BY contact_id
                HAVING COUNT(DISTINCT signal_type) >= 2
            )
            SELECT d.contact_id, d.signal_count, d.signal_types,
                   c.name, c.company, c.relationship_stage
            FROM disengaging d
            JOIN contacts c ON c.id = d.contact_id
            WHERE c.is_archived = FALSE
            LIMIT 10
        """),
        {"org_id": org_id}
    ).fetchall()

    insights = []
    for r in results:
        signal_types = r[2] if r[2] else []
        signal_desc = []
        if "email_silence" in signal_types:
            signal_desc.append("no email replies")
        if "attachment_ignored" in signal_types:
            signal_desc.append("ignored sent documents")
        if "meeting_negative" in signal_types:
            signal_desc.append("declined/cancelled meetings")

        insights.append({
            "insight_type": "relationship",
            "priority": "P1",
            "category": "disengagement",
            "title": f"{r[3]} is disengaging — {r[1]} negative signals in 14 days",
            "detail": (
                f"{r[3]} from {r[4] or 'Unknown'} shows multiple disengagement signals: "
                f"{', '.join(signal_desc)}. "
                f"Current stage: {r[5]}. Consider changing approach or escalating."
            ),
            "contact_id": str(r[0]),
            "contact_name": r[3],
            "metadata": {
                "signal_count": r[1],
                "signal_types": signal_types,
                "stage": r[5],
            },
        })
    return insights


def _detect_no_show_pattern(db, org_id: str) -> List[Dict]:
    """
    Detect contacts who have no-showed or cancelled multiple meetings.
    Pattern: 2+ calendar negative events (cancelled, declined, no-show) in 30 days.
    """
    results = db.execute(
        text("""
            SELECT c.id, c.name, c.company, c.relationship_stage,
                   COUNT(*) AS negative_count
            FROM interactions i
            JOIN contacts c ON c.id = i.contact_id
            WHERE i.org_id = :org_id
            AND i.source = 'calendar'
            AND i.interaction_at > NOW() - INTERVAL '30 days'
            AND (i.rsvp_status = 'declined' OR i.sentiment < 0)
            AND c.is_archived = FALSE
            GROUP BY c.id, c.name, c.company, c.relationship_stage
            HAVING COUNT(*) >= 2
            LIMIT 5
        """),
        {"org_id": org_id}
    ).fetchall()

    return [{
        "insight_type": "relationship",
        "priority": "P1",
        "category": "no_show_pattern",
        "title": f"{r[1]} cancelled or missed {r[4]} meetings in 30 days",
        "detail": (
            f"{r[1]} from {r[2] or 'Unknown'} has {r[4]} cancelled/declined/no-show "
            f"meetings in the last 30 days. This pattern suggests disinterest. "
            f"Consider direct outreach to understand their situation before scheduling more."
        ),
        "contact_id": str(r[0]),
        "contact_name": r[1],
        "metadata": {"negative_count": r[4], "stage": r[3]},
    } for r in results]


def _detect_attachment_ghosting(db, org_id: str) -> List[Dict]:
    """
    Detect contacts who received documents/attachments but never replied.
    High-value signal: sending a pitch deck or proposal with no response
    is a strong disengagement indicator.
    """
    results = db.execute(
        text("""
            SELECT c.id, c.name, c.company, c.relationship_stage,
                   COUNT(*) AS attachment_count
            FROM interactions i
            JOIN contacts c ON c.id = i.contact_id
            WHERE i.org_id = :org_id
            AND i.direction = 'outbound'
            AND i.has_attachment = TRUE
            AND i.interaction_at > NOW() - INTERVAL '14 days'
            AND NOT EXISTS (
                SELECT 1 FROM interactions i2
                WHERE i2.contact_id = i.contact_id
                AND i2.direction = 'inbound'
                AND i2.interaction_at > i.interaction_at
            )
            AND c.is_archived = FALSE
            GROUP BY c.id, c.name, c.company, c.relationship_stage
            LIMIT 5
        """),
        {"org_id": org_id}
    ).fetchall()

    return [{
        "insight_type": "relationship",
        "priority": "P2",
        "category": "attachment_ghosting",
        "title": f"{r[1]} hasn't responded to {r[4]} document{'s' if r[4] > 1 else ''} you sent",
        "detail": (
            f"You sent {r[4]} email{'s' if r[4] > 1 else ''} with attachments to {r[1]} "
            f"({r[2] or 'Unknown'}) in the last 14 days with no reply. "
            f"Consider a brief text-only follow-up asking if they received it."
        ),
        "contact_id": str(r[0]),
        "contact_name": r[1],
        "metadata": {"attachment_count": r[4], "stage": r[3]},
    } for r in results]


DISENGAGEMENT_DETECTORS = [
    _detect_disengagement_pattern,
    _detect_no_show_pattern,
    _detect_attachment_ghosting,
]
