"""JWT session tokens — stateless human-user auth.

Encoded claims:
  sub      user_id
  org      org_id (for multi-org support; v1 = same as user's primary org)
  name     human-readable name (cached for UI)
  email    email
  exp      unix epoch expiry
  iat      issued at
  iss      "genios-brain"

Why stateless: a logout in production just deletes the cookie. To force
server-side revocation we'd need a revocation list; not built v1 — keep
TTL short (1 week default) so worst case is short-lived stolen tokens.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import jwt

from core.foundations.config import settings

ISSUER = "genios-brain"


class JWTError(Exception):
    """Token decode/verify failed."""


def encode_session(
    *,
    user_id: str,
    org_id: str,
    email: str,
    name: str,
    ttl_hours: int | None = None,
) -> str:
    """Sign a session token. Raises ValueError if JWT_SECRET is unset."""
    if not settings.JWT_SECRET:
        raise ValueError("JWT_SECRET must be configured to issue session tokens")
    ttl = ttl_hours if ttl_hours is not None else settings.JWT_TTL_HOURS
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "sub": user_id,
        "org": org_id,
        "email": email,
        "name": name,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(hours=ttl)).timestamp()),
        "iss": ISSUER,
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm="HS256")


def decode_session(token: str) -> dict[str, Any]:
    """Verify + decode. Raises JWTError on any failure (expired, bad sig, etc)."""
    if not settings.JWT_SECRET:
        raise JWTError("JWT_SECRET not configured")
    try:
        return jwt.decode(
            token,
            settings.JWT_SECRET,
            algorithms=["HS256"],
            issuer=ISSUER,
            options={"require": ["exp", "iat", "sub", "org"]},
        )
    except jwt.PyJWTError as e:
        raise JWTError(str(e)) from e
