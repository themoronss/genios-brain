"""L1.1-U2 · REGISTRY HONESTY — no source may be offered that the connect endpoint refuses.

The defect these tests pin is not in the engine's guards; those were already right. It is that
the answer they enforce was never published, so the dashboard wrote its own list of clickable
tiles (`CONNECTABLE_TOOLS` in integrations-page.tsx) and four of its nine — slack, jira,
gsheets, gdocs — are hard-refused by the endpoint the tile calls. The founder clicks a tile the
UI promised would work and gets a 400.

The acceptance line of the unit is the first test in this file, and it is written as a
comparison between two things the product actually reads: what `/sources/catalog` marks
connectable, and what the connect guards accept. Anything the catalog offers that the guard
would refuse is the bug, by construction, forever — including for a source added next year.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from genios_engine.api import routes
from genios_engine.capture.source_registry import (BUILDABLE_SOURCES, OFFER_STATUSES, SOURCES,
                                                   catalog, descriptor_of, offer_of)
from genios_engine.capture.source_waitlist import InMemorySourceWaitlist
from genios_engine.platform import auth, wiring
from genios_engine.platform.auth import AuthCtx, get_auth_ctx

ORG = "org_catalog"


@pytest.fixture()
def api(monkeypatch):
    """Real routes and the real credential boundary; the waitlist store is in-memory.

    `check_org_kill` is stubbed because it reaches for a live engine — an infrastructure
    concern orthogonal to what is under test — while `get_current_org` stays real so the
    scoped-credential refusal below exercises the actual boundary.
    """
    monkeypatch.setattr(auth, "check_org_kill", lambda org_id: None)
    store = InMemorySourceWaitlist()
    monkeypatch.setattr(wiring, "make_source_waitlist_store", lambda: store)

    def _client(ctx: AuthCtx) -> TestClient:
        app = FastAPI()
        app.include_router(routes.router)
        app.dependency_overrides[get_auth_ctx] = lambda: ctx
        return TestClient(app)

    return _client, store


@pytest.fixture()
def client(api):
    build, _ = api
    return build(AuthCtx(org_id=ORG, actor_id="seat_founder", scopes=None))


# ── THE ACCEPTANCE ───────────────────────────────────────────────────────────────────────
def test_no_source_is_offered_as_connectable_that_the_connect_endpoint_would_refuse(client):
    """The unit's acceptance line, checked against the guard's own predicate.

    `IMPLEMENTED_SOURCE_TYPES` is what both `/connect/initiate` and `/auth/{tool}/connect`
    test membership in. If the catalog ever offers something outside it, the tile is a
    promise the next click breaks."""
    from genios_engine.platform.wiring import IMPLEMENTED_SOURCE_TYPES

    body = client.get("/sources/catalog").json()
    offered = {row["source"] for row in body["sources"] if row["connectable"]}
    assert offered == set(body["connectable"])
    assert offered - IMPLEMENTED_SOURCE_TYPES == set()


@pytest.mark.parametrize("tool", ["slack", "jira", "gsheets", "gdocs"])
def test_the_four_tiles_the_dashboard_hardcoded_are_offered_as_waitlist_not_connectable(
        client, tool):
    """The four the frontend listed as clickable and the guards refuse. One row per tool
    because "the catalog is honest" must fail with the tool's name in the message."""
    rows = {row["source"]: row for row in client.get("/sources/catalog").json()["sources"]}
    assert rows[tool]["connectable"] is False
    assert rows[tool]["status"] == "waitlist"


def test_the_upload_door_is_not_advertised_as_coming_soon(client):
    """`upload` has no connector and never will — a person hands it over. Calling that
    "coming soon" would be the opposite lie: a shipped feature reported as unbuilt."""
    rows = {row["source"]: row for row in client.get("/sources/catalog").json()["sources"]}
    for deliberate in ("upload", "internal", "human", "agent"):
        assert rows[deliberate]["status"] == "deliberate"
        assert rows[deliberate]["connectable"] is False


