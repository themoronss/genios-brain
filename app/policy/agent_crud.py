"""
Agent Registry — DB helpers (separated from the FastAPI route file to keep
[agent_registry.py] under the <300-line guideline).

Each helper is a small, single-purpose SQL transaction. All callers commit/rollback
in the route layer.
"""

from __future__ import annotations

import json
import secrets
from typing import Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.deps import _hash_key
from app.plan_enforcer import get_org_plan
from app.policy import scope_filter, scope_loader


def enforce_plan_limit(db: Session, org_id: str) -> None:
    """Raise ValueError(detail) if org has hit its agent-count limit."""
    plan = get_org_plan(db, org_id)
    max_agents = plan["config"]["max_agent_ids"]
    count = db.execute(
        text("""
            SELECT COUNT(*) FROM registered_agents
            WHERE org_id = :o AND status != 'archived' AND agent_id != 'default_agent'
        """),
        {"o": org_id},
    ).scalar() or 0
    if count >= max_agents:
        raise ValueError({
            "error": "PLAN_LIMIT",
            "message": f"Max {max_agents} agents on {plan['tier']} plan.",
            "current_count": count,
            "max_allowed": max_agents,
            "upgrade_required": True,
        })


def mint_key(
    db: Session, org_id: str, agent_uuid: str, scope_id: int, name: str
) -> tuple[str, str]:
    """Insert an api_keys row bound to (agent, scope). Returns (raw_key, prefix)."""
    raw = f"gn_live_{secrets.token_urlsafe(32)}"
    h = _hash_key(raw)
    prefix = raw[:16] + "..."
    db.execute(
        text("""
            INSERT INTO api_keys (org_id, key_hash, key_prefix, name, agent_uuid, scope_id, is_active, created_at)
            VALUES (:org, :h, :p, :n, :a, :s, TRUE, NOW())
        """),
        {"org": org_id, "h": h, "p": prefix, "n": name, "a": agent_uuid, "s": scope_id},
    )
    return raw, prefix


def insert_agent(
    db: Session, org_id: str, agent_id: str, name: str, description: Optional[str]
) -> str:
    return db.execute(
        text("""
            INSERT INTO registered_agents (org_id, agent_id, name, description, status, created_at)
            VALUES (:o, :a, :n, :d, 'active', NOW())
            RETURNING id
        """),
        {"o": org_id, "a": agent_id, "n": name, "d": description},
    ).fetchone()[0]


def insert_scope(db: Session, agent_uuid: str, org_id: str, policy: dict, version: int = 1) -> int:
    return db.execute(
        text("""
            INSERT INTO agent_scopes (agent_uuid, org_id, version, policy_json, is_active)
            VALUES (:a, :o, :v, CAST(:p AS jsonb), TRUE)
            RETURNING id
        """),
        {"a": agent_uuid, "o": org_id, "v": version, "p": json.dumps(policy)},
    ).fetchone()[0]


def replace_scope(db: Session, agent_uuid: str, org_id: str, policy: dict) -> tuple[int, int]:
    """Mark old scopes inactive, insert a new active version. Returns (id, version)."""
    db.execute(
        text("UPDATE agent_scopes SET is_active = FALSE WHERE agent_uuid = :a AND is_active = TRUE"),
        {"a": agent_uuid},
    )
    row = db.execute(
        text("""
            INSERT INTO agent_scopes (agent_uuid, org_id, version, policy_json, is_active)
            VALUES (:a, :o,
                    (SELECT COALESCE(MAX(version),0)+1 FROM agent_scopes WHERE agent_uuid = :a),
                    CAST(:p AS jsonb), TRUE)
            RETURNING id, version
        """),
        {"a": agent_uuid, "o": org_id, "p": json.dumps(policy)},
    ).fetchone()
    db.execute(
        text("UPDATE api_keys SET scope_id = :s WHERE agent_uuid = :a AND is_active = TRUE"),
        {"s": row[0], "a": agent_uuid},
    )
    db.execute(
        text("UPDATE registered_agents SET edited_at = NOW() WHERE id = :a"),
        {"a": agent_uuid},
    )
    return row[0], row[1]


