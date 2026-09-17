"""They asked what our ARR is. We wrote back "let me check". The ledger recorded it answered.

`close_loops_for_reply` closes every open loop a person has on the thread whatever the closing
message said, and its call site claimed the opposite in as many words — "the ledger says WHICH
requests this reply answered — one row each, never the whole person". `close_loops_awaited_from`
has the same shape inbound: we ask, they reply "will revert shortly", the ask is recorded as met.

It is the failure `read_overdue_commitments` refuses by name one module over: "Sending something
afterwards is not sending THE thing... received, complete, valid and accepted are four different
facts." The commitment reading states that and declines to close a promise on it. The loop ledger
did not.

WHAT IS NOT BEING TESTED HERE, because it is not being done: loops are not held open. Requiring
proof of an answer before closing would refuse on an ABSENCE, and a founder would be chased about
questions answered months ago. Every loop closes exactly when it closed before.
"""
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine, text

from genios_engine.context.open_loops import close_loops_awaited_from, close_loops_for_reply
from genios_engine.context.vocabulary import (CLOSED_ANSWERED, CLOSED_BASIS, CLOSED_REPLIED,
                                              discharged_asks)

ORG = "o"
NOW = datetime(2026, 9, 20, 12, 0, tzinfo=timezone.utc)
EARLIER = NOW - timedelta(days=3)


def _loops(*rows):
    e = create_engine("sqlite://")
    with e.begin() as c:
        c.execute(text("create table open_loops (loop_id text primary key, org_id text, "
                       "subject_node_id text, awaited_from_node_id text, kind text, "
                       "thread_id text, status text, opened_at timestamp, closed_at timestamp, "
                       "closed_by_event text, closed_basis text)"))
        for i, (kind, subject, awaited) in enumerate(rows):
            c.execute(text(
                "insert into open_loops (loop_id, org_id, subject_node_id, "
                "awaited_from_node_id, kind, thread_id, status, opened_at) "
                "values (:i,:o,:s,:a,:k,'t1','open',:at)"),
                {"i": f"l{i}", "o": ORG, "s": subject, "a": awaited, "k": kind, "at": EARLIER})
    return e


def _state(e):
    with e.connect() as c:
        return {r[0]: (r[1], r[2]) for r in c.execute(text(
            "select kind, status, closed_basis from open_loops")).all()}


# ── the vocabulary ───────────────────────────────────────────────────────────────────────────

def test_the_two_bases_are_closed() -> None:
    assert CLOSED_BASIS == {CLOSED_ANSWERED, CLOSED_REPLIED}


@pytest.mark.parametrize("kind, asks", [
    ("approval_granted", {"approval_requested"}),
    ("approval_blocked", {"approval_requested"}),       # a refusal answers the ask
    ("intro_made", {"intro_requested"}),
    ("document_sent", {"information_requested"}),
    ("meeting_scheduled", {"meeting_request", "demo_requested"}),
])
def test_a_declared_pair_discharges_its_ask(kind: str, asks: set) -> None:
    assert discharged_asks([kind]) == asks


@pytest.mark.parametrize("kind", ["question", "followup_sent", "positive_reply", "going_dark",
                                  "sample_collected"])
def test_everything_else_discharges_nothing(kind: str) -> None:
    """Most kinds keep the empty default. "What is your ARR?" is discharged by a SENTENCE, and no
    kind in this vocabulary means "answered the question" — so a reply to one is contact."""
    assert discharged_asks([kind]) == frozenset()


# ── the closure still happens, and now says what it rests on ─────────────────────────────────

def test_a_reply_that_answers_nothing_still_closes_the_loop() -> None:
    """The property that must not change. Holding it open would refuse on an absence."""
    e = _loops(("question", "them", None))
    with e.begin() as c:
        assert close_loops_for_reply(c, org_id=ORG, subject_node_id="them", thread_id="t1",
                                     event_id="e1", at=NOW,
                                     discharged=discharged_asks(["followup_sent"])) == 1
    assert _state(e)["question"] == ("closed", CLOSED_REPLIED)


def test_a_reply_that_answers_is_recorded_as_answered() -> None:
    e = _loops(("approval_requested", "them", None))
    with e.begin() as c:
        close_loops_for_reply(c, org_id=ORG, subject_node_id="them", thread_id="t1",
                              event_id="e1", at=NOW,
                              discharged=discharged_asks(["approval_granted"]))
    assert _state(e)["approval_requested"] == ("closed", CLOSED_ANSWERED)


def test_one_message_can_answer_one_ask_and_merely_reach_the_others() -> None:
    """The reason the verdict is a CASE over each row rather than one value for the statement.
    An approval arriving does not answer the unrelated question sitting beside it."""
    e = _loops(("approval_requested", "them", None),
               ("question", "them", None),
               ("intro_requested", "them", None))
    with e.begin() as c:
        close_loops_for_reply(c, org_id=ORG, subject_node_id="them", thread_id="t1",
                              event_id="e1", at=NOW,
                              discharged=discharged_asks(["approval_granted"]))
    state = _state(e)
    assert state["approval_requested"] == ("closed", CLOSED_ANSWERED)
    assert state["question"] == ("closed", CLOSED_REPLIED)
    assert state["intro_requested"] == ("closed", CLOSED_REPLIED)


def test_the_inbound_closer_records_it_too() -> None:
    """We ask, they reply "will revert shortly", the ask was recorded as met."""
    e = _loops(("information_requested", "us", "them"))
    with e.begin() as c:
        close_loops_awaited_from(c, org_id=ORG, node_id="them", thread_id="t1",
                                 event_id="e1", at=NOW,
                                 discharged=discharged_asks(["positive_reply"]))
    assert _state(e)["information_requested"] == ("closed", CLOSED_REPLIED)


def test_the_inbound_closer_can_also_see_an_answer() -> None:
    e = _loops(("information_requested", "us", "them"))
    with e.begin() as c:
        close_loops_awaited_from(c, org_id=ORG, node_id="them", thread_id="t1",
                                 event_id="e1", at=NOW,
                                 discharged=discharged_asks(["document_sent"]))
    assert _state(e)["information_requested"] == ("closed", CLOSED_ANSWERED)


@pytest.mark.parametrize("discharged", [None, frozenset()])
def test_a_caller_that_says_nothing_gets_replied_and_never_a_sql_error(discharged) -> None:
    """An empty set must skip the CASE rather than emit `kind in ()` — a syntax error on some
    drivers and a silent falsehood on the rest. `None` is the pre-existing caller."""
    e = _loops(("question", "them", None))
    with e.begin() as c:
        assert close_loops_for_reply(c, org_id=ORG, subject_node_id="them", thread_id="t1",
                                     event_id="e1", at=NOW, discharged=discharged) == 1
    assert _state(e)["question"] == ("closed", CLOSED_REPLIED)
