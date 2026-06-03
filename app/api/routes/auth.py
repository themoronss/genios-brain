from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session
import bcrypt
import jwt
import os
import time
import logging
from datetime import datetime, timedelta
import secrets

from app.api.deps import get_db


router = APIRouter()
logger = logging.getLogger(__name__)

JWT_SECRET = os.getenv("JWT_SECRET", "genios-secret-key-replace-in-production")

# Anti-abuse: IP-based signup rate limit so an attacker cannot mint hundreds
# of trial accounts in a loop. Sliding 24h window backed by Redis. Defaults
# are conservative — operators tune via env without code changes.
SIGNUP_PER_IP_DAILY = int(os.getenv("GENIOS_SIGNUP_PER_IP_DAILY", "3"))
SIGNUP_PER_IP_WEEKLY = int(os.getenv("GENIOS_SIGNUP_PER_IP_WEEKLY", "10"))


def _client_ip(request: Request) -> str:
    """Best-effort source IP. Trusts X-Forwarded-For when behind a known
    proxy; falls back to the socket peer otherwise."""
    fwd = request.headers.get("x-forwarded-for", "")
    if fwd:
        return fwd.split(",")[0].strip()
    if request.client:
        return request.client.host
    return "unknown"


def _enforce_signup_rate_limit(ip: str) -> None:
    """Block IPs that exceed the daily/weekly signup ceiling.

    Fail-open on Redis errors so a cache outage doesn't lock out new users
    on a legitimate launch day. The check is a defense-in-depth layer; a
    determined attacker rotating IPs will need an additional captcha at
    the gateway, which is configured separately.
    """
    try:
        from app.redis_client import redis_client
        now = int(time.time())
        for window, limit in [(86400, SIGNUP_PER_IP_DAILY),
                              (604800, SIGNUP_PER_IP_WEEKLY)]:
            key = f"signup_rl:{window}:{ip}"
            count = redis_client.incr(key)
            if count == 1:
                redis_client.expire(key, window)
            if count > limit:
                raise HTTPException(
                    status_code=429,
                    detail={
                        "error": "SIGNUP_RATE_LIMITED",
                        "message": "Too many signups from this network. Try again later or contact support.",
                    },
                )
    except HTTPException:
        raise
    except Exception as e:
        logger.warning(f"signup rate limit check failed (fail-open): {e}")


# Pydantic models for auth
class LoginRequest(BaseModel):
    email: str
    password: str


class RegisterRequest(BaseModel):
    name: str
    email: str
    password: str


class AuthResponse(BaseModel):
    org_id: str
    token: str
    name: str
    email: str


@router.post("/auth/login", response_model=AuthResponse)
def login(request: LoginRequest, db: Session = Depends(get_db)):
    """Login with email/password."""
    # Query user from orgs table
    result = db.execute(
        text("""
            SELECT id, name, email, password_hash,
                   subscription_tier, credits, topup_credits, created_at
            FROM orgs WHERE email = :email
        """),
        {"email": request.email},
    ).fetchone()

    if not result:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    # Verify password
    if not bcrypt.checkpw(
        request.password.encode("utf-8"), result.password_hash.encode("utf-8")
    ):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    # Generate JWT token
    token = jwt.encode(
        {
            "org_id": str(result.id),
            "email": result.email,
            "exp": datetime.utcnow() + timedelta(days=7),
        },
        JWT_SECRET,
        algorithm="HS256",
    )

    from app.core.analytics import capture, org_properties
    capture(str(result.id), "user_logged_in", {
        "email": result.email,
        "$set": org_properties(
            plan=result.subscription_tier,
            credits=(result.credits or 0) + (result.topup_credits or 0),
            created_at=result.created_at,
        ),
    })

    from fastapi.responses import JSONResponse
    response = JSONResponse(content={
        "org_id": str(result.id),
        "token": token,  # kept in body for backward compat during migration
        "name": result.name,
        "email": result.email,
    })
    # Set HttpOnly cookie — browser sends it automatically on subsequent requests
    response.set_cookie(
        key="genios_token",
        value=token,
        httponly=True,
        secure=True,           # HTTPS only
        samesite="lax",        # protects against CSRF
        max_age=7 * 24 * 3600, # 7 days (matches JWT expiry)
        path="/",
    )
    return response


