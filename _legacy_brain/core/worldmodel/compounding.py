"""Knowledge compounding — strengthen confirmed + detect candidate edges via lift.

Per MD g-i-3 §3.2.2:
- Strengthen existing: confirmed predictions -> Beta update up (already handled in learning.py)
- Propose NEW edges (DETECT auto, ASSERT only via human):
    signal = lift(X,Y) = P(X^Y) / (P(X) * P(Y))
    if signal > theta_signal AND co_occurrence >= N_min:
        create CandidateEdge(status=proposed)

HARD rule: candidate edges NEVER reasoned on as causal until confirmed.

Caps + ranking (per MD): max N proposals per cycle, rank by signal*relevance,
NEVER re-propose a rejected (status='rejected') pair.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from core.foundations import audit
from core.foundations.config import N_MIN_EVIDENCE
from core.foundations.telemetry import get_logger
from core.worldmodel.store import CandidateEdgeRow

log = get_logger(__name__)


# Per MD §3.2.2 — lift > 2 is a meaningful association in most use cases
DEFAULT_THETA_SIGNAL = 2.0

# Cap on proposals per detection cycle (anti-spam)
DEFAULT_MAX_PROPOSALS_PER_CYCLE = 10


@dataclass(frozen=True)
class CoOccurrence:
    """One observed (X, Y) co-occurrence statistic.

    Caller (g-i-2 reasoning or batch job) precomputes these — this module
    only consumes the counts to decide candidacy.
    """

    from_node: str
    to_node: str
    count_x: int  # how often X appeared alone or in context
    count_y: int
    count_x_and_y: int
    total_observations: int


def compute_lift(co: CoOccurrence) -> float:
    """lift(X,Y) = P(X^Y) / (P(X) * P(Y)). Returns 0 on insufficient data."""
    n = co.total_observations
    if n <= 0 or co.count_x <= 0 or co.count_y <= 0:
        return 0.0
    p_x = co.count_x / n
    p_y = co.count_y / n
    p_xy = co.count_x_and_y / n
    denom = p_x * p_y
    if denom <= 0:
        return 0.0
    return p_xy / denom


def propose_candidates(
    session: Session,
    *,
    org_id: str,
    co_occurrences: Iterable[CoOccurrence],
    theta_signal: float = DEFAULT_THETA_SIGNAL,
    n_min: int = N_MIN_EVIDENCE,
    max_proposals: int = DEFAULT_MAX_PROPOSALS_PER_CYCLE,
) -> list[CandidateEdgeRow]:
    """Detect + persist candidate edges. Skips already-rejected pairs.

    Returns the newly-proposed rows (may be empty).
    """
    scored: list[tuple[CoOccurrence, float]] = []
    for co in co_occurrences:
        if co.count_x_and_y < n_min:
            continue
        lift = compute_lift(co)
        if lift >= theta_signal:
            scored.append((co, lift))

    # Rank by lift desc, cap at max_proposals (anti-spam)
    scored.sort(key=lambda x: x[1], reverse=True)
    scored = scored[:max_proposals]

    rejected_pairs = _rejected_pairs(session, org_id=org_id)
    existing_pairs = _existing_proposed_or_confirmed_pairs(session, org_id=org_id)

    new_rows: list[CandidateEdgeRow] = []
    for co, lift in scored:
        pair = (co.from_node, co.to_node)
        if pair in rejected_pairs:
            log.info("candidate_skip_rejected", from_node=co.from_node, to_node=co.to_node)
            continue
        if pair in existing_pairs:
            log.info("candidate_skip_existing", from_node=co.from_node, to_node=co.to_node)
            continue
        row = CandidateEdgeRow(
            org_id=org_id,
            from_node=co.from_node,
            to_node=co.to_node,
            signal_lift=lift,
            co_occurrence_count=co.count_x_and_y,
            status="proposed",
        )
        session.add(row)
        new_rows.append(row)

    if new_rows:
        session.flush()
        for row in new_rows:
            audit.record(
                org_id=org_id,
                actor_type="system",
                actor_id="compounding.propose_candidates",
                action="config_changed",
                target_type="candidate_edge",
                target_id=row.id,
                metadata={
                    "from_node": row.from_node,
                    "to_node": row.to_node,
                    "lift": row.signal_lift,
                },
            )

    return new_rows


def _rejected_pairs(session: Session, *, org_id: str) -> set[tuple[str, str]]:
    rows = session.execute(
        select(CandidateEdgeRow.from_node, CandidateEdgeRow.to_node)
        .where(CandidateEdgeRow.org_id == org_id)
        .where(CandidateEdgeRow.status == "rejected")
    ).all()
    return {(r[0], r[1]) for r in rows}


def _existing_proposed_or_confirmed_pairs(session: Session, *, org_id: str) -> set[tuple[str, str]]:
    rows = session.execute(
        select(CandidateEdgeRow.from_node, CandidateEdgeRow.to_node)
        .where(CandidateEdgeRow.org_id == org_id)
        .where(
            or_(
                CandidateEdgeRow.status == "proposed",
                CandidateEdgeRow.status == "confirmed",
            )
        )
    ).all()
    return {(r[0], r[1]) for r in rows}


# unused import guard (kept to keep `and_` import clean — small future filters)
_ = and_
