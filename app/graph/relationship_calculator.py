"""
Relationship Stage Calculator
Determines relationship health based on interaction patterns
"""

from datetime import datetime, timezone, timedelta
from sqlalchemy import text
from typing import Dict, List
import json


# Relationship stages as per MVP
RELATIONSHIP_STAGES = {
    "ACTIVE": "Last interaction < 7 days + positive sentiment",
    "WARM": "Last interaction 7-30 days",
    "DORMANT": "Last interaction 30-60 days",
    "COLD": "Last interaction > 60 days",
    "AT_RISK": "Sentiment avg < -0.3 (overrides all above)",
}

# Source weights (Gmail only for V1)
SOURCE_WEIGHTS = {
    "gmail": 0.35,
}

# Decay halflife in days
CONFIDENCE_HALFLIFE_DAYS = 30

# EWMA smoothing factor
EWMA_ALPHA = 0.3  # Recent emails get 30% weight, previous history gets 70%


def calculate_ewma_sentiment(interactions: List[Dict]) -> float:
    """
    Calculate Exponential Weighted Moving Average of sentiment.
    Recent interactions matter 3x more than old ones.

    Args:
        interactions: List of interaction dicts with 'sentiment' and 'interaction_at'

    Returns:
        float: EWMA sentiment score (-1.0 to 1.0)
    """
    if not interactions:
        return 0.0

    # Sort by date ascending
    sorted_interactions = sorted(interactions, key=lambda x: x["interaction_at"])

    ewma = 0.0

    for interaction in sorted_interactions:
        sentiment = interaction.get("sentiment", 0.0)
        ewma = EWMA_ALPHA * sentiment + (1 - EWMA_ALPHA) * ewma

    return round(ewma, 3)


def calculate_sentiment_trend(interactions: List[Dict], window: int = 5) -> str:
    """
    Calculate whether sentiment is IMPROVING, STABLE, or DECLINING.
    Compares last N interactions against previous N interactions.

    Args:
        interactions: List of interaction dicts
        window: Number of recent interactions to compare

    Returns:
        str: IMPROVING, STABLE, or DECLINING
    """
    if len(interactions) < window * 2:
        # Not enough data, return STABLE as default
        return "STABLE"

    sorted_interactions = sorted(interactions, key=lambda x: x["interaction_at"])

    recent = sorted_interactions[-window:]
    previous = sorted_interactions[-window * 2 : -window]

    if not recent or not previous:
        return "STABLE"

    recent_avg = sum(i.get("sentiment", 0.0) for i in recent) / len(recent)
    previous_avg = sum(i.get("sentiment", 0.0) for i in previous) / len(previous)

    delta = recent_avg - previous_avg

    if delta > 0.15:
        return "IMPROVING"
    elif delta < -0.15:
        return "DECLINING"
    else:
        return "STABLE"


def calculate_confidence_score(
    interaction_count: int, days_since_last: int, sources: List[str] = None
) -> float:
    """
    Calculate confidence in relationship data quality.
    Based on: volume, recency, and data sources.

    Args:
        interaction_count: Total interactions with contact
        days_since_last: Days since last interaction
        sources: List of sources (gmail, calendar, etc.)

    Returns:
        float: Confidence score (0.0 to 1.0)
    """
    if sources is None:
        sources = ["gmail"]

    # Base score from sources
    base_score = sum(SOURCE_WEIGHTS.get(source, 0.1) for source in sources)

    # Recency decay
    recency_factor = 0.5 ** (days_since_last / CONFIDENCE_HALFLIFE_DAYS)

    # Volume multiplier
    if interaction_count >= 20:
        volume_mult = 1.15
    elif interaction_count >= 10:
        volume_mult = 1.05
    elif interaction_count >= 5:
        volume_mult = 1.00
    elif interaction_count >= 2:
        volume_mult = 0.80
    else:
        volume_mult = 0.55

    # Recency bucket
    if days_since_last > 90:
        recency_mult = 0.75
    elif days_since_last > 30:
        recency_mult = 0.90
    else:
        recency_mult = 1.00

    final_score = base_score * recency_factor * volume_mult * recency_mult

    return round(min(1.0, final_score), 2)


