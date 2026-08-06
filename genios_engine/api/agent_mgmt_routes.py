"""Agent Registry management API — the dashboard's Agents page. Authoring surface only: register an
agent (server mints the key), view/edit its scope policy, rotate its key, grant it accounts, read its
call audit, archive it. Identity is the key hash at rest (raw key shown once). These endpoints lived
only in the old genios-brain; wired onto the engine's agent_registry so the page shows real data.

Scope is STORED and returned; SQL-layer read-enforcement is honoured wherever the query path already
scopes agent reads (see platform/auth) — grants/segment enforcement is tracked in the backlog.
"""
from __future__ import annotations

import json
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import text

from genios_engine.platform.auth import (AuthCtx, get_auth_ctx, hash_key, invalidate_key_cache,
                                         require_owner)
from genios_engine.platform.ids import new_id
from genios_engine.platform.wiring import make_graph_store

router = APIRouter()
_graph = make_graph_store()

_DEFAULT_SCOPE = {"connectors": None, "segments": None, "fact_types": None,
                  "exclude_tags": [], "max_age_days": 365, "min_confidence": 0.0}
_DEFAULT_ACTIONS = ["read_context"]      # a dashboard-minted agent reads the brain; L5 claim is opt-in


def _scope(v) -> dict:
    s = v if isinstance(v, dict) else (json.loads(v) if v else {})
    return {**_DEFAULT_SCOPE, **s} if s else dict(_DEFAULT_SCOPE)


def _counts(c, org_id: str, agent_id: str) -> tuple[int, int]:
    since = datetime.now(timezone.utc) - timedelta(hours=24)
    calls = c.execute(text("select count(*) from agent_events where org_id=:o and agent_id=:a "
                           "and occurred_at >= :s"), {"o": org_id, "a": agent_id, "s": since}).scalar()
    blocked = c.execute(text("select count(*) from agent_events where org_id=:o and agent_id=:a "
                             "and occurred_at >= :s and result='blocked'"),
                        {"o": org_id, "a": agent_id, "s": since}).scalar()
    return int(calls or 0), int(blocked or 0)


def _summary(c, r, org_id: str) -> dict:
    calls, blocked = _counts(c, org_id, r.agent_id)
    return {
        "agent_id": r.agent_id, "name": r.name, "description": r.description,
        "status": r.status or "active", "scope": _scope(r.scope),
        "scope_version": int(r.scope_version or 1), "calls_24h": calls, "blocked_24h": blocked,
        "created_at": r.created_at.isoformat() if r.created_at else None,
        "is_default": bool(r.is_default), "connectors": [],
        # Proactive push: the URL is shown; the signing secret is write-only (returned once on set).
        "webhook_url": getattr(r, "webhook_url", None),
        "webhook_configured": bool(getattr(r, "webhook_secret", None)),
    }


@router.get("/v1/agents")
def list_agents(ctx: AuthCtx = Depends(require_owner)) -> dict:
    org_id = ctx.org_id
    with _graph.engine.connect() as c:
        rows = c.execute(text(
            "select agent_id, name, description, status, scope, scope_version, is_default, "
            "webhook_url, webhook_secret, created_at from agent_registry "
            "where org_id=:o and coalesce(status,'active')<>'archived' "
            "order by created_at desc nulls last"), {"o": org_id}).fetchall()
        agents = [_summary(c, r, org_id) for r in rows]
    return {"agents": agents, "count": len(agents)}


@router.get("/v1/agents/me")
def whoami(ctx: AuthCtx = Depends(get_auth_ctx)) -> dict:
    return {"org_id": ctx.org_id, "agent_id": ctx.agent_id,
            "scope_source": "owner" if ctx.scopes is None else "credential",
            "scope": dict(_DEFAULT_SCOPE) if ctx.scopes is None else None}


class CreateAgent(BaseModel):
    agent_id: str
    name: str | None = None
    description: str | None = None
    scope: dict | None = None
    webhook_url: str | None = None      # optional: register proactive push at create time


def _mint_key() -> tuple[str, str, str]:
    raw = "gn_live_" + secrets.token_urlsafe(24)
    return raw, raw[:12], hash_key(raw)


def _mint_webhook_secret() -> str:
    """Per-agent HMAC signing secret for outbound push. Shown once; the agent verifies
    X-Genios-Signature = sha256 hex of the raw body with this secret."""
    return "gnwh_" + secrets.token_urlsafe(32)


