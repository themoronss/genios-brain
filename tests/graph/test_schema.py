"""Tests for core.graph.schema — engine-facing types + the post-hoc-fallacy guard."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from core.graph.schema import (
    AssertionSource,
    CandidateEdge,
    Edge,
    EdgeStatus,
    EdgeType,
    Fact,
    Node,
    NodeType,
    WeightSource,
)


def _now() -> datetime:
    return datetime(2026, 6, 1, tzinfo=UTC)


@pytest.mark.unit
def test_fact_construction() -> None:
    f = Fact(
        id="f1",
        org_id="o",
        subject="Bob",
        predicate="emailed",
        object="Acme",
        source_item_id="mem_abc",
        asserted_by_type=AssertionSource.SOURCE,
        asserted_by_id="mem_abc",
        confidence=0.9,
        created_at=_now(),
    )
    assert f.confidence == 0.9
    assert f.asserted_by_type == AssertionSource.SOURCE


@pytest.mark.unit
def test_fact_confidence_bounded() -> None:
    with pytest.raises(ValidationError):
        Fact(
            id="f1",
            org_id="o",
            subject="x",
            predicate="y",
            object="z",
            source_item_id="m",
            asserted_by_type=AssertionSource.SOURCE,
            asserted_by_id="m",
            confidence=1.5,  # out of range
            created_at=_now(),
        )


@pytest.mark.unit
def test_node_basic() -> None:
    n = Node(
        id="n1",
        org_id="o",
        org_unit="sales",
        type=NodeType.ENTITY,
        canonical_name="Bob Smith",
        aliases=["Robert Smith", "R. Smith"],
        first_seen=_now(),
        last_seen=_now(),
    )
    assert "Robert Smith" in n.aliases
    assert n.type == NodeType.ENTITY


@pytest.mark.unit
def test_edge_with_provenance_ok() -> None:
    e = Edge(
        id="e1",
        org_id="o",
        from_node="n1",
        to_node="n2",
        type=EdgeType.TEMPORAL,
        asserted_by_type=AssertionSource.SOURCE,
        asserted_by_id="mem_xyz",
        asserted_at=_now(),
        weight=0.8,
        weight_source=WeightSource.FREQUENCY,
        alpha=10,
        beta=2,
    )
    assert e.status == EdgeStatus.ASSERTED
    assert e.weight_source == WeightSource.FREQUENCY


@pytest.mark.unit
def test_influence_edge_rejects_source_assertion() -> None:
    """The HARD RULE per MD g-i-2 §2.1.1 — influence cannot be auto-inferred from sources."""
    with pytest.raises(ValidationError) as excinfo:
        Edge(
            id="e1",
            org_id="o",
            from_node="n1",
            to_node="n2",
            type=EdgeType.INFLUENCE,
            asserted_by_type=AssertionSource.SOURCE,
            asserted_by_id="some_event",
            asserted_at=_now(),
        )
    assert (
        "post-hoc fallacy" in str(excinfo.value).lower()
        or "influence" in str(excinfo.value).lower()
    )


@pytest.mark.unit
def test_influence_edge_with_rule_or_human_ok() -> None:
    """Influence edges OK when asserted by a rule or a human."""
    e_rule = Edge(
        id="e1",
        org_id="o",
        from_node="n1",
        to_node="n2",
        type=EdgeType.INFLUENCE,
        asserted_by_type=AssertionSource.RULE,
        asserted_by_id="rule:churn_v1",
        asserted_at=_now(),
    )
    assert e_rule.type == EdgeType.INFLUENCE

    e_human = Edge(
        id="e2",
        org_id="o",
        from_node="n1",
        to_node="n2",
        type=EdgeType.INFLUENCE,
        asserted_by_type=AssertionSource.HUMAN,
        asserted_by_id="user:alice",
        asserted_at=_now(),
    )
    assert e_human.asserted_by_id == "user:alice"


@pytest.mark.unit
def test_candidate_edge_lift_must_be_positive() -> None:
    with pytest.raises(ValidationError):
        CandidateEdge(
            id="c1",
            org_id="o",
            from_node="n1",
            to_node="n2",
            signal_lift=-0.1,  # invalid
            co_occurrence_count=5,
            proposed_at=_now(),
        )

    ok = CandidateEdge(
        id="c1",
        org_id="o",
        from_node="n1",
        to_node="n2",
        signal_lift=2.5,
        co_occurrence_count=30,
        proposed_at=_now(),
    )
    assert ok.status == "proposed"
