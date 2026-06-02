"""Shared FastAPI dependencies — DB session + auth.

Auth model (v2):
- Customer integrations send `Authorization: Bearer <api_key>` on every request.
- The key is looked up in `secrets_ref` (g-i-1) and the linked AgentRegistry
  entry yields the org_id + granted scopes.
- Dashboard requests use the same header (browser → Next.js → backend), so
  the surface is uniform.

For local development the brain accepts `X-Dev-Org` when GENIOS_ENV is not
production. This is a deliberate convenience so the dashboard can boot without
a registered agent.
"""

from __future__ import annotations

from collections.abc import Iterator

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from core.delivery.store import AgentRegistryRow
from core.foundations.config import settings
from core.foundations.db import get_session
from core.foundations.telemetry import get_logger
from core.memory.store import SecretRef

log = get_logger(__name__)


def db_session() -> Iterator[Session]:
    """Yield a SQLAlchemy session scoped to one request."""
    with get_session() as session:
        yield session


def require_org(
    session: Session = Depends(db_session),
    authorization: str | None = Header(default=None),
    x_dev_org: str | None = Header(default=None, alias="X-Dev-Org"),
) -> str:
    """Resolve org_id from the bearer key (production) or X-Dev-Org (dev only).

    Returns org_id. Raises 401 on missing/invalid auth.
    """
    if authorization and authorization.lower().startswith("bearer "):
        api_key = authorization.split(None, 1)[1].strip()
        if not api_key:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="empty bearer token"
            )
        org_id = _lookup_org_for_api_key(session, api_key)
        if org_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="unknown api key"
            )
        return org_id

    if x_dev_org and settings.GENIOS_ENV.lower() != "production":
        return x_dev_org

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="missing Authorization: Bearer <api_key>",
    )


def _lookup_org_for_api_key(session: Session, api_key: str) -> str | None:
    """Resolve an api_key string to org_id via the SecretRef → AgentRegistry chain.

    We never store API keys in cleartext — the secrets table holds Fernet
    ciphertexts. To match a presented key we compare each agent's stored
    ciphertext via the encryption helper. Small N (handful of agents per org)
    keeps this acceptable for v1; a hash-prefix index can land when N grows.
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
