"""Tests for core.artifacts.graph_view — read-only subgraph extraction."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from core.artifacts.graph_view import render_graph_view
from core.foundations.db import Base
from core.graph.store import EdgeRow, NodeRow


@pytest.fixture
def session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return Session(engine)


def _node(session: Session, *, id: str, name: str, org_id: str = "o") -> None:
    session.add(
        NodeRow(
            id=id,
            org_id=org_id,
            org_unit="sales",
            type="entity",
            canonical_name=name,
            aliases=[],
            attributes={},
            source_item_ids=[],
            first_seen=datetime.now(UTC),
            last_seen=datetime.now(UTC),
        )
    )


def _edge(session: Session, *, id: str, src: str, dst: str, org_id: str = "o") -> None:
    session.add(
        EdgeRow(
            id=id,
            org_id=org_id,
            from_node=src,
            to_node=dst,
            type="dependency",
            asserted_by_type="human",
            asserted_by_id="user:alice",
            weight=0.9,
            weight_source="human",
            alpha=20,
            beta=2,
            trust=0.7,
            status="asserted",
        )
    )


@pytest.mark.unit
def test_zero_hops_returns_only_centers(session: Session) -> None:
    _node(session, id="A", name="Acme")
    _node(session, id="B", name="Bob")
    session.commit()
    v = render_graph_view(session, org_id="o", center_node_ids=["A"], hops=0)
    assert len(v.nodes) == 1
    assert v.nodes[0].id == "A"
    assert v.edges == []


@pytest.mark.unit
def test_one_hop_expands(session: Session) -> None:
    _node(session, id="A", name="Acme")
    _node(session, id="B", name="Bob")
    _node(session, id="C", name="Charlie")
    _edge(session, id="e1", src="A", dst="B")
    _edge(session, id="e2", src="B", dst="C")
    session.commit()

    v = render_graph_view(session, org_id="o", center_node_ids=["A"], hops=1)
    node_ids = {n.id for n in v.nodes}
    edge_ids = {e.id for e in v.edges}
    assert node_ids == {"A", "B"}
    assert edge_ids == {"e1"}


@pytest.mark.unit
def test_two_hops_expands_further(session: Session) -> None:
    _node(session, id="A", name="A")
    _node(session, id="B", name="B")
    _node(session, id="C", name="C")
    _edge(session, id="e1", src="A", dst="B")
    _edge(session, id="e2", src="B", dst="C")
    session.commit()

    v = render_graph_view(session, org_id="o", center_node_ids=["A"], hops=2)
    assert {n.id for n in v.nodes} == {"A", "B", "C"}
    assert {e.id for e in v.edges} == {"e1", "e2"}


@pytest.mark.unit
def test_per_org_isolation(session: Session) -> None:
    """Edge in org_a does NOT expand into org_b's view."""
    _node(session, id="A", name="A", org_id="org_a")
    _node(session, id="B", name="B", org_id="org_b")
    _edge(session, id="cross", src="A", dst="B", org_id="org_a")
    session.commit()

    v = render_graph_view(session, org_id="org_b", center_node_ids=["B"], hops=2)
    assert {n.id for n in v.nodes} == {"B"}  # A is in org_a, invisible


@pytest.mark.unit
def test_edge_provenance_visible(session: Session) -> None:
    """Per MD §6.1.1: edge provenance + weight + weight_source MUST be visible."""
    _node(session, id="A", name="A")
    _node(session, id="B", name="B")
    _edge(session, id="e1", src="A", dst="B")
    session.commit()

    v = render_graph_view(session, org_id="o", center_node_ids=["A"], hops=1)
    e = v.edges[0]
    assert e.weight == 0.9
    assert e.weight_source == "human"
    assert e.asserted_by_type == "human"
    assert e.asserted_by_id == "user:alice"


@pytest.mark.unit
def test_negative_hops_rejected(session: Session) -> None:
    with pytest.raises(ValueError):
        render_graph_view(session, org_id="o", center_node_ids=["A"], hops=-1)
