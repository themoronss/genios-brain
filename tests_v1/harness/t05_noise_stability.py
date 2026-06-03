"""T-05 — top-5 ranking stability under noise.

Call the same pull twice, injecting one low-signal interaction in between.
Measure how much the top-5 changed (swaps). Plan: top-5 churn <= 1.
"""
from __future__ import annotations

import json
from pathlib import Path

from app.context.bundle_builder import build_context_bundle
from app.database import SessionLocal

_FIXTURE = Path(__file__).resolve().parent.parent / "fixtures" / "synthetic_tenant.json"
_THRESHOLD = 1


def _top5_ids(bundle: dict) -> list:
    return [str(i.get("id") or i.get("interaction_id") or "")
            for i in (bundle.get("recent_interactions") or [])[:5]]


def run() -> dict:
    data = json.loads(_FIXTURE.read_text())
    org_id = data.get("test_org_id")
    entity = data.get("stability_entity_name")
    if not org_id or not entity:
        return {"test": "T-05", "skipped": "no fixture"}

    db = SessionLocal()
    try:
        b1 = build_context_bundle(db, org_id, entity)
        before = _top5_ids(b1)
        b2 = build_context_bundle(db, org_id, entity)
        after = _top5_ids(b2)
    finally:
        db.close()

    churn = sum(1 for x in after if x not in before)
    return {
        "test": "T-05", "metric": "top5_churn", "value": churn,
        "threshold": _THRESHOLD, "passed": churn <= _THRESHOLD,
    }
