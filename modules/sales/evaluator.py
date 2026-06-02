"""Sales module evaluator — operationalizes the §7 falsifiable experiment.

Per MD g-i-5 — module ships an `evaluator.py` with a `evaluate(**kwargs) -> dict`
callable. The SDK's golden_test.run_golden_test() loads + runs this.

NOTE: this is the ONLY .py file in a module that's NOT engine code. It's data:
a stand-alone script that reads ground-truth fixtures and returns a score.
The SDK's `_REJECTED_FILE_NAMES` allow-lists this by not blacklisting "evaluator.py".

For the §7 experiment, ground-truth fixtures live in a dataset_dir supplied by
the caller (typically synthetic seeds for unit tests; real customer-deal fixtures
during the design-partner pilot).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any


def evaluate(
    *,
    dataset_dir: str | None = None,
    ruleset: object | None = None,
) -> dict[str, Any]:
    """Score the Sales module against ground-truth labeled deals.

    Inputs:
      dataset_dir: path to JSONL file with one labeled deal per line, e.g.
        {"facts": {"days_in_stage": 25, "stage": "negotiation"},
         "expert_conclusion": "deal_stalled"}
      ruleset: optional RuleSet (caller may pre-load module rules)

    Output:
      {
        "score": <0..1>  # fraction matched
        "metrics": {
            "n_cases": int,
            "n_matched": int,
            "by_conclusion": {...}
        }
      }

    Returns a placeholder score when dataset_dir is missing OR empty (smoke-test mode).
    """
    if dataset_dir is None:
        # Smoke mode — used by sdk/golden_test unit tests before real fixtures exist.
        return {
            "score": 1.0,
            "metrics": {
                "mode": "smoke",
                "n_cases": 0,
                "n_matched": 0,
                "note": "no dataset supplied — placeholder pass for SDK plumbing tests",
            },
        }

    path = Path(dataset_dir)
    if not path.exists():
        return {
            "score": 0.0,
            "metrics": {"error": f"dataset path not found: {dataset_dir}"},
        }

    # Real eval: read JSONL, run engine on each, compare to expert_conclusion.
    # Full wiring lands when the design partner provides labeled cases.
    # Until then: report 0 cases / placeholder for the SDK's golden-test harness.
    return {
        "score": 0.0,
        "metrics": {
            "n_cases": 0,
            "n_matched": 0,
            "note": "evaluator scaffold present; real engine-wiring waits for labeled dataset",
        },
    }
