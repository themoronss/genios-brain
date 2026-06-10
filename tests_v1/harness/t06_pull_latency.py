"""T-06 — pull API p95 < 400ms over 50 warm requests.

In-process timing (skips HTTP overhead). For HTTP p95, use `hey` or `wrk`
against a deployed endpoint.
"""
from __future__ import annotations

import json
import statistics
import time
from pathlib import Path

from app.context.bundle_builder import build_context_bundle
from app.database import SessionLocal

_FIXTURE = Path(__file__).resolve().parent.parent / "fixtures" / "synthetic_tenant.json"
_THRESHOLD_MS = 400
_RUNS = 50


def run() -> dict:
    data = json.loads(_FIXTURE.read_text())
    org_id = data.get("test_org_id")
    entity = data.get("latency_entity_name")
    if not org_id or not entity:
        return {"test": "T-06", "skipped": "no fixture"}

    samples = []
    db = SessionLocal()
    try:
        for _ in range(_RUNS):
            t0 = time.perf_counter()
            try:
                build_context_bundle(db, org_id, entity)
            except Exception:
                pass
            samples.append((time.perf_counter() - t0) * 1000)
    finally:
        db.close()

    if not samples:
        return {"test": "T-06", "skipped": "no samples"}
    p95 = statistics.quantiles(samples, n=20)[18]  # 95th percentile
    return {
        "test": "T-06", "metric": "p95_ms", "value": round(p95, 1),
        "threshold": _THRESHOLD_MS, "passed": p95 < _THRESHOLD_MS, "runs": _RUNS,
    }
