"""M3.C1 · a promise is attributed to whoever made it.

    pytest tests/context/test_commitment_owner.py -q

THE THREE CARDS. On the pilot tenant, three of the nine cards rendered somebody ELSE's promise as
the founder's own overdue obligation, at critical urgency, in the founder's voice — the single
most embarrassing failure in the feed, because it is not a ranking mistake a user can shrug at.
It tells them they broke a promise they never made.

AND THE DATA WAS ALREADY THERE. `context/pipeline.py` writes an `owns` edge from the commitment
ACTOR to the commitment node, tagged `{"derived": "commitment actor"}`. It has been written on
every commitment this system has ever extracted. `read_overdue_commitments` simply never asked,
and its own docstring — "one finding per promise of OURS" — was an assumption the code never
checked.

So this is not new intelligence. It is a read of a fact the graph has always held.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine, text

from genios_engine.context.outreach_situations import (
    _COMMITMENT_OWNERS,
    read_overdue_commitments,
)

ORG = "org_pilot"
NOW = datetime(2026, 9, 8, 12, 0, tzinfo=timezone.utc)
OVERDUE = (NOW - timedelta(days=6)).isoformat()


def _rows(**over) -> dict:
    """One overdue commitment, shaped the way `_gather` shapes a held row."""
    row = {"commitment.due_at": OVERDUE, "commitment.action": "share the updated deck",
           "_name": "John Carter"}
    row.update(over)
    return {"cmt_1": row}


def _facts(finding) -> dict:
    return {name: value for name, value, _kind in finding.facts}


# =============================================================================================
# The reader.
# =============================================================================================
def test_a_promise_someone_else_made_names_them():
    """The regression, stated directly."""
    [finding] = read_overdue_commitments(
        _rows(_owner_name="Priya Nair", _owner_key="priya@acme.ai"), NOW, {})

    facts = _facts(finding)
    assert facts["commitment.owner"] == "Priya Nair"
    assert facts["commitment.owner_key"] == "priya@acme.ai"


def test_the_display_name_says_who_owes_whom():
    """"John Carter — promise past due" reads as the founder's failure whoever made it. Naming the
    owner is what stops the card being about the wrong person before anyone opens it."""
    [finding] = read_overdue_commitments(_rows(_owner_name="Priya Nair"), NOW, {})

    assert finding.display_name == "Priya Nair — promise to John Carter past due"


def test_an_unknown_owner_is_left_absent_rather_than_assumed_to_be_us():
    """The important half of the fix. "We do not know who promised this" and "the founder promised
    this" are different cards, and the second was being shown for both. Absent stays absent, and
    the card that renders it must not use an imperative."""
    [finding] = read_overdue_commitments(_rows(), NOW, {})

    facts = _facts(finding)
    assert "commitment.owner" not in facts
    assert "commitment.owner_key" not in facts
    assert finding.display_name == "John Carter — promise past due"


def test_the_owner_does_not_disturb_the_facts_the_card_already_had():
    """Additive. Everything `commitment_overdue` rendered before still renders."""
    [finding] = read_overdue_commitments(_rows(_owner_name="Priya Nair"), NOW, {})

    facts = _facts(finding)
    assert facts["commitment.owed_to"] == "John Carter"
    assert facts["commitment.action"] == "share the updated deck"
    assert facts["commitment.days_overdue"] == 6


def test_a_commitment_with_no_date_is_still_not_overdue():
    """Unchanged behaviour, pinned because this reading now touches more of the row: a promise
    with no date is a different situation and must produce nothing here."""
    assert read_overdue_commitments({"cmt_1": {"_name": "John", "_owner_name": "Priya"}},
                                    NOW, {}) == []


# =============================================================================================
# The read that supplies it.
# =============================================================================================
@pytest.fixture()
def db():
    engine = create_engine("sqlite://")
    with engine.begin() as c:
        c.execute(text(
            "create table graph_edges (org_id text, edge_type text, from_node_id text, "
            "to_node_id text, valid_to timestamp)"))
        c.execute(text(
            "create table graph_nodes (node_id text, org_id text, node_type text, "
            "canonical_key text, display_name text, valid_to timestamp)"))
    with engine.begin() as c:
        yield c


def _owns(c, owner_node: str, commitment_node: str, *, org: str = ORG, valid_to=None) -> None:
    c.execute(text("insert into graph_edges values (:o, 'owns', :f, :t, :v)"),
              {"o": org, "f": owner_node, "t": commitment_node, "v": valid_to})


def _person(c, node_id: str, name: str, email: str) -> None:
    c.execute(text("insert into graph_nodes values (:n, :o, 'person', :k, :d, null)"),
              {"n": node_id, "o": ORG, "k": email, "d": name})


def test_the_owns_edge_resolves_to_a_named_person(db):
    _person(db, "n_priya", "Priya Nair", "priya@acme.ai")
    _owns(db, "n_priya", "cmt_1")

    [row] = db.execute(text(_COMMITMENT_OWNERS), {"o": ORG}).mappings().all()

    assert row["commitment"] == "cmt_1"
    assert row["owner_name"] == "Priya Nair"
    assert row["owner_key"] == "priya@acme.ai"


def test_a_retired_edge_is_ignored(db):
    _person(db, "n_priya", "Priya Nair", "priya@acme.ai")
    _owns(db, "n_priya", "cmt_1", valid_to="2026-01-01")

    assert db.execute(text(_COMMITMENT_OWNERS), {"o": ORG}).mappings().all() == []


def test_another_orgs_ownership_is_never_visible(db):
    _person(db, "n_priya", "Priya Nair", "priya@acme.ai")
    _owns(db, "n_priya", "cmt_1", org="org_other")

    assert db.execute(text(_COMMITMENT_OWNERS), {"o": ORG}).mappings().all() == []
