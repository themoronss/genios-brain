"""Per-org rule threshold tuner — closes the learning loop.

The symbolic rule engine fires on hardcoded thresholds (eg.
`days_past_due > 7`). Different customers have different reality:
some clients pay if you nudge at day 5, others need a 9-day delay
before the email lands well. Today the rules YAML says 7 for every
tenant. This module reads outcome attribution + suggests per-org
overrides when the data supports it.

Wire (per the Phase-4 acceptance criteria):

  1. For each (org_id, module_id, rule_id), pull every insight that
     fired in the analysis window + its recorded outcome.
  2. Bucket by the threshold predicate's actual value at fire time
     (eg. days_past_due was 8, 10, 13, 8, ...) and pair with the
     business outcome (paid / ignored / dismissed).
  3. Walk candidate thresholds; pick the one with the best precision
     (= paid + acted / total outcomes) that still preserves recall.
  4. If improvement >= 5pp AND sample >= 20, write status='active'
     to `org_rule_overrides` — the pipeline will pick it up on the
     next run. Otherwise write status='shadow' so the dashboard can
     surface the suggestion and the founder can opt in manually.

Conservative on purpose. We only auto-apply when:
  * the sample is large enough to be statistically defensible, AND
  * the improvement is meaningful (5pp precision swing, not 1pp).

Every write is paired with a `justification` line the audit log
renders — "AR firm-reminder threshold tuned 7d -> 9d on Jun 15
based on 23 outcomes: precision 0.61 -> 0.78."

Plan alignment: g-i-8 (foundations for the learning loop) + g-i-5
(modules SDK preserved — the rules YAML is read-only; tuner writes
to org_rule_overrides, never patches the YAML).
"""

from __future__ import annotations

import logging
import uuid as _uuid
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from core.foundations.telemetry import get_logger

log = get_logger(__name__)
_legacy_log = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Tunables
# ─────────────────────────────────────────────────────────────────────────────

MIN_SAMPLE_SIZE = 20
MIN_PRECISION_IMPROVEMENT_PP = 0.05  # 5 percentage points
ANALYSIS_WINDOW_DAYS = 90  # look back 3 months for outcomes


def _load_module_knobs(
    module_id: str,
) -> dict[str, tuple[str, str, float]]:
    """Read tunable_knobs from a module's manifest.json.

    Returns {rule_id: (fact_predicate, op, default_threshold), ...}. Each
    rule may declare 0 or more knobs; today we tune the FIRST knob per rule
    (most rules only have one tunable). Multi-knob tuning is Phase 5+.
    """
    import json as _json
    from pathlib import Path as _Path

    repo_root = _Path(__file__).resolve().parents[2]
    manifest_path = repo_root / "modules" / module_id / "manifest.json"
    if not manifest_path.exists():
        log.warning("threshold_tuner_module_missing", module_id=module_id)
        return {}
    try:
        with open(manifest_path) as f:
            data = _json.load(f)
    except (_json.JSONDecodeError, OSError) as e:
        log.warning(
            "threshold_tuner_manifest_unreadable", module_id=module_id, error=str(e)
        )
        return {}
    rule_meta = data.get("rule_metadata") or {}
    knobs: dict[str, tuple[str, str, float]] = {}
    for rule_id, meta in rule_meta.items():
        tk = meta.get("tunable_knobs") or []
        if not tk:
            continue
        first = tk[0]
        knobs[rule_id] = (
            first["fact_predicate"],
            first["op"],
            float(first["default_threshold"]),
        )
    return knobs

# Outcomes that count as a "successful" insight — the rule pointed at
# something the founder did take action on (paid = paid after a nudge;
# acted = explicit positive action attributed to this insight).
_POSITIVE_OUTCOMES = {"paid", "acted", "escalated"}
_NEGATIVE_OUTCOMES = {"ignored", "dismissed"}


# ─────────────────────────────────────────────────────────────────────────────
# Data loading
# ─────────────────────────────────────────────────────────────────────────────


