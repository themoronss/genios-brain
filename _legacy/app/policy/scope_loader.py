"""
Scope loader — resolves a key hash → AuthCtx (org, agent, scope policy).

Cached in Redis (60s) alongside the existing api_key cache so /v1/context
takes one Redis hit, not two. On cache miss, single SQL JOIN walks
api_keys → registered_agents → agent_scopes.

Brain framing: this is the credential-time identity gate. Every read
endpoint that wants scope enforcement asks for `get_auth_ctx()`; the
loader makes that lookup near-free.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, asdict
from typing import Optional

from sqlalchemy import text

logger = logging.getLogger(__name__)

# Redis cache TTL — matches existing api_key cache so the two stay in sync.
SCOPE_CACHE_TTL = 60


@dataclass
class AuthCtx:
    """Resolved identity for a Bearer key. Carried on request.state.auth."""
    org_id: str
    agent_uuid: Optional[str] = None       # registered_agents.id
    agent_id: Optional[str] = None         # registered_agents.agent_id (slug)
    scope_id: Optional[int] = None
    policy: Optional[dict] = None
    scope_source: str = "legacy"           # 'agent' | 'default' | 'legacy'
    plan_status: str = "active"

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "AuthCtx":
        return cls(**d)


def _cache_key(hashed: str) -> str:
    return f"scope:{hashed}"


def invalidate(hashed: str) -> None:
    """Drop cached AuthCtx + api_key cache row. Called on key revoke / scope
    edit / agent archive. Both caches are flushed because deps.py stores
    AuthCtx alongside the api_key resolution blob."""
    try:
        from app.redis_client import redis_client
        redis_client.delete(_cache_key(hashed))
        redis_client.delete(f"api_key:{hashed}")
    except Exception:
        pass


def invalidate_for_agent(db, agent_uuid: str) -> None:
    """Invalidate all keys bound to an agent (used after scope edit)."""
    try:
        from app.redis_client import redis_client
        rows = db.execute(
            text("SELECT key_hash FROM api_keys WHERE agent_uuid = :aid AND is_active = TRUE"),
            {"aid": agent_uuid},
        ).fetchall()
        for r in rows:
            redis_client.delete(_cache_key(r[0]))
            redis_client.delete(f"api_key:{r[0]}")
    except Exception as e:
        logger.warning(f"scope cache invalidate_for_agent failed: {e}")


def resolve(db, hashed_key: str) -> Optional[AuthCtx]:
    """
    Look up an AuthCtx for a hashed bearer token.

    Priority:
      1. Redis cache (60s TTL).
      2. api_keys table — joins registered_agents + agent_scopes.
      3. Legacy: orgs.api_key_hash (or plain api_key) — falls back to the
         org's default_agent if one is bound.

    Returns None on miss. Caller decides whether to 401.
    """
    try:
        from app.redis_client import redis_client
        cached = redis_client.get(_cache_key(hashed_key))
        if cached:
            try:
                payload = json.loads(cached if isinstance(cached, str) else cached.decode())
                if payload.get("__miss__"):
                    return None
                return AuthCtx.from_dict(payload)
            except Exception:
                pass
    except Exception:
        pass

    ctx = _resolve_from_db(db, hashed_key)
    try:
        from app.redis_client import redis_client
        if ctx is None:
            redis_client.setex(_cache_key(hashed_key), 30, json.dumps({"__miss__": True}))
        else:
            redis_client.setex(
                _cache_key(hashed_key),
                SCOPE_CACHE_TTL,
                json.dumps(ctx.to_dict(), default=str),
            )
    except Exception:
        pass
    return ctx


def _resolve_from_db(db, hashed_key: str) -> Optional[AuthCtx]:
    """The actual SQL — single round-trip via UNION of the three lookup paths."""

    # Path 1: api_keys (additional or backfilled keys, fully bound)
    row = db.execute(
        text("""
            SELECT
                ak.org_id::text          AS org_id,
                ak.agent_uuid::text      AS agent_uuid,
                ra.agent_id              AS agent_id,
                ak.scope_id              AS scope_id,
                COALESCE(o.plan_status, 'active') AS plan_status,
                CASE
                    WHEN ak.agent_uuid IS NULL THEN 'legacy'
                    WHEN ra.agent_id = 'default_agent' THEN 'default'
                    ELSE 'agent'
                END                       AS scope_source,
                asc_.policy_json          AS policy_json
            FROM api_keys ak
            JOIN orgs o ON o.id = ak.org_id
            LEFT JOIN registered_agents ra ON ra.id = ak.agent_uuid
            LEFT JOIN agent_scopes asc_ ON asc_.id = ak.scope_id
            WHERE ak.key_hash = :h AND ak.is_active = TRUE
            LIMIT 1
        """),
        {"h": hashed_key},
    ).fetchone()

    if row:
        policy = _parse_policy(row.policy_json)
        return AuthCtx(
            org_id=row.org_id,
            agent_uuid=row.agent_uuid,
            agent_id=row.agent_id,
            scope_id=row.scope_id,
            policy=policy,
            scope_source=row.scope_source,
            plan_status=row.plan_status,
        )

    # Path 2: orgs.api_key_hash (legacy primary key — bind to default_agent
    # if one was provisioned via mig 086 backfill)
    row = db.execute(
        text("""
            SELECT
                o.id::text                  AS org_id,
                o.default_agent_id::text    AS agent_uuid,
                ra.agent_id                 AS agent_id,
                asc_.id                     AS scope_id,
                asc_.policy_json            AS policy_json,
                COALESCE(o.plan_status, 'active') AS plan_status
            FROM orgs o
            LEFT JOIN registered_agents ra ON ra.id = o.default_agent_id
            LEFT JOIN agent_scopes asc_ ON asc_.agent_uuid = o.default_agent_id AND asc_.is_active = TRUE
            WHERE o.api_key_hash = :h
            LIMIT 1
        """),
        {"h": hashed_key},
    ).fetchone()

    if row:
        return AuthCtx(
            org_id=row.org_id,
            agent_uuid=row.agent_uuid,
            agent_id=row.agent_id,
            scope_id=row.scope_id,
            policy=_parse_policy(row.policy_json),
            scope_source="default" if row.agent_uuid else "legacy",
            plan_status=row.plan_status,
        )

    return None


def _parse_policy(raw) -> Optional[dict]:
    """policy_json can come back as dict (asyncpg) or str (psycopg). Normalise."""
    if raw is None:
        return None
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, (bytes, bytearray)):
        raw = raw.decode()
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except Exception:
            return None
    return None
