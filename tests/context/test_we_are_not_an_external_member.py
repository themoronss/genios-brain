"""STEP-04 · we are not an external member of our own situations.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… pytest tests/context/test_we_are_not_an_external_member.py -q

`context/situation_bso.gather_members` (tree `yc2_w27_s04/M22.C2.L-logic.V2.U14`) names the
DISTINCT real counterparties correlated onto a situation, from the actor of each correlated event —
and it had no self test at all. The mail connector types every actor `external_contact`, the
founder's own outbound included, so the founder was a counterparty of his own situations, his
`gmail.com` and the company's `thegenios.com` were counted as external domains, and enough of us on
one thread tipped `split_required` (more than two external domains: "not one relationship").

Who is us is asked of `platform/self_identity`: an address of ours, or at a domain we declared, is
not a member. A customer writing from Gmail still is, and `gmail.com` is still their domain.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine, text

from genios_engine.context.situation_bso import (
    _distinct_external_domains,
    build_business_situation,
    gather_members,
)
from genios_engine.platform.self_identity import identity_for

pytestmark = pytest.mark.pg

ORG = "external_member_org"
CORR = "corr_external_members"
NOW = datetime(2026, 9, 25, 12, 0, tzinfo=timezone.utc)
#: `orgs.email` is UNIQUE, so this file's founder has an address no other test file inserts.
FOUNDER = "founder.members@gmail.com"
SECOND = "ceo@thegenios.com"                 # declared address
COLLEAGUE = "harsh@thegenios.com"            # at the declared domain
OUTSIDE = ("siddhant@neon.fund", "priya@another.vc", "asha.customer@gmail.com")


@pytest.fixture
def engine():
    url = os.environ.get("GENIOS_TEST_DATABASE_URL")
    if not url:
        # conftest's own words: tests/contracts/test_h0_gate.py reads any other
        # skip in tests/context as a placeholder that names no gate.
        pytest.skip("GENIOS_TEST_DATABASE_URL not set — real-Postgres L2 tests skipped")
    eng = create_engine(url)
    with eng.begin() as c:
        c.execute(text("delete from orgs where id = :o"), {"o": ORG})
        c.execute(text("insert into orgs (id, name, email) values (:o, :o, 'Founder.Members@gmail.com')"),
                  {"o": ORG})
        c.execute(text("insert into org_self_identities (org_id, kind, value, declared_by) values "
                       "(:o, 'address', :a, 'test'), (:o, 'domain', 'thegenios.com', 'test')"),
                  {"o": ORG, "a": SECOND})
        # One correlated situation, one event per actor — every actor typed `external_contact`,
        # exactly as the mail connector writes them.
        for n, actor in enumerate((FOUNDER, SECOND, COLLEAGUE, *OUTSIDE)):
            event = f"ev_members_{n}"
            c.execute(text(
                "insert into source_events (event_id, org_id, connection_id, source, object_type, "
                "  source_object_id, dedup_key, actor, occurred_at) "
                "values (:e, :o, 'conn_members', 'gmail', 'message', :e, :e, "
                "  cast(:actor as jsonb), :at)"),
                {"e": event, "o": ORG, "at": NOW - timedelta(days=n + 1),
                 "actor": json.dumps({"email": actor, "type": "external_contact"})})
            c.execute(text("insert into context_correlation_members (org_id, correlation_id, "
                           "  event_id) values (:o, :c, :e)"), {"o": ORG, "c": CORR, "e": event})
    yield eng
    with eng.begin() as c:
        c.execute(text("delete from orgs where id = :o"), {"o": ORG})       # cascades
    eng.dispose()


def _ids(members) -> set[str]:
    return {str(m["id"]) for m in members}


def test_the_founder_is_not_an_external_member(engine):
    with engine.connect() as c:
        members = gather_members(c, ORG, CORR)
    assert FOUNDER not in _ids(members), "the founder was a counterparty of his own situation"
    assert set(OUTSIDE) <= _ids(members), "a real counterparty stopped being a member"


def test_our_addresses_and_our_domain_are_not_external(engine):
    with engine.connect() as c:
        members = gather_members(c, ORG, CORR)
    assert not {SECOND, COLLEAGUE} & _ids(members), "an address of ours was an external member"
    domains = _distinct_external_domains(members)
    assert "thegenios.com" not in domains, "our declared domain was counted as an external domain"
    # A customer writing from Gmail is still external, and gmail.com is still THEIR domain.
    assert domains == {"neon.fund", "another.vc", "gmail.com"}


def test_a_thread_with_three_of_us_is_not_split_for_us(engine):
    """Two outside parties and three of us is one relationship. Counted with us it was four
    distinct 'external' domains (gmail.com, thegenios.com, neon.fund, another.vc) — over the
    threshold of two, so 'not one relationship'."""
    with engine.begin() as c:
        c.execute(text("delete from context_correlation_members where org_id = :o "
                       "and event_id in ('ev_members_5')"), {"o": ORG})   # the Gmail customer
    with engine.connect() as c:
        members = gather_members(c, ORG, CORR)
    situation = {"situation_id": "sit_members", "situation_type": "relationship",
                 "anchor_node_id": "n_anchor", "status": "active", "confidence_overall": 50,
                 "coverage": 100}
    bso = build_business_situation(org_id=ORG, situation=situation, signal_ids=["s1"],
                                   evidence=[{"event_id": "s1", "reconstructed": True}],
                                   trace_id="t1", members=members)
    assert bso.metadata["split_required"] is False, _distinct_external_domains(members)
    assert bso.metadata["distinct_counterparty_count"] == 2


def test_a_sweep_that_already_knows_who_we_are_hands_it_in(engine, monkeypatch):
    """The same answer when the caller passes the identity it read once for the sweep — and then
    the members are one statement, with no second read of who we are."""
    with engine.connect() as c:
        read_here = gather_members(c, ORG, CORR)
        assert FOUNDER not in _ids(read_here), "the founder was a counterparty of his own situation"
        us = identity_for(c, ORG)
        calls = []
        original = c.execute

        def counting(*a, **kw):
            calls.append(a[0])
            return original(*a, **kw)

        monkeypatch.setattr(c, "execute", counting)
        handed_in = gather_members(c, ORG, CORR, us=us)
    assert handed_in == read_here
    assert len(calls) == 1, "the members cost one statement when the sweep hands in who we are"
