import hashlib
import time
import logging
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.database import SessionLocal

logger = logging.getLogger(__name__)
security = HTTPBearer()

# ── Kill switch — cached in Redis, checked on every API request ───────────────
_KILL_SWITCH_CACHE_KEY = "feature_flag:kill_switch_all"
_KILL_SWITCH_CACHE_TTL = 10  # seconds — re-check DB at most every 10s


def check_kill_switch():
    """
    Emergency kill switch — if feature_flags.kill_switch_all = FALSE, reject all requests.
    Result is cached in Redis for 10s to avoid a DB hit on every call.
    """
    try:
        from app.redis_client import redis_client
        cached = redis_client.get(_KILL_SWITCH_CACHE_KEY)
        if cached is not None:
            if cached == b"0" or cached == "0":
                raise HTTPException(status_code=503, detail={"error": "SERVICE_UNAVAILABLE", "message": "GeniOS is temporarily offline for maintenance. Please try again shortly."})
            return  # cached as live

        # Cache miss — query DB
        db = SessionLocal()
        try:
            row = db.execute(
                text("SELECT enabled FROM feature_flags WHERE key = 'kill_switch_all' LIMIT 1")
            ).fetchone()
        finally:
            db.close()

        if row is None or row[0]:
            redis_client.setex(_KILL_SWITCH_CACHE_KEY, _KILL_SWITCH_CACHE_TTL, "1")
        else:
            redis_client.setex(_KILL_SWITCH_CACHE_KEY, _KILL_SWITCH_CACHE_TTL, "0")
            raise HTTPException(status_code=503, detail={"error": "SERVICE_UNAVAILABLE", "message": "GeniOS is temporarily offline for maintenance. Please try again shortly."})
    except HTTPException:
        raise
    except Exception as e:
        # Redis/DB failure — fail open (don't block requests on infra errors)
        logger.warning(f"Kill switch check failed (failing open): {e}")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _hash_key(raw_key: str) -> str:
    """SHA-256 hash of an API key for safe at-rest comparison."""
    return hashlib.sha256(raw_key.encode()).hexdigest()


def verify_api_key(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> str:
    """
    Verify API key and return org_id.
    Supports both legacy plain-text keys (for backward compat during migration)
    and future hashed keys.
    """
    check_kill_switch()

    token = credentials.credentials
    if not token.startswith("gn_live_"):
        raise HTTPException(status_code=401, detail="Invalid API Key format")

    hashed = _hash_key(token)
    db = SessionLocal()
    try:
        # Primary lookup: orgs table (plain-text legacy OR hashed column)
        result = db.execute(
            text("""
                SELECT id, subscription_tier, plan_status
                FROM orgs
                WHERE api_key = :raw_key
                   OR api_key_hash = :hashed_key
            """),
            {"raw_key": token, "hashed_key": hashed},
        ).fetchone()

        # Fallback: additional keys in api_keys table (migration 034+)
        if not result:
            result = db.execute(
                text("""
                    SELECT o.id, o.subscription_tier, o.plan_status
                    FROM api_keys ak
                    JOIN orgs o ON ak.org_id = o.id
                    WHERE ak.key_hash = :hashed_key AND ak.is_active = TRUE
                """),
                {"hashed_key": hashed},
            ).fetchone()
            # Update last_used_at for the additional key (non-blocking)
            if result:
                try:
                    db.execute(
                        text("UPDATE api_keys SET last_used_at = NOW() WHERE key_hash = :h"),
                        {"h": hashed},
                    )
                    db.commit()
                except Exception:
                    pass
    finally:
        db.close()

    if not result:
        raise HTTPException(status_code=401, detail="Invalid API Key")

    # Block suspended/expired plans from API access
    plan_status = result.plan_status or "active"
    if plan_status == "suspended":
        raise HTTPException(
            status_code=403,
            detail={"error": "ACCOUNT_SUSPENDED", "message": "Account suspended. Contact support."},
        )

    return str(result[0])


def check_rpm_limit(org_id: str, agent_id: str, plan_tier: str):
    """
    Sliding-window per-agent RPM check using Redis.
    Raises HTTP 429 if over limit.
    """
    try:
        from app.redis_client import redis_client
        from app.plan_enforcer import PLAN_CONFIG

        config = PLAN_CONFIG.get(plan_tier, PLAN_CONFIG["trial"])
        rpm_limit = config["rpm_per_agent"]
        rph_limit = config["rph_org"]

        now = int(time.time())
        minute_window = now - 60
        hour_window = now - 3600

        # Per-agent RPM (sliding window with sorted set)
        agent_key = f"rpm:{org_id}:{agent_id or 'default'}"
        pipe = redis_client.pipeline()
        pipe.zremrangebyscore(agent_key, 0, minute_window)
        pipe.zcard(agent_key)
        pipe.zadd(agent_key, {str(now): now})
        pipe.expire(agent_key, 120)
        results = pipe.execute()
        rpm_count = results[1]

        if rpm_count >= rpm_limit:
            raise HTTPException(
                status_code=429,
                detail={
                    "error": "RATE_LIMITED",
                    "message": f"Rate limit exceeded: {rpm_limit} requests/minute per agent.",
                    "retry_after": 60,
                },
                headers={"Retry-After": "60"},
            )

        # Org-level RPH (sliding window)
        org_key = f"rph:{org_id}"
        pipe2 = redis_client.pipeline()
        pipe2.zremrangebyscore(org_key, 0, hour_window)
        pipe2.zcard(org_key)
        pipe2.zadd(org_key, {str(now): now})
        pipe2.expire(org_key, 7200)
        results2 = pipe2.execute()
        rph_count = results2[1]

        if rph_count >= rph_limit:
            raise HTTPException(
                status_code=429,
                detail={
                    "error": "RATE_LIMITED",
                    "message": f"Org rate limit exceeded: {rph_limit} requests/hour.",
                    "retry_after": 3600,
                },
                headers={"Retry-After": "3600"},
            )

    except HTTPException:
        raise
    except Exception as e:
        # Redis failure → allow through (don't block on cache errors)
        logger.warning(f"RPM check failed (non-critical): {e}")


def check_abuse_detection(org_id: str):
    """
    Abuse detection: auto-flag orgs making >1,000 requests/hour.
    Raises HTTP 429 for flagged orgs.
    """
    try:
        from app.redis_client import redis_client

        flag_key = f"abuse_flag:{org_id}"
        if redis_client.get(flag_key):
            raise HTTPException(
                status_code=429,
                detail={
                    "error": "ABUSE_DETECTED",
                    "message": "Request rate exceeded safety threshold. Access temporarily suspended.",
                },
            )

        # Count total requests this hour (all sources)
        count_key = f"abuse_count:{org_id}"
        count = redis_client.incr(count_key)
        redis_client.expire(count_key, 3600)

        if count > 1000:
            # Flag for 1 hour
            redis_client.setex(flag_key, 3600, "1")
            logger.warning(f"Abuse flag set for org {org_id} (count={count})")
            raise HTTPException(
                status_code=429,
                detail={
                    "error": "ABUSE_DETECTED",
                    "message": "Request rate exceeded safety threshold. Access temporarily suspended.",
                },
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.warning(f"Abuse detection failed (non-critical): {e}")
