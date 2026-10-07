"""STEP-09 · who a connector introduced, whose is each name, and who is a connector — by names and
addresses, never by a model.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… pytest tests/context/test_introductions.py -q

`context/introductions` (tree `yc2_w27_s09 · M27.C1.L-data.V0.U01`, minted building C1). The
bookkeeping `context/pipeline` files a connector's mail by, and that a rebuild reads too
(`context/backfill`): an introduction's names are given to the people it introduced from the mail's
own words and addresses; a later mail names someone it introduced or nobody; the nodes the founder's
company brief names as connectors are introducers wherever they appear.
"""
from __future__ import annotations

import pytest
from sqlalchemy import text

from genios_engine.context.introductions import (Introduction, assign_names, connector_roles,
                                                 introductions_by, named_in, org_fits,
                                                 person_fits)
from genios_engine.contracts.company_brief import CompanyBrief

from .workstream_world import (CONNECTOR, FOUNDER, UNSUBSCRIBE, brief, mention, node, process,
                               reset, tenant)

ORG = "org_s09_introductions"
RAHUL, FARAH = "rahul@kestrelcap.test", "farah@kitepath.test"


# =================================================================================================
# names against addresses — pure
# =================================================================================================
@pytest.mark.unit
@pytest.mark.parametrize("name, address, fits", [
    ("Rahul Menon", "rahul@kestrelcap.test", True),       # the first local token is a name word
    ("Rahul Menon", "rahul.menon@kestrelcap.test", True),
    ("Rahul Menon", "rahulmenon@kestrelcap.test", True),  # the whole local part spells the name
    ("Rahul Menon", "rmenon@kestrelcap.test", False),     # an initial is not a name
    ("Farah Qureshi", "rahul@kestrelcap.test", False),
    ("Rahul", "r@kestrelcap.test", False),                # one letter matches too much
    ("R. Menon", "r@kestrelcap.test", False),             # …even when the name has an initial
    ("", "rahul@kestrelcap.test", False),
])
def test_a_persons_name_goes_with_their_address(name, address, fits):
    assert person_fits(name, address) is fits


@pytest.mark.unit
@pytest.mark.parametrize("name, address, fits", [
    ("Kestrel Capital", "rahul@kestrelcap.test", True),   # one spelling starts with the other
    ("Kestrel", "rahul@kestrelcap.test", True),           # …whichever is the longer
    ("Acme", "info@mail.acme.test", True),                # a generic label is never the stem
    ("Kitepath", "farah@kitepath.test", True),
    ("StartupSetu", "no-reply@notify.startupsetu.gov.test", True),   # generic labels are skipped
    ("Kestrel Capital", "farah@kitepath.test", False),
    ("Kit", "farah@kitepath.test", False),                # shorter than four letters
    ("Gmail", "someone@gmail.com", False),                # a personal mailbox names no one
])
def test_an_organisation_goes_with_its_domain(name, address, fits):
    assert org_fits(name, address) is fits


# =================================================================================================
# whose is each name an introduction used — pure
# =================================================================================================
@pytest.mark.unit
def test_each_name_goes_to_the_contact_it_fits():
    names = assign_names([mention("Rahul Menon"), mention("Farah Qureshi"),
                          mention("Kestrel Capital", "organization"),
                          mention("Kitepath", "organization")], [RAHUL, FARAH])
    assert names[RAHUL].person == "Rahul Menon" and names[RAHUL].organisation == "Kestrel Capital"
    assert names[FARAH].person == "Farah Qureshi" and names[FARAH].organisation == "Kitepath"


@pytest.mark.unit
def test_with_one_contact_the_one_name_left_is_theirs():
    """"Arjun, meet Vikram" sent to v.k@… — the address spells nothing, and the one person named
    who is not the founder or the connector is the one introduced."""
    names = assign_names([mention("Arjun Rao"), mention("Vikram Kale"),
                          mention("Introly", "organization")],
                         ["v.k@meridianfund.test"], not_theirs=[FOUNDER, CONNECTOR])
    assert names["v.k@meridianfund.test"].person == "Vikram Kale"
    assert names["v.k@meridianfund.test"].organisation is None, "Introly is the connector's own"


