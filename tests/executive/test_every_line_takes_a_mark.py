"""STEP-15 · POST /v1/executive/morning/lines/{line_id}/mark — useful, or not useful with your words.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… .venv/bin/python -m pytest -q tests/executive/test_every_line_takes_a_mark.py

`api/executive_routes.mark_morning_line` (tree `yc2_w27_s15` M45.C3.L-interface.V0.U02), over
`executive/morning_store.mark_line` (M44.C4.L-data.V0.U01). A later mark of yours replaces an earlier one; a mark
on a line no kept brief holds is a 404; a malformed mark (not one of `useful`/`not_useful`, or `not_useful` with
no words, or `useful` with words) is a 422. Recorded only — STEP-16 turns marks into proposals you accept, never
this step.
"""
from __future__ import annotations

import os
from datetime import date, datetime, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import text

from genios_engine.api import executive_routes as R
from genios_engine.contracts import morning_brief as B
from genios_engine.executive import morning_store
from genios_engine.platform import auth
from genios_engine.platform.auth import AuthCtx, get_auth_ctx

pytestmark = pytest.mark.pg

ORG = "org_s15_mark"
OWNER = AuthCtx(org_id=ORG, seat_id="seat_owner", role="owner", source="jwt")
MEMBER = AuthCtx(org_id=ORG, seat_id="seat_member", role="member", source="jwt")
NOW = datetime(2026, 10, 6, 3, 0, tzinfo=timezone.utc)
LOCAL = date(2026, 10, 6)


class _Graph:
    def __init__(self, engine) -> None:
        self.engine = engine


@pytest.fixture
def engine():
    if not os.environ.get("GENIOS_TEST_DATABASE_URL"):
        pytest.skip("GENIOS_TEST_DATABASE_URL not set — a mark is kept in Postgres")
    from genios_engine.platform.db import get_engine
    from genios_engine.platform.seats import ensure_owner_seat
    eng = get_engine(os.environ["GENIOS_TEST_DATABASE_URL"])
    with eng.begin() as c:
        c.execute(text("delete from orgs where id = :o"), {"o": ORG})
        c.execute(text("insert into orgs (id, name, email, timezone) values (:o, 'Arjun Rao', :e, "
                       "'Asia/Kolkata')"), {"o": ORG, "e": f"{ORG}@example.test"})
        ensure_owner_seat(c, ORG)
        c.execute(text("insert into org_seats (org_id, seat_id, email, role, active) values "
                       "(:o, 'seat_member', 'member@example.test', 'member', true)"), {"o": ORG})
    yield eng
    with eng.begin() as c:
        c.execute(text("delete from orgs where id = :o"), {"o": ORG})


def _client(monkeypatch, engine, ctx):
    monkeypatch.setattr(R, "_graph", _Graph(engine))
    monkeypatch.setattr(R, "_now", lambda: NOW)
    monkeypatch.setattr(auth, "check_org_kill", lambda org_id: None)
    app = FastAPI()
    app.include_router(R.router)
    app.dependency_overrides[get_auth_ctx] = lambda: ctx
    return TestClient(app)


@pytest.fixture
def line(engine):
    item = B.Item(item_id=B.item_id_for(B.WATCHED, "node_f"), kind=B.WATCHED, about="node_f", subject="Fjord",
                 material=B.Material(words=(("name", "Fjord"), ("headline", "Wait for the milestone"))),
                 sources=(B.Source(B.SOURCE_REVIEW, "node_f@fp"),), quiet_days=25.0)
    built = B.Line(line_id=B.line_id_for(ORG, "seat_owner", LOCAL, B.WATCHING, item.item_id), item_id=item.item_id,
                   section=B.WATCHING, words="Fjord: Wait for the milestone.", kind=item.kind, subject="Fjord",
                   sources=item.sources)
    brief = B.Brief(org_id=ORG, seat_id="seat_owner", local_date=LOCAL, timezone="Asia/Kolkata", as_of=NOW,
                    one_line="1 thing to know.", lines=(built,), items=(item,), written_by=B.TEMPLATE_BRIEF,
                    why="the template", model=None, tier=None, cost_micro_usd=0, cut=(),
                    material_digest=B.digest_of((item,)))
    with engine.begin() as c:
        morning_store.keep(c, brief)
    return built.line_id


def _marks(engine, line_id):
    with engine.connect() as c:
        return morning_store.marks_for(c, ORG, "seat_owner", LOCAL).get(line_id, ())


def test_a_useful_mark_is_kept(monkeypatch, engine, line):
    resp = _client(monkeypatch, engine, OWNER).post(f"/v1/executive/morning/lines/{line}/mark",
                                                     json={"mark": "useful"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["mark"] == "useful" and body["words"] is None and body["marked_by"] == "seat_owner"
    (kept,) = _marks(engine, line)
    assert kept.mark == "useful" and kept.words is None


def test_a_not_useful_mark_needs_words(monkeypatch, engine, line):
    bare = _client(monkeypatch, engine, OWNER).post(f"/v1/executive/morning/lines/{line}/mark",
                                                     json={"mark": "not_useful"})
    assert bare.status_code == 422
    said = _client(monkeypatch, engine, OWNER).post(f"/v1/executive/morning/lines/{line}/mark",
                                                     json={"mark": "not_useful", "words": "I already knew"})
    assert said.status_code == 200
    assert said.json()["words"] == "I already knew"


def test_a_useful_mark_with_words_is_refused(monkeypatch, engine, line):
    resp = _client(monkeypatch, engine, OWNER).post(f"/v1/executive/morning/lines/{line}/mark",
                                                     json={"mark": "useful", "words": "great"})
    assert resp.status_code == 422


def test_an_unknown_mark_value_is_refused(monkeypatch, engine, line):
    resp = _client(monkeypatch, engine, OWNER).post(f"/v1/executive/morning/lines/{line}/mark",
                                                     json={"mark": "love_it"})
    assert resp.status_code == 422


def test_a_later_mark_of_yours_replaces_the_earlier_one(monkeypatch, engine, line):
    client = _client(monkeypatch, engine, OWNER)
    client.post(f"/v1/executive/morning/lines/{line}/mark", json={"mark": "useful"})
    client.post(f"/v1/executive/morning/lines/{line}/mark", json={"mark": "not_useful", "words": "changed my mind"})
    (kept,) = _marks(engine, line)
    assert kept.mark == "not_useful" and kept.words == "changed my mind"


def test_two_seats_each_keep_their_own_mark(monkeypatch, engine, line):
    _client(monkeypatch, engine, OWNER).post(f"/v1/executive/morning/lines/{line}/mark", json={"mark": "useful"})
    _client(monkeypatch, engine, MEMBER).post(f"/v1/executive/morning/lines/{line}/mark",
                                              json={"mark": "not_useful", "words": "not for me"})
    marks = {m.marked_by: m.mark for m in _marks(engine, line)}
    assert marks == {"seat_owner": "useful", "seat_member": "not_useful"}


def test_a_line_no_kept_brief_holds_is_a_404(monkeypatch, engine, line):
    resp = _client(monkeypatch, engine, OWNER).post("/v1/executive/morning/lines/bl_no_such_line/mark",
                                                     json={"mark": "useful"})
    assert resp.status_code == 404