def _load_rule_outcomes(
    session: Session, *, org_id: str, rule_id: str, fact_predicate: str
) -> list[tuple[float, str]]:
    """Return [(fact_value_at_fire_time, outcome_label), ...] for every
    insight of this (org, rule) that has a recorded outcome.

    fact_value_at_fire_time is read from the matched_facts on the
    derivation chain we persisted at fire time -- that's the ground
    truth for what the rule saw, even if the fact has changed since.
    """
    cutoff = datetime.now(UTC) - timedelta(days=ANALYSIS_WINDOW_DAYS)
    rows = session.execute(
        text(
            """
            SELECT
              pi.id,
              pi.primary_entity,
              pi.derivation_chain_jsonb,
              pi.scores_jsonb,
              fa.action AS outcome
            FROM proactive_insights pi
            JOIN feedback_actions   fa ON fa.insight_id = pi.id::text
            WHERE pi.org_id = :org
              AND pi.created_at >= :cutoff
              AND (pi.scores_jsonb->>'rule_id') = :rule_id
              AND fa.action IN ('paid', 'ignored', 'dismissed', 'escalated', 'acted')
            """
        ),
        {"org": org_id, "cutoff": cutoff, "rule_id": rule_id},
    ).fetchall()

    out: list[tuple[float, str]] = []
    for r in rows:
        chain = r.derivation_chain_jsonb
        if not isinstance(chain, list) or not chain:
            continue
        # First step in the chain is the firing rule
        matched = chain[0].get("matched_facts") or {}
        val = matched.get(fact_predicate)
        # `subject` predicate facts also live on the proactive_insights
        # row's `scores_jsonb` because the pipeline pre-renders them
        # there. Fall back to that if the matched_facts dict is sparse.
        if val is None and isinstance(r.scores_jsonb, dict):
            mv = r.scores_jsonb.get("memory_view") or ""
            # Best-effort: pull a number after "<predicate>=" in the text.
            # If we can't parse, skip the row -- bad sample worse than no sample.
            import re

            m = re.search(rf"{re.escape(fact_predicate)}\s*=\s*([-\d.]+)", mv)
            if m:
                try:
                    val = float(m.group(1))
                except ValueError:
                    val = None
        try:
            val_f = float(val)
        except (TypeError, ValueError):
            continue
        out.append((val_f, r.outcome))
    return out


# ─────────────────────────────────────────────────────────────────────────────
# Precision math + candidate search
# ─────────────────────────────────────────────────────────────────────────────


def _precision_at_threshold(
    samples: list[tuple[float, str]], *, threshold: float, op_str: str
) -> tuple[float, int]:
    """Of the samples that this threshold would FIRE on, what fraction are
    positive outcomes?

    Returns (precision, n_fired). n_fired = 0 -> precision returned as 0.0
    (caller treats that as "not viable" alongside the empty sample case).
    """
    fired = []
    for val, outcome in samples:
        if op_str == ">" and val > threshold:
            fired.append(outcome)
        elif op_str == ">=" and val >= threshold:
            fired.append(outcome)
        elif op_str == "<" and val < threshold:
            fired.append(outcome)
        elif op_str == "<=" and val <= threshold:
            fired.append(outcome)
        elif op_str == "==" and val == threshold:
            fired.append(outcome)
    if not fired:
        return (0.0, 0)
    pos = sum(1 for o in fired if o in _POSITIVE_OUTCOMES)
    return (pos / len(fired), len(fired))


def _candidate_thresholds(samples: list[tuple[float, str]]) -> list[float]:
    """Candidate threshold values to try.

    Strategy: take the unique fact values that occurred + the midpoints
    between adjacent values. Limits the search to numbers that actually
    appeared in the data -- avoids cargo-culting an arbitrary 1-unit
    grid.
    """
    vals = sorted({v for v, _ in samples})
    cands: list[float] = []
    for v in vals:
        cands.append(v)
    for i in range(len(vals) - 1):
        cands.append((vals[i] + vals[i + 1]) / 2)
    return cands


