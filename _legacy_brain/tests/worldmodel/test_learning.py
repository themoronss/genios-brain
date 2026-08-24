"""Tests for core.worldmodel.learning — Correction → Bayesian update."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from core.foundations.db import Base
from core.graph.store import EdgeRow, NodeRow
from core.worldmodel.learning import apply_correction, derive_outcomes, effective_evidence
from core.worldmodel.store import CorrectionRow


@pytest.fixture
def session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return Session(engine)


def _seed_edge(session: Session, eid: str = "e1") -> EdgeRow:
    a = NodeRow(
        id="n1",
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
        id="n2",
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
    e = EdgeRow(
        id=eid,
        org_id="o",
        from_node="n1",
        to_node="n2",
        type="influence",
        asserted_by_type="rule",
        asserted_by_id="rule:test",
        weight=0.5,
        weight_source="default",
        alpha=5,
        beta=5,
        trust=0.0,
    )
    session.add(e)
    session.flush()
    return e


@pytest.mark.unit
def test_derive_outcomes_from_diff() -> None:
    diff = {
        "edges_confirmed": ["e1", "e2"],
        "edges_contradicted": ["e3"],
    }
    out = derive_outcomes(diff)
    assert out == {"e1": True, "e2": True, "e3": False}


@pytest.mark.unit
def test_apply_correction_confirm_increases_alpha(session: Session) -> None:
    edge = _seed_edge(session)
    session.commit()

    correction = CorrectionRow(
        org_id="o",
        decision_id="dec_1",
        input_context={"q": "is Acme at risk?"},
        engine_decision={"verdict": "yes"},
        human_decision={"verdict": "yes"},
        diff={"edges_confirmed": [edge.id]},
        rule_ids=[],
        edge_ids=[edge.id],
        actor="user:alice",
    )
    session.add(correction)
    session.flush()

    updates = apply_correction(session, correction=correction)
    session.commit()

    assert len(updates) == 1
    refreshed = session.get(EdgeRow, edge.id)
    assert refreshed is not None
    assert refreshed.alpha == 6  # was 5, +1 from confirm
    assert refreshed.beta == 5
    assert refreshed.weight > 0.5


@pytest.mark.unit
def test_apply_correction_contradict_increases_beta(session: Session) -> None:
    edge = _seed_edge(session)
    session.commit()

    correction = CorrectionRow(
        org_id="o",
        decision_id="dec_1",
        input_context={},
        engine_decision={},
        human_decision={},
        diff={"edges_contradicted": [edge.id]},
        rule_ids=[],
        edge_ids=[edge.id],
        actor="user:alice",
    )
    session.add(correction)
    session.flush()

    apply_correction(session, correction=correction)
    session.commit()

    refreshed = session.get(EdgeRow, edge.id)
    assert refreshed is not None
    assert refreshed.beta == 6
    assert refreshed.weight < 0.5


@pytest.mark.unit
def test_apply_correction_skips_unknown_edges(session: Session) -> None:
    """Robust: unknown edge_id in diff → logged + skipped, doesn't crash."""
    correction = CorrectionRow(
        org_id="o",
        decision_id="dec_1",
        input_context={},
        engine_decision={},
        human_decision={},
        diff={"edges_confirmed": ["nonexistent"]},
        rule_ids=[],
        edge_ids=["nonexistent"],
        actor="user:alice",
    )
    session.add(correction)
    session.flush()

    updates = apply_correction(session, correction=correction)
    assert updates == []  # nothing applied


@pytest.mark.unit
def test_effective_evidence_decays_with_age() -> None:
    """Old evidence weighs less after time decay."""
    now = datetime.now(UTC)
    fresh_alpha, fresh_beta = effective_evidence(
        alpha=100, beta=50, last_update_at=now - timedelta(days=1)
    )
    old_alpha, old_beta = effective_evidence(
        alpha=100, beta=50, last_update_at=now - timedelta(days=365)
    )
    assert fresh_alpha > old_alpha
    assert fresh_beta > old_beta
