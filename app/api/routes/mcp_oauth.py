"""
OAuth 2.1 authorization server for MCP remote clients (Claude Web, ChatGPT,
mobile Claude). Implements the minimum surface MCP's spec demands:

  - /.well-known/oauth-authorization-server    (RFC 8414 metadata)
  - /.well-known/oauth-protected-resource      (RFC 9728 — MCP spec)
  - /register                                   (RFC 7591 dynamic client reg)
  - /authorize + /authorize/consent             (auth-code + PKCE S256)
  - /token                                      (code exchange)

Identity model: this server does not introduce a new user system. A user's
existing `gn_live_*` API key IS the credential. The consent screen asks the
user to paste their key; the auth server then mints an opaque OAuth
access_token whose only job is to index back to that key in Redis.

The /mcp endpoint accepts either a raw `gn_live_*` (the local-stdio path,
unchanged) or an OAuth access_token (the Claude Web path). Both resolve to
the same org_id on the way down.

This is deliberately small — ~250 lines — because we are NOT an identity
provider. We just satisfy Claude's OAuth client so it can reuse the key the
user already has. When we later migrate to real per-user accounts, only
the consent form changes.
"""
from __future__ import annotations

import hashlib
import json as _json
import logging
import secrets
from typing import Any

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from sqlalchemy import text

from app.api.routes.mcp_oauth_consent import render_consent
from app.database import SessionLocal
from app.redis_client import redis_client

logger = logging.getLogger(__name__)
router = APIRouter(tags=["mcp-oauth"])

CODE_TTL_SEC = 300          # 5 min — authorization code lifetime
TOKEN_TTL_SEC = 24 * 3600   # 24 h — access_token lifetime
_CODE_PREFIX = "mcp:oauth:code:"
_TOKEN_PREFIX = "mcp:oauth:token:"
_CLIENT_PREFIX = "mcp:oauth:client:"


# ── helpers ──────────────────────────────────────────────────────────────────

