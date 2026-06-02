"""Relationship stage and sentiment detectors."""

from sqlalchemy import text
from datetime import datetime, timezone
from typing import List, Dict


def _detect_going_cold(db, org_id: str) -> List[Dict]:
    """Warm contacts approaching 30-day threshold (going cold this week)."""
    results = db.execute(
        text("""
            SELECT id, name, email, company, entity_type,
                EXTRACT(DAY FROM (NOW() - last_interaction_at)) as days_since
            FROM contacts
            WHERE org_id = :org_id
            AND relationship_stage = 'WARM'
            AND last_interaction_at BETWEEN NOW() - INTERVAL '30 days' AND NOW() - INTERVAL '23 days'
            AND is_archived = FALSE
        """),
        {"org_id": org_id}
    ).fetchall()

    insights = []
    for r in results:
        insights.append({
            "insight_type": "relationship",
            "priority": "P2",
            "category": "going_cold",
            "title": f"{r[1]}'s relationship going cold — {int(r[5])} days since last contact",
            "detail": f"{r[1]} from {r[3] or 'Unknown'} ({r[4] or 'other'}) has not been contacted in {int(r[5])} days. Will move to COLD stage soon.",
            "contact_id": str(r[0]),
            "contact_name": r[1],
            "metadata": {"days_since": int(r[5]), "entity_type": r[4]},
        })
    return insights


def _detect_at_risk(db, org_id: str) -> List[Dict]:
    """Contacts with AT_RISK stage — urgent attention needed."""
    results = db.execute(
        text("""
            SELECT id, name, email, company, entity_type, sentiment_ewma
            FROM contacts
            WHERE org_id = :org_id
            AND relationship_stage = 'AT_RISK'
            AND is_archived = FALSE
        """),
        {"org_id": org_id}
    ).fetchall()

    return [{
        "insight_type": "relationship",
        "priority": "P1",
        "category": "at_risk",
        "title": f"{r[1]} — relationship at risk (sentiment: {round(float(r[5] or 0), 2)})",
        "detail": f"{r[1]} from {r[3] or 'Unknown'} has negative sentiment trend. Immediate attention required.",
        "contact_id": str(r[0]),
        "contact_name": r[1],
        "metadata": {"sentiment_ewma": float(r[5] or 0), "entity_type": r[4]},
    } for r in results]


def _detect_reply_window_closing(db, org_id: str) -> List[Dict]:
    """Warm contacts approaching the 15-day no-reply threshold."""
    results = db.execute(
        text("""
            SELECT id, name, company,
                EXTRACT(DAY FROM (NOW() - last_interaction_at)) as days_since
            FROM contacts
            WHERE org_id = :org_id
            AND relationship_stage = 'WARM'
            AND last_interaction_at BETWEEN NOW() - INTERVAL '15 days' AND NOW() - INTERVAL '11 days'
            AND is_archived = FALSE
        """),
        {"org_id": org_id}
    ).fetchall()

    return [{
        "insight_type": "relationship",
        "priority": "P2",
        "category": "reply_window",
        "title": f"{r[1]}'s reply window closing in {15 - int(r[3])} days",
        "detail": f"Last contact with {r[1]} ({r[2] or 'Unknown'}) was {int(r[3])} days ago. Reply window closing soon.",
        "contact_id": str(r[0]),
        "contact_name": r[1],
        "metadata": {"days_since": int(r[3]), "days_remaining": 15 - int(r[3])},
    } for r in results]


