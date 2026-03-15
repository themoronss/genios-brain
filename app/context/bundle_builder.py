"""
Week 3: Context Bundle Builder
Builds rich context bundles for any entity in the relationship graph
"""

from sqlalchemy import text
from datetime import datetime, timezone
from typing import Dict, List, Optional
from rapidfuzz import process, fuzz


def _row_to_dict(result) -> Dict:
    return {
        "id": result[0],
        "name": result[1],
        "email": result[2],
        "company": result[3],
        "relationship_stage": result[4],
        "sentiment_avg": result[5],
        "last_interaction_at": result[6],
        "first_interaction_at": result[7],
        "interaction_count": result[8],
        "topics_aggregate": result[9] or [],
        "communication_style": result[10],
        "entity_type": result[11],
    }


def get_contact_by_name(db, org_id: str, entity_name: str) -> Optional[Dict]:
    """
    Find a contact by name with fuzzy matching.
    """
    try:
        # Try exact match first (case insensitive, trimmed)
        result = db.execute(
            text(
                """
                SELECT 
                    id, name, email, company, relationship_stage,
                    sentiment_avg, last_interaction_at, first_interaction_at,
                    interaction_count, topics_aggregate, communication_style,
                    entity_type
                FROM contacts
                WHERE org_id = :org_id 
                AND (TRIM(LOWER(name)) = TRIM(LOWER(:name)) OR LOWER(email) LIKE LOWER(:email_pattern))
                LIMIT 1
            """
            ),
            {
                "org_id": org_id,
                "name": entity_name,
                "email_pattern": f"%{entity_name.lower()}%",
            },
        ).fetchone()

        if result:
            res = _row_to_dict(result)
            res["match_confidence"] = 1.0
            res["matched_from"] = entity_name
            return res

        # Try fuzzy match
        candidates = db.execute(
            text("SELECT id, name, email FROM contacts WHERE org_id = :org_id"),
            {"org_id": org_id},
        ).fetchall()

        if candidates:
            choices = {str(row[0]): row[1] for row in candidates if row[1]}
            best_match = process.extractOne(
                entity_name, choices, scorer=fuzz.WRatio, score_cutoff=70.0
            )

            email_choices = {str(row[0]): row[2] for row in candidates if row[2]}
            best_email_match = None
            if email_choices:
                best_email_match = process.extractOne(
                    entity_name, email_choices, scorer=fuzz.WRatio, score_cutoff=70.0
                )

            best = best_match
            if best_email_match and (not best or best_email_match[1] > best[1]):
                best = best_email_match

            if best:
                matched_id = best[2]
                confidence = best[1] / 100.0

                full_result = db.execute(
                    text(
                        """
                        SELECT 
                            id, name, email, company, relationship_stage,
                            sentiment_avg, last_interaction_at, first_interaction_at,
                            interaction_count, topics_aggregate, communication_style,
                            entity_type
                        FROM contacts
                        WHERE id = :id AND org_id = :org_id
                        """
                    ),
                    {"id": matched_id, "org_id": org_id},
                ).fetchone()

                if full_result:
                    res = _row_to_dict(full_result)
                    res["match_confidence"] = round(confidence, 2)
                    res["matched_from"] = entity_name
                    return res

        return None
    except Exception as e:
        print(f"Database error in get_contact_by_name: {str(e)}")
        return None