def _b64url_nopad(raw: bytes) -> str:
    import base64

    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _hash_key(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def _s256(verifier: str) -> str:
    return _b64url_nopad(hashlib.sha256(verifier.encode("ascii")).digest())


def _issuer(request: Request) -> str:
    # Respect forward headers so the issuer matches the public URL even behind
    # DigitalOcean's load balancer.
    proto = request.headers.get("x-forwarded-proto", request.url.scheme)
    host = request.headers.get("x-forwarded-host") or request.headers.get("host") or request.url.hostname
    return f"{proto}://{host}"


def _lookup_org(raw_key: str) -> str | None:
    """Resolve a `gn_live_*` key to an org_id. Returns None if invalid/suspended."""
    if not raw_key or not raw_key.startswith("gn_live_"):
        return None
    hashed = _hash_key(raw_key)
    db = SessionLocal()
    try:
        row = db.execute(
            text("SELECT id, plan_status FROM orgs WHERE api_key = :raw OR api_key_hash = :hashed"),
            {"raw": raw_key, "hashed": hashed},
        ).fetchone()
        if not row:
            row = db.execute(
                text(
                    "SELECT o.id, o.plan_status FROM api_keys ak "
                    "JOIN orgs o ON ak.org_id = o.id "
                    "WHERE ak.key_hash = :hashed AND ak.is_active = TRUE"
                ),
                {"hashed": hashed},
            ).fetchone()
        if not row:
            return None
        if (row[1] or "active") == "suspended":
            return None
        return str(row[0])
    finally:
        db.close()


def _redis_set_json(key: str, payload: dict[str, Any], ttl: int) -> None:
    redis_client.setex(key, ttl, _json.dumps(payload))


def _redis_get_json(key: str) -> dict[str, Any] | None:
    raw = redis_client.get(key)
    if not raw:
        return None
    try:
        return _json.loads(raw)
    except Exception:
        return None


def resolve_oauth_token(access_token: str) -> str | None:
    """Map an opaque OAuth access_token back to the user's gn_live_* key."""
    data = _redis_get_json(_TOKEN_PREFIX + access_token)
    if not data:
        return None
    return data.get("api_key")


# ── metadata ─────────────────────────────────────────────────────────────────

@router.get("/.well-known/oauth-authorization-server")
async def oauth_as_metadata(request: Request):
    iss = _issuer(request)
    return {
        "issuer": iss,
        "authorization_endpoint": f"{iss}/authorize",
        "token_endpoint": f"{iss}/token",
        "registration_endpoint": f"{iss}/register",
        "response_types_supported": ["code"],
        "grant_types_supported": ["authorization_code"],
        "code_challenge_methods_supported": ["S256"],
        "token_endpoint_auth_methods_supported": ["none"],
        "scopes_supported": ["mcp"],
    }


@router.get("/.well-known/oauth-protected-resource")
async def oauth_resource_metadata(request: Request):
    iss = _issuer(request)
    return {
        "resource": f"{iss}/mcp",
        "authorization_servers": [iss],
        "scopes_supported": ["mcp"],
        "bearer_methods_supported": ["header"],
    }


# ── dynamic client registration (RFC 7591) ───────────────────────────────────

@router.post("/register")
async def register_client(request: Request):
    try:
        body = await request.json()
    except Exception:
        body = {}

    client_id = "mcp_" + secrets.token_urlsafe(16)
    stored = {
        "client_id": client_id,
        "client_name": body.get("client_name", "unknown"),
        "redirect_uris": body.get("redirect_uris", []),
    }
    _redis_set_json(_CLIENT_PREFIX + client_id, stored, ttl=30 * 24 * 3600)
    return JSONResponse(
        content={
            "client_id": client_id,
            "client_id_issued_at": 0,
            "token_endpoint_auth_method": "none",
            "grant_types": ["authorization_code"],
            "response_types": ["code"],
            "redirect_uris": stored["redirect_uris"],
        },
        status_code=201,
    )


# ── authorize (consent form) ─────────────────────────────────────────────────

@router.get("/authorize")
async def authorize_get(request: Request):
    q = request.query_params
    response_type = q.get("response_type")
    client_id = q.get("client_id") or ""
    redirect_uri = q.get("redirect_uri") or ""
    state = q.get("state") or ""
    code_challenge = q.get("code_challenge") or ""
    code_challenge_method = q.get("code_challenge_method") or "S256"

    if response_type != "code":
        raise HTTPException(400, "unsupported_response_type")
    if code_challenge_method != "S256":
        raise HTTPException(400, "code_challenge_method must be S256")
    if not redirect_uri.startswith("https://"):
        raise HTTPException(400, "redirect_uri must be https://")

    stored = _redis_get_json(_CLIENT_PREFIX + client_id)
    client_name = (stored or {}).get("client_name", "An MCP client")

    html = render_consent(client_name, client_id, redirect_uri, state, code_challenge, code_challenge_method)
    return HTMLResponse(content=html)


@router.post("/authorize/consent")
async def authorize_consent(
    request: Request,
    client_id: str = Form(...),
    redirect_uri: str = Form(...),
    state: str = Form(""),
    code_challenge: str = Form(...),
    code_challenge_method: str = Form("S256"),
    api_key: str = Form(...),
):
    org_id = _lookup_org(api_key.strip())
    if not org_id:
        html = render_consent(
            "An MCP client", client_id, redirect_uri, state, code_challenge, code_challenge_method,
            error="That API key is invalid, suspended, or not formatted as gn_live_*.",
        )
        return HTMLResponse(content=html, status_code=401)

    code = secrets.token_urlsafe(32)
    _redis_set_json(
        _CODE_PREFIX + code,
        {
            "org_id": org_id,
            "api_key": api_key.strip(),
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "code_challenge": code_challenge,
        },
        ttl=CODE_TTL_SEC,
    )

    sep = "&" if "?" in redirect_uri else "?"
    dest = f"{redirect_uri}{sep}code={code}"
    if state:
        dest += f"&state={state}"
    return RedirectResponse(dest, status_code=302)


# ── token exchange ───────────────────────────────────────────────────────────

@router.post("/token")
async def token_exchange(request: Request):
    form = await request.form()
    grant_type = form.get("grant_type")
    code = form.get("code") or ""
    redirect_uri = form.get("redirect_uri") or ""
    client_id = form.get("client_id") or ""
    verifier = form.get("code_verifier") or ""

    if grant_type != "authorization_code":
        return JSONResponse({"error": "unsupported_grant_type"}, status_code=400)

    data = _redis_get_json(_CODE_PREFIX + code)
    if not data:
        return JSONResponse({"error": "invalid_grant", "error_description": "code expired or unknown"}, status_code=400)

    # Codes are single-use.
    redis_client.delete(_CODE_PREFIX + code)

    if data["client_id"] != client_id or data["redirect_uri"] != redirect_uri:
        return JSONResponse({"error": "invalid_grant"}, status_code=400)
    if _s256(verifier) != data["code_challenge"]:
        return JSONResponse({"error": "invalid_grant", "error_description": "PKCE verifier mismatch"}, status_code=400)

    access_token = secrets.token_urlsafe(40)
    _redis_set_json(
        _TOKEN_PREFIX + access_token,
        {"org_id": data["org_id"], "api_key": data["api_key"], "client_id": client_id},
        ttl=TOKEN_TTL_SEC,
    )
    return {
        "access_token": access_token,
        "token_type": "Bearer",
        "expires_in": TOKEN_TTL_SEC,
        "scope": "mcp",
    }
