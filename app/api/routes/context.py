from fastapi import APIRouter, Depends, HTTPException, Header
from pydantic import BaseModel, root_validator, validator
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.api.deps import get_db, verify_api_key, check_rpm_limit, check_abuse_detection
from app.context.bundle_builder import build_context_bundle
from app.plan_enforcer import get_org_plan
from app.redis_client import redis_client
import json
import hashlib
import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Union

logger = logging.getLogger(__name__)

router = APIRouter()


# Pydantic models
class ContextRequest(BaseModel):
    entity: str
    situation: str = None
    agent_id: str = None      # Optional — identifies which agent is calling
    segment_id: str = None    # Optional — scope bundle to contacts in this segment
    tag: str = None           # Optional — only return entity if it has this tag

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


def get_cache_key(org_id: str, entity_name: str, situation: str = None) -> str:
    """Generate cache key for context bundle. Includes situation per spec."""
    situation_part = situation.strip().lower()[:100] if situation else ""
    key_data = f"{org_id}:{entity_name}:{situation_part}".lower()
    return f"context:{hashlib.md5(key_data.encode()).hexdigest()}"


from app.plan_enforcer import (
    check_period_quota, apply_bundle_depth, truncate_bundle_tokens,
    get_org_plan,
)
from app.llm_guard import check_agent_loop, call_with_timeout


def log_context_call(
    db: Session,
    org_id: str,
    entity_name: str,
    context_bundle: dict,
    cache_hit: bool = False,
    source: str = "api",
    agent_id: str = None,
    tokens_used: int = None,
):
    """
    Log every context API call to context_calls table.
    Non-blocking — failures are silently swallowed so they never affect the response.
    source: 'api' (external agent) or 'dashboard' (internal UI click)
    """
    try:
        entity = context_bundle.get("entity") or {}
        db.execute(
            text(
                """
                INSERT INTO context_calls
                    (org_id, entity_name, relationship_stage, action_recommendation,
                     confidence, cache_hit, source, agent_id, tokens_used, called_at)
                VALUES
                    (:org_id, :entity_name, :stage, :action, :confidence, :cache_hit,
                     :source, :agent_id, :tokens_used, NOW())
                """
            ),
            {
                "org_id": org_id,
                "entity_name": entity_name[:200],
                "stage": entity.get("relationship_stage"),
                "action": context_bundle.get("action_recommendation"),
                "confidence": context_bundle.get("confidence"),
                "cache_hit": cache_hit,
                "source": source,
                "agent_id": agent_id,
                "tokens_used": tokens_used,
            },
        )
        db.commit()
    except Exception as e:
        logger.warning(f"Context call logging failed (non-critical): {e}")


def context_error(code: str, message: str, status_code: int = 400):
    raise HTTPException(
        status_code=status_code,
        detail={"error": {"code": code, "message": message}}
    )



