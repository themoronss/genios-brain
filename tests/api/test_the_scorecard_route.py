"""STEP-16 · `GET /v1/learning/scorecard?week=` — the owner's view of a week.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… .venv/bin/python -m pytest -q tests/api/test_the_scorecard_route.py

Tree `yc2_w27_s16` M47.C3.L-interface.V6.U02 (`api/learning_routes`; `feedback/scorecard`). An ISO week in UTC
(`YYYY-Www`), this week so far when none is named; a week that is no ISO week refused, saying so; owner-level — a
member seat or a scoped key is refused; read only, and only the asking tenant's week.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import text

from genios_engine.api import learning_routes as routes
from genios_engine.platform import auth
from genios_engine.platform.auth import MEMBER_SCOPES, AuthCtx, get_auth_ctx

pytestmark = pytest.mark.pg

ORG, OTHER = "org_s16_scorecard_route", "org_s16_scorecard_other"
MONDAY = datetime(2026, 10, 12, tzinfo=timezone.utc)
NOW = MONDAY + timedelta(days=3)
OWNER = AuthCtx(org_id=ORG, actor_id="seat_owner", role="owner", source="jwt")
ADMIN = AuthCtx(org_id=ORG, actor_id="seat_admin", role="admin", source="jwt")
MEMBER = AuthCtx(org_id=ORG, actor_id="seat_member", role="member", source="jwt", scopes=sorted(MEMBER_SCOPES))


class _Graph:
    def __init__(self, engine) -> None:
        self.engine = engine


@pytest.fixture
def engine(live_db_url):
    if not live_db_url:
        pytest.skip("GENIOS_TEST_DATABASE_URL not set — the week is read from Postgres")
    from genios_engine.platform.db import get_engine
    eng = get_engine(live_db_url)
    with eng.begin() as c:
        for org in (ORG, OTHER):
            c.execute(text("delete from orgs where id = :o"), {"o": org})
            c.execute(text("insert into orgs (id, name, email) values (:o, :o, :e)"), {"o": org, "e": f"{org}@s16.test"})
    yield eng
    with eng.begin() as c:
        for org in (ORG, OTHER):
            c.execute(text("delete from orgs where id = :o"), {"o": org})


def _client(monkeypatch, engine, ctx: AuthCtx) -> TestClient:
    monkeypatch.setattr(routes, "_graph", _Graph(engine))
    monkeypatch.setattr(routes, "_now", lambda: NOW)
    monkeypatch.setattr(auth, "check_org_kill", lambda org_id: None)
    app = FastAPI()
    app.include_router(routes.router)
    app.dependency_overrides[get_auth_ctx] = lambda: ctx
    return TestClient(app)


def _card(engine, org, card_id, *, at):
    with engine.begin() as c:
        c.execute(text("insert into cards (card_id, signal_id, org_id, level, urgency_band, headline, situation, "
                       "score, expires_at, state, file_id, output_lane, lane_reason, created_at) values (:c, :s, :o, "
                       "'prescriptive', 'standard', 'h', 's', 10, :exp, 'queued', :f, 'decision', 'a test lane', :at)"),
                  {"c": card_id, "s": f"sig_{card_id}", "o": org, "exp": at + timedelta(days=7), "f": f"node_{card_id}",
                   "at": at})


def test_the_owner_reads_a_named_week(monkeypatch, engine):
    _card(engine, ORG, "k_in", at=MONDAY + timedelta(days=1))
    _card(engine, ORG, "k_before", at=MONDAY - timedelta(days=2))
    _card(engine, OTHER, "k_theirs", at=MONDAY + timedelta(days=1))
    got = _client(monkeypatch, engine, OWNER).get("/v1/learning/scorecard", params={"week": "2026-W42"})
    assert got.status_code == 200, got.text
    body = got.json()
    assert (body["org_id"], body["week"], body["nothing"]) == (ORG, "2026-W42", False)
    assert body["usefulness"] == {"decision": {**{e: 0 for e in body["usefulness"]["decision"]}, "open": 1}}, \
        "this week's card, the tenant's own"
    assert body["since"] == MONDAY.isoformat() and body["until"] == (MONDAY + timedelta(days=7)).isoformat()


def test_no_week_named_is_this_week_so_far(monkeypatch, engine):
    _card(engine, ORG, "k_later", at=NOW + timedelta(hours=1))
    body = _client(monkeypatch, engine, ADMIN).get("/v1/learning/scorecard").json()
    assert body["week"] == "2026-W42" and body["nothing"] is True, "read so far: a card after now is not yet"
    assert body["says"].startswith("Nothing happened in 2026-W42")


@pytest.mark.parametrize("week", ["2026-42", "2026-W54", "last week"])
def test_a_week_that_is_no_iso_week_is_refused_saying_so(monkeypatch, engine, week):
    got = _client(monkeypatch, engine, OWNER).get("/v1/learning/scorecard", params={"week": week})
    assert got.status_code == 400 and got.json()["detail"]["error"] == "invalid_week"


def test_a_member_seat_is_refused(monkeypatch, engine):
    got = _client(monkeypatch, engine, MEMBER).get("/v1/learning/scorecard", params={"week": "2026-W42"})
    assert got.status_code == 403
