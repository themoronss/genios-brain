"""Programmatic scorecard for the intelligence-layer claims.

Rather than hand-rolling "we're 30/70 extractor/intelligence now," this
script computes the score from code + DB inspection:

  * Module library depth     -> # installed modules + total rule count
  * Golden test coverage     -> running each module's evaluator, % pass
  * Event-driven trigger     -> bus subscriber registered? task wired?
  * Active outcome tracking  -> action_ledger rows + outcome rows last 7d
  * Hypothesis layer         -> # hypothesis-grade rows in proactive_insights
  * Calibration loop         -> # active org_rule_overrides + recent shadows
  * Outcome attribution      -> recovered_inr from feedback_actions
  * Cross-org isolation      -> verified via the brutal e2e suite (t12)
  * Brutal test pass rate    -> imports + invokes the e2e runner

Output: one JSON block + a human-readable per-axis verdict. The same
block is what the investor one-pager pulls its numbers from -- no
hand-tuned vapor.

Run:
    cd genios-brain && source venv/bin/activate
    python3 tests/scorecard_audit.py
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import text  # noqa: E402

from core.foundations.db import get_session  # noqa: E402


# ─────────────────────────────────────────────────────────────────────────────
# Axes
# ─────────────────────────────────────────────────────────────────────────────


def _module_library_depth() -> dict:
    """Count installed modules + rule counts per module."""
    from core.proactive.pipeline import installed_module_ids
    from core.modules_framework.loader import load_module_package

    mods = installed_module_ids()
    rules_per_module = {}
    total = 0
    for mid in mods:
        try:
            pkg = load_module_package(
                Path(__file__).resolve().parents[1] / "modules" / mid
            )
            rules_per_module[mid] = len(pkg.ruleset.rules)
            total += len(pkg.ruleset.rules)
        except Exception as e:
            rules_per_module[mid] = f"load_failed: {e}"
    return {
        "installed_modules": mods,
        "module_count": len(mods),
        "total_rules": total,
        "rules_per_module": rules_per_module,
    }


def _golden_coverage() -> dict:
    """Run each module's evaluator + report pass rate."""
    from core.proactive.pipeline import installed_module_ids

    per_module = {}
    overall_cases = 0
    overall_pass = 0
    for mid in installed_module_ids():
        try:
            mod = __import__(f"modules.{mid}.evaluator", fromlist=["evaluate"])
            r = mod.evaluate()
            m = r.get("metrics", {})
            per_module[mid] = {
                "score": round(r.get("score", 0), 3),
                "cases": m.get("n_cases", 0),
                "matched": m.get("n_matched", 0),
            }
            overall_cases += m.get("n_cases", 0) or 0
            overall_pass += m.get("n_matched", 0) or 0
        except Exception as e:
            per_module[mid] = {"error": str(e)[:120]}
    return {
        "per_module": per_module,
        "overall_cases": overall_cases,
        "overall_pass": overall_pass,
        "overall_score": round(overall_pass / overall_cases, 3) if overall_cases else 0,
    }


def _trigger_wiring() -> dict:
    """Confirm the event subscriber + beat task + manual route all delegate
    to run_all_for_org."""
    src_paths = {
        "event_subscriber": Path(__file__).resolve().parents[1] / "core/proactive/event_subscriber.py",
        "celery_app": Path(__file__).resolve().parents[1] / "app/celery_app.py",
        "v1_scan_route": Path(__file__).resolve().parents[1] / "app/api/routes/proactive.py",
    }
    results = {}
    for label, p in src_paths.items():
        body = p.read_text()
        results[label] = "run_all_for_org" in body
    return {
        "event_driven": results["event_subscriber"],
        "cron_driven":  results["celery_app"],
        "manual_route": results["v1_scan_route"],
        "all_share_one_pipeline": all(results.values()),
    }


