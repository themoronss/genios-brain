from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, validator
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.context.bundle_builder import build_context_bundle
from app.config import GEMINI_API_KEY
import google.generativeai as genai
import logging
import time

# Configure logging
logger = logging.getLogger(__name__)

# Configure Gemini
genai.configure(api_key=GEMINI_API_KEY)

router = APIRouter()


# Pydantic models
class DraftRequest(BaseModel):
    org_id: str
    entity_name: str
    user_request: str
    draft_type: str = "email"

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


# Dependency to get DB session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


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
    try:
        logger.info(
            f"Draft request for entity: {request.entity_name}, org: {request.org_id}"
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

        # Step 3: Call Gemini API with retry logic
        if not GEMINI_API_KEY:
            logger.error("GEMINI_API_KEY not configured")
            raise HTTPException(status_code=500, detail="AI service not configured")

        draft_text = None
        max_retries = 3

        for attempt in range(max_retries):
            try:
                model = genai.GenerativeModel(
                    model_name="gemini-2.5-flash", system_instruction=system_prompt
                )
                response = model.generate_content(user_prompt)
                draft_text = response.text

                if draft_text and len(draft_text.strip()) > 10:
                    logger.info(
                        f"Draft generated successfully on attempt {attempt + 1}"
                    )
                    break
                else:
                    logger.warning(f"Empty or too short draft on attempt {attempt + 1}")
                    if attempt < max_retries - 1:
                        time.sleep(1)
                    continue

            except Exception as e:
                logger.error(f"Gemini API error on attempt {attempt + 1}: {str(e)}")
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
        return DraftResponse(
            draft=draft_text,
            context_used=context_text,
            confidence=context_bundle.get("confidence", 0.0),
            entity_name=entity_info.get("name", request.entity_name),
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Draft generation failed: {str(e)}"
        )
