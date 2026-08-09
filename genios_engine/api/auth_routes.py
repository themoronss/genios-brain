from __future__ import annotations

import time

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import text

from genios_engine.contracts.events import AGENT_ACTIONS, AGENT_API_SCOPES, HUMAN_API_SCOPES
from genios_engine.platform.auth import (AuthCtx, get_auth_ctx, get_current_org, hash_key,
                                         hash_password, invalidate_key_cache, jwt_encode,
                                         new_api_key, require_owner, verify_password)
from genios_engine.platform.config import get_settings
from genios_engine.platform.db import get_engine
from genios_engine.platform.ids import new_id

# Auth routes — register/login (dashboard) + scoped API-key minting (agents/integrations). This
# is the parity port of genios-brain/app/api/routes/auth.py, engine-native. org_id is issued
# here and thereafter always derived from the credential (never trusted from a request body).

router = APIRouter(prefix="/auth", tags=["auth"])
JWT_TTL_SECONDS = 7 * 24 * 3600
GRANTABLE = AGENT_ACTIONS | AGENT_API_SCOPES | HUMAN_API_SCOPES


def _engine():
    s = get_settings()
    if not s.database_url:
        raise HTTPException(503, "auth not available (no database configured)")
    return get_engine(s.database_url)


class Register(BaseModel):
    name: str
    email: str
    password: str


@router.post("/register")
def register(body: Register) -> dict:
    """Create a tenant + its first full-scope gn_live_ key + a dashboard JWT. Raw key shown ONCE."""
    org_id = new_id("org")
    raw, key_hash, prefix = new_api_key()
    with _engine().begin() as c:
        exists = c.execute(text("select 1 from orgs where lower(email)=lower(:e)"),
                           {"e": body.email}).first()
        if exists:
            raise HTTPException(409, "email already registered")
        # New tenants start on the trial with its credit allowance already granted — otherwise
        # the credits column defaults to 0 and a fresh trial reads as "out of credits".
        from genios_engine.platform.billing import PLAN_CREDITS
        c.execute(text("insert into orgs (id, name, email, pass_hash, api_key_hash, "
                       "subscription_tier, plan_status, credits) "
                       "values (:id,:n,:e,:p,:kh,'trial','trial',:cr)"),
                  {"id": org_id, "n": body.name, "e": body.email,
                   "p": hash_password(body.password), "kh": key_hash,
                   "cr": PLAN_CREDITS["trial"]})
        c.execute(text("insert into credit_ledger (org_id,kind,amount,balance_after,reason,bucket,"
                       "idempotency_key) values (:o,'reset',:cr,:cr,'trial:signup','credits',:idem)"),
                  {"o": org_id, "cr": PLAN_CREDITS["trial"], "idem": f"trial:{org_id}"})
        c.execute(text("insert into api_keys (id, org_id, key_hash, key_prefix, name, scopes) "
                       "values (:id,:o,:kh,:pfx,'primary',:sc)"),
                  {"id": new_id("key"), "o": org_id, "kh": key_hash, "pfx": prefix,
                   "sc": sorted(GRANTABLE)})
    token = jwt_encode({"org_id": org_id, "email": body.email, "exp": time.time() + JWT_TTL_SECONDS},
                       get_settings().jwt_secret)
    return {"org_id": org_id, "token": token, "name": body.name, "email": body.email,
            "api_key": raw, "key_prefix": prefix, "note": "store api_key now — shown only once"}


class Login(BaseModel):
    email: str
    password: str


@router.post("/login")
def login(body: Login) -> dict:
    with _engine().connect() as c:
        row = c.execute(text("select id, name, pass_hash, plan_status, subscription_tier "
                             "from orgs where lower(email)=lower(:e)"), {"e": body.email}).first()
    if row is None or not verify_password(body.password, row.pass_hash):
        raise HTTPException(401, "invalid email or password")
    if row.plan_status == "suspended":
        raise HTTPException(403, {"error": "ACCOUNT_SUSPENDED"})
    token = jwt_encode({"org_id": row.id, "email": body.email, "exp": time.time() + JWT_TTL_SECONDS},
                       get_settings().jwt_secret)
    from genios_engine.platform.audit import record
    record(row.id, "user_logged_in", actor_type="user", actor_id=body.email)
    return {"org_id": row.id, "token": token, "name": row.name, "email": body.email,
            "plan": row.subscription_tier}


class MintKey(BaseModel):
    name: str = "key"
    agent_id: str | None = None
    scopes: list[str]                    # subset of the controlled grant vocabulary


@router.post("/keys")
def mint_key(body: MintKey, ctx: AuthCtx = Depends(require_owner)) -> dict:
    """Mint a scoped gn_live_ key for the authenticated tenant. This is the 'pick scope → get
    key → key carries that scope' flow. Raw key returned ONCE."""
    org_id = ctx.org_id
    bad = [s for s in body.scopes if s not in GRANTABLE]
    if bad:
        raise HTTPException(422, f"unknown scopes: {bad}")
    raw, key_hash, prefix = new_api_key()
    with _engine().begin() as c:
        c.execute(text("insert into api_keys (id, org_id, key_hash, key_prefix, name, agent_id, scopes) "
                       "values (:id,:o,:kh,:pfx,:n,:aid,:sc)"),
                  {"id": new_id("key"), "o": org_id, "kh": key_hash, "pfx": prefix,
                   "n": body.name, "aid": body.agent_id, "sc": body.scopes})
    return {"api_key": raw, "key_prefix": prefix, "scopes": body.scopes,
            "note": "store api_key now — shown only once"}


@router.get("/keys")
def list_keys(ctx: AuthCtx = Depends(require_owner)) -> dict:
    org_id = ctx.org_id
    with _engine().connect() as c:
        rows = c.execute(text("select id, key_prefix, name, agent_id, scopes, is_active, "
                              "created_at, last_used_at from api_keys where org_id=:o "
                              "order by created_at desc"), {"o": org_id}).mappings().all()
    return {"keys": [dict(r) for r in rows]}      # never returns key_hash or the raw key


@router.delete("/keys/{key_id}")
def revoke_key(key_id: str, ctx: AuthCtx = Depends(require_owner)) -> dict:
    org_id = ctx.org_id
    with _engine().begin() as c:
        row = c.execute(text("select key_hash from api_keys where id=:id and org_id=:o"),
                        {"id": key_id, "o": org_id}).first()
        if row is None:
            raise HTTPException(404, "key not found")
        c.execute(text("update api_keys set is_active=false where id=:id"), {"id": key_id})
    invalidate_key_cache(row.key_hash)
    return {"revoked": True, "key_id": key_id}


@router.get("/me")
def whoami(ctx: AuthCtx = Depends(get_auth_ctx)) -> dict:
    return {"org_id": ctx.org_id, "agent_id": ctx.agent_id, "scopes": ctx.scopes,
            "plan_status": ctx.plan_status, "source": ctx.source}


@router.post("/logout")
def logout() -> dict:
    """JWT sessions are stateless — logout is client-side (drop the token). This exists so the
    dashboard's logout call gets a clean 200 instead of a 404."""
    return {"ok": True}
