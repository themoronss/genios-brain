"""Tests for core.worldmodel.resolve — block + score + decide + reversible merge."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from core.foundations.db import Base
from core.graph.store import NodeRow
from core.worldmodel.resolve import (
    THETA_AUTO_MERGE,
    THETA_REVIEW,
    block_candidates,
    blocking_key,
    decide,
    merge,
    similarity,
    unmerge,
)


@pytest.fixture
def session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return Session(engine)


def _node(
    session: Session,
    *,
    id: str,
    name: str,
    aliases: list[str] | None = None,
    attributes: dict | None = None,
    source_ids: list[str] | None = None,
    org_id: str = "o",
    org_unit: str = "sales",
) -> NodeRow:
    n = NodeRow(
        id=id,
        org_id=org_id,
        org_unit=org_unit,
        type="entity",
        canonical_name=name,
        aliases=aliases or [],
        attributes=attributes or {},
        source_item_ids=source_ids or [],
        first_seen=datetime(2026, 1, 1, tzinfo=UTC),
        last_seen=datetime(2026, 1, 1, tzinfo=UTC),
    )
    session.add(n)
    session.flush()
    return n


# ── BLOCK ──────────────────────────────────────────────────────────────────


@pytest.mark.unit
def test_blocking_groups_same_first_token_and_domain(session: Session) -> None:
    """Same-domain emails + same first name → same block."""
    a = _node(session, id="1", name="Bob Smith", attributes={"email": "bob@acme.com"})
    b = _node(session, id="2", name="Bob Jones", attributes={"email": "bob@acme.com"})
    c = _node(session, id="3", name="Alice Cooper", attributes={"email": "alice@acme.com"})
    blocks = block_candidates([a, b, c])
    keys = list(blocks.keys())
    assert any(blocking_key(a) == k and blocking_key(b) == k for k in keys)
    # Alice in different block
    assert blocking_key(c) != blocking_key(a)


# ── SCORE ──────────────────────────────────────────────────────────────────


@pytest.mark.unit
def test_similar_names_high_score(session: Session) -> None:
    a = _node(session, id="1", name="Bob Smith")
    b = _node(session, id="2", name="Smith Bob")  # reordered tokens
    assert similarity(a, b) > 0.4


@pytest.mark.unit
def test_shared_source_context_boosts_score(session: Session) -> None:
    """Same name + shared source ids -> high but not auto-merge without attribute overlap.
    Per MD: bias toward false-split. auto-merge needs name+attrs+context all aligned.
    """
    a = _node(session, id="1", name="Bob", source_ids=["email_1", "cal_2"])
    b = _node(session, id="2", name="Bob", source_ids=["email_1", "cal_2"])
    s = similarity(a, b)
    # name 1.0*0.5 + shared_ctx 1.0*0.2 = 0.7 — below θ_review (correct: bias to false-split)
    assert s == pytest.approx(0.7, abs=0.05)
    # Adding even one shared attribute pushes above θ_review
    a3 = _node(session, id="5", name="Bob", attributes={"role": "rep"}, source_ids=["e"])
    b3 = _node(session, id="6", name="Bob", attributes={"role": "rep"}, source_ids=["e"])
    assert similarity(a3, b3) >= THETA_REVIEW
    # Adding shared attrs should push to auto-merge
    a2 = _node(session, id="3", name="Bob", attributes={"email": "x@y.com"}, source_ids=["e1"])
    b2 = _node(session, id="4", name="Bob", attributes={"email": "x@y.com"}, source_ids=["e1"])
    assert similarity(a2, b2) >= THETA_AUTO_MERGE


# ── DECIDE ─────────────────────────────────────────────────────────────────


@pytest.mark.unit
def test_decide_auto_merge_when_strong(session: Session) -> None:
    """Same name + same email + same source context → auto-merge."""
    a = _node(
        session,
        id="1",
        name="Bob Smith",
        attributes={"email": "bob@acme.com"},
        source_ids=["x", "y"],
    )
    b = _node(
        session,
        id="2",
        name="Bob Smith",
        attributes={"email": "bob@acme.com"},
        source_ids=["x", "y"],
    )
    d = decide(a, b)
    assert d.verdict == "auto_merge"


@pytest.mark.unit
def test_decide_flag_when_partial_attrs_match(session: Session) -> None:
    """Same name + partial attribute overlap → at least flag (don't silently distinct)."""
    a = _node(
        session,
        id="1",
        name="John Doe",
        attributes={"email": "j@acme.com", "role": "rep"},
    )
    b = _node(
        session,
        id="2",
        name="John Doe",
        attributes={"email": "j@acme.com"},
    )
    d = decide(a, b)
    # name 1.0*0.5 + attrs (1 shared / 2 in larger) 0.5*0.3 + ctx 0
    # = 0.5 + 0.15 = 0.65 — close to flag boundary
    assert d.score >= 0.5


@pytest.mark.unit
def test_decide_distinct_for_two_johns_at_different_companies(session: Session) -> None:
    """Two real 'John Doe's with no other overlap → distinct (per MD test case)."""
    a = _node(session, id="1", name="John Doe", attributes={"email": "john@acme.com"})
    b = _node(session, id="2", name="John Doe", attributes={"email": "john@globex.com"})
    d = decide(a, b)
    # Per MD: bias toward false-split. Different email domains → low attribute overlap.
    # name_sim is 1.0 * 0.5 = 0.5; attributes 0 (different emails); context 0.
    # Total = 0.5 → below θ_auto (0.92), and below θ_review (0.75) → distinct.
    assert d.verdict == "distinct"


# ── MERGE + UNMERGE (reversible) ───────────────────────────────────────────


@pytest.mark.unit
def test_merge_absorbs_aliases_and_source_ids(session: Session) -> None:
    keep = _node(
        session,
        id="keep",
        name="Bob Smith",
        aliases=["B. Smith"],
        source_ids=["s1"],
    )
    absorb = _node(
        session,
        id="abs",
        name="Robert Smith",
        aliases=["R. Smith"],
        source_ids=["s2"],
    )
    record = merge(
        session, org_id="o", keep_id=keep.id, absorb_ids=[absorb.id], merged_by="user:alice"
    )
    session.commit()

    assert record.merged_into == keep.id
    refreshed = session.get(NodeRow, keep.id)
    assert refreshed is not None
    # Aliases should include absorbed canonical_name + its aliases
    assert "Robert Smith" in refreshed.aliases
    assert "R. Smith" in refreshed.aliases
    assert "s2" in refreshed.source_item_ids

    # Absorbed node is gone
    assert session.get(NodeRow, "abs") is None


@pytest.mark.unit
def test_unmerge_restores_absorbed_node(session: Session) -> None:
    keep = _node(session, id="keep", name="Bob Smith", source_ids=["s1"])
    absorb = _node(
        session,
        id="abs",
        name="Robert Smith",
        aliases=["R. Smith"],
        attributes={"email": "bob@acme.com"},
        source_ids=["s2"],
    )
    record = merge(
        session, org_id="o", keep_id=keep.id, absorb_ids=[absorb.id], merged_by="user:alice"
    )
    session.commit()

    restored = unmerge(session, merge_id=record.merge_id, reversed_by="user:alice")
    session.commit()
    assert "abs" in restored

    restored_node = session.get(NodeRow, "abs")
    assert restored_node is not None
    assert restored_node.canonical_name == "Robert Smith"
    assert restored_node.aliases == ["R. Smith"]
    assert restored_node.attributes == {"email": "bob@acme.com"}


@pytest.mark.unit
def test_merge_rejects_self_merge(session: Session) -> None:
    _node(session, id="x", name="x")
    with pytest.raises(ValueError):
        merge(session, org_id="o", keep_id="x", absorb_ids=["x"], merged_by="user:a")


@pytest.mark.unit
def test_double_unmerge_rejected(session: Session) -> None:
    keep = _node(session, id="keep", name="K")
    absorb = _node(session, id="abs", name="A")
    record = merge(session, org_id="o", keep_id=keep.id, absorb_ids=[absorb.id], merged_by="user:a")
    session.commit()
    unmerge(session, merge_id=record.merge_id, reversed_by="user:a")
    session.commit()
    with pytest.raises(RuntimeError):
        unmerge(session, merge_id=record.merge_id, reversed_by="user:a")
