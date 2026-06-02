"""Human-user auth routes — signup / login / logout / me.

POST /auth/signup    create user + org + admin role + first API key + JWT
POST /auth/login     verify email/password, issue JWT, set HttpOnly cookie
POST /auth/logout    clear cookie (JWT is stateless; client just discards it)
GET  /auth/me        return current user + org + role

Auth model:
    Browser flow: HttpOnly cookie 'genios_session' + Bearer fallback
    Integration flow: 'Authorization: Bearer <api_key>' (resolved separately
                      via deps.require_org's API-key branch)

Passwords: bcrypt (12 rounds), sha256 pre-hash so passphrases work
Sessions:  stateless JWT, 7-day TTL by default
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from core.api.deps import db_session
from core.auth_store import OrgMemberRow, OrgRow, UserRow
from core.delivery.store import AgentRegistryRow
from core.foundations import audit
from core.foundations.encryption import encrypt
from core.foundations.jwt_session import JWTError, decode_session, encode_session
from core.foundations.passwords import hash_password, verify_password
from core.foundations.telemetry import get_logger
from core.memory.store import SecretRef

router = APIRouter(prefix="/auth", tags=["auth"])
log = get_logger(__name__)

SESSION_COOKIE = "genios_session"


# ─────────────────────────────────────────────────────────────────────────────
# Schemas
# ─────────────────────────────────────────────────────────────────────────────


class SignupRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=200)
    name: str = Field(..., min_length=1, max_length=255)
    org_name: str = Field(..., min_length=1, max_length=255)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=1, max_length=200)


class UserOut(BaseModel):
    user_id: str
    email: str
    name: str


class OrgOut(BaseModel):
    org_id: str
    name: str
    plan: str
    role: str


class AuthSuccess(BaseModel):
    token: str
    user: UserOut
    org: OrgOut
    api_key: str | None = None  # only on signup — admin's first key


class MeResponse(BaseModel):
    user: UserOut
    org: OrgOut


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────


def _generate_api_key() -> str:
    """Mint an API key. Format: gn_live_<32-byte url-safe>."""
    import secrets

    return f"gn_live_{secrets.token_urlsafe(32)}"


def _set_session_cookie(response: Response, token: str) -> None:
    """HttpOnly cookie — browser sends it on every same-origin request."""
    # secure=False for local dev (HTTP); production should set secure=True via reverse proxy/Cloudflare
    response.set_cookie(
        key=SESSION_COOKIE,
        value=token,
        httponly=True,
        samesite="lax",
        secure=False,
        max_age=60 * 60 * 24 * 7,  # 1 week, matches JWT default TTL
        path="/",
    )


def _provision_first_api_key(
    session: Session, *, org_id: str, user_id: str, user_name: str
) -> tuple[AgentRegistryRow, str]:
    """Mint an admin API key for the new org so integrations can call /v1/*.

    Returns (registry_row, plaintext_key). Plaintext is shown ONCE on signup.
    """
    api_key = _generate_api_key()

    # First we need a Connection row to attach the secret to (g-i-1 schema).
    # For human-admin API keys we use a synthetic connection (source_type='admin_console').
    from core.memory.store import Connection

    connection = Connection(
        org_id=org_id,
        source_type="admin_console",
        source_id=f"admin:{user_id}",
        status="active",
        created_by=user_id,
    )
    session.add(connection)
    session.flush()

    secret = SecretRef(
        connection_id=connection.id,
        org_id=org_id,
        secret_type="api_key",  # noqa: S106 — enum label, not a password value
        encrypted_value=encrypt(api_key),
    )
    session.add(secret)
    session.flush()

    registry = AgentRegistryRow(
        org_id=org_id,
        agent_id=f"admin-{user_id}",
        name=f"{user_name} (admin)",
        granted_scopes_jsonb=["*"],
        active_modules_jsonb=[],
        api_key_ref=secret.id,
    )
    session.add(registry)
    session.flush()
    return registry, api_key


# ─────────────────────────────────────────────────────────────────────────────
# Routes
# ─────────────────────────────────────────────────────────────────────────────


@router.post("/signup", response_model=AuthSuccess, status_code=status.HTTP_201_CREATED)
def signup(
    body: SignupRequest,
    response: Response,
    session: Session = Depends(db_session),
) -> AuthSuccess:
    """Create user → org → admin role → first API key → JWT session.

    Idempotent on email: returns 409 if email already used.
    """
    existing = session.execute(
        select(UserRow).where(UserRow.email == body.email)
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="email already registered"
        )

    user = UserRow(
        email=str(body.email),
        name=body.name,
        password_hash=hash_password(body.password),
    )
    session.add(user)
    session.flush()

    org = OrgRow(name=body.org_name, created_by_user_id=user.id)
    session.add(org)
    session.flush()

    membership = OrgMemberRow(org_id=org.id, user_id=user.id, role="admin")
    session.add(membership)
    session.flush()

    _registry, plaintext_key = _provision_first_api_key(
        session, org_id=org.id, user_id=user.id, user_name=user.name
    )

    user.last_login_at = datetime.now(UTC)
    session.flush()

    token = encode_session(
        user_id=user.id, org_id=org.id, email=user.email, name=user.name
    )
    _set_session_cookie(response, token)

    audit.record_db(
        session,
        org_id=org.id,
        actor_type="user",
        actor_id=user.id,
        action="permission_changed",
        target_type="org",
        target_id=org.id,
        metadata={"event": "signup", "role": "admin"},
    )
    session.commit()

    log.info("auth_signup", user_id=user.id, org_id=org.id, email=user.email)
    return AuthSuccess(
        token=token,
        user=UserOut(user_id=user.id, email=user.email, name=user.name),
        org=OrgOut(org_id=org.id, name=org.name, plan=org.plan, role="admin"),
        api_key=plaintext_key,
    )


@router.post("/login", response_model=AuthSuccess)
def login(
    body: LoginRequest,
    response: Response,
    session: Session = Depends(db_session),
) -> AuthSuccess:
    """Verify password + return JWT. 401 on any failure (no info leak)."""
    user = session.execute(
        select(UserRow).where(UserRow.email == str(body.email))
    ).scalar_one_or_none()
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid credentials"
        )

    # Pick the user's primary org (oldest membership). Multi-org switching can
    # land later via an /auth/switch_org endpoint; v1 = single primary.
    membership = session.execute(
        select(OrgMemberRow)
        .where(OrgMemberRow.user_id == user.id)
        .order_by(OrgMemberRow.joined_at.asc())
        .limit(1)
    ).scalar_one_or_none()
    if membership is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="user has no org membership"
        )
    org = session.get(OrgRow, membership.org_id)
    if org is None or org.status != "active":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="org not active"
        )

    user.last_login_at = datetime.now(UTC)
    session.flush()

    token = encode_session(
        user_id=user.id, org_id=org.id, email=user.email, name=user.name
    )
    _set_session_cookie(response, token)
    session.commit()

    log.info("auth_login", user_id=user.id, org_id=org.id)
    return AuthSuccess(
        token=token,
        user=UserOut(user_id=user.id, email=user.email, name=user.name),
        org=OrgOut(org_id=org.id, name=org.name, plan=org.plan, role=membership.role),
        api_key=None,
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(response: Response) -> None:
    """Clear the session cookie. JWT is stateless — client also discards token."""
    response.delete_cookie(SESSION_COOKIE, path="/")


@router.get("/me", response_model=MeResponse)
def me(
    request: Request,
    session: Session = Depends(db_session),
) -> MeResponse:
    """Return the currently-authenticated user + org from JWT (cookie or Bearer)."""
    claims = _extract_session_claims(request)
    user = session.get(UserRow, claims["sub"])
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="user not found"
        )
    org = session.get(OrgRow, claims["org"])
    if org is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="org not found"
        )
    membership = session.execute(
        select(OrgMemberRow)
        .where(OrgMemberRow.user_id == user.id)
        .where(OrgMemberRow.org_id == org.id)
    ).scalar_one_or_none()
    role = membership.role if membership else "viewer"
    return MeResponse(
        user=UserOut(user_id=user.id, email=user.email, name=user.name),
        org=OrgOut(org_id=org.id, name=org.name, plan=org.plan, role=role),
    )


# ─────────────────────────────────────────────────────────────────────────────
# Session extraction helper (exported for deps.py to reuse)
# ─────────────────────────────────────────────────────────────────────────────


def _extract_session_claims(request: Request) -> dict[str, Any]:
    """Pull JWT from cookie OR Bearer header; decode + return claims.

    Raises HTTPException 401 on any failure.
    """
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        auth = request.headers.get("authorization", "")
        if auth.lower().startswith("bearer "):
            # Could be a JWT (human) or an API key (integration). Only treat as
            # a JWT if it looks like one (has 2 dots, doesn't start with gn_).
            candidate = auth.split(None, 1)[1].strip()
            if candidate.count(".") == 2 and not candidate.startswith("gn_"):
                token = candidate
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="no session token"
        )
    try:
        return decode_session(token)
    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e)
        ) from e
