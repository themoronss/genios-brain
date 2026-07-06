import logging
import os
import time

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, validator
from sqlalchemy.orm import Session

from app.actions import ledger as action_ledger
from app.api.deps import get_db
from app.api.routes.approvals import enqueue as enqueue_approval
from app.context.bundle_builder import build_context_bundle
from app.coordination import blackboard
from app.llm import llm_client
from app.llm_guard import call_with_timeout
from app.policy import enforcement as policy_enforcement

logger = logging.getLogger(__name__)

router = APIRouter()


# Pydantic models
class DraftRequest(BaseModel):
    org_id: str
    entity_name: str
    user_request: str
    draft_type: str = "email"
    agent_id: str = "draft-agent"

    @validator("entity_name")
    def validate_entity_name(cls, v):
        if not v or len(v.strip()) < 2:
            raise ValueError("Entity name must be at least 2 characters")
        if len(v.strip()) > 200:
            raise ValueError("Entity name too long (max 200 characters)")
        return v.strip()

    @validator("user_request")
    def validate_user_request(cls, v):
        if not v or len(v.strip()) < 1:
            raise ValueError("Request cannot be empty")
        if len(v) > 500:
            raise ValueError("Request too long (max 500 characters)")
        return v.strip()


class DraftResponse(BaseModel):
    draft: str
    context_used: str  # The context that was given to Gemini
    confidence: float
    entity_name: str


def _v2_context_bundle(db, org_id: str, entity_name: str) -> dict:
    """Build a draft context bundle from the v2 graph (graph_nodes + facts).

    Replaces the legacy build_context_bundle(), which queried the v1
    `contacts`/`interactions` tables dropped in migration 0015 (→ hard 500).
    Returns the shape draft generation consumes ({entity, context_for_agent,
    confidence, error}) and NEVER raises on missing data — worst case a thin
    bundle so the draft still generates from the user's request alone.
    """
    from sqlalchemy import text as _t

    name = entity_name.strip()
    node = db.execute(
        _t("""
            SELECT id, canonical_name
            FROM graph_nodes
            WHERE org_id = :oid AND type = 'entity'
              AND (
                    LOWER(canonical_name) = LOWER(:n)
                 OR LOWER(COALESCE(attributes->>'email','')) = LOWER(:n)
                 OR EXISTS (SELECT 1 FROM jsonb_array_elements_text(
                                COALESCE(aliases::jsonb,'[]'::jsonb)) AS a
                            WHERE LOWER(a) = LOWER(:n))
              )
            ORDER BY last_seen DESC
            LIMIT 1
        """),
        {"oid": org_id, "n": name},
    ).fetchone()
    canonical = node.canonical_name if node else name
    node_id = str(node.id) if node else None

    facts = db.execute(
        _t("""
            SELECT predicate, object, confidence
            FROM facts
            WHERE org_id = :oid
              AND (LOWER(subject) = LOWER(:cn) OR LOWER(subject) = LOWER(:n))
            ORDER BY created_at DESC
            LIMIT 40
        """),
        {"oid": org_id, "cn": canonical, "n": name},
    ).fetchall()

    if not facts:
        return {
            "entity": {"id": node_id, "name": canonical},
            "context_for_agent": (
                f"No stored relationship history for {canonical} yet. "
                "Draft from the user's request; keep it professional and concise."
            ),
            "confidence": 0.0,
            "error": None,
        }

    lines = [f"What GeniOS knows about {canonical} (most recent first):"]
    for f in facts:
        lines.append(f"- {str(f.predicate).replace('_', ' ')} {f.object}")
    avg_conf = sum(float(f.confidence or 0) for f in facts) / len(facts)
    coverage = min(len(facts) / 10.0, 1.0)

    return {
        "entity": {"id": node_id, "name": canonical},
        "context_for_agent": "\n".join(lines),
        "confidence": round(avg_conf * (0.5 + 0.5 * coverage), 3),
        "error": None,
    }