def _detect_unacknowledged_introductions(db, org_id: str) -> List[Dict]:
    """Contacts who introduced people but never received a thank-you."""
    results = db.execute(
        text("""
            SELECT c.id, c.name, COUNT(c2.id) as intro_count
            FROM contacts c
            JOIN contacts c2 ON c2.introduced_by = c.id
            WHERE c.org_id = :org_id
            AND NOT EXISTS (
                SELECT 1 FROM interactions i
                WHERE i.contact_id = c.id
                AND i.direction = 'outbound'
                AND i.interaction_at > c2.created_at
            )
            GROUP BY c.id, c.name
            HAVING COUNT(c2.id) >= 1
        """),
        {"org_id": org_id}
    ).fetchall()

    return [{
        "insight_type": "relationship",
        "priority": "P2",
        "category": "unacknowledged_intro",
        "title": f"{r[1]} introduced {r[2]} contact(s) — no thank-you sent",
        "detail": f"{r[1]} made {r[2]} introduction(s) but you haven't sent an outbound message since. Consider sending a thank-you.",
        "contact_id": str(r[0]),
        "contact_name": r[1],
        "metadata": {"intro_count": r[2]},
    } for r in results]


def _detect_one_sided_relationships(db, org_id: str) -> List[Dict]:
    """Contacts with 5+ interactions but only one direction (no reply)."""
    results = db.execute(
        text("""
            SELECT id, name, company, interaction_count, entity_type
            FROM contacts
            WHERE org_id = :org_id
            AND is_bidirectional = FALSE
            AND interaction_count >= 5
            AND is_archived = FALSE
            AND relationship_stage NOT IN ('COLD', 'AT_RISK')
        """),
        {"org_id": org_id}
    ).fetchall()

    return [{
        "insight_type": "relationship",
        "priority": "P3",
        "category": "one_sided",
        "title": f"{r[1]} — {r[3]} interactions but one-sided communication",
        "detail": f"All {r[3]} interactions with {r[1]} ({r[2] or 'Unknown'}) are one-directional. No two-way engagement detected.",
        "contact_id": str(r[0]),
        "contact_name": r[1],
        "metadata": {"interaction_count": r[3], "entity_type": r[4]},
    } for r in results]


def _detect_declining_sentiment(db, org_id: str) -> List[Dict]:
    """Active/warm contacts with declining sentiment trend."""
    results = db.execute(
        text("""
            SELECT id, name, company, relationship_stage, sentiment_trend, sentiment_ewma
            FROM contacts
            WHERE org_id = :org_id
            AND sentiment_trend = 'DECLINING'
            AND relationship_stage IN ('ACTIVE', 'WARM')
            AND is_archived = FALSE
        """),
        {"org_id": org_id}
    ).fetchall()

    return [{
        "insight_type": "relationship",
        "priority": "P2",
        "category": "declining_sentiment",
        "title": f"{r[1]} — sentiment declining while {r[3].lower()}",
        "detail": f"{r[1]} ({r[2] or 'Unknown'}) has declining sentiment (EWMA: {round(float(r[5] or 0), 2)}) despite being {r[3]}. May transition to AT_RISK.",
        "contact_id": str(r[0]),
        "contact_name": r[1],
        "metadata": {"stage": r[3], "sentiment_ewma": float(r[5] or 0)},
    } for r in results]


def _detect_dormant_reengagement(db, org_id: str) -> List[Dict]:
    """Dormant contacts with previously positive sentiment — worth re-engaging."""
    results = db.execute(
        text("""
            SELECT id, name, company, entity_type, sentiment_avg,
                EXTRACT(DAY FROM (NOW() - last_interaction_at)) as days_since
            FROM contacts
            WHERE org_id = :org_id
            AND relationship_stage IN ('NEEDS_ATTENTION', 'DORMANT')
            AND sentiment_avg > 0.3
            AND interaction_count >= 3
            AND is_archived = FALSE
            ORDER BY sentiment_avg DESC
            LIMIT 5
        """),
        {"org_id": org_id}
    ).fetchall()

    return [{
        "insight_type": "relationship",
        "priority": "P3",
        "category": "reengagement",
        "title": f"{r[1]} — dormant but previously positive (sentiment: {round(float(r[4] or 0), 2)})",
        "detail": f"{r[1]} ({r[2] or 'Unknown'}, {r[3] or 'other'}) had positive engagement but went silent {int(r[5])} days ago. Good candidate for re-engagement.",
        "contact_id": str(r[0]),
        "contact_name": r[1],
        "metadata": {"days_since": int(r[5]), "sentiment_avg": float(r[4] or 0)},
    } for r in results]


