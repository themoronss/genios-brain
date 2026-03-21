"""
Insights Engine — Nightly Signal Detection
Per PDF spec §9: ~40 pre-built signal detection queries that run nightly.
Each query has a threshold and priority tier:
  P1 = act within 24h
  P2 = act this week
  P3 = FYI

No LLM involved in detection — all deterministic graph queries.
LLM only writes the human-readable insight sentence on top of the structured result.
"""

from sqlalchemy import text
from datetime import datetime, timezone
from uuid import uuid4
from typing import List, Dict
import json


def run_insights_engine(db, org_id: str) -> List[Dict]:
    """
    Run all signal detection queries for an org.
    Clears stale insights and generates fresh ones.
    Returns list of generated insights.
    """
    # Clear old insights (older than 7 days or dismissed)
    db.execute(
        text("""
            DELETE FROM insights
            WHERE org_id = :org_id
            AND (generated_at < NOW() - INTERVAL '7 days' OR is_dismissed = TRUE)
        """),
        {"org_id": org_id}
    )

    insights = []

    # Run each detection query
    for detector in _DETECTORS:
        try:
            new_insights = detector(db, org_id)
            insights.extend(new_insights)
        except Exception as e:
            print(f"⚠️ Insight detector failed: {e}")
            continue

    # Batch insert all insights
    for insight in insights:
        db.execute(
            text("""
                INSERT INTO insights (id, org_id, insight_type, priority, category,
                    title, detail, contact_id, contact_name, metadata, generated_at, expires_at)
                VALUES (:id, :org_id, :insight_type, :priority, :category,
                    :title, :detail, :contact_id, :contact_name, :metadata, NOW(),
                    NOW() + INTERVAL '7 days')
            """),
            {
                "id": str(uuid4()),
                "org_id": org_id,
                "insight_type": insight.get("insight_type", "relationship"),
                "priority": insight.get("priority", "P3"),
                "category": insight.get("category", "general"),
                "title": insight.get("title", ""),
                "detail": insight.get("detail"),
                "contact_id": insight.get("contact_id"),
                "contact_name": insight.get("contact_name"),
                "metadata": json.dumps(insight.get("metadata", {})),
            }
        )

    db.commit()
    print(f"💡 Generated {len(insights)} insights for org {org_id[:8]}")
    return insights


# ══════════════════════════════════════════════════════════════════════════
# RELATIONSHIP GRAPH DETECTORS
# ══════════════════════════════════════════════════════════════════════════


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


def _detect_overdue_commitments(db, org_id: str) -> List[Dict]:
    """Open commitments past their due date."""
    results = db.execute(
        text("""
            SELECT c.id, c.name, cm.commit_text, cm.due_date, cm.owner,
                EXTRACT(DAY FROM (NOW() - cm.due_date)) as days_overdue
            FROM commitments cm
            JOIN contacts c ON cm.contact_id = c.id
            WHERE cm.org_id = :org_id
            AND cm.status = 'OPEN'
            AND cm.due_date < NOW()
            ORDER BY cm.due_date ASC
            LIMIT 20
        """),
        {"org_id": org_id}
    ).fetchall()

    return [{
        "insight_type": "state",
        "priority": "P1",
        "category": "overdue_commitment",
        "title": f"Overdue: {r[2][:60]} — {int(r[5])} days past due",
        "detail": f"Commitment to {r[1]} ({r[4]}): \"{r[2]}\". Due {r[3].strftime('%b %d') if r[3] else 'unknown'}. {int(r[5])} days overdue.",
        "contact_id": str(r[0]),
        "contact_name": r[1],
        "metadata": {"commit_text": r[2], "days_overdue": int(r[5]), "owner": r[4]},
    } for r in results]


def _detect_no_follow_up_investors(db, org_id: str) -> List[Dict]:
    """Investor contacts with no update in 30+ days."""
    results = db.execute(
        text("""
            SELECT id, name, company,
                EXTRACT(DAY FROM (NOW() - last_interaction_at)) as days_since
            FROM contacts
            WHERE org_id = :org_id
            AND entity_type = 'investor'
            AND last_interaction_at < NOW() - INTERVAL '30 days'
            AND is_archived = FALSE
            ORDER BY last_interaction_at ASC
        """),
        {"org_id": org_id}
    ).fetchall()

    if not results:
        return []

    count = len(results)
    names = ", ".join(r[1] for r in results[:3])
    if count > 3:
        names += f" +{count - 3} more"

    return [{
        "insight_type": "relationship",
        "priority": "P2",
        "category": "investor_dormant",
        "title": f"{count} investor contact(s) received no update this month",
        "detail": f"Investors without updates: {names}. Consider sending a traction update.",
        "contact_id": str(results[0][0]) if results else None,
        "contact_name": results[0][1] if results else None,
        "metadata": {"count": count, "contacts": [{"name": r[1], "days_since": int(r[3])} for r in results[:5]]},
    }]


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


