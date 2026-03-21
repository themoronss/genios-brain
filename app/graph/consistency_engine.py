"""
Consistency Engine for GeniOS Context Scoring
Checks if multiple sources/interactions agree on facts about a contact.
"""

from sqlalchemy import text
from typing import Dict, List
import logging

logger = logging.getLogger(__name__)


def calculate_consistency_score(db, contact_id: str) -> float:
    """
    Calculate consistency score for a contact.
    Measures how consistently different interactions agree on facts (role, company, sentiment).

    Returns: 0.0-1.0 (>0.7 strong, 0.4-0.7 medium, <0.4 conflict)
    """
    scores = []

    # 1. Role consistency — check if entity_type stays the same across interactions
    role_data = db.execute(
        text("""
            SELECT
                ARRAY_AGG(DISTINCT intent) as intents,
                COUNT(DISTINCT intent) as intent_diversity
            FROM interactions
            WHERE contact_id = :contact_id AND intent IS NOT NULL AND intent != 'other'
        """),
        {"contact_id": contact_id}
    ).fetchone()

    if role_data and role_data[1]:
        # Fewer distinct intents = more consistent behavior
        intent_count = role_data[1] or 1
        role_consistency = max(0.3, 1.0 - (intent_count - 1) * 0.15)
        scores.append(role_consistency)

    # 2. Sentiment consistency — check if sentiment is stable vs wildly varying
    sentiment_data = db.execute(
        text("""
            SELECT
                STDDEV(sentiment) as sentiment_stddev,
                COUNT(*) as count
            FROM interactions
            WHERE contact_id = :contact_id AND sentiment IS NOT NULL
        """),
        {"contact_id": contact_id}
    ).fetchone()

    if sentiment_data and sentiment_data[0] is not None and sentiment_data[1] >= 2:
        stddev = float(sentiment_data[0])
        # Low stddev = consistent sentiment = higher score
        sentiment_consistency = max(0.2, 1.0 - stddev)
        scores.append(sentiment_consistency)

    # 3. Topic consistency — check if topics cluster tightly
    topic_data = db.execute(
        text("""
            SELECT COUNT(DISTINCT topic) as unique_topics, COUNT(*) as total_mentions
            FROM interactions i, unnest(i.topics) as topic
            WHERE i.contact_id = :contact_id AND i.topics IS NOT NULL
        """),
        {"contact_id": contact_id}
    ).fetchone()

    if topic_data and topic_data[1] and topic_data[1] > 0:
        unique_topics = topic_data[0] or 1
        total_mentions = topic_data[1] or 1
        # Ratio of unique to total — lower = more focused/consistent
        topic_ratio = unique_topics / total_mentions
        topic_consistency = max(0.3, 1.0 - topic_ratio * 0.5)
        scores.append(topic_consistency)

    if not scores:
        return 0.5  # Default for insufficient data

    return round(sum(scores) / len(scores), 3)


def calculate_authority_score(db, contact_id: str) -> float:
    """
    Calculate authority score for a contact.
    Based on source reliability and interaction directness.

    Direct email > CC > Inferred
    Gmail = 0.35 base, Manual = 1.0

    Returns: 0.0-1.0
    """
    result = db.execute(
        text("""
            SELECT
                COUNT(*) FILTER (WHERE direction = 'inbound') as direct_inbound,
                COUNT(*) FILTER (WHERE direction = 'outbound') as direct_outbound,
                COUNT(*) as total,
                COALESCE(source, 'gmail') as primary_source
            FROM interactions
            WHERE contact_id = :contact_id
            GROUP BY COALESCE(source, 'gmail')
        """),
        {"contact_id": contact_id}
    ).fetchall()

    if not result:
        return 0.3  # Minimum for any existing contact

    total_interactions = sum(r[2] for r in result)
    direct_interactions = sum(r[0] + r[1] for r in result)

    if total_interactions == 0:
        return 0.3

    # Source weight
    source_weights = {"gmail": 0.35, "calendar": 0.25, "manual": 1.0, "slack": 0.15}
    source_score = max(source_weights.get(r[3], 0.1) for r in result)

    # Directness ratio (direct / total)
    directness = direct_interactions / total_interactions

    # Combined: 60% source quality + 40% directness
    authority = source_score * 0.6 + directness * 0.4

    return round(min(1.0, authority), 3)
