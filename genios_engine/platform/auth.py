from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
from dataclasses import dataclass

from fastapi import Depends, Header, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import text

from genios_engine.platform.cache import get_cache, okey
from genios_engine.platform.config import get_settings
from genios_engine.platform.db import get_engine

# Auth & identity — ported from genios-brain/app/api/deps.py, engine-native + stdlib-only (no
# PyJWT/passlib/bcrypt dependency). Two credential families, BOTH resolving org_id server-side:
#   • JWT dashboard session (HS256, from /auth/login) — stateless, full owner scope.
#   • gn_live_… API key — sha256 at rest, Redis-cached 60s, carries a scope grant.
# Law: org_id ALWAYS comes from the credential, NEVER from a query param → tenant isolation.

_API_KEY_CACHE_TTL = 60
_KILL_TTL = 10
_PBKDF2_ITERS = 200_000
security = HTTPBearer(auto_error=False)


# ── base64url + HS256 JWT (stdlib) ─────────────────────────────────────────────────────
def _b64u(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def _b64u_dec(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def jwt_encode(payload: dict, secret: str) -> str:
    head = _b64u(json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")).encode())
    body = _b64u(json.dumps(payload, separators=(",", ":"), default=str).encode())
    signing = f"{head}.{body}".encode()
    sig = _b64u(hmac.new(secret.encode(), signing, hashlib.sha256).digest())
    return f"{head}.{body}.{sig}"


def jwt_decode(token: str, secret: str) -> dict | None:
    try:
        head, body, sig = token.split(".")
        expected = _b64u(hmac.new(secret.encode(), f"{head}.{body}".encode(), hashlib.sha256).digest())
        if not hmac.compare_digest(sig, expected):
            return None
        payload = json.loads(_b64u_dec(body))
        if payload.get("exp") and time.time() > float(payload["exp"]):
            return None
        return payload
    except Exception:
        return None


# ── password hashing (pbkdf2, stdlib) ──────────────────────────────────────────────────
def hash_password(pw: str) -> str:
    salt = secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac("sha256", pw.encode(), salt, _PBKDF2_ITERS)
    return f"pbkdf2${_PBKDF2_ITERS}${salt.hex()}${dk.hex()}"


def verify_password(pw: str, stored: str | None) -> bool:
    if not stored or not stored.startswith("pbkdf2$"):
        return False
    try:
        _, iters, salt_hex, hash_hex = stored.split("$")
        dk = hashlib.pbkdf2_hmac("sha256", pw.encode(), bytes.fromhex(salt_hex), int(iters))
        return hmac.compare_digest(dk.hex(), hash_hex)
    except Exception:
        return False


# ── API keys ────────────────────────────────────────────────────────────────────────
def hash_key(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def new_api_key() -> tuple[str, str, str]:
    """Return (raw_key, key_hash, key_prefix). Raw is shown ONCE; only the hash is stored."""
    raw = "gn_live_" + secrets.token_urlsafe(24)
    return raw, hash_key(raw), raw[:12]


@dataclass
class AuthCtx:
    org_id: str
    agent_id: str | None = None
    scopes: list[str] | None = None      # None = full owner scope (dashboard JWT / legacy key)
    plan_status: str = "active"
    source: str = "legacy"               # jwt | api_key | legacy

    def has_scope(self, scope: str) -> bool:
        return self.scopes is None or scope in self.scopes


def _engine():
    s = get_settings()
    if not s.database_url:
        raise HTTPException(503, "auth not available (no database configured)")
    return get_engine(s.database_url)


# ── kill switch (Redis-cached, fail-open) ──────────────────────────────────────────────
def check_kill_switch() -> None:
    cache = get_cache()
    cached = cache.get("ff:kill_switch_all")
    if cached == "0":
        raise HTTPException(503, {"error": "SERVICE_UNAVAILABLE", "message": "GeniOS is temporarily offline."})
    if cached == "1":
        return
    try:
        with _engine().connect() as c:
            row = c.execute(text("select enabled from feature_flags where key='kill_switch_all'")).first()
        live = row is None or bool(row.enabled)
        cache.setex("ff:kill_switch_all", _KILL_TTL, "1" if live else "0")
        if not live:
            raise HTTPException(503, {"error": "SERVICE_UNAVAILABLE", "message": "GeniOS is temporarily offline."})
    except HTTPException:
        raise
    except Exception:
        return                       # infra hiccup → fail open, never block on the flag lookup


# ── the resolver ───────────────────────────────────────────────────────────────────────
def verify_bearer(token: str) -> AuthCtx:
    check_kill_switch()
    s = get_settings()

    # Path 1 — JWT dashboard session (stateless, full owner scope)
    if token.count(".") == 2 and not token.startswith("gn_"):
        payload = jwt_decode(token, s.jwt_secret)
        if not payload or not payload.get("org_id"):
            raise HTTPException(401, {"code": "SESSION_EXPIRED", "message": "Please log in again."})
        org_id = str(payload["org_id"])
        with _engine().connect() as c:
            ok = c.execute(text("select 1 from orgs where id=:o"), {"o": org_id}).first()
        if ok is None:
            raise HTTPException(401, {"code": "TOKEN_REVOKED", "message": "Session no longer valid."})
        return AuthCtx(org_id=org_id, scopes=None, source="jwt")

    # Path 2 — gn_live_ API key
    if not token.startswith("gn_live_"):
        raise HTTPException(401, "Invalid credential format")
    hashed = hash_key(token)
    cache = get_cache()
    blob = cache.get_json(f"apikey:{hashed}")
    if blob is not None:
        if blob.get("plan_status") == "invalid":
            raise HTTPException(401, "Invalid API key")
        if blob.get("plan_status") == "suspended":
            raise HTTPException(403, {"error": "ACCOUNT_SUSPENDED"})
        return AuthCtx(org_id=blob["org_id"], agent_id=blob.get("agent_id"),
                       scopes=blob.get("scopes"), plan_status=blob.get("plan_status", "active"),
                       source="api_key")

    with _engine().begin() as c:
        row = c.execute(text(
            "select k.org_id, k.agent_id, k.scopes, o.plan_status from api_keys k "
            "join orgs o on o.id=k.org_id where k.key_hash=:h and k.is_active"),
            {"h": hashed}).first()
        if row is None:      # legacy: org primary key
            row2 = c.execute(text("select id as org_id, plan_status from orgs where api_key_hash=:h"),
                             {"h": hashed}).first()
            if row2 is None:
                cache.set_json(f"apikey:{hashed}", 30, {"org_id": "", "plan_status": "invalid"})
                raise HTTPException(401, "Invalid API key")
            ctx = AuthCtx(org_id=row2.org_id, scopes=None, plan_status=row2.plan_status or "active",
                          source="legacy")
        else:
            c.execute(text("update api_keys set last_used_at=now() where key_hash=:h"), {"h": hashed})
            ctx = AuthCtx(org_id=row.org_id, agent_id=row.agent_id, scopes=list(row.scopes or []),
                          plan_status=row.plan_status or "active", source="api_key")
    cache.set_json(f"apikey:{hashed}", _API_KEY_CACHE_TTL,
                   {"org_id": ctx.org_id, "agent_id": ctx.agent_id, "scopes": ctx.scopes,
                    "plan_status": ctx.plan_status})
    if ctx.plan_status == "suspended":
        raise HTTPException(403, {"error": "ACCOUNT_SUSPENDED"})
    return ctx


def invalidate_key_cache(key_hash: str) -> None:
    get_cache().delete(f"apikey:{key_hash}")


# ── FastAPI dependencies ───────────────────────────────────────────────────────────────
def get_auth_ctx(request: Request,
                 creds: HTTPAuthorizationCredentials | None = Depends(security)) -> AuthCtx:
    if creds is None or not creds.credentials:
        raise HTTPException(401, "Missing bearer credential")
    ctx = verify_bearer(creds.credentials)
    request.state.auth = ctx
    return ctx


_ORG_KILL_TTL = 30


def check_org_kill(org_id: str) -> None:
    """Per-org kill (spec Level C — the tenant's 'stop everything' switch, complementing the global
    kill and the per-source pause). A feature_flags row key='kill_switch:{org}' with enabled=false
    blocks every request for that org (503). Redis-cached (30s), fail-open like the global switch —
    an infra hiccup never blocks a legitimate tenant."""
    if not org_id:
        return
    cache = get_cache()
    ckey = f"ff:kill:{org_id}"
    cached = cache.get(ckey)
    if cached == "1":
        return
    if cached == "0":
        raise HTTPException(503, {"error": "TENANT_PAUSED", "message": "This workspace is paused."})
    try:
        with _engine().connect() as c:
            row = c.execute(text("select enabled from feature_flags where key=:k"),
                            {"k": f"kill_switch:{org_id}"}).first()
        live = row is None or bool(row.enabled)
        cache.setex(ckey, _ORG_KILL_TTL, "1" if live else "0")
        if not live:
            raise HTTPException(503, {"error": "TENANT_PAUSED", "message": "This workspace is paused."})
    except HTTPException:
        raise
    except Exception:
        return                       # infra hiccup → fail open


def get_current_org(ctx: AuthCtx = Depends(get_auth_ctx)) -> str:
    """The org_id, resolved from the credential. Endpoints use this INSTEAD of an org_id query
    param, so a caller can only ever touch their own tenant. Also enforces the per-org kill."""
    check_org_kill(ctx.org_id)
    return ctx.org_id


def require_scope(scope: str):
    """Dependency factory: 403 unless the credential carries `scope` (owner JWT = all scopes)."""
    def _dep(ctx: AuthCtx = Depends(get_auth_ctx)) -> AuthCtx:
        if not ctx.has_scope(scope):
            raise HTTPException(403, f"scope '{scope}' not granted")
        return ctx
    return _dep


def require_internal(x_internal_token: str | None = Header(None)) -> None:
    """Cron / internal endpoints (cross-org sweep, ingest-all). Requires a shared secret so a
    tenant can't trigger a cross-org run or enumerate which orgs exist. Denies if unset."""
    expected = get_settings().internal_token
    if not expected or x_internal_token != expected:
        raise HTTPException(403, "internal endpoint")


def verify_webhook_hmac(raw_body: bytes, signature: str | None, secret: str) -> bool:
    """HMAC-SHA256 hex over the raw body (same scheme as genios-brain X-Genios-Signature).
    Constant-time compare. Accepts an optional 'sha256=' / 'v1,' prefix on the header."""
    if not signature:
        return False
    expected = hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest()
    sig = signature.split("=", 1)[-1].split(",", 1)[-1].strip()
    return hmac.compare_digest(sig, expected)