def get_recent_interactions(db, contact_id: str, limit: int = 10) -> List[Dict]:
    """
    Get recent interactions for a contact with enhanced engagement signals.
    Returns up to 10 interactions sorted by weight_score DESC so the most
    important interactions (replies, commitments) surface first.
    """
    results = db.execute(
        text(
            """
            SELECT 
                subject, summary, sentiment, intent,
                topics, interaction_at, direction, interaction_type,
                weight_score, reply_time_hours
            FROM interactions
            WHERE contact_id = :contact_id
            ORDER BY weight_score DESC NULLS LAST, interaction_at DESC
            LIMIT :limit
        """
        ),
        {"contact_id": contact_id, "limit": limit},
    ).fetchall()

    interactions = []
    for row in results:
        interactions.append(
            {
                "subject": row[0],
                "summary": row[1],
                "sentiment": row[2],
                "intent": row[3],
                "topics": row[4] or [],
                "interaction_at": row[5],
                "direction": row[6],
                "interaction_type": row[7],
                "weight_score": row[8],
                "reply_time_hours": row[9],
            }
        )

    return interactions


def format_time_ago(dt: datetime) -> str:
    """Format datetime as 'X days ago'."""
    if dt is None:
        return "never"

    now = datetime.now(timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)

    diff = now - dt
    days = diff.days

    if days == 0:
        hours = diff.seconds // 3600
        if hours == 0:
            return "just now"
        return f"{hours} hour{'s' if hours != 1 else ''} ago"
    elif days == 1:
        return "1 day ago"
    elif days < 7:
        return f"{days} days ago"
    elif days < 30:
        weeks = days // 7
        return f"{weeks} week{'s' if weeks != 1 else ''} ago"
    elif days < 365:
        months = days // 30
        return f"{months} month{'s' if months != 1 else ''} ago"
    else:
        years = days // 365
        return f"{years} year{'s' if years != 1 else ''} ago"


def get_sentiment_trend(sentiment_avg: float) -> str:
    """Convert sentiment score to human-readable trend."""
    if sentiment_avg is None or sentiment_avg == 0:
        return "neutral"
    elif sentiment_avg > 0.3:
        return "positive"
    elif sentiment_avg < -0.3:
        return "negative"
    else:
        return "neutral"


def get_open_commitments(interactions: List[Dict]) -> List[str]:
    """Extract all commitments from recent interactions."""
    commitments = []
    for interaction in interactions:
        if interaction.get("commitments"):
            commitments.extend(interaction["commitments"])
    return commitments[:5]  # Limit to 5 most recent


def get_open_commitments_detailed(db, contact_id: str) -> List[Dict]:
    """
    Get open and soft commitments from commitments table with detailed lifecycle info.
    Returns OPEN + OVERDUE (firm) and SOFT (tentative) commitments ranked by due date.
    """
    try:
        results = db.execute(
            text(
                """
                SELECT 
                    commit_text, owner, due_date, status,
                    EXTRACT(DAY FROM (due_date - NOW())) as days_until_due,
                    created_at
                FROM commitments
                WHERE contact_id = :contact_id 
                    AND status IN ('OPEN', 'OVERDUE', 'SOFT')
                ORDER BY 
                    CASE status WHEN 'OVERDUE' THEN 0 WHEN 'OPEN' THEN 1 ELSE 2 END,
                    due_date ASC NULLS LAST,
                    created_at DESC
                LIMIT 10
            """
            ),
            {"contact_id": contact_id},
        ).fetchall()

        commitments = []
        for row in results:
            days_until_due = row[4]
            is_overdue = days_until_due is not None and days_until_due < 0
            status = row[3]

            commitments.append(
                {
                    "text": row[0],
                    "owner": row[1],
                    "due_date": str(row[2]) if row[2] else None,
                    "status": status,
                    "is_overdue": is_overdue,
                    "is_soft": status == "SOFT",
                    "days_until_due": int(days_until_due) if days_until_due else None,
                    "created_at": str(row[5]),
                }
            )

        return commitments
    except Exception as e:
        print(f"⚠️ Error fetching commitments: {e}")
        return []


def get_interaction_type_summary(interactions: List[Dict]) -> Dict:
    """
    Summarize interaction types and engagement levels from recent interactions.
    """
    type_counts = {
        "email_reply": 0,
        "email_one_way": 0,
        "commitment": 0,
        "meeting": 0,
        "other": 0,
    }

    for interaction in interactions:
        itype = interaction.get("interaction_type", "other")
        if itype in type_counts:
            type_counts[itype] += 1

    return type_counts