def _detect_warm_going_cold_this_week(db, org_id: str) -> List[Dict]:
    """WARM contacts projected to cross the 30-day threshold within 7 days."""
    results = db.execute(
        text("""
            SELECT c.id, c.name, c.company,
                EXTRACT(DAY FROM NOW() - c.last_interaction_at)::int AS days_since
            FROM contacts c
            WHERE c.org_id = :org_id
            AND c.relationship_stage = 'WARM'
            AND c.last_interaction_at IS NOT NULL
            AND EXTRACT(DAY FROM NOW() - c.last_interaction_at) BETWEEN 23 AND 29
            ORDER BY c.last_interaction_at ASC
            LIMIT 10
        """),
        {"org_id": org_id}
    ).fetchall()

    return [{
        "insight_type": "relationship",
        "priority": "P1",
        "category": "going_cold_this_week",
        "title": f"{r[1]} goes cold in {30 - int(r[3])} day{'s' if 30 - int(r[3]) != 1 else ''}",
        "detail": f"{r[1]} ({r[2] or 'Unknown'}) is WARM but last contact was {int(r[3])} days ago. Reach out before they cross the 30-day cold threshold.",
        "contact_id": str(r[0]),
        "contact_name": r[1],
        "metadata": {"days_since": int(r[3]), "days_remaining": 30 - int(r[3])},
    } for r in results]


def _detect_high_value_no_reply(db, org_id: str) -> List[Dict]:
    """ACTIVE contacts where 3+ outbound sent but no inbound reply in 14 days."""
    results = db.execute(
        text("""
            SELECT c.id, c.name, c.company,
                COUNT(i.id) FILTER (WHERE i.direction = 'outbound') AS outbound_count,
                MAX(i.interaction_at) AS last_outbound
            FROM contacts c
            JOIN interactions i ON i.contact_id = c.id
            WHERE c.org_id = :org_id
            AND c.relationship_stage = 'ACTIVE'
            AND i.interaction_at >= NOW() - INTERVAL '14 days'
            GROUP BY c.id, c.name, c.company
            HAVING
                COUNT(i.id) FILTER (WHERE i.direction = 'outbound') >= 3
                AND COUNT(i.id) FILTER (WHERE i.direction = 'inbound') = 0
            ORDER BY outbound_count DESC
            LIMIT 5
        """),
        {"org_id": org_id}
    ).fetchall()

    return [{
        "insight_type": "relationship",
        "priority": "P2",
        "category": "high_value_no_reply",
        "title": f"{r[1]} — {int(r[3])} emails sent, no reply",
        "detail": f"You sent {int(r[3])} emails to {r[1]} ({r[2] or 'Unknown'}) in the last 14 days with no response. Consider a different approach or check if they're the right contact.",
        "contact_id": str(r[0]),
        "contact_name": r[1],
        "metadata": {"outbound_count": int(r[3])},
    } for r in results]


def _detect_positive_cold_contacts(db, org_id: str) -> List[Dict]:
    """COLD contacts whose last interaction had positive sentiment — worth re-engaging."""
    results = db.execute(
        text("""
            SELECT c.id, c.name, c.company, c.entity_type,
                c.sentiment_ewma,
                EXTRACT(DAY FROM NOW() - c.last_interaction_at)::int AS days_since
            FROM contacts c
            WHERE c.org_id = :org_id
            AND c.relationship_stage = 'COLD'
            AND c.sentiment_ewma > 0.3
            AND c.interaction_count >= 3
            AND (c.is_archived = FALSE OR c.is_archived IS NULL)
            ORDER BY c.sentiment_ewma DESC
            LIMIT 8
        """),
        {"org_id": org_id}
    ).fetchall()

    return [{
        "insight_type": "relationship",
        "priority": "P3",
        "category": "positive_cold",
        "title": f"{r[1]} — cold but positive history (sentiment {round(float(r[4] or 0), 2)})",
        "detail": f"{r[1]} ({r[2] or 'Unknown'}) went cold {int(r[5])} days ago but your relationship history was positive. A brief check-in could re-activate this contact.",
        "contact_id": str(r[0]),
        "contact_name": r[1],
        "metadata": {"days_since": int(r[5]), "sentiment_ewma": float(r[4] or 0)},
    } for r in results]


