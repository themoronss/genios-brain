"""
Event-driven bundle refresher.

Runs for a single (org_id, contact_id) after the brain-router debounce window
closes. Rebuilds the context bundle, writes it to `precomputed_bundles` (the
hot path read by /v1/context Layer 1), and mirrors into Redis for the
situation-keyed cache.

Design: GeniOS is a context-intelligence API for agents — pulls must be <400ms
with real data, so bundles are pre-computed on every change rather than built
on demand.
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import timedelta
from typing import Optional

from sqlalchemy import text

from app.context.bundle_builder import build_context_bundle
from app.database import SessionLocal
from app.redis_client import redis_client

logger = logging.getLogger(__name__)

# If the same (org, contact) gets flushed repeatedly, this short window
# prevents a refresh storm. Separate from the router's 30s debounce — this
# is just a "did we JUST refresh" guard.
_MIN_REFRESH_INTERVAL_S = 10


def _skip_key(org_id: str, contact_id: str) -> str:
    return f"bundle_refresh_guard:{org_id}:{contact_id}"


def run_refresh_bundle(org_id: str, contact_id: str) -> dict:
    """Refresh the precomputed bundle for one contact. Safe to call repeatedly."""
    try:
        if redis_client.set(_skip_key(org_id, contact_id), "1", ex=_MIN_REFRESH_INTERVAL_S, nx=True) is None:
            return {"skipped": True, "reason": "recent_refresh"}
    except Exception:
        pass  # fail-open: let the refresh run

    db = SessionLocal()
    try:
        row = db.execute(
            text("""
                SELECT name, relationship_stage, sentiment_ewma, interaction_count
                FROM contacts
                WHERE id = :cid AND org_id = :oid
            """),
            {"cid": contact_id, "oid": org_id},
        ).fetchone()
        if not row:
            return {"error": "contact_not_found", "contact_id": contact_id}

        material = f"{row.relationship_stage}:{row.sentiment_ewma}:{row.interaction_count}"
        material_hash = hashlib.md5(material.encode()).hexdigest()

        existing = db.execute(
            text("""
                SELECT material_hash FROM precomputed_bundles
                WHERE org_id = :oid AND contact_id = :cid AND expires_at > NOW()
            """),
            {"oid": org_id, "cid": contact_id},
        ).fetchone()
        if existing and existing[0] == material_hash:
            return {"skipped": True, "reason": "unchanged", "contact_id": contact_id}

        bundle = build_context_bundle(db, org_id, row.name)
        if bundle.get("error"):
            return {"error": bundle["error"], "contact_id": contact_id}

        db.execute(
            text("""
                INSERT INTO precomputed_bundles
                    (org_id, contact_id, bundle, context_paragraph,
                     generated_at, expires_at, material_hash)
                VALUES
                    (:oid, :cid, CAST(:bundle AS jsonb), :paragraph,
                     NOW(), NOW() + INTERVAL '24 hours', :mh)
                ON CONFLICT (org_id, contact_id) DO UPDATE SET
                    bundle = EXCLUDED.bundle,
                    context_paragraph = EXCLUDED.context_paragraph,
                    generated_at = NOW(),
                    expires_at = NOW() + INTERVAL '24 hours',
                    material_hash = EXCLUDED.material_hash
            """),
            {
                "oid": org_id,
                "cid": contact_id,
                "bundle": json.dumps(bundle, default=str),
                "paragraph": bundle.get("context_for_agent", ""),
                "mh": material_hash,
            },
        )
        db.commit()
        logger.info(f"bundle_refresh ok org={org_id} contact={contact_id}")
        return {"refreshed": True, "contact_id": contact_id}
    except Exception as e:
        db.rollback()
        logger.exception(f"bundle_refresh failed org={org_id} contact={contact_id}: {e}")
        return {"error": str(e), "contact_id": contact_id}
    finally:
        db.close()