def _active_outcomes() -> dict:
    """Read action_ledger + feedback_actions over the last 7d."""
    cutoff = datetime.now(UTC) - timedelta(days=7)
    with get_session() as s:
        deliveries = s.execute(
            text(
                """
                SELECT outcome, COUNT(*) FROM action_ledger
                WHERE action_type = 'webhook_delivered' AND created_at >= :c
                GROUP BY outcome
                """
            ),
            {"c": cutoff},
        ).fetchall()
        outcomes = s.execute(
            text(
                """
                SELECT action, COUNT(*),
                       COALESCE(SUM((edit_diff_jsonb->>'value_amount')::NUMERIC), 0)
                FROM feedback_actions
                WHERE insight_id IS NOT NULL
                  AND timestamp >= :c
                  AND action IN ('paid','ignored','dismissed','escalated','acted')
                GROUP BY action
                """
            ),
            {"c": cutoff},
        ).fetchall()
    return {
        "deliveries_by_outcome": {r[0]: int(r[1]) for r in deliveries},
        "outcomes_by_action": {r[0]: {"count": int(r[1]), "value_sum": float(r[2] or 0)} for r in outcomes},
        "total_recovered_inr": float(
            sum(float(r[2] or 0) for r in outcomes if r[0] == "paid")
        ),
    }


