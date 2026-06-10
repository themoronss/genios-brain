"""
Phase 6: Churn risk detector.

Reads the latest `engagement_health` snapshot for the org. When churn_score
is in the actionable band, emits a candidate so the brain router runs it
through the standard pipeline (reasoner → score → gate → recommendation).

The candidate's `insight_type='churn_risk'` makes Phase 6 offer composer
take over in the action layer (response_shaper.shape_bundle won't touch it
because the offer is composed separately by `tasks/retention_offer.py`).

Three tiers based on churn_score:
  • 0.30–0.60  → 'nudge'   (helpful tip / feature hint)
  • 0.60–0.80  → 'offer'   (free month / upgrade discount / 1-on-1)
  • 0.80+      → 'rescue'  (founder personal email + custom proposal)
"""

from __future__ import annotations

from typing import Dict, List

from sqlalchemy import text


def _detect_churn_risk(db, org_id: str) -> List[Dict]:
    """Emit a candidate when latest engagement_health crosses the threshold."""
    try:
        row = db.execute(
            text("""
                SELECT churn_score, hard_signal_score, soft_signal_score,
                       context_signal_score, api_calls_7d, api_calls_prev_7d,
                       dismiss_rate_30d, sync_errors_7d, signals_payload,
                       snapshot_date
                FROM engagement_health
                WHERE org_id = :oid
                ORDER BY snapshot_date DESC
                LIMIT 1
            """),
            {"oid": org_id},
        ).fetchone()
    except Exception:
        return []

    if not row:
        return []

    score = float(row.churn_score or 0.0)
    if score < 0.30:
        return []

    if score >= 0.80:
        tier = "rescue"
        priority_label = "P1"
    elif score >= 0.60:
        tier = "offer"
        priority_label = "P2"
    else:
        tier = "nudge"
        priority_label = "P3"

    delta_pct = None
    if row.api_calls_prev_7d:
        delta_pct = round(
            100.0 * ((row.api_calls_7d or 0) - row.api_calls_prev_7d)
            / max(1, row.api_calls_prev_7d),
            1,
        )

    title = (
        f"Churn risk ({tier}): score={score:.2f}, "
        f"7d API calls Δ={delta_pct}%" if delta_pct is not None else
        f"Churn risk ({tier}): score={score:.2f}"
    )
    detail = (
        f"hard={row.hard_signal_score:.2f} "
        f"soft={row.soft_signal_score:.2f} "
        f"context={row.context_signal_score:.2f} | "
        f"dismiss_rate={row.dismiss_rate_30d:.2f} "
        f"sync_errors={row.sync_errors_7d}"
    )

    return [{
        "insight_type": "churn_risk",
        "priority": priority_label,
        "category": tier,
        "title": title,
        "detail": detail,
        "contact_id": None,           # org-level, not contact-level
        "contact_name": None,
        "metadata": {
            "tier": tier,
            "churn_score": score,
            "snapshot_date": str(row.snapshot_date),
            "delta_pct": delta_pct,
            "signals": dict(row.signals_payload or {}),
            "action_verb": "compose_retention_offer",
        },
    }]


CHURN_DETECTORS = [_detect_churn_risk]
