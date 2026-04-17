import logging
import os
import time

from fastapi import APIRouter, Depends, HTTPException
from groq import Groq
from pydantic import BaseModel, validator
from sqlalchemy.orm import Session

from app.actions import ledger as action_ledger
from app.api.deps import get_db
from app.api.routes.approvals import enqueue as enqueue_approval
from app.context.bundle_builder import build_context_bundle
from app.coordination import blackboard
from app.llm_guard import call_with_timeout
from app.policy import enforcement as policy_enforcement

logger = logging.getLogger(__name__)

# Use Groq (matches the model used by entity_extractor + proactive_scanner).
# Gemini stays around for other endpoints; drafts go through Groq to avoid
# the paid-tier rate limits we were hitting.
_GROQ_CLIENT = Groq(api_key=os.getenv("GROQ_API_KEY"))
_GROQ_MODEL = os.getenv("GROQ_DRAFT_MODEL", "llama-3.3-70b-versatile")

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
        _contact_row = db.execute(
            _sql_text("""
                SELECT id FROM contacts
                WHERE org_id = :oid
                  AND (LOWER(name) = LOWER(:n) OR LOWER(email) = LOWER(:n))
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

        # Step 1: Get context bundle for the entity
        try:
            context_bundle = build_context_bundle(
                db, request.org_id, request.entity_name, None
            )
        except Exception as e:
            logger.error(f"Context bundle build failed: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail="Failed to build relationship context. Please try again.",
            )

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

        # Step 3: Call Groq with retry logic
        if not os.getenv("GROQ_API_KEY"):
            logger.error("GROQ_API_KEY not configured")
            raise HTTPException(status_code=500, detail="AI service not configured")

        def _generate() -> str:
            resp = _GROQ_CLIENT.chat.completions.create(
                model=_GROQ_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user",   "content": user_prompt},
                ],
                temperature=0.4,
                max_tokens=800,
            )
            return (resp.choices[0].message.content or "").strip()

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