# ── Fix A+B: Escalation + Action Recommendation ─────────────────────────────

ESCALATION_TOPICS = {
    "investor", "board", "performance", "legal", "compliance",
    "acquisition", "term sheet", "due diligence", "equity",
    "fundraising", "series a", "series b", "investment",
}


def determine_action_recommendation(contact: Dict, entity: Dict) -> Dict:
    """
    Determine what action the calling agent should take based on relationship health.
    Returns action_recommendation and escalation_recommended as top-level signals
    so agents don't need to parse the context paragraph to decide.

    action_recommendation values:
      'block'    - DO NOT contact. Relationship is at risk. Escalate to human.
      'escalate' - Draft with extreme care. Must be reviewed by human before sending.
      'warn'     - Relationship needs attention. Use cautious tone.
      'proceed'  - Normal contact. Agent can draft and send.

    Returns:
        Dict with 'action_recommendation', 'escalation_recommended', 'action_reason'
    """
    stage = entity.get("relationship_stage", "")
    sentiment_ewma = entity.get("sentiment_ewma", 0.0)
    topics = [t.lower() for t in entity.get("topics_of_interest", [])]
    entity_type = (contact.get("entity_type") or "").upper()
    overdue = entity.get("overdue_commitments", 0)

    # Rule 1: AT_RISK → hard block
    if stage == "AT_RISK" or sentiment_ewma < -0.5:
        return {
            "action_recommendation": "block",
            "escalation_recommended": True,
            "action_reason": "Relationship is AT_RISK or sentiment strongly negative. Do not auto-contact.",
        }

    # Rule 2: Investor/board topics + ACTIVE relationship → must escalate
    has_sensitive_topic = any(
        any(et in t for et in ESCALATION_TOPICS) for t in topics
    )
    is_investor = entity_type in ("INVESTOR", "BOARD")

    if (has_sensitive_topic or is_investor) and stage in ("ACTIVE", "WARM"):
        return {
            "action_recommendation": "escalate",
            "escalation_recommended": True,
            "action_reason": "Investor or board-related contact on sensitive topic. Human review required before sending.",
        }

    # Rule 3: Overdue commitments → warn
    if overdue > 0:
        return {
            "action_recommendation": "warn",
            "escalation_recommended": False,
            "action_reason": f"You have {overdue} overdue commitment(s) with this contact. Address before drafting new outreach.",
        }

    # Rule 4: DORMANT + declining → warn
    if stage == "DORMANT" and entity.get("sentiment_trend") == "DECLINING":
        return {
            "action_recommendation": "warn",
            "escalation_recommended": False,
            "action_reason": "Relationship is dormant and declining. Use re-engagement tone.",
        }

    # Default: proceed normally
    return {
        "action_recommendation": "proceed",
        "escalation_recommended": False,
        "action_reason": "Relationship is healthy. Agent can draft and send.",
    }


