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
import time
import uuid
from datetime import datetime, timezone

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


def log_context_call(
    db: Session,
    org_id: str,
    entity_name: str,
    context_bundle: dict,
    cache_hit: bool = False,
):
    """
    Fix C: Log every context API call to context_calls table.
    Non-blocking — failures are silently swallowed so they never affect the response.
    """
    try:
        entity = context_bundle.get("entity") or {}
        db.execute(
            text(
                """
                INSERT INTO context_calls
                    (org_id, entity_name, relationship_stage, action_recommendation,
                     confidence, cache_hit, called_at)
                VALUES
                    (:org_id, :entity_name, :stage, :action, :confidence, :cache_hit, NOW())
                """
            ),
            {
                "org_id": org_id,
                "entity_name": entity_name[:200],
                "stage": entity.get("relationship_stage"),
                "action": context_bundle.get("action_recommendation"),
                "confidence": context_bundle.get("confidence"),
                "cache_hit": cache_hit,
            },
        )
        db.commit()
    except Exception as e:
        logger.warning(f"Context call logging failed (non-critical): {e}")


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
                # Log cache hit (Fix C)
                log_context_call(
                    db, org_id, request.entity,
                    json.loads(cached) if isinstance(cached, (str, bytes)) else {},
                    cache_hit=True,
                )
                return json.loads(cached)
        except Exception as redis_error:
            # Continue if Redis fails (don't block on cache errors)
            logger.warning(f"Redis cache read failed: {redis_error}")

        # Try pre-computed bundle first (24h cache from nightly refresh)
        context_bundle = None
        try:
            precomputed = db.execute(
                text("""
                    SELECT pb.bundle, pb.generated_at, c.id
                    FROM precomputed_bundles pb
                    JOIN contacts c ON pb.contact_id = c.id AND pb.org_id = c.org_id
                    WHERE pb.org_id = :org_id
                    AND LOWER(c.name) = LOWER(:entity_name)
                    AND pb.expires_at > NOW()
                    LIMIT 1
                """),
                {"org_id": org_id, "entity_name": request.entity.strip()}
            ).fetchone()

            if precomputed and precomputed[0]:
                context_bundle = precomputed[0] if isinstance(precomputed[0], dict) else json.loads(precomputed[0])
                # Set cache_age_seconds
                if precomputed[1]:
                    age = (datetime.now(timezone.utc) - precomputed[1]).total_seconds()
                    context_bundle["cache_age_seconds"] = int(age)
                logger.info(f"Serving pre-computed bundle for {request.entity}")
        except Exception as e:
            logger.debug(f"Pre-computed bundle lookup failed: {e}")

        # Fall back to on-demand build
        if not context_bundle:
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

        # Log the call (Fix C)
        log_context_call(db, org_id, request.entity, context_bundle, cache_hit=False)

        # Cache for 60 seconds
        try:
            redis_client.setex(
                cache_key,
                60,
                json.dumps(context_bundle, default=str),
            )
            logger.info(f"Cached context for {request.entity}")
        except Exception as redis_error:
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


# ── New V1 Detailing Endpoints ──────────────────────────────────────────────


class ContextOutcomeRequest(BaseModel):
    org_id: str
    session_id: str = None
    agent_id: str = None
    action_type: str  # email_sent, meeting_scheduled, crm_updated
    target_entity: str = None
    outcome: dict  # {type: EXECUTED|EDITED|REJECTED|ESCALATED}
    interaction_record: dict = None  # {subject, direction, topics[], commitment_made}