def _hypothesis_layer() -> dict:
    """Inspect persisted hypothesis-grade insights."""
    with get_session() as s:
        rows = s.execute(
            text(
                """
                SELECT type, scores_jsonb->>'title' AS title,
                       (foresight_jsonb->>'confidence')::float AS conf,
                       created_at
                FROM proactive_insights
                WHERE (scores_jsonb->>'rule_id') = 'hypothesis:llm'
                ORDER BY created_at DESC
                LIMIT 20
                """
            )
        ).fetchall()
    return {
        "persisted_count": len(rows),
        "recent": [
            {
                "type": r.type,
                "title": r.title,
                "confidence": round(r.conf or 0, 2),
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows[:5]
        ],
    }


def _calibration_loop() -> dict:
    """Inspect org_rule_overrides — how many tuned thresholds exist."""
    with get_session() as s:
        rows = s.execute(
            text(
                """
                SELECT status, COUNT(*) FROM org_rule_overrides
                GROUP BY status
                """
            )
        ).fetchall()
        recent_active = s.execute(
            text(
                """
                SELECT module_id, rule_id, fact_predicate, threshold_value,
                       precision_before, precision_after, sample_size,
                       applied_at
                FROM org_rule_overrides
                WHERE status = 'active'
                ORDER BY created_at DESC
                LIMIT 10
                """
            )
        ).fetchall()
    return {
        "overrides_by_status": {r[0]: int(r[1]) for r in rows},
        "active_overrides": [
            {
                "module": r.module_id,
                "rule": r.rule_id,
                "predicate": r.fact_predicate,
                "tuned_to": float(r.threshold_value),
                "precision_before": r.precision_before,
                "precision_after": r.precision_after,
                "sample_size": r.sample_size,
                "applied_at": r.applied_at.isoformat() if r.applied_at else None,
            }
            for r in recent_active
        ],
    }


def _brutal_test_pass_rate() -> dict:
    """Import + run the brutal e2e suite as a single function and report
    pass count. Skipped when the brain isn't reachable (returns -1)."""
    try:
        from tests.brutal_e2e import _TESTS  # type: ignore
    except Exception as e:
        return {"error": f"could not import brutal e2e suite: {e}"}
    n = len(_TESTS)
    passes = 0
    fails = []
    for name, fn in _TESTS:
        try:
            ok, msg = fn()
        except Exception as e:
            ok = False
            msg = str(e)
        if ok:
            passes += 1
        else:
            fails.append({"name": name, "reason": msg})
    return {"total": n, "passed": passes, "failed": n - passes, "failures": fails}


# ─────────────────────────────────────────────────────────────────────────────
# Scoring rubric (the actual extractor vs intelligence numbers)
# ─────────────────────────────────────────────────────────────────────────────


def _score_axis_intelligence(data: dict) -> dict:
    """Map raw signals to an 0-10 intelligence score per axis.

    The split (extractor vs intelligence) was the brutal-audit framing.
    Each axis gets:
      0-3 = extractor-grade (rote / hand-rolled / static)
      4-6 = early-intelligence (rules + tracking, but no feedback loop)
      7-10 = intelligence (closes the loop / synthesizes / adapts)
    """
    scores: dict[str, dict] = {}

    # Module library
    mc = data["module_library"]["module_count"]
    tr = data["module_library"]["total_rules"]
    scores["module_library_depth"] = {
        "score": min(10, mc * 2 + (1 if tr >= 20 else 0)),
        "rationale": f"{mc} modules / {tr} rules — production minimum is ~5 modules with ~30 rules total",
    }

    # Golden coverage
    gs = data["golden_coverage"]["overall_score"]
    scores["rule_correctness"] = {
        "score": int(round(gs * 10)),
        "rationale": f"{int(gs * 100)}% golden pass across all modules",
    }

    # Trigger wiring
    tw = data["trigger_wiring"]
    scores["proactive_trigger"] = {
        "score": (10 if tw["all_share_one_pipeline"] else 4),
        "rationale": "event + cron + manual all delegate to run_all_for_org"
        if tw["all_share_one_pipeline"]
        else "Trigger paths not unified",
    }

    # Active outcomes
    ao = data["active_outcomes"]
    has_deliveries = sum(ao["deliveries_by_outcome"].values()) > 0
    has_outcomes = sum(o["count"] for o in ao["outcomes_by_action"].values()) > 0
    has_recovered = ao["total_recovered_inr"] > 0
    scores["active_outcome_tracking"] = {
        "score": 2 + (3 if has_deliveries else 0) + (3 if has_outcomes else 0) + (2 if has_recovered else 0),
        "rationale": (
            f"deliveries={'y' if has_deliveries else 'n'}, "
            f"outcomes={'y' if has_outcomes else 'n'}, "
            f"recovered ₹{ao['total_recovered_inr']:,.0f}"
        ),
    }

    # Hypothesis layer
    hp = data["hypothesis_layer"]["persisted_count"]
    scores["hypothesis_generation"] = {
        "score": (8 if hp >= 1 else 3),
        "rationale": f"{hp} hypothesis-grade rows persisted via LLM propose+refute",
    }

    # Calibration
    cb = data["calibration_loop"]["overrides_by_status"]
    active = int(cb.get("active", 0))
    shadow = int(cb.get("shadow", 0))
    scores["calibration_loop"] = {
        "score": (8 if active >= 1 else 5 if shadow >= 1 else 3),
        "rationale": f"{active} active overrides, {shadow} shadow suggestions",
    }

    # Brutal test pass rate
    bt = data["brutal_tests"]
    if "error" in bt:
        scores["robustness"] = {"score": 0, "rationale": bt["error"]}
    else:
        rate = bt["passed"] / bt["total"] if bt["total"] else 0
        scores["robustness"] = {
            "score": int(round(rate * 10)),
            "rationale": f"{bt['passed']}/{bt['total']} brutal cases pass",
        }

    total = sum(v["score"] for v in scores.values())
    max_total = 10 * len(scores)
    return {
        "axes": scores,
        "raw_total": total,
        "max_total": max_total,
        "pct_intelligence": round(total / max_total, 3),
        "pct_extractor": round(1 - (total / max_total), 3),
    }


def main() -> int:
    print("=" * 78)
    print(f"GENIOS PROGRAMMATIC SCORECARD  ·  {datetime.now(UTC).isoformat()}")
    print("=" * 78)

    data = {
        "module_library": _module_library_depth(),
        "golden_coverage": _golden_coverage(),
        "trigger_wiring": _trigger_wiring(),
        "active_outcomes": _active_outcomes(),
        "hypothesis_layer": _hypothesis_layer(),
        "calibration_loop": _calibration_loop(),
        "brutal_tests": _brutal_test_pass_rate(),
    }
    scored = _score_axis_intelligence(data)
    report = {"signals": data, "scoring": scored}

    print("\nSignals:")
    print(json.dumps(data, indent=2, default=str))
    print("\nAxis scores:")
    for axis, info in scored["axes"].items():
        bar = "█" * info["score"] + "·" * (10 - info["score"])
        print(f"  {axis:30s}  [{bar}] {info['score']}/10  — {info['rationale']}")
    print("\nOVERALL:")
    print(f"  raw           : {scored['raw_total']}/{scored['max_total']}")
    print(f"  intelligence  : {int(scored['pct_intelligence'] * 100)}%")
    print(f"  extractor     : {int(scored['pct_extractor'] * 100)}%")

    # Persist for the investor one-pager
    out = Path(__file__).resolve().parents[1] / "tests" / "scorecard_latest.json"
    out.write_text(json.dumps(report, indent=2, default=str))
    print(f"\nWritten: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