@router.post("/api/generate/draft")
def generate_draft(request: DraftRequest, db: Session = Depends(get_db)):
    """
    Generate an AI-drafted message using full relationship context.

    Week 5 Feature: The "Holy Shit" moment - AI drafts with perfect context.

    Flow:
    1. Get context bundle for entity
    2. Inject context into Gemini prompt
    3. Let Gemini draft the message
    4. Return draft to user

    Request:
        - org_id: Organization UUID
        - entity_name: Who this is for/about
        - user_request: What to draft (e.g., "Follow up on funding discussion")
        - draft_type: Type of draft (email, message, note)

    Returns:
        - draft: The AI-generated draft
        - context_used: The context given to AI (for transparency)
        - confidence: Context confidence score
        - entity_name: Confirmed entity name
    """
    claim_result = None
    lock_ref = None
    ledger_id = None
    ledger_finalized = False  # prevents the except block from overwriting a deliberate outcome
    try:
        logger.info(
            f"Draft request for entity: {request.entity_name}, org: {request.org_id}"
        )

        # Resolve entity → contact_id early so the ledger row + policy ctx
        # carry the UUID (the explainer joins on it, segment filters too).
        from sqlalchemy import text as _sql_text
        # v2: resolve entity → graph_nodes id (v1 `contacts` was dropped in 0015).
        # Match on canonical_name, a stored email attribute, or any alias.
        _contact_row = db.execute(
            _sql_text("""
                SELECT id FROM graph_nodes
                WHERE org_id = :oid
                  AND type = 'entity'
                  AND (
                        LOWER(canonical_name) = LOWER(:n)
                     OR LOWER(COALESCE(attributes->>'email', '')) = LOWER(:n)
                     OR EXISTS (
                            SELECT 1
                            FROM jsonb_array_elements_text(COALESCE(aliases::jsonb, '[]'::jsonb)) AS a
                            WHERE LOWER(a) = LOWER(:n)
                        )
                  )
                ORDER BY last_seen DESC
                LIMIT 1
            """),
            {"oid": request.org_id, "n": request.entity_name.strip()},
        ).fetchone()
        resolved_contact_id = str(_contact_row[0]) if _contact_row else None

        policy_payload = {
            "entity": request.entity_name,
            "user_request": request.user_request,
            "draft_type": request.draft_type,
            "contact_id": resolved_contact_id,
        }
        decision, ledger_id = policy_enforcement.evaluate_and_open(
            db, org_id=request.org_id, agent_id=request.agent_id,
            action_type="draft", risk_tier="external_draft",
            target_ref=request.entity_name, payload=policy_payload,
            contact_id=resolved_contact_id,
        )

        if decision["decision"] == "block":
            policy_enforcement.close(db, ledger_id, "failed", f"policy_block:{decision.get('rule_name')}")
            ledger_finalized = True
            raise HTTPException(status_code=403, detail={
                "error": "POLICY_BLOCK", "message": "Draft blocked by policy.",
                "rule_id": decision["rule_id"], "rule_name": decision["rule_name"],
            })

        if decision["decision"] == "require_approval":
            approval_id = enqueue_approval(
                db, org_id=request.org_id, agent_id=request.agent_id,
                action_type="draft", risk_tier="external_draft",
                target_ref=request.entity_name, payload=policy_payload,
                action_ledger_id=ledger_id,
                triggered_rule_id=decision["rule_id"],
                reason=f"matched rule {decision.get('rule_name')}",
            )
            # Ledger intentionally stays 'pending' — approval flow will flip it.
            ledger_finalized = True
            raise HTTPException(status_code=202, detail={
                "status": "awaiting_approval", "approval_id": approval_id,
                "rule_id": decision["rule_id"], "rule_name": decision["rule_name"],
            })

        # Blackboard lock — prevent duplicate drafts on the same entity.
        # Key is entity_name at this stage (contact_id resolved later inside bundle).
        lock_ref = request.entity_name.lower().strip()
        claim_result = blackboard.claim(
            org_id=request.org_id,
            contact_ref=lock_ref,
            agent_id=request.agent_id,
            action="draft",
            ttl_seconds=90,
        )
        if not claim_result["acquired"]:
            blackboard.audit(
                db, request.org_id, request.agent_id,
                action="draft", status="conflicted",
                metadata={"entity": request.entity_name, "holder": claim_result["holder"]},
                ended=True,
            )
            if ledger_id:
                action_ledger.update_outcome(db, ledger_id, "failed", "contact_locked")
            ledger_finalized = True
            raise HTTPException(
                status_code=409,
                detail={
                    "error": "CONTACT_LOCKED",
                    "message": "Another agent is currently acting on this contact.",
                    "holder": claim_result["holder"],
                },
            )

        # Step 1: Get context bundle for the entity (v2 graph — graph_nodes/facts).
        try:
            context_bundle = _v2_context_bundle(db, request.org_id, request.entity_name)
        except Exception as e:
            logger.error(f"Context bundle build failed: {str(e)}")
            # Degrade rather than 500 — draft from the user's request alone.
            context_bundle = {
                "entity": {"id": None, "name": request.entity_name},
                "context_for_agent": (
                    f"(Relationship context unavailable.) Draft for "
                    f"{request.entity_name} from the user's request; keep it "
                    "professional and concise."
                ),
                "confidence": 0.0,
                "error": None,
            }

        # Check if contact was found
        if context_bundle.get("error"):
            logger.warning(f"Contact not found: {request.entity_name}")
            raise HTTPException(
                status_code=404,
                detail=f"Contact '{request.entity_name}' not found in your network. Make sure Gmail sync is complete.",
            )

        if not context_bundle or not context_bundle.get("context_for_agent"):
            logger.warning(f"No context available for {request.entity_name}")
            raise HTTPException(
                status_code=404,
                detail=f"Contact '{request.entity_name}' not found in your network. Make sure Gmail sync is complete.",
            )

        # Step 2: Build prompt with context injection
        context_text = context_bundle["context_for_agent"]
        entity_info = context_bundle.get("entity", {})

        system_prompt = """You are a professional communication assistant. You draft emails and messages that are:
- Appropriate in tone and style for the relationship
- Reference-aware (mention relevant past conversations)
- Action-oriented and clear
- Natural, not robotic

Use the provided RELATIONSHIP CONTEXT to inform your draft. Reference specific details when relevant."""

        user_prompt = f"""RELATIONSHIP CONTEXT:
{context_text}

USER REQUEST:
{request.user_request}

Draft a {request.draft_type} based on the above context and request. Be specific, reference past interactions when relevant, and match the communication style described in the context."""

        # Step 3: Call LLM with retry logic.
        # `draft` purpose is routed to Anthropic Haiku; the llm_client falls
        # back to Groq → Gemini internally if Anthropic is unavailable, so
        # any of these keys being set is enough. Check Anthropic first since
        # that's the primary route.
        if not (os.getenv("ANTHROPIC_API_KEY") or os.getenv("GROQ_API_KEY") or os.getenv("GEMINI_API_KEY")):
            logger.error("No LLM provider key configured (ANTHROPIC_API_KEY / GROQ_API_KEY / GEMINI_API_KEY)")
            raise HTTPException(status_code=500, detail="AI service not configured")

        def _generate() -> str:
            return llm_client.call(
                org_id=request.org_id, purpose="draft",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user",   "content": user_prompt},
                ],
                temperature=0.4, max_tokens=800,
            ).strip()

        draft_text = None
        max_retries = 3

        for attempt in range(max_retries):
            try:
                draft_text = call_with_timeout(_generate, fallback=None)
                if draft_text is None:
                    raise HTTPException(
                        status_code=504,
                        detail={"error": "TIMEOUT", "message": "Draft generation timed out."},
                    )

                if draft_text and len(draft_text.strip()) > 10:
                    logger.info(f"Draft generated successfully on attempt {attempt + 1}")
                    break
                else:
                    logger.warning(f"Empty or too short draft on attempt {attempt + 1}")
                    if attempt < max_retries - 1:
                        time.sleep(1)
                    continue

            except Exception as e:
                logger.error(f"Groq API error on attempt {attempt + 1}: {str(e)}")
                if attempt == max_retries - 1:
                    raise HTTPException(
                        status_code=503,
                        detail="AI service temporarily unavailable. Please try again in a moment.",
                    )
                time.sleep(2**attempt)  # Exponential backoff

        if not draft_text:
            raise HTTPException(
                status_code=500, detail="Failed to generate draft. Please try again."
            )

        # Step 4: Return draft with context transparency
        blackboard.log(
            request.org_id, lock_ref, request.agent_id,
            action="draft", status="completed",
            metadata={"entity": entity_info.get("name", request.entity_name)},
        )
        blackboard.audit(
            db, request.org_id, request.agent_id,
            action="draft", status="completed",
            contact_id=entity_info.get("id") if isinstance(entity_info, dict) else None,
            metadata={"entity": request.entity_name},
            ended=True,
        )
        if ledger_id:
            action_ledger.update_outcome(db, ledger_id, "success")
            ledger_finalized = True
        return DraftResponse(
            draft=draft_text,
            context_used=context_text,
            confidence=context_bundle.get("confidence", 0.0),
            entity_name=entity_info.get("name", request.entity_name),
        )

    except HTTPException:
        # Only mark as failed if no branch has already finalized the ledger
        # (policy_block / awaiting_approval / contact_locked / success all pre-set it).
        if ledger_id and not ledger_finalized:
            action_ledger.update_outcome(db, ledger_id, "failed", "http_exception")
        raise
    except Exception as e:
        if ledger_id and not ledger_finalized:
            action_ledger.update_outcome(db, ledger_id, "failed", str(e)[:500])
        raise HTTPException(
            status_code=500, detail=f"Draft generation failed: {str(e)}"
        )
    finally:
        # Always release the lock we acquired, even on failure.
        if claim_result and claim_result.get("acquired") and claim_result.get("lock_id"):
            blackboard.release(request.org_id, lock_ref, claim_result["lock_id"])
