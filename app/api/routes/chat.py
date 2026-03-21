"""
Mr. Elite Chatbot — Conversational graph query interface.
Supports 4 query types: entity, temporal, situation, action.
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.context.bundle_builder import build_context_bundle, get_contact_by_name
from app.config import GEMINI_API_KEY
import google.generativeai as genai
import logging
import re

logger = logging.getLogger(__name__)
genai.configure(api_key=GEMINI_API_KEY)

router = APIRouter()

SYSTEM_PROMPT = """You are Mr. Elite, an intelligent relationship advisor for a founder/executive.
You have access to their relationship graph — emails, meetings, contact history, and context scores.
Be concise, direct, and actionable. Never fabricate facts. If context is missing, say so.
Format responses with short paragraphs or bullet points. Use markdown sparingly."""

QUERY_TYPE_INSTRUCTIONS = {
    "entity": "The user is asking about a specific person or company. Provide a relationship brief: who they are, current status, key topics, recent interactions, and a recommended next action.",
    "temporal": "The user wants to know who to reach out to or what relationships need attention. Rank contacts by urgency, recency, and relationship health. Be specific about why each contact matters now.",
    "situation": "The user is preparing for a specific interaction (meeting, call, email). Provide tactical prep: key context, talking points, topics to avoid, and relevant commitments.",
    "action": "The user wants help drafting or deciding on a specific action. Use the relationship context to make the draft/recommendation feel personal and relationship-aware.",
}


class ChatMessage(BaseModel):
    role: str  # user | assistant
    content: str


class ChatRequest(BaseModel):
    message: str
    query_type: str = "entity"  # entity, temporal, situation, action
    history: list[ChatMessage] = []
    entity_name: str = None  # Optional: pre-load context for a specific entity


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def extract_entity_from_message(message: str, db, org_id: str) -> str | None:
    """Try to detect an entity name from the user's message by checking against contacts."""
    # Simple heuristic: look for capitalized words that match contact names
    words = message.split()
    # Try 2-word combinations first (first + last name)
    for i in range(len(words) - 1):
        candidate = f"{words[i]} {words[i+1]}"
        if re.match(r'^[A-Z][a-z]+ [A-Z][a-z]+', candidate):
            contact = get_contact_by_name(db, org_id, candidate)
            if contact and contact.get("match_confidence", 0) > 0.7:
                return contact["name"]
    return None


def get_temporal_context(db, org_id: str, limit: int = 8) -> str:
    """Build a summary of who needs attention for temporal queries."""
    try:
        results = db.execute(
            text("""
                SELECT
                    name, company, relationship_stage, last_interaction_at,
                    interaction_count, entity_type,
                    EXTRACT(DAY FROM NOW() - last_interaction_at) as days_ago,
                    sentiment_avg, composite_score
                FROM contacts
                WHERE org_id = :org_id
                    AND relationship_stage IN ('NEEDS_ATTENTION', 'WARM', 'DORMANT', 'AT_RISK')
                ORDER BY
                    CASE relationship_stage
                        WHEN 'AT_RISK' THEN 1
                        WHEN 'NEEDS_ATTENTION' THEN 2
                        WHEN 'DORMANT' THEN 3
                        WHEN 'WARM' THEN 4
                        ELSE 5
                    END,
                    last_interaction_at DESC NULLS LAST
                LIMIT :limit
            """),
            {"org_id": org_id, "limit": limit},
        ).fetchall()

        if not results:
            # Fall back to all contacts ordered by stage priority
            results = db.execute(
                text("""
                    SELECT
                        name, company, relationship_stage, last_interaction_at,
                        interaction_count, entity_type,
                        EXTRACT(DAY FROM NOW() - last_interaction_at) as days_ago,
                        sentiment_avg, composite_score
                    FROM contacts
                    WHERE org_id = :org_id AND relationship_stage IS NOT NULL
                    ORDER BY last_interaction_at DESC NULLS LAST
                    LIMIT :limit
                """),
                {"org_id": org_id, "limit": limit},
            ).fetchall()

        lines = []
        for r in results:
            days = int(r[6]) if r[6] else 999
            company_str = f" @ {r[1]}" if r[1] else ""
            lines.append(
                f"- {r[0]}{company_str} | Stage: {r[2]} | Last contact: {days}d ago | {r[5] or 'other'}"
            )

        return "\n".join(lines) if lines else "No contacts found in your network."
    except Exception as e:
        logger.error(f"Error fetching temporal context: {e}")
        return "Unable to fetch contact data."