def _detect_rapid_sentiment_drop(db, org_id: str) -> List[Dict]:
    """Contacts where last 3 interactions show sharp sentiment drop vs previous 3."""
    results = db.execute(
        text("""
            SELECT c.id, c.name, c.company, c.sentiment_history,
                c.relationship_stage
            FROM contacts c
            WHERE c.org_id = :org_id
            AND c.sentiment_history IS NOT NULL
            AND c.relationship_stage IN ('ACTIVE', 'WARM')
            AND c.interaction_count >= 6
        """),
        {"org_id": org_id}
    ).fetchall()

    insights = []
    for r in results:
        try:
            history = r[3] if isinstance(r[3], list) else []
            if len(history) < 6:
                continue
            recent_avg = sum(history[:3]) / 3
            previous_avg = sum(history[3:6]) / 3
            drop = previous_avg - recent_avg
            if drop >= 0.35:
                insights.append({
                    "insight_type": "relationship",
                    "priority": "P1",
                    "category": "rapid_sentiment_drop",
                    "title": f"{r[1]} — sentiment dropping fast (−{round(drop, 2)})",
                    "detail": f"{r[1]} ({r[2] or 'Unknown'}) sentiment has dropped {round(drop, 2)} points in recent interactions. Relationship may be at risk — review last 3 conversations.",
                    "contact_id": str(r[0]),
                    "contact_name": r[1],
                    "metadata": {"drop": round(drop, 2), "recent_avg": round(recent_avg, 2), "previous_avg": round(previous_avg, 2)},
                })
        except Exception:
            continue

    return insights[:5]


def _detect_no_response_after_commitment(db, org_id: str) -> List[Dict]:
    """We fulfilled a commitment but no reply from them in 7 days."""
    results = db.execute(
        text("""
            SELECT DISTINCT c.id, c.name, c.company,
                MAX(i.interaction_at) AS last_outbound
            FROM contacts c
            JOIN interactions i ON i.contact_id = c.id AND i.direction = 'outbound'
                AND i.intent = 'commitment'
                AND i.interaction_at BETWEEN NOW() - INTERVAL '21 days' AND NOW() - INTERVAL '7 days'
            WHERE c.org_id = :org_id
            AND NOT EXISTS (
                SELECT 1 FROM interactions ir
                WHERE ir.contact_id = c.id
                AND ir.direction = 'inbound'
                AND ir.interaction_at > i.interaction_at
            )
            GROUP BY c.id, c.name, c.company
            ORDER BY last_outbound ASC
            LIMIT 5
        """),
        {"org_id": org_id}
    ).fetchall()

    return [{
        "insight_type": "relationship",
        "priority": "P2",
        "category": "no_response_after_commitment",
        "title": f"{r[1]} — no reply after your follow-up (7+ days)",
        "detail": f"You followed up with {r[1]} ({r[2] or 'Unknown'}) but they haven't replied in over 7 days. Consider a gentle nudge or a different channel.",
        "contact_id": str(r[0]),
        "contact_name": r[1],
        "metadata": {"last_outbound": str(r[3])},
    } for r in results]


