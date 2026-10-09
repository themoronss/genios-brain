"""STEP-11 · the founder adds, or accepts, an in-motion line with its kind of work and counterparty.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… pytest tests/api/test_the_brief_route_takes_a_kind.py -q

`api/company_brief_routes.py` (tree `yc2_w27_s11 · M30.C4.L-interface.V2.U07`, `06` D31). The store keeps
an in-motion line's kind (`platform/company_brief_store`), but the confirm screen's routes took none: a
founder could not add a line saying what kind of work it is, nor accept the drafter's kind, correct it or
clear it. Now `POST /v1/company-brief/lines` takes `kind`, and accepting a proposal takes `kind`,
`address` and `domain` — a value sets or corrects it, `null` clears it, a field left out keeps the
proposal's. `GET /v1/company-brief` shows each line's kind and each proposal's; the brief's text, which
the models read, never does. A kind that cannot be is refused (422); adding a line the brief holds with
another kind is a conflict (409), never a silent success.
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

ORG = "org_s11_brief_kind_route"
AT = datetime(2026, 10, 9, 9, 0, tzinfo=timezone.utc)
OWNER = AuthCtx(org_id=ORG, actor_id="seat_owner", role="owner", source="jwt")
FUND = "Banyan Seed — first call held, data room asked"


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
                       "(:o, 'Arjun Rao', 'Nimbus Labs', 'arjun@s11-route.test')"), {"o": ORG})
    yield eng
    with eng.begin() as c:
        c.execute(text("delete from orgs where id = :o"), {"o": ORG})


@pytest.fixture
def api(monkeypatch, engine) -> TestClient:
    monkeypatch.setattr(routes, "_graph", _Graph(engine))
    monkeypatch.setattr(auth, "check_org_kill", lambda org_id: None)
    app = FastAPI()
    app.include_router(routes.router)
    app.dependency_overrides[get_auth_ctx] = lambda: OWNER
    return TestClient(app)


def _proposal(engine, words, **kw):
    with engine.begin() as c:
        return store.propose(c, org_id=ORG, section="in_motion", words=words, proposed_by="drafter",
                             at=AT, **kw)


def _decide(api, line_id, **body):
    return api.post(f"/v1/company-brief/proposals/{line_id}/decide",
                    json={"decision": "accept", **body})


def _lines(api) -> dict:
    return {ln["text"]: (ln["kind"], ln["address"], ln["domain"])
            for ln in api.get("/v1/company-brief").json()["lines"]}


def test_the_founder_adds_an_in_motion_line_with_its_kind_and_counterparty(api):
    added = api.post("/v1/company-brief/lines",
                     json={"section": "in_motion", "text": FUND, "kind": "investor",
                           "domain": "banyanseed.test"})
    assert added.status_code == 201 and added.json()["status"] == "accepted"
    body = api.get("/v1/company-brief").json()
    assert _lines(api) == {FUND: ("investor", None, "banyanseed.test")}
    assert FUND in body["text"] and "investor" not in body["text"], "a model was shown the kind"


def test_accepting_sets_corrects_or_clears_the_kind_and_a_field_left_out_keeps_the_proposals(
        api, engine):
    kept = _proposal(engine, FUND, kind="investor", domain="banyanseed.test")
    unnamed = _proposal(engine, "Lakshya — the accelerator application")
    wrong = _proposal(engine, "Northfield — a distribution partnership", kind="investor")
    cleared = _proposal(engine, "DigiVault — documents for the application", kind="compliance")
    moved = _proposal(engine, "Tusker Capital — pitch on Friday", kind="investor",
                      domain="tusker.test")
    for line_id, body in ((kept, {}), (unnamed, {"kind": "program"}), (wrong, {"kind": "partner"}),
                          (cleared, {"kind": None}), (moved, {"domain": "tuskercapital.vc"})):
        answer = _decide(api, line_id, **body)
        assert answer.status_code == 200 and answer.json()["status"] == "accepted", answer.json()
    assert _lines(api) == {
        FUND: ("investor", None, "banyanseed.test"),
        "Lakshya — the accelerator application": ("program", None, None),
        "Northfield — a distribution partnership": ("partner", None, None),
        "DigiVault — documents for the application": (None, None, None),
        "Tusker Capital — pitch on Friday": ("investor", None, "tuskercapital.vc")}


def test_accepting_names_the_counterparty_by_address(api, engine):
    line = _proposal(engine, "Kiran — partner call booked", kind="investor")
    assert _decide(api, line, address="Kiran@BanyanSeed.test").status_code == 200
    assert _lines(api) == {"Kiran — partner call booked": ("investor", "kiran@banyanseed.test",
                                                            None)}


def test_the_proposals_say_the_kind_they_propose(api, engine):
    named = _proposal(engine, FUND, kind="investor", domain="banyanseed.test")
    plain = _proposal(engine, "Hiring a founding AI engineer")
    proposals = {p["line_id"]: p["kind"] for p in api.get("/v1/company-brief").json()["proposals"]}
    assert proposals == {named: "investor", plain: None}


@pytest.mark.parametrize("line", [
    {"section": "goals", "text": "Raise the seed round", "kind": "investor"},
    {"section": "in_motion", "text": FUND, "kind": "fundraising"},
    {"section": "in_motion", "text": FUND, "kind": "investor", "domain": "gmail.com"},
])
def test_a_line_that_cannot_name_that_kind_or_counterparty_is_refused(api, line):
    refused = api.post("/v1/company-brief/lines", json=line)
    assert refused.status_code == 422 and refused.json()["detail"]["error"] == "invalid_line"
    assert api.get("/v1/company-brief").json()["lines"] == []


def test_an_acceptance_that_cannot_be_is_refused_and_the_proposal_waits(api, engine):
    with engine.begin() as c:
        goal = store.propose(c, org_id=ORG, section="goals", words="Raise the seed round",
                             proposed_by="drafter", at=AT)
    line = _proposal(engine, FUND, kind="investor", domain="banyanseed.test")
    for line_id, body in ((goal, {"kind": "investor"}), (line, {"kind": "fundraising"}),
                          (line, {"domain": "gmail.com"})):
        refused = _decide(api, line_id, **body)
        assert refused.status_code == 422 and refused.json()["detail"]["error"] == "invalid_line"
    assert {p["line_id"] for p in api.get("/v1/company-brief").json()["proposals"]} == {goal, line}


def test_adding_what_the_brief_holds_with_another_kind_is_a_conflict(api):
    first = api.post("/v1/company-brief/lines", json={"section": "in_motion", "text": FUND})
    again = api.post("/v1/company-brief/lines",
                     json={"section": "in_motion", "text": FUND, "kind": "investor"})
    assert first.status_code == 201
    assert again.status_code == 409 and again.json()["detail"]["error"] == "kind_differs"
    assert first.json()["line_id"] in again.json()["detail"]["message"]
    assert _lines(api) == {FUND: (None, None, None)}
