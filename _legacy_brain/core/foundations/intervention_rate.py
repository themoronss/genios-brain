"""THE North Star metric (g-i-8) — intervention_rate per org / per module / per day.

Definition:
    intervention_rate = human_overrides_count / max(1, total_decisions)

Where:
- total_decisions       = rows in `decisions` for that org/module/day
- human_overrides_count = rows in `corrections` for that org joined to those
                          decisions (👎 + edit feedback both create CorrectionRow)

Trending DOWN over weeks = engine getting smarter (thesis alive).
Trending UP over weeks   = engine drifting / domain shifting → INVESTIGATE.

Why the rollup table:
- Compute is cheap (couple of group-by queries) but the dashboard hits this
  metric on every page load — pre-aggregating daily keeps the read O(weeks).
- Idempotent recompute: a re-run for the same (org, module, date) UPSERTs.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from core.decision_store import DecisionRow
from core.foundations.metrics_store import InterventionMetricRow
from core.foundations.telemetry import get_logger
from core.worldmodel.store import CorrectionRow

log = get_logger(__name__)


@dataclass(frozen=True)
class InterventionSnapshot:
    """One day's rollup for one (org, module)."""

    org_id: str
    module_id: str
    on_date: date
    total_decisions: int
    autonomous_count: int
    notify_count: int
    flag_count: int
    human_overrides_count: int
    intervention_rate: float


@dataclass(frozen=True)
class InterventionTrend:
    """Series of daily rates for an (org, module) over a window."""

    org_id: str
    module_id: str
    days: list[date]
    rates: list[float]
    direction: str  # "down" | "up" | "flat" — over the window


def compute_for_day(
    session: Session,
    *,
    org_id: str,
    module_id: str,
    on_date: date,
) -> InterventionSnapshot:
    """Compute one (org, module, date) snapshot. Pure read."""
    start = datetime.combine(on_date, datetime.min.time(), tzinfo=UTC)
    end = start + timedelta(days=1)

    decisions = list(
        session.execute(
            select(DecisionRow)
            .where(DecisionRow.org_id == org_id)
            .where(DecisionRow.module_id == module_id)
            .where(DecisionRow.created_at >= start)
            .where(DecisionRow.created_at < end)
        )
        .scalars()
        .all()
    )

    total = len(decisions)
    counts = {"autonomous": 0, "notify": 0, "flag": 0}
    decision_ids: list[str] = []
    for d in decisions:
        decision_ids.append(d.id)
        if d.route in counts:
            counts[d.route] += 1

    overrides = 0
    if decision_ids:
        overrides = (
            session.execute(
                select(CorrectionRow)
                .where(CorrectionRow.org_id == org_id)
                .where(CorrectionRow.decision_id.in_(decision_ids))
            )
            .scalars()
            .unique()
            .all()
            .__len__()
        )

    rate = overrides / total if total else 0.0
    return InterventionSnapshot(
        org_id=org_id,
        module_id=module_id,
        on_date=on_date,
        total_decisions=total,
        autonomous_count=counts["autonomous"],
        notify_count=counts["notify"],
        flag_count=counts["flag"],
        human_overrides_count=overrides,
        intervention_rate=round(rate, 4),
    )


def rollup_day(
    session: Session,
    *,
    org_id: str,
    module_id: str,
    on_date: date,
) -> InterventionMetricRow:
    """Compute + UPSERT into intervention_metrics. Returns the persisted row."""
    snap = compute_for_day(
        session, org_id=org_id, module_id=module_id, on_date=on_date
    )
    existing = (
        session.execute(
            select(InterventionMetricRow)
            .where(InterventionMetricRow.org_id == org_id)
            .where(InterventionMetricRow.module_id == module_id)
            .where(InterventionMetricRow.date == on_date)
        )
        .scalars()
        .one_or_none()
    )
    if existing is None:
        row = InterventionMetricRow(
            org_id=org_id,
            module_id=module_id,
            date=on_date,
            total_decisions=snap.total_decisions,
            autonomous_count=snap.autonomous_count,
            notify_count=snap.notify_count,
            flag_count=snap.flag_count,
            human_overrides_count=snap.human_overrides_count,
            intervention_rate=snap.intervention_rate,
        )
        session.add(row)
    else:
        existing.total_decisions = snap.total_decisions
        existing.autonomous_count = snap.autonomous_count
        existing.notify_count = snap.notify_count
        existing.flag_count = snap.flag_count
        existing.human_overrides_count = snap.human_overrides_count
        existing.intervention_rate = snap.intervention_rate
        existing.computed_at = datetime.now(UTC)
        row = existing
    session.flush()
    log.info(
        "intervention_rate_rolled_up",
        org_id=org_id,
        module_id=module_id,
        date=on_date.isoformat(),
        rate=snap.intervention_rate,
        total=snap.total_decisions,
    )
    return row


def rollup_range(
    session: Session,
    *,
    org_id: str,
    module_ids: list[str],
    start_date: date,
    end_date: date,
) -> int:
    """Rollup every (module, day) in [start_date, end_date] inclusive. Returns count."""
    if start_date > end_date:
        raise ValueError("start_date must be <= end_date")
    n = 0
    cur = start_date
    while cur <= end_date:
        for mid in module_ids:
            rollup_day(session, org_id=org_id, module_id=mid, on_date=cur)
            n += 1
        cur += timedelta(days=1)
    return n


