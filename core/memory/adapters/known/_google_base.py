"""Shared Google OAuth helper for Drive/Docs/Sheets/Calendar/Gmail adapters.

Each Google adapter has the same boilerplate (client_id, client_secret env,
Credentials, refresh + rotate). Centralized here so per-service adapters are
just the API-specific code.
"""

from __future__ import annotations

import os
from typing import Any

from google.auth.transport.requests import Request as GoogleRequest
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build as google_build
from sqlalchemy.orm import Session

from core.memory.secrets import get_secret, rotate_secret


def google_client_id() -> str:
    v = os.getenv("GOOGLE_CLIENT_ID", "").strip()
    if not v:
        raise RuntimeError("GOOGLE_CLIENT_ID env var required")
    return v


def google_client_secret() -> str:
    v = os.getenv("GOOGLE_CLIENT_SECRET", "").strip()
    if not v:
        raise RuntimeError("GOOGLE_CLIENT_SECRET env var required")
    return v


def build_google_service(
    session: Session,
    *,
    api_name: str,
    api_version: str,
    access_secret_ref: str,
    refresh_secret_ref: str,
) -> Any:
    """Build a Google API service with auto-refresh of the access token.

    Rotated access token persisted via rotate_secret so subsequent runs reuse it.
    """
    access = get_secret(session, access_secret_ref)
    refresh = get_secret(session, refresh_secret_ref)
    creds = Credentials(  # type: ignore[no-untyped-call]
        token=access,
        refresh_token=refresh,
        token_uri="https://oauth2.googleapis.com/token",  # noqa: S106 — Google's well-known endpoint
        client_id=google_client_id(),
        client_secret=google_client_secret(),
    )
    if not creds.valid:
        creds.refresh(GoogleRequest())  # type: ignore[no-untyped-call]
        if creds.token and creds.token != access:
            rotate_secret(session, access_secret_ref, creds.token)
    return google_build(api_name, api_version, credentials=creds, cache_discovery=False)
