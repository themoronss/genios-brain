"""STEP-15 · GET /v1/executive/morning — your brief for today, served; composed on read once the hour has passed.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… .venv/bin/python -m pytest -q tests/executive/test_the_morning_route.py

`api/executive_routes.morning_brief` / `morning_brief_of` (tree `yc2_w27_s15` M44.C4.L-interface.V2.U04; `06` D9: the engine
serves the route, the Today view is `genios-dashboard`'s). Before 08:00 in the org's timezone: the last brief, and when
today's arrives. After it with none kept: composed on read — once, the row's key makes it so. A day's kept brief by its
date, 404 when none was kept. Whose brief: the signed-in seat's; an owner-level key's is the account owner's.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import text

from genios_engine.api import executive_routes as R
from genios_engine.platform import auth
from genios_engine.platform.auth import AuthCtx, get_auth_ctx

pytestmark = pytest.mark.pg

ORG, BARE = "org_s15_route", "org_s15_route_noseat"
OWNER = AuthCtx(org_id=ORG, seat_id="seat_owner", role="owner", source="jwt")
KEY = AuthCtx(org_id=ORG, source="api_key")
EARLY = datetime(2026, 10, 6, 2, 0, tzinfo=timezone.utc)        # 07:30 in Kolkata
LATE = datetime(2026, 10, 6, 3, 0, tzinfo=timezone.utc)         # 08:30
NEXT_EARLY = datetime(2026, 10, 7, 2, 0, tzinfo=timezone.utc)


class _Graph:
    def __init__(self, engine) -> None:
        self.engine = engine


@pytest.fixture
def engine():
    if not os.environ.get("GENIOS_TEST_DATABASE_URL"):
        pytest.skip("GENIOS_TEST_DATABASE_URL not set — the brief is served from Postgres")
    from genios_engine.platform.db import get_engine
    from genios_engine.platform.seats import ensure_owner_seat
    eng = get_engine(os.environ["GENIOS_TEST_DATABASE_URL"])
    with eng.begin() as c:
        for org in (ORG, BARE):
            c.execute(text("delete from orgs where id = :o"), {"o": org})
            c.execute(text("insert into orgs (id, name, email, timezone) values (:o, 'Arjun Rao', :e, 'Asia/Kolkata')"),
                      {"o": org, "e": f"{org}@example.test"})
        ensure_owner_seat(c, ORG)
        c.execute(text("insert into org_seats (org_id, seat_id, email, role, active) values "
                       "(:o, 'seat_member', 'member@example.test', 'member', true)"), {"o": ORG})
    yield eng
    with eng.begin() as c:
        for org in (ORG, BARE):
            c.execute(text("delete from orgs where id = :o"), {"o": org})


def _client(monkeypatch, engine, ctx, now):
    monkeypatch.setattr(R, "_graph", _Graph(engine))
    monkeypatch.setattr(R, "_now", lambda: now)
    monkeypatch.setattr(auth, "check_org_kill", lambda org_id: None)
    app = FastAPI()
    app.include_router(R.router)
    app.dependency_overrides[get_auth_ctx] = lambda: ctx
    return TestClient(app)


def _kept(engine, org=ORG):
    with engine.connect() as c:
        return c.execute(text("select seat_id, local_date::text from morning_briefs where org_id = :o "
                              "order by local_date, seat_id"), {"o": org}).all()


def test_before_the_hour_it_says_when_todays_brief_arrives(monkeypatch, engine):
    got = _client(monkeypatch, engine, OWNER, EARLY).get("/v1/executive/morning").json()
    assert got == {"state": "before_the_hour", "arrives_at": "2026-10-06T08:00:00+05:30",
                   "timezone": "Asia/Kolkata", "last": None}
    assert _kept(engine) == []                                     # nothing is composed before the hour


def test_after_the_hour_it_is_composed_on_read_once_and_served(monkeypatch, engine):
    client = _client(monkeypatch, engine, OWNER, LATE)
    first = client.get("/v1/executive/morning").json()
    assert first["state"] == "today" and first["one_line"] == "Nothing needs you today."
    assert (first["local_date"], first["timezone"], first["written_by"], first["sections"]) == \
        ("2026-10-06", "Asia/Kolkata", "template", [])
    assert client.get("/v1/executive/morning").json() == first
    assert _kept(engine) == [("seat_owner", "2026-10-06")]
    early = _client(monkeypatch, engine, OWNER, NEXT_EARLY).get("/v1/executive/morning").json()
    assert early["state"] == "before_the_hour" and early["last"]["local_date"] == "2026-10-06"
    assert early["arrives_at"] == "2026-10-07T08:00:00+05:30"
    by_day = _client(monkeypatch, engine, OWNER, NEXT_EARLY).get("/v1/executive/morning/2026-10-06")
    assert by_day.status_code == 200 and by_day.json()["state"] == "kept"
    assert by_day.json()["one_line"] == first["one_line"]
    missing = _client(monkeypatch, engine, OWNER, NEXT_EARLY).get("/v1/executive/morning/2026-10-05")
    assert missing.status_code == 404


def test_a_kept_brief_is_served_with_its_sections_lines_and_marks(monkeypatch, engine):
    from datetime import date
    from genios_engine.contracts import morning_brief as B
    from genios_engine.executive import morning_store
    item = B.Item(item_id=B.item_id_for(B.WATCHED, "node_f"), kind=B.WATCHED, about="node_f", subject="Fjord",
                  material=B.Material(words=(("name", "Fjord"), ("headline", "Wait for the milestone"))),
                  sources=(B.Source(B.SOURCE_REVIEW, "node_f@fp"),), quiet_days=25.0)
    line = B.Line(line_id=B.line_id_for(ORG, "seat_owner", date(2026, 10, 6), B.WATCHING, item.item_id),
                  item_id=item.item_id, section=B.WATCHING, words="Fjord: Wait for the milestone.", kind=item.kind,
                  subject="Fjord", sources=item.sources)
    brief = B.Brief(org_id=ORG, seat_id="seat_owner", local_date=date(2026, 10, 6), timezone="Asia/Kolkata",
                    as_of=LATE, one_line="Nothing urgent today; 1 thing to know.", lines=(line,), items=(item,),
                    written_by=B.TEMPLATE_BRIEF, why="the template", model=None, tier=None, cost_micro_usd=0,
                    cut=((B.WATCHING, 1),), material_digest=B.digest_of((item,)))
    with engine.begin() as c:
        morning_store.keep(c, brief)
        morning_store.mark_line(c, org_id=ORG, line_id=line.line_id, marked_by="seat_owner",
                                mark=morning_store.NOT_USEFUL, words="I know", at=LATE)
    got = _client(monkeypatch, engine, OWNER, LATE).get("/v1/executive/morning").json()
    (section,) = got["sections"]
    assert (section["section"], section["title"]) == (B.WATCHING, "Watching")
    (served,) = section["lines"]
    assert served["words"] == "Fjord: Wait for the milestone." and served["sources"] == [
        {"kind": "review", "ref": "node_f@fp"}]
    assert served["marks"] == [{"by": "seat_owner", "mark": "not_useful", "words": "I know", "at": LATE.isoformat()}]
    assert got["cut"] == [{"section": "watching", "n": 1}] and got["words"] == brief.words
    early = _client(monkeypatch, engine, OWNER, EARLY).get("/v1/executive/morning").json()
    assert early["state"] == "today" and early["one_line"] == brief.one_line      # kept today: served, whatever the hour


def test_whose_brief_a_seat_an_owner_key_and_a_workspace_with_no_owner(monkeypatch, engine):
    member = AuthCtx(org_id=ORG, seat_id="seat_member", role="member", source="jwt")
    assert _client(monkeypatch, engine, member, LATE).get("/v1/executive/morning").status_code == 200
    assert _client(monkeypatch, engine, KEY, LATE).get("/v1/executive/morning").status_code == 200
    assert _kept(engine) == [("seat_member", "2026-10-06"), ("seat_owner", "2026-10-06")]
    bare = AuthCtx(org_id=BARE, source="api_key")
    assert _client(monkeypatch, engine, bare, LATE).get("/v1/executive/morning").status_code == 404
    scoped = AuthCtx(org_id=ORG, source="api_key", scopes=["cards:read"])
    assert _client(monkeypatch, engine, scoped, LATE).get("/v1/executive/morning").status_code == 403
