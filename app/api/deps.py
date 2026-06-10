import hashlib
import json
import os
import time
import logging
import jwt
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.policy.scope_loader import AuthCtx, resolve as resolve_scope

JWT_SECRET = os.getenv("JWT_SECRET", "genios-secret-key-replace-in-production")

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


# ── API-key Redis cache (60s) — kills ~150ms DB lookup per request ────────────
_API_KEY_CACHE_TTL = 60


def _api_key_cache_key(hashed: str) -> str:
    return f"api_key:{hashed}"


def _api_key_cache_invalidate(hashed: str) -> None:
    """Drop cached resolution. Call from API-key rotation / suspension paths."""
    try:
        from app.redis_client import redis_client
        redis_client.delete(_api_key_cache_key(hashed))
    except Exception:
        pass


def _verify_jwt_and_stash_ctx(token: str, request: Request) -> str | None:
    """Decode dashboard-session JWT (issued by /auth/login) and return org_id.

    Stateless — no DB or Redis hit. JWT shape: {org_id, email, exp}. Returns
    None on any decode failure (caller treats as auth miss). On success,
    stashes a legacy-scope AuthCtx onto `request.state.auth` so scope-aware
    endpoints (`Depends(get_auth_ctx)`) continue to work for browser users
    with the owner's full scope.
    """
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
    except jwt.PyJWTError:
        return None
    org_id = payload.get("org_id") or payload.get("org") or payload.get("sub")
    if not org_id:
        return None
    org_id = str(org_id)
    # Reject orphan tokens — JWT signed for an org that no longer exists
    # (test wipes, manual deletion, GDPR erasure). Without this, the token
    # decodes cleanly forever and the user lands on a ghost session that
    # only DevTools can recover. Frontend turns the 401 detail.code into
    # an auto-logout + redirect.
    db = SessionLocal()
    try:
        exists = db.execute(
            text("SELECT 1 FROM orgs WHERE id = :oid LIMIT 1"),
            {"oid": org_id},
        ).fetchone()
    finally:
        db.close()
    if exists is None:
        raise HTTPException(
            status_code=401,
            detail={
                "code": "TOKEN_REVOKED",
                "message": "Your session has expired. Please log in again.",
            },
        )
    request.state.auth = AuthCtx(org_id=org_id, scope_source="jwt")
    return org_id


