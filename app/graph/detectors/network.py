"""Entity-type specific, network/cluster, and engagement detectors."""

from sqlalchemy import text
from typing import List, Dict


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
        "metadata": {"count": count, "contacts": [{"name": r[1], "days_since": int(r[3] or 0)} for r in results[:5]]},
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


def _detect_investor_cluster_no_update(db, org_id: str) -> List[Dict]:
    """Aggregate investor contacts with no outbound in 30+ days."""
    result = db.execute(
        text("""
            SELECT COUNT(*) AS dormant_count,
                array_agg(c.name ORDER BY c.last_interaction_at ASC NULLS FIRST) AS names
            FROM contacts c
            WHERE c.org_id = :org_id
            AND c.entity_type = 'investor'
            AND (c.last_interaction_at IS NULL OR c.last_interaction_at < NOW() - INTERVAL '30 days')
            AND (c.is_archived = FALSE OR c.is_archived IS NULL)
        """),
        {"org_id": org_id}
    ).fetchone()

    if not result or not result[0] or result[0] == 0:
        return []

    count = int(result[0])
    names = (result[1] or [])[:3]
    names_str = ", ".join(names) + ("..." if count > 3 else "")

    return [{
        "insight_type": "relationship",
        "priority": "P2",
        "category": "investor_cluster_no_update",
        "title": f"{count} investor contact{'s' if count != 1 else ''} received no update in 30+ days",
        "detail": f"Investors including {names_str} have not heard from you in over 30 days. Consider a brief portfolio update or check-in to keep relationships warm.",
        "contact_id": None,
        "contact_name": None,
        "metadata": {"count": count, "sample_names": names},
    }]


def _detect_new_contacts_no_followup(db, org_id: str) -> List[Dict]:
    """New contacts added in last 7 days but no outbound sent."""
    results = db.execute(
        text("""
            SELECT c.id, c.name, c.company, c.entity_type,
                EXTRACT(DAY FROM NOW() - c.created_at)::int AS days_old
            FROM contacts c
            WHERE c.org_id = :org_id
            AND c.created_at >= NOW() - INTERVAL '7 days'
            AND (c.is_archived = FALSE OR c.is_archived IS NULL)
            AND NOT EXISTS (
                SELECT 1 FROM interactions i
                WHERE i.contact_id = c.id AND i.direction = 'outbound'
            )
            ORDER BY c.created_at DESC
            LIMIT 10
        """),
        {"org_id": org_id}
    ).fetchall()

    return [{
        "insight_type": "relationship",
        "priority": "P2",
        "category": "new_contact_no_followup",
        "title": f"New contact {r[1]} — no outbound sent yet ({int(r[4] or 0)} days)",
        "detail": f"{r[1]} ({r[2] or 'Unknown'}, {r[3] or 'other'}) was added {int(r[4] or 0)} days ago but you haven't sent any outbound yet. Reach out while the connection is fresh.",
        "contact_id": str(r[0]),
        "contact_name": r[1],
        "metadata": {"days_old": int(r[4] or 0), "entity_type": r[3]},
    } for r in results]


def _detect_advisor_dormant(db, org_id: str) -> List[Dict]:
    """Advisor contacts with no interaction in 60+ days."""
    results = db.execute(
        text("""
            SELECT id, name, company,
                EXTRACT(DAY FROM NOW() - last_interaction_at)::int AS days_since
            FROM contacts
            WHERE org_id = :org_id
            AND entity_type = 'advisor'
            AND (last_interaction_at IS NULL OR last_interaction_at < NOW() - INTERVAL '60 days')
            AND (is_archived = FALSE OR is_archived IS NULL)
            ORDER BY last_interaction_at ASC NULLS FIRST
            LIMIT 5
        """),
        {"org_id": org_id}
    ).fetchall()

    return [{
        "insight_type": "relationship",
        "priority": "P2",
        "category": "advisor_dormant",
        "title": f"Advisor {r[1]} — silent for {int(r[3] or 0)} days",
        "detail": f"Advisor {r[1]} ({r[2] or 'Unknown'}) has not been in contact for {int(r[3] or 0)} days. Advisors should be updated at least quarterly.",
        "contact_id": str(r[0]),
        "contact_name": r[1],
        "metadata": {"days_since": int(r[3] or 0)},
    } for r in results]


