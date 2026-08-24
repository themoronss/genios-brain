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
from app.graph.embedder import embed_text
from app.plan_enforcer import require_mr_elite_mode
from app.llm_guard import call_with_timeout
from app.llm import llm_client
import logging
import re

logger = logging.getLogger(__name__)

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
    "semantic": "The user is asking a strategic question about their network — who to prioritize, follow up with, or invest in. Use the semantic match rankings provided. For each recommended contact, state their name, why they're relevant (match score, stage, days since last contact), and a concrete next action. Be specific and data-backed.",
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
                    sentiment_avg, context_score
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
                        sentiment_avg, context_score
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


def get_semantic_context(db, org_id: str, query: str, limit: int = 8) -> str:
    """
    Embed the query string and rank contacts by cosine similarity + relationship health.
    Returns a formatted context block for Gemini to reason over.
    """
    try:
        query_vec = embed_text(query)
        # Format as pgvector literal: '[0.1, 0.2, ...]'
        query_vec_str = "[" + ",".join(str(v) for v in query_vec) + "]"

        rows = db.execute(
            text("""
                SELECT
                    name, company, entity_type, relationship_stage,
                    COALESCE(context_score, 0.5) AS health,
                    COALESCE(sentiment_avg, 0) AS sentiment,
                    EXTRACT(DAY FROM NOW() - last_interaction_at) AS days_ago,
                    interaction_count,
                    ROUND(CAST(
                        (1 - (embedding <=> CAST(:qvec AS vector))) * 0.5
                        + COALESCE(context_score, 0.5) * 0.3
                        + ((COALESCE(sentiment_avg, 0) + 1.0) / 2.0) * 0.2
                    AS numeric), 3) AS relevance_score
                FROM contacts
                WHERE org_id = :org_id
                    AND embedding IS NOT NULL
                    AND (disclosure_level IS NULL OR disclosure_level != 'private')
                ORDER BY relevance_score DESC
                LIMIT :limit
            """),
            {"org_id": org_id, "qvec": query_vec_str, "limit": limit},
        ).fetchall()

        if not rows:
            return "No contacts with embeddings found. Sync your graph first to enable semantic search."

        lines = ["=== SEMANTIC MATCH — CONTACTS MOST RELEVANT TO YOUR QUERY ==="]
        for r in rows:
            name, company, etype, stage, health, sentiment, days_ago, count, score = r
            company_str = f" @ {company}" if company else ""
            days_str = f"{int(days_ago)}d ago" if days_ago is not None else "never contacted"
            type_str = etype or "contact"
            lines.append(
                f"- {name}{company_str} | {type_str} | {stage or 'unknown'} | "
                f"Last contact: {days_str} | Health: {float(health):.0%} | Relevance: {float(score):.0%}"
            )

        return "\n".join(lines)

    except Exception as e:
        logger.error(f"Semantic context error: {e}")
        try:
            db.rollback()
        except Exception:
            pass
        return "Semantic search unavailable. Ensure contacts have embeddings."


def get_v2_graph_context(db, org_id: str, query: str, entity_name: str | None = None) -> str:
    """Grounding context from the v2 graph (graph_nodes + facts).

    The v1 `contacts`/`interactions` tables were dropped in migration 0015;
    this reads the live v2 data via core.graph.views so Mr. Elite answers are
    grounded in the user's actual graph instead of erroring on a missing table.
    """
    try:
        from core.graph.views import list_contacts, list_facts

        lines: list[str] = []

        # People / companies — v2 'entity' nodes, most recently active first.
        contacts = list_contacts(db, org_id=org_id, limit=25).get("contacts", [])
        if contacts:
            lines.append("=== PEOPLE / COMPANIES IN YOUR GRAPH (most recent first) ===")
            for c in contacts:
                comp = f" @ {c['company']}" if c.get("company") else ""
                last = c.get("lastInteraction")
                last_str = last[:10] if isinstance(last, str) else "unknown"
                lines.append(
                    f"- {c.get('name', '?')}{comp} | stage: {c.get('relationshipStage', 'unknown')}"
                    f" | mentions: {c.get('interactionCount', 0)} | last seen: {last_str}"
                )

        # Facts (subject-predicate-object). If a specific entity is in play,
        # focus on it; always add a recent-facts baseline so broad questions
        # ("any risky relationships?") still have material to reason over.
        facts: list = []
        if entity_name:
            facts = list_facts(db, org_id=org_id, subject=entity_name, limit=40).get("facts", [])
        if len(facts) < 10:
            recent = list_facts(db, org_id=org_id, limit=50).get("facts", [])
            seen = {(f["subject"], f["predicate"], f["object"]) for f in facts}
            for f in recent:
                key = (f["subject"], f["predicate"], f["object"])
                if key not in seen:
                    facts.append(f)
        if facts:
            lines.append("\n=== FACTS KNOWN (subject — predicate — object) ===")
            for f in facts[:60]:
                lines.append(f"- {f.get('subject', '?')} — {f.get('predicate', '?')} — {f.get('object', '?')}")

        if not lines:
            return (
                "No graph data yet — the user hasn't synced a source or the graph "
                "is empty. Tell them to connect Gmail / upload data in Resources."
            )
        return "\n".join(lines)
    except Exception as e:
        logger.error(f"v2 graph context error: {e}", exc_info=True)
        try:
            db.rollback()
        except Exception:
            pass
        return "Unable to load graph context right now."