@pytest.mark.unit
def test_with_one_contact_two_leftover_names_are_nobodys():
    names = assign_names([mention("Vikram Kale"), mention("Meera Iyer"),
                          mention("Northfield", "organization"), mention("Lumen", "organization")],
                         ["v.k@meridianfund.test"])
    assert names["v.k@meridianfund.test"].person is None
    assert names["v.k@meridianfund.test"].organisation is None


@pytest.mark.unit
def test_with_two_contacts_a_leftover_name_is_nobodys():
    names = assign_names([mention("Vikram Kale")], ["v.k@meridianfund.test", FARAH])
    assert names["v.k@meridianfund.test"].person is None and names[FARAH].person is None


@pytest.mark.unit
def test_a_name_that_fits_two_contacts_is_nobodys():
    names = assign_names([mention("Rahul")], ["rahul@kestrelcap.test", "rahul@kitepath.test"])
    assert all(a.person is None and a.names == () for a in names.values())


@pytest.mark.unit
def test_our_names_and_the_connectors_are_never_a_contacts():
    names = assign_names([mention("Arjun Rao"), mention("Introly", "organization")],
                         [RAHUL], not_theirs=[FOUNDER, CONNECTOR])
    assert names[RAHUL].person is None and names[RAHUL].organisation is None


@pytest.mark.unit
def test_a_mention_with_no_name_or_a_type_it_cannot_place_is_ignored():
    names = assign_names([{"type": "person", "name": ""}, {"type": "product", "name": "Rahul"}],
                         [RAHUL])
    assert names[RAHUL].names == ()


# =================================================================================================
# which of the people it introduced a later mail names — pure
# =================================================================================================
INTROS = [Introduction(contact="n_rahul", address=RAHUL, company="n_kestrel",
                       names=("Rahul Menon", "Kestrel Capital")),
          Introduction(contact="n_farah", address=FARAH, company=None, names=("Farah Qureshi",)),
          Introduction(contact="n_vikram", address="v.k@meridianfund.test", company=None,
                       names=("Vikram Kale",))]


@pytest.mark.unit
@pytest.mark.parametrize("mentions, contacts", [
    ([mention("Rahul")], ["n_rahul"]),                                   # by their first name
    ([mention("Kestrel Capital", "organization")], ["n_rahul"]),         # by their organisation
    ([mention("Kestrelcap", "organization")], ["n_rahul"]),              # by their domain
    ([mention("Farah Qureshi"), mention("Rahul Menon")], ["n_rahul", "n_farah"]),
    ([mention("Vikram")], ["n_vikram"]),                                 # by the name it was given
    ([mention("Rahul"), mention("Kestrel Capital", "organization")], ["n_rahul"]),   # once
    ([mention("Introly", "organization")], []),                          # its own ask
    ([mention("Priya")], []),
    ([], []),
])
def test_a_later_mail_names_the_people_it_introduced(mentions, contacts):
    assert [i.contact for i in named_in(mentions, INTROS)] == contacts


# =================================================================================================
# the graph's answers — Postgres
# =================================================================================================
@pytest.fixture
def store(pg_store):
    tenant(pg_store, ORG)
    yield pg_store
    reset(pg_store, ORG)


@pytest.mark.pg
def test_who_a_connector_introduced_is_read_with_their_company_and_names(store):
    b = brief(ORG)
    process(store, ORG, event_id="evt_intro", sender=CONNECTOR, sender_name="Introly",
            recipients=(FOUNDER, RAHUL), thread="t_intro", headers=UNSUBSCRIBE,
            mentions=(mention("Rahul Menon"), mention("Kestrel Capital", "organization")),
            company_brief=b)
    with store.engine.connect() as c:
        [intro] = introductions_by(c, org_id=ORG, connector_node=node(store, ORG, CONNECTOR).node_id)
    assert intro.address == RAHUL and intro.contact == node(store, ORG, RAHUL).node_id
    assert intro.company == node(store, ORG, "kestrelcap.test").node_id
    assert intro.names == ("Rahul Menon", "Kestrel Capital")