def _detect_customer_churn_risk(db, org_id: str) -> List[Dict]:
    """Customer contacts with declining sentiment AND no inbound in 21 days."""
    results = db.execute(
        text("""
            SELECT c.id, c.name, c.company, c.sentiment_ewma,
                EXTRACT(DAY FROM NOW() - c.last_interaction_at)::int AS days_since
            FROM contacts c
            WHERE c.org_id = :org_id
            AND c.entity_type = 'customer'
            AND c.sentiment_ewma < 0
            AND (c.last_interaction_at IS NULL OR c.last_interaction_at < NOW() - INTERVAL '21 days')
            AND (c.is_archived = FALSE OR c.is_archived IS NULL)
            ORDER BY c.sentiment_ewma ASC
            LIMIT 5
        """),
        {"org_id": org_id}
    ).fetchall()

    return [{
        "insight_type": "relationship",
        "priority": "P1",
        "category": "customer_churn_risk",
        "title": f"Customer {r[1]} — churn risk (sentiment {round(float(r[3] or 0), 2)}, silent {int(r[4] or 0)} days)",
        "detail": f"Customer {r[1]} ({r[2] or 'Unknown'}) has negative sentiment and has not contacted you in {int(r[4] or 0)} days. Immediate outreach needed.",
        "contact_id": str(r[0]),
        "contact_name": r[1],
        "metadata": {"sentiment_ewma": float(r[3] or 0), "days_since": int(r[4] or 0)},
    } for r in results]


def _detect_candidate_pipeline_stall(db, org_id: str) -> List[Dict]:
    """Candidate contacts with no outbound follow-up in 7+ days."""
    results = db.execute(
        text("""
            SELECT c.id, c.name, c.company,
                EXTRACT(DAY FROM NOW() - c.last_interaction_at)::int AS days_since
            FROM contacts c
            WHERE c.org_id = :org_id
            AND c.entity_type = 'candidate'
            AND c.relationship_stage IN ('ACTIVE', 'WARM')
            AND (c.last_interaction_at IS NULL OR c.last_interaction_at < NOW() - INTERVAL '7 days')
            AND (c.is_archived = FALSE OR c.is_archived IS NULL)
            ORDER BY c.last_interaction_at ASC NULLS FIRST
            LIMIT 5
        """),
        {"org_id": org_id}
    ).fetchall()

    return [{
        "insight_type": "relationship",
        "priority": "P2",
        "category": "candidate_pipeline_stall",
        "title": f"Candidate {r[1]} — pipeline stalled ({int(r[3] or 0)} days no contact)",
        "detail": f"Candidate {r[1]} ({r[2] or 'Unknown'}) has been in your pipeline for {int(r[3] or 0)} days without follow-up. Good candidates don't wait long.",
        "contact_id": str(r[0]),
        "contact_name": r[1],
        "metadata": {"days_since": int(r[3] or 0)},
    } for r in results]


def _detect_high_interaction_low_signal(db, org_id: str) -> List[Dict]:
    """Contacts with 10+ interactions but zero commitments extracted."""
    results = db.execute(
        text("""
            SELECT c.id, c.name, c.company, c.interaction_count, c.entity_type
            FROM contacts c
            WHERE c.org_id = :org_id
            AND c.interaction_count >= 10
            AND (c.is_archived = FALSE OR c.is_archived IS NULL)
            AND NOT EXISTS (
                SELECT 1 FROM commitments cm
                WHERE cm.contact_id = c.id AND cm.org_id = :org_id
            )
            ORDER BY c.interaction_count DESC
            LIMIT 5
        """),
        {"org_id": org_id}
    ).fetchall()

    return [{
        "insight_type": "relationship",
        "priority": "P3",
        "category": "high_interaction_low_signal",
        "title": f"{r[1]} — {int(r[3] or 0)} interactions, no structured commitments",
        "detail": f"{r[1]} ({r[2] or 'Unknown'}) has {int(r[3] or 0)} email interactions but no commitments have been extracted. This may be a high-value relationship worth structuring.",
        "contact_id": str(r[0]),
        "contact_name": r[1],
        "metadata": {"interaction_count": int(r[3] or 0), "entity_type": r[4]},
    } for r in results]


