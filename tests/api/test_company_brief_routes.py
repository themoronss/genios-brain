"""STEP-07 · the founder confirms the company brief — and only the founder.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… pytest tests/api/test_company_brief_routes.py -q

Tree `yc2_w27_s07 · M25.C2.L-interface.V2.U01`. The dashboard's confirm screen calls these routes: read
the brief and what waits, add a line, accept (or edit) or reject a proposal, remove a line. Every
change is the account owner's (`06` D27) — an admin seat may read, never decide. Accepting a sender the
brief now names promotes what the gate archived from it, so it is read on the next pass.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import text

from genios_engine.api import company_brief_routes as routes
from genios_engine.platform import auth
from genios_engine.platform import company_brief_store as store
from genios_engine.platform.auth import AuthCtx, get_auth_ctx

pytestmark = pytest.mark.pg

ORG = "org_s07_brief_routes"
AT = datetime(2026, 10, 7, 9, 0, tzinfo=timezone.utc)
OWNER = AuthCtx(org_id=ORG, actor_id="seat_owner", role="owner", source="jwt")
ADMIN = AuthCtx(org_id=ORG, actor_id="seat_admin", role="admin", source="jwt")


class _Graph:
    def __init__(self, engine) -> None:
        self.engine = engine


@pytest.fixture
def engine(live_db_url):
    if not live_db_url:
        pytest.skip("GENIOS_TEST_DATABASE_URL not set — needs real Postgres")
    from genios_engine.platform.db import get_engine
    eng = get_engine(live_db_url)
    with eng.begin() as c:
        c.execute(text("delete from orgs where id = :o"), {"o": ORG})
        c.execute(text("insert into orgs (id, name, company, email) values "
                       "(:o, 'Arjun Rao', 'Nimbus Labs', 'arjun@nimbuslabs.test')"), {"o": ORG})
    yield eng
    with eng.begin() as c:
        c.execute(text("delete from raw_payloads where org_id = :o"), {"o": ORG})
        c.execute(text("delete from source_events where org_id = :o"), {"o": ORG})
        c.execute(text("delete from orgs where id = :o"), {"o": ORG})


def _client(monkeypatch, engine, ctx: AuthCtx) -> TestClient:
    monkeypatch.setattr(routes, "_graph", _Graph(engine))
    monkeypatch.setattr(auth, "check_org_kill", lambda org_id: None)
    app = FastAPI()
    app.include_router(routes.router)
    app.dependency_overrides[get_auth_ctx] = lambda: ctx
    return TestClient(app)


def _proposal(engine, **kw):
    with engine.begin() as c:
        return store.propose(c, org_id=ORG, proposed_by="drafter", at=AT, **kw)


def test_the_brief_and_its_proposals_are_read(monkeypatch, engine):
    pending = _proposal(engine, section="goals", words="raise the pre-seed round",
                        evidence=[{"pattern": "wave:2026-08-11"}])
    body = _client(monkeypatch, engine, ADMIN).get("/v1/company-brief").json()
    assert body["version"] is None and body["text"] == "" and body["lines"] == []
    assert [p["line_id"] for p in body["proposals"]] == [pending]
    assert body["last_review"] is None                     # the weekly review has never run


def test_the_owner_accepts_and_the_brief_exists(monkeypatch, engine):
    pending = _proposal(engine, section="goals", words="raise the pre-seed round")
    api = _client(monkeypatch, engine, OWNER)
    answer = api.post(f"/v1/company-brief/proposals/{pending}/decide", json={"decision": "accept"})
    assert answer.status_code == 200 and answer.json()["status"] == "accepted"
    body = api.get("/v1/company-brief").json()
    assert body["version"].startswith("cb-") and "raise the pre-seed round" in body["text"]
    assert [ln["line_id"] for ln in body["lines"]] == [pending] and body["proposals"] == []


def test_an_admin_may_read_but_not_decide(monkeypatch, engine):
    pending = _proposal(engine, section="goals", words="raise the pre-seed round")
    api = _client(monkeypatch, engine, ADMIN)
    assert api.post(f"/v1/company-brief/proposals/{pending}/decide",
                    json={"decision": "accept"}).status_code == 403
    assert api.post("/v1/company-brief/lines",
                    json={"section": "goals", "text": "anything"}).status_code == 403
    assert api.delete(f"/v1/company-brief/lines/{pending}").status_code == 403


def test_accept_in_the_founders_words_and_reject(monkeypatch, engine):
    edited = _proposal(engine, section="goals", words="raise a seed round")
    refused = _proposal(engine, section="goals", words="hire a sales lead")
    api = _client(monkeypatch, engine, OWNER)
    api.post(f"/v1/company-brief/proposals/{edited}/decide",
             json={"decision": "accept", "text": "raise the pre-seed round by December"})
    api.post(f"/v1/company-brief/proposals/{refused}/decide", json={"decision": "reject"})
    body = api.get("/v1/company-brief").json()
    assert [ln["text"] for ln in body["lines"]] == ["raise the pre-seed round by December"]
    assert body["lines"][0]["proposed_text"] == "raise a seed round"
    again = api.post(f"/v1/company-brief/proposals/{refused}/decide", json={"decision": "accept"})
    assert again.status_code == 409 and again.json()["detail"]["error"] == "not_pending"


def test_a_bad_line_or_decision_is_refused(monkeypatch, engine):
    api = _client(monkeypatch, engine, OWNER)
    assert api.post("/v1/company-brief/lines",
                    json={"section": "watchlist", "text": "a portal"}).status_code == 422
    assert api.post("/v1/company-brief/lines",
                    json={"section": "us", "text": "we are"}).status_code == 422
    assert api.post("/v1/company-brief/proposals/cbl_nope/decide",
                    json={"decision": "accept"}).status_code == 404
    pending = _proposal(engine, section="goals", words="raise the pre-seed round")
    assert api.post(f"/v1/company-brief/proposals/{pending}/decide",
                    json={"decision": "maybe"}).status_code == 422


def test_the_founders_line_and_its_removal(monkeypatch, engine):
    api = _client(monkeypatch, engine, OWNER)
    added = api.post("/v1/company-brief/lines",
                     json={"section": "preferences", "text": "never on a Sunday"})
    assert added.status_code == 201
    line_id = added.json()["line_id"]
    assert api.delete(f"/v1/company-brief/lines/{line_id}").json()["status"] == "removed"
    assert api.get("/v1/company-brief").json()["lines"] == []
    assert api.delete(f"/v1/company-brief/lines/{line_id}").status_code == 409


def _archived(engine, event_id: str, sender: str, rule: str = "N-02"):
    with engine.begin() as c:
        c.execute(text(
            "insert into source_events (event_id, org_id, connection_id, source, object_type, "
            " source_object_id, dedup_key, actor, occurred_at, outcome, attention, attention_reason) "
            "values (:e, :o, 'con_1', 'gmail', 'email_message', :e, :e, "
            " cast(:actor as jsonb), :at, 'archived', 'archive', :rule)"),
            {"e": event_id, "o": ORG, "actor": f'{{"email": "{sender}"}}', "at": AT, "rule": rule})
        c.execute(text(
            "insert into raw_payloads (id, org_id, event_id, enc_content, expires_at) values "
            "(:i, :o, :e, :b, :exp)"),
            {"i": f"rp_{event_id}", "o": ORG, "e": event_id, "b": b"x",
             "exp": datetime(2027, 1, 1, tzinfo=timezone.utc)})


def test_accepting_a_connector_promotes_what_the_gate_archived_from_it(monkeypatch, engine):
    _archived(engine, "evt_intro_1", "hello@introly.test")
    _archived(engine, "evt_intro_2", "hello@introly.test")
    _archived(engine, "evt_news_1", "news@letters.test")
    pending = _proposal(engine, section="connectors", words="Introly — introduces people",
                        address="hello@introly.test")
    api = _client(monkeypatch, engine, OWNER)
    answer = api.post(f"/v1/company-brief/proposals/{pending}/decide", json={"decision": "accept"})
    assert answer.json()["promoted"] == 2
    with engine.connect() as c:
        outcomes = dict(c.execute(text("select event_id, outcome from source_events "
                                       "where org_id = :o"), {"o": ORG}).fetchall())
    assert outcomes == {"evt_intro_1": "emitted", "evt_intro_2": "emitted",
                        "evt_news_1": "archived"}


def test_a_key_person_at_a_public_mail_host_promotes_nothing(monkeypatch, engine):
    _archived(engine, "evt_gmail_1", "someone@gmail.com")
    api = _client(monkeypatch, engine, OWNER)
    added = api.post("/v1/company-brief/lines",
                     json={"section": "people", "text": "Kavita Rao — an angel",
                           "address": "kavita.rao.vc@gmail.com"})
    assert added.json()["promoted"] == 0