def _clean_webhook_url(url: str | None) -> str | None:
    url = (url or "").strip()
    if not url:
        return None
    if not (url.startswith("https://") or url.startswith("http://")):
        raise HTTPException(422, {"error": "invalid_webhook_url",
                                  "message": "webhook_url must start with https:// (http:// allowed for localhost)"})
    return url


@router.post("/v1/agents")
def create_agent(body: CreateAgent, ctx: AuthCtx = Depends(require_owner)) -> dict:
    org_id = ctx.org_id
    aid = (body.agent_id or "").strip()
    if not aid or len(aid) < 2:
        raise HTTPException(422, {"error": "invalid_agent_id", "message": "agent_id required (≥2 chars)"})
    raw, prefix, key_hash = _mint_key()
    scope = _scope(body.scope)
    webhook_url = _clean_webhook_url(body.webhook_url)
    webhook_secret = _mint_webhook_secret() if webhook_url else None
    now = datetime.now(timezone.utc)
    with _graph.engine.begin() as c:
        # race-safe: rely on the unique(org_id, agent_id) index (migration 0017) — ON CONFLICT DO
        # NOTHING + RETURNING means a concurrent create can't slip past a TOCTOU SELECT check.
        row = c.execute(text(
            "insert into agent_registry (id, org_id, agent_id, key_hash, allowed_actions, name, "
            "description, status, scope, scope_version, key_prefix, webhook_url, webhook_secret, "
            "created_at, scope_updated_at) "
            "values (:id,:o,:a,:kh,:acts,:nm,:desc,'active',cast(:sc as jsonb),1,:kp,:wu,:ws,:ts,:ts) "
            "on conflict (org_id, agent_id) do nothing returning agent_id"),
            {"id": new_id("agt"), "o": org_id, "a": aid, "kh": key_hash, "acts": _DEFAULT_ACTIONS,
             "nm": body.name, "desc": body.description, "sc": json.dumps(scope), "kp": prefix,
             "wu": webhook_url, "ws": webhook_secret, "ts": now}).first()
        if row is None:
            raise HTTPException(409, {"error": "agent_exists", "message": f"agent '{aid}' already exists"})
        # ALSO register the key in api_keys so it authenticates get_current_org (/v1/*) — a key only
        # in agent_registry can't call the brain (verify_bearer never reads agent_registry).
        c.execute(text(
            "insert into api_keys (id, org_id, key_hash, key_prefix, name, agent_id, scopes, is_active) "
            "values (:i,:o,:kh,:kp,:nm,:a,:sc,true)"),
            {"i": new_id("key"), "o": org_id, "kh": key_hash, "kp": prefix, "nm": aid, "a": aid,
             "sc": _DEFAULT_ACTIONS})
    from genios_engine.platform.audit import record
    record(org_id, "permission_changed", actor_type="user", target_type="agent", target_id=aid,
           metadata={"event": "agent_created", "webhook": bool(webhook_url)})
    out = {"agent_id": aid, "key": raw, "key_prefix": prefix, "scope": scope,
           "warning": "Copy this key now — it is shown only once and cannot be recovered."}
    if webhook_url:
        out["webhook_url"] = webhook_url
        out["webhook_secret"] = webhook_secret   # shown once; agent verifies X-Genios-Signature with it
    return out


def _get_agent(c, org_id: str, aid: str):
    r = c.execute(text(
        "select agent_id, name, description, status, scope, scope_version, scope_updated_at, "
        "is_default, key_prefix, created_at, key_last_used_at, webhook_url, webhook_secret "
        "from agent_registry where org_id=:o and agent_id=:a"), {"o": org_id, "a": aid}).first()
    if r is None:
        raise HTTPException(404, {"error": "not_found", "message": "agent not found"})
    return r


@router.get("/v1/agents/{aid}")
def get_agent(aid: str, ctx: AuthCtx = Depends(require_owner)) -> dict:
    org_id = ctx.org_id
    with _graph.engine.connect() as c:
        r = _get_agent(c, org_id, aid)
        base = _summary(c, r, org_id)
    base["scope_updated_at"] = r.scope_updated_at.isoformat() if r.scope_updated_at else None
    base["keys"] = [{"id": "primary", "prefix": r.key_prefix or "gn_live_…", "name": "primary",
                     "created_at": r.created_at.isoformat() if r.created_at else None,
                     "last_used_at": r.key_last_used_at.isoformat() if r.key_last_used_at else None}]
    return base


