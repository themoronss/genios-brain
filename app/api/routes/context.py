from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, root_validator, validator
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.context.bundle_builder import build_context_bundle
from app.redis_client import redis_client
import json
import hashlib
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


# Pydantic models
class ContextRequest(BaseModel):
    entity: str
    situation: str = None

    @validator("entity")
    def validate_entity(cls, v):
        if not v or len(v.strip()) < 2:
            raise ValueError("Entity name must be at least 2 characters")
        if len(v) > 200:
            raise ValueError("Entity name too long")
        return v.strip()


class EntityDetails(BaseModel):
    name: str
    company: str = None
    relationship_stage: str
    last_interaction: str
    sentiment_trend: str
    communication_style: str
    topics_of_interest: list
    open_commitments: list
    interaction_count: int


class ContextResponse(BaseModel):
    entity: EntityDetails = None
    match_confidence: float = 1.0
    matched_from: str = None
    context_for_agent: str
    confidence: float
    error: str = None


# Dependency to get DB session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_cache_key(org_id: str, entity_name: str) -> str:
    """Generate cache key for context bundle."""
    key_data = f"{org_id}:{entity_name}".lower()
    return f"context:{hashlib.md5(key_data.encode()).hexdigest()}"


security = HTTPBearer()

def verify_api_key(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Verify API key and return org_id. Uses its own DB session to avoid holding
    connections open for the entire request lifecycle."""
    token = credentials.credentials
    if not token.startswith("gn_live_"):
        raise HTTPException(status_code=401, detail="Invalid API Key format")
    
    # Create and immediately close DB session for auth check only
    db = SessionLocal()
    try:
        result = db.execute(
            text("SELECT id FROM orgs WHERE api_key = :api_key"),
            {"api_key": token}
        ).fetchone()
    finally:
        db.close()
    
    if not result:
        raise HTTPException(status_code=401, detail="Invalid API Key")
        
    return str(result[0])

@router.post("/v1/context")
def get_context(request: ContextRequest, db: Session = Depends(get_db), org_id: str = Depends(verify_api_key)):
    """
    Get context bundle for an entity.

    Week 6: Added validation, better error handling, and logging.

    Request:
        - org_id: Organization UUID
        - entity_name: Person/company name
        - situation: Optional context (for future use)

    Returns:
        - entity: Detailed entity information
        - context_for_agent: Ready-to-use paragraph for LLM prompts
        - confidence: 0.0 to 1.0 score
    """
    try:
        logger.info(
            f"Context request for: {request.entity}, org: {org_id}"
        )

        # Check cache first (60 second TTL as per MVP)
        cache_key = get_cache_key(org_id, request.entity)

        try:
            cached = redis_client.get(cache_key)
            if cached:
                logger.info(f"Cache hit for {request.entity}")
                return json.loads(cached)
        except Exception as redis_error:
            # Continue if Redis fails (don't block on cache errors)
            logger.warning(f"Redis cache read failed: {redis_error}")

        # Build context bundle
        try:
            context_bundle = build_context_bundle(
                db, org_id, request.entity, request.situation
            )
        except Exception as e:
            logger.error(f"Context bundle build error: {str(e)}")
            raise HTTPException(
                status_code=500, detail="Failed to build context. Please try again."
            )

        # Handle case where entity not found
        if context_bundle.get("error"):
            logger.warning(f"Entity not found: {request.entity}")
            raise HTTPException(
                status_code=404,
                detail=f"Contact '{request.entity}' not found in your network.",
            )

        # Cache for 60 seconds
        try:
            redis_client.setex(
                cache_key,
                60,  # 60 second TTL as per MVP spec
                json.dumps(context_bundle, default=str),
            )
            logger.info(f"Cached context for {request.entity}")
        except Exception as redis_error:
            # Continue if Redis fails
            logger.warning(f"Redis cache write failed: {redis_error}")

        return context_bundle

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in get_context: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


class DashboardContextRequest(BaseModel):
    entity_name: str
    situation: str = None

@router.post("/api/org/{org_id}/context")
def get_dashboard_context(org_id: str, request: DashboardContextRequest, db: Session = Depends(get_db)):
    """Internal endpoint for testing context without API key."""
    try:
        context_bundle = build_context_bundle(
            db, org_id, request.entity_name, request.situation
        )
        if context_bundle.get("error"):
            raise HTTPException(
                status_code=404,
                detail=f"Contact '{request.entity_name}' not found in your network.",
            )
        return context_bundle
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in dashboard context: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")
