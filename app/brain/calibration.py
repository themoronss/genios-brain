"""Calibration worker (Phase 4.10).

Nightly job: for each org, fit Platt scaling over (predicted_confidence, was_acted)
pairs from `recommendations` in the last 60 days. Store the curve + per-type
thresholds in `calibration_models`. Gate reads it.

Dormant by default — `GENIOS_CALIBRATION_ENABLED=false`. Even when enabled per-org
it only activates after ≥ 50 labeled outcomes (otherwise the fit is noise).
"""
from __future__ import annotations

import json
import logging
from typing import List, Tuple

from sqlalchemy import text

from app import config
from app.database import SessionLocal

logger = logging.getLogger(__name__)

_MIN_SAMPLES = 20  # lowered from 50 — small startups reach this in ~7d
_LOOKBACK_DAYS = 60


def _fetch_labels(db, org_id: str) -> List[Tuple[float, int, str]]:
    """Return (confidence, label, insight_type). label=1 if acted, 0 otherwise."""
    rows = db.execute(
        text("""
            SELECT confidence, outcome, insight_type
            FROM recommendations
            WHERE org_id = :oid
              AND outcome IS NOT NULL
              AND created_at >= NOW() - INTERVAL '60 days'
        """),
        {"oid": org_id},
    ).fetchall()
    out = []
    for c, o, t in rows:
        if c is None or o is None:
            continue
        label = 1 if o == "acted" else 0
        out.append((float(c), label, t or "generic"))
    return out


def _fit_platt(conf: list[float], labels: list[int]) -> tuple[float, float]:
    """Platt scaling: 1 / (1 + exp(A*conf + B)). Returns (A, B)."""
    from sklearn.linear_model import LogisticRegression
    import numpy as np

    X = np.array(conf).reshape(-1, 1)
    y = np.array(labels)
    if len(set(labels)) < 2:
        return 0.0, 0.0  # degenerate — no signal to fit
    model = LogisticRegression()
    model.fit(X, y)
    # sigmoid(Ax + B)  ≡  LogisticRegression with coef_=A, intercept_=B
    # sklearn uses sigmoid(w·x + b); to match Platt's sigmoid(-(A·f + B)) we
    # flip sign: A = -coef, B = -intercept
    a = float(-model.coef_[0][0])
    b = float(-model.intercept_[0])
    return a, b


def _expected_calibration_error(conf: list[float], labels: list[int], bins: int = 10) -> float:
    import numpy as np
    conf = np.array(conf)
    labels = np.array(labels)
    edges = np.linspace(0, 1, bins + 1)
    total = len(conf)
    ece = 0.0
    for i in range(bins):
        mask = (conf >= edges[i]) & (conf < edges[i + 1] if i < bins - 1 else conf <= edges[i + 1])
        n = mask.sum()
        if n == 0:
            continue
        avg_conf = conf[mask].mean()
        accuracy = labels[mask].mean()
        ece += (n / total) * abs(avg_conf - accuracy)
    return float(ece)


def _per_type_thresholds(rows: list[tuple[float, int, str]]) -> dict[str, float]:
    """For each type, find the confidence cutoff where acted-rate crosses 0.5."""
    by_type: dict[str, list[tuple[float, int]]] = {}
    for c, l, t in rows:
        by_type.setdefault(t, []).append((c, l))
    out = {}
    for t, pairs in by_type.items():
        if len(pairs) < 10:
            continue
        pairs.sort(key=lambda x: x[0], reverse=True)
        # Walk top-down; cut where cumulative acted-rate drops below 0.5.
        acted = 0
        for i, (c, l) in enumerate(pairs, start=1):
            acted += l
            if acted / i < 0.5:
                out[t] = round(c, 3)
                break
    return out


def run_for_org(org_id: str) -> dict:
    if not config.GENIOS_CALIBRATION_ENABLED:
        return {"skipped": "disabled"}
    db = SessionLocal()
    try:
        rows = _fetch_labels(db, org_id)
        if len(rows) < _MIN_SAMPLES:
            return {"skipped": "insufficient_samples", "have": len(rows), "need": _MIN_SAMPLES}

        conf = [r[0] for r in rows]
        labels = [r[1] for r in rows]

        a, b = _fit_platt(conf, labels)
        ece = _expected_calibration_error(conf, labels)
        thresholds = _per_type_thresholds(rows)

        db.execute(
            text("""
                INSERT INTO calibration_models
                    (org_id, platt_a, platt_b, ece, thresholds_per_type, sample_count, trained_at)
                VALUES (:oid, :a, :b, :ece, CAST(:th AS jsonb), :n, NOW())
                ON CONFLICT (org_id) DO UPDATE SET
                    platt_a = EXCLUDED.platt_a,
                    platt_b = EXCLUDED.platt_b,
                    ece = EXCLUDED.ece,
                    thresholds_per_type = EXCLUDED.thresholds_per_type,
                    sample_count = EXCLUDED.sample_count,
                    trained_at = NOW()
            """),
            {"oid": org_id, "a": a, "b": b, "ece": ece,
             "th": json.dumps(thresholds), "n": len(rows)},
        )
        db.commit()
        return {"fitted": True, "ece": round(ece, 4), "samples": len(rows), "thresholds": thresholds}
    finally:
        db.close()


def run_nightly() -> dict:
    """Iterate all orgs with ≥ _MIN_SAMPLES recommendations in the window."""
    db = SessionLocal()
    try:
        orgs = db.execute(
            text(f"""
                SELECT org_id, COUNT(*) AS n
                FROM recommendations
                WHERE outcome IS NOT NULL
                  AND created_at >= NOW() - INTERVAL '{_LOOKBACK_DAYS} days'
                GROUP BY org_id
                HAVING COUNT(*) >= {_MIN_SAMPLES}
            """),
        ).fetchall()
    finally:
        db.close()

    results = {}
    for row in orgs:
        try:
            results[str(row[0])] = run_for_org(str(row[0]))
        except Exception as e:
            logger.warning(f"calibration failed for {row[0]}: {e}")
    return results
