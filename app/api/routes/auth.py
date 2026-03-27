from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session
import bcrypt
import jwt
from datetime import datetime, timedelta
import secrets

from app.database import SessionLocal
from app.ingestion.gmail_connector import create_oauth_flow, build_gmail_service, get_user_email
from app.config import GOOGLE_REDIRECT_URI
from app.tasks.gmail_sync import run_gmail_sync
from app.redis_client import redis_client


router = APIRouter()

# JWT Secret (use env var in production)
JWT_SECRET = "genios-secret-key-replace-in-production"


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


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.get("/auth/gmail/connect")
def gmail_connect(org_id: str):

    flow = create_oauth_flow()

    authorization_url, state = flow.authorization_url(
        access_type="offline", include_granted_scopes="true", prompt="consent"
    )

    # Store org_id AND code_verifier in Redis (for PKCE flow)
    # Code verifier is needed to complete the OAuth flow
    # Expires in 180 seconds (3 minutes) - enough time for OAuth flow
    import json

    flow_data = {
        "org_id": org_id,
        "code_verifier": flow.code_verifier if hasattr(flow, "code_verifier") else None,
    }
    redis_client.setex(f"oauth_state:{state}", 180, json.dumps(flow_data))

    return RedirectResponse(authorization_url)


@router.get("/auth/gmail/callback")
async def gmail_callback(state: str, code: str, background_tasks: BackgroundTasks):
    import json

    # Retrieve flow data from Redis using state
    flow_data_json = redis_client.get(f"oauth_state:{state}")

    if not flow_data_json:
        return {
            "error": "Invalid OAuth state or session expired. Please try connecting again."
        }

    # Decode and parse flow data
    flow_data_json = (
        flow_data_json.decode("utf-8")
        if isinstance(flow_data_json, bytes)
        else flow_data_json
    )
    flow_data = json.loads(flow_data_json)
    org_id = flow_data["org_id"]
    code_verifier = flow_data.get("code_verifier")

    # Delete the state from Redis (one-time use)
    redis_client.delete(f"oauth_state:{state}")

    # Recreate flow and restore code_verifier for PKCE
    flow = create_oauth_flow()
    flow.redirect_uri = GOOGLE_REDIRECT_URI

    # Restore code_verifier if it exists (for PKCE flow)
    if code_verifier:
        flow.code_verifier = code_verifier

    # Fetch token and handle OAuth warnings
    import warnings

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")  # Suppress OAuth scope warnings
        flow.fetch_token(code=code)

    credentials = flow.credentials

    access_token = credentials.token
    refresh_token = credentials.refresh_token
    expiry = credentials.expiry

    # -- Update 4: Identify which Gmail account this token belongs to --
    # Build a temporary service with the fresh credentials to call the profile API.
    gmail_service = build_gmail_service(access_token, refresh_token)
    connected_email = get_user_email(gmail_service)

    db = SessionLocal()

    db.execute(
        text(
            """
        INSERT INTO oauth_tokens (
            org_id,
            account_email,
            access_token,
            refresh_token,
            token_expiry,
            last_synced_at,
            sync_status
        )
        VALUES (
            :org_id,
            :account_email,
            :access_token,
            :refresh_token,
            :expiry,
            :now,
            'running'
        )
        ON CONFLICT (org_id, account_email)
        DO UPDATE SET
            access_token = EXCLUDED.access_token,
            refresh_token = EXCLUDED.refresh_token,
            token_expiry = EXCLUDED.token_expiry,
            last_synced_at = EXCLUDED.last_synced_at,
            sync_status = 'running'
        """
        ),
        {
            "org_id": org_id,
            "account_email": connected_email,
            "access_token": access_token,
            "refresh_token": refresh_token,
            "expiry": expiry,
            "now": datetime.utcnow(),
        },
    )

    db.commit()
    db.close()

    # Trigger automatic sync in background for this specific account
    from app.config import SYNC_MAX_EMAILS
    background_tasks.add_task(run_gmail_sync, org_id, SYNC_MAX_EMAILS, connected_email)

    import os
    frontend_url = os.getenv("FRONTEND_URL", "http://localhost:3000")
    
    # Redirect straight to dashboard — the dashboard sync-in-progress screen
    # handles the UX from here (shows email tally, auto-refreshes graph).
    return RedirectResponse(url=f"{frontend_url}/dashboard")


@router.post("/auth/login", response_model=AuthResponse)
def login(request: LoginRequest, db: Session = Depends(get_db)):
    """Login with email/password."""
    # Query user from orgs table
    result = db.execute(
        text("SELECT id, name, email, password_hash FROM orgs WHERE email = :email"),
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

    return {
        "org_id": str(result.id),
        "token": token,
        "name": result.name,
        "email": result.email,
    }


@router.post("/auth/register", response_model=AuthResponse, status_code=201)
def register(request: RegisterRequest, db: Session = Depends(get_db)):
    """Register new user."""
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

    # Insert user
    result = db.execute(
        text(
            """
            INSERT INTO orgs (name, email, password_hash, api_key)
            VALUES (:name, :email, :password_hash, :api_key)
            RETURNING id
        """
        ),
        {
            "name": request.name,
            "email": request.email,
            "password_hash": password_hash,
            "api_key": api_key,
        },
    )
    org_id = result.fetchone()[0]
    db.commit()

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

    return {
        "org_id": str(org_id),
        "token": token,
        "name": request.name,
        "email": request.email,
    }


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


class NotificationPrefs(BaseModel):
    syncComplete: bool = True
    conflictDetected: bool = True
    commitmentOverdue: bool = True
    stageChange: bool = True
    lowConfidence: bool = True
    weeklyDigest: bool = False
    emailNotifications: bool = True
    browserNotifications: bool = False

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
    today = db.execute(
        text("SELECT COUNT(*) FROM context_calls WHERE org_id = :oid AND called_at >= CURRENT_DATE"),
        {"oid": org_id},
    ).scalar() or 0
    week = db.execute(
        text("SELECT COUNT(*) FROM context_calls WHERE org_id = :oid AND called_at >= CURRENT_DATE - INTERVAL '7 days'"),
        {"oid": org_id},
    ).scalar() or 0
    month = db.execute(
        text("SELECT COUNT(*) FROM context_calls WHERE org_id = :oid AND called_at >= CURRENT_DATE - INTERVAL '30 days'"),
        {"oid": org_id},
    ).scalar() or 0
    return {
        "today": today, "today_limit": 3000,
        "week": week, "week_limit": 21000,
        "month": month, "month_limit": 90000,
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