def _detect_stalled_deals(db, org_id: str) -> List[Dict]:
    """State entities (payments/invoices) that are PENDING too long."""
    results = db.execute(
        text("""
            SELECT entity_type, entity_id, vendor, amount, due_date, status,
                EXTRACT(DAY FROM (NOW() - updated_at)) as days_stalled
            FROM state_entities
            WHERE org_id = :org_id
            AND status = 'PENDING'
            AND updated_at < NOW() - INTERVAL '7 days'
        """),
        {"org_id": org_id}
    ).fetchall()

    return [{
        "insight_type": "state",
        "priority": "P2",
        "category": "stalled_state",
        "title": f"{r[0]} {r[1]} stalled {int(r[6])} days — still {r[5]}",
        "detail": f"{r[0]} for {r[2] or 'Unknown'} (amount: {r[3] or 'N/A'}) has been {r[5]} for {int(r[6])} days.",
        "contact_id": None,
        "contact_name": None,
        "metadata": {"entity_type": r[0], "entity_id": r[1], "days_stalled": int(r[6])},
    } for r in results]


def _detect_open_commitments_summary(db, org_id: str) -> List[Dict]:
    """Summary insight: total open commitments count."""
    result = db.execute(
        text("""
            SELECT
                COUNT(*) FILTER (WHERE status = 'OPEN') as open_count,
                COUNT(*) FILTER (WHERE status = 'OVERDUE') as overdue_count,
                COUNT(*) FILTER (WHERE status = 'SOFT') as soft_count
            FROM commitments
            WHERE org_id = :org_id
            AND status IN ('OPEN', 'OVERDUE', 'SOFT')
        """),
        {"org_id": org_id}
    ).fetchone()

    if not result or (not result[0] and not result[1]):
        return []

    open_count = result[0] or 0
    overdue_count = result[1] or 0
    soft_count = result[2] or 0
    total = open_count + overdue_count

    if total == 0:
        return []

    priority = "P1" if overdue_count > 0 else "P3"

    return [{
        "insight_type": "state",
        "priority": priority,
        "category": "commitment_summary",
        "title": f"{total} open commitment(s) — {overdue_count} overdue",
        "detail": f"Open: {open_count}, Overdue: {overdue_count}, Soft/tentative: {soft_count}. Review and resolve overdue items.",
        "contact_id": None,
        "contact_name": None,
        "metadata": {"open": open_count, "overdue": overdue_count, "soft": soft_count},
    }]


def _detect_network_health_summary(db, org_id: str) -> List[Dict]:
    """Overall network health summary insight."""
    result = db.execute(
        text("""
            SELECT
                COUNT(*) as total,
                COUNT(*) FILTER (WHERE relationship_stage = 'ACTIVE') as active,
                COUNT(*) FILTER (WHERE relationship_stage = 'WARM') as warm,
                COUNT(*) FILTER (WHERE relationship_stage IN ('NEEDS_ATTENTION', 'DORMANT')) as needs_attention,
                COUNT(*) FILTER (WHERE relationship_stage = 'COLD') as cold,
                COUNT(*) FILTER (WHERE relationship_stage = 'AT_RISK') as at_risk
            FROM contacts
            WHERE org_id = :org_id
            AND relationship_stage IS NOT NULL AND relationship_stage != 'unknown'
            AND is_archived = FALSE
        """),
        {"org_id": org_id}
    ).fetchone()

    if not result or not result[0]:
        return []

    return [{
        "insight_type": "relationship",
        "priority": "P3",
        "category": "network_health",
        "title": f"Network: {result[1]} active, {result[4]} cold, {result[5]} at risk — {result[0]} total contacts",
        "detail": f"Active: {result[1]}, Warm: {result[2]}, Needs attention: {result[3]}, Cold: {result[4]}, At risk: {result[5]}.",
        "contact_id": None,
        "contact_name": None,
        "metadata": {
            "total": result[0], "active": result[1], "warm": result[2],
            "needs_attention": result[3], "cold": result[4], "at_risk": result[5],
        },
    }]


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


# Register all detectors
_DETECTORS = [
    _detect_going_cold,
    _detect_at_risk,
    _detect_overdue_commitments,
    _detect_no_follow_up_investors,
    _detect_reply_window_closing,
    _detect_unacknowledged_introductions,
    _detect_one_sided_relationships,
    _detect_declining_sentiment,
    _detect_stalled_deals,
    _detect_open_commitments_summary,
    _detect_network_health_summary,
    _detect_dormant_reengagement,
]
