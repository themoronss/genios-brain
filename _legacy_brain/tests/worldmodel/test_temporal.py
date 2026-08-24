"""Tests for core.worldmodel.temporal — as_of / diff / history queries."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from core.foundations.db import Base
from core.worldmodel.temporal import (
    append_event,
    as_of,
    capture_snapshot,
    diff,
    history,
    should_snapshot,
)


@pytest.fixture
def session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return Session(engine)


@pytest.mark.unit
def test_as_of_empty_graph_returns_empty_state(session: Session) -> None:
    state = as_of(session, org_id="o", when=datetime.now(UTC))
    assert state.version == 0
    assert state.nodes == {}
    assert state.edges == {}


@pytest.mark.unit
def test_as_of_replays_events(session: Session) -> None:
    """Add 3 events; as_of reconstructs all 3."""
    append_event(
        session,
        org_id="o",
        event_type="node_add",
        target_type="node",
        target_id="n1",
        payload={"name": "Bob"},
    )
    append_event(
        session,
        org_id="o",
        event_type="edge_add",
        target_type="edge",
        target_id="e1",
        payload={"from": "n1", "to": "n2"},
    )
    append_event(
        session,
        org_id="o",
        event_type="node_update",
        target_type="node",
        target_id="n1",
        payload={"role": "rep"},
    )
    session.commit()

    state = as_of(session, org_id="o", when=datetime.now(UTC))
    assert state.version == 3
    assert state.nodes["n1"]["name"] == "Bob"
    assert state.nodes["n1"]["role"] == "rep"
    assert state.edges["e1"]["from"] == "n1"


@pytest.mark.unit
def test_diff_returns_events_in_window(session: Session) -> None:
    t0 = datetime.now(UTC) - timedelta(seconds=60)
    append_event(
        session, org_id="o", event_type="node_add", target_type="node", target_id="n1", payload={}
    )
    session.commit()

    d = diff(session, org_id="o", from_time=t0, to_time=datetime.now(UTC))
    assert len(d.events) == 1


@pytest.mark.unit
def test_history_for_target_only(session: Session) -> None:
    append_event(
        session,
        org_id="o",
        event_type="node_add",
        target_type="node",
        target_id="n1",
        payload={},
    )
    append_event(
        session,
        org_id="o",
        event_type="node_add",
        target_type="node",
        target_id="n2",
        payload={},
    )
    append_event(
        session,
        org_id="o",
        event_type="node_update",
        target_type="node",
        target_id="n1",
        payload={"x": 1},
    )
    session.commit()

    h = history(session, org_id="o", target_id="n1")
    assert len(h) == 2
    assert {e.event_type for e in h} == {"node_add", "node_update"}


@pytest.mark.unit
def test_should_snapshot_true_when_no_snapshot(session: Session) -> None:
    assert should_snapshot(session, org_id="o") is True


@pytest.mark.unit
def test_snapshot_speeds_up_as_of(session: Session) -> None:
    """After snapshot, as_of starts from snapshot version (not from 0)."""
    append_event(
        session,
        org_id="o",
        event_type="node_add",
        target_type="node",
        target_id="n1",
        payload={"name": "Bob"},
    )
    session.commit()
    capture_snapshot(session, org_id="o", nodes={"n1": {"name": "Bob"}}, edges={})
    session.commit()

    # Add more events
    append_event(
        session,
        org_id="o",
        event_type="node_update",
        target_type="node",
        target_id="n1",
        payload={"role": "rep"},
    )
    session.commit()

    state = as_of(session, org_id="o", when=datetime.now(UTC))
    # Snapshot held n1, then update applied
    assert state.nodes["n1"]["name"] == "Bob"
    assert state.nodes["n1"]["role"] == "rep"


@pytest.mark.unit
def test_diff_rejects_inverted_window(session: Session) -> None:
    with pytest.raises(ValueError):
        diff(
            session,
            org_id="o",
            from_time=datetime.now(UTC),
            to_time=datetime.now(UTC) - timedelta(seconds=10),
        )
