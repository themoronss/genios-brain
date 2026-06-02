"""
Phase 7: Live fetch cost guard.

Per-org, per-day cap on live tool dispatches (Gmail/Calendar/Docs API
calls triggered from /v1/context fallback). Mirrors the LLM cost guard
pattern: Redis counter keyed by (org_id, YYYY-MM-DD), soft-fail when
absent so dispatcher always works in dev.

Plan tier limits (read from PLAN_CONFIG.live_fetch_daily_cap):
  trial    →  10/day
  hustler  → 100/day
  startup  → 1000/day

Why a cap exists:
  - Gmail / Calendar APIs are quota-bound and metered
  - A misbehaving agent could brute-force live fetches and either bankrupt
    the customer (per-call OAuth costs) or get the org rate-limited by
    Google itself, breaking sync for everyone
  - Predictable spend story for finance + YC slide
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from app.redis_client import redis_client

logger = logging.getLogger(__name__)

_KEY_PREFIX = "live_fetch_count:"
_DEFAULT_TIER_CAPS = {
    "trial":    10,
    "hustler":  100,
    "startup":  1000,
}
_FALLBACK_CAP = 50  # used when plan tier unknown


def _today_key(org_id: str) -> str:
    return f"{_KEY_PREFIX}{org_id}:{datetime.now(timezone.utc).strftime('%Y-%m-%d')}"


def _cap_for_org(org_id: str) -> int:
    """Look up tier cap. Falls back to PLAN_CONFIG override if present,
    else the static defaults above."""
    try:
        from app.plan_enforcer import get_org_plan, PLAN_CONFIG
        from app.database import SessionLocal
        db = SessionLocal()
        try:
            plan_info = get_org_plan(db, org_id)
        finally:
            db.close()
        tier = plan_info.get("tier") or "trial"
        cfg = PLAN_CONFIG.get(tier, {}) or {}
        return int(cfg.get("live_fetch_daily_cap")
                   or _DEFAULT_TIER_CAPS.get(tier, _FALLBACK_CAP))
    except Exception:
        return _FALLBACK_CAP


def get_usage(org_id: str) -> int:
    """Current count of live fetches today. Returns 0 on Redis outage."""
    if not org_id:
        return 0
    try:
        n = redis_client.get(_today_key(org_id))
        return int(n or 0)
    except Exception:
        return 0


def allow(org_id: str) -> bool:
    """Return True if org can make another live fetch right now."""
    if not org_id:
        return False
    cap = _cap_for_org(org_id)
    if cap <= 0:
        return False
    return get_usage(org_id) < cap


def increment(org_id: str, count: int = 1) -> int:
    """Record `count` more live fetches. Returns new total. Best-effort."""
    if not org_id or count <= 0:
        return 0
    key = _today_key(org_id)
    try:
        pipe = redis_client.pipeline()
        pipe.incrby(key, count)
        pipe.expire(key, 36 * 3600)  # 36h — covers DST + clock skew
        results = pipe.execute()
        return int(results[0]) if results else 0
    except Exception as e:
        logger.debug(f"cost_guard increment failed: {e}")
        return 0


def status(org_id: str) -> dict:
    """For benchmark/dashboard: current usage + cap + remaining."""
    cap = _cap_for_org(org_id)
    used = get_usage(org_id)
    return {
        "org_id": org_id,
        "used_today": used,
        "cap_daily": cap,
        "remaining": max(0, cap - used),
        "exhausted": used >= cap,
    }
