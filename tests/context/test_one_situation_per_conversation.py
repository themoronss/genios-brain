"""M2.C1 · one `awaiting_response` situation per conversation, addressed to the person.

    pytest tests/context/test_one_situation_per_conversation.py -q

MEASURED ON THE PILOT: 41 `awaiting_response` situations covering 22 distinct counterparties.
Every waiting conversation produced two — one anchored on the person (`vatsa@valiron.co`,
`confidence_overall = 10`) and one on the thread (`Thread with vatsa@valiron.co`,
`confidence_overall = 0`) — with identical `days_waiting` and `follow_up_count`.

NOBODY WROTE A BUG. `waiting.py` writes `thread.*` onto both subjects because "this thread has
waited 28 days" and "this person has waited 28 days" are genuinely different facts, and a later
reader may want either. This reading mints one anchor per node carrying those facts, so it faithfully
produced both. The two rows are not near-duplicates to be merged afterwards — one of them is simply
the wrong subject to address a card to. "Vidushi has not replied in 28 days" is the card;
"Thread with vidushi@peakxv.com has not replied" is the same sentence said worse.

THE ORPHAN CASE IS THE ONE TO GET RIGHT. Three of the pilot's twenty-one waiting threads have no
waiting party — a thread whose counterparty node was never resolved. Those must keep their
situation, or a real silence disappears into a gap nobody can see. The second block below is that
guarantee.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine, text

from genios_engine.context.outreach_situations import (
    _THREAD_COVERED_BY_PARTY,
    read_awaiting_response,
)

ORG = "org_pilot"
OTHER = "org_other"
NOW = datetime(2026, 9, 9, 12, 0, tzinfo=timezone.utc)


def _waiting(name: str, days: int = 28, **over) -> dict:
    row = {"thread.days_waiting": days, "_name": name}
    row.update(over)
    return row


def _names(findings) -> list[str]:
    return [f.display_name for f in findings]


# =============================================================================================
# The reading.
# =============================================================================================
def test_the_thread_twin_does_not_produce_a_second_situation():
    """THE DEFECT, stated directly. Both rows carry the same waiting facts; only the person's
    becomes a card."""
    rows = {
        "n_person": _waiting("vidushi@peakxv.com"),
        "n_thread": _waiting("Thread with vidushi@peakxv.com",
                             _covered_by_party="vidushi@peakxv.com"),
    }

    findings = read_awaiting_response(rows, NOW, {})

    assert _names(findings) == ["vidushi@peakxv.com — awaiting reply"]


def test_a_thread_whose_counterparty_is_unknown_keeps_its_situation():
    """THE ORPHAN. Three of the pilot's waiting threads are in this state. Suppressing them would
    trade a duplicate for a disappearance, which is the worse failure of the two."""
    rows = {"n_thread": _waiting("Thread with someone@unresolved.example")}

    findings = read_awaiting_response(rows, NOW, {})

    assert _names(findings) == ["Thread with someone@unresolved.example — awaiting reply"]


def test_the_surviving_finding_keeps_every_fact_it_had():
    """Additive suppression. Nothing about the row that stays changes."""
    rows = {"n_person": _waiting("manik@titancapital.vc", 31,
                                 **{"thread.follow_up_count": 2,
                                    "thread.last_heard_days": 31}),
            "n_thread": _waiting("Thread with manik@titancapital.vc", 31,
                                 _covered_by_party="manik@titancapital.vc")}

    [finding] = read_awaiting_response(rows, NOW, {})
    facts = {name: value for name, value, _kind in finding.facts}

    assert facts["outreach.days_waiting"] == 31
    assert facts["outreach.counterparty"] == "manik@titancapital.vc"
    assert facts["outreach.follow_up_count"] == 2
    assert facts["outreach.days_since_last_heard"] == 31


def test_the_whole_pilot_shape_collapses_to_one_per_counterparty():
    """The measured number, reproduced: eleven investors, twenty-two rows, eleven cards."""
    investors = ["siddhant@neon.fund", "vidushi@peakxv.com", "harshita@peakxv.com",
                 "manik@titancapital.vc", "joseph@afore.vc", "madison@afore.vc",
                 "shivam@together.fund", "piyush@3one4capital.com", "apply@surgeahead.com",
                 "team@zfellows.com", "adityad@iima.ac.in"]
    rows = {}
    for i, who in enumerate(investors):
        rows[f"n_person_{i}"] = _waiting(who)
        rows[f"n_thread_{i}"] = _waiting(f"Thread with {who}", _covered_by_party=who)

    findings = read_awaiting_response(rows, NOW, {})

    assert len(findings) == 11
    assert sorted(f.display_name.split(" — ")[0] for f in findings) == sorted(investors)


def test_suppression_never_fires_on_a_row_that_was_not_stamped():
    """The stamp is the only trigger. A row the bulk read did not match is untouched, which is
    what keeps this change inert on any tenant whose graph has no `corresponded_with` edges."""
    rows = {"n_a": _waiting("a@example.com"), "n_b": _waiting("b@example.com")}

    assert len(read_awaiting_response(rows, NOW, {})) == 2


def test_a_thread_still_below_the_waiting_floor_is_unaffected():
    """Unchanged behaviour, pinned because this reading now touches more of the row."""
    rows = {"n_person": _waiting("x@example.com", 0)}

    assert read_awaiting_response(rows, NOW, {}) == []


# =============================================================================================
# The read that supplies the stamp.
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
        c.execute(text(
            "create table graph_facts (org_id text, subject_node_id text, field text, "
            "status text, valid_to timestamp)"))
    with engine.begin() as c:
        yield c


def _node(c, node_id: str, node_type: str, name: str, *, org: str = ORG) -> None:
    c.execute(text("insert into graph_nodes values (:n, :o, :t, :k, :d, null)"),
              {"n": node_id, "o": org, "t": node_type, "k": name, "d": name})


def _corresponded(c, party: str, thread: str, *, org: str = ORG, valid_to=None) -> None:
    c.execute(text("insert into graph_edges values (:o, 'corresponded_with', :f, :t, :v)"),
              {"o": org, "f": party, "t": thread, "v": valid_to})


def _is_waiting(c, node_id: str, *, org: str = ORG, status: str = "active") -> None:
    c.execute(text("insert into graph_facts values (:o, :n, 'thread.days_waiting', :s, null)"),
              {"o": org, "n": node_id, "s": status})


def _rows(c, org: str = ORG):
    return c.execute(text(_THREAD_COVERED_BY_PARTY), {"o": org}).mappings().all()


def test_a_thread_whose_person_is_also_waiting_is_covered(db):
    _node(db, "n_p", "person", "Vidushi")
    _node(db, "n_t", "thread", "Thread with vidushi@peakxv.com")
    _corresponded(db, "n_p", "n_t")
    _is_waiting(db, "n_p")

    [row] = _rows(db)

    assert row["thread"] == "n_t"
    assert row["party_name"] == "Vidushi"


def test_a_party_who_is_not_waiting_does_not_cover_the_thread(db):
    """Existing is not enough. A counterparty we are NOT waiting on will mint no anchor, so
    suppressing their thread would delete the situation rather than relocate it."""
    _node(db, "n_p", "person", "Vidushi")
    _node(db, "n_t", "thread", "Thread with vidushi@peakxv.com")
    _corresponded(db, "n_p", "n_t")

    assert _rows(db) == []


def test_a_superseded_waiting_fact_does_not_cover_the_thread(db):
    _node(db, "n_p", "person", "Vidushi")
    _node(db, "n_t", "thread", "Thread with vidushi@peakxv.com")
    _corresponded(db, "n_p", "n_t")
    _is_waiting(db, "n_p", status="superseded")

    assert _rows(db) == []


def test_a_retired_edge_does_not_cover_the_thread(db):
    _node(db, "n_p", "person", "Vidushi")
    _node(db, "n_t", "thread", "Thread with vidushi@peakxv.com")
    _corresponded(db, "n_p", "n_t", valid_to="2026-01-01")
    _is_waiting(db, "n_p")

    assert _rows(db) == []


def test_a_service_counterparty_covers_its_thread_too(db):
    """`corresponded_with` also arrives from `service` nodes — two on the pilot. A vendor's
    notification address is still the subject a card would name."""
    _node(db, "n_s", "service", "notification@accubate.app")
    _node(db, "n_t", "thread", "Thread with notification@accubate.app")
    _corresponded(db, "n_s", "n_t")
    _is_waiting(db, "n_s")

    [row] = _rows(db)

    assert row["party_name"] == "notification@accubate.app"


def test_another_orgs_edge_never_covers_this_orgs_thread(db):
    """Tenancy. Every join filters org; dropping any one of them would let one tenant's
    conversation suppress another's situation."""
    _node(db, "n_p", "person", "Vidushi", org=OTHER)
    _node(db, "n_t", "thread", "Thread with vidushi@peakxv.com", org=OTHER)
    _corresponded(db, "n_p", "n_t", org=OTHER)
    _is_waiting(db, "n_p", org=OTHER)

    assert _rows(db, ORG) == []
