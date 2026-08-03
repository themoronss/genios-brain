"""T-03 — entity resolution accuracy on variants.

Load fixture with (name_variant, expected_contact_id) pairs. Call resolver;
count accuracy = correct_hits / total.

Threshold: >= 0.98
"""
from __future__ import annotations

import json
from pathlib import Path

from app.database import SessionLocal
from app.ingestion.entity_resolver import resolve

_FIXTURE = Path(__file__).resolve().parent.parent / "fixtures" / "synthetic_tenant.json"
_THRESHOLD = 0.98


def run() -> dict:
    data = json.loads(_FIXTURE.read_text())
    cases = data.get("resolution_cases", [])
    org_id = data.get("test_org_id")
    if not cases or not org_id:
        return {"test": "T-03", "skipped": "no fixture cases"}

    db = SessionLocal()
    try:
        correct = 0
        for c in cases:
            try:
                m = resolve(db, org_id, c["input_name"], c.get("input_email"))
                if m.contact_id == c["expected_contact_id"]:
                    correct += 1
            except Exception:
                continue
        accuracy = correct / len(cases)
    finally:
        db.close()
    return {
        "test": "T-03", "metric": "accuracy", "value": round(accuracy, 3),
        "threshold": _THRESHOLD, "passed": accuracy >= _THRESHOLD, "cases": len(cases),
    }
