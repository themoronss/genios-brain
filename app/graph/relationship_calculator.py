"""
Relationship Stage Calculator
Determines relationship health based on interaction patterns
"""

from datetime import datetime, timezone, timedelta
from sqlalchemy import text
from typing import Dict


# Relationship stages as per MVP
RELATIONSHIP_STAGES = {
    "ACTIVE": "Last interaction < 7 days + positive sentiment",
    "WARM": "Last interaction 7-30 days",
    "DORMANT": "Last interaction 30-60 days",
    "COLD": "Last interaction > 60 days",
    "AT_RISK": "Sentiment avg < -0.3 (overrides all above)",
}


def calculate_relationship_stage(
    last_interaction_at: datetime, sentiment_avg: float, now: datetime = None
) -> str:
    """
    Calculate relationship stage based on simple rules from MVP.

    Rules:
    - Last interaction < 7 days + positive sentiment = ACTIVE
    - Last interaction 7-30 days = WARM
    - Last interaction 30-60 days = DORMANT
    - Last interaction > 60 days = COLD
    - Sentiment avg < -0.3 = AT_RISK (overrides all above)

    Args:
        last_interaction_at: DateTime of last interaction
        sentiment_avg: Average sentiment score (-1.0 to 1.0)
        now: Current datetime (defaults to now)

    Returns:
        str: Relationship stage (ACTIVE, WARM, DORMANT, COLD, AT_RISK)
    """
    if now is None:
        now = datetime.now(timezone.utc)

    # If no last interaction, default to COLD
    if last_interaction_at is None:
        return "COLD"

    # Make timezone-aware if needed
    if last_interaction_at.tzinfo is None:
        last_interaction_at = last_interaction_at.replace(tzinfo=timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)

    # AT_RISK overrides everything
    if sentiment_avg < -0.3:
        return "AT_RISK"

    # Calculate days since last interaction
    days_since = (now - last_interaction_at).days

    # Apply rules
    if days_since < 7 and sentiment_avg > 0:
        return "ACTIVE"
    elif days_since < 30:
        return "WARM"
    elif days_since < 60:
        return "DORMANT"
    else:
        return "COLD"


def recalculate_contact_relationship(db, contact_id: str) -> Dict:
    """
    Recalculate relationship metrics for a single contact.

    Args:
        db: Database session
        contact_id: UUID of the contact

    Returns:
        Dict with updated metrics
    """
    # Get all interactions for this contact
    result = db.execute(
        text(
            """
            SELECT 
                COUNT(*) as interaction_count,
                AVG(sentiment) as sentiment_avg,
                MIN(interaction_at) as first_interaction,
                MAX(interaction_at) as last_interaction,
                ARRAY(
                    SELECT DISTINCT topic 
                    FROM interactions i2, unnest(i2.topics) as topic
                    WHERE i2.contact_id = :contact_id AND i2.topics IS NOT NULL
                ) as all_topics
            FROM interactions
            WHERE contact_id = :contact_id
        """
        ),
        {"contact_id": contact_id},
    ).fetchone()

    if not result or result[0] == 0:
        # No interactions, set to COLD
        db.execute(
            text(
                """
                UPDATE contacts
                SET relationship_stage = 'COLD',
                    sentiment_avg = 0.0,
                    interaction_count = 0
                WHERE id = :contact_id
            """
            ),
            {"contact_id": contact_id},
        )
        db.commit()
        return {"stage": "COLD"}

    interaction_count = result[0]
    sentiment_avg = float(result[1] or 0.0)
    first_interaction = result[2]
    last_interaction = result[3]
    all_topics = result[4] or []

    # Calculate relationship stage
    stage = calculate_relationship_stage(last_interaction, sentiment_avg)

    # Update contact
    db.execute(
        text(
            """
            UPDATE contacts
            SET relationship_stage = :stage,
                sentiment_avg = :sentiment_avg,
                first_interaction_at = :first_interaction,
                last_interaction_at = :last_interaction,
                interaction_count = :interaction_count,
                topics_aggregate = :topics
            WHERE id = :contact_id
        """
        ),
        {
            "contact_id": contact_id,
            "stage": stage,
            "sentiment_avg": sentiment_avg,
            "first_interaction": first_interaction,
            "last_interaction": last_interaction,
            "interaction_count": interaction_count,
            "topics": all_topics[:10],  # Keep top 10 topics
        },
    )
    db.commit()

    return {
        "stage": stage,
        "sentiment_avg": sentiment_avg,
        "interaction_count": interaction_count,
        "last_interaction": last_interaction,
    }


def recalculate_all_relationships(db, org_id: str = None):
    """
    Recalculate relationship stages for all contacts.
    Run this nightly as a cron job.

    Args:
        db: Database session
        org_id: Optional org_id to limit recalculation
    """
    # Get all contacts
    if org_id:
        contacts = db.execute(
            text("SELECT id FROM contacts WHERE org_id = :org_id"), {"org_id": org_id}
        ).fetchall()
    else:
        contacts = db.execute(text("SELECT id FROM contacts")).fetchall()

    updated_count = 0

    for contact in contacts:
        contact_id = contact[0]
        try:
            recalculate_contact_relationship(db, contact_id)
            updated_count += 1
        except Exception as e:
            print(f"Error updating contact {contact_id}: {e}")

    print(f"✓ Recalculated {updated_count} contacts")
    return updated_count
