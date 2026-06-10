"""ROI tracker (g-i-8 §1) — value of autonomous actions vs LLM+infra cost.

Per MD: the engine pays for itself only if value > cost. We can't compute value
ourselves — it's domain-specific (Sales = "qualified lead surfaced ahead of
human triage worth $X"). Caller supplies a `ValueHeuristic` callable per module.

Cost side:
- LLM cost: read from `AgentCallRow.cost_usd` summed per day per module
- Infra cost: passed in (allocated from monthly Supabase/Upstash bill; not auto-derived)

Output:
- Per day per (org, module): autonomous_actions_count, value_usd, llm_cost_usd,
  infra_cost_usd, roi_ratio
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from core.decision_store import DecisionRow
from core.delivery.store import AgentCallRow
from core.foundations.metrics_store import ResolutionMetricRow, RoiMetricRow
from core.foundations.telemetry import get_logger

log = get_logger(__name__)

# Module-supplied: given a DecisionRow, return its estimated dollar value.
# Return 0.0 if the decision shouldn't count (non-autonomous, low-confidence, etc.).
ValueHeuristic = Callable[[DecisionRow], float]


@dataclass(frozen=True)
class RoiSnapshot:
    """Per-(org, module, day) ROI breakdown."""

    org_id: str
    module_id: str
    on_date: date
    autonomous_actions_count: int
    estimated_value_usd: float
    llm_cost_usd: float
    infra_cost_usd: float
    roi_ratio: float


def compute_roi(
    session: Session,
    *,
    org_id: str,
    module_id: str,
    on_date: date,
    value_heuristic: ValueHeuristic,
    infra_cost_usd: float = 0.0,
) -> RoiSnapshot:
    """Pure-read ROI computation for one day."""
    start = datetime.combine(on_date, datetime.min.time(), tzinfo=UTC)
    end = start + timedelta(days=1)

    decisions = list(
        session.execute(
            select(DecisionRow)
            .where(DecisionRow.org_id == org_id)
            .where(DecisionRow.module_id == module_id)
            .where(DecisionRow.created_at >= start)
            .where(DecisionRow.created_at < end)
            .where(DecisionRow.route == "autonomous")
        )
        .scalars()
        .all()
    )

    n_actions = len(decisions)
    value = sum(value_heuristic(d) for d in decisions)

    llm_cost = (
        session.execute(
            select(AgentCallRow.cost_usd)
            .where(AgentCallRow.org_id == org_id)
            .where(AgentCallRow.timestamp >= start)
            .where(AgentCallRow.timestamp < end)
        )
        .scalars()
        .all()
    )
    llm_cost_total = float(sum(llm_cost))

    total_cost = llm_cost_total + infra_cost_usd
    ratio = (value / total_cost) if total_cost > 0 else float("inf") if value > 0 else 0.0

    return RoiSnapshot(
        org_id=org_id,
        module_id=module_id,
        on_date=on_date,
        autonomous_actions_count=n_actions,
        estimated_value_usd=round(value, 2),
        llm_cost_usd=round(llm_cost_total, 4),
        infra_cost_usd=round(infra_cost_usd, 4),
        roi_ratio=round(ratio, 2) if ratio != float("inf") else ratio,
    )


def persist_roi(
    session: Session,
    *,
    snap: RoiSnapshot,
    notes: str | None = None,
) -> RoiMetricRow:
    """UPSERT one RoiMetricRow per (org, module, date)."""
    existing = (
        session.execute(
            select(RoiMetricRow)
            .where(RoiMetricRow.org_id == snap.org_id)
            .where(RoiMetricRow.module_id == snap.module_id)
            .where(RoiMetricRow.date == snap.on_date)
        )
        .scalars()
        .one_or_none()
    )
    # SQLAlchemy Float doesn't take Python inf — clamp for persistence
    persisted_ratio = snap.roi_ratio if snap.roi_ratio != float("inf") else 9999.0

    if existing is None:
        row = RoiMetricRow(
            org_id=snap.org_id,
            module_id=snap.module_id,
            date=snap.on_date,
            autonomous_actions_count=snap.autonomous_actions_count,
            estimated_value_usd=snap.estimated_value_usd,
            llm_cost_usd=snap.llm_cost_usd,
            infra_cost_usd=snap.infra_cost_usd,
            roi_ratio=persisted_ratio,
            notes=notes,
        )
        session.add(row)
    else:
        existing.autonomous_actions_count = snap.autonomous_actions_count
        existing.estimated_value_usd = snap.estimated_value_usd
        existing.llm_cost_usd = snap.llm_cost_usd
        existing.infra_cost_usd = snap.infra_cost_usd
        existing.roi_ratio = persisted_ratio
        existing.notes = notes
        existing.computed_at = datetime.now(UTC)
        row = existing
    session.flush()
    log.info(
        "roi_persisted",
        org_id=snap.org_id,
        module_id=snap.module_id,
        date=snap.on_date.isoformat(),
        value_usd=snap.estimated_value_usd,
        cost_usd=snap.llm_cost_usd + snap.infra_cost_usd,
        ratio=persisted_ratio,
    )
    return row


# ─────────────────────────────────────────────────────────────────────────────
# Resolution-rate (engine health) — symbolic vs neural vs hybrid path counts
# ─────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class ResolutionSnapshot:
    org_id: str
    module_id: str
    on_date: date
    symbolic_count: int
    neural_count: int
    hybrid_count: int
    symbolic_resolution_rate: float


def compute_resolution(
    session: Session,
    *,
    org_id: str,
    module_id: str,
    on_date: date,
) -> ResolutionSnapshot:
    """Path counts for one day. symbolic_resolution_rate should trend UP as graph fills."""
    start = datetime.combine(on_date, datetime.min.time(), tzinfo=UTC)
    end = start + timedelta(days=1)
    rows = (
        session.execute(
            select(DecisionRow.path)
            .where(DecisionRow.org_id == org_id)
            .where(DecisionRow.module_id == module_id)
            .where(DecisionRow.created_at >= start)
            .where(DecisionRow.created_at < end)
        )
        .scalars()
        .all()
    )
    sym = sum(1 for p in rows if p == "symbolic")
    neu = sum(1 for p in rows if p == "neural")
    hyb = sum(1 for p in rows if p == "hybrid")
    total = sym + neu + hyb
    rate = sym / total if total else 0.0
    return ResolutionSnapshot(
        org_id=org_id,
        module_id=module_id,
        on_date=on_date,
        symbolic_count=sym,
        neural_count=neu,
        hybrid_count=hyb,
        symbolic_resolution_rate=round(rate, 4),
    )


def persist_resolution(
    session: Session,
    *,
    snap: ResolutionSnapshot,
) -> ResolutionMetricRow:
    existing = (
        session.execute(
            select(ResolutionMetricRow)
            .where(ResolutionMetricRow.org_id == snap.org_id)
            .where(ResolutionMetricRow.module_id == snap.module_id)
            .where(ResolutionMetricRow.date == snap.on_date)
        )
        .scalars()
        .one_or_none()
    )
    if existing is None:
        row = ResolutionMetricRow(
            org_id=snap.org_id,
            module_id=snap.module_id,
            date=snap.on_date,
            symbolic_count=snap.symbolic_count,
            neural_count=snap.neural_count,
            hybrid_count=snap.hybrid_count,
            symbolic_resolution_rate=snap.symbolic_resolution_rate,
        )
        session.add(row)
    else:
        existing.symbolic_count = snap.symbolic_count
        existing.neural_count = snap.neural_count
        existing.hybrid_count = snap.hybrid_count
        existing.symbolic_resolution_rate = snap.symbolic_resolution_rate
        existing.computed_at = datetime.now(UTC)
        row = existing
    session.flush()
    return row