@router.post("/api/org/{org_id}/chat")
def chat_with_mr_elite(org_id: str, request: ChatRequest, db: Session = Depends(get_db)):
    """
    Mr. Elite conversational interface — graph-grounded responses to natural language queries.
    """
    try:
        query_type = request.query_type
        message = request.message.strip()

        if not message:
            raise HTTPException(status_code=400, detail="Message cannot be empty")

        # ── Build context based on query type ──────────────────────────────

        context_block = ""

        if query_type in ("entity", "situation", "action"):
            # Try to find entity from explicit param or message
            entity_name = request.entity_name
            if not entity_name:
                entity_name = extract_entity_from_message(message, db, org_id)

            if entity_name:
                bundle = build_context_bundle(db, org_id, entity_name)
                if not bundle.get("error"):
                    ctx = bundle.get("context_for_agent", "")
                    entity = bundle.get("entity", {})
                    scores = bundle.get("scores", {})
                    context_block = (
                        f"=== RELATIONSHIP CONTEXT ===\n"
                        f"{ctx}\n\n"
                        f"Scores — Freshness: {scores.get('freshness', 0.5):.0%}, "
                        f"Confidence: {scores.get('confidence', 0.5):.0%}, "
                        f"Consistency: {scores.get('consistency', 0.5):.0%}, "
                        f"Composite: {scores.get('composite', 0.5):.0%}\n"
                        f"Response rate: {entity.get('response_rate', 'unknown')}, "
                        f"Avg reply time: {entity.get('avg_response_time_hours', 'unknown')}h\n"
                        f"Action signal: {bundle.get('action_recommendation', 'proceed')} — {bundle.get('action_reason', '')}"
                    )
                else:
                    context_block = f"No relationship data found for '{entity_name}' in your network."
            else:
                context_block = "No specific contact identified. I'll answer from general graph knowledge."

        elif query_type == "temporal":
            temporal_data = get_temporal_context(db, org_id)
            context_block = f"=== CONTACTS NEEDING ATTENTION ===\n{temporal_data}"

        # ── Build Gemini prompt ────────────────────────────────────────────

        type_instruction = QUERY_TYPE_INSTRUCTIONS.get(query_type, QUERY_TYPE_INSTRUCTIONS["entity"])

        system_with_context = (
            f"{SYSTEM_PROMPT}\n\n"
            f"Query mode: {query_type.upper()}\n"
            f"Instructions: {type_instruction}\n\n"
            f"{context_block}"
        )

        # Build conversation history
        gemini_history = []
        for msg in request.history[-6:]:  # Last 6 messages for context window
            role = "user" if msg.role == "user" else "model"
            gemini_history.append({"role": role, "parts": [msg.content]})

        model = genai.GenerativeModel(
            model_name="gemini-1.5-flash",
            system_instruction=system_with_context,
        )

        chat_session = model.start_chat(history=gemini_history)
        response = chat_session.send_message(message)
        reply = response.text.strip()

        return {
            "reply": reply,
            "query_type": query_type,
            "context_used": bool(context_block and "===" in context_block),
            "entity_resolved": request.entity_name or extract_entity_from_message(message, db, org_id),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Chat error: {e}")
        raise HTTPException(status_code=500, detail="Chat failed. Please try again.")
