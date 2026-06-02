"""Tests for core.artifacts.trace + uncertainty."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from core.artifacts.trace import build_trace
from core.artifacts.uncertainty import UncertaintyKind, collect_uncertainty
from core.foundations.db import Base
from core.graph.store import EdgeRow, FactRow, NodeRow


@pytest.fixture
def session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return Session(engine)


def _seed_node(session: Session, *, id: str, name: str = "X") -> NodeRow:
    n = NodeRow(
        id=id,
        org_id="o",
        org_unit="sales",
        type="entity",
        canonical_name=name,
        aliases=[],
        attributes={},
        source_item_ids=[],
        first_seen=datetime.now(UTC),
        last_seen=datetime.now(UTC),
    )
    session.add(n)
    session.flush()
    return n


def _seed_edge(
    session: Session,
    *,
    eid: str,
    weight_source: str = "frequency",
    status: str = "asserted",
    alpha: int = 30,
    beta: int = 10,
) -> EdgeRow:
    _seed_node(session, id="A")
    _seed_node(session, id="B")
    e = EdgeRow(
        id=eid,
        org_id="o",
        from_node="A",
        to_node="B",
        type="influence",
        asserted_by_type="rule",
        asserted_by_id="r1",
        weight=alpha / (alpha + beta) if (alpha + beta) else 0.5,
        weight_source=weight_source,
        alpha=alpha,
        beta=beta,
        trust=0.5,
        status=status,
    )
    session.add(e)
    session.flush()
    return e


# ── uncertainty.collect_uncertainty ────────────────────────────────────────


@pytest.mark.unit
def test_symbolic_decision_no_gap_fill_flag(session: Session) -> None:
    """Pure symbolic -> no LLM_GAP_FILL flag."""
    flags = collect_uncertainty(session, org_id="o", decision_path="symbolic", edge_ids_in_proof=[])
    assert not any(f.kind == UncertaintyKind.LLM_GAP_FILL for f in flags)


@pytest.mark.unit
def test_neural_decision_flags_gap_fill(session: Session) -> None:
    flags = collect_uncertainty(session, org_id="o", decision_path="neural", edge_ids_in_proof=[])
    assert any(f.kind == UncertaintyKind.LLM_GAP_FILL for f in flags)


@pytest.mark.unit
def test_below_n_min_edge_flagged(session: Session) -> None:
    """Edge with alpha+beta < N_MIN_EVIDENCE -> flagged as low-trust."""
    e = _seed_edge(session, eid="e_low", alpha=3, beta=2)  # 5 total < 20 default
    session.commit()
    flags = collect_uncertainty(
        session, org_id="o", decision_path="symbolic", edge_ids_in_proof=[e.id]
    )
    assert any(f.kind == UncertaintyKind.BELOW_N_MIN and f.target == e.id for f in flags)


@pytest.mark.unit
def test_default_weight_edge_flagged(session: Session) -> None:
    e = _seed_edge(session, eid="e_default", weight_source="default")
    session.commit()
    flags = collect_uncertainty(
        session, org_id="o", decision_path="symbolic", edge_ids_in_proof=[e.id]
    )
    assert any(f.kind == UncertaintyKind.DEFAULT_WEIGHT and f.target == e.id for f in flags)


@pytest.mark.unit
def test_candidate_edge_flagged(session: Session) -> None:
    """Per MD: candidate edges should NEVER appear in a finalized proof."""
    e = _seed_edge(session, eid="e_cand", status="candidate")
    session.commit()
    flags = collect_uncertainty(
        session, org_id="o", decision_path="symbolic", edge_ids_in_proof=[e.id]
    )
    assert any(f.kind == UncertaintyKind.CANDIDATE_EDGE and f.severity == "high" for f in flags)


@pytest.mark.unit
def test_no_session_skips_edge_checks() -> None:
    """When called without a session (e.g. unit test without DB), gracefully skip edge inspection."""
    flags = collect_uncertainty(
        session=None, org_id="o", decision_path="symbolic", edge_ids_in_proof=["e1"]
    )
    assert flags == []


# ── trace.build_trace ──────────────────────────────────────────────────────


@pytest.mark.unit
def test_build_trace_assembles_payload(session: Session) -> None:
    fact = FactRow(
        org_id="o",
        subject="acme",
        predicate="renewing",
        object="60d",
        source_item_id="mem_1",
        asserted_by_type="source",
        asserted_by_id="mem_1",
        confidence=1.0,
        created_at=datetime.now(UTC),
    )
    session.add(fact)
    edge = _seed_edge(session, eid="e1")
    session.commit()

    trace = build_trace(
        session,
        decision_id="dec_1",
        org_id="o",
        derivation_chain=[
            {
                "rule_id": "r1",
                "rule_priority": 80,
                "matched_facts": {"x": 1},
                "conclusion": "churn_risk_high",
            }
        ],
        grounding_ref_ids=[fact.id],
        edge_path_ids=[edge.id],
        confidence_overall=0.85,
        confidence_breakdown={"grounding": 1.0, "consistency": 0.7, "symbolic": 1.0},
        decision_path="symbolic",
        as_of_version=42,
        as_of_timestamp=datetime(2026, 6, 1, tzinfo=UTC),
    )

    assert trace.decision_id == "dec_1"
    assert len(trace.source_facts) == 1
    assert trace.source_facts[0].subject == "acme"
    assert len(trace.rules_fired) == 1
    assert trace.rules_fired[0].id == "r1"
    assert len(trace.graph_path) == 1
    assert trace.confidence.overall == 0.85
    assert trace.as_of.graph_version == 42


@pytest.mark.unit
def test_build_trace_handles_missing_fact_gracefully(session: Session) -> None:
    """Unknown fact_id in grounding_refs -> dropped (not crashed)."""
    trace = build_trace(
        session,
        decision_id="dec_1",
        org_id="o",
        derivation_chain=[],
        grounding_ref_ids=["nonexistent"],
        edge_path_ids=[],
        confidence_overall=0.5,
        confidence_breakdown={},
        decision_path="symbolic",
        as_of_version=0,
        as_of_timestamp=datetime.now(UTC),
    )
    assert trace.source_facts == []
