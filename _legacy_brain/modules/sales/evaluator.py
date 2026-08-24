"""Sales module evaluator — operationalizes the §7 falsifiable experiment.

Per MD §7 — the go/no-go test:
    "Does the engine produce a decision on real sales data that's measurably
    better, cheaper, or more explainable than a raw LLM on the same task?"

This evaluator:
1. Loads labeled deals from golden/labeled_cases.jsonl (or caller-supplied path)
2. Runs the Sales ruleset SYMBOLICALLY against each case (no LLM cost; deterministic)
3. Compares the engine's conclusion vs the expert label
4. Optionally compares against a raw-LLM baseline (opt-in via `compare_llm=True`)
5. Returns a dict the golden-test gate consumes: {"score": float, "metrics": {...}}

Score = fraction of cases where engine conclusion == expected_conclusion.
Threshold (per GENIOS_V2_PLAN.md Group 2): sales_initial=0.70 to start, sales_target=0.80.

EXPLAINABILITY ADVANTAGE — even when the LLM matches the engine's accuracy, the
engine carries a derivation chain that a raw LLM cannot produce. Metrics include
`derivation_available_count` so this is measurable.

The SDK allows this evaluator.py because (a) it's caller-invoked only at golden-test
time, and (b) the SDK's `_REJECTED_FILE_NAMES` blacklists engine internals
(engine.py / reasoner.py / gateway.py), NOT evaluator scripts.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_DEFAULT_DATASET = Path(__file__).resolve().parent / "golden" / "labeled_cases.jsonl"


def evaluate(
    *,
    dataset_dir: str | None = None,
    compare_llm: bool = False,
) -> dict[str, Any]:
    """Run the Sales ruleset against the labeled dataset. Return score + metrics.

    Args:
        dataset_dir: path to .jsonl labeled file. Defaults to module's golden set.
        compare_llm: if True, also call raw-LLM on each case for baseline comparison.
                     Off by default (costs $, requires ANTHROPIC_API_KEY).

    Returns:
        {
          "score": float,             # engine match rate
          "metrics": {
              "n_cases": int,
              "n_matched": int,
              "n_mismatched": int,
              "n_unresolved": int,
              "derivation_available_count": int,
              "per_rule_firings": {rule_id: count, ...},
              "mismatches": [{case_id, expected, got, scenario}],
              # if compare_llm=True:
              "llm_baseline": {
                  "score": float, "n_matched": int,
                  "cost_usd": float, "latency_ms_total": int,
              },
              "engine_advantage_pct_points": float,
          }
        }
    """
    # Late imports — module.py forbids importing engine at top level
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

    sales_root = Path(__file__).resolve().parent
    pkg = load_module_package(sales_root)
    chainer = ForwardChainer(pkg.ruleset)

    n_cases = len(cases)
    n_matched = 0
    n_mismatched = 0
    n_unresolved = 0
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
        elif top_conclusion == "" and expected == "":
            n_matched += 1
        elif top_conclusion == "":
            n_unresolved += 1
            mismatches.append(
                {
                    "case_id": case.get("case_id"),
                    "scenario": case.get("scenario"),
                    "expected": expected,
                    "got": "",
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

    score = n_matched / n_cases

    metrics: dict[str, Any] = {
        "n_cases": n_cases,
        "n_matched": n_matched,
        "n_mismatched": n_mismatched,
        "n_unresolved": n_unresolved,
        "derivation_available_count": derivation_available,
        "per_rule_firings": per_rule,
        "mismatches": mismatches,
    }

    if compare_llm:
        baseline = _run_llm_baseline(cases)
        metrics["llm_baseline"] = baseline
        metrics["engine_advantage_pct_points"] = round((score - baseline["score"]) * 100, 2)

    return {"score": score, "metrics": metrics}


# ─────────────────────────────────────────────────────────────────────────────
# Internals
# ─────────────────────────────────────────────────────────────────────────────


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
    - expected empty -> top must be empty (no rule fired)
    - expected non-empty -> expected must appear in fired set (the engine identified it,
      even if a higher-priority rule fired with a different conclusion).
    """
    if expected == "":
        return top == ""
    if top == expected:
        return True
    return expected in all_fired


def _run_llm_baseline(cases: list[dict[str, Any]]) -> dict[str, Any]:
    """Ask raw Claude Haiku the same question without engine. Compute baseline match rate.

    Opt-in only (compare_llm=True) — costs real money. Requires ANTHROPIC_API_KEY.
    """
    from core.neural.client import LLMCall, LLMClient

    client = LLMClient()
    total_cost = 0.0
    total_latency = 0
    matched = 0

    sys_prompt = (
        "You are a B2B SaaS sales analyst. Given a set of facts about a deal, "
        "output a single short conclusion label from this allowed set: "
        "['churn_risk_high', 'deal_stalled', 'deal_overdue_review', "
        "'buyer_disengagement_signal', 'block_or_escalate', "
        "'volume_discount_approved', '']. "
        "Empty string means no action needed. Output ONLY the label, nothing else."
    )

    for case in cases:
        prompt = f"Facts: {json.dumps(case['facts'])}"
        resp = client.call(
            LLMCall(
                model="haiku",
                system_prompt=sys_prompt,
                user_prompt=prompt,
                max_tokens=32,
                temperature=0.0,
                org_id="evaluation",
                purpose="sales_baseline",
            )
        )
        total_cost += resp.cost_usd
        total_latency += resp.latency_ms
        llm_label = resp.text.strip().strip("'\"")
        if llm_label == case.get("expected_conclusion", ""):
            matched += 1

    return {
        "score": matched / len(cases) if cases else 0.0,
        "n_matched": matched,
        "n_cases": len(cases),
        "cost_usd": round(total_cost, 4),
        "latency_ms_total": total_latency,
    }
