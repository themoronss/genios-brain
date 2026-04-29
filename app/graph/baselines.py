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