def build_context_bundle(
    db, org_id: str, entity_name: str, situation: str = None
) -> Dict:
    """
    Build complete context bundle for an entity.
    Enhanced with EWMA sentiment, trends, confidence, and commitment tracking.

    Args:
        db: Database session
        org_id: Organization UUID
        entity_name: Name of the person/company
        situation: Optional situation context

    Returns:
        Dict with entity details, confidence score, and context_for_agent
    """
    # 1. Find the contact
    contact = get_contact_by_name(db, org_id, entity_name)

    if not contact:
        return {
            "error": "Contact not found",
            "entity_name": entity_name,
            "context_for_agent": f"No information found for {entity_name}.",
            "confidence": 0.0,
        }

    # 2. Get recent interactions
    interactions = get_recent_interactions(db, contact["id"], limit=5)

    # 3. Get open commitments with lifecycle info
    open_commitments = get_open_commitments_detailed(db, contact["id"])

    # 4. Build entity details with enhanced metrics
    entity = {
        "name": contact["name"],
        "email": contact.get("email"),
        "company": contact["company"],
        "relationship_stage": contact["relationship_stage"] or "UNKNOWN",
        "confidence": contact.get("confidence_score", 0.5),
        "sentiment_avg": round(contact.get("sentiment_avg", 0.0), 2),
        "sentiment_ewma": round(contact.get("sentiment_ewma", 0.0), 2),
        "sentiment_trend": contact.get("sentiment_trend", "STABLE"),
        "last_interaction": format_time_ago(contact["last_interaction_at"]),
        "communication_style": contact["communication_style"] or "Unknown",
        "topics_of_interest": contact["topics_aggregate"][:5],
        "open_commitments": len(open_commitments),
        "open_commitments_detail": open_commitments,
        "overdue_commitments": sum(1 for c in open_commitments if c.get("is_overdue")),
        "interaction_count": contact["interaction_count"] or 0,
        "interaction_types": get_interaction_type_summary(interactions),
    }

    # 5. Generate rich context_for_agent paragraph
    context_for_agent = generate_context_paragraph(
        contact, interactions, entity, open_commitments
    )

    # Determine action recommendation and escalation signal
    action = determine_action_recommendation(contact, entity)

    return {
        "entity": entity,
        "match_confidence": contact.get("match_confidence", 1.0),
        "matched_from": contact.get("matched_from", entity_name),
        "recent_interactions": interactions,
        "context_for_agent": context_for_agent,
        "confidence": contact.get("confidence_score", 0.5),
        # ── Fix A+B: Action signals — agents check these first ──
        "action_recommendation": action["action_recommendation"],
        "escalation_recommended": action["escalation_recommended"],
        "action_reason": action["action_reason"],
        "data_quality": {
            "confidence_score": contact.get("confidence_score", 0.5),
            "last_recalc": contact.get("metadata", {}).get("last_recalc_at", "unknown"),
            "sources": ["gmail"],
        },
    }


def calculate_confidence_score(contact: Dict, interactions: List[Dict]) -> float:
    """
    Calculate confidence score based on data completeness.

    Returns: 0.0 to 1.0
    """
    score = 0.0

    # Has basic info (30%)
    if contact.get("email"):
        score += 0.15
    if contact.get("company"):
        score += 0.15

    # Has interaction data (40%)
    if interactions:
        score += 0.2
        if len(interactions) >= 3:
            score += 0.2

    # Has relationship data (30%)
    if contact.get("relationship_stage") and contact["relationship_stage"] != "unknown":
        score += 0.15
    if contact.get("topics_aggregate") and len(contact["topics_aggregate"]) > 0:
        score += 0.15

    return round(min(score, 1.0), 2)


