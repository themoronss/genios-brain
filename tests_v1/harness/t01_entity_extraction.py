"""T-01 — entity extraction F1 over a synthetic fixture.

Each fixture email has a gold-labelled set of entities. We extract via
llm_client.call(purpose="extract_entities"), compare the extracted
mentioned_people against the gold set, compute micro-F1 across the batch.

Threshold per plan: F1 >= 0.94
"""
from __future__ import annotations

import json
from pathlib import Path

from app.ingestion.entity_extractor import extract_email_intelligence

_FIXTURE = Path(__file__).resolve().parent.parent / "fixtures" / "synthetic_tenant.json"
_THRESHOLD = 0.94


def _f1(gold: set, pred: set) -> float:
    if not gold and not pred:
        return 1.0
    if not pred:
        return 0.0
    tp = len(gold & pred)
    precision = tp / max(1, len(pred))
    recall = tp / max(1, len(gold))
    if (precision + recall) == 0:
        return 0.0
    return 2 * precision * recall / (precision + recall)


def run() -> dict:
    data = json.loads(_FIXTURE.read_text())
    cases = data.get("entity_extraction_cases", [])
    if not cases:
        return {"test": "T-01", "skipped": "no fixture cases"}

    scores = []
    for case in cases:
        try:
            intel = extract_email_intelligence(
                subject=case.get("subject", ""),
                body=case.get("body", ""),
                sender_name=case.get("sender", ""),
            )
            pred = {p.lower().strip() for p in intel.get("mentioned_people", []) if p}
            gold = {p.lower().strip() for p in case.get("gold_mentioned", [])}
            scores.append(_f1(gold, pred))
        except Exception:
            scores.append(0.0)

    f1 = sum(scores) / len(scores) if scores else 0.0
    return {
        "test": "T-01", "metric": "f1", "value": round(f1, 3),
        "threshold": _THRESHOLD, "passed": f1 >= _THRESHOLD, "cases": len(scores),
    }