def revoke_keys_for_agent(db: Session, agent_uuid: str) -> list[str]:
    """Mark all keys for this agent inactive. Returns the list of key_hashes
    so the caller can invalidate Redis cache after commit."""
    hashes = [r[0] for r in db.execute(
        text("SELECT key_hash FROM api_keys WHERE agent_uuid = :a AND is_active = TRUE"),
        {"a": agent_uuid},
    ).fetchall()]
    db.execute(
        text("UPDATE api_keys SET is_active = FALSE WHERE agent_uuid = :a"),
        {"a": agent_uuid},
    )
    return hashes


def archive(db: Session, agent_uuid: str) -> None:
    db.execute(
        text("UPDATE registered_agents SET status = 'archived', edited_at = NOW() WHERE id = :a"),
        {"a": agent_uuid},
    )


def find_agent(db: Session, org_id: str, slug: str):
    return db.execute(
        text("""
            SELECT ra.id::text, ra.name, ra.description, ra.status, ra.created_at,
                   asc_.id AS scope_id, asc_.policy_json, asc_.version, asc_.created_at AS scope_at
            FROM registered_agents ra
            LEFT JOIN agent_scopes asc_ ON asc_.agent_uuid = ra.id AND asc_.is_active = TRUE
            WHERE ra.org_id = :o AND ra.agent_id = :a AND ra.status != 'archived'
        """),
        {"o": org_id, "a": slug},
    ).fetchone()


def list_keys(db: Session, org_id: str, agent_uuid: str):
    return db.execute(
        text("""
            SELECT id::text, key_prefix, name, created_at, last_used_at
            FROM api_keys WHERE org_id = :o AND agent_uuid = :a AND is_active = TRUE
            ORDER BY created_at ASC
        """),
        {"o": org_id, "a": agent_uuid},
    ).fetchall()


def list_agents_with_counters(db: Session, org_id: str):
    return db.execute(
        text("""
            SELECT ra.agent_id, ra.name, ra.description, ra.status, ra.created_at,
                   ra.id::text AS agent_uuid,
                   asc_.policy_json, asc_.version,
                   (SELECT COUNT(*) FROM context_calls cc
                      WHERE cc.org_id = ra.org_id AND cc.agent_id = ra.agent_id
                        AND cc.called_at > NOW() - INTERVAL '24 hours') AS calls_24h,
                   (SELECT COUNT(*) FROM context_calls cc
                      WHERE cc.org_id = ra.org_id AND cc.agent_id = ra.agent_id
                        AND cc.scope_blocked = TRUE
                        AND cc.called_at > NOW() - INTERVAL '24 hours') AS blocked_24h,
                   -- Phase 11.5: at-a-glance tool list per agent.
                   -- Returns array of {source, provider, last_event_at} for the
                   -- list page so the customer can SEE which tools each agent
                   -- has without opening the drawer.
                   (
                     SELECT COALESCE(jsonb_agg(jsonb_build_object(
                                'source',        cc.source,
                                'provider',      cc.metadata->>'provider',
                                'account',       COALESCE(
                                                    cc.metadata->>'mailbox_address',
                                                    cc.metadata->>'phone_number',
                                                    cc.metadata->>'account'),
                                'last_event_at', cc.last_event_at
                             ) ORDER BY cc.created_at), '[]'::jsonb)
                     FROM connector_credentials cc
                     WHERE cc.agent_uuid = ra.id AND cc.is_active = TRUE
                   ) AS connectors
            FROM registered_agents ra
            LEFT JOIN agent_scopes asc_ ON asc_.agent_uuid = ra.id AND asc_.is_active = TRUE
            WHERE ra.org_id = :o AND ra.status != 'archived'
            ORDER BY ra.agent_id = 'default_agent' DESC, ra.created_at ASC
        """),
        {"o": org_id},
    ).fetchall()


def recent_audit(db: Session, org_id: str, slug: str, limit: int):
    return db.execute(
        text("""
            SELECT entity_name, called_at, latency_ms, scope_blocked, scope_source,
                   tokens_used, cache_hit
            FROM context_calls
            WHERE org_id = :o AND agent_id = :a
            ORDER BY called_at DESC LIMIT :l
        """),
        {"o": org_id, "a": slug, "l": limit},
    ).fetchall()