def _detect_relationship_velocity_drop(db, org_id: str) -> List[Dict]:
    """Contacts whose interaction frequency dropped 50%+ between last 30d vs previous 30d."""
    results = db.execute(
        text("""
            SELECT c.id, c.name, c.company,
                COUNT(i.id) FILTER (WHERE i.interaction_at >= NOW() - INTERVAL '30 days') AS recent_count,
                COUNT(i.id) FILTER (WHERE i.interaction_at BETWEEN NOW() - INTERVAL '60 days' AND NOW() - INTERVAL '30 days') AS prev_count
            FROM contacts c
            JOIN interactions i ON i.contact_id = c.id
            WHERE c.org_id = :org_id
            AND c.relationship_stage IN ('ACTIVE', 'WARM')
            AND (c.is_archived = FALSE OR c.is_archived IS NULL)
            GROUP BY c.id, c.name, c.company
            HAVING
                COUNT(i.id) FILTER (WHERE i.interaction_at BETWEEN NOW() - INTERVAL '60 days' AND NOW() - INTERVAL '30 days') >= 4
                AND COUNT(i.id) FILTER (WHERE i.interaction_at >= NOW() - INTERVAL '30 days') <=
                    COUNT(i.id) FILTER (WHERE i.interaction_at BETWEEN NOW() - INTERVAL '60 days' AND NOW() - INTERVAL '30 days') / 2
            ORDER BY recent_count ASC
            LIMIT 5
        """),
        {"org_id": org_id}
    ).fetchall()

    return [{
        "insight_type": "relationship",
        "priority": "P2",
        "category": "velocity_drop",
        "title": f"{r[1]} — contact frequency dropped from {int(r[4])} to {int(r[3])} this month",
        "detail": f"{r[1]} ({r[2] or 'Unknown'}) previously had {int(r[4])} interactions/month; this month only {int(r[3])}. Check if the relationship is cooling.",
        "contact_id": str(r[0]),
        "contact_name": r[1],
        "metadata": {"recent_count": int(r[3]), "prev_count": int(r[4])},
    } for r in results]


def _detect_unanswered_inbound(db, org_id: str) -> List[Dict]:
    """Active/warm contacts whose last inbound message was never replied to (7+ days)."""
    results = db.execute(
        text("""
            SELECT DISTINCT ON (c.id)
                c.id, c.name, c.company, c.relationship_stage,
                i.interaction_at AS last_inbound
            FROM contacts c
            JOIN interactions i ON i.contact_id = c.id AND i.direction = 'inbound'
            WHERE c.org_id = :org_id
            AND c.relationship_stage IN ('ACTIVE', 'WARM')
            AND i.interaction_at BETWEEN NOW() - INTERVAL '30 days' AND NOW() - INTERVAL '7 days'
            AND (c.is_archived = FALSE OR c.is_archived IS NULL)
            AND NOT EXISTS (
                SELECT 1 FROM interactions ir
                WHERE ir.contact_id = c.id
                AND ir.direction = 'outbound'
                AND ir.interaction_at > i.interaction_at
            )
            ORDER BY c.id, i.interaction_at DESC
            LIMIT 5
        """),
        {"org_id": org_id}
    ).fetchall()

    return [{
        "insight_type": "relationship",
        "priority": "P1",
        "category": "unanswered_inbound",
        "title": f"{r[1]} messaged you — no reply in {(datetime.now(timezone.utc) - r[4].replace(tzinfo=timezone.utc) if r[4] else __import__('datetime').timedelta(0)).days} days",
        "detail": f"{r[1]} ({r[2] or 'Unknown'}) sent an inbound message that hasn't been replied to. Unanswered messages can damage relationships.",
        "contact_id": str(r[0]),
        "contact_name": r[1],
        "metadata": {"stage": r[3]},
    } for r in results]


RELATIONSHIP_DETECTORS = [
    _detect_going_cold,
    _detect_at_risk,
    _detect_reply_window_closing,
    _detect_unacknowledged_introductions,
    _detect_one_sided_relationships,
    _detect_declining_sentiment,
    _detect_dormant_reengagement,
    _detect_warm_going_cold_this_week,
    _detect_high_value_no_reply,
    _detect_positive_cold_contacts,
    _detect_rapid_sentiment_drop,
    _detect_no_response_after_commitment,
    _detect_relationship_velocity_drop,
    _detect_unanswered_inbound,
]
