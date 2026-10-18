"""STEP-09 · an introduction is a file per person introduced, and each one's reply stays in their own.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… pytest tests/context/test_an_intro_is_a_file_per_contact.py -q

`context/correlation.correlate_event` (tree `yc2_w27_s09 · M27.C1.L-logic.V1.U03`). With the connector
an introducer and the people it introduces in memory (U01, U02), an introduction anchors on each of
them — one file each. A reply joins its conversation by thread, and correlation is thread-first; so in
a thread that holds SEVERAL people's files, a reply from one of them used to join all of them, and
Farah's answer landed in Rahul's file too. Now a reply in such a thread joins only the files of the
parties in it — all of them when it names them all, every one when it names none (a bare "thanks"
from us), so nothing is ever left out of its conversation.
"""
from __future__ import annotations

import pytest
from sqlalchemy import text

from genios_engine.context.correlation import correlate_event

from .workstream_world import (CONNECTOR, FOUNDER, UNSUBSCRIBE, anchors, brief, later, ledger, node,
                               process, reset, tenant)

pytestmark = pytest.mark.pg

ORG = "org_s09_file_per_contact"
RAHUL, FARAH = "rahul@kestrelcap.test", "farah@kitepath.test"


@pytest.fixture
def store(pg_store):
    tenant(pg_store, ORG)
    yield pg_store
    reset(pg_store, ORG)


def _intro(store, event_id, recipients, thread):
    process(store, ORG, event_id=event_id, sender=CONNECTOR, sender_name="Introly",
            recipients=recipients, thread=thread, headers=UNSUBSCRIBE, company_brief=brief(ORG))


def test_one_introduction_of_two_people_is_two_files(store):
    _intro(store, "evt_two", (FOUNDER, RAHUL, FARAH), "t_two")
    assert anchors(store, ORG, "evt_two") == {"kestrelcap.test", "kitepath.test"}


def test_a_reply_joins_only_the_file_of_the_person_who_wrote(store):
    _intro(store, "evt_two", (FOUNDER, RAHUL, FARAH), "t_two")
    process(store, ORG, event_id="evt_farah", sender=FARAH, sender_name="Farah Qureshi",
            recipients=(FOUNDER,), thread="t_two", at=later(1), company_brief=brief(ORG))
    assert anchors(store, ORG, "evt_farah") == {"kitepath.test"}


def test_our_answer_to_one_of_them_joins_only_theirs(store):
    _intro(store, "evt_two", (FOUNDER, RAHUL, FARAH), "t_two")
    process(store, ORG, event_id="evt_mine", sender=FOUNDER, recipients=(RAHUL,),
            thread="t_two", at=later(1), company_brief=brief(ORG))
    assert anchors(store, ORG, "evt_mine") == {"kestrelcap.test"}


def test_a_reply_to_everyone_joins_every_file(store):
    _intro(store, "evt_two", (FOUNDER, RAHUL, FARAH), "t_two")
    process(store, ORG, event_id="evt_all", sender=FOUNDER, recipients=(RAHUL, FARAH),
            thread="t_two", at=later(1), company_brief=brief(ORG))
    assert anchors(store, ORG, "evt_all") == {"kestrelcap.test", "kitepath.test"}


def test_a_party_handed_over_as_a_bare_person_still_finds_their_file(store):
    """The structured lanes hand correlation bare people (a calendar attendee has no employer edge);
    the thread's files are narrowed on the same lifted pool an anchor would be chosen from."""
    _intro(store, "evt_two", (FOUNDER, RAHUL, FARAH), "t_two")
    ledger(store, ORG, event_id="evt_cal", sender=FARAH, thread="t_two", at=later(1))
    with store.engine.begin() as c:
        correlate_event(c, org_id=ORG, event_id="evt_cal", occurred_at=later(1), thread_id="t_two",
                        node_types={node(store, ORG, FARAH).node_id: "person"}, domain_hints=None)
    assert anchors(store, ORG, "evt_cal") == {"kitepath.test"}


def test_a_reply_that_names_no_party_keeps_its_whole_conversation(store):
    """A bare note from us to the connector alone names neither file: it joins both, as before —
    under-correlating it into neither would drop it out of its own conversation."""
    _intro(store, "evt_two", (FOUNDER, RAHUL, FARAH), "t_two")
    process(store, ORG, event_id="evt_thanks", sender=FOUNDER, recipients=(CONNECTOR,),
            thread="t_two", at=later(1), company_brief=brief(ORG))
    assert anchors(store, ORG, "evt_thanks") == {"kestrelcap.test", "kitepath.test"}


def test_one_introduction_and_its_reply_are_one_file(store):
    _intro(store, "evt_intro", (FOUNDER, RAHUL), "t_one")
    process(store, ORG, event_id="evt_reply", sender=RAHUL, sender_name="Rahul Menon",
            recipients=(FOUNDER,), thread="t_one", at=later(1), company_brief=brief(ORG))
    with store.engine.connect() as c:
        files = c.execute(text(
            "select correlation_id, count(*) as n from context_correlation_members "
            " where org_id = :o group by 1"), {"o": ORG}).fetchall()
    assert [int(f.n) for f in files] == [2], files


def test_a_thread_with_one_file_is_untouched(store):
    """Thread-first, as ever, when the thread holds one file — whoever writes."""
    process(store, ORG, event_id="evt_a", sender="priya@northwind.test", recipients=(FOUNDER,),
            thread="t_plain", company_brief=brief(ORG))
    process(store, ORG, event_id="evt_b", sender="ops@southwind.test", recipients=(FOUNDER,),
            thread="t_plain", at=later(1), company_brief=brief(ORG))
    assert anchors(store, ORG, "evt_b") == {"northwind.test"}
