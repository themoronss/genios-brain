"""
Per-agent OAuth start + callback for Gmail / Calendar.

Mirrors the workspace-level flow in `integrations_auth.py`, but the
returned tokens are stored in `connector_credentials.metadata` against
a specific agent_uuid (encrypted via Fernet) instead of the workspace's
`oauth_tokens` table.

Flow:
  1. GET /v1/agents/{slug}/oauth/{tool}/start
     → builds Google auth URL, stashes (org_id, agent_uuid) in Redis
     → 302 redirect to Google
  2. User consents on Google
     → Google redirects to /v1/agents/oauth/callback?state=...&code=...
  3. Callback recovers state, exchanges code for tokens, stores in
     connector_credentials, kicks off initial sync, redirects to dashboard.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.deps import get_db, verify_api_key
from app.config import GOOGLE_REDIRECT_URI

FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")
from app.policy import agent_crud, connector_crud
from app.redis_client import redis_client

logger = logging.getLogger(__name__)
router = APIRouter()

# Per-agent OAuth callbacks share ONE redirect URI (configured in Google
# Console). Agent identity travels through the `state` param.
AGENT_OAUTH_CALLBACK_PATH = "/v1/agents/oauth/callback"


# ── Tool registry — tool_id → (build_flow, scopes, provider_label) ──────────
def _gmail_flow():
    from app.ingestion.gmail_connector import create_oauth_flow
    return create_oauth_flow()


def _calendar_flow():
    from app.ingestion.calendar_connector import create_calendar_oauth_flow
    return create_calendar_oauth_flow()


_TOOL_FLOWS = {
    "gmail":    (_gmail_flow,    "email",    "gmail"),
    "calendar": (_calendar_flow, "calendar", "calendar"),
}


# ── Routes ──────────────────────────────────────────────────────────────────
@router.get("/v1/agents/{slug}/oauth/{tool}/start")
def agent_oauth_start(
    slug: str,
    tool: str,
    org_id: str,                # query param — matches existing /auth/gmail/connect pattern
    db: Session = Depends(get_db),
):
    """Browser-initiated OAuth — auth via org_id query param (mirrors the
    workspace-level /auth/gmail/connect flow). Browsers can't carry Bearer
    headers across a 302, so we validate ownership by confirming the agent
    slug actually belongs to org_id before issuing the OAuth state."""
    if tool not in _TOOL_FLOWS:
        raise HTTPException(status_code=400, detail={"error": "UNKNOWN_TOOL", "tool": tool})

    row = agent_crud.find_agent(db, org_id, slug)
    if not row:
        raise HTTPException(status_code=404, detail={"error": "AGENT_NOT_FOUND"})

    flow_factory, _source, _provider = _TOOL_FLOWS[tool]
    flow = flow_factory()
    # Override the redirect_uri to our per-agent callback path
    flow.redirect_uri = _agent_callback_uri()

    auth_url, state = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
    )
    redis_client.setex(
        f"agent_oauth_state:{state}",
        300,
        json.dumps({
            "org_id": org_id,
            "agent_uuid": row[0],
            "agent_slug": slug,
            "tool": tool,
            "code_verifier": getattr(flow, "code_verifier", None),
        }),
    )
    return RedirectResponse(auth_url)


@router.get(AGENT_OAUTH_CALLBACK_PATH)
async def agent_oauth_callback(state: str, code: str, request: Request):
    raw = redis_client.get(f"agent_oauth_state:{state}")
    if not raw:
        return _redirect_to_dash(error="oauth_state_expired")
    redis_client.delete(f"agent_oauth_state:{state}")

    payload = json.loads(raw.decode() if isinstance(raw, bytes) else raw)
    org_id = payload["org_id"]
    agent_uuid = payload["agent_uuid"]
    agent_slug = payload["agent_slug"]
    tool = payload["tool"]
    code_verifier = payload.get("code_verifier")

    flow_factory, source, provider = _TOOL_FLOWS[tool]
    flow = flow_factory()
    flow.redirect_uri = _agent_callback_uri()
    if code_verifier:
        flow.code_verifier = code_verifier

    try:
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            flow.fetch_token(code=code)
    except Exception as e:
        logger.error(f"agent oauth token exchange failed: {e}")
        return _redirect_to_dash(error="oauth_token_exchange_failed")

    creds = flow.credentials
    access_token = creds.token
    refresh_token = creds.refresh_token
    expiry = creds.expiry

    # Resolve the actual Google account email so the dashboard can show it
    account_email = _resolve_account_email(tool, access_token, refresh_token)

    db = None
    try:
        from app.database import SessionLocal
        db = SessionLocal()
        meta = {
            "provider": provider,
            "account": account_email,
            "access_token":  access_token,
            "refresh_token": refresh_token,
            "token_expiry":  expiry.isoformat() if expiry else None,
            "oauth_provider": "google",
        }
        if source == "email" and account_email:
            meta["mailbox_address"] = account_email

        conn_id, _signing = connector_crud.upsert(db, org_id, agent_uuid, source, meta)
        db.commit()

        # Kick initial sync
        try:
            from app.tasks.sync_connector import task_sync_connector
            task_sync_connector.delay(conn_id)
        except Exception as e:
            logger.debug(f"initial sync enqueue skipped: {e}")
    except Exception as e:
        logger.exception(f"agent oauth store failed: {e}")
        if db:
            db.rollback()
        return _redirect_to_dash(error="oauth_store_failed")
    finally:
        if db:
            db.close()

    try:
        from app.core.analytics import capture
        capture(org_id, "agent_integration_connected", {"agent": agent_slug, "tool": tool})
    except Exception:
        pass

    return _redirect_to_dash(connected=tool, agent=agent_slug)


# ── Helpers ──────────────────────────────────────────────────────────────────
def _agent_callback_uri() -> str:
    """Build the absolute callback URI from existing GOOGLE_REDIRECT_URI's
    host + scheme — the path just changes."""
    if GOOGLE_REDIRECT_URI:
        # GOOGLE_REDIRECT_URI is configured in env to point at workspace callback;
        # swap the path to ours. Same host, same scheme, same OAuth client.
        from urllib.parse import urlparse, urlunparse
        u = urlparse(GOOGLE_REDIRECT_URI)
        return urlunparse((u.scheme, u.netloc, AGENT_OAUTH_CALLBACK_PATH, "", "", ""))
    # Fallback for local dev
    return f"{os.environ.get('GENIOS_BASE_URL', 'http://localhost:8001')}{AGENT_OAUTH_CALLBACK_PATH}"


def _resolve_account_email(tool: str, access_token: str, refresh_token: str) -> str:
    try:
        if tool == "gmail":
            from app.ingestion.gmail_connector import build_gmail_service, get_user_email
            return get_user_email(build_gmail_service(access_token, refresh_token)) or ""
        if tool == "calendar":
            from app.ingestion.calendar_connector import build_calendar_service, get_calendar_user_email
            return get_calendar_user_email(build_calendar_service(access_token, refresh_token)) or ""
    except Exception as e:
        logger.warning(f"resolve account_email failed for {tool}: {e}")
    return ""


def _redirect_to_dash(connected: str = None, agent: str = None, error: str = None) -> RedirectResponse:
    base = FRONTEND_URL or "http://localhost:3000"
    qs = []
    if connected: qs.append(f"connected={connected}")
    if agent:     qs.append(f"agent={agent}")
    if error:     qs.append(f"error={error}")
    suffix = ("?" + "&".join(qs)) if qs else ""
    target = f"{base}/dashboard/agents{suffix}"
    return RedirectResponse(url=target)