@router.post("/v1/context")
def get_context(
    request: ContextRequest,
    db: Session = Depends(get_db),
    org_id: str = Depends(verify_api_key),
    x_genios_source: str = Header(None, alias="X-GeniOS-Source"),
):
    """
    Get context bundle for an entity.

    Request:
        - entity: Person/company name
        - situation: Optional context
        - agent_id: Optional agent identifier

    Returns:
        - entity: Detailed entity information
        - context_for_agent: Ready-to-use paragraph for LLM prompts
        - confidence: 0.0 to 1.0 score
    """
    try:
        start_time = time.time()
        segment_name = None

        # Determine call source: dashboard UI vs external agent
        source = "dashboard" if x_genios_source == "dashboard" else "api"

        # Abuse detection (all sources)
        check_abuse_detection(org_id)

        # Quota check — only external API calls consume quota
        if source == "api":
            # Get tier for RPM + loop checks
            plan_info = get_org_plan(db, org_id)
            check_rpm_limit(org_id, request.agent_id, plan_info["tier"])

            # Validate agent_id against registered_agents (2.4 — irregular caller handling)
            # Only enforced when org has registered at least one agent
            if request.agent_id:
                reg_count = db.execute(
                    text("SELECT COUNT(*) FROM registered_agents WHERE org_id = :org_id"),
                    {"org_id": org_id},
                ).scalar() or 0
                if reg_count > 0:
                    is_registered = db.execute(
                        text("""
                            SELECT 1 FROM registered_agents
                            WHERE org_id = :org_id AND agent_id = :aid
                        """),
                        {"org_id": org_id, "aid": request.agent_id},
                    ).fetchone()
                    if not is_registered:
                        raise HTTPException(
                            status_code=401,
                            detail={
                                "error": "UNREGISTERED_AGENT",
                                "message": f"Agent '{request.agent_id}' is not registered. Register via POST /v1/agent.",
                                "agent_id": request.agent_id,
                            },
                        )

            check_agent_loop(org_id, request.agent_id, plan_info["tier"])
            quota = check_period_quota(db, org_id)
            if not quota["allowed"]:
                raise HTTPException(
                    status_code=429,
                    detail={
                        "error": {
                            "code": quota.get("error_code", "QUOTA_EXCEEDED"),
                            "message": quota.get("message", "Quota exceeded."),
                            "plan": quota.get("tier"),
                            "daily_used": quota.get("daily_used"),
                            "daily_limit": quota.get("daily_limit"),
                            "period_used": quota.get("period_used"),
                            "period_limit": quota.get("period_limit"),
                            "upgrade_required": quota.get("upgrade_required", False),
                        }
                    },
                    headers={"Retry-After": "86400"},
                )

        logger.info(
            f"Context request for: {request.entity}, org: {org_id}, source: {source}"
        )

        # Segment scoping: if segment_id provided, verify entity is a member
        segment_name = None
        if request.segment_id:
            seg_row = db.execute(
                text("""
                    SELECT gs.name FROM graph_segments gs
                    WHERE gs.id = :sid AND gs.org_id = :org_id
                """),
                {"sid": request.segment_id, "org_id": org_id},
            ).fetchone()
            if not seg_row:
                raise HTTPException(
                    status_code=404,
                    detail={"error": "SEGMENT_NOT_FOUND", "message": f"Segment '{request.segment_id}' not found"},
                )
            segment_name = seg_row.name
            # Verify the entity is in the segment
            in_segment = db.execute(
                text("""
                    SELECT 1 FROM segment_members sm
                    JOIN contacts c ON c.id = sm.contact_id
                    WHERE sm.segment_id = :sid
                      AND c.org_id = :org_id
                      AND LOWER(c.name) = LOWER(:entity)
                    LIMIT 1
                """),
                {"sid": request.segment_id, "org_id": org_id, "entity": request.entity.strip()},
            ).fetchone()
            if not in_segment:
                raise HTTPException(
                    status_code=403,
                    detail={
                        "error": "ENTITY_NOT_IN_SEGMENT",
                        "message": f"'{request.entity}' is not a member of segment '{segment_name}'.",
                        "segment_id": request.segment_id,
                    },
                )

        # ── Disclosure control (Phase 7) ─────────────────────────────────────
        # Check BEFORE cache so private contacts are never served from cache either
        disclosure_row = db.execute(
            text("""
                SELECT disclosure_level, restricted_to_agents
                FROM contacts
                WHERE org_id = :org_id
                  AND LOWER(TRIM(name)) = LOWER(TRIM(:entity))
                LIMIT 1
            """),
            {"org_id": org_id, "entity": request.entity.strip()},
        ).fetchone()

        if disclosure_row:
            disclosure = disclosure_row[0] or "public"
            if disclosure == "private":
                raise HTTPException(
                    status_code=403,
                    detail={
                        "error": "CONTACT_PRIVATE",
                        "message": f"'{request.entity}' is marked private and excluded from context bundles.",
                    },
                )
            if disclosure == "restricted":
                allowed = list(disclosure_row[1] or [])
                if not request.agent_id or request.agent_id not in allowed:
                    raise HTTPException(
                        status_code=403,
                        detail={
                            "error": "CONTACT_RESTRICTED",
                            "message": f"'{request.entity}' is restricted. Agent '{request.agent_id}' is not authorized.",
                            "agent_id": request.agent_id,
                        },
                    )

        # ── Tag filter (Phase 7) ──────────────────────────────────────────────
        if request.tag:
            tag_match = db.execute(
                text("""
                    SELECT 1 FROM contacts
                    WHERE org_id = :org_id
                      AND LOWER(TRIM(name)) = LOWER(TRIM(:entity))
                      AND tags @> ARRAY[:tag]::text[]
                    LIMIT 1
                """),
                {"org_id": org_id, "entity": request.entity.strip(), "tag": request.tag.lower().strip()},
            ).fetchone()
            if not tag_match:
                raise HTTPException(
                    status_code=404,
                    detail={
                        "error": "ENTITY_TAG_MISMATCH",
                        "message": f"'{request.entity}' does not have tag '{request.tag}'.",
                        "tag": request.tag,
                    },
                )

        # Check cache first (60 second TTL as per MVP)
        cache_key = get_cache_key(org_id, request.entity, request.situation)

        try:
            cached = redis_client.get(cache_key)
            if cached:
                logger.info(f"Cache hit for {request.entity}")
                cached_bundle = json.loads(cached) if isinstance(cached, (str, bytes)) else {}
                cached_tokens = max(1, len(cached_bundle.get("context_for_agent", "")) // 4)
                log_context_call(
                    db, org_id, request.entity,
                    cached_bundle,
                    cache_hit=True,
                    source=source,
                    agent_id=request.agent_id,
                    tokens_used=cached_tokens,
                )
                cached_bundle["latency_ms"] = int((time.time() - start_time) * 1000)
                cached_bundle["cache_hit"] = True
                from app.core.analytics import capture as _capture
                _capture(org_id, "api_context_requested", {
                    "source": source,
                    "cache_hit": True,
                    "confidence": round(float(cached_bundle.get("confidence_score", 0) or 0), 2),
                    "relationship_stage": cached_bundle.get("relationship_stage"),
                    "latency_ms": cached_bundle["latency_ms"],
                    "plan": tier,
                    "tokens_used": cached_tokens,
                })
                from fastapi.responses import JSONResponse
                return JSONResponse(
                    content=cached_bundle,
                    headers={"X-Tokens-Used": str(cached_tokens)},
                )
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

        # Fall back to on-demand build — enforced 3s timeout (PDF guardrail)
        if not context_bundle:
            context_bundle = call_with_timeout(
                build_context_bundle,
                db, org_id, request.entity, request.situation,
                fallback=None,  # timeout uses LLM_TIMEOUT_SECONDS env var (default 30s)
            )
            if context_bundle is None:
                raise HTTPException(
                    status_code=504,
                    detail={
                        "error": "TIMEOUT",
                        "message": "Context build timed out (3s limit). Try again or simplify the entity name.",
                    },
                )

        # Handle error from bundle_builder (entity not found / below score floor)
        if context_bundle.get("error"):
            err = context_bundle["error"]
            if err == "ENTITY_BELOW_SCORE_FLOOR":
                logger.warning(f"Score floor block for {request.entity}: confidence too low")
                context_error("LOW_CONFIDENCE", f"Contact '{request.entity}' has insufficient confidence score (below 0.20).", 422)
            else:
                logger.warning(f"Entity not found: {request.entity}")
                context_error("ENTITY_NOT_FOUND", f"Contact '{request.entity}' not found in your network.", 404)

        # Handle low-confidence warning (0.20–0.45 range)
        if context_bundle.get("confidence", 1.0) < 0.40:
            logger.warning(f"Confidence low for {request.entity}: {context_bundle.get('confidence')}")
            context_bundle["_warning"] = "LOW_CONFIDENCE"

        # Apply plan-based depth gating + token truncation
        plan_info = get_org_plan(db, org_id)
        tier = plan_info["tier"]
        context_bundle = apply_bundle_depth(context_bundle, tier)
        context_bundle = truncate_bundle_tokens(context_bundle, tier)

        # Token accounting (1 token ≈ 4 chars)
        tokens_used = max(1, len(context_bundle.get("context_for_agent", "")) // 4)

        # Situation missing flag (2.4 — irregular caller handling)
        if request.situation is None:
            context_bundle["situation_missing"] = True

        # Add context versioning fields
        context_bundle["bundle_id"] = str(uuid.uuid4())
        context_bundle["generated_at"] = datetime.now(timezone.utc).isoformat()
        context_bundle["latency_ms"] = int((time.time() - start_time) * 1000)
        context_bundle["cache_hit"] = False
        context_bundle["plan_tier"] = tier
        context_bundle["tokens_used"] = tokens_used
        if segment_name:
            context_bundle["segment_name"] = segment_name
            context_bundle["segment_id"] = request.segment_id

        # Log the call
        log_context_call(db, org_id, request.entity, context_bundle, cache_hit=False,
                         source=source, agent_id=request.agent_id, tokens_used=tokens_used)

        from app.core.analytics import capture
        capture(org_id, "api_context_requested", {
            "source": source,
            "cache_hit": False,
            "confidence": round(float(context_bundle.get("confidence_score", 0) or 0), 2),
            "relationship_stage": context_bundle.get("relationship_stage"),
            "latency_ms": context_bundle.get("latency_ms"),
            "plan": tier,
            "tokens_used": tokens_used,
        })

        # Build response headers (quota info + token count)
        response_headers = {"X-Tokens-Used": str(tokens_used)}
        if source == "api":
            quota = check_period_quota(db, org_id)
            remaining = max(0, quota.get("daily_limit", 0) - quota.get("daily_used", 0))
            response_headers["X-Quota-Remaining"] = str(remaining)
            response_headers["X-Quota-Period-Remaining"] = str(
                max(0, quota.get("period_limit", 0) - quota.get("period_used", 0))
            )
            if quota.get("warning"):
                response_headers["X-Quota-Warning"] = "true"
            if quota.get("overage"):
                response_headers["X-Quota-Overage"] = "true"

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

        from fastapi.responses import JSONResponse
        return JSONResponse(content=context_bundle, headers=response_headers)

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
    # Phase 9 spec fields
    context_id: str = None
    outcome: Union[str, dict]  # "success"|"failure"|"partial" OR {"type": "EXECUTED|EDITED|..."}
    outcome_notes: str = None
    # Legacy agent-execution fields (backward compat)
    session_id: str = None
    agent_id: str = None
    action_type: str = None
    target_entity: str = None
    interaction_record: dict = None


# Confidence deltas per outcome quality
_OUTCOME_CONFIDENCE_DELTA = {"success": 0.05, "partial": 0.02, "failure": -0.03}


@router.post("/v1/context/outcome")
def report_context_outcome(
    request: ContextOutcomeRequest,
    db: Session = Depends(get_db),
    org_id: str = Depends(verify_api_key),
):
    """
    Record context call quality feedback for the learning loop.
    - Trial: stored but no updates applied.
    - Hustler: stored for passive collection, no confidence updates.
    - Startup: stored + immediate confidence delta applied to contact.
    Also handles legacy agent-execution outcomes (action_type + outcome dict).
    """
    try:
        plan_info = get_org_plan(db, org_id)
        tier = plan_info["tier"]

        # ── Detect schema: new spec vs legacy ─────────────────────────────
        is_new_schema = isinstance(request.outcome, str) or request.context_id is not None
        aer_delta = 0.0

        if is_new_schema:
            # New spec: context_id + outcome string + outcome_notes
            outcome_str = request.outcome if isinstance(request.outcome, str) else "success"
            if outcome_str not in ("success", "failure", "partial"):
                raise HTTPException(status_code=400, detail="outcome must be success, failure, or partial")

            confidence_delta = _OUTCOME_CONFIDENCE_DELTA.get(outcome_str, 0.0)

            # Store in context_outcomes regardless of plan (Trial: applied=False)
            db.execute(
                text("""
                    INSERT INTO context_outcomes
                        (org_id, context_id, outcome, outcome_notes, confidence_delta, applied)
                    VALUES
                        (:org_id, :context_id, :outcome, :outcome_notes, :delta, :applied)
                """),
                {
                    "org_id": org_id,
                    "context_id": request.context_id,
                    "outcome": outcome_str,
                    "outcome_notes": request.outcome_notes,
                    "delta": confidence_delta,
                    "applied": False,
                },
            )

            # Startup only: apply confidence delta immediately to the linked contact
            applied = False
            if tier == "startup" and request.context_id and confidence_delta != 0.0:
                try:
                    contact_row = db.execute(
                        text("""
                            SELECT c.id FROM context_calls cc
                            JOIN contacts c ON c.name = cc.entity_name AND c.org_id = cc.org_id
                            WHERE cc.id = :ctx_id AND cc.org_id = :org_id
                            LIMIT 1
                        """),
                        {"ctx_id": request.context_id, "org_id": org_id},
                    ).fetchone()

                    if contact_row:
                        db.execute(
                            text("""
                                UPDATE contacts
                                SET confidence_score = GREATEST(0.0, LEAST(1.0,
                                    COALESCE(confidence_score, 0.5) + :delta))
                                WHERE id = :contact_id AND org_id = :org_id
                            """),
                            {"delta": confidence_delta, "contact_id": str(contact_row[0]), "org_id": org_id},
                        )
                        db.execute(
                            text("UPDATE context_outcomes SET applied = TRUE WHERE context_id = :ctx_id AND org_id = :org_id AND applied = FALSE"),
                            {"ctx_id": request.context_id, "org_id": org_id},
                        )
                        applied = True
                except Exception as e:
                    logger.warning(f"Confidence delta failed for context {request.context_id}: {e}")
                    db.rollback()

            db.commit()
            plan_effect = "active" if tier == "startup" else ("passive" if tier == "hustler" else "stored")
            return {
                "learned": True,
                "plan_effect": plan_effect,
                "confidence_delta_applied": applied,
                "confidence_delta": confidence_delta if applied else 0.0,
            }

        # ── Legacy schema: action_type + outcome dict ──────────────────────
        if not request.action_type:
            raise HTTPException(status_code=400, detail="action_type is required for legacy outcome schema")

        outcome_type = request.outcome.get("type", "EXECUTED") if isinstance(request.outcome, dict) else "EXECUTED"
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

        if outcome_type == "EXECUTED":
            aer_delta = 0.02
        elif outcome_type == "EDITED":
            aer_delta = 0.01

        time_delta = 5.0 / 60.0 if outcome_type == "EXECUTED" else (2.0 / 60.0 if outcome_type == "EDITED" else 0.0)

        if aer_delta > 0 or time_delta > 0:
            db.execute(
                text("""
                    UPDATE orgs
                    SET aer = LEAST(1.0, COALESCE(aer, 0) + :aer_delta),
                        time_saved_hours = COALESCE(time_saved_hours, 0) + :time_delta
                    WHERE id = :org_id
                """),
                {"org_id": org_id, "aer_delta": aer_delta, "time_delta": time_delta},
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


@router.get("/api/org/{org_id}/reports")
def get_graph_reports(
    org_id: str,
    limit: int = 10,
    db: Session = Depends(get_db),
):
    """Dashboard endpoint: weekly graph intelligence reports (Startup plan only)."""
    try:
        rows = db.execute(
            text("""
                SELECT id, week_start, summary, generated_at
                FROM graph_intelligence_reports
                WHERE org_id = :org_id
                ORDER BY week_start DESC
                LIMIT :limit
            """),
            {"org_id": org_id, "limit": min(limit, 52)},
        ).fetchall()

        return {
            "reports": [
                {
                    "id": str(r[0]),
                    "week_start": r[1].isoformat() if r[1] else None,
                    "summary": r[2] if isinstance(r[2], dict) else {},
                    "generated_at": r[3].isoformat() if r[3] else None,
                }
                for r in rows
            ]
        }
    except Exception as e:
        logger.error(f"Graph reports fetch failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch reports")


@router.get("/api/org/{org_id}/context/history")
def get_context_history(
    org_id: str,
    page: int = 1,
    limit: int = 50,
    db: Session = Depends(get_db),
):
    """Dashboard endpoint: paginated context call log for Startup-only lifecycle view."""
    limit = min(limit, 100)
    offset = (page - 1) * limit
    try:
        total = db.execute(
            text("SELECT COUNT(*) FROM context_calls WHERE org_id = :org_id"),
            {"org_id": org_id},
        ).scalar() or 0

        rows = db.execute(
            text("""
                SELECT entity_name, confidence, cache_hit, source, agent_id, tokens_used, called_at
                FROM context_calls
                WHERE org_id = :org_id
                ORDER BY called_at DESC
                LIMIT :limit OFFSET :offset
            """),
            {"org_id": org_id, "limit": limit, "offset": offset},
        ).fetchall()

        calls = [
            {
                "entity_name": r[0],
                "confidence": float(r[1]) if r[1] is not None else None,
                "cache_hit": bool(r[2]),
                "source": r[3],
                "agent_id": r[4],
                "tokens_used": r[5],
                "called_at": r[6].isoformat() if r[6] else None,
            }
            for r in rows
        ]
        return {"calls": calls, "total": total, "page": page}
    except Exception as e:
        logger.error(f"Context history failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch context history")


@router.get("/v1/llms.txt")
def get_llms_txt(
    org_id: str = Depends(verify_api_key),
    db: Session = Depends(get_db),
):
    """Dynamic per-org llms.txt — plain text summary of top 10 relationships for LLM-native tools."""
    from fastapi.responses import PlainTextResponse

    rows = db.execute(text("""
        SELECT name, company, entity_type, relationship_stage,
               sentiment_avg, interaction_count, last_interaction_at,
               composite_score
        FROM contacts
        WHERE org_id = :org_id AND (is_archived = FALSE OR is_archived IS NULL)
        ORDER BY composite_score DESC NULLS LAST
        LIMIT 10
    """), {"org_id": org_id}).fetchall()

    graph_stats = db.execute(text("""
        SELECT COUNT(*) as total_contacts,
               COUNT(CASE WHEN relationship_stage = 'ACTIVE' THEN 1 END) as active,
               AVG(composite_score) as avg_score
        FROM contacts WHERE org_id = :org_id AND (is_archived = FALSE OR is_archived IS NULL)
    """), {"org_id": org_id}).fetchone()

    lines = [
        "# GeniOS Brain — Organizational Context Summary",
        f"# Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
        f"# Total contacts: {graph_stats.total_contacts or 0}",
        f"# Active relationships: {graph_stats.active or 0}",
        f"# Avg graph quality: {round(float(graph_stats.avg_score or 0), 2)}",
        "",
        "## Top 10 Relationships",
        "",
    ]

    for r in rows:
        stage = r.relationship_stage or "unknown"
        last = r.last_interaction_at.strftime("%Y-%m-%d") if r.last_interaction_at else "never"
        lines.append(
            f"- {r.name} ({r.company or 'unknown'}) | {r.entity_type or 'contact'} | "
            f"Stage: {stage} | Interactions: {r.interaction_count or 0} | "
            f"Last: {last} | Score: {round(float(r.composite_score or 0), 2)}"
        )

    lines.append("")
    lines.append("## API")
    lines.append("- POST /v1/context — Get context bundle before agent action")
    lines.append("- POST /v1/context/outcome — Report action outcome")
    lines.append("- POST /v1/context/search — Search contacts by stage/recency")

    return PlainTextResponse("\n".join(lines))