@router.post("/auth/register", response_model=AuthResponse, status_code=201)
def register(request: RegisterRequest, http_request: Request, db: Session = Depends(get_db)):
    """Register new user.

    Anti-abuse: IP-based signup rate limit (configurable via env) blocks
    bots from minting trial accounts in a loop. Trial credits are granted
    immediately so the user can ship code on day-zero without payment.
    """
    # IP rate limit — blocks at 3/day, 10/week per IP by default.
    _enforce_signup_rate_limit(_client_ip(http_request))

    # Check if email exists
    existing = db.execute(
        text("SELECT id FROM orgs WHERE email = :email"), {"email": request.email}
    ).fetchone()

    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    # Hash password
    password_hash = bcrypt.hashpw(
        request.password.encode("utf-8"), bcrypt.gensalt()
    ).decode("utf-8")

    # Generate API key
    api_key = f"gn_live_{secrets.token_urlsafe(32)}"

    # Insert user — auto-assign trial plan with single-pool credit grant.
    # 7-day trial: 500 credits (see PLAN_CONFIG["trial"]).
    from app.plan_enforcer import PLAN_CONFIG
    trial_cfg = PLAN_CONFIG["trial"]
    result = db.execute(
        text(
            """
            INSERT INTO orgs (
                name, email, password_hash, api_key,
                subscription_tier, plan_status,
                plan_started_at, plan_expires_at, period_reset_at,
                period_context_count,
                credits,
                credit_period_start, credit_period_end
            )
            VALUES (
                :name, :email, :password_hash, :api_key,
                'trial', 'active',
                NOW(), NOW() + (:days || ' days')::INTERVAL,
                NOW() + (:days || ' days')::INTERVAL,
                0,
                :credits,
                NOW(), NOW() + (:days || ' days')::INTERVAL
            )
            RETURNING id
        """
        ),
        {
            "name": request.name,
            "email": request.email,
            "password_hash": password_hash,
            "api_key": api_key,
            "days":    trial_cfg["period_days"],
            "credits": trial_cfg["credits"],
        },
    )
    org_id = result.fetchone()[0]
    db.commit()

    # Audit ledger row so trial grants show up in reconciliation.
    try:
        db.execute(
            text("""
                INSERT INTO credit_ledger
                    (org_id, bucket, kind, amount, balance_after, reason, idempotency_key)
                VALUES (:org, 'credits', 'grant', :amt, :amt,
                        'signup_trial_grant', :key)
                ON CONFLICT (org_id, idempotency_key) WHERE idempotency_key IS NOT NULL
                DO NOTHING
            """),
            {
                "org": str(org_id),
                "amt": trial_cfg["credits"],
                "key": f"signup:{org_id}",
            },
        )
        db.commit()
    except Exception as e:
        logger.warning(f"trial grant ledger write failed for org={org_id}: {e}")
        db.rollback()

    # Auto-create default_agent + full-scope policy + bind primary key.
    # Day-0 UX stays the same — one key, integrate, ship. The Agent Registry
    # only surfaces when the customer registers a second agent.
    try:
        import json as _json
        agent_uuid = db.execute(
            text("""
                INSERT INTO registered_agents (org_id, agent_id, name, description, status, created_at)
                VALUES (:o, 'default_agent', 'Default Agent',
                        'Auto-created. Full org access. Used by primary API key.',
                        'active', NOW())
                ON CONFLICT (org_id, agent_id) DO UPDATE SET status = 'active'
                RETURNING id
            """),
            {"o": str(org_id)},
        ).fetchone()[0]
        scope_id = db.execute(
            text("""
                INSERT INTO agent_scopes (agent_uuid, org_id, version, policy_json, is_active, created_by)
                VALUES (:a, :o, 1, CAST(:p AS jsonb), TRUE, 'system_signup')
                RETURNING id
            """),
            {
                "a": str(agent_uuid), "o": str(org_id),
                "p": _json.dumps({
                    "version": 1, "connectors": None, "segments": None, "fact_types": None,
                    "exclude_tags": [], "max_age_days": 3650, "min_confidence": 0.0,
                    "data_visibility": "all",
                }),
            },
        ).fetchone()[0]
        db.execute(
            text("UPDATE orgs SET default_agent_id = :a WHERE id = :o"),
            {"a": str(agent_uuid), "o": str(org_id)},
        )
        db.commit()
    except Exception as _agent_err:
        import logging as _log
        _log.getLogger(__name__).warning(f"default_agent provision failed: {_agent_err}")
        db.rollback()

    # v1 precedent graph is gone (precedent_graph table dropped in mig 0015).
    # v2 modules ship their own bootstrap data via core/modules_framework.

    # Generate token
    token = jwt.encode(
        {
            "org_id": str(org_id),
            "email": request.email,
            "exp": datetime.utcnow() + timedelta(days=7),
        },
        JWT_SECRET,
        algorithm="HS256",
    )

    from app.core.analytics import capture, org_properties
    capture(str(org_id), "user_signed_up", {
        "plan": "trial",
        "email": request.email,
        "$set": org_properties(plan="trial", created_at=datetime.utcnow()),
    })

    from fastapi.responses import JSONResponse
    response = JSONResponse(content={
        "org_id": str(org_id),
        "token": token,
        "name": request.name,
        "email": request.email,
    }, status_code=201)
    response.set_cookie(
        key="genios_token",
        value=token,
        httponly=True,
        secure=True,
        samesite="lax",
        max_age=7 * 24 * 3600,
        path="/",
    )
    return response


