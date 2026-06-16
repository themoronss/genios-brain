"""§7 falsifiable-experiment harness — GeniOS vs. raw Sonnet vs. human label.

Implements GATE 0 / Task 1 of GENIOS_BRIEFING_CTO_AND_AGENT.md (§5, §8). This is
the one experiment the plan puts before everything else: prove the engine decides
*as well as or better than* a raw LLM on REAL sales decisions, and measure how
often the cheap symbolic pass resolves a case without the LLM (the 80/20 bet).

What it does, per real labeled case, on identical facts:
    1. GeniOS   core.decision.decide()  — the real engine path (symbolic + Haiku
                gap-fill), via the same wiring the production query handler uses.
                Captures: conclusion, route, confidence, and whether the SYMBOLIC
                pass alone resolved it (path == "symbolic").
    2. raw Sonnet  — one neutral Claude Sonnet call with the same facts and no
                rules. The honest "could you just call an LLM?" baseline.
    3. human label — ground truth from the case file.

What it emits (to --out as JSON, and a table to stdout):
    - per-case row: symbolic_resolved (Y/N), geniOS conclusion, sonnet conclusion,
      human label, geniOS↔human match, sonnet↔human match, derivation present
    - aggregates: % symbolic-resolved (the 80/20 test), GeniOS accuracy,
      Sonnet accuracy, delta (pp), Sonnet cost + latency

It deliberately does NOT invent or enforce pass thresholds. Per §5 the founder
PRE-REGISTERS the numbers in writing before running; this script only reports
what reality produced. No moving goalposts.

Modes
-----
  --preflight   Symbolic-only (ForwardChainer). No DB, no API key, no $ cost.
                Validates the case file and prints the symbolic-resolution rate
                and symbolic accuracy. Run this FIRST — it's free and catches
                malformed cases before you spend money on the full run.

  (default)     Full 3-way run. Requires ANTHROPIC_API_KEY + a configured
                DATABASE_URL (the engine persists a DecisionRow per case, which
                also feeds Gate 2's metrics).

Usage
-----
    # 1) free preflight — check the file + see the 80/20 number
    python -m tools.section7_harness --preflight \\
        --cases modules/sales/golden/real_cases.jsonl

    # 2) full experiment (needs keys + DB)
    python -m tools.section7_harness \\
        --cases modules/sales/golden/real_cases.jsonl \\
        --org-id genios-eval --out section7_results.json

Case file format: see modules/sales/golden/REAL_CASES_README.md
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
SALES_ROOT = REPO_ROOT / "modules" / "sales"
DEFAULT_CASES = SALES_ROOT / "golden" / "real_cases.jsonl"

# Conclusions that all mean "no action needed" — collapsed so a human "" label
# and an engine "insufficient_data" don't count as a disagreement when both are
# really saying "nothing to do here."
NO_ACTION = {"", "insufficient_data", "need_more_facts", "no_action", "none", "n/a"}


# ─────────────────────────────────────────────────────────────────────────────
# Matching (shared by both modes — same fairness rules for engine and Sonnet)
# ─────────────────────────────────────────────────────────────────────────────


def _norm(label: str | None) -> str:
    return (label or "").strip().strip("'\"").lower()


def _is_no_action(label: str | None) -> bool:
    return _norm(label) in NO_ACTION


def _matches(predicted: str | None, human: str | None) -> bool:
    """A prediction matches the human label if both say 'no action', or the
    normalized strings are equal. Same rule applied to GeniOS and Sonnet."""
    if _is_no_action(human):
        return _is_no_action(predicted)
    return _norm(predicted) == _norm(human)


# ─────────────────────────────────────────────────────────────────────────────
# Case loading
# ─────────────────────────────────────────────────────────────────────────────


def _load_cases(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        sys.exit(
            f"ERROR: case file not found: {path}\n"
            f"Create it from the template — see modules/sales/golden/REAL_CASES_README.md"
        )
    cases: list[dict[str, Any]] = []
    for i, raw in enumerate(path.read_text("utf-8").splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("//"):
            continue
        try:
            case = json.loads(line)
        except json.JSONDecodeError as e:
            sys.exit(f"ERROR: bad JSON on line {i} of {path}: {e}")
        if "facts" not in case or not isinstance(case["facts"], dict):
            sys.exit(f"ERROR: case on line {i} missing a 'facts' object: {case.get('case_id', '?')}")
        # Accept either 'human_label' (real cases) or 'expected_conclusion' (golden set).
        case["human_label"] = case.get("human_label", case.get("expected_conclusion", ""))
        case.setdefault("case_id", f"case_{i:03d}")
        case.setdefault("scenario", "")
        cases.append(case)
    if not cases:
        sys.exit(f"ERROR: no cases found in {path}")
    return cases


def _allowed_labels(cases: list[dict[str, Any]]) -> list[str]:
    """The label vocabulary the humans actually used — given to Sonnet so it
    chooses from the same set the humans did (fair, neutral)."""
    labels = sorted({_norm(c["human_label"]) for c in cases if not _is_no_action(c["human_label"])})
    return labels


# ─────────────────────────────────────────────────────────────────────────────
# Preflight: symbolic-only (no DB, no API key, no cost)
# ─────────────────────────────────────────────────────────────────────────────


def run_preflight(cases: list[dict[str, Any]]) -> dict[str, Any]:
    from core.modules_framework.loader import load_module_package
    from core.reasoning.rule_engine import ForwardChainer

    pkg = load_module_package(SALES_ROOT)
    chainer = ForwardChainer(pkg.ruleset)

    rows: list[dict[str, Any]] = []
    n_symbolic_resolved = 0
    n_symbolic_match = 0
    for case in cases:
        result = chainer.run(case["facts"])
        fired = [s.conclusion for s in result.proof.steps]
        top = fired[0] if fired else ""
        resolved = bool(result.resolved)
        # symbolic counts as correct if the chosen conclusion matches, OR the
        # expected label appears anywhere in the fired set (engine identified it).
        match = _matches(top, case["human_label"]) or (
            not _is_no_action(case["human_label"]) and _norm(case["human_label"]) in {_norm(f) for f in fired}
        )
        if resolved:
            n_symbolic_resolved += 1
        if match:
            n_symbolic_match += 1
        rows.append(
            {
                "case_id": case["case_id"],
                "symbolic_resolved": resolved,
                "symbolic_conclusion": top,
                "all_fired": fired,
                "human_label": case["human_label"],
                "symbolic_match": match,
            }
        )

    n = len(cases)
    aggregates = {
        "n_cases": n,
        "pct_symbolic_resolved": round(100 * n_symbolic_resolved / n, 1),
        "symbolic_accuracy_vs_human": round(n_symbolic_match / n, 3),
        "n_symbolic_resolved": n_symbolic_resolved,
        "n_symbolic_match": n_symbolic_match,
        "sales_rules_loaded": len(pkg.ruleset.rules),
    }
    return {"mode": "preflight", "rows": rows, "aggregates": aggregates}


# ─────────────────────────────────────────────────────────────────────────────
# Full 3-way run: GeniOS decide() + raw Sonnet + human label
# ─────────────────────────────────────────────────────────────────────────────


def run_full(cases: list[dict[str, Any]], org_id: str) -> dict[str, Any]:
    # Heavy imports kept local so --preflight never needs anthropic / a DB.
    from core.foundations.db import get_session
    from core.modules_framework.bootstrap import _DEFAULT_NEURAL_SYSTEM_PROMPT, _decide_with_retry
    from core.modules_framework.loader import load_module_package
    from core.neural.client import LLMCall, LLMClient
    from core.neural.cost_guard import CostGuard
    from core.neural.gateway import Gateway

    pkg = load_module_package(SALES_ROOT)
    system_prompt = getattr(pkg.manifest, "neural_prompt", None) or _DEFAULT_NEURAL_SYSTEM_PROMPT
    client = LLMClient()  # raises early if ANTHROPIC_API_KEY is missing
    allowed = _allowed_labels(cases)

    sonnet_sys = (
        "You are a B2B SaaS sales analyst. Given a set of facts about a deal, output a "
        "single short conclusion label. Choose from this allowed set when one fits: "
        f"{allowed}. If no action is needed, output an empty string. "
        "Output ONLY the label, nothing else."
    )

    rows: list[dict[str, Any]] = []
    n_symbolic_resolved = n_genios_match = n_sonnet_match = n_derivation = 0
    sonnet_cost = 0.0
    sonnet_latency = 0

    for idx, case in enumerate(cases, start=1):
        case_id = case["case_id"]
        human = case["human_label"]

        # --- 1) GeniOS decide() (real engine path) ---
        g_conclusion = g_route = g_path = ""
        g_conf = 0.0
        g_deriv = False
        g_error: str | None = None
        try:
            with get_session() as session:
                gateway = Gateway(llm=LLMClient(), cost_guard=CostGuard())
                result = _decide_with_retry(
                    session=session,
                    gateway=gateway,
                    ruleset=pkg.ruleset,
                    org_id=org_id,
                    query={"question": case.get("scenario", ""), "case_id": case_id},
                    facts=case["facts"],
                    user_id=None,
                    module_id="sales",
                    gap_desc=case.get("scenario") or "Decide the sales situation from the facts",
                    system_prompt=system_prompt,
                )
            g_conclusion = result.conclusion
            g_route = result.route.value if hasattr(result.route, "value") else str(result.route)
            g_path = result.path
            g_conf = round(result.confidence, 3)
            g_deriv = bool(result.proof and result.proof.steps)
        except Exception as e:  # noqa: BLE001 — one bad case must not kill the run
            g_error = str(e)[:200]

        # --- 2) raw Sonnet baseline ---
        s_conclusion = ""
        s_error: str | None = None
        try:
            resp = client.call(
                LLMCall(
                    model="sonnet",
                    system_prompt=sonnet_sys,
                    user_prompt=f"Facts: {json.dumps(case['facts'])}",
                    max_tokens=32,
                    temperature=0.0,
                    org_id="section7",
                    purpose="sonnet_baseline",
                )
            )
            s_conclusion = resp.text.strip().strip("'\"")
            sonnet_cost += resp.cost_usd
            sonnet_latency += resp.latency_ms
        except Exception as e:  # noqa: BLE001
            s_error = str(e)[:200]

        symbolic_resolved = g_path == "symbolic"
        g_match = g_error is None and _matches(g_conclusion, human)
        s_match = s_error is None and _matches(s_conclusion, human)

        if symbolic_resolved:
            n_symbolic_resolved += 1
        if g_match:
            n_genios_match += 1
        if s_match:
            n_sonnet_match += 1
        if g_deriv:
            n_derivation += 1

        rows.append(
            {
                "case_id": case_id,
                "symbolic_resolved": symbolic_resolved,
                "genios_path": g_path,
                "genios_conclusion": g_conclusion,
                "genios_route": g_route,
                "genios_confidence": g_conf,
                "derivation_present": g_deriv,
                "sonnet_conclusion": s_conclusion,
                "human_label": human,
                "genios_match": g_match,
                "sonnet_match": s_match,
                "genios_error": g_error,
                "sonnet_error": s_error,
            }
        )
        print(f"  [{idx}/{len(cases)}] {case_id}: "
              f"engine={g_conclusion or '∅'}({g_path}) sonnet={s_conclusion or '∅'} human={human or '∅'}",
              flush=True)

    n = len(cases)
    aggregates = {
        "n_cases": n,
        "pct_symbolic_resolved": round(100 * n_symbolic_resolved / n, 1),
        "genios_accuracy_vs_human": round(n_genios_match / n, 3),
        "sonnet_accuracy_vs_human": round(n_sonnet_match / n, 3),
        "genios_minus_sonnet_pp": round(100 * (n_genios_match - n_sonnet_match) / n, 1),
        "derivation_present_count": n_derivation,
        "n_symbolic_resolved": n_symbolic_resolved,
        "n_genios_match": n_genios_match,
        "n_sonnet_match": n_sonnet_match,
        "sonnet_cost_usd": round(sonnet_cost, 4),
        "sonnet_latency_ms_total": sonnet_latency,
        "genios_engine_cost_note": "symbolic cases cost $0; gap-fill cases cost ~1 Haiku call each",
    }
    return {"mode": "full", "org_id": org_id, "rows": rows, "aggregates": aggregates}


# ─────────────────────────────────────────────────────────────────────────────
# Reporting
# ─────────────────────────────────────────────────────────────────────────────


def _print_report(out: dict[str, Any]) -> None:
    agg = out["aggregates"]
    print("\n" + "=" * 70)
    if out["mode"] == "preflight":
        print("§7 PREFLIGHT (symbolic-only — no LLM, no cost)")
        print("=" * 70)
        print(f"  cases:                    {agg['n_cases']}")
        print(f"  sales rules loaded:       {agg['sales_rules_loaded']}")
        print(f"  % symbolic-resolved:      {agg['pct_symbolic_resolved']}%   <- the 80/20 read")
        print(f"  symbolic accuracy:        {agg['symbolic_accuracy_vs_human']}  "
              f"({agg['n_symbolic_match']}/{agg['n_cases']} vs human)")
        print("\n  NOTE: this is the cheap pre-check. Run the full 3-way mode")
        print("  (needs ANTHROPIC_API_KEY + DB) for the GeniOS-vs-Sonnet result.")
    else:
        print("§7 FULL RESULT — GeniOS vs. raw Sonnet vs. human label")
        print("=" * 70)
        print(f"  cases:                    {agg['n_cases']}")
        print(f"  % symbolic-resolved:      {agg['pct_symbolic_resolved']}%   <- the 80/20 test")
        print(f"  GeniOS accuracy:          {agg['genios_accuracy_vs_human']}  "
              f"({agg['n_genios_match']}/{agg['n_cases']})")
        print(f"  Sonnet accuracy:          {agg['sonnet_accuracy_vs_human']}  "
              f"({agg['n_sonnet_match']}/{agg['n_cases']})")
        print(f"  GeniOS − Sonnet:          {agg['genios_minus_sonnet_pp']:+} pp")
        print(f"  derivation chains:        {agg['derivation_present_count']}/{agg['n_cases']} "
              f"(explainability — Sonnet has 0)")
        print(f"  Sonnet cost:              ${agg['sonnet_cost_usd']}")
    print("=" * 70)
    print("Compare these against your PRE-REGISTERED thresholds. This script")
    print("reports numbers only — it does not pass/fail. No moving goalposts.\n")


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="§7 falsifiable-experiment harness")
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES,
                        help="path to real_cases.jsonl (default: modules/sales/golden/real_cases.jsonl)")
    parser.add_argument("--preflight", action="store_true",
                        help="symbolic-only check — no DB, no API key, no cost")
    parser.add_argument("--org-id", default="genios-eval",
                        help="org_id to run decide() under (full mode only)")
    parser.add_argument("--out", type=Path, default=None,
                        help="write full results JSON to this path")
    args = parser.parse_args(argv)

    cases = _load_cases(args.cases)
    print(f"Loaded {len(cases)} case(s) from {args.cases}")

    if args.preflight:
        out = run_preflight(cases)
    else:
        out = run_full(cases, args.org_id)

    _print_report(out)

    out_path = args.out or (args.cases.parent / f"section7_{out['mode']}_results.json")
    out_path.write_text(json.dumps(out, indent=2, default=str), "utf-8")
    print(f"Wrote results → {out_path}")


if __name__ == "__main__":
    main()
