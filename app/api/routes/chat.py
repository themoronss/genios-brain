"""
Mr. Elite Chatbot — Conversational graph query interface.
Supports 4 query types: entity, temporal, situation, action.
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.api.deps import get_db
from app.context.bundle_builder import build_context_bundle, get_contact_by_name
from app.graph.indirect_edges import find_warm_intro_path
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


def extract_entity_from_message(message: str, db, org_id: str) -> str | None:
    """Try to detect an entity name from the user's message by checking against contacts."""
    try:
        words = message.split()

        # Strategy 1: Try 2-word combinations (first + last name) — any casing
        for i in range(len(words) - 1):
            candidate = f"{words[i]} {words[i+1]}"
            # Strip punctuation from candidate
            candidate_clean = re.sub(r'[^\w\s]', '', candidate).strip()
            if len(candidate_clean) > 3:
                contact = get_contact_by_name(db, org_id, candidate_clean)
                if contact and contact.get("match_confidence", 0) > 0.7:
                    return contact["name"]

        # Strategy 2: Try single words (company names, single-word identifiers)
        for word in words:
            word_clean = re.sub(r'[^\w]', '', word).strip()
            if len(word_clean) > 2 and word_clean.lower() not in {
                "the", "and", "for", "with", "about", "from", "who", "what",
                "how", "when", "should", "have", "has", "had", "was", "were",
                "been", "being", "this", "that", "these", "those", "tell",
                "know", "any", "can", "could", "would", "will", "shall",
                "may", "might", "must", "need", "want", "like", "get",
                "give", "take", "make", "come", "see", "look", "find",
                "help", "let", "say", "ask", "try", "call", "send",
                "meet", "follow", "reach", "check", "draft", "prep",
                "status", "update", "email", "meeting", "week", "today",
                "tomorrow", "yesterday", "now", "next", "last", "ago",
                "out", "back", "off", "over", "down", "into", "most",
                "some", "all", "not", "very", "just", "also", "too",
                "much", "many", "more", "less", "good", "bad", "best",
                "important", "risky", "warm", "cold", "active",
            }:
                contact = get_contact_by_name(db, org_id, word_clean)
                if contact and contact.get("match_confidence", 0) > 0.75:
                    return contact["name"]

        return None
    except Exception as e:
        logger.warning(f"Entity extraction from message failed: {e}")
        return None


WARM_INTRO_PATTERNS = [
    r"who\s+knows?\s+(.+)",
    r"introduce\s+me\s+to\s+(.+)",
    r"connection\s+to\s+(.+)",
    r"intro\s+to\s+(.+)",
    r"warm\s+intro\s+(?:to\s+)?(.+)",
    r"how\s+(?:do\s+i|can\s+i)\s+reach\s+(.+)",
    r"path\s+to\s+(.+)",
]


def detect_warm_intro_query(message: str) -> str | None:
    """Detect if the message is asking for a warm intro and extract the target name."""
    msg_lower = message.lower().strip().rstrip("?.,!")
    for pattern in WARM_INTRO_PATTERNS:
        match = re.search(pattern, msg_lower)
        if match:
            target = match.group(1).strip().rstrip("?.,!")
            # Clean common trailing words
            target = re.sub(r'\s+(please|pls|for me|asap)$', '', target).strip()
            if len(target) > 1:
                return target
    return None


