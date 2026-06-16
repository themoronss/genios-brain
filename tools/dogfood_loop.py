"""Full-loop dogfood verification — GATE 2 of GENIOS_BRIEFING_CTO_AND_AGENT.md (§5, §8 Task 3).

Pushes ONE real dataset through the whole machine and proves the learning loop
actually turns over on reality (not sample_data/ CSVs):

    ingest CSV  ->  graph  ->  rules  ->  insight + webhook  ->  human correction
    ->  Bayesian edge update  ->  intervention_metrics

The four checks (MD acceptance — all four must pass on REAL input):
    1. INGEST       a real CSV lands facts in the graph
    2. INSIGHT      run_for_org fires proactive insights (+ webhook if registered)
    3. CORRECTION   a human thumbs-down/edit writes a correction AND the Bayesian
                    edge update fires (graph_edges alpha/beta actually move)
    4. METRICS      intervention_metrics gets a real row (north-star becomes measurable)

Why this matters: per the brief, "the learning loop has, to date, never turned
over once." Check 3 is the one that proves the moat machinery works — and it
exercises the feedback_capture edge-outcome path that was previously broken
(edit_diff edges never reached learning.derive_outcomes).

Runs against the REAL database (get_session) — like tests/brutal_e2e.py, NOT a
sqlite unit test. Requirements:
    - DATABASE_URL configured (a real/staging Postgres)
    - a real CSV (founder supplies; see tools/dogfood_sample.template.csv)
    - ANTHROPIC_API_KEY only for check 3 (it mints a decision via decide());
      use --skip-corrections to run checks 1, 2, 4 without a key.

Usage:
    python -m tools.dogfood_loop --org-id <org> --csv path/to/real.csv
    python -m tools.dogfood_loop --org-id <org> --csv path/to/real.csv --skip-corrections
    python -m tools.dogfood_loop --org-id <org> --csv path/to/real.csv --module-id ar_collection
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

CheckResult = tuple[bool, str]


# ─────────────────────────────────────────────────────────────────────────────
# Check 1 — ingest a real CSV into the graph
# ─────────────────────────────────────────────────────────────────────────────


def check_ingest(org_id: str, csv_path: Path) -> CheckResult:
    from sqlalchemy import text

    from core.foundations.db import get_session
    from core.resources.uploads import UploadInput, create_upload

    raw = csv_path.read_bytes()
    with get_session() as s:
        before = s.execute(
            text("SELECT COUNT(*) FROM facts WHERE org_id = :o"), {"o": org_id}
        ).scalar() or 0
        row = create_upload(
            s,
            org_id=org_id,
            actor_email="dogfood@genios",
            upload=UploadInput(file_name=csv_path.name, file_type="csv", raw=raw, tag="dogfood"),
        )
    with get_session() as s:
        after = s.execute(
            text("SELECT COUNT(*) FROM facts WHERE org_id = :o"), {"o": org_id}
        ).scalar() or 0

    if row.get("status") == "failed":
        return False, f"upload failed: {row.get('error')}"
    gained = after - before
    if gained <= 0:
        return False, f"upload status={row.get('status')} but facts did not grow ({before}->{after})"
    return True, f"ingested {row.get('rows', '?')} rows -> facts {before}->{after} (+{gained})"


# ─────────────────────────────────────────────────────────────────────────────
# Check 2 — proactive insights + webhook
# ─────────────────────────────────────────────────────────────────────────────


def check_insights(org_id: str, module_id: str) -> CheckResult:
    from core.foundations.db import get_session
    from core.proactive.pipeline import run_for_org

    with get_session() as s:
        result = run_for_org(s, org_id=org_id, module_id=module_id, source="dogfood")
        s.commit()

    fired = result.get("insights_fired", 0)
    hooks = result.get("webhooks_called", 0)
    ok_hooks = result.get("webhook_success", 0)
    if fired <= 0:
        return False, (
            f"0 insights fired (evaluated={result.get('invoices_evaluated')}, "
            f"candidates={result.get('candidates')}, suppressed={result.get('suppressed_dedupe')}). "
            "If this is a re-run, the 24h dedupe may have suppressed everything."
        )
    return True, f"{fired} insight(s) fired; webhooks called={hooks} success={ok_hooks}"


# ─────────────────────────────────────────────────────────────────────────────
# Check 3 — correction -> Bayesian edge update (the loop turning over)
# ─────────────────────────────────────────────────────────────────────────────


def check_corrections(org_id: str, n_corrections: int = 5) -> CheckResult:
    from sqlalchemy import text

    from core.delivery.feedback_capture import FeedbackAction, capture_feedback
    from core.foundations.db import get_session
    from core.worldmodel.learning import apply_correction
    from core.worldmodel.store import CorrectionRow

    # Need real graph edges to contradict, and a decision to attach feedback to.
    with get_session() as s:
        edges = s.execute(
            text("SELECT id, alpha, beta FROM graph_edges WHERE org_id = :o ORDER BY id LIMIT :n"),
            {"o": org_id, "n": n_corrections},
        ).fetchall()
    if not edges:
        return False, (
            "no graph_edges for this org — ingest data that builds relationships first "
            "(symbolic-only insights create no edges, so there's nothing to learn on)."
        )

    decision_id = _mint_decision(org_id)
    if decision_id is None:
        return False, "could not mint a decision to attach corrections to (need ANTHROPIC_API_KEY)"

    before = {e[0]: (e[1], e[2]) for e in edges}
    corrections_written = 0
    edges_moved = 0
    with get_session() as s:
        for edge_id, _a, _b in edges:
            out = capture_feedback(
                s,
                org_id=org_id,
                user_id="dogfood-human",
                decision_id=decision_id,
                insight_id=None,
                action=FeedbackAction.EDIT,
                edit_diff={"edges_contradicted": [edge_id]},
            )
            if out.correction_id:
                corrections_written += 1
                corr = s.get(CorrectionRow, out.correction_id)
                if corr is not None:
                    apply_correction(s, correction=corr)
        s.commit()

    with get_session() as s:
        after_rows = s.execute(
            text("SELECT id, alpha, beta FROM graph_edges WHERE id = ANY(:ids)"),
            {"ids": list(before.keys())},
        ).fetchall()
    for edge_id, a, b in after_rows:
        if (a, b) != before.get(edge_id):
            edges_moved += 1

    if corrections_written < n_corrections:
        return False, f"only {corrections_written}/{n_corrections} corrections written"
    if edges_moved == 0:
        return False, (
            f"{corrections_written} corrections written but NO graph_edge alpha/beta moved — "
            "the Bayesian learning loop did not turn over (Gate 2 NOT met)."
        )
    return True, f"{corrections_written} corrections written; {edges_moved} graph_edge(s) updated (alpha/beta moved)"


def _mint_decision(org_id: str) -> str | None:
    """Run one real decide() (sales) to get a decision_id for corrections.
    Returns None if no ANTHROPIC_API_KEY (Gateway needs it)."""
    try:
        from core.foundations.db import get_session
        from core.modules_framework.bootstrap import _DEFAULT_NEURAL_SYSTEM_PROMPT, _decide_with_retry
        from core.modules_framework.loader import load_module_package
        from core.neural.client import LLMClient
        from core.neural.cost_guard import CostGuard
        from core.neural.gateway import Gateway

        sales_root = Path(__file__).resolve().parents[1] / "modules" / "sales"
        pkg = load_module_package(sales_root)
        system_prompt = getattr(pkg.manifest, "neural_prompt", None) or _DEFAULT_NEURAL_SYSTEM_PROMPT
        with get_session() as s:
            gateway = Gateway(llm=LLMClient(), cost_guard=CostGuard())
            result = _decide_with_retry(
                session=s,
                gateway=gateway,
                ruleset=pkg.ruleset,
                org_id=org_id,
                query={"question": "dogfood loop decision", "case_id": "dogfood_001"},
                facts={"usage_drop_pct_30d": 70, "days_since_last_contact": 21},
                user_id=None,
                module_id="sales",
                gap_desc="Decide the sales situation from the facts",
                system_prompt=system_prompt,
            )
            s.commit()
            return result.decision_id
    except Exception as e:  # noqa: BLE001 — surfaced as a skipped check, not a crash
        print(f"  (decision mint failed: {str(e)[:160]})", flush=True)
        return None


# ─────────────────────────────────────────────────────────────────────────────
# Check 4 — intervention_metrics populates (north-star becomes measurable)
# ─────────────────────────────────────────────────────────────────────────────


def check_metrics(org_id: str, module_id: str) -> CheckResult:
    from datetime import UTC, datetime

    from core.foundations.db import get_session
    from core.foundations.intervention_rate import rollup_day

    today = datetime.now(UTC).date()
    with get_session() as s:
        row = rollup_day(s, org_id=org_id, module_id=module_id, on_date=today)
        s.commit()
        total = row.total_decisions
        rate = row.intervention_rate
        overrides = row.human_overrides_count
    if total <= 0:
        return False, (
            f"intervention_metrics row written but total_decisions=0 for {module_id} on {today} "
            "(no decisions flowed through this module today — run check 3 / make decisions first)."
        )
    return True, (
        f"intervention_metrics row: total_decisions={total}, human_overrides={overrides}, "
        f"intervention_rate={rate}"
    )


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Full-loop dogfood verification (Gate 2)")
    parser.add_argument("--org-id", required=True, help="org to run the loop under")
    parser.add_argument("--csv", type=Path, required=True, help="path to a REAL csv to ingest")
    parser.add_argument("--module-id", default="ar_collection", help="proactive module (default ar_collection)")
    parser.add_argument("--skip-corrections", action="store_true",
                        help="skip check 3 (no decide() / no ANTHROPIC_API_KEY needed)")
    args = parser.parse_args(argv)

    if not args.csv.exists():
        print(f"ERROR: csv not found: {args.csv}")
        return 2

    checks: list[tuple[str, CheckResult]] = []
    print(f"Dogfood loop — org={args.org_id} module={args.module_id} csv={args.csv}\n")

    print("[1/4] INGEST ...", flush=True)
    checks.append(("1 INGEST", _safe(check_ingest, args.org_id, args.csv)))

    print("[2/4] INSIGHTS + WEBHOOK ...", flush=True)
    checks.append(("2 INSIGHT", _safe(check_insights, args.org_id, args.module_id)))

    if args.skip_corrections:
        checks.append(("3 CORRECTION", (False, "skipped (--skip-corrections)")))
    else:
        print("[3/4] CORRECTION -> BAYESIAN EDGE UPDATE ...", flush=True)
        checks.append(("3 CORRECTION", _safe(check_corrections, args.org_id)))

    print("[4/4] INTERVENTION_METRICS ...", flush=True)
    checks.append(("4 METRICS", _safe(check_metrics, args.org_id, args.module_id)))

    print("\n" + "=" * 70)
    print("GATE 2 — full-loop dogfood result")
    print("=" * 70)
    all_pass = True
    for name, (ok, msg) in checks:
        mark = "PASS" if ok else ("SKIP" if "skipped" in msg else "FAIL")
        if not ok and mark == "FAIL":
            all_pass = False
        print(f"  [{mark}] {name}: {msg}")
    print("=" * 70)
    print("Gate 2 is MET only when all four pass on REAL (not sample_data/) input.\n")
    return 0 if all_pass else 1


def _safe(fn, *fn_args) -> CheckResult:
    try:
        return fn(*fn_args)
    except Exception as e:  # noqa: BLE001 — a check failing must not abort the run
        return False, f"error: {str(e)[:200]}"


if __name__ == "__main__":
    sys.exit(main())
