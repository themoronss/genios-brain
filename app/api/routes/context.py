from fastapi import APIRouter, Depends, HTTPException, Header
from pydantic import BaseModel, root_validator, validator
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.api.deps import get_db, verify_api_key, check_rpm_limit, check_abuse_detection, preflight_ratelimit, get_auth_ctx
from app.context.bundle_builder import build_context_bundle
from app.policy import scope_filter
from app.policy.scope_loader import AuthCtx
from app.coordination import blackboard
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
    context_size: str = "medium"  # small | medium | large (per CLM spec)
    agent_id: str = None      # Optional — identifies which agent is calling
    segment_id: str = None    # Optional — scope bundle to contacts in this segment
    tag: str = None           # Optional — only return entity if it has this tag
    as_of: str = None         # Phase 2 bitemporal: ISO-8601 timestamp ("what did we know on date X")

    @validator("entity")
    def validate_entity(cls, v):
        if not v or len(v.strip()) < 2:
            raise ValueError("Entity name must be at least 2 characters")
        if len(v) > 200:
            raise ValueError("Entity name too long")
        return v.strip()

    @validator("as_of")
    def validate_as_of(cls, v):
        if v is None:
            return v
        from datetime import datetime
        try:
            datetime.fromisoformat(v.replace("Z", "+00:00"))
        except Exception:
            raise ValueError("as_of must be an ISO-8601 timestamp")
        return v


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
    latency_ms: int = None,
    cache_source: str = None,
    scope_hash: str = None,
    scope_blocked: bool = False,
    scope_source: str = None,
):
    """
    Log every context API call to context_calls table.
    Non-blocking — failures are silently swallowed so they never affect the response.

    source:        'api' (external agent) or 'dashboard' (internal UI click)
    cache_source:  'precomputed' | 'redis' | 'minimal' | 'fresh' — feeds benchmarks p95 by path
    scope_*:       per Agent Registry PRD §06 — audit trail for who saw what
    """
    try:
        entity = context_bundle.get("entity") or {}
        db.execute(
            text(
                """
                INSERT INTO context_calls
                    (org_id, entity_name, relationship_stage, action_recommendation,
                     confidence, cache_hit, source, agent_id, tokens_used,
                     latency_ms, cache_source, scope_hash, scope_blocked, scope_source,
                     called_at)
                VALUES
                    (:org_id, :entity_name, :stage, :action, :confidence, :cache_hit,
                     :source, :agent_id, :tokens_used,
                     :latency_ms, :cache_source, :scope_hash, :scope_blocked, :scope_source,
                     NOW())
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
                "latency_ms": latency_ms,
                "cache_source": cache_source,
                "scope_hash": scope_hash,
                "scope_blocked": scope_blocked,
                "scope_source": scope_source,
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
    auth: AuthCtx = Depends(get_auth_ctx),
    x_genios_source: str = Header(None, alias="X-GeniOS-Source"),
):
    """
    Get context bundle for an entity.

    Identity is server-derived from the Bearer key (Agent Registry PRD §03).
    The `agent_id` field on the request body is **logged for audit only** —
    it cannot grant or change scope.
    """
    try:
        start_time = time.time()
        segment_name = None
        org_id = auth.org_id

        # Server-derived agent_id always wins. Body's agent_id is kept only
        # for backward-compat logging.
        derived_agent_id = auth.agent_id or request.agent_id

        # Determine call source: dashboard UI vs external agent
        source = "dashboard" if x_genios_source == "dashboard" else "api"

        # ── Dashboard-passive billing toggle ──────────────────────────────
        # Dashboard renders (open contact page, click node) MUST NOT
        # decrement the user-visible credit meter, even if the internal
        # bundle build path lazily calls an LLM for narrative/reasoner/
        # response-shape. API integrators DO consume credits — they're
        # using GeniOS as a paid service.
        #
        # We flip a request-scoped contextvar; llm_client.call reads it
        # and skips deduct when False. Token is reset in the outer
        # finally below regardless of which return-path the handler takes.
        from app.credits.billing_context import (
            disable_billing_for_request, restore_billing,
        )
        _billing_token = disable_billing_for_request() if source == "dashboard" else None

        # Phase 2: bitemporal short-circuit. When as_of is set we bypass the
        # normal cache/build pipeline and return a historical snapshot from
        # event_log + versioned rows.
        # (Run BEFORE preflight — historical queries aren't rate-limited the
        # same way; we still want abuse detection to apply though.)
        if request.as_of:
            # Minimal abuse-flag check only; full preflight applies to live pulls.
            check_abuse_detection(org_id)
            from app.memory.as_of import build_as_of_bundle
            snapshot = build_as_of_bundle(db, org_id, request.entity, request.as_of)
            if snapshot.get("error"):
                code = snapshot["error"]
                status_map = {"INVALID_AS_OF": 400, "NO_HISTORY_AT_AS_OF": 404}
                raise HTTPException(
                    status_code=status_map.get(code, 400),
                    detail={"error": code, "message": f"{code}: {request.as_of}"},
                )
            snapshot["other_agents_active"] = blackboard.peek(
                org_id, request.entity.lower().strip()
            )
            from fastapi.responses import JSONResponse
            return JSONResponse(content=snapshot)

        # Single-pipeline preflight for API callers: abuse + RPM + RPH + loop
        # in one Redis round-trip. Dashboard calls skip rate limiting.
        if source == "api":
            plan_info = get_org_plan(db, org_id)
            preflight_ratelimit(
                org_id,
                request.agent_id,
                plan_info["tier"],
                entity=request.entity,
                check_loop=True,
            )

            # Validate agent_id against registered_agents (2.4 — irregular caller handling)
            # Only enforced when org has registered at least one agent.
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
        else:
            # Dashboard path — abuse flag only (no RPM / loop enforcement)
            check_abuse_detection(org_id)
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

        # ── Segment lock check ────────────────────────────────────────────
        # If a contact exists but is in a locked segment (beyond tier's max_clusters),
        # return 403 with entity_exists=true so agents know data is behind a gate.
        segment_name = None
        if source == "api":
            _plan = plan_info if "plan_info" in dir() else get_org_plan(db, org_id)
            _tier = _plan["tier"]
            _max_clusters = _plan["config"]["max_clusters"]

            locked_check = db.execute(
                text("""
                    SELECT c.id, c.segment_id, gs.cluster_type, gs.name,
                           ROW_NUMBER() OVER (PARTITION BY gs.org_id ORDER BY gs.created_at) AS seg_rank
                    FROM contacts c
                    LEFT JOIN graph_segments gs ON gs.id = c.segment_id AND gs.org_id = c.org_id
                    WHERE c.org_id = :org_id
                      AND LOWER(TRIM(c.name)) = LOWER(TRIM(:entity))
                    LIMIT 1
                """),
                {"org_id": org_id, "entity": request.entity.strip()},
            ).fetchone()

            if locked_check and locked_check[1] is not None:
                # Check if this contact's segment is beyond the tier's allowed count
                seg_rank_row = db.execute(
                    text("""
                        SELECT COUNT(*) FROM graph_segments
                        WHERE org_id = :org_id AND created_at <= (
                            SELECT created_at FROM graph_segments WHERE id = :sid
                        )
                    """),
                    {"org_id": org_id, "sid": str(locked_check[1])},
                ).fetchone()
                seg_rank = seg_rank_row[0] if seg_rank_row else 0

                if seg_rank > _max_clusters:
                    raise HTTPException(
                        status_code=403,
                        detail={
                            "error": "SEGMENT_LOCKED",
                            "message": f"'{request.entity}' is in the '{locked_check[3]}' segment which requires a higher plan.",
                            "entity_exists": True,
                            "entity_preview": None,
                            "segment": locked_check[2],
                            "tier_required": "startup" if _max_clusters < 10 else _tier,
                            "upgrade_url": "https://genios.ai/upgrade",
                        },
                    )

        # Segment scoping: if segment_id provided, verify entity is a member
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
                # Check if entity exists at all (for better 403)
                entity_exists = db.execute(
                    text("""
                        SELECT 1 FROM contacts
                        WHERE org_id = :org_id AND LOWER(TRIM(name)) = LOWER(TRIM(:entity))
                        LIMIT 1
                    """),
                    {"org_id": org_id, "entity": request.entity.strip()},
                ).fetchone()
                raise HTTPException(
                    status_code=403,
                    detail={
                        "error": "ENTITY_NOT_IN_SEGMENT",
                        "message": f"'{request.entity}' is not a member of segment '{segment_name}'.",
                        "segment_id": request.segment_id,
                        "entity_exists": entity_exists is not None,
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
                if not derived_agent_id or derived_agent_id not in allowed:
                    raise HTTPException(
                        status_code=403,
                        detail={
                            "error": "CONTACT_RESTRICTED",
                            "message": f"'{request.entity}' is restricted. Agent '{derived_agent_id}' is not authorized.",
                            "agent_id": derived_agent_id,
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

        # ── Agent Registry scope pre-check (PRD §07) ──────────────────────────
        # If the calling agent's scope policy excludes this entity, return 404
        # not_in_scope before we waste cycles building a bundle. Audit log
        # captures every blocked attempt with scope_hash for SOC 2 trail.
        scope_hash = scope_filter.policy_hash(auth.policy)
        if not scope_filter.is_unrestricted(auth.policy):
            try:
                in_scope = scope_filter.is_entity_in_scope(
                    db, org_id, request.entity, auth.policy, agent_uuid=auth.agent_uuid
                )
            except Exception as _se:
                logger.warning(f"scope pre-check failed (failing open): {_se}")
                in_scope = True
            if not in_scope:
                try:
                    log_context_call(
                        db, org_id, request.entity, {"entity": {}},
                        cache_hit=False, source=source,
                        agent_id=derived_agent_id,
                        latency_ms=int((time.time() - start_time) * 1000),
                        scope_hash=scope_hash, scope_blocked=True,
                        scope_source=auth.scope_source,
                    )
                except Exception:
                    pass
                raise HTTPException(
                    status_code=404,
                    detail={
                        "error": "NOT_IN_SCOPE",
                        "message": f"'{request.entity}' is not visible to agent '{derived_agent_id or 'default'}'.",
                        "agent_id": derived_agent_id,
                        "scope_source": auth.scope_source,
                    },
                )

        # ── Phase 2: Intent + Emotion classification (entry-point) ───────────
        # One Haiku call (cached 5min) returns {intent, domain, emotion, urgency,
        # requires_live_fetch, confidence}. Drives bundle live-fetch + tone shaping.
        # Fail-soft — never blocks request. Returns neutral default on any error.
        intent_signal = None
        try:
            from app.intent import classify as classify_intent
            intent_signal = classify_intent(
                f"{request.entity} {request.situation or ''}".strip(),
                org_id=org_id,
            )
            logger.info(
                f"intent_signal entity={request.entity[:40]} "
                f"intent={intent_signal.intent} emotion={intent_signal.emotion} "
                f"urgency={intent_signal.urgency} live={intent_signal.requires_live_fetch}"
            )
        except Exception as _e:
            logger.debug(f"intent classify skipped: {_e}")

        # ── Cache lookup: precomputed (situation-independent) → Redis → fresh build ──
        # Layer 1: Precomputed bundles (24h TTL, situation-independent, highest hit rate)
        context_bundle = None
        cache_key = get_cache_key(org_id, request.entity, request.situation)

        try:
            precomputed = db.execute(
                text("""
                    SELECT pb.bundle, pb.generated_at, c.id
                    FROM precomputed_bundles pb
                    JOIN contacts c ON pb.contact_id = c.id AND pb.org_id = c.org_id
                    WHERE pb.org_id = :org_id
                    AND (
                        LOWER(c.name) = LOWER(:entity_name)
                        OR LOWER(c.email) = LOWER(:entity_name)
                    )
                    AND pb.expires_at > NOW()
                    LIMIT 1
                """),
                {"org_id": org_id, "entity_name": request.entity.strip()}
            ).fetchone()

            if precomputed and precomputed[0]:
                context_bundle = precomputed[0] if isinstance(precomputed[0], dict) else json.loads(precomputed[0])
                if precomputed[1]:
                    age = (datetime.now(timezone.utc) - precomputed[1]).total_seconds()
                    context_bundle["cache_age_seconds"] = int(age)
                # Apply scope policy to bundle facts — precomputed rows are
                # built once for the org and don't know who's calling, so we
                # post-filter here. Cheap (~µs) since it's a list comprehension.
                if not scope_filter.is_unrestricted(auth.policy):
                    if isinstance(context_bundle.get("facts"), list):
                        context_bundle["facts"] = scope_filter.filter_facts(
                            context_bundle["facts"], auth.policy
                        )
                logger.info(f"Serving pre-computed bundle for {request.entity}")

                cached_tokens = max(1, len(context_bundle.get("context_for_agent", "")) // 4)
                _lat = int((time.time() - start_time) * 1000)
                log_context_call(
                    db, org_id, request.entity,
                    context_bundle,
                    cache_hit=True,
                    source=source,
                    agent_id=derived_agent_id,
                    tokens_used=cached_tokens,
                    latency_ms=_lat,
                    cache_source="precomputed",
                    scope_hash=scope_hash, scope_source=auth.scope_source,
                )
                context_bundle["latency_ms"] = _lat
                context_bundle["cache_hit"] = True
                context_bundle["cache_source"] = "precomputed"
                context_bundle["other_agents_active"] = blackboard.peek(org_id, request.entity.lower().strip())
                # Phase 2: attach fresh intent signal even on cache hit
                if intent_signal is not None:
                    try:
                        context_bundle["intent_signal"] = intent_signal.model_dump()
                    except Exception:
                        pass
                from app.core.analytics import capture as _capture
                _capture(org_id, "api_context_requested", {
                    "source": source,
                    "cache_hit": True,
                    "cache_source": "precomputed",
                    "confidence": round(float(context_bundle.get("confidence_score", 0) or 0), 2),
                    "relationship_stage": context_bundle.get("relationship_stage"),
                    "latency_ms": context_bundle["latency_ms"],
                    "plan": _tier if source == "api" else "dashboard",
                    "tokens_used": cached_tokens,
                })
                from fastapi.responses import JSONResponse
                return JSONResponse(
                    content=context_bundle,
                    headers={"X-Tokens-Used": str(cached_tokens)},
                )
        except Exception as e:
            logger.debug(f"Pre-computed bundle lookup failed: {e}")

        # Layer 2: Redis cache (60s TTL, situation-keyed, for repeat identical calls)
        try:
            cached = redis_client.get(cache_key)
            if cached:
                logger.info(f"Redis cache hit for {request.entity}")
                cached_bundle = json.loads(cached) if isinstance(cached, (str, bytes)) else {}
                cached_tokens = max(1, len(cached_bundle.get("context_for_agent", "")) // 4)
                _lat = int((time.time() - start_time) * 1000)
                log_context_call(
                    db, org_id, request.entity,
                    cached_bundle,
                    cache_hit=True,
                    source=source,
                    agent_id=derived_agent_id,
                    tokens_used=cached_tokens,
                    latency_ms=_lat,
                    cache_source="redis",
                    scope_hash=scope_hash, scope_source=auth.scope_source,
                )
                cached_bundle["latency_ms"] = _lat
                cached_bundle["cache_hit"] = True
                cached_bundle["cache_source"] = "redis"
                cached_bundle["other_agents_active"] = blackboard.peek(org_id, request.entity.lower().strip())
                from app.core.analytics import capture as _capture
                _capture(org_id, "api_context_requested", {
                    "source": source,
                    "cache_hit": True,
                    "cache_source": "redis",
                    "confidence": round(float(cached_bundle.get("confidence_score", 0) or 0), 2),
                    "relationship_stage": cached_bundle.get("relationship_stage"),
                    "latency_ms": cached_bundle["latency_ms"],
                    "plan": _tier if source == "api" else "dashboard",
                    "tokens_used": cached_tokens,
                })
                from fastapi.responses import JSONResponse
                return JSONResponse(
                    content=cached_bundle,
                    headers={"X-Tokens-Used": str(cached_tokens)},
                )
        except Exception as redis_error:
            logger.warning(f"Redis cache read failed: {redis_error}")

        # Layer 3: Minimal-real fallback + enqueue full refresh.
        #
        # GeniOS is a context-intelligence API — agents calling on the hot
        # path must get *real* data, never an empty pack. If the pre-computed
        # bundle is missing (new contact / first pull / eviction), we serve a
        # minimal real bundle from a single indexed query (<150ms) and enqueue
        # the full rebuild. The next pull hits Layer 1 with the rich shape.
        if not context_bundle:
            from app.context.minimal_bundle import build_minimal_bundle
            _dv = (auth.policy or {}).get("data_visibility", "all") if auth.policy else "all"
            minimal = build_minimal_bundle(
                db, org_id, request.entity,
                requesting_agent_uuid=auth.agent_uuid,
                data_visibility=_dv,
            )

            if minimal:
                # Trigger the full pre-compute so next call upgrades to rich data.
                try:
                    from app.celery_app import task_refresh_bundle
                    task_refresh_bundle.delay(org_id, minimal["entity"]["id"])
                except Exception as enq_err:
                    logger.debug(f"bundle refresh enqueue failed: {enq_err}")

                minimal["latency_ms"] = int((time.time() - start_time) * 1000)
                minimal["cache_hit"] = False
                minimal["cache_source"] = "minimal"

                log_context_call(
                    db, org_id, request.entity, minimal, cache_hit=False,
                    source=source, agent_id=derived_agent_id,
                    tokens_used=max(1, len(minimal.get("context_for_agent", "")) // 4),
                    latency_ms=minimal["latency_ms"],
                    cache_source="minimal",
                    scope_hash=scope_hash, scope_source=auth.scope_source,
                )

                minimal["other_agents_active"] = blackboard.peek(
                    org_id, request.entity.lower().strip()
                )
                # Phase 2: attach intent_signal so callers see the classifier output
                if intent_signal is not None:
                    try:
                        minimal["intent_signal"] = intent_signal.model_dump()
                    except Exception:
                        pass
                from fastapi.responses import JSONResponse
                return JSONResponse(content=minimal)

            # ── Phase 1: Live Tool Dispatch fallback (was 404) ───────────
            # Graph + minimal both missed. Before giving up, try going LIVE
            # into Gmail / Calendar / uploaded docs. Returns a 200 with
            # `live_fetch` payload when anything found; falls through to 404
            # only when truly nothing exists anywhere.
            #
            # IMPORTANT: Gmail `q=` does AND-match across whitespace tokens.
            # If the entity didn't resolve, including its raw text in the
            # query guarantees zero hits. Prefer situation-only when present;
            # fall back to entity only when no situation provided.
            try:
                from app.retrieval import live_dispatcher
                situation_clean = (request.situation or "").strip()
                live_query = situation_clean if situation_clean else request.entity
                live_results = live_dispatcher.dispatch(
                    org_id, live_query, limit_per_source=5,
                )
                if live_results.get("total"):
                    live_text = live_dispatcher.format_for_bundle(live_results)
                    payload = {
                        "entity_name": request.entity,
                        "context_for_agent": (
                            f"No cached profile for {request.entity}. "
                            f"Pulled {live_results['total']} live items from "
                            f"{', '.join(live_results['sources_hit'])}:\n\n{live_text}"
                        ),
                        "confidence": 0.55,
                        "matched_from": request.entity,
                        "resolution_method": "live_tool_fetch",
                        "live_fetch": live_results,
                        "fallback_used": True,
                        "cache_hit": False,
                        "cache_source": "live",
                        "latency_ms": int((time.time() - start_time) * 1000),
                    }
                    if intent_signal is not None:
                        try:
                            payload["intent_signal"] = intent_signal.model_dump()
                        except Exception:
                            pass
                    log_context_call(
                        db, org_id, request.entity, payload, cache_hit=False,
                        source=source, agent_id=derived_agent_id,
                        tokens_used=max(1, len(payload.get("context_for_agent", "")) // 4),
                        latency_ms=payload["latency_ms"],
                        cache_source="live",
                        scope_hash=scope_hash, scope_source=auth.scope_source,
                    )
                    from fastapi.responses import JSONResponse
                    return JSONResponse(content=payload)
            except Exception as live_err:
                logger.debug(f"live dispatch fallback failed: {live_err}")

            # Entity truly unknown in this org — that's a real 404.
            context_error(
                "ENTITY_NOT_FOUND",
                f"Contact '{request.entity}' not found in your network.",
                404,
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
                         source=source, agent_id=derived_agent_id, tokens_used=tokens_used,
                         latency_ms=context_bundle.get("latency_ms"), cache_source="fresh",
                         scope_hash=scope_hash, scope_source=auth.scope_source)

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

        # Cache — TTL from env (default 300s / 5 min)
        from app.context.cache import CACHE_TTL_SECONDS
        try:
            redis_client.setex(
                cache_key,
                CACHE_TTL_SECONDS,
                json.dumps(context_bundle, default=str),
            )
            logger.info(f"Cached context for {request.entity}")
        except Exception as redis_error:
            logger.warning(f"Redis cache write failed: {redis_error}")

        # Attach live blackboard peek (never cached — always fresh)
        context_bundle["other_agents_active"] = blackboard.peek(org_id, request.entity.lower().strip())

        from fastapi.responses import JSONResponse
        return JSONResponse(content=context_bundle, headers=response_headers)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in get_context: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")
    finally:
        # Always restore the billing flag, no matter which path the
        # handler took. restore_billing(None) is a no-op so this is safe
        # even on the api/integrator path where billing stayed enabled.
        try:
            restore_billing(_billing_token)
        except Exception:
            pass


class DashboardContextRequest(BaseModel):
    entity_name: str
    situation: str = None

@router.post("/api/org/{org_id}/context")
def get_dashboard_context(org_id: str, request: DashboardContextRequest, db: Session = Depends(get_db)):
    """Internal endpoint for dashboard testing — never bills credits.

    Hits the same bundle pipeline as `/v1/context` but bypasses the API
    key path. Always treated as dashboard-passive: opening this from the
    UI must not decrement user credits even if narrative/reasoner LLM
    calls fire under the hood.
    """
    from app.credits.billing_context import billing_disabled
    try:
        with billing_disabled():
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
    auth: AuthCtx = Depends(get_auth_ctx),
):
    """Temporal and topic-anchored search, returns ranked contacts (scope-aware)."""
    try:
        start_time = time.time()
        org_id = auth.org_id
        filters = request.filter
        conditions = ["c.org_id = :org_id", "c.relationship_stage IS NOT NULL", "c.relationship_stage != 'unknown'"]
        params: dict = {"org_id": org_id, "limit": min(request.limit, 25)}

        # Agent Registry scope filter — same as /v1/contacts list
        _frag, _binds = scope_filter.contact_clauses(auth.policy, contact_alias="c")
        if _frag:
            conditions.append(_frag.strip().removeprefix("AND "))
            params.update(_binds)

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
            order = "c.context_score DESC NULLS LAST, c.interaction_count DESC"

        results = db.execute(
            text(f"""
                SELECT
                    c.id, c.name, c.email, c.company, c.relationship_stage,
                    c.sentiment_avg, c.interaction_count, c.last_interaction_at,
                    c.entity_type, c.confidence_score, c.freshness_score,
                    c.context_score
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
                "context_score": float(r[11] or 0.5),
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
    auth: AuthCtx = Depends(get_auth_ctx),
    x_genios_source: str = Header(None, alias="X-GeniOS-Source"),
):
    """Pull full context for a specific entity by ID (contact UUID, scope-aware).

    Dashboard clicks send `X-GeniOS-Source: dashboard` → bills as
    passive view (no credit deduct). API integrators get charged.
    """
    import uuid as _uuid
    from app.credits.billing_context import billing_disabled
    org_id = auth.org_id
    try:
        _uuid.UUID(entity_id)
    except (ValueError, AttributeError):
        raise HTTPException(
            status_code=404,
            detail={"error_code": "entity_not_found", "message": f"Entity {entity_id} not found"},
        )

    is_dashboard = x_genios_source == "dashboard"
    try:
        # Pull contact with scope filter applied — out-of-scope = 404.
        _frag, _binds = scope_filter.contact_clauses(auth.policy, contact_alias="c")
        sql = (
            "SELECT c.name FROM contacts c WHERE c.id = :id AND c.org_id = :org_id"
            + _frag
            + " LIMIT 1"
        )
        contact = db.execute(text(sql), {"id": entity_id, "org_id": org_id, **_binds}).fetchone()

        if not contact:
            raise HTTPException(
                status_code=404,
                detail={
                    "error_code": "entity_not_found",
                    "message": f"Entity {entity_id} not found or not in scope.",
                    "agent_id": auth.agent_id,
                },
            )

        _dv = (auth.policy or {}).get("data_visibility", "all") if auth.policy else "all"
        # Wrap bundle build in billing_disabled when dashboard-sourced.
        if is_dashboard:
            with billing_disabled():
                context_bundle = build_context_bundle(
                    db, org_id, contact[0],
                    requesting_agent_uuid=auth.agent_uuid,
                    data_visibility=_dv,
                )
        else:
            context_bundle = build_context_bundle(
                db, org_id, contact[0],
                requesting_agent_uuid=auth.agent_uuid,
                data_visibility=_dv,
            )

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
               context_score
        FROM contacts
        WHERE org_id = :org_id AND (is_archived = FALSE OR is_archived IS NULL)
        ORDER BY context_score DESC NULLS LAST
        LIMIT 10
    """), {"org_id": org_id}).fetchall()

    graph_stats = db.execute(text("""
        SELECT COUNT(*) as total_contacts,
               COUNT(CASE WHEN relationship_stage = 'ACTIVE' THEN 1 END) as active,
               AVG(context_score) as avg_score
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
            f"Last: {last} | Score: {round(float(r.context_score or 0), 2)}"
        )

    lines.append("")
    lines.append("## API")
    lines.append("- POST /v1/context — Get context bundle before agent action")
    lines.append("- POST /v1/context/outcome — Report action outcome")
    lines.append("- POST /v1/context/search — Search contacts by stage/recency")

    return PlainTextResponse("\n".join(lines))