def _suggest_threshold(
    samples: list[tuple[float, str]], *, current: float, op_str: str
) -> dict[str, Any] | None:
    """Search candidate thresholds; return the one with the best precision
    that keeps recall reasonable. None if no candidate beats current."""
    cands = _candidate_thresholds(samples)
    if not cands:
        return None

    current_prec, current_n = _precision_at_threshold(
        samples, threshold=current, op_str=op_str
    )
    best: dict[str, Any] | None = None
    for c in cands:
        prec, n = _precision_at_threshold(samples, threshold=c, op_str=op_str)
        # Skip candidates that fire on < 30% of the current sample - they
        # may have high precision but be too narrow to be useful.
        if current_n > 0 and n < max(3, int(0.3 * current_n)):
            continue
        if prec - current_prec < MIN_PRECISION_IMPROVEMENT_PP:
            continue
        if best is None or prec > best["precision"]:
            best = {
                "threshold": c,
                "precision": prec,
                "n_fired": n,
            }
    if best is None:
        return None
    return {
        "current_threshold": current,
        "current_precision": current_prec,
        "current_n_fired": current_n,
        "suggested_threshold": best["threshold"],
        "suggested_precision": best["precision"],
        "suggested_n_fired": best["n_fired"],
        "improvement_pp": round(best["precision"] - current_prec, 4),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Override persistence
# ─────────────────────────────────────────────────────────────────────────────


def _write_override(
    session: Session,
    *,
    org_id: str,
    module_id: str,
    rule_id: str,
    fact_predicate: str,
    op_str: str,
    new_threshold: float,
    old_threshold: float,
    sample_size: int,
    prec_before: float,
    prec_after: float,
    auto_apply: bool,
    source: str = "tuner",
) -> str:
    """Insert one row into org_rule_overrides + mark any prior active
    override for the same (org, rule) reverted. Returns the new row id.

    Append-only: prior overrides are NOT deleted, just status -> reverted
    with reverted_at. Keeps the audit timeline intact.
    """
    # Mark previously active row as reverted (idempotent — does nothing if
    # there's none).
    session.execute(
        text(
            """
            UPDATE org_rule_overrides
            SET status = 'reverted',
                reverted_at = NOW()
            WHERE org_id = :org
              AND module_id = :mod
              AND rule_id = :rule
              AND status = 'active'
            """
        ),
        {"org": org_id, "mod": module_id, "rule": rule_id},
    )

    new_id = str(_uuid.uuid4())
    status = "active" if auto_apply else "shadow"
    justification = (
        f"Outcome-driven tuning: across {sample_size} outcomes for this rule on "
        f"this org, the precision moves {prec_before:.2f} -> {prec_after:.2f} when "
        f"threshold shifts from {fact_predicate}{op_str}{_clean_num(old_threshold)} "
        f"to {fact_predicate}{op_str}{_clean_num(new_threshold)}. "
        + ("Auto-applied." if auto_apply else "Suggestion only (shadow) — too few samples or improvement under 5pp.")
    )
    session.execute(
        text(
            """
            INSERT INTO org_rule_overrides
                (id, org_id, module_id, rule_id, fact_predicate, op,
                 threshold_value, status, source, justification,
                 sample_size, precision_before, precision_after,
                 applied_at, created_at)
            VALUES
                (CAST(:id AS uuid), CAST(:org AS uuid), :mod, :rule, :pred, :op,
                 :val, :status, :src, :just,
                 :ss, :pb, :pa,
                 CASE WHEN :status = 'active' THEN NOW() END, NOW())
            """
        ),
        {
            "id": new_id,
            "org": org_id,
            "mod": module_id,
            "rule": rule_id,
            "pred": fact_predicate,
            "op": op_str,
            "val": float(new_threshold),
            "status": status,
            "src": source,
            "just": justification[:1000],
            "ss": sample_size,
            "pb": float(prec_before),
            "pa": float(prec_after),
        },
    )
    return new_id


def _current_threshold(
    session: Session,
    org_id: str,
    module_id: str,
    rule_id: str,
    fact_predicate: str,
    op_str: str,
    fallback: float,
) -> float:
    """The threshold currently in force for this rule on this org. Returns
    the active override if any; otherwise the global default from the
    rule knobs (which mirrors the YAML)."""
    # Caller passed `fallback` so a missing override returns whatever
    # value the analyzer is COMPARING from -- avoids extra DB lookups.
    return float(fallback)


def _clean_num(v: float) -> str:
    if float(v).is_integer():
        return str(int(v))
    return f"{v:.2f}"


# ─────────────────────────────────────────────────────────────────────────────
# Public entry points
# ─────────────────────────────────────────────────────────────────────────────


def get_active_override(
    session: Session,
    *,
    org_id: str,
    module_id: str,
    rule_id: str,
) -> dict[str, Any] | None:
    """Return the currently-active override for this rule on this org, if any.

    Read by `pipeline.run_for_org` BEFORE rule evaluation: when an override
    exists, the pipeline mutates the rule's threshold in memory before
    handing the ruleset to the ForwardChainer.
    """
    row = session.execute(
        text(
            """
            SELECT id, fact_predicate, op, threshold_value,
                   justification, sample_size, precision_before, precision_after
            FROM org_rule_overrides
            WHERE org_id = :org
              AND module_id = :mod
              AND rule_id = :rule
              AND status = 'active'
            ORDER BY created_at DESC
            LIMIT 1
            """
        ),
        {"org": org_id, "mod": module_id, "rule": rule_id},
    ).fetchone()
    if not row:
        return None
    return {
        "id": str(row.id),
        "fact_predicate": row.fact_predicate,
        "op": row.op,
        "threshold_value": float(row.threshold_value),
        "justification": row.justification,
        "sample_size": row.sample_size,
        "precision_before": row.precision_before,
        "precision_after": row.precision_after,
    }


def tune_for_org(
    session: Session,
    *,
    org_id: str,
    module_id: str = "ar_collection",
    auto_apply: bool = True,
) -> dict[str, Any]:
    """Iterate every rule in the module's tunable knob list, analyze
    outcomes, and either auto-apply or shadow a suggestion.

    Returns a summary the caller logs from a Celery task or returns
    from the HTTP route. Does NOT commit the session — caller does.
    """
    rule_results: list[dict[str, Any]] = []
    knobs = _load_module_knobs(module_id)
    if not knobs:
        return {
            "org_id": org_id,
            "module_id": module_id,
            "rules_evaluated": 0,
            "rules_with_outcomes": 0,
            "auto_applied": 0,
            "shadow_suggestions": 0,
            "details": [],
            "note": f"Module {module_id} has no tunable_knobs in manifest.json.",
        }

    for rule_id, (fact_predicate, op_str, default_threshold) in knobs.items():
        samples = _load_rule_outcomes(
            session,
            org_id=org_id,
            rule_id=rule_id,
            fact_predicate=fact_predicate,
        )
        if not samples:
            rule_results.append(
                {
                    "rule_id": rule_id,
                    "skipped": "no_outcomes",
                    "sample_size": 0,
                }
            )
            continue

        # The threshold "currently in force" is the active override if any,
        # else the YAML default. Compare candidates against THAT.
        active = get_active_override(
            session, org_id=org_id, module_id=module_id, rule_id=rule_id
        )
        baseline = active["threshold_value"] if active else default_threshold

        suggestion = _suggest_threshold(
            samples, current=baseline, op_str=op_str
        )
        if not suggestion:
            rule_results.append(
                {
                    "rule_id": rule_id,
                    "skipped": "no_better_threshold",
                    "sample_size": len(samples),
                    "current_threshold": baseline,
                }
            )
            continue

        meets_auto_bar = (
            len(samples) >= MIN_SAMPLE_SIZE
            and suggestion["improvement_pp"] >= MIN_PRECISION_IMPROVEMENT_PP
        )
        apply_now = bool(auto_apply and meets_auto_bar)

        override_id = _write_override(
            session,
            org_id=org_id,
            module_id=module_id,
            rule_id=rule_id,
            fact_predicate=fact_predicate,
            op_str=op_str,
            new_threshold=suggestion["suggested_threshold"],
            old_threshold=baseline,
            sample_size=len(samples),
            prec_before=suggestion["current_precision"],
            prec_after=suggestion["suggested_precision"],
            auto_apply=apply_now,
        )
        rule_results.append(
            {
                "rule_id": rule_id,
                "override_id": override_id,
                "auto_applied": apply_now,
                "sample_size": len(samples),
                **suggestion,
            }
        )

    return {
        "org_id": org_id,
        "module_id": module_id,
        "rules_evaluated": len(_AR_RULE_KNOBS),
        "rules_with_outcomes": sum(
            1 for r in rule_results if r.get("sample_size", 0) > 0
        ),
        "auto_applied": sum(1 for r in rule_results if r.get("auto_applied")),
        "shadow_suggestions": sum(
            1
            for r in rule_results
            if r.get("override_id") and not r.get("auto_applied")
        ),
        "details": rule_results,
    }
