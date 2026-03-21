"""
Relationship Stage Calculator
Determines relationship health based on interaction patterns
"""

from datetime import datetime, timezone, timedelta
from sqlalchemy import text
from typing import Dict, List
import json


# Relationship stages as per MVP V1 Detailing spec
RELATIONSHIP_STAGES = {
    "ACTIVE": "Last interaction < 14 days + positive sentiment + bidirectional",
    "WARM": "Last interaction < 30 days",
    "NEEDS_ATTENTION": "Last interaction 31-60 days OR no reply",
    "DORMANT": "Last interaction 31-60 days",
    "COLD": "Last interaction > 60 days",
    "AT_RISK": "Recent but negative sentiment (overrides all above)",
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
    last_interaction_at: datetime, sentiment: float, now: datetime = None,
    is_bidirectional: bool = True
) -> str:
    """
    Calculate relationship stage based on MVP V1 Detailing spec rules.
    Uses EWMA sentiment (passed as `sentiment`) — not simple average.

    Rules (updated per V1 Detailing):
    - AT_RISK: Recent but negative sentiment (overrides all)
    - ACTIVE: Last interaction < 14 days + positive sentiment + bidirectional
    - WARM: Last interaction < 30 days
    - NEEDS_ATTENTION: 31-60 days OR one-sided (no reply)
    - COLD: > 60 days

    Args:
        last_interaction_at: DateTime of last interaction
        sentiment: EWMA sentiment score (-1.0 to 1.0)
        now: Current datetime (defaults to now)
        is_bidirectional: Whether communication is two-way

    Returns:
        str: Relationship stage
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

    # Apply stage rules (updated thresholds per V1 Detailing)
    if days_since < 14 and sentiment > 0 and is_bidirectional:
        return "ACTIVE"
    elif days_since < 14 and sentiment > 0:
        return "WARM"  # Recent + positive but one-sided
    elif days_since < 30:
        return "WARM"
    elif days_since <= 60:
        if not is_bidirectional:
            return "NEEDS_ATTENTION"
        return "NEEDS_ATTENTION"
    else:
        return "COLD"


# ── Update 1.1: Freshness Decay Computation ─────────────────────────────


def compute_freshness(days_since: int, stage: str) -> float:
    """
    Compute freshness score (0.1-1.0) based on recency and relationship stage.

    Uses exponential decay with stage-specific half-life:
        ACTIVE: 7 days (fast decay - needs continuous engagement)
        WARM: 30 days (moderate decay)
        DORMANT: 60 days (slow decay)
        COLD: 90 days (very slow decay)
        AT_RISK: 15 days (fast decay - needs urgent attention)

    Formula: max(0.1, 0.5 ^ (days_since / half_life))

    Args:
        days_since: Days since last interaction
        stage: Relationship stage (ACTIVE, WARM, DORMANT, COLD, AT_RISK)

    Returns:
        float: Freshness score 0.1-1.0 (1.0 = very recent, 0.1 = stale)

    Example:
        >>> compute_freshness(3, "ACTIVE")
        0.766  # Recent active relationship (3/7 half-life)

        >>> compute_freshness(45, "WARM")
        0.354  # Aging warm relationship (45/30 half-life)

        >>> compute_freshness(120, "COLD")
        0.26  # Very old cold relationship
    """
    # Stage-specific half-life in days
    HALF_LIFE_MAP = {
        "ACTIVE": 7,  # Fast decay - active relationships need continuous engagement
        "WARM": 30,  # Moderate decay
        "NEEDS_ATTENTION": 45,  # Medium decay
        "DORMANT": 60,  # Slow decay - already dormant, slower fade
        "COLD": 90,  # Very slow decay
        "AT_RISK": 15,  # Faster decay - needs urgent attention
    }

    half_life = HALF_LIFE_MAP.get(stage, 30)  # Default 30 days

    # Exponential decay: 0.5 ^ (days_since / half_life)
    # Clamp minimum to 0.1 (never fully zero)
    freshness = max(0.1, 0.5 ** (days_since / half_life))

    return round(freshness, 3)


def calculate_size_score(interaction_count_90d: int, recency_score: float) -> float:
    """
    Calculate node size score per MVP V1 Detailing spec.
    Formula: (interaction_count_90d × 0.6) + (recency_score × 0.4)

    Tiers: Large (>0.70), Medium (0.40-0.70), Small (<0.40)
    """
    # Normalize interaction count (cap at 20 for scoring)
    normalized_count = min(interaction_count_90d / 20.0, 1.0)
    size = (normalized_count * 0.6) + (recency_score * 0.4)
    return round(min(1.0, size), 3)


def calculate_bidirectionality(db, contact_id: str) -> bool:
    """Check if both SENT (outbound) and RECEIVED (inbound) interactions exist."""
    result = db.execute(
        text("""
            SELECT
                BOOL_OR(direction = 'inbound') AS has_inbound,
                BOOL_OR(direction = 'outbound') AS has_outbound
            FROM interactions
            WHERE contact_id = :contact_id
        """),
        {"contact_id": contact_id}
    ).fetchone()

    if not result:
        return False
    return bool(result[0] and result[1])


def calculate_response_metrics(db, contact_id: str) -> Dict:
    """
    Calculate response rate and average response time.
    Response rate = replies received / emails sent to them
    Avg response time = average reply_time_hours where available
    """
    result = db.execute(
        text("""
            SELECT
                COUNT(*) FILTER (WHERE direction = 'outbound') as sent,
                COUNT(*) FILTER (WHERE direction = 'inbound' AND interaction_type = 'email_reply') as replies,
                AVG(reply_time_hours) FILTER (WHERE reply_time_hours IS NOT NULL AND reply_time_hours > 0) as avg_reply_time
            FROM interactions
            WHERE contact_id = :contact_id
        """),
        {"contact_id": contact_id}
    ).fetchone()

    if not result or not result[0]:
        return {"response_rate": None, "avg_response_time_hours": None}

    sent = result[0] or 0
    replies = result[1] or 0
    avg_reply_time = float(result[2]) if result[2] else None

    response_rate = round(replies / max(sent, 1), 3)

    return {
        "response_rate": response_rate,
        "avg_response_time_hours": round(avg_reply_time, 1) if avg_reply_time else None
    }


def calculate_composite_score(
    freshness: float, confidence: float, consistency: float,
    signal: float, authority: float
) -> float:
    """
    Calculate composite context score per MVP V1 Detailing spec.
    Threshold: >= 0.45 to include in context bundles.

    Weights: freshness 25%, confidence 25%, consistency 20%, signal 15%, authority 15%
    """
    composite = (
        freshness * 0.25 +
        confidence * 0.25 +
        consistency * 0.20 +
        signal * 0.15 +
        authority * 0.15
    )
    return round(min(1.0, composite), 3)


def aggregate_communication_style(db, contact_id: str) -> Dict:
    """
    Aggregate communication preferences from per-interaction comm_style_signals.
    Returns the most common what_works and what_to_avoid across all interactions.
    """
    results = db.execute(
        text("""
            SELECT comm_style_signals
            FROM interactions
            WHERE contact_id = :contact_id
            AND comm_style_signals IS NOT NULL
            ORDER BY interaction_at DESC
            LIMIT 20
        """),
        {"contact_id": contact_id}
    ).fetchall()

    if not results:
        return {"what_works": None, "what_to_avoid": None}

    # Collect all signals, most recent first (most recent wins for ties)
    works_signals = []
    avoid_signals = []

    for row in results:
        signals = row[0] if isinstance(row[0], dict) else {}
        if signals.get("what_works"):
            works_signals.append(signals["what_works"])
        if signals.get("what_to_avoid"):
            avoid_signals.append(signals["what_to_avoid"])

    # Return the most recent non-null value (LLM gets better with more context)
    return {
        "what_works": works_signals[0] if works_signals else None,
        "what_to_avoid": avoid_signals[0] if avoid_signals else None,
    }


def generate_relationship_summary(db, contact_id: str, contact_name: str) -> str:
    """
    Generate a structured summary for contacts with 50+ interactions.
    Compresses interaction history into a 3-sentence relationship arc.
    Per PDF spec: trajectory, recurring topics, key commitments, communication style.
    """
    # Get interaction stats
    stats = db.execute(
        text("""
            SELECT
                COUNT(*) as total,
                MIN(interaction_at) as first_at,
                MAX(interaction_at) as last_at,
                AVG(sentiment) as avg_sentiment,
                ARRAY_AGG(DISTINCT topic ORDER BY topic) as all_topics
            FROM interactions i, unnest(COALESCE(i.topics, ARRAY[]::text[])) as topic
            WHERE contact_id = :contact_id
        """),
        {"contact_id": contact_id}
    ).fetchone()

    if not stats or not stats[0]:
        return None

    total = stats[0]
    first_at = stats[1]
    last_at = stats[2]
    avg_sentiment = float(stats[3] or 0)
    top_topics = (stats[4] or [])[:5]

    # Get commitment summary
    commitments = db.execute(
        text("""
            SELECT status, COUNT(*) FROM commitments
            WHERE contact_id = :contact_id
            GROUP BY status
        """),
        {"contact_id": contact_id}
    ).fetchall()

    commit_summary = {r[0]: r[1] for r in commitments} if commitments else {}

    # Build the summary
    # Trajectory
    if avg_sentiment > 0.3:
        trajectory = "positive and engaged"
    elif avg_sentiment < -0.2:
        trajectory = "strained with declining sentiment"
    else:
        trajectory = "stable and professional"

    duration_days = (last_at - first_at).days if first_at and last_at else 0
    duration_str = f"{duration_days // 30} months" if duration_days > 60 else f"{duration_days} days"

    topics_str = ", ".join(str(t) for t in top_topics[:3]) if top_topics else "general"

    fulfilled = commit_summary.get("FULFILLED", 0)
    open_count = commit_summary.get("OPEN", 0) + commit_summary.get("OVERDUE", 0)

    summary = (
        f"Relationship with {contact_name} spans {duration_str} across {total} interactions. "
        f"Overall trajectory is {trajectory}. "
        f"Key topics: {topics_str}. "
    )

    if fulfilled or open_count:
        summary += f"Commitments: {fulfilled} fulfilled, {open_count} open/overdue."

    return summary


def check_archive_eligibility(db, contact_id: str) -> bool:
    """
    Check if a contact should be archived (no interaction for 6+ months).
    Per PDF spec: archived contacts still exist and are searchable but
    skip nightly stage calculations and context bundle pre-generation.
    """
    result = db.execute(
        text("""
            SELECT last_interaction_at FROM contacts
            WHERE id = :contact_id
        """),
        {"contact_id": contact_id}
    ).fetchone()

    if not result or not result[0]:
        return True  # No interactions = archive

    days_since = (datetime.now(timezone.utc) - result[0]).days
    return days_since > 180  # 6 months


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

    # Calculate bidirectionality
    is_bidirectional = calculate_bidirectionality(db, contact_id)

    # Calculate relationship stage (updated with bidirectionality)
    stage = calculate_relationship_stage(last_interaction, sentiment_ewma, is_bidirectional=is_bidirectional)

    # Calculate freshness score
    freshness_score = compute_freshness(days_since, stage)

    # Calculate response metrics
    response_metrics = calculate_response_metrics(db, contact_id)

    # Calculate size score (interaction count last 90 days)
    count_90d_result = db.execute(
        text("""
            SELECT COUNT(*) FROM interactions
            WHERE contact_id = :contact_id AND interaction_at >= NOW() - INTERVAL '90 days'
        """),
        {"contact_id": contact_id}
    ).fetchone()
    interaction_count_90d = count_90d_result[0] if count_90d_result else 0
    size_score = calculate_size_score(interaction_count_90d, freshness_score)

    # Calculate consistency and authority scores
    try:
        from app.graph.consistency_engine import calculate_consistency_score as calc_consistency
        from app.graph.consistency_engine import calculate_authority_score as calc_authority
        consistency_score = calc_consistency(db, contact_id)
        authority_score = calc_authority(db, contact_id)
    except Exception:
        consistency_score = 0.5
        authority_score = 0.5

    # Calculate average signal score
    signal_result = db.execute(
        text("SELECT AVG(signal_score) FROM interactions WHERE contact_id = :contact_id AND signal_score IS NOT NULL"),
        {"contact_id": contact_id}
    ).fetchone()
    avg_signal_score = float(signal_result[0]) if signal_result and signal_result[0] else 0.5

    # Calculate composite score
    composite_score = calculate_composite_score(
        freshness_score, confidence, consistency_score, avg_signal_score, authority_score
    )

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

    # ── Human score calculation ─────────────────────────────────────────────
    # Score 0.0 to 1.0 based on signals — used for graph node sizing, NOT filtering
    human_signals = db.execute(
        text(
            """
            SELECT
                BOOL_OR(direction = 'outbound') AS has_outbound,
                BOOL_OR(has_unsubscribe = TRUE) AS any_unsubscribe,
                COUNT(*) AS total_interactions
            FROM interactions
            WHERE contact_id = :contact_id
            """
        ),
        {"contact_id": contact_id},
    ).fetchone()

    human_score = 0.0
    if human_signals:
        # +0.3 if no unsubscribe headers found (not marketing)
        if not human_signals[1]:  # any_unsubscribe is False
            human_score += 0.3
        # +0.2 if you replied to them (two-way conversation)
        if human_signals[0]:  # has_outbound
            human_score += 0.2
        # +0.2 if multiple interactions (sustained relationship)
        if human_signals[2] and human_signals[2] >= 2:
            human_score += 0.2
        # +0.3 base — will be overridden by LLM is_human_email in future recalcs
        # For now, give benefit of doubt
        human_score += 0.3

    human_score = round(min(1.0, human_score), 2)

    # Aggregate communication style from per-interaction signals
    comm_style = aggregate_communication_style(db, contact_id)

    # Check archive eligibility (6+ months no interaction)
    is_archived = check_archive_eligibility(db, contact_id)

    # Generate structured summary for deep relationships (50+ interactions)
    relationship_summary = None
    summary_generated_at = None
    if interaction_count >= 50:
        # Get contact name for summary
        contact_row = db.execute(
            text("SELECT name FROM contacts WHERE id = :id"),
            {"id": contact_id}
        ).fetchone()
        contact_name = contact_row[0] if contact_row else "Unknown"
        relationship_summary = generate_relationship_summary(db, contact_id, contact_name)
        summary_generated_at = datetime.now(timezone.utc)

    # Detect stage change for tracking
    current_stage_row = db.execute(
        text("SELECT relationship_stage FROM contacts WHERE id = :id"),
        {"id": contact_id}
    ).fetchone()
    previous_stage = current_stage_row[0] if current_stage_row else None
    stage_changed = previous_stage and previous_stage != stage

    # Update contact with all fields including new V1 Detailing scores
    db.execute(
        text(
            """
            UPDATE contacts
            SET relationship_stage = :stage,
                sentiment_avg = :sentiment_avg,
                sentiment_ewma = :sentiment_ewma,
                sentiment_trend = :sentiment_trend,
                confidence_score = :confidence,
                freshness_score = :freshness_score,
                first_interaction_at = :first_interaction,
                last_interaction_at = :last_interaction,
                interaction_count = :interaction_count,
                topics_aggregate = :topics,
                sentiment_history = :sentiment_history,
                human_score = :human_score,
                is_bidirectional = :is_bidirectional,
                size_score = :size_score,
                consistency_score = :consistency_score,
                authority_score = :authority_score,
                composite_score = :composite_score,
                response_rate = :response_rate,
                avg_response_time_hours = :avg_response_time_hours,
                what_works = COALESCE(:what_works, what_works),
                what_to_avoid = COALESCE(:what_to_avoid, what_to_avoid),
                is_archived = :is_archived,
                relationship_summary = COALESCE(:relationship_summary, relationship_summary),
                summary_generated_at = COALESCE(:summary_generated_at, summary_generated_at),
                stage_changed_at = CASE WHEN :stage_changed THEN NOW() ELSE stage_changed_at END,
                previous_stage = CASE WHEN :stage_changed THEN :previous_stage ELSE previous_stage END,
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
            "freshness_score": freshness_score,
            "first_interaction": first_interaction,
            "last_interaction": last_interaction,
            "interaction_count": interaction_count,
            "topics": all_topics,
            "sentiment_history": sentiment_history,
            "human_score": human_score,
            "is_bidirectional": is_bidirectional,
            "size_score": size_score,
            "consistency_score": consistency_score,
            "authority_score": authority_score,
            "composite_score": composite_score,
            "response_rate": response_metrics["response_rate"],
            "avg_response_time_hours": response_metrics["avg_response_time_hours"],
            "what_works": comm_style.get("what_works"),
            "what_to_avoid": comm_style.get("what_to_avoid"),
            "is_archived": is_archived,
            "relationship_summary": relationship_summary,
            "summary_generated_at": summary_generated_at,
            "stage_changed": stage_changed,
            "previous_stage": previous_stage,
        },
    )
    db.commit()

    return {
        "stage": stage,
        "sentiment_avg": sentiment_avg,
        "sentiment_ewma": sentiment_ewma,
        "sentiment_trend": sentiment_trend,
        "confidence": confidence,
        "freshness_score": freshness_score,
        "interaction_count": interaction_count,
        "last_interaction": last_interaction,
        "human_score": human_score,
        "is_bidirectional": is_bidirectional,
        "size_score": size_score,
        "consistency_score": consistency_score,
        "authority_score": authority_score,
        "composite_score": composite_score,
        "response_rate": response_metrics["response_rate"],
        "avg_response_time_hours": response_metrics["avg_response_time_hours"],
        "what_works": comm_style.get("what_works"),
        "what_to_avoid": comm_style.get("what_to_avoid"),
        "is_archived": is_archived,
        "stage_changed": stage_changed,
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
