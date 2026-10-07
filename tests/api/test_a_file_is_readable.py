"""STEP-10 · one file, readable — what it is, its timeline and its numbers; the tenant's own; nothing written.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… pytest tests/api/test_a_file_is_readable.py -q

Tree `yc2_w27_s10 · M29.C2.L-interface.V3.U02`. `GET /v1/workstreams/{file_id}` serves the file as the list
gives it, its timeline (`context/workstream_timeline`) and its numbers (`context/workstream_numbers`) — each
person's reply time and yours with n and basis, the normals that hold, a bounce, the mailboxes and whether
"no reply" may be said. Another tenant's file and an unknown id are the same 404; a scoped key is refused;
reading writes nothing; and it is mounted on the application behind the tenant read.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import text

from genios_engine.api import workstream_routes as routes
from genios_engine.context.periodic import _ensure_tenant_node
from genios_engine.context.waiting import compute_waiting
from genios_engine.platform import auth
from genios_engine.platform.auth import AuthCtx, get_auth_ctx
from tests.context.workstream_world import FOUNDER, T0, node, process, reset, tenant

pytestmark = pytest.mark.pg

ORG, OTHER = "org_s10_file_route", "org_s10_file_route_other"
PRIYA = "priya@northwind.test"
NOW = T0 + timedelta(days=60)
ADMIN = AuthCtx(org_id=ORG, actor_id="seat_admin", role="admin", source="jwt")


class _Graph:
    def __init__(self, engine) -> None:
        self.engine = engine


@pytest.fixture
def store(pg_store):
    for org in (ORG, OTHER):
        tenant(pg_store, org)
        with pg_store.engine.begin() as c:
            _ensure_tenant_node(pg_store, c, org)
        for i, gap in enumerate((1, 2, 2, 3, 9)):
            asked = T0 + timedelta(days=5 * i)
            process(pg_store, org, event_id=f"{org}_ask_{i}", sender=FOUNDER, recipients=(PRIYA,),
                    thread=f"t_{i}", at=asked)
            process(pg_store, org, event_id=f"{org}_her_{i}", sender=PRIYA, thread=f"t_{i}",
                    at=asked + timedelta(days=gap))
        compute_waiting(pg_store, org, now=NOW)
    yield pg_store
    for org in (ORG, OTHER):
        reset(pg_store, org)


def _client(monkeypatch, store, ctx: AuthCtx) -> TestClient:
    monkeypatch.setattr(routes, "_graph", _Graph(store.engine))
    monkeypatch.setattr(routes, "_now", lambda: NOW)
    monkeypatch.setattr(auth, "check_org_kill", lambda org_id: None)
    app = FastAPI()
    app.include_router(routes.router)
    app.dependency_overrides[get_auth_ctx] = lambda: ctx
    return TestClient(app)


def _file_id(store, org: str) -> str:
    who = node(store, org, PRIYA).node_id
    with store.engine.connect() as c:
        return c.execute(text(
            "select k.anchor_node_id from context_correlations k "
            "  join context_correlation_members m on m.org_id = k.org_id "
            "       and m.correlation_id = k.correlation_id "
            "  join source_events se on se.org_id = m.org_id and se.event_id = m.event_id "
            " where k.org_id = :o and lower(se.actor->>'email') = :k limit 1"),
            {"o": org, "k": PRIYA}).scalar() or who


def test_a_file_reads_with_its_timeline_and_its_numbers(monkeypatch, store):
    file_id = _file_id(store, ORG)
    answer = _client(monkeypatch, store, ADMIN).get(f"/v1/workstreams/{file_id}")
    assert answer.status_code == 200
    body = answer.json()
    assert body["as_of"] == NOW.isoformat()
    assert body["file"]["file_id"] == file_id and body["file"]["counterparty"]["key"] == "northwind.test"
    assert [t["event_id"] for t in body["timeline"]["touches"]][:2] == [f"{ORG}_ask_0", f"{ORG}_her_0"]
    assert body["timeline"]["usual_gap"]["n"] == 9
    [priya] = body["numbers"]["people"]
    assert priya["key"] == PRIYA
    assert (priya["their_reply_time"]["value"], priya["their_reply_time"]["n"]) == (2.0, 5)
    assert priya["their_normal"]["says"] == "usually 2 days (n=5, person)"
    assert priya["your_reply_time"]["says"] == "not measured"
    assert body["numbers"]["no_reply_can_be_said"] is False, "no mailbox has vouched for anything"


def test_an_unknown_file_is_404(monkeypatch, store):
    assert _client(monkeypatch, store, ADMIN).get("/v1/workstreams/node_nope").status_code == 404


def test_another_tenants_file_is_the_same_404(monkeypatch, store):
    theirs = _file_id(store, OTHER)
    answer = _client(monkeypatch, store, ADMIN).get(f"/v1/workstreams/{theirs}")
    assert answer.status_code == 404 and answer.json()["detail"] == "no such file"


def test_a_scoped_key_is_refused(monkeypatch, store):
    scoped = AuthCtx(org_id=ORG, actor_id="key_x", source="api_key", scopes=["read:cards"])
    file_id = _file_id(store, ORG)
    assert _client(monkeypatch, store, scoped).get(f"/v1/workstreams/{file_id}").status_code == 403


def test_reading_writes_nothing(monkeypatch, store):
    def counts():
        with store.engine.connect() as c:
            return [c.execute(text(f"select count(*) from {t} where org_id = :o"),
                              {"o": ORG}).scalar()
                    for t in ("graph_nodes", "graph_facts", "graph_observations",
                              "context_correlations", "context_correlation_members",
                              "open_loops")]
    before = counts()
    _client(monkeypatch, store, ADMIN).get(f"/v1/workstreams/{_file_id(store, ORG)}")
    assert counts() == before


def test_without_a_database_it_says_so(monkeypatch):
    monkeypatch.setattr(routes, "_graph", None)
    monkeypatch.setattr(auth, "check_org_kill", lambda org_id: None)
    app = FastAPI()
    app.include_router(routes.router)
    app.dependency_overrides[get_auth_ctx] = lambda: ADMIN
    assert TestClient(app).get("/v1/workstreams/node_x").status_code == 503


def test_the_route_is_mounted_on_the_application_behind_the_tenant_read():
    import inspect

    from fastapi.params import Depends as DependsMarker

    from genios_engine.main import app
    assert set(app.openapi()["paths"]["/v1/workstreams/{file_id}"]) == {"get"}
    gates = [p.default.dependency for p in inspect.signature(routes.read_workstream).parameters
             .values() if isinstance(p.default, DependsMarker)]
    assert gates == [auth.get_current_org]


def test_the_clock_is_read_at_the_request_boundary():
    """The read models take `now`; only the route reads the wall clock."""
    assert abs((routes._now() - datetime.now(timezone.utc)).total_seconds()) < 5
