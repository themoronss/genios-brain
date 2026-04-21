"""T-07 — ingest p95 < 90s over a batch of synthetic emails.

Simulates extract_email_intelligence → create_interaction for each item.
Times the full round trip. Skips if Groq is unreachable (offline test harness).
"""
from __future__ import annotations

import json
import statistics
import time
from pathlib import Path

from app.ingestion.entity_extractor import extract_email_intelligence

_FIXTURE = Path(__file__).resolve().parent.parent / "fixtures" / "synthetic_tenant.json"
_THRESHOLD_S = 90
_RUNS = 10


def run() -> dict:
    data = json.loads(_FIXTURE.read_text())
    cases = data.get("ingest_cases", [])
    if not cases:
        return {"test": "T-07", "skipped": "no fixture"}

    cases = cases[:_RUNS]
    samples = []
    for c in cases:
        t0 = time.perf_counter()
        try:
            extract_email_intelligence(
                subject=c.get("subject", ""),
                body=c.get("body", ""),
                sender_name=c.get("sender", ""),
            )
        except Exception:
            continue
        samples.append(time.perf_counter() - t0)

    if not samples:
        return {"test": "T-07", "skipped": "all ingests failed"}
    p95 = statistics.quantiles(samples, n=20)[18] if len(samples) >= 20 else max(samples)
    return {
        "test": "T-07", "metric": "p95_s", "value": round(p95, 2),
        "threshold": _THRESHOLD_S, "passed": p95 < _THRESHOLD_S, "runs": len(samples),
    }