def _detect_media_contact_cold(db, org_id: str) -> List[Dict]:
    """Media/press contacts going cold."""
    results = db.execute(
        text("""
            SELECT id, name, company,
                EXTRACT(DAY FROM NOW() - last_interaction_at)::int AS days_since
            FROM contacts
            WHERE org_id = :org_id
            AND entity_type = 'media'
            AND last_interaction_at < NOW() - INTERVAL '45 days'
            AND (is_archived = FALSE OR is_archived IS NULL)
            ORDER BY last_interaction_at ASC
            LIMIT 5
        """),
        {"org_id": org_id}
    ).fetchall()

    return [{
        "insight_type": "relationship",
        "priority": "P3",
        "category": "media_contact_cold",
        "title": f"Media contact {r[1]} — cold for {int(r[3] or 0)} days",
        "detail": f"{r[1]} ({r[2] or 'press'}) has not been in contact for {int(r[3] or 0)} days. Warm up press/media relationships ahead of announcements.",
        "contact_id": str(r[0]),
        "contact_name": r[1],
        "metadata": {"days_since": int(r[3] or 0)},
    } for r in results]


def _detect_partner_stall(db, org_id: str) -> List[Dict]:
    """Partner contacts with no outbound in 30+ days and open commitments."""
    results = db.execute(
        text("""
            SELECT c.id, c.name, c.company,
                EXTRACT(DAY FROM NOW() - c.last_interaction_at)::int AS days_since,
                COUNT(cm.id) AS open_commitments
            FROM contacts c
            LEFT JOIN commitments cm ON cm.contact_id = c.id AND cm.status IN ('OPEN', 'OVERDUE')
            WHERE c.org_id = :org_id
            AND c.entity_type = 'partner'
            AND (c.last_interaction_at IS NULL OR c.last_interaction_at < NOW() - INTERVAL '30 days')
            AND (c.is_archived = FALSE OR c.is_archived IS NULL)
            GROUP BY c.id, c.name, c.company, c.last_interaction_at
            ORDER BY c.last_interaction_at ASC NULLS FIRST
            LIMIT 5
        """),
        {"org_id": org_id}
    ).fetchall()

    return [{
        "insight_type": "relationship",
        "priority": "P2",
        "category": "partner_stall",
        "title": f"Partner {r[1]} — no contact for {int(r[3] or 0)} days" + (f" + {int(r[4] or 0)} open commitments" if r[4] else ""),
        "detail": f"Partnership with {r[1]} ({r[2] or 'Unknown'}) has stalled. {int(r[3] or 0)} days since last contact" + (f" with {int(r[4] or 0)} open commitments." if r[4] else "."),
        "contact_id": str(r[0]),
        "contact_name": r[1],
        "metadata": {"days_since": int(r[3] or 0), "open_commitments": int(r[4] or 0)},
    } for r in results]


def _detect_top_referrer_not_engaged(db, org_id: str) -> List[Dict]:
    """Contacts who made 2+ introductions but no outbound in 30 days."""
    results = db.execute(
        text("""
            SELECT c.id, c.name, c.company, COUNT(c2.id) AS intro_count,
                EXTRACT(DAY FROM NOW() - MAX(i.interaction_at))::int AS days_since_outbound
            FROM contacts c
            JOIN contacts c2 ON c2.introduced_by = c.id
            LEFT JOIN interactions i ON i.contact_id = c.id AND i.direction = 'outbound'
            WHERE c.org_id = :org_id
            AND (c.is_archived = FALSE OR c.is_archived IS NULL)
            GROUP BY c.id, c.name, c.company
            HAVING
                COUNT(c2.id) >= 2
                AND (
                    MAX(i.interaction_at) IS NULL
                    OR MAX(i.interaction_at) < NOW() - INTERVAL '30 days'
                )
            ORDER BY intro_count DESC
            LIMIT 5
        """),
        {"org_id": org_id}
    ).fetchall()

    return [{
        "insight_type": "relationship",
        "priority": "P3",
        "category": "top_referrer_cold",
        "title": f"{r[1]} — introduced {int(r[2] or 0)} contacts but no recent outbound",
        "detail": f"{r[1]} ({r[2] or 'Unknown'}) made {int(r[3] or 0)} introductions for you but hasn't received an outbound in {int(r[4] or 0)} days. Keep your referral sources warm.",
        "contact_id": str(r[0]),
        "contact_name": r[1],
        "metadata": {"intro_count": int(r[3] or 0), "days_since_outbound": int(r[4] or 0)},
    } for r in results]