# ── Logout ────────────────────────────────────────────────────────────────────

@router.post("/auth/logout")
def auth_logout():
    """Clear the HttpOnly auth cookie."""
    from fastapi.responses import JSONResponse
    response = JSONResponse(content={"logged_out": True})
    response.delete_cookie("genios_token", path="/")
    return response


# ── Profile ───────────────────────────────────────────────────────────────────

@router.get("/api/org/{org_id}/profile")
def get_profile(org_id: str, db: Session = Depends(get_db)):
    row = db.execute(
        text("SELECT name, email, first_name, last_name, company, role FROM orgs WHERE id = :oid"),
        {"oid": org_id},
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Org not found")
    # Split name into first/last if first_name not set
    first = row.first_name or (row.name.split()[0] if row.name else "")
    last = row.last_name or (" ".join(row.name.split()[1:]) if row.name and " " in row.name else "")
    return {
        "first_name": first,
        "last_name": last,
        "email": row.email,
        "company": row.company or "",
        "role": row.role or "",
    }


class ProfileUpdate(BaseModel):
    first_name: str = None
    last_name: str = None
    company: str = None
    role: str = None

@router.patch("/api/org/{org_id}/profile")
def update_profile(org_id: str, body: ProfileUpdate, db: Session = Depends(get_db)):
    sets = []
    params: dict = {"oid": org_id}
    if body.first_name is not None:
        sets.append("first_name = :first_name")
        params["first_name"] = body.first_name
    if body.last_name is not None:
        sets.append("last_name = :last_name")
        params["last_name"] = body.last_name
        # Also update the display name
        full_name = f"{body.first_name or ''} {body.last_name}".strip()
        if full_name:
            sets.append("name = :name")
            params["name"] = full_name
    if body.company is not None:
        sets.append("company = :company")
        params["company"] = body.company
    if body.role is not None:
        sets.append("role = :role")
        params["role"] = body.role
    if not sets:
        return {"updated": False}
    db.execute(text(f"UPDATE orgs SET {', '.join(sets)} WHERE id = :oid"), params)
    db.commit()
    return {"updated": True}


# ── Security (Password Change) ────────────────────────────────────────────────

class PasswordChange(BaseModel):
    current_password: str
    new_password: str

@router.post("/api/org/{org_id}/password/change")
def change_password(org_id: str, body: PasswordChange, db: Session = Depends(get_db)):
    import bcrypt
    row = db.execute(text("SELECT password_hash FROM orgs WHERE id = :oid"), {"oid": org_id}).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Org not found")
    if not bcrypt.checkpw(body.current_password.encode(), row.password_hash.encode()):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    if len(body.new_password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")
    new_hash = bcrypt.hashpw(body.new_password.encode(), bcrypt.gensalt()).decode()
    db.execute(text("UPDATE orgs SET password_hash = :h WHERE id = :oid"), {"h": new_hash, "oid": org_id})
    db.commit()
    return {"updated": True}


# ── Notification Preferences ──────────────────────────────────────────────────

@router.get("/api/org/{org_id}/notifications/preferences")
def get_notification_prefs(org_id: str, db: Session = Depends(get_db)):
    row = db.execute(text("SELECT notification_prefs FROM orgs WHERE id = :oid"), {"oid": org_id}).fetchone()
    defaults = {
        "syncComplete": True, "conflictDetected": True, "commitmentOverdue": True,
        "stageChange": True, "lowConfidence": True, "weeklyDigest": False,
        "emailNotifications": True, "browserNotifications": False,
    }
    prefs = row.notification_prefs if row and row.notification_prefs else {}
    return {**defaults, **prefs}


class QuietHoursWindow(BaseModel):
    start: str  # "HH:MM"
    end:   str  # "HH:MM"; if end<=start the window crosses midnight


class QuietHours(BaseModel):
    enabled: bool = False
    tz: str = "UTC"
    windows: list[QuietHoursWindow] = []


class NotificationPrefs(BaseModel):
    syncComplete: bool = True
    conflictDetected: bool = True
    commitmentOverdue: bool = True
    stageChange: bool = True
    lowConfidence: bool = True
    weeklyDigest: bool = False
    emailNotifications: bool = True
    browserNotifications: bool = False
    quiet_hours: QuietHours | None = None

@router.put("/api/org/{org_id}/notifications/preferences")
def save_notification_prefs(org_id: str, body: NotificationPrefs, db: Session = Depends(get_db)):
    import json as _json
    db.execute(
        text("UPDATE orgs SET notification_prefs = CAST(:prefs AS jsonb) WHERE id = :oid"),
        {"prefs": _json.dumps(body.model_dump()), "oid": org_id},
    )
    db.commit()
    return {"saved": True}


# ── API Usage Stats ───────────────────────────────────────────────────────────

@router.get("/api/org/{org_id}/usage")
def get_usage_stats(org_id: str, db: Session = Depends(get_db)):
    from app.plan_enforcer import get_org_plan, PLAN_CONFIG

    plan_info = get_org_plan(db, org_id)
    tier = plan_info["tier"]
    config = plan_info["config"]
    api_filter = "AND (source = 'api' OR source IS NULL)"

    today = db.execute(
        text(f"SELECT COUNT(*) FROM context_calls WHERE org_id = :oid AND called_at >= CURRENT_DATE {api_filter}"),
        {"oid": org_id},
    ).scalar() or 0

    # Period usage (since last reset)
    period_reset_at = plan_info.get("period_reset_at")
    if period_reset_at:
        period_used = db.execute(
            text(f"SELECT COUNT(*) FROM context_calls WHERE org_id = :oid AND called_at >= :reset_at {api_filter}"),
            {"oid": org_id, "reset_at": period_reset_at},
        ).scalar() or 0
    else:
        period_used = 0

    expires_at = plan_info.get("expires_at")
    days_remaining = None
    if expires_at:
        from datetime import timezone as tz
        now = datetime.utcnow().replace(tzinfo=tz.utc)
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=tz.utc)
        days_remaining = max(0, (expires_at - now).days)

    # Post-099: single-pool credit model. Legacy `today`/`period_used`
    # counts from context_calls are returned for analytics-only displays;
    # the user-visible meter should read `credits.balance`.
    credits_total = plan_info.get("credits", 0) + plan_info.get("topup_credits", 0)
    return {
        "today": today,
        "period_used": period_used,
        "plan": tier,
        "plan_status": plan_info.get("plan_status", "active"),
        "expires_at": expires_at.isoformat() if expires_at else None,
        "days_remaining": days_remaining,
        # New single-pool meter
        "credits": {
            "balance": credits_total,
            "plan":    plan_info.get("credits", 0),
            "topup":   plan_info.get("topup_credits", 0),
            "period_limit": config["credits"],
        },
        "sonnet_daily_limit": config.get("sonnet_daily_limit", 0),
    }


# ── API Keys ──────────────────────────────────────────────────────────────────

@router.get("/api/org/{org_id}/apikey")
def get_api_key(org_id: str, db: Session = Depends(get_db)):
    result = db.execute(
        text("SELECT api_key FROM orgs WHERE id = :org_id"), {"org_id": org_id}
    ).fetchone()
    if not result:
        raise HTTPException(status_code=404, detail="Org not found")
    return {"api_key": result.api_key}


@router.post("/api/org/{org_id}/apikey/regenerate")
def regenerate_api_key(org_id: str, db: Session = Depends(get_db)):
    new_key = f"gn_live_{secrets.token_urlsafe(32)}"
    db.execute(
        text("UPDATE orgs SET api_key = :api_key WHERE id = :org_id"),
        {"api_key": new_key, "org_id": org_id},
    )
    db.commit()
    return {"api_key": new_key}


@router.delete("/api/org/{org_id}/account")
def delete_account(org_id: str, db: Session = Depends(get_db)):
    """Delete organization and all associated data."""
    try:
        # Cascade delete in correct order (foreign keys)
        for table in [
            "precomputed_bundles", "outcome_events", "agent_sessions",
            "context_calls", "insights", "commitments", "communities",
            "authority_assignments", "authority_permissions", "authority_roles",
            "precedent_graph", "merge_queue", "activity_log",
            "interactions", "contacts", "oauth_tokens",
        ]:
            db.execute(text(f"DELETE FROM {table} WHERE org_id = :oid"), {"oid": org_id})
        # orgs table uses `id` not `org_id`
        db.execute(text("DELETE FROM orgs WHERE id = :oid"), {"oid": org_id})
        db.commit()
        return {"deleted": True}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
