"""STEP-09 · a connector's nudge about a person it introduced joins that person's file; its own ask
stays its own.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… pytest tests/context/test_a_nudge_joins_the_introduced_persons_file.py -q

`context/pipeline.process_event` (tree `yc2_w27_s09 · M27.C1.L-logic.V1.U04`, minted building C1 from
the golden F03 and F09). After an introduction the connector writes to the founder alone — "Did you see
my intro to Rahul?", "Rahul is still waiting" — in a thread of its own. Addressed to nobody else, that
mail anchored on the connector and filed every nudge about every person under one connector file,
where a card could tell the founder to reply to the connector (F03 forbids it). Now a connector's mail
that introduces nobody joins the file of the one person it names among those IT introduced — by the
names the introduction used or the person's own; names none, and it is the connector's own ask, its
own file (F09); names two of them, and it joins both files — it is evidence about each, and it is
recorded on each so a rebuild files it the same way.
"""
from __future__ import annotations

import pytest

from .workstream_world import (CONNECTOR, FOUNDER, UNSUBSCRIBE, anchors, brief, later, mention,
                               process, reset, tenant)

pytestmark = pytest.mark.pg

ORG = "org_s09_nudges"
RAHUL, FARAH = "rahul@kestrelcap.test", "farah@kitepath.test"
OTHER = "team@matchmaker.test"


@pytest.fixture
def store(pg_store):
    tenant(pg_store, ORG)
    b = brief(ORG, connectors=(CONNECTOR, OTHER))
    for event_id, contact, names in (
            ("evt_intro_rahul", RAHUL, (mention("Rahul Menon"),
                                        mention("Kestrel Capital", "organization"))),
            ("evt_intro_farah", FARAH, (mention("Farah Qureshi"),
                                        mention("Kitepath", "organization")))):
        process(pg_store, ORG, event_id=event_id, sender=CONNECTOR, sender_name="Introly",
                recipients=(FOUNDER, contact), thread=f"t_{event_id}", headers=UNSUBSCRIBE,
                mentions=names, company_brief=b)
    yield pg_store, b
    reset(pg_store, ORG)


def _nudge(store, b, event_id, mentions, sender=CONNECTOR, thread="t_nudges"):
    process(store, ORG, event_id=event_id, sender=sender, sender_name="Introly",
            thread=thread, headers=UNSUBSCRIBE, mentions=mentions, company_brief=b,
            at=later(2))
    return anchors(store, ORG, event_id)


def test_a_nudge_naming_the_person_joins_their_file(store):
    store, b = store
    assert _nudge(store, b, "evt_nudge", (mention("Rahul"),)) == {"kestrelcap.test"}


def test_a_nudge_naming_their_company_joins_their_file(store):
    store, b = store
    assert _nudge(store, b, "evt_nudge", (mention("Kestrel Capital", "organization"),
                                          mention("Introly", "organization"))) == {
        "kestrelcap.test"}


def test_the_next_nudge_in_that_thread_follows_it(store):
    store, b = store
    _nudge(store, b, "evt_nudge1", (mention("Rahul"),))
    assert _nudge(store, b, "evt_nudge2", ()) == {"kestrelcap.test"}


def test_a_mail_naming_no_one_it_introduced_is_the_connectors_own_ask(store):
    store, b = store
    assert _nudge(store, b, "evt_ask", (mention("Introly", "organization"),),
                  thread="t_ask") == {"introly.test"}


def test_a_nudge_naming_two_people_joins_both_files(store):
    store, b = store
    assert _nudge(store, b, "evt_both", (mention("Rahul"), mention("Farah"))) == {
        "kestrelcap.test", "kitepath.test"}


def test_a_name_another_connector_introduced_is_not_this_ones(store):
    """Rahul was introduced by Introly; Matchmaker naming him is not a nudge about its own intro."""
    store, b = store
    assert _nudge(store, b, "evt_mm", (mention("Rahul"),), sender=OTHER,
                  thread="t_mm") == {"matchmaker.test"}
