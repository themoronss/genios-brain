"""Correction-driven learning loop.

Per MD g-i-3 §3.2.1:
- Each Correction lists edge_ids it confirms/contradicts
- For each edge: bayesian_update -> persist new alpha/beta/weight/trust/source
- Volume gate: weight USED downstream only when (alpha+beta) >= N_min
- Time decay applied to effective evidence counts
- Per-org-unit namespacing: corrections don't bleed across org_units

Workflow (called by g-i-7 feedback capture or background reducer):
1. apply_correction(session, correction)
   -> for each edge_id, fetch row, derive outcome (confirm/contradict from diff),
      compute updated WeightResult, write back, record event
"""

from __future__ import annotations

import math
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from core.foundations import audit
from core.foundations.config import DECAY_HALF_LIFE_DAYS
from core.foundations.telemetry import get_logger
from core.graph.store import EdgeRow
from core.graph.weights import WeightResult, bayesian_update
from core.worldmodel.store import CorrectionRow
from core.worldmodel.temporal import append_event

log = get_logger(__name__)


@dataclass(frozen=True)
class EdgeUpdate:
    """One edge's update as a result of applying a correction."""

    edge_id: str
    outcome: bool  # True=confirm, False=contradict
    before: WeightResult
    after: WeightResult


def derive_outcomes(correction_diff: dict[str, object]) -> dict[str, bool]:
    """Map a correction.diff payload to per-edge outcomes.

    Conventions used by g-i-7 capture (documented; can be extended):
    - diff["edges_confirmed"]: list[str]   (caller marks edges as confirmed)
    - diff["edges_contradicted"]: list[str]
    """
    out: dict[str, bool] = {}
    for eid in _str_list(correction_diff.get("edges_confirmed")):
        out[eid] = True
    for eid in _str_list(correction_diff.get("edges_contradicted")):
        out[eid] = False
    return out


def apply_correction(
    session: Session,
    *,
    correction: CorrectionRow,
) -> list[EdgeUpdate]:
    """Apply a Correction's edge outcomes to graph_edges. Returns per-edge updates.

    Writes:
    - Updates edge_row alpha/beta/weight/trust/weight_source
    - Appends a `weight_update` graph_event per touched edge
    - Audit log entry per applied edge
    """
    outcomes = derive_outcomes(correction.diff)
    if not outcomes:
        log.info(
            "correction_no_edge_outcomes",
            correction_id=correction.id,
            decision_id=correction.decision_id,
        )
        return []

    updates: list[EdgeUpdate] = []
    for edge_id, outcome in outcomes.items():
        row = session.get(EdgeRow, edge_id)
        if row is None or row.org_id != correction.org_id:
            log.warning(
                "correction_edge_not_found",
                correction_id=correction.id,
                edge_id=edge_id,
            )
            continue

        before = _weight_result_from_row(row)
        result = bayesian_update(alpha=row.alpha, beta=row.beta, outcome=outcome)

        # Persist new state
        if outcome:
            row.alpha += 1
        else:
            row.beta += 1
        row.weight = result.weight
        row.trust = result.trust
        row.weight_source = result.source.value

        append_event(
            session,
            org_id=correction.org_id,
            event_type="weight_update",
            target_type="edge",
            target_id=row.id,
            payload={
                "alpha": row.alpha,
                "beta": row.beta,
                "weight": row.weight,
                "trust": row.trust,
                "weight_source": row.weight_source,
                "source_correction_id": correction.id,
                "outcome": outcome,
            },
        )

        audit.record(
            org_id=correction.org_id,
            actor_type="user",
            actor_id=correction.actor,
            action="override_captured",
            target_type="edge",
            target_id=row.id,
            metadata={
                "correction_id": correction.id,
                "outcome": "confirmed" if outcome else "contradicted",
                "trusted": result.trusted,
            },
        )

        updates.append(EdgeUpdate(edge_id=row.id, outcome=outcome, before=before, after=result))

    return updates


def effective_evidence(
    *,
    alpha: int,
    beta: int,
    last_update_at: datetime,
    now: datetime | None = None,
    half_life_days: float = DECAY_HALF_LIFE_DAYS,
) -> tuple[float, float]:
    """Apply exponential time decay to (alpha, beta) counts.

    Used by g-i-2 when reading edge weights — old confirmations weigh less.
    Pure function; does not mutate the row.

    Returns (effective_alpha, effective_beta) as floats (not persisted, transient).
    """
    now = now or datetime.now(UTC)
    age_days = (now - _to_utc(last_update_at)).total_seconds() / 86400.0
    if age_days < 0:
        age_days = 0.0
    decay = math.exp(-math.log(2) * age_days / half_life_days)
    return alpha * decay, beta * decay


# ─── helpers ────────────────────────────────────────────────────────────────


def _weight_result_from_row(row: EdgeRow) -> WeightResult:
    from core.graph.schema import WeightSource

    total = row.alpha + row.beta
    return WeightResult(
        weight=row.weight,
        source=WeightSource(row.weight_source),
        trust=row.trust,
        sample_count=total,
        trusted=total >= 1,  # placeholder; real check uses N_min in bayesian_update
    )


def _str_list(v: object) -> Iterable[str]:
    if v is None:
        return []
    if isinstance(v, list):
        return [str(x) for x in v]
    return []


def _to_utc(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)