class ScopeUpdate(BaseModel):
    scope: dict


@router.patch("/v1/agents/{aid}/scope")
def edit_scope(aid: str, body: ScopeUpdate,
               ctx: AuthCtx = Depends(require_owner)) -> dict:
    org_id = ctx.org_id
    scope = _scope(body.scope)
    with _graph.engine.begin() as c:
        _get_agent(c, org_id, aid)
        ver = c.execute(text(
            "update agent_registry set scope=cast(:sc as jsonb), scope_version=scope_version+1, "
            "scope_updated_at=now() where org_id=:o and agent_id=:a returning scope_version"),
            {"sc": json.dumps(scope), "o": org_id, "a": aid}).scalar()
    return {"agent_id": aid, "scope": scope, "version": int(ver)}


class WebhookUpdate(BaseModel):
    webhook_url: str | None = None      # null/empty → clear (agent reverts to poll-only)


@router.patch("/v1/agents/{aid}/webhook")
def set_webhook(aid: str, body: WebhookUpdate,
                ctx: AuthCtx = Depends(require_owner)) -> dict:
    """Register / rotate / clear an agent's proactive-push webhook. Setting a URL mints a fresh
    signing secret returned ONCE (rotating the URL rotates the secret). Empty → poll-only."""
    org_id = ctx.org_id
    url = _clean_webhook_url(body.webhook_url)
    with _graph.engine.begin() as c:
        _get_agent(c, org_id, aid)
        if url is None:
            c.execute(text("update agent_registry set webhook_url=null, webhook_secret=null "
                           "where org_id=:o and agent_id=:a"), {"o": org_id, "a": aid})
            return {"agent_id": aid, "webhook_url": None, "webhook_configured": False}
        secret = _mint_webhook_secret()
        c.execute(text("update agent_registry set webhook_url=:u, webhook_secret=:s "
                       "where org_id=:o and agent_id=:a"),
                  {"u": url, "s": secret, "o": org_id, "a": aid})
    from genios_engine.platform.audit import record
    record(org_id, "config_changed", actor_type="user", target_type="agent", target_id=aid,
           metadata={"event": "webhook_set"})
    return {"agent_id": aid, "webhook_url": url, "webhook_secret": secret, "webhook_configured": True,
            "warning": "Copy this signing secret now — it is shown only once. Verify the X-Genios-Signature "
                       "header: sha256 = HMAC-SHA256 hex of the raw request body using this secret."}


class KeyRotate(BaseModel):
    name: str | None = None
    revoke_old: bool = False


@router.post("/v1/agents/{aid}/keys")
def rotate_key(aid: str, body: KeyRotate,
               ctx: AuthCtx = Depends(require_owner)) -> dict:
    org_id = ctx.org_id
    raw, prefix, key_hash = _mint_key()
    with _graph.engine.begin() as c:
        old = _get_agent(c, org_id, aid)
        old_hash = c.execute(text("select key_hash from agent_registry where org_id=:o and agent_id=:a"),
                             {"o": org_id, "a": aid}).scalar()
        c.execute(text("update agent_registry set key_hash=:kh, key_prefix=:kp, key_last_used_at=null "
                       "where org_id=:o and agent_id=:a"),
                  {"kh": key_hash, "kp": prefix, "o": org_id, "a": aid})
        # keep api_keys in sync (that's what /v1/* auth reads); deactivate old rows, add the new one.
        c.execute(text("update api_keys set is_active=false where org_id=:o and agent_id=:a"),
                  {"o": org_id, "a": aid})
        c.execute(text("insert into api_keys (id, org_id, key_hash, key_prefix, name, agent_id, "
                       "scopes, is_active) values (:i,:o,:kh,:kp,:nm,:a,:sc,true)"),
                  {"i": new_id("key"), "o": org_id, "kh": key_hash, "kp": prefix, "nm": aid,
                   "a": aid, "sc": _DEFAULT_ACTIONS})
    if old_hash:
        invalidate_key_cache(old_hash)          # old key must stop working immediately (bust 60s cache)
    return {"agent_id": aid, "key": raw, "key_prefix": prefix,
            "warning": "New key issued — the previous key no longer works. Copy this now."}


