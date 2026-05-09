"""
Agent Registry — REST surface (Agent Registry PRD §08, §12).

Identity is server-derived from the bearer key. Clients never declare it.
Heavy lifting lives in [app/policy/agent_crud.py]; this file is thin routing.

    POST   /v1/agents                  register agent + scope + mint key
    GET    /v1/agents                  list agents with 24h counters
    GET    /v1/agents/me               whoami — server-derived identity
    GET    /v1/agents/{slug}           detail (scope, keys)
    GET    /v1/agents/{slug}/audit     recent calls (Activity tab)
    PATCH  /v1/agents/{slug}/scope     versioned scope edit
    POST   /v1/agents/{slug}/keys      rotate / mint
    DELETE /v1/agents/{slug}           archive (slug becomes immutable)
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, validator
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.deps import get_auth_ctx, get_db, verify_api_key
from app.policy import agent_crud, connector_crud, grants_crud, scope_filter, scope_loader, trust_crud
from app.policy.scope_loader import AuthCtx

logger = logging.getLogger(__name__)
router = APIRouter()

_SLUG_RE = re.compile(r"^[a-z0-9_]{2,40}$")


# ── Schemas ──────────────────────────────────────────────────────────────────
class ScopePolicy(BaseModel):
    connectors:      Optional[list[str]] = None
    segments:        Optional[list[str]] = None
    fact_types:      Optional[list[str]] = None
    exclude_tags:    list[str] = []
    max_age_days:    int = 365
    min_confidence:  float = 0.0
    # Per-agent data isolation: 'own' = sees only its own ingested data
    # (default for scoped agents), 'all' = master view (default_agent only).
    data_visibility: str = "own"


class CreateAgentRequest(BaseModel):
    agent_id:    str
    name:        Optional[str] = None
    description: Optional[str] = None
    scope:       ScopePolicy = ScopePolicy()

    @validator("agent_id")
    def _v_slug(cls, v):
        v = (v or "").strip().lower()
        if not _SLUG_RE.match(v):
            raise ValueError("agent_id must match ^[a-z0-9_]{2,40}$")
        if v == "default_agent":
            raise ValueError("'default_agent' is reserved")
        return v


class EditScopeRequest(BaseModel):
    scope: ScopePolicy


class RotateKeyRequest(BaseModel):
    name: Optional[str] = None
    revoke_old: bool = False


def _http(detail, status=400):
    return HTTPException(status_code=status, detail=detail)


# ── Routes ───────────────────────────────────────────────────────────────────
@router.post("/v1/agents", status_code=201)
def create_agent(
    req: CreateAgentRequest,
    db: Session = Depends(get_db),
    org_id: str = Depends(verify_api_key),
):
    try:
        agent_crud.enforce_plan_limit(db, org_id)
    except ValueError as e:
        raise _http(e.args[0], 403)

    if agent_crud.find_agent(db, org_id, req.agent_id):
        raise _http({"error": "AGENT_EXISTS", "agent_id": req.agent_id}, 409)

    try:
        agent_uuid = agent_crud.insert_agent(db, org_id, req.agent_id, req.name or req.agent_id, req.description)
        policy = scope_filter.normalize(req.scope.dict())
        scope_id = agent_crud.insert_scope(db, str(agent_uuid), org_id, policy)
        raw_key, prefix = agent_crud.mint_key(db, org_id, str(agent_uuid), scope_id, f"{req.agent_id} key")
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"create_agent failed: {e}")
        raise _http("Agent creation failed", 500)

    try:
        from app.core.analytics import capture
        capture(org_id, "agent_registered", {"agent_id": req.agent_id})
    except Exception:
        pass

    return {
        "agent_id": req.agent_id,
        "name": req.name or req.agent_id,
        "description": req.description,
        "scope": policy,
        "key": raw_key,
        "key_prefix": prefix,
        "warning": "Store this key securely — it will not be shown again.",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/v1/agents")
def list_agents(db: Session = Depends(get_db), org_id: str = Depends(verify_api_key)):
    rows = agent_crud.list_agents_with_counters(db, org_id)
    return {
        "agents": [
            {
                "agent_id": r.agent_id,
                "name": r.name,
                "description": r.description,
                "status": r.status,
                "scope": scope_filter.normalize(scope_loader._parse_policy(r.policy_json)),
                "scope_version": r.version,
                "calls_24h": int(r.calls_24h or 0),
                "blocked_24h": int(r.blocked_24h or 0),
                "created_at": r.created_at.isoformat() if r.created_at else None,
                "is_default": r.agent_id == "default_agent",
                # Phase 11.5: tools connected per agent (visible on list page)
                "connectors": list(r.connectors or []),
            }
            for r in rows
        ],
        "count": len(rows),
    }


@router.get("/v1/agents/me")
def whoami(
    auth: AuthCtx = Depends(get_auth_ctx),
    db: Session = Depends(get_db),
):
    """Server-derived identity + scope + the agent's own connected channels.

    `own_channels` is critical for outreach bots — agent needs to know its
    own email/phone (e.g. "I am sales-bot@inkboxmail.com") so it doesn't
    treat itself as the counterparty when reasoning about a thread.
    """
    own_channels = []
    if auth.agent_uuid:
        rows = db.execute(
            text("""
                SELECT source, metadata FROM connector_credentials
                WHERE agent_uuid = :a AND is_active = TRUE
                ORDER BY source
            """),
            {"a": auth.agent_uuid},
        ).fetchall()
        for r in rows:
            md = r[1] or {}
            entry = {"source": r[0]}
            if md.get("mailbox_address"):
                entry["address"] = md["mailbox_address"]
            if md.get("phone_number"):
                entry["number"] = md["phone_number"]
            own_channels.append(entry)
    return {
        "org_id": auth.org_id,
        "agent_id": auth.agent_id,
        "scope_source": auth.scope_source,
        "scope": scope_filter.normalize(auth.policy),
        "own_channels": own_channels,
    }


@router.get("/v1/agents/{slug}")
def get_agent(slug: str, db: Session = Depends(get_db), org_id: str = Depends(verify_api_key)):
    row = agent_crud.find_agent(db, org_id, slug)
    if not row:
        raise _http({"error": "AGENT_NOT_FOUND"}, 404)
    keys = agent_crud.list_keys(db, org_id, row[0])
    return {
        "agent_id": slug,
        "name": row.name,
        "description": row.description,
        "status": row.status,
        "scope": scope_filter.normalize(scope_loader._parse_policy(row.policy_json)),
        "scope_version": row.version,
        "scope_updated_at": row.scope_at.isoformat() if row.scope_at else None,
        "keys": [
            {
                "id": k.id, "prefix": k.key_prefix, "name": k.name,
                "created_at": k.created_at.isoformat() if k.created_at else None,
                "last_used_at": k.last_used_at.isoformat() if k.last_used_at else None,
            } for k in keys
        ],
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


@router.patch("/v1/agents/{slug}/scope")
def edit_scope(
    slug: str, req: EditScopeRequest,
    db: Session = Depends(get_db), org_id: str = Depends(verify_api_key),
):
    row = agent_crud.find_agent(db, org_id, slug)
    if not row:
        raise _http({"error": "AGENT_NOT_FOUND"}, 404)
    if slug == "default_agent":
        raise _http({"error": "CANNOT_EDIT_DEFAULT", "message": "Default agent has full scope and is read-only."}, 400)

    agent_uuid = row[0]
    policy = scope_filter.normalize(req.scope.dict())
    try:
        _, version = agent_crud.replace_scope(db, agent_uuid, org_id, policy)
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"edit_scope failed: {e}")
        raise _http("Scope edit failed", 500)
    scope_loader.invalidate_for_agent(db, agent_uuid)
    return {"agent_id": slug, "scope": policy, "version": version}


@router.post("/v1/agents/{slug}/keys", status_code=201)
def rotate_key(
    slug: str, req: RotateKeyRequest,
    db: Session = Depends(get_db), org_id: str = Depends(verify_api_key),
):
    row = agent_crud.find_agent(db, org_id, slug)
    if not row:
        raise _http({"error": "AGENT_NOT_FOUND"}, 404)
    agent_uuid, scope_id = row[0], row.scope_id

    try:
        old_hashes: list[str] = []
        if req.revoke_old:
            old_hashes = agent_crud.revoke_keys_for_agent(db, agent_uuid)
        raw_key, prefix = agent_crud.mint_key(db, org_id, agent_uuid, scope_id, req.name or f"{slug} key")
        db.commit()
        for h in old_hashes:
            scope_loader.invalidate(h)
    except Exception as e:
        db.rollback()
        logger.error(f"rotate_key failed: {e}")
        raise _http("Key rotation failed", 500)

    return {
        "agent_id": slug, "key": raw_key, "key_prefix": prefix,
        "warning": "Store this key securely — it will not be shown again.",
    }


@router.delete("/v1/agents/{slug}")
def archive_agent(slug: str, db: Session = Depends(get_db), org_id: str = Depends(verify_api_key)):
    if slug == "default_agent":
        raise _http({"error": "CANNOT_ARCHIVE_DEFAULT"}, 400)
    row = agent_crud.find_agent(db, org_id, slug)
    if not row:
        raise _http({"error": "AGENT_NOT_FOUND"}, 404)
    agent_uuid = row[0]
    try:
        old_hashes = agent_crud.revoke_keys_for_agent(db, agent_uuid)
        agent_crud.archive(db, agent_uuid)
        db.commit()
        for h in old_hashes:
            scope_loader.invalidate(h)
    except Exception as e:
        db.rollback()
        logger.error(f"archive_agent failed: {e}")
        raise _http("Archive failed", 500)
    return {"agent_id": slug, "status": "archived"}


# ── Per-agent grants (Phase 12 — workspace tools, agent picks subset) ───────
# Tools are connected at workspace level on the Integrations page. Each
# connection produces an "account". Agents grant themselves access to a
# subset of those accounts; sync runs at workspace level and the grant
# table gates what each agent reads via scope_filter.interaction_clauses.

class GrantsReplaceRequest(BaseModel):
    accounts: list[dict] = []
    # Each: {"account_id": "<uuid>", "account_kind": "oauth" | "connector"}


@router.get("/v1/agents/{slug}/grants")
def list_grants(slug: str, db: Session = Depends(get_db), org_id: str = Depends(verify_api_key)):
    row = agent_crud.find_agent(db, org_id, slug)
    if not row:
        raise _http({"error": "AGENT_NOT_FOUND"}, 404)
    granted = grants_crud.list_for_agent(db, org_id, row[0])
    workspace = grants_crud.list_workspace_accounts(db, org_id)
    granted_keys = {(g.account_id, g.account_kind) for g in granted}
    return {
        "agent_id": slug,
        "grants": [
            {
                "grant_id":     g.grant_id,
                "account_id":   g.account_id,
                "account_kind": g.account_kind,
                "tool":         g.tool,
                "label":        g.account_label,
                "granted_at":   g.granted_at.isoformat() if g.granted_at else None,
            } for g in granted
        ],
        # Available accounts the customer can toggle (workspace-wide)
        "available_accounts": [
            {
                "account_id":   a[0],
                "account_kind": a[1],
                "tool":         a[2],
                "label":        a[3],
                "last_event_at": a[4].isoformat() if a[4] else None,
                "granted":      (a[0], a[1]) in granted_keys,
            } for a in workspace
        ],
    }


@router.put("/v1/agents/{slug}/grants")
def replace_grants(
    slug: str,
    req: GrantsReplaceRequest,
    db: Session = Depends(get_db),
    org_id: str = Depends(verify_api_key),
):
    """Atomic replace — clears existing grants, sets new list. Master agent's
    grants are ignored (master sees everything via data_visibility='all')."""
    row = agent_crud.find_agent(db, org_id, slug)
    if not row:
        raise _http({"error": "AGENT_NOT_FOUND"}, 404)
    try:
        count = grants_crud.replace_grants(db, org_id, row[0], req.accounts)
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"replace_grants failed: {e}")
        raise _http("Grants update failed", 500)
    return {"agent_id": slug, "granted_count": count}


# ── Per-agent trust list (Phase 6.5 — instruction senders) ──────────────────
class TrustAddRequest(BaseModel):
    contact_id:  Optional[str] = None
    match_email: Optional[str] = None
    match_phone: Optional[str] = None
    note:        Optional[str] = None


@router.get("/v1/agents/{slug}/trust")
def list_trust(slug: str, db: Session = Depends(get_db), org_id: str = Depends(verify_api_key)):
    row = agent_crud.find_agent(db, org_id, slug)
    if not row:
        raise _http({"error": "AGENT_NOT_FOUND"}, 404)
    rows = trust_crud.list_for_agent(db, org_id, row[0])
    return {"trust": [
        {
            "id": r[0],
            "contact_id": r[1],
            "match_email": r[2],
            "match_phone": r[3],
            "note": r[4],
            "created_at": r[5].isoformat() if r[5] else None,
            "contact_name": r[6],
            "contact_email": r[7],
        } for r in rows
    ]}


@router.post("/v1/agents/{slug}/trust", status_code=201)
def add_trust(
    slug: str,
    req: TrustAddRequest,
    db: Session = Depends(get_db),
    org_id: str = Depends(verify_api_key),
):
    row = agent_crud.find_agent(db, org_id, slug)
    if not row:
        raise _http({"error": "AGENT_NOT_FOUND"}, 404)
    # Exactly one match mode (DB CHECK enforces it; pre-check for nicer error)
    modes = [bool(req.contact_id), bool(req.match_email), bool(req.match_phone)]
    if sum(modes) != 1:
        raise _http({"error": "INVALID_MATCH",
                     "message": "Provide exactly one of: contact_id, match_email, match_phone."}, 400)
    try:
        tid = trust_crud.add(
            db, org_id, row[0],
            contact_id=req.contact_id,
            match_email=req.match_email,
            match_phone=req.match_phone,
            note=req.note,
        )
        db.commit()
    except Exception as e:
        db.rollback()
        if "uq_agent_trust" in str(e) or "duplicate key" in str(e):
            raise _http({"error": "TRUST_EXISTS"}, 409)
        logger.error(f"add_trust failed: {e}")
        raise _http("Trust add failed", 500)
    return {"id": tid, "agent_id": slug,
            "match_email": req.match_email, "match_phone": req.match_phone,
            "contact_id": req.contact_id, "note": req.note}


@router.delete("/v1/agents/{slug}/trust/{trust_id}")
def remove_trust(
    slug: str, trust_id: str,
    db: Session = Depends(get_db), org_id: str = Depends(verify_api_key),
):
    row = agent_crud.find_agent(db, org_id, slug)
    if not row:
        raise _http({"error": "AGENT_NOT_FOUND"}, 404)
    ok = trust_crud.remove(db, org_id, row[0], trust_id)
    if not ok:
        raise _http({"error": "TRUST_NOT_FOUND"}, 404)
    db.commit()
    return {"id": trust_id, "removed": True}


@router.get("/v1/agents/{slug}/audit")
def agent_audit(
    slug: str,
    limit: int = 50,
    db: Session = Depends(get_db), org_id: str = Depends(verify_api_key),
):
    limit = max(1, min(200, int(limit)))
    rows = agent_crud.recent_audit(db, org_id, slug, limit)
    return {
        "calls": [
            {
                "entity": r.entity_name,
                "at": r.called_at.isoformat() if r.called_at else None,
                "latency_ms": r.latency_ms,
                "blocked": bool(r.scope_blocked),
                "scope_source": r.scope_source,
                "tokens": r.tokens_used,
                "cache_hit": bool(r.cache_hit),
            }
            for r in rows
        ]
    }