@router.post("/v1/context/outcome")
def report_context_outcome(
    request: ContextOutcomeRequest,
    db: Session = Depends(get_db),
    org_id: str = Depends(verify_api_key),
):
    """Record agent execution outcomes for the feedback loop."""
    try:
        outcome_type = request.outcome.get("type", "EXECUTED")
        if outcome_type not in ("EXECUTED", "EDITED", "REJECTED", "ESCALATED"):
            raise HTTPException(status_code=400, detail="Invalid outcome type")

        db.execute(
            text("""
                INSERT INTO outcome_events
                    (org_id, session_id, agent_id, action_type, target_entity, outcome_type, interaction_record)
                VALUES
                    (:org_id, :session_id, :agent_id, :action_type, :target_entity, :outcome_type, :interaction_record)
            """),
            {
                "org_id": org_id,
                "session_id": request.session_id,
                "agent_id": request.agent_id,
                "action_type": request.action_type,
                "target_entity": request.target_entity,
                "outcome_type": outcome_type,
                "interaction_record": json.dumps(request.interaction_record) if request.interaction_record else None,
            },
        )

        # Update AER (Autonomous Execution Rate)
        aer_delta = 0.0
        if outcome_type == "EXECUTED":
            aer_delta = 0.02
        elif outcome_type == "EDITED":
            aer_delta = 0.01

        if aer_delta > 0:
            db.execute(
                text("""
                    UPDATE orgs SET aer = LEAST(1.0, COALESCE(aer, 0) + :delta)
                    WHERE id = :org_id
                """),
                {"org_id": org_id, "delta": aer_delta},
            )

        db.commit()

        return {
            "learned": True,
            "graph_updated": request.interaction_record is not None,
            "aer_delta": aer_delta,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to record outcome: {e}")
        raise HTTPException(status_code=500, detail="Failed to record outcome")


class ContextSearchRequest(BaseModel):
    query_type: str = "temporal"  # temporal, topic, entity
    filter: dict = {}  # {stages: [], last_contact_days: {min, max}, entity_types: []}
    limit: int = 10


@router.post("/v1/context/search")
def search_context(
    request: ContextSearchRequest,
    db: Session = Depends(get_db),
    org_id: str = Depends(verify_api_key),
):
    """Temporal and topic-anchored search, returns ranked contacts."""
    try:
        start_time = time.time()
        filters = request.filter
        conditions = ["c.org_id = :org_id", "c.relationship_stage IS NOT NULL", "c.relationship_stage != 'unknown'"]
        params: dict = {"org_id": org_id, "limit": min(request.limit, 25)}

        # Stage filter
        stages = filters.get("stages", [])
        if stages:
            conditions.append("c.relationship_stage = ANY(:stages)")
            params["stages"] = stages

        # Recency filter
        last_contact = filters.get("last_contact_days", {})
        if last_contact.get("max"):
            conditions.append("c.last_interaction_at >= NOW() - INTERVAL '1 day' * :max_days")
            params["max_days"] = last_contact["max"]
        if last_contact.get("min"):
            conditions.append("c.last_interaction_at <= NOW() - INTERVAL '1 day' * :min_days")
            params["min_days"] = last_contact["min"]

        # Entity type filter
        entity_types = filters.get("entity_types", [])
        if entity_types:
            conditions.append("c.entity_type = ANY(:entity_types)")
            params["entity_types"] = entity_types

        where_clause = " AND ".join(conditions)

        # Order by based on query type
        if request.query_type == "temporal":
            order = "c.last_interaction_at DESC NULLS LAST"
        else:
            order = "c.composite_score DESC NULLS LAST, c.interaction_count DESC"

        results = db.execute(
            text(f"""
                SELECT
                    c.id, c.name, c.email, c.company, c.relationship_stage,
                    c.sentiment_avg, c.interaction_count, c.last_interaction_at,
                    c.entity_type, c.confidence_score, c.freshness_score,
                    c.composite_score
                FROM contacts c
                WHERE {where_clause}
                ORDER BY {order}
                LIMIT :limit
            """),
            params,
        ).fetchall()

        latency_ms = int((time.time() - start_time) * 1000)

        contacts = []
        for r in results:
            days_ago = (datetime.now(timezone.utc) - r[7]).days if r[7] else 999
            contacts.append({
                "id": str(r[0]),
                "name": r[1],
                "email": r[2],
                "company": r[3],
                "relationship_stage": r[4],
                "sentiment_avg": float(r[5] or 0),
                "interaction_count": r[6],
                "last_interaction_days": days_ago,
                "entity_type": r[8] or "other",
                "confidence_score": float(r[9] or 0.5),
                "freshness_score": float(r[10] or 0.5),
                "composite_score": float(r[11] or 0.5),
            })

        return {
            "contacts": contacts,
            "total": len(contacts),
            "query_type": request.query_type,
            "latency_ms": latency_ms,
        }
    except Exception as e:
        logger.error(f"Context search failed: {e}")
        raise HTTPException(status_code=500, detail="Search failed")


@router.get("/v1/context/entity/{entity_id}")
def get_entity_context(
    entity_id: str,
    db: Session = Depends(get_db),
    org_id: str = Depends(verify_api_key),
):
    """Pull full context for a specific entity by ID."""
    try:
        contact = db.execute(
            text("""
                SELECT name FROM contacts WHERE id = :id AND org_id = :org_id
            """),
            {"id": entity_id, "org_id": org_id},
        ).fetchone()

        if not contact:
            raise HTTPException(
                status_code=404,
                detail={"error_code": "entity_not_found", "message": f"Entity {entity_id} not found"},
            )

        context_bundle = build_context_bundle(db, org_id, contact[0])

        if context_bundle.get("error"):
            raise HTTPException(status_code=404, detail={"error_code": "entity_not_found"})

        return context_bundle
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Entity context failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to get entity context")
