"""STEP-09 · the founder's files, read over the API — the tenant's own, never another's, nothing written.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… pytest tests/api/test_workstream_routes.py -q

Tree `yc2_w27_s09 · M27.C4.L-interface.V2.U02`. `GET /v1/workstreams` is the read model
(`context/workstreams.files_for`) for the signed-in member's tenant, with the brief the founder
accepted: each file's kind, counterparty, evidence, last touch, open asks and whose move it is, and
the named counterparties with mail and no file. Anyone who may read the tenant may read it; a scoped
key may not; and it is mounted on the application.
"""
from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import text

from genios_engine.api import workstream_routes as routes
from genios_engine.platform import auth, company_brief, company_brief_store
from genios_engine.platform.auth import AuthCtx, get_auth_ctx
from tests.context.workstream_world import (CONNECTOR, FOUNDER, T0, UNSUBSCRIBE, WATCHED, later,
                                            mention, process, reset, tenant)

pytestmark = pytest.mark.pg

ORG, OTHER = "org_s09_routes", "org_s09_routes_other"
RAHUL = "rahul@kestrelcap.test"
ADMIN = AuthCtx(org_id=ORG, actor_id="seat_admin", role="admin", source="jwt")


class _Graph:
    def __init__(self, engine) -> None:
        self.engine = engine


@pytest.fixture
def store(pg_store):
    for org in (ORG, OTHER):
        tenant(pg_store, org)
    with pg_store.engine.begin() as c:
        for section, kw in (("connectors", {"address": CONNECTOR}),
                            ("watchlist", {"domain": WATCHED})):
            company_brief_store.add(c, org_id=ORG, section=section, decided_by="founder", at=T0,
                                    words=f"{section} line", **kw)
    brief = company_brief.current(pg_store, ORG)
    process(pg_store, ORG, event_id="evt_intro", sender=CONNECTOR, recipients=(FOUNDER, RAHUL),
            thread="t_intro", headers=UNSUBSCRIBE, mentions=(mention("Rahul Menon"),),
            company_brief=brief)
    process(pg_store, ORG, event_id="evt_notice", sender=f"updates@{WATCHED}",
            company_brief=brief, at=later(1))
    process(pg_store, OTHER, event_id="evt_elsewhere", sender="ops@southwind.test",
            thread="t_elsewhere")
    yield pg_store
    for org in (ORG, OTHER):
        reset(pg_store, org)
        company_brief.invalidate(org)


def _client(monkeypatch, store, ctx: AuthCtx) -> TestClient:
    monkeypatch.setattr(routes, "_graph", _Graph(store.engine))
    monkeypatch.setattr(auth, "check_org_kill", lambda org_id: None)
    app = FastAPI()
    app.include_router(routes.router)
    app.dependency_overrides[get_auth_ctx] = lambda: ctx
    return TestClient(app)


def test_the_tenants_files_are_read_with_its_accepted_brief(monkeypatch, store):
    answer = _client(monkeypatch, store, ADMIN).get("/v1/workstreams")
    assert answer.status_code == 200
    body = answer.json()
    assert [(f["counterparty"]["key"], f["kind"]) for f in body["files"]] == [
        (WATCHED, "watched"), ("kestrelcap.test", "intro")]
    kestrel = body["files"][1]
    assert kestrel["introduced_by"] == CONNECTOR and kestrel["events"] == ["evt_intro"]
    assert kestrel["whose_move"] == "ours" and kestrel["line"] == "connectors line"
    assert body["unfiled"] == [] and body["as_of"]


def test_another_tenants_files_are_never_in_it(monkeypatch, store):
    body = _client(monkeypatch, store, ADMIN).get("/v1/workstreams").json()
    assert "southwind.test" not in {f["counterparty"]["key"] for f in body["files"]}


def test_a_scoped_key_is_refused(monkeypatch, store):
    scoped = AuthCtx(org_id=ORG, actor_id="key_x", source="api_key", scopes=["read:cards"])
    assert _client(monkeypatch, store, scoped).get("/v1/workstreams").status_code == 403


def test_reading_writes_nothing(monkeypatch, store):
    def counts():
        with store.engine.connect() as c:
            return [c.execute(text(f"select count(*) from {t} where org_id = :o"),
                              {"o": ORG}).scalar()
                    for t in ("graph_nodes", "graph_facts", "context_correlations",
                              "context_correlation_members", "open_loops")]
    before = counts()
    _client(monkeypatch, store, ADMIN).get("/v1/workstreams")
    assert counts() == before


def test_without_a_database_it_says_so(monkeypatch):
    monkeypatch.setattr(routes, "_graph", None)
    monkeypatch.setattr(auth, "check_org_kill", lambda org_id: None)
    app = FastAPI()
    app.include_router(routes.router)
    app.dependency_overrides[get_auth_ctx] = lambda: ADMIN
    assert TestClient(app).get("/v1/workstreams").status_code == 503


def test_the_route_is_mounted_on_the_application_behind_the_tenant_read():
    """Read off the OpenAPI schema — this FastAPI includes routers lazily, so walking `app.routes`
    finds no paths at all (`tests/test_l4_pilot_activation.py`). And on the DEPENDENCY that runs."""
    import inspect

    from fastapi.params import Depends as DependsMarker

    from genios_engine.main import app
    assert set(app.openapi()["paths"]["/v1/workstreams"]) == {"get"}
    gates = [p.default.dependency for p in inspect.signature(routes.list_workstreams).parameters
             .values() if isinstance(p.default, DependsMarker)]
    assert gates == [auth.get_current_org]
