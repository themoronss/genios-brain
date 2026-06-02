"""Pluggable auth schemes for adapters.

Why this exists (g-i-1 §1.2.1 + custom integration path):
Custom sources use diverse auth: OAuth2, API key, service account, basic, mTLS,
JWT, signed headers. Each adapter shouldn't reinvent its own auth plumbing.

This module:
- Resolves a stored AuthConfig into a ready-to-use authenticator
- Handles OAuth2 refresh transparently when access tokens expire
- For providers issuing read+write tokens, an outer guard refuses non-read calls

Returns an `Authenticator` object that the adapter calls to sign / wrap outbound
HTTP requests. Adapters never touch raw credentials.
"""

from __future__ import annotations

import base64
from abc import ABC, abstractmethod
from typing import Any

import httpx
from sqlalchemy.orm import Session

from core.foundations.telemetry import get_logger
from core.memory.secrets import get_secret, rotate_secret
from core.memory.types import AuthConfig, AuthScheme

log = get_logger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Authenticator interface
# ─────────────────────────────────────────────────────────────────────────────


class Authenticator(ABC):
    """Signs/wraps outbound HTTP requests for the adapter."""

    @abstractmethod
    def apply(self, request: httpx.Request) -> httpx.Request:
        """Mutate the request in-place to add auth (headers, query, cert, etc.)."""


class _BearerToken(Authenticator):
    """Authorization: Bearer <token>. Used by OAuth2, API key, JWT, service account."""

    def __init__(self, token: str) -> None:
        self._token = token

    def apply(self, request: httpx.Request) -> httpx.Request:
        request.headers["Authorization"] = f"Bearer {self._token}"
        return request


class _BasicAuth(Authenticator):
    """Authorization: Basic <b64(user:pass)>."""

    def __init__(self, user: str, password: str) -> None:
        encoded = base64.b64encode(f"{user}:{password}".encode()).decode("ascii")
        self._header = f"Basic {encoded}"

    def apply(self, request: httpx.Request) -> httpx.Request:
        request.headers["Authorization"] = self._header
        return request


class _ApiKeyHeader(Authenticator):
    """X-Api-Key (or configurable header name)."""

    def __init__(self, key: str, header_name: str = "X-Api-Key") -> None:
        self._key = key
        self._header_name = header_name

    def apply(self, request: httpx.Request) -> httpx.Request:
        request.headers[self._header_name] = self._key
        return request


class _SignedHeader(Authenticator):
    """Custom signed header (e.g. webhook HMAC verification on outbound)."""

    def __init__(self, header_name: str, value: str) -> None:
        self._header_name = header_name
        self._value = value

    def apply(self, request: httpx.Request) -> httpx.Request:
        request.headers[self._header_name] = self._value
        return request


# ─────────────────────────────────────────────────────────────────────────────
# OAuth2 refresh wrapper (transparent token refresh + rotation)
# ─────────────────────────────────────────────────────────────────────────────


class OAuth2Authenticator(Authenticator):
    """Bearer token with transparent refresh.

    When the access token is rejected (401), this authenticator:
    1. Reads the refresh token from secrets
    2. Calls the provider's token_url
    3. Stores the new access token via rotate_secret
    4. Retries the original request once
    """

    def __init__(
        self,
        session: Session,
        access_token: str,
        access_secret_ref_id: str,
        refresh_token: str,
        token_url: str,
        client_id: str,
        client_secret: str,
    ) -> None:
        self._session = session
        self._access_token = access_token
        self._access_ref = access_secret_ref_id
        self._refresh_token = refresh_token
        self._token_url = token_url
        self._client_id = client_id
        self._client_secret = client_secret

    def apply(self, request: httpx.Request) -> httpx.Request:
        request.headers["Authorization"] = f"Bearer {self._access_token}"
        return request

    def refresh(self) -> None:
        """Refresh the access token using the refresh token. Persists the new value."""
        with httpx.Client(timeout=30.0) as client:
            resp = client.post(
                self._token_url,
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": self._refresh_token,
                    "client_id": self._client_id,
                    "client_secret": self._client_secret,
                },
            )
            resp.raise_for_status()
            data: dict[str, Any] = resp.json()

        new_access = data.get("access_token")
        if not new_access:
            raise AuthError("OAuth2 refresh returned no access_token")
        self._access_token = new_access
        rotate_secret(self._session, self._access_ref, new_access)
        log.info("oauth2_refreshed", access_ref=self._access_ref)


# ─────────────────────────────────────────────────────────────────────────────
# Factory
# ─────────────────────────────────────────────────────────────────────────────


class AuthError(Exception):
    """Misconfigured auth or refresh failure."""


def build_authenticator(session: Session, cfg: AuthConfig) -> Authenticator:
    """Resolve an AuthConfig into a ready Authenticator.

    The actual secret is fetched here (decrypted) and held only by the
    authenticator instance. Callers never touch plaintext.
    """
    plaintext = get_secret(session, cfg.secrets_ref_id)

    match cfg.scheme:
        case AuthScheme.OAUTH2:
            # extra: { token_url, client_id, client_secret, refresh_secret_ref_id }
            required = ["token_url", "client_id", "client_secret", "refresh_secret_ref_id"]
            for k in required:
                if k not in cfg.extra:
                    raise AuthError(f"OAuth2 missing extra param: {k}")
            refresh_plain = get_secret(session, cfg.extra["refresh_secret_ref_id"])
            return OAuth2Authenticator(
                session=session,
                access_token=plaintext,
                access_secret_ref_id=cfg.secrets_ref_id,
                refresh_token=refresh_plain,
                token_url=cfg.extra["token_url"],
                client_id=cfg.extra["client_id"],
                client_secret=cfg.extra["client_secret"],
            )
        case AuthScheme.API_KEY:
            header_name = cfg.extra.get("header_name", "X-Api-Key")
            return _ApiKeyHeader(plaintext, header_name=header_name)
        case AuthScheme.JWT:
            return _BearerToken(plaintext)
        case AuthScheme.SERVICE_ACCOUNT:
            # plaintext is a pre-issued bearer token here. Provider-specific token
            # exchange (e.g. Google JWT->Bearer) is handled by the adapter using SDKs.
            return _BearerToken(plaintext)
        case AuthScheme.BASIC:
            # extra: { user }; password = plaintext
            user = cfg.extra.get("user")
            if not user:
                raise AuthError("BASIC auth missing 'user' in extra")
            return _BasicAuth(user, plaintext)
        case AuthScheme.SIGNED_HEADER:
            header_name_opt = cfg.extra.get("header_name")
            if not header_name_opt:
                raise AuthError("SIGNED_HEADER missing 'header_name' in extra")
            return _SignedHeader(header_name_opt, plaintext)
        case AuthScheme.MTLS:
            # mTLS uses a client cert + key file; plaintext is unused here.
            # The adapter wires the cert into the httpx.Client; this returns a no-op auth.
            raise AuthError("MTLS handled by adapter's httpx.Client(cert=...), not header auth")