def test_genios_own_output_is_not_offered_at_all(client):
    """Evidence the engine itself produced is not a thing a tenant connects, and putting it
    on a waitlist would invite a request nobody could fulfil."""
    assert offer_of("genios") is None
    assert "genios" not in {row["source"] for row in
                            client.get("/sources/catalog").json()["sources"]}


# ── the derivation itself ────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("source,status", [
    ("gmail", "connectable"), ("hubspot", "connectable"), ("postgres", "connectable"),
    ("slack", "waitlist"), ("salesforce", "waitlist"), ("gdocs", "waitlist"),
    ("upload", "deliberate"), ("agent", "deliberate"),
])
def test_status_is_derived_from_the_descriptor(source, status):
    offer = offer_of(source)
    assert offer is not None and offer.status == status
    assert offer.connectable == (status == "connectable")


def test_every_registered_source_is_described_exactly_once_and_only_by_canonical_id():
    """Aliases resolve, but the catalog lists canonical ids only — nine rows for one system
    is how a UI ends up showing `gcal`, `calendar` and `google_calendar` as three tools."""
    listed = [offer.source for offer in catalog()]
    assert len(listed) == len(set(listed))
    assert set(listed) <= {d.source for d in SOURCES}
    assert offer_of("google_calendar") is not None
    assert offer_of("google_calendar").source == "gcal"


def test_every_status_is_a_declared_one_and_every_buildable_source_is_offered():
    offers = catalog()
    assert {offer.status for offer in offers} <= OFFER_STATUSES
    # Nothing buildable may be hidden: a source we CAN connect that the UI never shows is
    # the same defect pointed the other way.
    canonical_buildable = {descriptor_of(s).source for s in BUILDABLE_SOURCES}
    assert canonical_buildable <= {o.source for o in offers if o.connectable}


def test_catalog_orders_connectable_first_then_alphabetically():
    """The order is product copy — what you can connect today, then what you cannot."""
    offers = catalog()
    keys = [(not o.connectable, o.status, o.source) for o in offers]
    assert keys == sorted(keys)


def test_offer_of_is_none_for_a_source_nobody_described():
    assert offer_of("clickup") is None


# ── the boundary ─────────────────────────────────────────────────────────────────────────
def test_a_scoped_credential_cannot_read_the_catalog(api):
    """The catalog is a tenant-scoped read (it carries this org's waitlist flags), so it
    obeys the same owner boundary as every other dashboard route."""
    build, _ = api
    scoped = build(AuthCtx(org_id=ORG, actor_id="key", scopes=["cards.read"]))
    assert scoped.get("/sources/catalog").status_code == 403


def test_waitlist_flag_is_per_org(api):
    build, store = api
    mine = build(AuthCtx(org_id=ORG, actor_id="a", scopes=None))
    theirs = build(AuthCtx(org_id="org_other", actor_id="b", scopes=None))
    assert mine.post("/sources/waitlist", json={"source": "slack"}).status_code == 200

    def _flag(client_):
        rows = {r["source"]: r for r in client_.get("/sources/catalog").json()["sources"]}
        return rows["slack"]["waitlisted"]

    assert _flag(mine) is True
    assert _flag(theirs) is False
    assert store.entries_for("org_other") == ()


def test_the_catalog_still_answers_when_the_waitlist_store_is_down(client, monkeypatch):
    """Which sources are connectable is a fact about the BUILD. Degrading that answer
    because demand rows could not be read would break the connect page for an unrelated
    reason — the flags go false, the catalog still renders."""
    def _boom():
        raise RuntimeError("waitlist database unreachable")

    monkeypatch.setattr(wiring, "make_source_waitlist_store", _boom)
    body = client.get("/sources/catalog").json()
    assert body["connectable"]
    assert all(row["waitlisted"] is False for row in body["sources"])