def generate_context_paragraph(
    contact: Dict,
    interactions: List[Dict],
    entity: Dict,
    open_commitments: List[Dict] = None,
) -> str:
    """
    Generate the context_for_agent paragraph - the key output.
    Enhanced with EWMA sentiment, trends, confidence, and commitment details.
    This paragraph can be directly prepended to any LLM prompt.
    """
    if open_commitments is None:
        open_commitments = []

    parts = []

    # Line 1: Identity and role
    name = contact["name"]
    company = contact["company"]
    entity_type = contact.get("entity_type", "")

    if company and entity_type:
        parts.append(f"{name} from {company} ({entity_type}).")
    elif company:
        parts.append(f"{name} from {company}.")
    else:
        parts.append(f"{name}.")

    # Line 2: Relationship context with confidence indicator
    stage = entity["relationship_stage"]
    last_interaction = entity["last_interaction"]
    interaction_count = entity["interaction_count"]
    confidence = entity.get("confidence", 0.5)

    confidence_label = (
        "HIGH" if confidence >= 0.75 else "MEDIUM" if confidence >= 0.5 else "LOW"
    )

    if stage != "UNKNOWN":
        parts.append(
            f"Relationship: {stage}. {interaction_count} exchanges. Last contact {last_interaction}. "
            f"(Confidence: {confidence_label}, {confidence})"
        )
    else:
        parts.append(
            f"{interaction_count} interactions total. Last contact {last_interaction}."
        )

    # Line 3: Sentiment with EWMA and trend
    sentiment_ewma = entity.get("sentiment_ewma", 0.0)
    sentiment_trend = entity.get("sentiment_trend", "STABLE")

    if sentiment_trend == "IMPROVING":
        trend_signal = "📈 sentiment improving"
    elif sentiment_trend == "DECLINING":
        trend_signal = "📉 sentiment declining"
    else:
        trend_signal = "sentiment stable"

    if sentiment_ewma > 0.3:
        parts.append(f"Positive dynamics ({trend_signal}).")
    elif sentiment_ewma < -0.3:
        parts.append(f"⚠️ Negative dynamics ({trend_signal}). Use caution.")
    else:
        parts.append(f"Neutral tone ({trend_signal}).")

    # Line 4: Topics - be specific
    topics = entity["topics_of_interest"]
    if topics and len(topics) > 0:
        if len(topics) == 1:
            parts.append(f"Main topic: {topics[0]}.")
        else:
            topics_str = ", ".join(str(t) for t in topics[:3])
            parts.append(f"Primary topics: {topics_str}.")

    # Line 5: Commitments - CRITICAL for n8n/agent decision making
    firm_commitments = [c for c in open_commitments if not c.get("is_soft")]
    soft_commitments = [c for c in open_commitments if c.get("is_soft")]

    if firm_commitments:
        overdue = [c for c in firm_commitments if c.get("is_overdue")]

        if overdue:
            parts.append(f"⚠️ OVERDUE: {len(overdue)} commitment(s) not fulfilled.")
            for commit in overdue[:2]:
                due_str = f" (due {commit.get('due_date', '')[:10]}" if commit.get('due_date') else ""
                parts.append(f"  - {commit.get('text', 'Unknown')[:100]}{due_str}")
        else:
            parts.append(f"⏳ {len(firm_commitments)} open commitment(s).")
            for commit in firm_commitments[:2]:
                due_str = f" (due {commit.get('due_date', '')[:10]})" if commit.get('due_date') else ""
                parts.append(f"  - {commit.get('text', 'Unknown')[:100]}{due_str}")

    if soft_commitments:
        parts.append(f"~ {len(soft_commitments)} tentative promise(s) (follow up to confirm):")
        for commit in soft_commitments[:2]:
            parts.append(f"  - {commit.get('text', 'Unknown')[:100]}")

    # Line 6: Communication preferences
    comm_style = contact.get("communication_style")
    if comm_style and comm_style != "Unknown":
        parts.append(f"Prefers: {comm_style}.")

    # Line 7: Last interaction with direction
    if interactions and len(interactions) > 0:
        last = interactions[0]
        if last.get("summary"):
            summary = last["summary"][:200]
            direction = last.get("direction", "").lower()
            if direction == "inbound":
                parts.append(f"Last from them: {summary}")
            else:
                parts.append(f"Last from you: {summary}")

    # Line 8: Interaction type distribution
    interaction_types = entity.get("interaction_types", {})
    if interaction_types.get("email_reply", 0) > 0:
        parts.append(f"Engaged: {interaction_types.get('email_reply', 0)} replies.")

    # Line 9: Health alert
    if stage == "AT_RISK":
        parts.append("🚨 ALERT: Relationship at risk. Action required.")
    elif stage == "DORMANT" and entity.get("sentiment_trend") == "DECLINING":
        parts.append("⚠️ Dormant + declining. Consider warm re-engagement.")

    return " ".join(parts)
