"""AR-collection module evaluator.

Falsifiable check per MD §7: run the symbolic ruleset against a hand-labeled
golden set (15 invoice cases mixing fire/no-fire scenarios). Each case has the
exact facts the engine would receive from a CSV-uploaded invoice row, plus the
expected conclusion. Score = engine-match / total-cases.

Thresholds (analogous to GENIOS_V2_PLAN.md Group 2):
    ar_initial = 0.85   # we own the rules, golden set is small + curated
    ar_target  = 0.95

The evaluator deliberately exercises BOUNDARY cases (exactly 3d late, exactly
15d late, exactly ₹1L) so any drift in rule thresholds gets caught here before
shipping. Add new fixtures whenever a real customer surfaces an edge case.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_DEFAULT_DATASET = Path(__file__).resolve().parent / "golden" / "labeled_cases.jsonl"


def evaluate(
    *,
    dataset_dir: str | None = None,
) -> dict[str, Any]:
    """Run the AR ruleset against labeled invoices. Return score + metrics.

    Args:
        dataset_dir: optional override path to the labeled .jsonl file.

    Returns:
        {
          "score": float,                       # engine match rate (0-1)
          "metrics": {
              "n_cases": int,
              "n_matched": int,
              "n_mismatched": int,
              "n_unresolved": int,              # expected something, got nothing
              "n_false_positives": int,         # expected nothing, got something
              "derivation_available_count": int,
              "per_rule_firings": {rule_id: count, ...},
              "mismatches": [{case_id, scenario, expected, got, all_fired}],
          }
        }
    """
    from core.modules_framework.loader import load_module_package
    from core.reasoning.rule_engine import ForwardChainer

    dataset_path = Path(dataset_dir) if dataset_dir else _DEFAULT_DATASET
    if not dataset_path.exists():
        return {
            "score": 0.0,
            "metrics": {"error": f"dataset not found: {dataset_path}"},
        }

    cases = _load_jsonl(dataset_path)
    if not cases:
        return {"score": 0.0, "metrics": {"error": "dataset is empty"}}

    ar_root = Path(__file__).resolve().parent
    pkg = load_module_package(ar_root)
    chainer = ForwardChainer(pkg.ruleset)

    n_matched = 0
    n_mismatched = 0
    n_unresolved = 0
    n_false_pos = 0
    derivation_available = 0
    per_rule: dict[str, int] = {}
    mismatches: list[dict[str, Any]] = []

    for case in cases:
        facts = case.get("facts", {})
        expected = case.get("expected_conclusion", "")
        result = chainer.run(facts)
        fired_conclusions = [s.conclusion for s in result.proof.steps]
        top_conclusion = fired_conclusions[0] if fired_conclusions else ""

        if _conclusion_matches(top_conclusion, expected, fired_conclusions):
            n_matched += 1
        elif expected == "" and top_conclusion != "":
            n_false_pos += 1
            mismatches.append(
                {
                    "case_id": case.get("case_id"),
                    "scenario": case.get("scenario"),
                    "expected": "(no fire)",
                    "got": top_conclusion,
                    "all_fired": fired_conclusions,
                }
            )
        elif expected != "" and top_conclusion == "":
            n_unresolved += 1
            mismatches.append(
                {
                    "case_id": case.get("case_id"),
                    "scenario": case.get("scenario"),
                    "expected": expected,
                    "got": "(nothing fired)",
                    "all_fired": [],
                }
            )
        else:
            n_mismatched += 1
            mismatches.append(
                {
                    "case_id": case.get("case_id"),
                    "scenario": case.get("scenario"),
                    "expected": expected,
                    "got": top_conclusion,
                    "all_fired": fired_conclusions,
                }
            )

        if result.proof.steps:
            derivation_available += 1
        for s in result.proof.steps:
            per_rule[s.rule_id] = per_rule.get(s.rule_id, 0) + 1

    n_cases = len(cases)
    score = n_matched / n_cases

    return {
        "score": score,
        "metrics": {
            "n_cases": n_cases,
            "n_matched": n_matched,
            "n_mismatched": n_mismatched,
            "n_unresolved": n_unresolved,
            "n_false_positives": n_false_pos,
            "derivation_available_count": derivation_available,
            "per_rule_firings": per_rule,
            "mismatches": mismatches,
        },
    }


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    for raw in path.read_text("utf-8").splitlines():
        line = raw.strip()
        if not line:
            continue
        cases.append(json.loads(line))
    return cases


def _conclusion_matches(top: str, expected: str, all_fired: list[str]) -> bool:
    """Match policy:
    - expected empty   → top must be empty (no rule fired)
    - expected non-empty → expected must appear in fired set (engine identified
      it, even if a higher-priority rule fired a different conclusion alongside).
    """
    if expected == "":
        return top == ""
    if top == expected:
        return True
    return expected in all_fired
