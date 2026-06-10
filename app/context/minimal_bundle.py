"""
Minimal real bundle — the cold-path fallback for /v1/context.

When the pre-computed bundle is missing (new contact, first pull, cache
eviction), we must still return *real* intelligence to the agent, not an
empty degraded pack. This path runs one joined query and returns the
essentials an agent needs to act: who they are, relationship stage, and
the last few interactions.

Target: <150ms p95 single DB round-trip. The full bundle is enqueued to
Celery in parallel so the next pull upgrades to the rich pre-computed shape.
"""

from __future__ import annotations

from typing import Dict, Optional
from sqlalchemy import text
from sqlalchemy.orm import Session


def build_minimal_bundle(
    db: Session,
    org_id: str,
    entity: str,
    requesting_agent_uuid: Optional[str] = None,
    data_visibility: str = "all",
) -> Optional[Dict]:
    """Return a real-but-small bundle for `entity` using a single DB round-trip.

    Matches the shape of the full pre-computed bundle so agents consume one schema.
    Returns None if the entity is unknown in this org.

    Phase 7: when caller is a scoped agent (data_visibility='own'), the inner
    interactions sub-select filters by `agent_uuid` so the agent only sees
    its own ingested interactions plus untagged (workspace-level) rows.
    """
    is_email = "@" in entity
    lookup_col = "email" if is_email else "name"

    # data_visibility='own' → restrict interactions sub-select
    _i_extra = ""
    binds = {"oid": org_id, "ent": entity}
    if data_visibility == "own" and requesting_agent_uuid:
        _i_extra = " AND (i.agent_uuid IS NULL OR i.agent_uuid = :req_agent)"
        binds["req_agent"] = requesting_agent_uuid

    # Single query: contact row + last 3 interactions as JSONB aggregate.
    row = db.execute(
        text(f"""
            SELECT
                c.id,
                c.name,
                c.email,
                c.company,
                c.relationship_stage,
                c.sentiment_ewma,
                c.confidence_score,
                c.last_interaction_at,
                c.interaction_count,
                (
                    SELECT COALESCE(jsonb_agg(x ORDER BY x.at DESC), '[]'::jsonb)
                    FROM (
                        SELECT
                            i.interaction_type AS type,
                            COALESCE(i.raw_snippet, '') AS summary,
                            i.interaction_at AS at,
                            i.sentiment AS sentiment
                        FROM interactions i
                        WHERE i.contact_id = c.id{_i_extra}
                        ORDER BY i.interaction_at DESC
                        LIMIT 3
                    ) x
                ) AS recent
            FROM contacts c
            WHERE c.org_id = :oid
              AND LOWER(c.{lookup_col}) = LOWER(:ent)
            LIMIT 1
        """),
        binds,
    ).fetchone()

    if not row:
        return None

    # is_broadcast is derived (no column) — compute it from the email.
    from app.context.bundle_builder import _is_broadcast_address
    is_broadcast = _is_broadcast_address(row.email or "")

    conf = float(row.confidence_score or 0.5)
    stage = row.relationship_stage or "UNKNOWN"
    recent = row.recent or []

    # Compose a short agent-facing paragraph from what we have.
    parts = [f"{row.name or row.email}"]
    if row.company:
        parts.append(f"at {row.company}")
    parts.append(f"— {stage}")
    if row.last_interaction_at:
        parts.append(f"last contact {row.last_interaction_at.date()}")
    summary_line = ", ".join(parts) + "."

    return {
        "entity": {
            "id": str(row.id),
            "name": row.name,
            "email": row.email,
            "company": row.company,
            "relationship_stage": stage,
            "sentiment_ewma": float(row.sentiment_ewma or 0.0),
            "is_broadcast": is_broadcast,
            "last_interaction": row.last_interaction_at.isoformat() if row.last_interaction_at else None,
            "interaction_count": int(row.interaction_count or 0),
            "communication_style": "unknown",
        },
        "context_for_agent": summary_line,
        "confidence": conf,
        "confidence_score": conf,  # deprecated alias; see PHASE_DEVIATIONS item Y
        "confidence_level": "high" if conf >= 0.7 else ("medium" if conf >= 0.4 else "low"),
        "situation_type": None,
        "sources_used": ["contacts", "interactions"],
        "recent_interactions": list(recent),
        "meta": {
            "source": "minimal",
            "reason": "precomputed_miss",
            "upgrade_in_progress": True,
        },
    }
