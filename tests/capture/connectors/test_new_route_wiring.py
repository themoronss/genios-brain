"""Three units that were built, tested, and reachable from no HTTP route at all.

    pytest tests/capture/connectors/test_new_route_wiring.py -q

* `with_backfill_days` — L1.2.4-U1's WRITE seam, and the whole reason migration 0082 added the
  column. `backfill_window_for` (the read) decides the window every Gmail and Calendar sync
  uses; the write had no caller, so the setting was readable, per-connection, persisted, and
  UNCHANGEABLE. Every tenant was pinned to `DEFAULT_BACKFILL_DAYS` for ever.
* `mapping_coverage` + `all_mappings` — L1.3.9-U2. An unmapped structured source is parked as
  `mapping_missing` and the tenant sees nothing from a tool they connected; the unit that says
  which sources are in that state answered only its own test.
* `can_dispatch` — the predicate that separates "this source has no real-time lane" from "this
  payload did not parse". Both were reported as `unmapped payload`, which is how a lane whose
  parser was never written stays dead: every push looks like a payload problem.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from genios_engine.api import routes
from genios_engine.capture.connectors.backfill import (BACKFILL_DAYS_KEY, DEFAULT_BACKFILL_DAYS,
                                                       backfill_window_for)
from genios_engine.contracts.connection import Connection
from genios_engine.platform.auth import AuthCtx, get_auth_ctx

ORG = "org_routes_wiring"
CONN = "con_routes_wiring"


class _Store:
    def __init__(self, *connections: Connection) -> None:
        self._by_id = {c.connection_id: c for c in connections}

    def list_active(self, source_type: str | None = None):
        return [c for c in self._by_id.values() if c.status == "connected"]

    def get(self, connection_id: str):
        return self._by_id.get(connection_id)

    def add(self, c: Connection) -> None:                 # the upsert the route persists through
        self._by_id[c.connection_id] = c


@pytest.fixture
def store(monkeypatch):
    s = _Store(Connection(org_id=ORG, connection_id=CONN, source_type="gmail",
                          composio_user_id=ORG),
               Connection(org_id=ORG, connection_id="con_hs", source_type="hubspot",
                          composio_user_id=ORG))
    monkeypatch.setattr(routes, "_connections", s)
    return s


@pytest.fixture
def client(store):
    app = FastAPI()
    app.include_router(routes.router)
    app.dependency_overrides[get_auth_ctx] = lambda: AuthCtx(org_id=ORG, actor_id="seat_founder")
    return TestClient(app)


# ── L1.2.4-U1 · the backfill window's write seam ─────────────────────────────────────────────

def test_a_tenant_can_change_how_far_back_their_first_sync_reaches(client, store):
    """The setting stops being read-only. `backfill_window_for` — the function
    `make_connector_for` calls to build every Gmail and Calendar connector — must see the new
    number off the PERSISTED connection, not off the response body."""
    before = backfill_window_for(store.get(CONN))
    assert before.days == DEFAULT_BACKFILL_DAYS, "the default under test moved"

    res = client.patch(f"/connections/{CONN}/backfill-window", json={"days": 90})

    assert res.status_code == 200, res.text
    assert res.json()["backfill_days"] == 90
    persisted = store.get(CONN)
    assert persisted.config[BACKFILL_DAYS_KEY] == 90
    assert backfill_window_for(persisted).days == 90, (
        "the connector factory would still build the default window — the write did not reach "
        "the read")


def test_an_out_of_range_window_is_refused_at_the_edit_not_at_the_next_sync(client, store):
    """Validation lives INSIDE `with_backfill_days`, which constructs a `BackfillWindow` before
    it copies. That is the difference between a 422 the caller sees and a sync that silently
    clamps a month later."""
    res = client.patch(f"/connections/{CONN}/backfill-window", json={"days": 0})

    assert res.status_code == 422, res.text
    assert BACKFILL_DAYS_KEY not in (store.get(CONN).config or {}), \
        "a refused value was written anyway"


def test_the_window_route_is_not_shadowed_by_the_lifecycle_action_route(client):
    """`/connections/{id}/{action}` matches any single segment. Declared after it, this route
    would arrive as an `action` of "backfill-window" and 422 on the action check — which is a
    422 for the right reason with the wrong meaning, and exactly the kind of shadowing that
    reads as "the endpoint does not work"."""
    res = client.patch(f"/connections/{CONN}/backfill-window", json={"days": 120})
    assert res.status_code == 200
    assert res.json()["backfill_days"] == 120


def test_another_tenants_connection_cannot_be_retuned(client, store):
    store.add(Connection(org_id="org_other", connection_id="con_other", source_type="gmail",
                         composio_user_id="org_other"))
    res = client.patch("/connections/con_other/backfill-window", json={"days": 90})
    assert res.status_code == 404


# ── L1.3.9-U2 · which connected structured sources have no mapping ───────────────────────────

def test_the_mapping_coverage_report_reads_the_tenants_own_connections(client):
    res = client.get("/structured/mapping-coverage")

    assert res.status_code == 200, res.text
    body = res.json()
    assert body["org_id"] == ORG
    assert set(body["connected_sources"]) == {"gmail", "hubspot"}
    # HubSpot's `deal` is carried by `hubspot.deal.v1`, so it is MAPPED…
    deal = [r for r in body["rows"] if r["source"] == "hubspot" and r["object_type"] == "deal"]
    assert deal and deal[0]["mapped"] and deal[0]["mapping_id"] == "hubspot.deal.v1"
    # …and the registry is reported live, never as a list written down in the route.
    assert "hubspot.deal.v1" in body["registered_mappings"]
    assert body["coverage_bp"] == 10000
    assert body["unmapped"] == body["unmapped_structured"] == 0


def test_an_unmapped_structured_source_is_reported_as_actionable(client, store, monkeypatch):
    """The state the report exists for: a connected structured object type no mapping carries.
    Its rows have no prose body, so nothing can read them and the tenant sees nothing from a
    tool they connected."""
    from genios_engine.capture.structured import registry as R

    saved = dict(R._REGISTRY)
    R._REGISTRY.pop(("hubspot", "deal"), None)
    try:
        body = client.get("/structured/mapping-coverage").json()
    finally:
        R._REGISTRY.clear()
        R._REGISTRY.update(saved)

    deal = [r for r in body["rows"] if r["source"] == "hubspot" and r["object_type"] == "deal"]
    assert deal and deal[0]["mapped"] is False and deal[0]["actionable"] is True
    assert body["unmapped_structured"] >= 1
    assert body["coverage_bp"] < 10000, "an unmapped structured source did not move coverage"


# ── L1.2.5-U1 · a source with no real-time lane says so ──────────────────────────────────────

def test_can_dispatch_separates_a_missing_lane_from_a_bad_payload():
    """The predicate itself, on the two answers the webhook route now gives different reasons
    for. `hubspot` is the source that sat in the missing-parser hole for the whole of L1.2.5."""
    from genios_engine.capture.connectors.dispatch import can_dispatch

    assert can_dispatch("hubspot") is True
    assert can_dispatch("gmail") is True
    assert can_dispatch("google_calendar") is True, "an alias must resolve through the registry"
    # A source with no connector at all has no real-time lane, by definition.
    assert can_dispatch("slack") is False
    assert can_dispatch("") is False


def test_the_webhook_route_reports_a_missing_lane_as_its_own_reason(monkeypatch, client):
    """Through the route, against the REAL predicate — `slack` genuinely has no parser, so
    nothing here is stubbed. A source whose parser was never written must not be reported as a
    payload problem; that is how a dead lane stays dead."""
    conn = Connection(org_id=ORG, connection_id="con_ws", source_type="slack",
                      composio_user_id="composio_user_ws")
    monkeypatch.setattr(routes, "_connections", _Store(conn))
    monkeypatch.setattr(routes.get_settings(), "composio_webhook_secret", "", raising=False)

    res = client.post("/webhooks/composio",
                      json={"user_id": "composio_user_ws", "data": {"id": "x"}})

    if res.status_code == 403:                 # fail-closed outside dev; the reason is the point
        pytest.skip("webhook secret not configured in this environment")
    assert res.status_code == 200, res.text
    assert res.json()["reason"] == "no realtime lane", (
        "a source with no parser is still reported as `unmapped payload`, which is "
        "indistinguishable from one bad body")
