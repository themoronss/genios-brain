"""Per-tenant per-insight-type act-rate lookup.

Returns the rolling 90-day acted/(acted+ignored+dismissed) ratio for an org's
insight type. Used by the priority scorer to give weight to insight types
this tenant historically actually acts on.

  - Below MIN_SAMPLES (15) → return 0.5 (uniform default).
  - Above → return clamped acted-rate, optionally re-cast against a baseline.

Cache: Redis 1h TTL. Misses fall back to Postgres; if Postgres errors,
return the uniform default (fail-soft — never block scoring).
"""
from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy import text

from app.database import SessionLocal
from app.redis_client import redis_client

logger = logging.getLogger(__name__)

_TTL = 3600  # 1 hour
_MIN_SAMPLES = 15  # lowered from 30 — small startups reach this faster
_DEFAULT = 0.5


def _cache_key(org_id: str, insight_type: str) -> str:
    return f"user_fit:{org_id}:{insight_type}"


def _query_pg(org_id: str, insight_type: str) -> Optional[float]:
    db = SessionLocal()
    try:
        row = db.execute(
            text("""
                SELECT
                  COUNT(*)                                             AS total,
                  COUNT(*) FILTER (WHERE outcome = 'acted')::float     AS acted
                FROM feedback
                WHERE org_id = :oid
                  AND insight_type = :it
                  AND created_at > NOW() - INTERVAL '90 days'
            """),
            {"oid": org_id, "it": insight_type},
        ).fetchone()
    except Exception as e:
        logger.debug(f"user_fit pg lookup failed for {org_id}/{insight_type}: {e}")
        return None
    finally:
        db.close()

    if not row:
        return None
    total = int(row.total or 0)
    if total < _MIN_SAMPLES:
        return None  # caller treats None as default
    acted = float(row.acted or 0.0)
    return max(0.0, min(1.0, acted / total))


def get(org_id: str, insight_type: str) -> float:
    """Return the user-fit score in [0,1]. Always safe — never raises."""
    if not org_id or not insight_type:
        return _DEFAULT

    key = _cache_key(org_id, insight_type)
    try:
        cached = redis_client.get(key)
        if cached is not None:
            return float(cached)
    except Exception:
        pass  # cache miss path

    val = _query_pg(org_id, insight_type)
    if val is None:
        val = _DEFAULT

    try:
        redis_client.setex(key, _TTL, str(val))
    except Exception:
        pass
    return val
