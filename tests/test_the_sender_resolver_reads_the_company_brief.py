"""STEP-07 · the brief's senders are known senders — to every stage that asks.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… pytest tests/test_the_sender_resolver_reads_the_company_brief.py -q

Tree `yc2_w27_s07 · M25.C4.L-integration.V2.U03`. Four stages stop the portal's and the intro agent's
mail on "unknown sender" — the noise rules, the AI filter, the relevance page's service-account and bulk
rungs, the bulk check before extraction (`speedrun008/YC-II W27/` STEP-07 §8.1). They all ask one
resolver, `api/routes._sender_resolver_for`, so the brief is read there: a connector's or a key
person's address, or any address at a watchlist domain, is known — and `.named` says why.
A tenant with no brief is answered exactly as before.
"""
from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from sqlalchemy import text

from genios_engine.platform import company_brief as cb
from genios_engine.platform import company_brief_store as store

pytestmark = pytest.mark.pg

ORG = "org_s07_resolver"
AT = datetime(2026, 10, 7, 9, 0, tzinfo=timezone.utc)


def _raw(email):
    return SimpleNamespace(actor_email=email)


@pytest.fixture
def resolver(live_db_url, monkeypatch):
    if not live_db_url:
        pytest.skip("GENIOS_TEST_DATABASE_URL not set — needs real Postgres")
    from genios_engine.api import routes
    from genios_engine.platform.db import get_engine
    eng = get_engine(live_db_url)
    with eng.begin() as c:
        c.execute(text("delete from orgs where id = :o"), {"o": ORG})
        c.execute(text("insert into orgs (id, name, company) values (:o, 'Arjun Rao', 'Nimbus Labs')"),
                  {"o": ORG})
    monkeypatch.setattr(routes, "_graph", SimpleNamespace(engine=eng))
    routes._SENDER_CACHE.pop(ORG, None)
    cb.invalidate(ORG)
    yield eng, routes._sender_resolver_for(ORG)
    with eng.begin() as c:
        c.execute(text("delete from orgs where id = :o"), {"o": ORG})
    routes._SENDER_CACHE.pop(ORG, None)
    cb.invalidate(ORG)


def test_with_no_brief_nobody_new_is_known(resolver):
    _eng, known = resolver
    assert known(_raw("hello@introly.test")) is False
    assert known.named(_raw("hello@introly.test")) is None


def test_the_brief_names_a_connector_a_person_and_a_watchlist_domain(resolver):
    eng, known = resolver
    with eng.begin() as c:
        store.add(c, org_id=ORG, section="connectors", words="Introly — introduces people",
                  address="hello@introly.test", decided_by="founder", at=AT)
        store.add(c, org_id=ORG, section="people", words="Kiran — partner at Banyan Seed",
                  address="kiran@banyanseed.test", decided_by="founder", at=AT)
        store.add(c, org_id=ORG, section="watchlist", words="StartupSetu — the recognition portal",
                  domain="startupsetu.gov.test", decided_by="founder", at=AT)
    assert known(_raw("Hello@Introly.test")) is True
    assert known.named(_raw("hello@introly.test")) == "connector:hello@introly.test"
    assert known.named(_raw("kiran@banyanseed.test")) == "person:kiran@banyanseed.test"
    assert known(_raw("no-reply@portal.startupsetu.gov.test")) is True
    assert known.named(_raw("updates@startupsetu.gov.test")) == "watchlist:startupsetu.gov.test"
    assert known(_raw("stranger@elsewhere.test")) is False
    assert known(_raw(None)) is False and known.named(_raw("")) is None


def test_a_line_the_founder_accepts_is_read_on_the_next_mail(resolver):
    eng, known = resolver
    assert known(_raw("updates@startupsetu.gov.test")) is False          # caches the empty brief
    with eng.begin() as c:
        store.add(c, org_id=ORG, section="watchlist", words="StartupSetu",
                  domain="startupsetu.gov.test", decided_by="founder", at=AT)
    assert known(_raw("updates@startupsetu.gov.test")) is True           # the write dropped it


def test_a_removed_line_stops_naming_its_sender(resolver):
    eng, known = resolver
    with eng.begin() as c:
        line = store.add(c, org_id=ORG, section="connectors", words="Introly",
                         address="hello@introly.test", decided_by="founder", at=AT)
    assert known(_raw("hello@introly.test")) is True
    with eng.begin() as c:
        store.remove(c, org_id=ORG, line_id=line, decided_by="founder", at=AT)
    assert known(_raw("hello@introly.test")) is False