@pytest.mark.pg
def test_a_contact_known_only_by_address_has_no_names(store):
    """A node's display name is its address until something names it — that is not a name."""
    process(store, ORG, event_id="evt_intro", sender=CONNECTOR, sender_name="Introly",
            recipients=(FOUNDER, RAHUL), thread="t_intro", headers=UNSUBSCRIBE,
            company_brief=brief(ORG))
    with store.engine.connect() as c:
        [intro] = introductions_by(c, org_id=ORG, connector_node=node(store, ORG, CONNECTOR).node_id)
    assert intro.names == ()


@pytest.mark.pg
def test_a_connector_that_introduced_nobody_has_no_introductions(store):
    process(store, ORG, event_id="evt_ask", sender=CONNECTOR, thread="t_ask",
            headers=UNSUBSCRIBE, company_brief=brief(ORG))
    with store.engine.connect() as c:
        assert introductions_by(c, org_id=ORG,
                                connector_node=node(store, ORG, CONNECTOR).node_id) == []


@pytest.mark.pg
def test_every_node_the_brief_names_a_connector_is_an_introducer(store):
    process(store, ORG, event_id="evt_ask", sender=CONNECTOR, thread="t_ask",
            headers=UNSUBSCRIBE, company_brief=brief(ORG))
    with store.engine.connect() as c:
        roles = connector_roles(c, org_id=ORG, company_brief=brief(ORG))
    assert roles == {node(store, ORG, CONNECTOR).node_id: "introducer"}


@pytest.mark.pg
def test_without_a_connector_line_nothing_is_read(store):
    class _NoQueries:
        def execute(self, *_a, **_k):
            raise AssertionError("a brief with no connector read the graph")
    assert connector_roles(_NoQueries(), org_id=ORG, company_brief=CompanyBrief(org_id=ORG)) == {}
    assert connector_roles(_NoQueries(), org_id=ORG,
                           company_brief=brief(ORG, connectors=())) == {}
    assert connector_roles(_NoQueries(), org_id=ORG, company_brief=None) == {}


@pytest.mark.pg
def test_a_person_the_brief_names_is_not_a_connector(store):
    from genios_engine.contracts.company_brief import CompanyBriefLine, compose
    process(store, ORG, event_id="evt_vc", sender=RAHUL, thread="t_vc", company_brief=None)
    people = compose(org_id=ORG, company="Nimbus Labs", founder="Arjun Rao",
                     lines=[CompanyBriefLine(line_id="cbl_p", section="people", address=RAHUL,
                                             text="Rahul — an investor")])
    assert people.named_sender(RAHUL) == f"person:{RAHUL}"
    with store.engine.connect() as c:
        assert connector_roles(c, org_id=ORG, company_brief=people) == {}


@pytest.mark.pg
def test_a_merged_away_connector_node_is_not_read(store):
    process(store, ORG, event_id="evt_ask", sender=CONNECTOR, thread="t_ask",
            headers=UNSUBSCRIBE, company_brief=brief(ORG))
    with store.engine.begin() as c:
        c.execute(text("update graph_nodes set valid_to = now() where org_id = :o "
                       "   and canonical_key = :k"), {"o": ORG, "k": CONNECTOR})
        assert connector_roles(c, org_id=ORG, company_brief=brief(ORG)) == {}


@pytest.mark.pg
def test_a_connector_the_graph_has_not_met_is_no_node(store):
    with store.engine.connect() as c:
        assert connector_roles(c, org_id=ORG, company_brief=brief(ORG)) == {}
        assert c.execute(text("select count(*) from graph_nodes where org_id = :o"),
                         {"o": ORG}).scalar() == 0
