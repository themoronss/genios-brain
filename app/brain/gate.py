"""Push gate (spec §8.5) — 5 blocking rules between reasoner and dispatcher.

1. Reasoner said keep=False                 → block
2. confidence < calibrated threshold        → block   (Item 4 — uses Platt scaling when available)
3. priority   < GENIOS_MIN_PUSH_PRIORITY    → block
4. deduped in the last 24h (Redis SET)      → block
5. Org daily budget exhausted                → block

All pass → return True. Any block → False + reason.

Rule 2 — calibration integration:
  When `GENIOS_CALIBRATION_ENABLED=true` AND calibration_models.is_active=true
  AND ece<0.15 AND sample_count>=50 for the org, apply the Platt curve
  (A, B) to the raw confidence so gate decisions use calibrated confidence.
  Per-type thresholds override the flat GENIOS_MIN_PUSH_CONFIDENCE when set.
  Fall back to flat threshold otherwise (fail-safe).
"""
from __future__ import annotations

import json
import logging
import math
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import text

from app import config
from app.brain.reasoner import ReasonResult
from app.database import SessionLocal
from app.redis_client import redis_client

logger = logging.getLogger(__name__)

_DEDUP_TTL = 24 * 3600
_CAL_CACHE_TTL = 600  # 10 min
_MAX_ECE_FOR_USE = 0.15
_MIN_SAMPLES_FOR_USE = 50


def _dedup_key(org_id: str, insight_type: str, subject_entity_id: str) -> str:
    return f"dedup:{org_id}:{insight_type}:{subject_entity_id}"


def _budget_key(org_id: str) -> str:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return f"push_budget:{org_id}:{today}"


def _calibration_cache_key(org_id: str) -> str:
    return f"cal_model:{org_id}"


def _load_calibration(org_id: str) -> Optional[dict]:
    """Return {A, B, ece, thresholds, samples} if a usable, active model
    exists for this org. None otherwise. Cached 10 min in Redis."""
    if not config.GENIOS_CALIBRATION_ENABLED:
        return None
    if not org_id:
        return None

    cache_key = _calibration_cache_key(org_id)
    try:
        cached = redis_client.get(cache_key)
        if cached == "__none__":
            return None
        if cached:
            return json.loads(cached)
    except Exception:
        pass

    db = SessionLocal()
    try:
        row = db.execute(
            text("""
                SELECT platt_a, platt_b, ece, thresholds_per_type, sample_count
                FROM calibration_models
                WHERE org_id = :oid AND is_active = TRUE
            """),
            {"oid": org_id},
        ).fetchone()
    except Exception as e:
        logger.debug(f"calibration lookup failed: {e}")
        db.close()
        return None
    finally:
        db.close()

    if not row:
        try:
            redis_client.setex(cache_key, _CAL_CACHE_TTL, "__none__")
        except Exception:
            pass
        return None

    # Guard: only use a model that's within the ECE / sample-count envelope.
    ece = float(row.ece or 1.0)
    samples = int(row.sample_count or 0)
    if ece >= _MAX_ECE_FOR_USE or samples < _MIN_SAMPLES_FOR_USE:
        try:
            redis_client.setex(cache_key, _CAL_CACHE_TTL, "__none__")
        except Exception:
            pass
        return None

    thresholds = row.thresholds_per_type or {}
    if isinstance(thresholds, str):
        try:
            thresholds = json.loads(thresholds)
        except Exception:
            thresholds = {}

    model = {
        "A": float(row.platt_a or 0.0),
        "B": float(row.platt_b or 0.0),
        "ece": ece,
        "thresholds": thresholds,
        "samples": samples,
    }
    try:
        redis_client.setex(cache_key, _CAL_CACHE_TTL, json.dumps(model))
    except Exception:
        pass
    return model


def _apply_platt(raw_conf: float, model: dict) -> float:
    """Platt: sigmoid(-(A·f + B)). Sign convention matches calibration._fit_platt
    (which already flips sign so callers just negate inside the sigmoid here)."""
    A = model.get("A", 0.0)
    B = model.get("B", 0.0)
    try:
        return 1.0 / (1.0 + math.exp(A * raw_conf + B))
    except OverflowError:
        # Saturated — return extreme end of sigmoid
        return 0.0 if (A * raw_conf + B) > 0 else 1.0


def allow(
    *,
    candidate: dict,
    reason_result: ReasonResult,
    priority: float,
) -> tuple[bool, str]:
    """Return (allowed, blocking_reason). blocking_reason is '' when allowed."""
    if not reason_result.keep:
        return False, "reasoner_keep_false"

    org_id = str(candidate.get("org_id") or "")
    itype = candidate.get("insight_type") or "generic"

    # Rule 2 — calibrated confidence check (with fallback to flat threshold)
    raw_conf = reason_result.confidence
    model = _load_calibration(org_id)
    if model:
        cal_conf = _apply_platt(raw_conf, model)
        threshold = model["thresholds"].get(itype, config.GENIOS_MIN_PUSH_CONFIDENCE)
        effective_conf = cal_conf
    else:
        threshold = config.GENIOS_MIN_PUSH_CONFIDENCE
        effective_conf = raw_conf

    if effective_conf < threshold:
        logger.debug(
            f"gate_block below_confidence org={org_id} type={itype} "
            f"raw={raw_conf:.3f} cal={effective_conf:.3f} thr={threshold:.3f}"
        )
        return False, "below_min_confidence"

    if priority < config.GENIOS_MIN_PUSH_PRIORITY:
        return False, "below_min_priority"

    subj = str(candidate.get("contact_id") or candidate.get("subject_entity_id") or "")

    # Rule 4 — dedup 24h
    dkey = _dedup_key(org_id, itype, subj)
    try:
        if redis_client.set(dkey, "1", ex=_DEDUP_TTL, nx=True) is None:
            return False, "dedup_recent"
    except Exception as e:
        logger.warning(f"dedup check failed open: {e}")

    # Rule 5 — daily budget
    bkey = _budget_key(org_id)
    try:
        used = int(redis_client.get(bkey) or 0)
        if used >= config.GENIOS_WEBHOOK_DAILY_BUDGET:
            return False, "budget_exhausted"
        # reserve one slot; TTL to end-of-day is approximated at 24h.
        pipe = redis_client.pipeline()
        pipe.incr(bkey)
        pipe.expire(bkey, 24 * 3600)
        pipe.execute()
    except Exception as e:
        logger.warning(f"budget check failed open: {e}")

    return True, ""