def verify_api_key(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> str:
    """
    Resolve org_id from either a dashboard JWT or a `gn_live_...` API key.

    Two credential shapes accepted on the same `Authorization: Bearer ...` header:

      • JWT (browser/dashboard) — 3 dot-separated segments, no `gn_` prefix.
        Stateless verify, no Redis/DB hit. Used by the dashboard UI.

      • API key `gn_live_...` (customer agents / integrations) — hashed lookup
        against `orgs.api_key_hash` or `api_keys.key_hash`. Cached in Redis 60s.
        Carries per-agent scope/policy via `AuthCtx`. This is the product
        credential — customer mints multiple keys, each with its own scope.

    Both paths stash an `AuthCtx` on `request.state.auth` for `get_auth_ctx`.
    Signature preserved (returns org_id string) — all 57 existing callers
    work unchanged.
    """
    check_kill_switch()

    token = credentials.credentials

    # ── Path 1: JWT (dashboard session) — stateless, no Redis ─────────────
    if token.count(".") == 2 and not token.startswith("gn_"):
        org_id = _verify_jwt_and_stash_ctx(token, request)
        if org_id is not None:
            return org_id
        raise HTTPException(status_code=401, detail="Invalid or expired session")

    # ── Path 2: API key (programmatic / customer agents) ──────────────────
    if not token.startswith("gn_live_"):
        raise HTTPException(status_code=401, detail="Invalid API Key format")

    hashed = _hash_key(token)

    # ── Fast path: combined Redis cache (org_id + plan + AuthCtx JSON) ────
    from app.redis_client import redis_client
    cache_key = _api_key_cache_key(hashed)
    try:
        cached = redis_client.get(cache_key)
        if cached:
            payload = cached if isinstance(cached, str) else cached.decode()
            try:
                blob = json.loads(payload)
                org_id = blob["org_id"]
                plan_status = blob.get("plan_status", "active")
                if plan_status == "suspended":
                    raise HTTPException(
                        status_code=403,
                        detail={"error": "ACCOUNT_SUSPENDED", "message": "Account suspended. Contact support."},
                    )
                if plan_status == "invalid":
                    raise HTTPException(status_code=401, detail="Invalid API Key")
                if blob.get("auth"):
                    request.state.auth = AuthCtx.from_dict(blob["auth"])
                return org_id
            except (json.JSONDecodeError, KeyError):
                # Legacy "org|status" cache shape — fall through and re-cache
                pass
    except HTTPException:
        raise
    except Exception:
        pass

    # ── Slow path: DB resolve org + scope in one open session ─────────────
    db = SessionLocal()
    try:
        result = db.execute(
            text("""
                SELECT id, subscription_tier, plan_status
                FROM orgs
                WHERE api_key = :raw_key
                   OR api_key_hash = :hashed_key
            """),
            {"raw_key": token, "hashed_key": hashed},
        ).fetchone()

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
            if result:
                try:
                    db.execute(
                        text("UPDATE api_keys SET last_used_at = NOW() WHERE key_hash = :h"),
                        {"h": hashed},
                    )
                    db.commit()
                except Exception:
                    pass

        # AuthCtx (agent + scope) — same session, single round-trip pair
        auth_ctx = None
        if result:
            try:
                auth_ctx = resolve_scope(db, hashed)
                if auth_ctx is None:
                    # Legacy key (orgs.api_key plaintext, no api_keys row, no
                    # default_agent backfill yet) — synthesise legacy AuthCtx.
                    auth_ctx = AuthCtx(
                        org_id=str(result[0]),
                        agent_uuid=None,
                        agent_id=None,
                        scope_id=None,
                        policy=None,
                        scope_source="legacy",
                        plan_status=result.plan_status or "active",
                    )
            except Exception as e:
                logger.warning(f"AuthCtx resolve failed (degrading to legacy): {e}")
                auth_ctx = AuthCtx(
                    org_id=str(result[0]),
                    scope_source="legacy",
                    plan_status=result.plan_status or "active",
                )
    finally:
        db.close()

    if not result:
        try:
            redis_client.setex(cache_key, 30, json.dumps({"org_id": "", "plan_status": "invalid"}))
        except Exception:
            pass
        raise HTTPException(status_code=401, detail="Invalid API Key")

    plan_status = result.plan_status or "active"
    org_id = str(result[0])

    try:
        blob = {
            "org_id": org_id,
            "plan_status": plan_status,
            "auth": auth_ctx.to_dict() if auth_ctx else None,
        }
        redis_client.setex(cache_key, _API_KEY_CACHE_TTL, json.dumps(blob, default=str))
    except Exception:
        pass

    if plan_status == "suspended":
        raise HTTPException(
            status_code=403,
            detail={"error": "ACCOUNT_SUSPENDED", "message": "Account suspended. Contact support."},
        )

    if auth_ctx:
        request.state.auth = auth_ctx
    return org_id


def get_auth_ctx(request: Request, org_id: str = Depends(verify_api_key)) -> AuthCtx:
    """
    Scope-aware dependency. Endpoints that enforce policy use this:

        @router.get("/v1/context")
        def f(auth: AuthCtx = Depends(get_auth_ctx)): ...

    Falls back to a legacy full-scope AuthCtx if `request.state.auth` is
    unset (e.g. a code path that bypassed the new caching). Never returns
    None — always carries at least an org_id.
    """
    auth = getattr(request.state, "auth", None)
    if isinstance(auth, AuthCtx):
        return auth
    return AuthCtx(org_id=org_id, scope_source="legacy")


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


def preflight_ratelimit(
    org_id: str,
    agent_id: str,
    plan_tier: str,
    entity: str = None,
    check_loop: bool = True,
):
    """
    One-shot preflight that runs abuse-detection + per-agent RPM + per-org RPH
    + optional agent-loop check in a **single Redis pipeline**.

    Replaces three sequential calls (3 round-trips) with one (1 round-trip).
    On Upstash this saves ~60–100ms on the hot path.

    Raises HTTPException 429 with the appropriate error code on any violation.
    Fails open (allows through) if Redis itself is unreachable.
    """
    try:
        from app.redis_client import redis_client
        from app.plan_enforcer import PLAN_CONFIG
        from fastapi import HTTPException

        config = PLAN_CONFIG.get(plan_tier, PLAN_CONFIG["trial"])
        rpm_limit = config["rpm_per_agent"]
        rph_limit = config["rph_org"]

        now = int(time.time())
        minute_window = now - 60
        hour_window = now - 3600

        abuse_flag_key = f"abuse_flag:{org_id}"
        abuse_count_key = f"abuse_count:{org_id}"
        agent_key = f"rpm:{org_id}:{agent_id or 'default'}"
        org_key = f"rph:{org_id}"

        ent_key = (entity or "").strip().lower()
        use_loop = check_loop and bool(ent_key)
        loop_key = f"entity_loop:{org_id}:{agent_id or 'default'}:{ent_key[:128]}" if use_loop else None

        pipe = redis_client.pipeline()

        # 1) Abuse flag check + counter bump (hourly)
        pipe.get(abuse_flag_key)            # [0]
        pipe.incr(abuse_count_key)          # [1]
        pipe.expire(abuse_count_key, 3600)  # [2]

        # 2) RPM sliding window (per agent)
        pipe.zremrangebyscore(agent_key, 0, minute_window)  # [3]
        pipe.zcard(agent_key)                                # [4]
        pipe.zadd(agent_key, {str(now): now})                # [5]
        pipe.expire(agent_key, 120)                          # [6]

        # 3) RPH sliding window (per org)
        pipe.zremrangebyscore(org_key, 0, hour_window)       # [7]
        pipe.zcard(org_key)                                  # [8]
        pipe.zadd(org_key, {str(now): now})                  # [9]
        pipe.expire(org_key, 7200)                           # [10]

        # 4) Entity-loop sliding window (optional, per agent+entity)
        if use_loop:
            pipe.zremrangebyscore(loop_key, 0, minute_window)  # [11]
            pipe.zcard(loop_key)                                # [12]
            pipe.zadd(loop_key, {str(now): now})                # [13]
            pipe.expire(loop_key, 120)                          # [14]

        results = pipe.execute()

        # Parse
        abuse_flagged = results[0]
        abuse_count = results[1] or 0
        rpm_count = results[4] or 0
        rph_count = results[8] or 0
        loop_count = results[12] if use_loop else 0

        # Raise in precedence order: abuse → RPM → RPH → loop
        if abuse_flagged:
            raise HTTPException(
                status_code=429,
                detail={
                    "error": "ABUSE_DETECTED",
                    "message": "Request rate exceeded safety threshold. Access temporarily suspended.",
                },
            )

        if abuse_count > 1000:
            # Set 1h abuse flag and reject
            try:
                redis_client.setex(abuse_flag_key, 3600, "1")
            except Exception:
                pass
            logger.warning(f"Abuse flag set for org {org_id} (count={abuse_count})")
            raise HTTPException(
                status_code=429,
                detail={
                    "error": "ABUSE_DETECTED",
                    "message": "Request rate exceeded safety threshold. Access temporarily suspended.",
                },
            )

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

        if use_loop:
            from app.llm_guard import ENTITY_REPEAT_CAP
            if loop_count >= ENTITY_REPEAT_CAP:
                raise HTTPException(
                    status_code=429,
                    detail={
                        "error": "ENTITY_REPEAT_LIMIT",
                        "message": (
                            f"Same entity requested {loop_count} times in 60s by this agent. "
                            f"Cap is {ENTITY_REPEAT_CAP}. This looks like a loop — try a different query."
                        ),
                        "entity": ent_key,
                        "calls_in_window": loop_count,
                        "hard_cap": ENTITY_REPEAT_CAP,
                    },
                )

    except HTTPException:
        raise
    except Exception as e:
        # Redis unreachable — fail open
        logger.warning(f"Preflight ratelimit failed (non-critical): {e}")


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
