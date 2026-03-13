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


def get_recent_interactions(db, contact_id: str, limit: int = 5) -> List[Dict]:
    """
    Get recent interactions for a contact.

    Args:
        db: Database session
        contact_id: Contact UUID
        limit: Number of interactions to return

    Returns:
        List of interaction dicts
    """
    results = db.execute(
        text(
            """
            SELECT 
                subject, summary, sentiment, intent,
                commitments, topics, interaction_at, direction
            FROM interactions
            WHERE contact_id = :contact_id
            ORDER BY interaction_at DESC
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
                "commitments": row[4] or [],
                "topics": row[5] or [],
                "interaction_at": row[6],
                "direction": row[7],
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


def build_context_bundle(
    db, org_id: str, entity_name: str, situation: str = None
) -> Dict:
    """
    Build complete context bundle for an entity.

    Args:
        db: Database session
        org_id: Organization UUID
        entity_name: Name of the person/company
        situation: Optional situation context (for future use)

    Returns:
        Dict with entity details and context_for_agent
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

    # 3. Build entity details
    entity = {
        "name": contact["name"],
        "company": contact["company"],
        "relationship_stage": contact["relationship_stage"] or "UNKNOWN",
        "last_interaction": format_time_ago(contact["last_interaction_at"]),
        "sentiment_trend": get_sentiment_trend(contact["sentiment_avg"]),
        "communication_style": contact["communication_style"]
        or "Unknown communication style",
        "topics_of_interest": contact["topics_aggregate"][:5],  # Top 5 topics
        "open_commitments": get_open_commitments(interactions),
        "interaction_count": contact["interaction_count"] or 0,
    }

    # 4. Calculate confidence score
    confidence = calculate_confidence_score(contact, interactions)

    # 5. Generate context_for_agent paragraph (will implement next)
    context_for_agent = generate_context_paragraph(contact, interactions, entity)

    return {
        "entity": entity,
        "match_confidence": contact.get("match_confidence", 1.0),
        "matched_from": contact.get("matched_from", entity_name),
        "context_for_agent": context_for_agent,
        "confidence": confidence,
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
    contact: Dict, interactions: List[Dict], entity: Dict
) -> str:
    """
    Generate the context_for_agent paragraph - the key output.
    This paragraph can be directly prepended to any LLM prompt.

    Week 6 improvement: More structured, actionable context.
    """
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

    # Line 2: Relationship context with specificity
    stage = entity["relationship_stage"]
    last_interaction = entity["last_interaction"]
    sentiment = entity["sentiment_trend"]
    interaction_count = entity["interaction_count"]

    if stage != "UNKNOWN":
        parts.append(
            f"Relationship: {stage}. You've exchanged {interaction_count} messages. Last contact {last_interaction}."
        )
    else:
        parts.append(
            f"{interaction_count} interactions total. Last contact {last_interaction}."
        )

    # Line 3: Sentiment with context
    if sentiment == "positive":
        parts.append("Recent conversations have been positive and engaged.")
    elif sentiment == "negative":
        parts.append(
            "Recent interactions show some friction or concern. Tread carefully."
        )

    # Line 4: Topics - be specific
    topics = entity["topics_of_interest"]
    if topics and len(topics) > 0:
        if len(topics) == 1:
            parts.append(f"Main topic discussed: {topics[0]}.")
        else:
            topics_str = ", ".join(topics[:3])
            parts.append(f"Primary topics: {topics_str}.")

    # Line 5: Open commitments - critical for follow-ups
    commitments = entity["open_commitments"]
    if commitments and len(commitments) > 0:
        if len(commitments) == 1:
            parts.append(f"⚠️ Open commitment: {commitments[0]}")
        else:
            parts.append(
                f"⚠️ {len(commitments)} open commitments. Most recent: {commitments[0]}"
            )

    # Line 6: Communication preferences
    comm_style = contact.get("communication_style")
    if comm_style and comm_style != "Unknown communication style":
        parts.append(f"Prefers: {comm_style}.")

    # Line 7: Last interaction summary with actionable detail
    if interactions and len(interactions) > 0:
        last = interactions[0]
        if last.get("summary"):
            summary = last["summary"][:200]  # Slightly longer for more context
            direction = last.get("direction", "").lower()
            if direction == "inbound":
                parts.append(f"They last said: {summary}")
            else:
                parts.append(f"You last said: {summary}")

        # Add intent if available
        intent = last.get("intent")
        if intent and intent not in ["other", "unknown"]:
            parts.append(f"Intent: {intent}.")

    # Line 8: Relationship health indicator
    if stage == "AT_RISK":
        parts.append("⚠️ ALERT: Relationship at risk. Follow up urgently.")
    elif stage == "DORMANT":
        parts.append("Note: No recent contact. Consider a warm re-engagement.")

    return " ".join(parts)
