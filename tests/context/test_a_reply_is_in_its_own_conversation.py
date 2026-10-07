"""STEP-10 · a reply is a reply in its own conversation — theirs and yours are measured inside each thread.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… pytest tests/context/test_a_reply_is_in_its_own_conversation.py -q

`context/waiting` (tree `yc2_w27_s10 · M29.C1.L-logic.V2.U06`). Found while building the file's numbers: both
reply times were read off ONE timeline per counterparty, merged across every thread. So a new topic they
opened two days after our pitch, on another thread, counted as their two-day reply; and our one-day answer
to their second thread was measured from their first mail a week before — the plan's own words for your
reply time are "in the same conversation" (`STEP-10` §8.4). Now each gap is measured inside one
conversation — the Gmail thread — and pooled per counterparty; a message with no thread pairs with nothing.
The waiting state (who spoke last, for how long) stays per counterparty.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import text

from genios_engine.context.waiting import (compute_waiting, conversation_our_reply_gaps,
                                           conversation_reply_gaps, directed_timelines,
                                           our_reply_gaps_of, reply_gaps_of)

from .workstream_world import FOUNDER, T0, node, process, reset, tenant

pytestmark = pytest.mark.pg

ORG = "org_s10_own_conversation"
PRIYA = "priya@northwind.test"
NOW = T0 + timedelta(days=90)


@pytest.fixture
def store(pg_store):
    tenant(pg_store, ORG)
    yield pg_store
    reset(pg_store, ORG)


def test_the_merged_timeline_misread_both_and_the_conversations_do_not():
    t = datetime(2026, 9, 1, tzinfo=timezone.utc)
    day = timedelta(days=1)
    conversations = {"thread:t1": [("out", t), ("in", t + 3 * day)],
                     "thread:t2": [("in", t + 10 * day), ("out", t + 11 * day)]}
    merged = sorted((m for c in conversations.values() for m in c), key=lambda m: m[1])
    assert (reply_gaps_of(merged), our_reply_gaps_of(merged)) == ([3.0], [8.0]), "the old reading"
    assert conversation_reply_gaps(conversations) == [3.0]
    assert conversation_our_reply_gaps(conversations) == [1.0], "measured from the mail it answers"


def _conversations(store, key: str) -> dict:
    with store.engine.connect() as c:
        _per_node, _types, conversations = directed_timelines(c, ORG, now=NOW)
    return conversations[node(store, ORG, key).node_id]


def test_a_new_topic_on_another_thread_is_not_their_reply(store):
    """Five answers on their own threads, a day each; then our pitch on t_pitch, and two days later
    a new topic of hers on t_new. Five replies — not six."""
    for i in range(5):
        process(store, ORG, event_id=f"evt_q{i}", sender=FOUNDER, recipients=(PRIYA,),
                thread=f"t_{i}", at=T0 + timedelta(days=5 * i))
        process(store, ORG, event_id=f"evt_a{i}", sender=PRIYA, thread=f"t_{i}",
                at=T0 + timedelta(days=5 * i + 1))
    process(store, ORG, event_id="evt_pitch", sender=FOUNDER, recipients=(PRIYA,),
            thread="t_pitch", at=T0 + timedelta(days=30))
    process(store, ORG, event_id="evt_new", sender=PRIYA, thread="t_new",
            at=T0 + timedelta(days=32))
    assert conversation_reply_gaps(_conversations(store, PRIYA)) == [1.0] * 5
    compute_waiting(store, ORG, now=NOW)
    with store.engine.connect() as c:
        n = c.execute(text(
            "select f.value #>> '{}' from graph_facts f join graph_nodes p on p.org_id = f.org_id "
            "   and p.node_id = f.subject_node_id and p.valid_to is null "
            " where f.org_id = :o and p.canonical_key = :k and f.field = 'party.reply_cadence_n' "
            "   and f.valid_to is null"), {"o": ORG, "k": PRIYA}).scalar()
    assert n == "5"


def test_your_answer_is_measured_from_the_mail_it_answers(store):
    process(store, ORG, event_id="evt_hers_1", sender=PRIYA, thread="t1", at=T0)
    process(store, ORG, event_id="evt_hers_2", sender=PRIYA, thread="t2", at=T0 + timedelta(days=10))
    process(store, ORG, event_id="evt_ours", sender=FOUNDER, recipients=(PRIYA,), thread="t2",
            at=T0 + timedelta(days=11))
    assert conversation_our_reply_gaps(_conversations(store, PRIYA)) == [1.0]


def test_a_message_with_no_thread_pairs_with_nothing(store):
    process(store, ORG, event_id="evt_out", sender=FOUNDER, recipients=(PRIYA,), thread=None, at=T0)
    process(store, ORG, event_id="evt_in", sender=PRIYA, thread=None, at=T0 + timedelta(days=1))
    conversations = _conversations(store, PRIYA)
    assert sorted(conversations) == ["event:evt_in", "event:evt_out"]
    assert conversation_reply_gaps(conversations) == []


def test_the_waiting_state_is_still_about_them_not_one_thread(store):
    """We answered her on t1 and pitched her on t2: she owes the reply on t2, so we wait — on her."""
    process(store, ORG, event_id="evt_hers", sender=PRIYA, thread="t1", at=T0)
    process(store, ORG, event_id="evt_ours", sender=FOUNDER, recipients=(PRIYA,), thread="t2",
            at=T0 + timedelta(days=2))
    compute_waiting(store, ORG, now=T0 + timedelta(days=12))
    with store.engine.connect() as c:
        waiting = c.execute(text(
            "select f.value #>> '{}' from graph_facts f join graph_nodes p on p.org_id = f.org_id "
            "   and p.node_id = f.subject_node_id and p.valid_to is null "
            " where f.org_id = :o and p.canonical_key = :k and f.field = 'thread.days_waiting' "
            "   and f.valid_to is null"), {"o": ORG, "k": PRIYA}).scalar()
    assert waiting == "10"


def test_your_normal_with_them_is_measured_inside_each_conversation(store):
    """Five times she asked and we answered the next day — and five days before each ask she sent a
    note on another thread that needed no answer. Merged, every answer looked six days late."""
    for i in range(5):
        process(store, ORG, event_id=f"evt_note{i}", sender=PRIYA, thread=f"t_note{i}",
                at=T0 + timedelta(days=10 * i + 5))
        process(store, ORG, event_id=f"evt_ask{i}", sender=PRIYA, thread=f"t_ask{i}",
                at=T0 + timedelta(days=10 * i + 10))
        process(store, ORG, event_id=f"evt_ans{i}", sender=FOUNDER, recipients=(PRIYA,),
                thread=f"t_ask{i}", at=T0 + timedelta(days=10 * i + 11))
    compute_waiting(store, ORG, now=NOW)
    with store.engine.connect() as c:
        days = c.execute(text(
            "select f.value #>> '{}' from graph_facts f join graph_nodes p on p.org_id = f.org_id "
            "   and p.node_id = f.subject_node_id and p.valid_to is null "
            " where f.org_id = :o and p.canonical_key = :k and f.field = 'party.our_reply_days' "
            "   and f.valid_to is null"), {"o": ORG, "k": PRIYA}).scalar()
    assert days == "1.0"
