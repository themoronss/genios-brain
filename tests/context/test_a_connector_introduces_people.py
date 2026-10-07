"""STEP-09 · a connector's introduction creates the people it introduces — even under its unsubscribe
header — and names them.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… pytest tests/context/test_a_connector_introduces_people.py -q

`context/pipeline.process_event` (tree `yc2_w27_s09 · M27.C1.L-logic.V0.U02`, `06` D30). An intro
network's mail carries `List-Unsubscribe`, so `addressed_to_a_list` dropped EVERY To/Cc recipient and
the person introduced never entered memory unless they replied: on the golden set Rahul (F03), Simon
and Omar (F08) were not in the graph at all (`03` F91). Now the recipients of a mail from a connector
the founder's brief names are people — ours excepted — each typed `introduced` (a `party.role` fact and
an `introduced` edge from the connector, carrying the thread and the names the introduction used), and
named from the introduction when it names exactly them. A real mailing list from anyone else still
establishes nobody.
"""
from __future__ import annotations

import pytest

from .workstream_world import (CONNECTOR, FOUNDER, UNSUBSCRIBE, brief, edges, facts, mention, node,
                               process, reset, tenant)

pytestmark = pytest.mark.pg

ORG = "org_s09_connector_people"
RAHUL, FARAH = "rahul@kestrelcap.test", "farah@kitepath.test"


@pytest.fixture
def store(pg_store):
    tenant(pg_store, ORG)
    yield pg_store
    reset(pg_store, ORG)


def _intro(store, event_id, recipients, mentions=(), **kw):
    return process(store, ORG, event_id=event_id, sender=CONNECTOR, sender_name="Introly",
                   recipients=recipients, thread=f"t_{event_id}", headers=UNSUBSCRIBE,
                   mentions=mentions, company_brief=brief(ORG), **kw)


def test_the_person_introduced_enters_memory_under_the_unsubscribe_header(store):
    _intro(store, "evt_intro", (FOUNDER, RAHUL))
    assert node(store, ORG, RAHUL) is not None, "the contact is not in the graph"
    [(role, evidence)] = facts(store, ORG, RAHUL, "party.role")
    assert role == "introduced" and evidence.get("by") == CONNECTOR
    assert (CONNECTOR, RAHUL) in edges(store, ORG, "introduced")


def test_one_of_us_on_the_line_is_never_introduced(store):
    _intro(store, "evt_intro", (FOUNDER, RAHUL))
    assert facts(store, ORG, FOUNDER, "party.role") == []
    assert {b for _, b in edges(store, ORG, "introduced")} == {RAHUL}


def test_the_introduction_names_the_person_and_the_company(store):
    """One person introduced: the person and the organisation the introduction names are theirs."""
    _intro(store, "evt_intro", (FOUNDER, RAHUL),
           mentions=(mention("Rahul Menon"), mention("Kestrel Capital", "organization"),
                     mention("Introly", "organization"), mention("Arjun Rao")))
    assert node(store, ORG, RAHUL).display_name == "Rahul Menon"
    assert node(store, ORG, "kestrelcap.test").display_name == "Kestrel Capital"
    [(_, evidence)] = facts(store, ORG, RAHUL, "party.role")
    assert set(evidence.get("names") or ()) == {"Rahul Menon", "Kestrel Capital"}


def test_the_one_name_left_is_the_person_introduced(store):
    """An address that spells nothing: the one person named who is not ours and not the connector's
    is the introduced person — and the organisations named here are ours and the connector's, so
    none is theirs: their company keeps its domain rather than taking the connector's name."""
    _intro(store, "evt_vk", (FOUNDER, "v.k@meridianfund.test"),
           mentions=(mention("Arjun Rao"), mention("Vikram Kale"),
                     mention("Introly", "organization"), mention("Nimbus Labs", "organization")))
    assert node(store, ORG, "v.k@meridianfund.test").display_name == "Vikram Kale"
    assert node(store, ORG, "meridianfund.test").display_name == "meridianfund.test"


def test_two_people_introduced_each_get_only_their_own_names(store):
    _intro(store, "evt_two", (FOUNDER, RAHUL, FARAH),
           mentions=(mention("Rahul Menon"), mention("Kestrel Capital", "organization"),
                     mention("Farah Qureshi"), mention("Kitepath", "organization")))
    assert node(store, ORG, RAHUL).display_name == "Rahul Menon"
    assert node(store, ORG, FARAH).display_name == "Farah Qureshi"
    assert node(store, ORG, "kitepath.test").display_name == "Kitepath"
    [(_, rahul)] = facts(store, ORG, RAHUL, "party.role")
    assert set(rahul["names"]) == {"Rahul Menon", "Kestrel Capital"}


def test_a_name_that_fits_nobody_names_nobody(store):
    """Two people introduced and a name neither address carries: it is attached to no one."""
    _intro(store, "evt_two", (FOUNDER, RAHUL, FARAH), mentions=(mention("Meera Iyer"),))
    assert node(store, ORG, RAHUL).display_name == RAHUL
    assert node(store, ORG, FARAH).display_name == FARAH


def test_a_mailing_list_from_anyone_else_still_establishes_nobody(store):
    process(store, ORG, event_id="evt_list", sender="news@letters.test",
            recipients=(FOUNDER, RAHUL), thread="t_list", headers=UNSUBSCRIBE,
            company_brief=brief(ORG))
    assert node(store, ORG, RAHUL) is None


def test_without_a_brief_the_connectors_recipients_are_skipped_as_before(store):
    process(store, ORG, event_id="evt_intro", sender=CONNECTOR, recipients=(FOUNDER, RAHUL),
            thread="t_intro", headers=UNSUBSCRIBE, company_brief=None)
    assert node(store, ORG, RAHUL) is None
    assert edges(store, ORG, "introduced") == set()