def format_warm_intro_response(target_name: str, intros: list) -> str:
    """Format warm intro results into context for the LLM."""
    if not intros:
        return f"No warm intro path found to {target_name}. No active/warm contacts share email threads with them."

    lines = [f"=== WARM INTRO PATHS TO {target_name.upper()} ==="]
    for intro in intros:
        conf_pct = f"{intro['confidence']:.0%}"
        lines.append(
            f"- {intro['name']} ({intro['relationship_stage']}) @ {intro.get('company') or 'unknown'} "
            f"| {intro['shared_threads']} shared threads | confidence: {conf_pct}"
        )
    lines.append(f"\nBest introducer: {intros[0]['name']} ({intros[0]['shared_threads']} shared threads).")
    return "\n".join(lines)


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
        try:
            db.rollback()
        except Exception:
            pass
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

        # ── Check for warm intro / "who knows" queries ────────────────────
        warm_intro_target = detect_warm_intro_query(message)
        if warm_intro_target:
            target_contact = get_contact_by_name(db, org_id, warm_intro_target)
            if target_contact:
                intros = find_warm_intro_path(db, org_id, str(target_contact["id"]))
                intro_context = format_warm_intro_response(target_contact["name"], intros)
                # Also get the target's bundle for full context
                try:
                    target_bundle = build_context_bundle(db, org_id, target_contact["name"])
                    target_ctx = target_bundle.get("context_for_agent", "")
                except Exception:
                    target_ctx = ""
                    try:
                        db.rollback()
                    except Exception:
                        pass

                context_block = f"{intro_context}\n\n=== TARGET CONTACT ===\n{target_ctx}" if target_ctx else intro_context
                query_type = "entity"  # Override for proper instruction

                # Skip normal context building, jump to Gemini
                type_instruction = (
                    "The user is asking for a warm introduction path. "
                    "Explain who can introduce them, why that person is a good connector, "
                    "and suggest how to ask for the intro. Be specific and actionable."
                )

                system_with_context = (
                    f"{SYSTEM_PROMPT}\n\n"
                    f"Query mode: WARM_INTRO\n"
                    f"Instructions: {type_instruction}\n\n"
                    f"{context_block}"
                )

                gemini_history = []
                for msg in request.history[-6:]:
                    role = "user" if msg.role == "user" else "model"
                    gemini_history.append({"role": role, "parts": [msg.content]})

                model = genai.GenerativeModel(
                    model_name="gemini-2.5-flash",
                    system_instruction=system_with_context,
                )
                chat_session = model.start_chat(history=gemini_history)
                response = chat_session.send_message(message)
                reply = response.text.strip()

                return {
                    "reply": reply,
                    "query_type": "warm_intro",
                    "context_used": True,
                    "entity_resolved": target_contact["name"],
                    "warm_intro_paths": intros,
                }

        # ── Build context based on query type ──────────────────────────────

        context_block = ""

        if query_type in ("entity", "situation", "action"):
            # Try to find entity from explicit param or message
            entity_name = request.entity_name
            if not entity_name:
                entity_name = extract_entity_from_message(message, db, org_id)

            # If no specific entity found, check if message mentions a category
            # e.g. "tell me about my top investor" → find best investor contact
            if not entity_name:
                msg_lower = message.lower()
                category_keywords = {
                    "investor": "investor", "investors": "investor",
                    "customer": "customer", "customers": "customer",
                    "vendor": "vendor", "vendors": "vendor",
                    "partner": "partner", "partners": "partner",
                    "advisor": "advisor", "advisors": "advisor",
                    "lead": "lead", "leads": "lead",
                }
                for keyword, entity_type in category_keywords.items():
                    if keyword in msg_lower:
                        try:
                            top_contact = db.execute(
                                text("""
                                    SELECT name FROM contacts
                                    WHERE org_id = :org_id AND entity_type = :etype
                                    ORDER BY interaction_count DESC, composite_score DESC NULLS LAST
                                    LIMIT 1
                                """),
                                {"org_id": org_id, "etype": entity_type},
                            ).fetchone()
                            if top_contact:
                                entity_name = top_contact[0]
                        except Exception:
                            try:
                                db.rollback()
                            except Exception:
                                pass
                        break

            if entity_name:
                try:
                    bundle = build_context_bundle(db, org_id, entity_name)
                except Exception as e:
                    logger.warning(f"Bundle build failed for '{entity_name}': {e}")
                    try:
                        db.rollback()
                    except Exception:
                        pass
                    bundle = {"error": str(e)}
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
                # No entity found — provide general graph overview as context
                try:
                    top_contacts = db.execute(
                        text("""
                            SELECT name, company, entity_type, relationship_stage, interaction_count
                            FROM contacts WHERE org_id = :org_id AND interaction_count > 0
                            ORDER BY interaction_count DESC LIMIT 10
                        """),
                        {"org_id": org_id},
                    ).fetchall()
                    if top_contacts:
                        lines = ["=== YOUR TOP CONTACTS ==="]
                        for tc in top_contacts:
                            company_str = f" @ {tc[1]}" if tc[1] else ""
                            lines.append(f"- {tc[0]}{company_str} | {tc[2] or 'other'} | {tc[3]} | {tc[4]} interactions")
                        context_block = "\n".join(lines)
                    else:
                        context_block = "No contacts found in your network yet. Connect Gmail and sync to build your graph."
                except Exception:
                    try:
                        db.rollback()
                    except Exception:
                        pass
                    context_block = "Unable to load graph data."

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
            model_name="gemini-2.5-flash",
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
        logger.error(f"Chat error: {e}", exc_info=True)
        try:
            db.rollback()
        except Exception:
            pass
        raise HTTPException(status_code=500, detail=f"Chat failed: {type(e).__name__}. Please try again.")
