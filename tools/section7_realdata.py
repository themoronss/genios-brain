"""§7 on REAL data — GeniOS engine vs raw Sonnet vs real Won/Lost outcomes.

Uses the public Maven "CRM Sales Opportunities" dataset (real B2B deals with
real Won/Lost outcomes). The only NON-LEAKY real signal is the deal cycle length
(close_date - engage_date) — close_value is excluded because it's 0 for every
Lost deal (that would be outcome leakage).

Task: from the real deal facts, predict whether the deal is AT RISK (Lost) or
HEALTHY (Won), three ways on identical inputs:
  1. GeniOS  — symbolic ForwardChainer (any rule fires => at_risk)
  2. raw Sonnet — one neutral LLM call
  3. ground truth — the real Won/Lost outcome

This is a PARTIAL §7: Maven only exposes cycle length, so it tests the
velocity/aging dimension on real outcomes — not churn/pricing/qualification
(those fields don't exist in any public dataset). Honest about that.

Run:  python -m tools.section7_realdata --n 40
Needs ANTHROPIC_API_KEY (in .env). Costs ~$ for N Sonnet calls. No DB writes.
"""

from __future__ import annotations

import argparse
import csv
from datetime import date

CSV_PATH = "/tmp/maven_sales.csv"


def _age_days(engage: str, close: str) -> int | None:
    try:
        y1, m1, d1 = map(int, engage.split("-"))
        y2, m2, d2 = map(int, close.split("-"))
        return (date(y2, m2, d2) - date(y1, m1, d1)).days
    except Exception:
        return None


def _load_balanced(n: int) -> list[dict]:
    rows = list(csv.DictReader(open(CSV_PATH)))
    won, lost = [], []
    for r in rows:
        if r["deal_stage"] not in ("Won", "Lost"):
            continue
        age = _age_days(r["engage_date"], r["close_date"])
        if age is None or age < 0:
            continue
        rec = {"id": r["opportunity_id"], "age": age, "outcome": r["deal_stage"]}
        (won if r["deal_stage"] == "Won" else lost).append(rec)
    half = n // 2
    # deterministic, evenly spaced sample across the cycle-length range
    won.sort(key=lambda x: x["age"]); lost.sort(key=lambda x: x["age"])
    def spaced(lst, k):
        if len(lst) <= k:
            return lst
        step = len(lst) / k
        return [lst[int(i * step)] for i in range(k)]
    return spaced(won, half) + spaced(lost, n - half)


def _genios_symbolic(age: int) -> str:
    """Engine's symbolic verdict on the real facts. at_risk if any rule fires."""
    import sys
    from pathlib import Path
    sys.path.insert(0, ".")
    from core.modules_framework.loader import load_module_package
    from core.reasoning.rule_engine import ForwardChainer
    pkg = load_module_package(Path("modules/sales"))
    chainer = ForwardChainer(pkg.ruleset)
    # Only non-leaky real fact + an in-flight stage assumption (applied equally
    # to the LLM via the prompt). deal_aging_overall fires when age>90.
    facts = {"deal_age_days": age, "stage": "negotiation"}
    result = chainer.run(facts)
    fired = [s.conclusion for s in result.proof.steps]
    return "at_risk" if fired else "healthy"


def _sonnet(age: int, client) -> str:
    from core.neural.client import LLMCall
    resp = client.call(LLMCall(
        model="sonnet",
        system_prompt=(
            "You are a B2B sales analyst. Given a deal's facts, judge whether it is "
            "AT RISK of being lost or HEALTHY (likely to close). Reply with EXACTLY "
            "one word: at_risk or healthy."
        ),
        user_prompt=f"Deal has been in negotiation for {age} days. at_risk or healthy?",
        max_tokens=8, temperature=0.0, org_id="section7", purpose="realdata_baseline",
    ))
    t = resp.text.strip().lower()
    return "at_risk" if "at_risk" in t or "risk" in t else "healthy"


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=40, help="balanced sample size (half Won, half Lost)")
    args = ap.parse_args(argv)

    cases = _load_balanced(args.n)
    print(f"Loaded {len(cases)} REAL deals (balanced Won/Lost) from Maven dataset\n")

    from core.neural.client import LLMClient
    client = LLMClient()

    g_correct = s_correct = g_fire = 0
    g_tp = g_fp = g_fn = 0  # GeniOS at_risk vs Lost
    s_tp = s_fp = s_fn = 0
    for i, c in enumerate(cases, 1):
        truth = "at_risk" if c["outcome"] == "Lost" else "healthy"
        g = _genios_symbolic(c["age"])
        s = _sonnet(c["age"], client)
        if g == "at_risk":
            g_fire += 1
        if g == truth:
            g_correct += 1
        if s == truth:
            s_correct += 1
        if truth == "at_risk":
            g_tp += g == "at_risk"; g_fn += g == "healthy"
            s_tp += s == "at_risk"; s_fn += s == "healthy"
        else:
            g_fp += g == "at_risk"; s_fp += s == "at_risk"
        print(f"  [{i}/{len(cases)}] age={c['age']:>4}d outcome={c['outcome']:<5} "
              f"genios={g:<8} sonnet={s}", flush=True)

    n = len(cases)
    def f1(tp, fp, fn):
        p = tp / (tp + fp) if (tp + fp) else 0.0
        r = tp / (tp + fn) if (tp + fn) else 0.0
        return round(2 * p * r / (p + r), 3) if (p + r) else 0.0
    print("\n" + "=" * 60)
    print("§7 ON REAL DATA — GeniOS vs raw Sonnet vs Won/Lost")
    print("=" * 60)
    print(f"  deals:                 {n} (balanced)")
    print(f"  GeniOS fired (at_risk): {g_fire}/{n}")
    print(f"  GeniOS accuracy:        {g_correct/n:.3f}   (F1 on at_risk: {f1(g_tp,g_fp,g_fn)})")
    print(f"  Sonnet accuracy:        {s_correct/n:.3f}   (F1 on at_risk: {f1(s_tp,s_fp,s_fn)})")
    print(f"  delta (GeniOS-Sonnet):  {(g_correct-s_correct)/n*100:+.1f} pp")
    print("=" * 60)
    print("Honest scope: only deal cycle-length was usable from real data")
    print("(value leaks outcome; churn/pricing/MEDDIC fields don't exist publicly).\n")


if __name__ == "__main__":
    main()
