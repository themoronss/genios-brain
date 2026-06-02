"""Shared FastAPI dependencies — DB session + auth.

Auth resolution order for `require_org`:

1. JWT (browser flow)        — cookie `genios_session` OR Bearer <jwt>
2. API key (integration)     — Bearer <api_key>; resolves via SecretRef → AgentRegistry
3. X-Dev-Org (dev only)      — convenience header, refused when GENIOS_ENV=production

Returns the org_id (string) on success; raises 401 on failure.
"""

from __future__ import annotations

from collections.abc import Iterator

from fastapi import Depends, Header, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from core.delivery.store import AgentRegistryRow
from core.foundations.config import settings
from core.foundations.db import get_session
from core.foundations.jwt_session import JWTError, decode_session
from core.foundations.telemetry import get_logger
from core.memory.store import SecretRef

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
    # 1. JWT cookie
    jwt_token = request.cookies.get(SESSION_COOKIE)

    # 2. Bearer can be JWT or API key — disambiguate by shape
    api_key: str | None = None
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization.split(None, 1)[1].strip()
        if token:
            # JWTs are 3 dot-separated segments and don't use our gn_ prefix
            if token.count(".") == 2 and not token.startswith("gn_"):
                jwt_token = jwt_token or token
            else:
                api_key = token

    if jwt_token:
        try:
            claims = decode_session(jwt_token)
            return str(claims["org"])
        except (JWTError, KeyError):
            # Fall through — maybe the request also has an API key or dev header
            pass

    if api_key:
        org_id = _lookup_org_for_api_key(session, api_key)
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


def _lookup_org_for_api_key(session: Session, api_key: str) -> str | None:
    """Resolve api_key → org_id via SecretRef → AgentRegistry chain.

    Each agent's ciphertext is decrypted + compared. Small N (handful of
    agents per org) keeps this acceptable for v1; a hash-prefix index can
    land when N grows.
    """
    from core.foundations.encryption import decrypt

    agents = (
        session.execute(
            select(AgentRegistryRow).where(AgentRegistryRow.api_key_ref.is_not(None))
        )
        .scalars()
        .all()
    )
    for agent in agents:
        if agent.api_key_ref is None:
            continue
        secret = session.get(SecretRef, agent.api_key_ref)
        if secret is None:
            continue
        try:
            if decrypt(secret.encrypted_value) == api_key:
                return agent.org_id
        except Exception:  # noqa: S112 — one bad cipher must not block other matches
            continue
    return None
