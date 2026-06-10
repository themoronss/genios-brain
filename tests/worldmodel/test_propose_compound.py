"""Tests for compounding.py + propose.py — candidate-edge detect + confirm/reject."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from core.foundations.db import Base
from core.graph.schema import EdgeType
from core.graph.store import EdgeRow, NodeRow
from core.worldmodel.compounding import (
    CoOccurrence,
    compute_lift,
    propose_candidates,
)
from core.worldmodel.propose import ProposalNotFound, confirm, reject
from core.worldmodel.store import CandidateEdgeRow


@pytest.fixture
def session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return Session(engine)


def _seed_two_nodes(session: Session) -> tuple[str, str]:
    a = NodeRow(
        id="A",
        org_id="o",
        org_unit="u",
        type="entity",
        canonical_name="A",
        aliases=[],
        attributes={},
        source_item_ids=[],
        first_seen=datetime.now(UTC),
        last_seen=datetime.now(UTC),
    )
    b = NodeRow(
        id="B",
        org_id="o",
        org_unit="u",
        type="entity",
        canonical_name="B",
        aliases=[],
        attributes={},
        source_item_ids=[],
        first_seen=datetime.now(UTC),
        last_seen=datetime.now(UTC),
    )
    session.add_all([a, b])
    session.flush()
    return a.id, b.id


# ── compounding ─────────────────────────────────────────────────────────────


@pytest.mark.unit
def test_compute_lift_returns_zero_on_empty_data() -> None:
    co = CoOccurrence(
        from_node="A", to_node="B", count_x=0, count_y=0, count_x_and_y=0, total_observations=0
    )
    assert compute_lift(co) == 0.0


@pytest.mark.unit
def test_compute_lift_strong_association() -> None:
    """Lift = P(X^Y) / P(X)*P(Y). Strong = > 1, weak/random = ~1."""
    co = CoOccurrence(
        from_node="A", to_node="B", count_x=50, count_y=50, count_x_and_y=40, total_observations=100
    )
    # P(X)=0.5, P(Y)=0.5, P(XY)=0.4, lift = 0.4 / 0.25 = 1.6
    lift = compute_lift(co)
    assert 1.5 < lift < 1.7


@pytest.mark.unit
def test_propose_candidates_below_signal_threshold_skipped(session: Session) -> None:
    a, b = _seed_two_nodes(session)
    co = CoOccurrence(
        from_node=a, to_node=b, count_x=50, count_y=50, count_x_and_y=30, total_observations=100
    )  # lift = 1.2, below default theta=2.0
    rows = propose_candidates(session, org_id="o", co_occurrences=[co])
    assert rows == []


@pytest.mark.unit
def test_propose_candidates_above_threshold_persisted(session: Session) -> None:
    a, b = _seed_two_nodes(session)
    co = CoOccurrence(
        from_node=a, to_node=b, count_x=30, count_y=30, count_x_and_y=25, total_observations=100
    )  # lift ~= 2.78
    rows = propose_candidates(session, org_id="o", co_occurrences=[co])
    session.commit()
    assert len(rows) == 1
    assert rows[0].status == "proposed"


@pytest.mark.unit
def test_propose_skips_rejected_pair(session: Session) -> None:
    """Per MD: rejected pair → negative memory, never re-proposed."""
    a, b = _seed_two_nodes(session)
    rejected = CandidateEdgeRow(
        org_id="o",
        from_node=a,
        to_node=b,
        signal_lift=3.0,
        co_occurrence_count=30,
        status="rejected",
    )
    session.add(rejected)
    session.flush()

    co = CoOccurrence(
        from_node=a, to_node=b, count_x=30, count_y=30, count_x_and_y=25, total_observations=100
    )
    rows = propose_candidates(session, org_id="o", co_occurrences=[co])
    assert rows == []  # suppressed


# ── propose-confirm ─────────────────────────────────────────────────────────


@pytest.mark.unit
def test_confirm_creates_asserted_edge(session: Session) -> None:
    a, b = _seed_two_nodes(session)
    cand = CandidateEdgeRow(
        org_id="o",
        from_node=a,
        to_node=b,
        signal_lift=3.0,
        co_occurrence_count=30,
        status="proposed",
    )
    session.add(cand)
    session.flush()

    edge = confirm(session, candidate_id=cand.id, confirmed_by="user:alice")
    session.commit()

    assert edge.type == EdgeType.INFLUENCE.value
    assert edge.asserted_by_type == "human"
    assert edge.asserted_by_id == "user:alice"
    refreshed_cand = session.get(CandidateEdgeRow, cand.id)
    assert refreshed_cand is not None
    assert refreshed_cand.status == "confirmed"

    in_db = session.get(EdgeRow, edge.id)
    assert in_db is not None


@pytest.mark.unit
def test_reject_marks_negative_memory(session: Session) -> None:
    a, b = _seed_two_nodes(session)
    cand = CandidateEdgeRow(
        org_id="o",
        from_node=a,
        to_node=b,
        signal_lift=3.0,
        co_occurrence_count=30,
        status="proposed",
    )
    session.add(cand)
    session.flush()

    reject(session, candidate_id=cand.id, rejected_by="user:alice")
    session.commit()

    refreshed = session.get(CandidateEdgeRow, cand.id)
    assert refreshed is not None
    assert refreshed.status == "rejected"


@pytest.mark.unit
def test_confirm_rejects_already_decided(session: Session) -> None:
    a, b = _seed_two_nodes(session)
    cand = CandidateEdgeRow(
        org_id="o",
        from_node=a,
        to_node=b,
        signal_lift=3.0,
        co_occurrence_count=30,
        status="confirmed",
    )
    session.add(cand)
    session.flush()

    with pytest.raises(ProposalNotFound):
        confirm(session, candidate_id=cand.id, confirmed_by="user:alice")