def calculate_relationship_stage(
    last_interaction_at: datetime, sentiment: float, now: datetime = None
) -> str:
    """
    Calculate relationship stage based on simple rules.
    Uses EWMA sentiment (passed as `sentiment`) — not simple average.

    Rules:
    - Last interaction < 7 days + positive EWMA sentiment = ACTIVE
    - Last interaction 7-30 days = WARM
    - Last interaction 30-60 days = DORMANT
    - Last interaction > 60 days = COLD
    - EWMA sentiment < -0.3 = AT_RISK (overrides all above)

    Args:
        last_interaction_at: DateTime of last interaction
        sentiment: EWMA sentiment score (-1.0 to 1.0) — use sentiment_ewma, not sentiment_avg
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

    # AT_RISK overrides everything (uses EWMA, not simple avg)
    if sentiment < -0.3:
        return "AT_RISK"

    # Calculate days since last interaction
    days_since = (now - last_interaction_at).days

    # Apply stage rules
    if days_since < 7 and sentiment > 0:
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
    Now includes EWMA sentiment, trend detection, and confidence scoring.

    Args:
        db: Database session
        contact_id: UUID of the contact

    Returns:
        Dict with updated metrics including sentiment_ewma, sentiment_trend, confidence
    """
    # Get all interactions for this contact with sentiment details
    result = db.execute(
        text(
            """
            SELECT 
                COUNT(*) as interaction_count,
                AVG(sentiment) as sentiment_avg,
                MIN(interaction_at) as first_interaction,
                MAX(interaction_at) as last_interaction,
                ARRAY_AGG(
                    json_build_object('sentiment', sentiment, 'interaction_at', interaction_at)
                    ORDER BY interaction_at DESC
                ) as interactions_data,
                ARRAY(
                    SELECT DISTINCT topic 
                    FROM interactions i2, unnest(i2.topics) as topic
                    WHERE i2.contact_id = :contact_id AND i2.topics IS NOT NULL
                    LIMIT 10
                ) as all_topics
            FROM interactions
            WHERE contact_id = :contact_id
        """
        ),
        {"contact_id": contact_id},
    ).fetchone()

    if not result or result[0] == 0:
        # No interactions, set to COLD with low confidence
        db.execute(
            text(
                """
                UPDATE contacts
                SET relationship_stage = 'COLD',
                    sentiment_avg = 0.0,
                    sentiment_ewma = 0.0,
                    sentiment_trend = 'STABLE',
                    interaction_count = 0,
                    confidence_score = 0.1
                WHERE id = :contact_id
            """
            ),
            {"contact_id": contact_id},
        )
        db.commit()
        return {"stage": "COLD", "confidence": 0.1}

    interaction_count = result[0]
    sentiment_avg = float(result[1] or 0.0)
    first_interaction = result[2]
    last_interaction = result[3]
    interactions_data = result[4] or []
    all_topics = result[5] or []

    # Parse timestamps from JSON (they come back as ISO format strings)
    parsed_interactions = []
    for i in interactions_data:
        try:
            if isinstance(i.get("interaction_at"), str):
                # Parse ISO format timestamp string
                ts_str = i.get("interaction_at")
                # Handle both formats: with and without 'Z'
                if ts_str.endswith("Z"):
                    ts_str = ts_str[:-1] + "+00:00"
                ts = datetime.fromisoformat(ts_str)
            else:
                ts = i.get("interaction_at")

            parsed_interactions.append(
                {"sentiment": i.get("sentiment", 0.0), "interaction_at": ts}
            )
        except Exception as e:
            print(f"⚠️ Skipping interaction with bad timestamp: {e}")
            continue

    # Calculate enhanced metrics
    sentiment_ewma = calculate_ewma_sentiment(parsed_interactions)
    sentiment_trend = calculate_sentiment_trend(parsed_interactions)

    days_since = (
        (datetime.now(timezone.utc) - last_interaction).days
        if last_interaction
        else 999
    )
    confidence = calculate_confidence_score(
        interaction_count, days_since, sources=["gmail"]
    )

    # Calculate relationship stage
    stage = calculate_relationship_stage(last_interaction, sentiment_ewma)

    # Store sentiment history (keep last 10)
    sentiment_history = json.dumps(
        [
            {
                "timestamp": (
                    i.get("interaction_at").isoformat()
                    if hasattr(i.get("interaction_at"), "isoformat")
                    else str(i.get("interaction_at", ""))
                ),
                "sentiment": i.get("sentiment", 0.0),
            }
            for i in parsed_interactions[:10]
        ]
    )

    # Update contact with all new fields
    db.execute(
        text(
            """
            UPDATE contacts
            SET relationship_stage = :stage,
                sentiment_avg = :sentiment_avg,
                sentiment_ewma = :sentiment_ewma,
                sentiment_trend = :sentiment_trend,
                confidence_score = :confidence,
                first_interaction_at = :first_interaction,
                last_interaction_at = :last_interaction,
                interaction_count = :interaction_count,
                topics_aggregate = :topics,
                sentiment_history = :sentiment_history,
                metadata = jsonb_set(
                    COALESCE(metadata, '{}'::jsonb),
                    '{last_recalc_at}',
                    to_jsonb(NOW())
                )
            WHERE id = :contact_id
        """
        ),
        {
            "contact_id": contact_id,
            "stage": stage,
            "sentiment_avg": sentiment_avg,
            "sentiment_ewma": sentiment_ewma,
            "sentiment_trend": sentiment_trend,
            "confidence": confidence,
            "first_interaction": first_interaction,
            "last_interaction": last_interaction,
            "interaction_count": interaction_count,
            "topics": all_topics,
            "sentiment_history": sentiment_history,
        },
    )
    db.commit()

    return {
        "stage": stage,
        "sentiment_avg": sentiment_avg,
        "sentiment_ewma": sentiment_ewma,
        "sentiment_trend": sentiment_trend,
        "confidence": confidence,
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
