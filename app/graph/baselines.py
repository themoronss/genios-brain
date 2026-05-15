"""Baseline lookup helper for detectors.

Detectors call `get_baseline(db, org_id, contact_id, metric)` to retrieve a
contact's personal baseline (mean + stddev). Returns `None` when there isn't
enough data, so callers fall back to absolute thresholds gracefully.

`z_score(current, baseline)` computes the standardized deviation; values
beyond ±2.0 mark statistically significant departures from the contact's
own normal — what a human relationship manager would notice.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

from sqlalchemy import text

logger = logging.getLogger(__name__)

# Below this many samples the mean/std aren't trustworthy. Detectors should
# fall through to their existing absolute-threshold logic.
MIN_TRUSTED_SAMPLES = 5


@dataclass(frozen=True)
class Baseline:
    metric: str
    value: float       # rolling mean
    stddev: float      # rolling stddev (>= 0)
    samples: int       # contributing samples


def get_baseline(
    db, org_id: str, contact_id: str, metric: str,
) -> Optional[Baseline]:
    """Return the contact's baseline for `metric`, or None if missing/weak."""
    if not (org_id and contact_id and metric):
        return None
    try:
        row = db.execute(
            text("""
                SELECT value, stddev, samples
                FROM personal_baselines
                WHERE org_id = :oid
                  AND contact_id = :cid
                  AND metric = :metric
            """),
            {"oid": org_id, "cid": str(contact_id), "metric": metric},
        ).fetchone()
    except Exception as e:
        logger.debug(f"baseline lookup failed: {e}")
        return None

    if not row or int(row.samples or 0) < MIN_TRUSTED_SAMPLES:
        return None
    return Baseline(
        metric=metric,
        value=float(row.value or 0.0),
        stddev=float(row.stddev or 0.0),
        samples=int(row.samples),
    )


def z_score(current: float, baseline: Baseline) -> Optional[float]:
    """Standardized deviation. None when stddev is 0 (degenerate)."""
    if baseline.stddev <= 0:
        return None
    return (float(current) - baseline.value) / baseline.stddev


# Multiplier on the contact's typical response time used to define the
# "cold horizon". 3x normal cadence is the point where silence is no
# longer routine. Floor of 7d prevents the prediction from collapsing on
# contacts with near-instant turnaround.
_COLD_MULTIPLIER = 3
_COLD_FLOOR_DAYS = 7
_COLD_GLOBAL_FALLBACK_DAYS = 21


def predict_cold_window(
    db, org_id: str, contact_id: str, days_since_last: int,
) -> Optional[int]:
    """Estimate days remaining before the contact crosses the cold horizon.

    Strategy:
      1. Prefer contact_baselines.response_time_avg_hours (simple column).
      2. Fall back to personal_baselines (metric='response_hours') EAV row.
      3. If neither exists, use a 21-day global default.

    Returns None on unrecoverable DB errors. Returns 0 if already past cold.
    """
    if days_since_last is None or days_since_last < 0:
        return None

    response_hours: Optional[float] = None
    try:
        row = db.execute(
            text(
                """
                SELECT response_time_avg_hours
                FROM contact_baselines
                WHERE contact_id = :cid
                ORDER BY computed_at DESC
                LIMIT 1
                """
            ),
            {"cid": str(contact_id)},
        ).fetchone()
        if row and row.response_time_avg_hours is not None:
            response_hours = float(row.response_time_avg_hours)
    except Exception as e:
        logger.debug(f"contact_baselines lookup failed: {e}")

    if response_hours is None:
        try:
            row = db.execute(
                text(
                    """
                    SELECT value
                    FROM personal_baselines
                    WHERE org_id = :oid
                      AND contact_id = :cid
                      AND metric = 'response_hours'
                    ORDER BY updated_at DESC
                    LIMIT 1
                    """
                ),
                {"oid": org_id, "cid": str(contact_id)},
            ).fetchone()
            if row and row.value is not None:
                response_hours = float(row.value)
        except Exception as e:
            logger.debug(f"personal_baselines lookup failed: {e}")

    if response_hours and response_hours > 0:
        normal_response_days = response_hours / 24.0
        cold_threshold_days = max(normal_response_days * _COLD_MULTIPLIER, _COLD_FLOOR_DAYS)
    else:
        cold_threshold_days = _COLD_GLOBAL_FALLBACK_DAYS

    remaining = int(cold_threshold_days - days_since_last)
    return remaining if remaining > 0 else 0