def resolve_entity_v2(db, org_id: str, message: str) -> str | None:
    """Return an entity name from the v2 graph whose name appears in the message.

    Replaces the v1 `get_contact_by_name` lookup (dropped contacts table).
    Longest names match first so 'Acme Corp' wins over 'Acme'.
    """
    try:
        from core.graph.views import list_contacts
        contacts = list_contacts(db, org_id=org_id, limit=500).get("contacts", [])
        msg_low = (message or "").lower()
        for c in sorted(contacts, key=lambda x: -len(x.get("name") or "")):
            name = (c.get("name") or "").strip()
            if len(name) >= 3 and name.lower() in msg_low:
                return name
        return None
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass
        return None


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
        # Warm-intro path traversal needs the v1 interactions graph (dropped in
        # mig 0015), so it's unavailable until the v2 edge-path build lands.
        # Guard resolution so "who knows X" degrades to a normal v2-grounded
        # answer instead of 500-ing on the dropped contacts table.
        warm_intro_target = detect_warm_intro_query(message)
        try:
            target_contact = (
                get_contact_by_name(db, org_id, warm_intro_target)
                if warm_intro_target else None
            )
        except Exception:
            target_contact = None
            try:
                db.rollback()
            except Exception:
                pass
        if warm_intro_target and target_contact:
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

                messages = [{"role": "system", "content": system_with_context}]
                for msg in request.history[-6:]:
                    role = "user" if msg.role == "user" else "assistant"
                    messages.append({"role": role, "content": msg.content})
                messages.append({"role": "user", "content": message})

                reply = call_with_timeout(
                    llm_client.call,
                    org_id=org_id, purpose="chat",
                    messages=messages, temperature=0.4, max_tokens=1024,
                    fallback=None,
                )
                if reply is None:
                    raise HTTPException(status_code=504, detail={"error": "TIMEOUT", "message": "LLM response timed out."})
                reply = reply.strip()

                return {
                    "reply": reply,
                    "query_type": "warm_intro",
                    "context_used": True,
                    "entity_resolved": target_contact["name"],
                    "warm_intro_paths": intros,
                }

        # ── Plan gate for restricted query modes ──────────────────────────
        if query_type in ("temporal", "semantic"):
            require_mr_elite_mode(db, org_id, query_type)

        # ── Build context based on query type ──────────────────────────────

        context_block = ""

        if query_type == "semantic":
            context_block = get_v2_graph_context(db, org_id, message)

        elif query_type in ("entity", "situation", "action"):
            entity_name = request.entity_name or resolve_entity_v2(db, org_id, message)
            context_block = get_v2_graph_context(db, org_id, message, entity_name=entity_name)

        elif query_type == "temporal":
            context_block = get_v2_graph_context(db, org_id, message)

        # ── Build Gemini prompt ────────────────────────────────────────────

        type_instruction = QUERY_TYPE_INSTRUCTIONS.get(query_type, QUERY_TYPE_INSTRUCTIONS["entity"])

        system_with_context = (
            f"{SYSTEM_PROMPT}\n\n"
            f"Query mode: {query_type.upper()}\n"
            f"Instructions: {type_instruction}\n\n"
            f"{context_block}"
        )

        # Build conversation (flattened for unified LLM client)
        messages = [{"role": "system", "content": system_with_context}]
        for msg in request.history[-6:]:  # Last 6 messages for context window
            role = "user" if msg.role == "user" else "assistant"
            messages.append({"role": role, "content": msg.content})
        messages.append({"role": "user", "content": message})

        reply = call_with_timeout(
            llm_client.call,
            org_id=org_id, purpose="chat",
            messages=messages, temperature=0.4, max_tokens=1024,
            fallback=None,
        )
        if reply is None:
            raise HTTPException(status_code=504, detail={"error": "TIMEOUT", "message": "LLM response timed out."})
        reply = reply.strip()

        return {
            "reply": reply,
            "query_type": query_type,
            "context_used": bool(context_block and "===" in context_block),
            "entity_resolved": request.entity_name or resolve_entity_v2(db, org_id, message),
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
