"""CSM module evaluator. Same shape as hr_pipeline/evaluator.py."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_DEFAULT_DATASET = Path(__file__).resolve().parent / "golden" / "labeled_cases.jsonl"


def evaluate(*, dataset_dir: str | None = None) -> dict[str, Any]:
    from core.modules_framework.loader import load_module_package
    from core.reasoning.rule_engine import ForwardChainer

    dataset_path = Path(dataset_dir) if dataset_dir else _DEFAULT_DATASET
    if not dataset_path.exists():
        return {"score": 0.0, "metrics": {"error": f"dataset not found: {dataset_path}"}}
    cases = _load_jsonl(dataset_path)
    if not cases:
        return {"score": 0.0, "metrics": {"error": "dataset is empty"}}

    pkg = load_module_package(Path(__file__).resolve().parent)
    chainer = ForwardChainer(pkg.ruleset)

    n_matched = n_mismatched = n_unresolved = n_false_pos = derivation = 0
    per_rule: dict[str, int] = {}
    mismatches: list[dict[str, Any]] = []

    for case in cases:
        facts = case.get("facts", {})
        expected = case.get("expected_conclusion", "")
        result = chainer.run(facts)
        fired = [s.conclusion for s in result.proof.steps]
        top = fired[0] if fired else ""

        if _matches(top, expected, fired):
            n_matched += 1
        elif expected == "" and top != "":
            n_false_pos += 1
            mismatches.append({"case_id": case.get("case_id"), "expected": "(no fire)", "got": top, "all_fired": fired})
        elif expected != "" and top == "":
            n_unresolved += 1
            mismatches.append({"case_id": case.get("case_id"), "expected": expected, "got": "(nothing)"})
        else:
            n_mismatched += 1
            mismatches.append({"case_id": case.get("case_id"), "expected": expected, "got": top, "all_fired": fired})

        if result.proof.steps:
            derivation += 1
        for s in result.proof.steps:
            per_rule[s.rule_id] = per_rule.get(s.rule_id, 0) + 1

    return {
        "score": n_matched / len(cases),
        "metrics": {
            "n_cases": len(cases),
            "n_matched": n_matched,
            "n_mismatched": n_mismatched,
            "n_unresolved": n_unresolved,
            "n_false_positives": n_false_pos,
            "derivation_available_count": derivation,
            "per_rule_firings": per_rule,
            "mismatches": mismatches,
        },
    }


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text("utf-8").splitlines() if line.strip()]


def _matches(top: str, expected: str, all_fired: list[str]) -> bool:
    if expected == "":
        return top == ""
    if top == expected:
        return True
    return expected in all_fired
