from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session
import bcrypt
import jwt
from datetime import datetime, timedelta
import secrets

from app.database import SessionLocal
from app.ingestion.gmail_connector import create_oauth_flow
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

    db = SessionLocal()

    db.execute(
        text(
            """
        INSERT INTO oauth_tokens (
            org_id,
            access_token,
            refresh_token,
            token_expiry,
            last_synced_at
        )
        VALUES (
            :org_id,
            :access_token,
            :refresh_token,
            :expiry,
            :now
        )
        ON CONFLICT (org_id)
        DO UPDATE SET
            access_token = EXCLUDED.access_token,
            refresh_token = EXCLUDED.refresh_token,
            token_expiry = EXCLUDED.token_expiry,
            last_synced_at = EXCLUDED.last_synced_at
        """
        ),
        {
            "org_id": org_id,
            "access_token": access_token,
            "refresh_token": refresh_token,
            "expiry": expiry,
            "now": datetime.utcnow(),
        },
    )

    db.commit()
    db.close()

    # Trigger automatic sync in background
    background_tasks.add_task(run_gmail_sync, org_id, 100)  # 50 inbox + 50 sent

    import os
    frontend_url = os.getenv("FRONTEND_URL", "http://localhost:3000")
    
    # Redirect back to dashboard after successful connection
    return RedirectResponse(url=f"{frontend_url}/dashboard/connect")


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