def _detect_cluster_concentration_risk(db, org_id: str) -> List[Dict]:
    """If 60%+ of active interactions are in one cluster, warn about concentration."""
    result = db.execute(
        text("""
            SELECT
                c.community_id,
                COUNT(DISTINCT i.id) AS interaction_count,
                SUM(COUNT(DISTINCT i.id)) OVER () AS total_interactions
            FROM contacts c
            JOIN interactions i ON i.contact_id = c.id
            WHERE c.org_id = :org_id
            AND i.interaction_at >= NOW() - INTERVAL '30 days'
            AND c.community_id IS NOT NULL
            GROUP BY c.community_id
            ORDER BY interaction_count DESC
            LIMIT 1
        """),
        {"org_id": org_id}
    ).fetchone()

    if not result or not result[2] or result[2] == 0:
        return []

    pct = float(result[1]) / float(result[2])
    if pct < 0.60:
        return []

    return [{
        "insight_type": "relationship",
        "priority": "P3",
        "category": "cluster_concentration",
        "title": f"{int(pct * 100)}% of recent activity concentrated in one cluster",
        "detail": f"{int(pct * 100)}% of your last 30 days of email interactions are with a single relationship cluster. Consider diversifying outreach.",
        "contact_id": None,
        "contact_name": None,
        "metadata": {"community_id": result[0], "pct": round(pct, 2), "cluster_interactions": int(result[1])},
    }]


def _detect_introduction_chain_unused(db, org_id: str) -> List[Dict]:
    """Contacts referred but never directly contacted."""
    results = db.execute(
        text("""
            SELECT c.id, c.name, c.company, c.entity_type,
                c2.name AS introduced_by_name,
                EXTRACT(DAY FROM NOW() - c.created_at)::int AS days_since_intro
            FROM contacts c
            JOIN contacts c2 ON c.introduced_by = c2.id
            WHERE c.org_id = :org_id
            AND c.created_at < NOW() - INTERVAL '7 days'
            AND (c.is_archived = FALSE OR c.is_archived IS NULL)
            AND NOT EXISTS (
                SELECT 1 FROM interactions i
                WHERE i.contact_id = c.id AND i.direction = 'outbound'
            )
            ORDER BY c.created_at ASC
            LIMIT 5
        """),
        {"org_id": org_id}
    ).fetchall()

    return [{
        "insight_type": "relationship",
        "priority": "P2",
        "category": "unused_introduction",
        "title": f"{r[1]} — introduced by {r[4]} but never contacted ({int(r[5] or 0)} days)",
        "detail": f"{r[1]} ({r[2] or 'Unknown'}) was introduced by {r[4]} {int(r[5] or 0)} days ago but you have never sent an outbound message. Don't let warm introductions go cold.",
        "contact_id": str(r[0]),
        "contact_name": r[1],
        "metadata": {"introduced_by": r[4], "days_since_intro": int(r[5] or 0), "entity_type": r[3]},
    } for r in results]


def _detect_total_interaction_milestone(db, org_id: str) -> List[Dict]:
    """Detect contacts that just crossed an interaction milestone (10, 25, 50, 100)."""
    results = db.execute(
        text("""
            SELECT id, name, company, interaction_count, entity_type
            FROM contacts
            WHERE org_id = :org_id
            AND interaction_count IN (10, 25, 50, 100)
            AND (is_archived = FALSE OR is_archived IS NULL)
            AND last_interaction_at >= NOW() - INTERVAL '7 days'
        """),
        {"org_id": org_id}
    ).fetchall()

    return [{
        "insight_type": "relationship",
        "priority": "P3",
        "category": "interaction_milestone",
        "title": f"{r[1]} — {int(r[3] or 0)} interaction milestone reached",
        "detail": f"You've now had {int(r[3] or 0)} interactions with {r[1]} ({r[2] or 'Unknown'}). This is a significant relationship depth milestone.",
        "contact_id": str(r[0]),
        "contact_name": r[1],
        "metadata": {"milestone": int(r[3] or 0), "entity_type": r[4]},
    } for r in results]


NETWORK_DETECTORS = [
    _detect_no_follow_up_investors,
    _detect_network_health_summary,
    _detect_investor_cluster_no_update,
    _detect_new_contacts_no_followup,
    _detect_advisor_dormant,
    _detect_customer_churn_risk,
    _detect_candidate_pipeline_stall,
    _detect_high_interaction_low_signal,
    _detect_media_contact_cold,
    _detect_partner_stall,
    _detect_top_referrer_not_engaged,
    _detect_cluster_concentration_risk,
    _detect_introduction_chain_unused,
    _detect_total_interaction_milestone,
]