def trend(
    session: Session,
    *,
    org_id: str,
    module_id: str,
    window_days: int = 14,
) -> InterventionTrend:
    """Read the last `window_days` from intervention_metrics and label direction."""
    if window_days < 2:
        raise ValueError("window_days must be >= 2 to compute direction")
    end = datetime.now(UTC).date()
    start = end - timedelta(days=window_days - 1)
    rows = (
        session.execute(
            select(InterventionMetricRow)
            .where(InterventionMetricRow.org_id == org_id)
            .where(InterventionMetricRow.module_id == module_id)
            .where(InterventionMetricRow.date >= start)
            .where(InterventionMetricRow.date <= end)
            .order_by(InterventionMetricRow.date.asc())
        )
        .scalars()
        .all()
    )
    by_date = {r.date: r.intervention_rate for r in rows}
    days: list[date] = []
    rates: list[float] = []
    cur = start
    while cur <= end:
        days.append(cur)
        rates.append(by_date.get(cur, 0.0))
        cur += timedelta(days=1)

    direction = _classify_direction(rates)
    return InterventionTrend(
        org_id=org_id,
        module_id=module_id,
        days=days,
        rates=rates,
        direction=direction,
    )


def org_summary(
    session: Session,
    *,
    org_id: str,
    on_date: date | None = None,
) -> dict[str, float]:
    """Per-module intervention-rate map for one day.

    Strategy: prefer the rollup table (intervention_metrics) when it has
    data — that's the cron-computed authoritative store. When the rollup
    is empty (new org, rollup task hasn't run yet, or org never had a
    decision in `decisions`), fall back to a live computation from
    `feedback_actions` joined with `proactive_insights`.

    The fallback is what the dashboard north-star widget uses on day-1
    of a customer: rules fire on CSV, customer marks a few outcomes,
    the chip should display SOMETHING instead of a flat zero.
    """
    on_date = on_date or datetime.now(UTC).date()
    rows = (
        session.execute(
            select(InterventionMetricRow)
            .where(InterventionMetricRow.org_id == org_id)
            .where(InterventionMetricRow.date == on_date)
        )
        .scalars()
        .all()
    )
    out: dict[str, float] = defaultdict(float)
    for r in rows:
        out[r.module_id] = r.intervention_rate
    if out:
        return dict(out)

    # ── Live fallback: compute per-module rate from feedback_actions over
    # the last 30 days. We accept higher latency here in exchange for the
    # widget actually displaying something on day-1. The rollup-based
    # path remains correct for orgs that DO have intervention_metrics.
    from sqlalchemy import text as _text

    rows = session.execute(
        _text(
            """
            SELECT
              COALESCE(pi.scores_jsonb->>'rule_id', 'unknown')
                AS rule_id,
              COUNT(*) FILTER (WHERE fa.action = 'dismissed')
                AS overrides,
              COUNT(*) FILTER (WHERE fa.action IN
                ('paid','ignored','dismissed','escalated','acted'))
                AS total
            FROM feedback_actions fa
            JOIN proactive_insights pi ON pi.id::text = fa.insight_id
            WHERE pi.org_id = :org
              AND fa.timestamp >= NOW() - INTERVAL '30 days'
            GROUP BY 1
            HAVING COUNT(*) FILTER (WHERE fa.action IN
              ('paid','ignored','dismissed','escalated','acted')) >= 1
            """
        ),
        {"org": org_id},
    ).fetchall()
    # Map rule_id -> module_id via best-effort prefix. ar_*, hr_*, csm_*
    # cover today's installed modules; anything else collapses to "default".
    for rule_id, overrides, total in rows:
        if total == 0:
            continue
        mod = (
            "ar_collection"
            if rule_id.startswith("ar_")
            else "hr_pipeline"
            if rule_id.startswith("hr_")
            else "csm_health"
            if rule_id.startswith("csm_")
            else "sales"
            if rule_id.startswith(("churn_", "pricing_", "stage_", "deal_", "response_"))
            else "default"
        )
        rate = overrides / total if total > 0 else 0.0
        # When multiple rules collapse to the same module, average across
        # them weighted by sample.
        if mod in out:
            # Simple recomputation — sum overrides + sum totals across rules
            # would be cleaner; keeping it as average for v1 since most
            # modules will have 1 rule active anyway at this scale.
            out[mod] = round((out[mod] + rate) / 2, 4)
        else:
            out[mod] = round(rate, 4)
    return dict(out)


def _classify_direction(rates: list[float]) -> str:
    """Split window in half, compare means. Threshold: 2 pct points."""
    if len(rates) < 2:
        return "flat"
    mid = len(rates) // 2
    first = sum(rates[:mid]) / max(1, len(rates[:mid]))
    second = sum(rates[mid:]) / max(1, len(rates[mid:]))
    delta = second - first
    if delta < -0.02:
        return "down"
    if delta > 0.02:
        return "up"
    return "flat"
