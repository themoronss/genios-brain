"""STEP-09 · an introduction puts the founder's turn with the person introduced, never with the connector.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… pytest tests/context/test_the_connector_is_never_owed_a_reply.py -q

`context/pipeline.process_event` (tree `yc2_w27_s09 · M27.C3.L-logic.V0.U01`, redrawn building C1).
Every inbound mail writes whose turn it is — `thread.last_inbound` and `thread.ball_in_court = us` — on
the person who spoke, and the legacy `unanswered_email` rule reads exactly those two facts. So an intro
network's introduction put the founder's turn with the NETWORK: on six golden cases the rule raised
Introly as a person owed a reply, and the decider deferred it every sweep (`03` F81). Now an
introduction writes that state on each person it introduces — the reply it calls for is owed to them —
and a nudge about them changes nobody's turn (they did not write; the introduction already put it with
us). The connector's own ask is owed a reply as any mail is: its state stays on the connector (F09).
"""
from __future__ import annotations

import pytest

from .workstream_world import (CONNECTOR, FOUNDER, T0, UNSUBSCRIBE, brief, facts, later, mention,
                               node, process, reset, tenant)

pytestmark = pytest.mark.pg

ORG = "org_s09_whose_turn"
RAHUL = "rahul@kestrelcap.test"


@pytest.fixture
def store(pg_store):
    tenant(pg_store, ORG)
    yield pg_store
    reset(pg_store, ORG)


def _turn(store, key) -> tuple:
    ball = [v for v, _ in facts(store, ORG, key, "thread.ball_in_court")]
    last = [v for v, _ in facts(store, ORG, key, "thread.last_inbound")]
    return (ball[0] if ball else None, last[0] if last else None)


def _intro(store, **kw):
    process(store, ORG, event_id="evt_intro", sender=CONNECTOR, sender_name="Introly",
            recipients=(FOUNDER, RAHUL), thread="t_intro", headers=UNSUBSCRIBE,
            mentions=(mention("Rahul Menon"),), **kw)


def test_the_introduction_puts_our_turn_with_the_person_introduced(store):
    _intro(store, company_brief=brief(ORG))
    assert _turn(store, RAHUL) == ("us", T0.isoformat())
    assert _turn(store, CONNECTOR) == (None, None), "the connector was made a person owed a reply"


def test_a_nudge_changes_nobodys_turn(store):
    _intro(store, company_brief=brief(ORG))
    process(store, ORG, event_id="evt_nudge", sender=CONNECTOR, sender_name="Introly",
            thread="t_nudges", headers=UNSUBSCRIBE, mentions=(mention("Rahul"),),
            company_brief=brief(ORG), at=later(2))
    assert _turn(store, RAHUL) == ("us", T0.isoformat()), "the nudge re-dated Rahul's wait"
    assert _turn(store, CONNECTOR) == (None, None)


def test_a_later_nudge_in_the_nudge_thread_is_still_a_nudge(store):
    _intro(store, company_brief=brief(ORG))
    for i, names in enumerate(((mention("Rahul"),), ())):
        process(store, ORG, event_id=f"evt_nudge{i}", sender=CONNECTOR, sender_name="Introly",
                thread="t_nudges", headers=UNSUBSCRIBE, mentions=names,
                company_brief=brief(ORG), at=later(2 + i))
    assert _turn(store, CONNECTOR) == (None, None)


def test_the_introductions_thread_is_with_the_person_introduced(store):
    """The thread carries the same turn, under a name: the conversation is with Rahul."""
    _intro(store, company_brief=brief(ORG))
    assert node(store, ORG, "thread:t_intro").display_name == f"Thread with {RAHUL}"
    assert _turn(store, "thread:t_intro") == ("us", T0.isoformat())


def test_an_introduction_of_two_names_no_one_for_its_thread(store):
    process(store, ORG, event_id="evt_two", sender=CONNECTOR, sender_name="Introly",
            recipients=(FOUNDER, RAHUL, "farah@kitepath.test"), thread="t_two",
            headers=UNSUBSCRIBE, company_brief=brief(ORG))
    assert node(store, ORG, "thread:t_two").display_name == "Thread t_two"


def test_a_nudge_writes_no_turn_on_its_thread(store):
    _intro(store, company_brief=brief(ORG))
    process(store, ORG, event_id="evt_nudge", sender=CONNECTOR, sender_name="Introly",
            thread="t_nudges", headers=UNSUBSCRIBE, mentions=(mention("Rahul"),),
            company_brief=brief(ORG), at=later(2))
    assert node(store, ORG, "thread:t_nudges") is None


def test_the_connectors_own_ask_is_owed_a_reply(store):
    process(store, ORG, event_id="evt_ask", sender=CONNECTOR, sender_name="Introly",
            thread="t_ask", headers=UNSUBSCRIBE, company_brief=brief(ORG), at=later(3))
    assert _turn(store, CONNECTOR) == ("us", later(3).isoformat())
    assert node(store, ORG, "thread:t_ask").display_name == f"Thread with {CONNECTOR}"


def test_the_persons_own_reply_moves_the_turn_as_ever(store):
    _intro(store, company_brief=brief(ORG))
    process(store, ORG, event_id="evt_reply", sender=RAHUL, sender_name="Rahul Menon",
            thread="t_intro", company_brief=brief(ORG), at=later(1))
    assert _turn(store, RAHUL) == ("us", later(1).isoformat())


def test_without_a_brief_the_turn_is_where_it_always_was(store):
    _intro(store, company_brief=None)
    assert _turn(store, CONNECTOR) == ("us", T0.isoformat())
