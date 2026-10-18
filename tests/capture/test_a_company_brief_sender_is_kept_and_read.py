"""STEP-07 · a sender the company brief names reaches a reader, on every capture door.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… pytest tests/capture/test_a_company_brief_sender_is_kept_and_read.py -q

Tree `yc2_w27_s07 · M25.C4.L-integration.V3.U02`. The resolver (`api/routes._sender_resolver_for`, U03)
knows the brief's senders and says why; this unit carries that reason to the gate on the sync door and
the push door (`capture/pipeline.named_in_brief`), so the portal's Promotions mail and the intro agent's
unsubscribe-headed mail land EMITTED with W-07 — and, because the sender is known, the relevance page's
bulk rule no longer refuses it before extraction. A stranger's Promotions mail is archived as before.
"""
from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from sqlalchemy import text

from genios_engine.capture import pipeline as P
from genios_engine.capture.acquire import sync_runner as S
from genios_engine.capture.connectors import push_ingest as PI
from genios_engine.capture.connectors.base import RawObject, SourceBatch
from genios_engine.capture.esqe.relevance import refused_without_extraction
from genios_engine.capture.gate.relevance import RelevanceVerdict
from genios_engine.capture.landing.repository import InMemorySourceEventRepository
from genios_engine.platform import company_brief as cb
from genios_engine.platform import company_brief_store as store

pytestmark = pytest.mark.pg

ORG = "org_s07_kept_and_read"
T = datetime(2026, 9, 24, 5, 20, tzinfo=timezone.utc)
UNSUB = {"List-Unsubscribe": "<mailto:unsubscribe@introly.test>"}


def _objects():
    return [
        RawObject("gmail", "email_message", "m_portal", T, actor_email="updates@startupsetu.gov.test",
                  raw={"subject": "Application SSR-2026-48213: status updated",
                       "snippet": "Your application has moved to the stage: Under Examination.",
                       "labelIds": ["INBOX", "CATEGORY_PROMOTIONS"]}),
        RawObject("gmail", "email_message", "m_intro", T, actor_email="hello@introly.test",
                  raw={"subject": "Intro: meet Kestrel Capital", "snippet": "Happy to connect you.",
                       "headers": UNSUB}),
        RawObject("gmail", "email_message", "m_shop", T, actor_email="deals@shop.test",
                  raw={"subject": "50% off", "snippet": "This week only.",
                       "labelIds": ["INBOX", "CATEGORY_PROMOTIONS"]}),
    ]


class _Inbox:
    source = "gmail"

    def incremental_changes(self, cursor=None, limit=100, since=None):
        return SourceBatch(objects=_objects(), next_cursor=None)

    def initial_snapshot(self, cursor=None, limit=100):
        return SourceBatch(objects=_objects(), next_cursor=None)


class _Junk:
    """The AI filter at its worst: everything is automated junk. W-07 must never ask it."""

    def __init__(self):
        self.asked: list[str] = []

    def classify(self, ctx, prepared):
        self.asked.append(ctx.event.actor.email)
        return RelevanceVerdict(False, 0.05, disposition="drop", reason="automated")


@pytest.fixture
def resolver(live_db_url, monkeypatch):
    if not live_db_url:
        pytest.skip("GENIOS_TEST_DATABASE_URL not set — needs real Postgres")
    from genios_engine.api import routes
    from genios_engine.platform.db import get_engine
    eng = get_engine(live_db_url)
    at = datetime(2026, 10, 7, tzinfo=timezone.utc)
    with eng.begin() as c:
        c.execute(text("delete from orgs where id = :o"), {"o": ORG})
        c.execute(text("insert into orgs (id, name, company) values (:o, 'Arjun Rao', 'Nimbus Labs')"),
                  {"o": ORG})
        store.add(c, org_id=ORG, section="watchlist", words="StartupSetu — the recognition portal",
                  domain="startupsetu.gov.test", decided_by="founder", at=at)
        store.add(c, org_id=ORG, section="connectors", words="Introly — introduces people",
                  address="hello@introly.test", decided_by="founder", at=at)
    monkeypatch.setattr(routes, "_graph", SimpleNamespace(engine=eng))
    routes._SENDER_CACHE.pop(ORG, None)
    cb.invalidate(ORG)
    yield routes._sender_resolver_for(ORG)
    with eng.begin() as c:
        c.execute(text("delete from orgs where id = :o"), {"o": ORG})
    routes._SENDER_CACHE.pop(ORG, None)
    cb.invalidate(ORG)


def _by_object(results):
    out = {}
    for r in results:
        s1 = next((rec for rec in r.trace.records if rec.stage == "S1"), None)
        out[r.event.source_object_id] = (r.outcome, s1.detail.get("whitelist") if s1 else None,
                                         s1.reason_code if s1 else None)
    return out


def test_the_sync_door_keeps_and_reads_what_the_brief_names(resolver):
    junk = _Junk()
    summary = S.run_sync(_Inbox(), org_id=ORG, connection_id="c", repo=InMemorySourceEventRepository(),
                         relevance=junk, sender_resolver=resolver)
    got = _by_object(summary.results)
    assert got["m_portal"] == ("emitted", "W-07", None)
    assert got["m_intro"] == ("emitted", "W-07", None)
    assert got["m_shop"][0] == "archived" and got["m_shop"][2] == "N-06"
    assert junk.asked == [], "neither the brief's senders nor the rule-archived mail met the filter"


def test_the_push_door_does_the_same(resolver):
    wiring = PI.PushIngestWiring(repo=InMemorySourceEventRepository(), relevance=_Junk(),
                                 sender_resolver=resolver)
    outcome = PI.ingest_pushed_objects(tuple(_objects()), org_id=ORG, connection_id="c",
                                       wiring=wiring)
    got = _by_object(outcome.results)
    assert got["m_portal"][:2] == ("emitted", "W-07") and got["m_intro"][:2] == ("emitted", "W-07")


def test_the_bulk_rule_no_longer_refuses_the_named_connector_before_extraction(resolver):
    intro = _objects()[1]
    known = P.page_relevance_candidate(intro, sender_known=bool(resolver(intro)))
    stranger = P.page_relevance_candidate(intro, sender_known=False)
    assert refused_without_extraction(known) is None
    assert refused_without_extraction(stranger) is not None, "the control: unknown, it is refused"


def test_a_resolver_that_names_nobody_changes_nothing():
    plain = lambda raw: False                                   # noqa: E731 — no `.named`
    summary = S.run_sync(_Inbox(), org_id=ORG, connection_id="c",
                         repo=InMemorySourceEventRepository(), relevance=_Junk(),
                         sender_resolver=plain)
    got = _by_object(summary.results)
    assert got["m_portal"][0] == "archived" and got["m_intro"][0] == "archived"
