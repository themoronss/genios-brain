from sqlalchemy import text
from datetime import datetime, timezone
from app.context.situation_embedder import embed_situation
from app.graph.queries import search_contacts_by_embedding
from app.context.cache import get_cached_context, set_cached_context


def _calculate_recommended_action(contact, interactions):
    """
    Calculate recommended action based on relationship rules.

    Rules:
    1. If last_interaction > 14 days and stage = warm → "Send follow-up this week"
    2. If last_interaction > 30 days → "Relationship cooling — re-engage"
    3. If last_sentiment < 0 → "Approach carefully — last interaction negative"
    4. Default → "Maintain relationship"
    """
    # Get last interaction date
    last_interaction_date = None
    if interactions:
        # Find the most recent interaction with a date
        for interaction in interactions:
            if interaction.get("interaction_at"):
                try:
                    last_interaction_date = datetime.fromisoformat(
                        interaction["interaction_at"]
                    )
                    break
                except (ValueError, TypeError):
                    continue

    # Calculate days since last interaction
    days_since_interaction = None
    if last_interaction_date:
        now = datetime.now(timezone.utc)
        # Make last_interaction_date timezone-aware if needed
        if last_interaction_date.tzinfo is None:
            last_interaction_date = last_interaction_date.replace(tzinfo=timezone.utc)
        days_since_interaction = (now - last_interaction_date).days

    # Get relationship stage
    stage = contact.get("relationship_stage", "unknown")

    # Apply rules in priority order
    # Rule 3: Check sentiment (if available)
    # Note: sentiment field may not exist yet in database
    last_sentiment = contact.get("last_sentiment", 0)
    if last_sentiment < 0:
        return "Approach carefully — last interaction negative"

    # Rule 2: Over 30 days since last interaction
    if days_since_interaction and days_since_interaction > 30:
        return "Relationship cooling — re-engage"

    # Rule 1: Over 14 days and stage is warm
    if days_since_interaction and days_since_interaction > 14 and stage == "warm":
        return "Send follow-up this week"

    # Rule 4: Default
    return "Maintain relationship"


def _calculate_coverage_score(contact, interactions):
    """
    Calculate coverage score representing how complete the context is.

    Formula: score = populated_fields / total_fields

    Fields considered:
    - contact name
    - email
    - company
    - recent interactions
    - relationship_stage
    - sentiment

    Returns:
        float: Coverage score between 0 and 1
    """
    total_fields = 6
    populated_fields = 0

    # Check contact name
    if contact.get("name"):
        populated_fields += 1

    # Check email
    if contact.get("email"):
        populated_fields += 1

    # Check company
    if contact.get("company"):
        populated_fields += 1

    # Check recent interactions
    if interactions and len(interactions) > 0:
        populated_fields += 1

    # Check relationship_stage (only if not 'unknown')
    stage = contact.get("relationship_stage")
    if stage and stage != "unknown":
        populated_fields += 1

    # Check sentiment (if field exists and has meaningful value)
    sentiment = contact.get("last_sentiment")
    if sentiment is not None and sentiment != 0:
        populated_fields += 1

    # Calculate score
    coverage_score = populated_fields / total_fields

    return round(coverage_score, 2)


def compile_context(db, org_id: str, situation: str):
    """
    Build a ContextBundle from a situation.

    Args:
        db: SQLAlchemy database session
        org_id: Organization ID
        situation: The situation text to get context for

    Returns:
        Dictionary with situation and relevant contacts with their recent interactions
    """
    # Check Redis cache first
    cached_bundle = get_cached_context(org_id, situation)
    if cached_bundle:
        return cached_bundle

    # Step 1: Embed the situation
    situation_embedding = embed_situation(situation)

    # Step 2: Search top 3 contacts using vector similarity
    top_contacts = search_contacts_by_embedding(
        db, org_id, situation_embedding, limit=3
    )

    # Step 3: Fetch last 5 interactions for each contact
    for contact in top_contacts:
        contact_id = contact["id"]

        result = db.execute(
            text(
                """
                SELECT subject, summary, interaction_at, direction
                FROM interactions
                WHERE contact_id = :contact_id
                ORDER BY interaction_at DESC
                LIMIT 5
            """
            ),
            {"contact_id": contact_id},
        )

        interactions = []
        for row in result.fetchall():
            interactions.append(
                {
                    "subject": row[0],
                    "summary": row[1],
                    "interaction_at": row[2].isoformat() if row[2] else None,
                    "direction": row[3],
                }
            )

        contact["recent_interactions"] = interactions

        # Calculate and add recommended action
        contact["recommended_action"] = _calculate_recommended_action(
            contact, interactions
        )

        # Calculate and add coverage score
        contact["coverage_score"] = _calculate_coverage_score(contact, interactions)

    # Step 4: Build and return the context bundle
    context_bundle = {"situation": situation, "contacts": top_contacts}

    # Store in Redis cache
    set_cached_context(org_id, situation, context_bundle)

    return context_bundle
