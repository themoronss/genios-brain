"""Shared FastAPI dependencies — DB session + auth.

v1 stack owns human auth (signup/login/JWT). v2 brain validates inbound
requests using the SAME orgs/api_keys tables v1 created. No second auth
system; one source of truth.

`require_org` resolution order:
  1. JWT (cookie 'genios_session' OR 'Authorization: Bearer <jwt>') —
     decoded with shared JWT_SECRET; reads org_id claim (v1 shape).
  2. Bearer API key — sha256(key) looked up in v1's `api_keys` table
     (or hash_api_key column on `orgs` row for legacy 1-key-per-org accounts).
  3. X-Dev-Org — dev convenience header, refused when GENIOS_ENV=production.
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterator

import jwt
from fastapi import Depends, Header, HTTPException, Request, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from core.foundations.config import settings
from core.foundations.db import get_session
from core.foundations.telemetry import get_logger

log = get_logger(__name__)
SESSION_COOKIE = "genios_session"


def db_session() -> Iterator[Session]:
    """Yield a SQLAlchemy session scoped to one request."""
    with get_session() as session:
        yield session


def require_org(
    request: Request,
    session: Session = Depends(db_session),
    authorization: str | None = Header(default=None),
    x_dev_org: str | None = Header(default=None, alias="X-Dev-Org"),
) -> str:
    """Resolve org_id from JWT cookie, JWT bearer, API-key bearer, or X-Dev-Org."""
    jwt_token = request.cookies.get(SESSION_COOKIE)
    api_key: str | None = None

    if authorization and authorization.lower().startswith("bearer"):
        parts = authorization.split(None, 1)
        token = parts[1].strip() if len(parts) > 1 else ""
        if token:
            # JWTs are 3 dot-separated segments and don't use the v1 'gn_' prefix
            if token.count(".") == 2 and not token.startswith("gn_"):
                jwt_token = jwt_token or token
            else:
                api_key = token

    if jwt_token:
        org_id = _org_from_jwt(jwt_token)
        if org_id is not None:
            return org_id

    if api_key:
        org_id = _org_from_api_key(session, api_key)
        if org_id is not None:
            return org_id
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="unknown api key"
        )

    if x_dev_org and settings.GENIOS_ENV.lower() != "production":
        return x_dev_org

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="missing auth (cookie session, Bearer token, or X-Dev-Org)",
    )


def require_org_and_policy(
    request: Request,
    session: Session = Depends(db_session),
    authorization: str | None = Header(default=None),
    x_dev_org: str | None = Header(default=None, alias="X-Dev-Org"),
) -> dict:
    """Resolve org_id PLUS per-agent scope policy.

    Returns: {org_id: str, policy: dict|None, agent_uuid: str|None,
              scope_source: 'agent' | 'jwt' | 'dev'}

    - JWT (cookie or Bearer) → policy=None  (dashboard/admin = unrestricted)
    - API key (Bearer gn_*)  → policy from api_keys → agent_scopes
    - X-Dev-Org              → policy=None  (dev only, non-prod)

    Endpoints that need scope enforcement pass this dep instead of
    `require_org`. v1 scope_filter / v2_scope are then applied at SQL.
    """
    jwt_token = request.cookies.get(SESSION_COOKIE)
    api_key: str | None = None

    if authorization and authorization.lower().startswith("bearer"):
        parts = authorization.split(None, 1)
        token = parts[1].strip() if len(parts) > 1 else ""
        if token:
            if token.count(".") == 2 and not token.startswith("gn_"):
                jwt_token = jwt_token or token
            else:
                api_key = token

    if jwt_token:
        org_id = _org_from_jwt(jwt_token)
        if org_id is not None:
            return {"org_id": org_id, "policy": None, "agent_uuid": None, "scope_source": "jwt"}

    if api_key:
        ctx = _org_and_policy_from_api_key(session, api_key)
        if ctx is not None:
            return ctx
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="unknown api key"
        )

    if x_dev_org and settings.GENIOS_ENV.lower() != "production":
        return {"org_id": x_dev_org, "policy": None, "agent_uuid": None, "scope_source": "dev"}

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="missing auth (cookie session, Bearer token, or X-Dev-Org)",
    )


def _org_and_policy_from_api_key(session: Session, raw_key: str) -> dict | None:
    """Join api_keys → registered_agents → agent_scopes to return both
    org_id and the active policy. Falls back to legacy 1-key-per-org rows
    on `orgs.api_key` (no policy attached → unrestricted)."""
    hashed = hashlib.sha256(raw_key.encode("utf-8")).hexdigest()
    row = session.execute(
        text("""
            SELECT ak.org_id, ak.agent_uuid::text AS agent_uuid,
                   asc_.policy_json
            FROM api_keys ak
            LEFT JOIN agent_scopes asc_
              ON asc_.agent_uuid = ak.agent_uuid AND asc_.is_active = TRUE
            WHERE ak.key_hash = :h AND ak.is_active = TRUE
            LIMIT 1
        """),
        {"h": hashed},
    ).fetchone()
    if row is not None:
        import json as _json
        policy = None
        if row.policy_json is not None:
            try:
                policy = row.policy_json if isinstance(row.policy_json, dict) else _json.loads(row.policy_json)
            except Exception:
                policy = None
        return {
            "org_id": str(row.org_id),
            "policy": policy,
            "agent_uuid": row.agent_uuid,
            "scope_source": "agent" if row.agent_uuid else "legacy",
        }

    # Legacy: orgs.api_key (plaintext OR hashed). No agent attached.
    row = session.execute(
        text("SELECT id FROM orgs WHERE api_key = :raw OR api_key = :h LIMIT 1"),
        {"raw": raw_key, "h": hashed},
    ).fetchone()
    if row is not None:
        return {"org_id": str(row[0]), "policy": None, "agent_uuid": None, "scope_source": "legacy"}
    return None


def _org_from_jwt(token: str) -> str | None:
    """Decode a v1-shape JWT ({org_id, email, exp}) and return org_id."""
    if not settings.JWT_SECRET:
        return None
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=["HS256"])
    except jwt.PyJWTError:
        return None
    org_id = payload.get("org_id") or payload.get("org") or payload.get("sub")
    return str(org_id) if org_id else None


def _org_from_api_key(session: Session, raw_key: str) -> str | None:
    """Look up `raw_key` against v1's auth tables.

    Two storage paths exist (v1 evolved):
      (a) `orgs.api_key` — legacy 1-key-per-org accounts (column is plaintext OR
          its sha256 hash, depending on age — try both)
      (b) `api_keys.key_hash` — multi-key-per-org (added in v1 migration 034)

    Returns the resolved org_id (UUID string) or None on no match.
    """
    hashed = hashlib.sha256(raw_key.encode("utf-8")).hexdigest()

    # Path (b): api_keys.key_hash. Most recent + supports rotation.
    row = session.execute(
        text(
            "SELECT org_id FROM api_keys "
            "WHERE key_hash = :h AND is_active = TRUE "
            "LIMIT 1"
        ),
        {"h": hashed},
    ).fetchone()
    if row is not None:
        return str(row[0])

    # Path (a): legacy `orgs.api_key`. Plaintext match OR sha256 match.
    row = session.execute(
        text("SELECT id FROM orgs WHERE api_key = :raw OR api_key = :h LIMIT 1"),
        {"raw": raw_key, "h": hashed},
    ).fetchone()
    if row is not None:
        return str(row[0])

    return None
