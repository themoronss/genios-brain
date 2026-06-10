"""Propose-confirm flow for candidate edges.

Per MD g-i-3 §3.2.2:
- Surface a candidate to a human ("X and Y co-occur strongly. Real influence? y/n/edit")
- Approved -> assert edge (asserted_by=HUMAN, type=influence, logged, versioned)
- Rejected -> mark rejected; suppress re-proposing same pair (negative memory)

This module owns the state transitions on CandidateEdgeRow + the resulting
EdgeRow creation when confirmed. No UI here — UI is g-i-7.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.orm import Session

from core.foundations import audit
from core.foundations.telemetry import get_logger
from core.graph.schema import AssertionSource, EdgeStatus, EdgeType, WeightSource
from core.graph.store import EdgeRow
from core.worldmodel.store import CandidateEdgeRow
from core.worldmodel.temporal import append_event

log = get_logger(__name__)


class ProposalNotFound(Exception):
    """Candidate id not found or already decided."""


def confirm(
    session: Session,
    *,
    candidate_id: str,
    confirmed_by: str,
    edge_type: EdgeType = EdgeType.INFLUENCE,
) -> EdgeRow:
    """Human confirms the candidate. Asserts a real edge.

    Default edge_type=INFLUENCE — the typical use case for candidate-via-lift.
    Caller may pass DEPENDENCY if appropriate. TEMPORAL doesn't make sense here.
    """
    row = _load_proposed(session, candidate_id)

    edge = EdgeRow(
        org_id=row.org_id,
        from_node=row.from_node,
        to_node=row.to_node,
        type=edge_type.value,
        asserted_by_type=AssertionSource.HUMAN.value,
        asserted_by_id=confirmed_by,
        weight=min(1.0, max(0.0, row.signal_lift / 5.0)),  # lift-derived starting weight
        weight_source=WeightSource.HUMAN.value,
        alpha=1,
        beta=1,
        trust=0.0,
        status=EdgeStatus.ASSERTED.value,
    )
    session.add(edge)
    session.flush()

    row.status = "confirmed"
    row.decided_at = datetime.now(UTC)
    row.decided_by = confirmed_by

    append_event(
        session,
        org_id=row.org_id,
        event_type="edge_add",
        target_type="edge",
        target_id=edge.id,
        payload={
            "from_node": edge.from_node,
            "to_node": edge.to_node,
            "type": edge.type,
            "asserted_by_type": edge.asserted_by_type,
            "asserted_by_id": edge.asserted_by_id,
            "weight": edge.weight,
            "weight_source": edge.weight_source,
            "from_candidate": row.id,
        },
    )

    audit.record(
        org_id=row.org_id,
        actor_type="user",
        actor_id=confirmed_by,
        action="config_changed",
        target_type="candidate_edge",
        target_id=row.id,
        metadata={"op": "confirmed", "new_edge_id": edge.id, "edge_type": edge.type},
    )

    return edge


def reject(
    session: Session,
    *,
    candidate_id: str,
    rejected_by: str,
) -> CandidateEdgeRow:
    """Human rejects. Status -> 'rejected'; pair never re-proposed (negative memory)."""
    row = _load_proposed(session, candidate_id)
    row.status = "rejected"
    row.decided_at = datetime.now(UTC)
    row.decided_by = rejected_by

    audit.record(
        org_id=row.org_id,
        actor_type="user",
        actor_id=rejected_by,
        action="config_changed",
        target_type="candidate_edge",
        target_id=row.id,
        metadata={"op": "rejected"},
    )

    return row


def _load_proposed(session: Session, candidate_id: str) -> CandidateEdgeRow:
    row = session.get(CandidateEdgeRow, candidate_id)
    if row is None:
        raise ProposalNotFound(f"candidate {candidate_id} not found")
    if row.status != "proposed":
        raise ProposalNotFound(f"candidate {candidate_id} already {row.status}")
    return row