@router.delete("/v1/agents/{aid}")
def archive_agent(aid: str, ctx: AuthCtx = Depends(require_owner)) -> dict:
    org_id = ctx.org_id
    with _graph.engine.begin() as c:
        _get_agent(c, org_id, aid)
        hashes = [r.key_hash for r in c.execute(text(
            "select key_hash from api_keys where org_id=:o and agent_id=:a and is_active"),
            {"o": org_id, "a": aid})]
        c.execute(text("update agent_registry set status='archived' where org_id=:o and agent_id=:a"),
                  {"o": org_id, "a": aid})
        # revoke on the /v1/* path too: deactivate its api_keys rows (events_store.verify already
        # rejects archived on the agent-events path).
        c.execute(text("update api_keys set is_active=false where org_id=:o and agent_id=:a"),
                  {"o": org_id, "a": aid})
    for h in hashes:
        invalidate_key_cache(h)                 # bust the 60s auth cache so revocation is immediate
    return {"agent_id": aid, "status": "archived"}


@router.get("/v1/agents/{aid}/audit")
def agent_audit(aid: str, limit: int = 50,
                ctx: AuthCtx = Depends(require_owner)) -> dict:
    org_id = ctx.org_id
    with _graph.engine.connect() as c:
        _get_agent(c, org_id, aid)
        rows = c.execute(text(
            "select action_taken, target_hint, result, occurred_at from agent_events "
            "where org_id=:o and agent_id=:a order by occurred_at desc limit :l"),
            {"o": org_id, "a": aid, "l": max(1, min(int(limit), 200))}).fetchall()
    calls = []
    for r in rows:
        th = r.target_hint if isinstance(r.target_hint, dict) else json.loads(r.target_hint or "{}")
        calls.append({"entity": th.get("entity") or r.action_taken,
                      "at": r.occurred_at.isoformat() if r.occurred_at else None,
                      "latency_ms": None, "blocked": r.result == "blocked",
                      "scope_source": "agent", "tokens": None, "cache_hit": False})
    return {"calls": calls}


@router.get("/v1/agents/{aid}/grants")
def get_grants(aid: str, ctx: AuthCtx = Depends(require_owner)) -> dict:
    org_id = ctx.org_id
    with _graph.engine.connect() as c:
        _get_agent(c, org_id, aid)
        granted = [dict(r) for r in c.execute(text(
            "select grant_id, account_id, account_kind, tool, label, granted_at from agent_grants "
            "where org_id=:o and agent_id=:a"), {"o": org_id, "a": aid}).mappings()]
        granted_ids = {g["account_id"] for g in granted}
        # available accounts = the org's connected sources (OAuth connections + workspace accounts)
        avail = []
        for r in c.execute(text(
                "select connection_id, source_type, external_account_id "
                "from connections where org_id=:o and status='connected'"), {"o": org_id}):
            avail.append({"account_id": r.connection_id, "account_kind": "oauth",
                          "tool": r.source_type, "label": r.external_account_id or r.source_type,
                          "last_event_at": None, "granted": r.connection_id in granted_ids})
    for g in granted:
        g["granted_at"] = g["granted_at"].isoformat() if g["granted_at"] else None
    return {"agent_id": aid, "grants": granted, "available_accounts": avail}


class GrantsSet(BaseModel):
    accounts: list[dict]


@router.put("/v1/agents/{aid}/grants")
def set_grants(aid: str, body: GrantsSet,
               ctx: AuthCtx = Depends(require_owner)) -> dict:
    org_id = ctx.org_id
    with _graph.engine.begin() as c:
        _get_agent(c, org_id, aid)
        c.execute(text("delete from agent_grants where org_id=:o and agent_id=:a"),
                  {"o": org_id, "a": aid})
        n = 0
        for acc in body.accounts:
            c.execute(text(
                "insert into agent_grants (grant_id, org_id, agent_id, account_id, account_kind) "
                "values (:g,:o,:a,:acc,:k) on conflict (org_id, agent_id, account_id) do nothing"),
                {"g": new_id("grant"), "o": org_id, "a": aid,
                 "acc": acc.get("account_id"), "k": acc.get("account_kind") or "oauth"})
            n += 1
    return {"agent_id": aid, "granted_count": n}
