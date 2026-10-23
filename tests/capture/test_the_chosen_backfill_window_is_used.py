"""GeniOS-011 S09.U1 · the window the founder picks is the window captured.

    pytest tests/capture/test_the_chosen_backfill_window_is_used.py -q
    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… pytest tests/capture/test_the_chosen_backfill_window_is_used.py -q

THE DEFECT (audit `l1-resync-and-history-window`, skeptic's correction; `l1-c3-d16-history-window-still-60-days`).
The dashboard's Sources modal offers a "Historical backfill" of 30 days, 90 days, 6 months or 12 months
and PUTs it to `/api/org/{org}/integrations/{tool}/config`, which stored it in
`integration_preferences.sync_settings.historical_backfill` — and nothing in capture read that value.
Every connector reads `connections.capture_scope.backfill_days`, sixty days unless an operator PATCHed
it. So a founder could pick "12 months" and get sixty days; Rohit's Theresa/Antler thread, last inbound
77 days ago, sat outside memory.

And a second wipe sat in the same path: the dashboard's post-connect save is followed by
`/integrations/{tool}/sync`, which mirrors the connection with an EMPTY `capture_scope` — so even an
operator's PATCH was erased by the next Sync click.

This file holds four things true:
  1. the modal's choice parses to days, closed vocabulary, 12 months → 365;
  2. saving it writes it through to every one of the tenant's connections of that tool (Postgres);
  3. a Sync click (the mirror) keeps the window on an existing row, and a row made after the pick
     starts with it;
  4. the owner's history drain (STEP-08's resync) BYPASSES the ingestion meter, and says so in the log
     with the meter's numbers before it reads a page.
"""
from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import text

from genios_engine.api import account_routes
from genios_engine.api import routes
from genios_engine.capture.connectors.backfill import BACKFILL_DAYS_KEY
from genios_engine.capture.connectors.backfill import DEFAULT_BACKFILL_DAYS
from genios_engine.capture.connectors.backfill import DRAIN_QUOTA_DECISION
from genios_engine.capture.connectors.backfill import backfill_window_for
from genios_engine.capture.connectors.backfill import chosen_backfill_days
from genios_engine.capture.connections.store import InMemoryConnectionStore
from genios_engine.contracts.connection import Connection
from genios_engine.platform.auth import AuthCtx
from genios_engine.platform.auth import get_auth_ctx


# =================================================================================================
# 1 · The modal's choice, as days
# =================================================================================================

@pytest.mark.parametrize("settings, days", [
    # the Sources modal's ids (dashboard src/components/sources/source-preferences.ts:67-72)
    ({"historical_backfill": "30d"}, 30),
    ({"historical_backfill": "90d"}, 90),
    ({"historical_backfill": "180d"}, 180),
    ({"historical_backfill": "365d"}, 365),
    # the older Integrations page sends its labels under a camelCase key
    ({"historicalBackfill": "1 month"}, 30),
    ({"historicalBackfill": "3 months"}, 90),
    ({"historicalBackfill": "6 months"}, 180),
    ({"historicalBackfill": "12 months"}, 365),
    ({"historical_backfill": " 12 Months "}, 365),
    ({"historical_backfill": 365}, 365),
    # snake_case wins when both are present: it is what the current modal sends
    ({"historical_backfill": "365d", "historicalBackfill": "1 month"}, 365),
])
def test_the_founders_pick_reads_as_days(settings, days):
    assert chosen_backfill_days(settings) == days


@pytest.mark.parametrize("settings", [{}, None, {"historical_backfill": None},
                                      {"configured_cadence": "1h"}])
def test_no_pick_is_no_window_and_never_the_default(settings):
    """`None`, not sixty: a save that names no window must leave the connection's window alone."""
    assert chosen_backfill_days(settings) is None


@pytest.mark.parametrize("value", ["forever", "0d", "4000d", "12 weeks", True, 3.5, ""])
def test_a_pick_that_cannot_be_honoured_is_refused(value):
    """Loud, like `backfill_window_for`: a typo'd window must never quietly become sixty days."""
    with pytest.raises(ValueError):
        chosen_backfill_days({"historical_backfill": value})


# =================================================================================================
# 3 · A Sync click keeps the window; a row made after the pick starts with it (no database)
# =================================================================================================

ORG_MEM = "org_s09u1_mirror"


def test_a_sync_click_keeps_the_window_on_the_connection(monkeypatch):
    """`/integrations/{tool}/sync` and sync-all call `_mirror_connection` on every click. It upserted
    `capture_scope = {}`, erasing the founder's window and any operator PATCH before the sync read it."""
    store = InMemoryConnectionStore()
    cid = f"con_{ORG_MEM}_gmail"
    store.add(Connection(connection_id=cid, org_id=ORG_MEM, source_type="gmail",
                         composio_user_id=ORG_MEM,
                         config={BACKFILL_DAYS_KEY: 365, "label": "kept"}))
    monkeypatch.setattr(routes, "_connections", store)
    monkeypatch.setattr(account_routes, "chosen_capture_scope",
                        lambda *_a, **_k: pytest.fail("an existing row must not be re-seeded"))

    routes._mirror_connection(ORG_MEM, "gmail")

    kept = store.get(cid)
    assert kept.status == "connected"
    assert kept.config == {BACKFILL_DAYS_KEY: 365, "label": "kept"}
    assert backfill_window_for(kept).days == 365


def test_a_connection_made_after_the_pick_starts_with_it(monkeypatch):
    store = InMemoryConnectionStore()
    monkeypatch.setattr(routes, "_connections", store)
    asked = []
    monkeypatch.setattr(account_routes, "chosen_capture_scope",
                        lambda org, tool: (asked.append((org, tool)), {BACKFILL_DAYS_KEY: 365})[1])

    routes._mirror_connection(ORG_MEM, "gmail")

    assert asked == [(ORG_MEM, "gmail")]
    assert backfill_window_for(store.get(f"con_{ORG_MEM}_gmail")).days == 365


def test_a_connection_made_with_no_pick_keeps_the_default(monkeypatch):
    """The production default does not move: no pick, no key, sixty days (the brief's rule)."""
    store = InMemoryConnectionStore()
    monkeypatch.setattr(routes, "_connections", store)
    monkeypatch.setattr(account_routes, "chosen_capture_scope", lambda *_a: {})

    routes._mirror_connection(ORG_MEM, "gmail")

    made = store.get(f"con_{ORG_MEM}_gmail")
    assert BACKFILL_DAYS_KEY not in made.config
    assert backfill_window_for(made).days == DEFAULT_BACKFILL_DAYS == 60


# =================================================================================================
# 4 · The history drain and the ingestion meter: an explicit, logged decision
# =================================================================================================

class _Summary:
    scanned = 3
    emitted = 2
    cursor_exhausted = True


def test_the_history_drain_bypasses_a_full_meter_and_says_so_first(monkeypatch, caplog):
    """STEP-08's resync lands its mail through `POST /connections/{id}/backfill`. That door never
    read the meter — a bypass nobody had decided or could see. Now it is decided (`bypass`: trimming
    a drain to the headroom would leave freed keys with no message, and a TRUNCATED re-run always
    starts from the newest page) and it is logged with the meter's numbers BEFORE the first page."""
    assert DRAIN_QUOTA_DECISION == "bypass"
    conn = Connection(connection_id="con_s09u1_drain", org_id="org_s09u1_drain",
                      source_type="gmail", composio_user_id="org_s09u1_drain",
                      config={BACKFILL_DAYS_KEY: 365})
    calls: list[str] = []
    monkeypatch.setattr(routes, "_graph", SimpleNamespace(engine=object()), raising=False)
    monkeypatch.setattr(routes._connections, "get", lambda _cid: conn, raising=False)
    monkeypatch.setattr(routes, "make_connector_for", lambda _c, **_: object(), raising=False)
    for helper in ("make_relevance_classifier", "_sender_resolver_for", "_coverage_fn_for",
                   "_esqe_stage_for", "_structured_lane_for", "_mailbox_owner_for_connection",
                   "_semantic_lane_for"):
        monkeypatch.setattr(routes, helper, lambda *a, **k: None, raising=False)
    monkeypatch.setattr(routes, "_run_l2", lambda *a, **k: None, raising=False)
    monkeypatch.setattr(routes, "_replay_l2_history", lambda *a, **k: False, raising=False)

    import genios_engine.platform.quota as quota
    monkeypatch.setattr(quota, "sync_status", lambda _e, org: (
        calls.append(f"meter:{org}"),
        {"tier": "trial", "used": 1200, "limit": 1000, "remaining": 0, "exhausted": True,
         "first_period": False, "backfill_included": 0})[1])

    def _drain(*_a, **_k):
        calls.append("drain")
        return _Summary()

    import genios_engine.capture.acquire.sync_runner as sync_runner
    monkeypatch.setattr(sync_runner, "backfill_drain", _drain, raising=False)

    class _BG:
        @staticmethod
        def add_task(fn, *a, **k):
            fn(*a, **k)

    with caplog.at_level(logging.INFO):
        routes.backfill_connection(conn.connection_id, _BG(), org_id=conn.org_id)  # type: ignore[arg-type]

    assert calls == ["meter:org_s09u1_drain", "drain"], "a full meter must not stop the drain"
    lines = [r.getMessage() for r in caplog.records if "quota=bypass" in r.getMessage()]
    assert len(lines) == 1, [r.getMessage() for r in caplog.records]
    line = lines[0]
    for part in ("org=org_s09u1_drain", "conn=con_s09u1_drain", "window=365d", "used=1200",
                 "limit=1000", "remaining=0", "exhausted"):
        assert part in line, (part, line)


def test_the_drain_decision_still_logs_when_the_meter_cannot_be_read(monkeypatch, caplog):
    """Fail open like every meter read — and say the meter was unread, never a fabricated zero."""
    conn = Connection(connection_id="con_s09u1_unread", org_id="org_s09u1_unread",
                      source_type="gmail", composio_user_id="org_s09u1_unread")
    monkeypatch.setattr(routes, "_graph", object(), raising=False)        # no `.engine` at all
    monkeypatch.setattr(routes._connections, "get", lambda _cid: conn, raising=False)
    monkeypatch.setattr(routes, "make_connector_for", lambda _c, **_: object(), raising=False)
    for helper in ("make_relevance_classifier", "_sender_resolver_for", "_coverage_fn_for",
                   "_esqe_stage_for", "_structured_lane_for", "_mailbox_owner_for_connection",
                   "_semantic_lane_for"):
        monkeypatch.setattr(routes, helper, lambda *a, **k: None, raising=False)
    monkeypatch.setattr(routes, "_run_l2", lambda *a, **k: None, raising=False)
    monkeypatch.setattr(routes, "_replay_l2_history", lambda *a, **k: False, raising=False)
    drained = []
    import genios_engine.capture.acquire.sync_runner as sync_runner
    monkeypatch.setattr(sync_runner, "backfill_drain",
                        lambda *a, **k: (drained.append(1), _Summary())[1], raising=False)

    class _BG:
        @staticmethod
        def add_task(fn, *a, **k):
            fn(*a, **k)

    with caplog.at_level(logging.INFO):
        routes.backfill_connection(conn.connection_id, _BG(), org_id=conn.org_id)  # type: ignore[arg-type]

    assert drained == [1]
    line = next(r.getMessage() for r in caplog.records if "quota=bypass" in r.getMessage())
    assert "meter unread" in line and f"window={DEFAULT_BACKFILL_DAYS}d" in line, line


# =================================================================================================
# 2 · Saving the pick writes it through — real Postgres
# =================================================================================================

@pytest.fixture
def pg(live_db_url, monkeypatch):
    if not live_db_url:
        pytest.skip("GENIOS_TEST_DATABASE_URL not set — the write-through is SQL")
    from genios_engine.platform.db import get_engine

    engine = get_engine(live_db_url)
    run = uuid.uuid4().hex[:10]
    orgs = (f"org_s09u1_{run}", f"org_s09u1_{run}_other")
    with engine.begin() as conn:
        cols = conn.execute(text(
            "select column_name, data_type from information_schema.columns "
            "where table_schema='public' and table_name='orgs' and is_nullable='NO' "
            "and column_default is null and column_name<>'id'")).all()
        now = datetime.now(timezone.utc)
        for org in orgs:
            names, params = ["id"], {"id": org}
            for col in cols:
                names.append(col.column_name)
                params[col.column_name] = (0 if "int" in col.data_type
                                           or "numeric" in col.data_type
                                           else now if "timestamp" in col.data_type else org)
            conn.execute(text(f"insert into orgs ({', '.join(names)}) values "
                              f"({', '.join(':' + n for n in names)})"), params)
    monkeypatch.setattr(account_routes, "_graph", SimpleNamespace(engine=engine))
    yield SimpleNamespace(engine=engine, org=orgs[0], other=orgs[1], url=live_db_url)
    with engine.begin() as conn:      # connections and integration_preferences cascade
        conn.execute(text("delete from orgs where id in (:a, :b)"), {"a": orgs[0], "b": orgs[1]})


def _client(org: str) -> TestClient:
    app = FastAPI()
    app.include_router(account_routes.router)
    app.dependency_overrides[get_auth_ctx] = lambda: AuthCtx(org_id=org, actor_id="seat_founder")
    return TestClient(app)


def _connection(engine, cid: str, org: str, source: str, scope: dict) -> None:
    with engine.begin() as conn:
        conn.execute(text(
            "insert into connections (connection_id, org_id, source_type, composio_user_id, "
            "capture_scope, status) values (:c, :o, :s, :o, cast(:scope as jsonb), 'connected')"),
            {"c": cid, "o": org, "s": source, "scope": json.dumps(scope)})


def _scope(engine, cid: str) -> dict:
    with engine.connect() as conn:
        value = conn.execute(text("select capture_scope from connections where connection_id=:c"),
                             {"c": cid}).scalar()
    return json.loads(value) if isinstance(value, str) else dict(value or {})


def _save(org: str, tool: str, backfill) -> object:
    return _client(org).put(f"/api/org/{org}/integrations/{tool}/config", json={
        "syncSettings": {"configured_cadence": "auto", "historical_backfill": backfill,
                         "source_volatility": "provider_capability_aware"},
        "preferences": {"schema_version": 1, "mode": "simple",
                        "default_profile": {"backfill": backfill}}})


@pytest.mark.pg
def test_picking_twelve_months_puts_365_days_on_the_tenants_gmail(pg):
    from genios_engine.capture.connections.store import PostgresConnectionStore
    from genios_engine.capture.coverage.window import coverage_for_connection

    gmail, seat = f"con_{pg.org}_gmail", f"con_{pg.org}_seat_a_gmail"
    gcal, theirs = f"con_{pg.org}_gcal", f"con_{pg.other}_gmail"
    _connection(pg.engine, gmail, pg.org, "gmail", {"label": "kept", BACKFILL_DAYS_KEY: 60})
    _connection(pg.engine, seat, pg.org, "gmail", {})
    _connection(pg.engine, gcal, pg.org, "gcal", {})
    _connection(pg.engine, theirs, pg.other, "gmail", {})

    res = _save(pg.org, "gmail", "365d")

    assert res.status_code == 200, res.text
    assert res.json()["backfill_days"] == 365 and res.json()["connections_updated"] == 2
    assert _scope(pg.engine, gmail) == {"label": "kept", BACKFILL_DAYS_KEY: 365}
    assert _scope(pg.engine, seat) == {BACKFILL_DAYS_KEY: 365}
    assert _scope(pg.engine, gcal) == {}, "another tool's window is that tool's own pick"
    assert _scope(pg.engine, theirs) == {}, "another tenant's connection is never touched"
    # …and it is the window the connector and the coverage read now use.
    assert backfill_window_for(PostgresConnectionStore(pg.url).get(gmail)).days == 365
    with pg.engine.connect() as conn:
        cov = coverage_for_connection(conn, org_id=pg.org, connection_id=gmail,
                                      now=datetime.now(timezone.utc))
    assert cov.window_days == 365


@pytest.mark.pg
def test_the_calendar_pick_lands_on_the_calendar_under_its_canonical_name(pg):
    gcal = f"con_{pg.org}_gcal"
    _connection(pg.engine, gcal, pg.org, "gcal", {})

    res = _save(pg.org, "googlecalendar", "180d")

    assert res.status_code == 200, res.text
    assert _scope(pg.engine, gcal) == {BACKFILL_DAYS_KEY: 180}


@pytest.mark.pg
def test_a_pick_that_cannot_be_honoured_writes_nothing(pg):
    gmail = f"con_{pg.org}_gmail"
    _connection(pg.engine, gmail, pg.org, "gmail", {BACKFILL_DAYS_KEY: 90})

    res = _save(pg.org, "gmail", "forever")

    assert res.status_code == 422, res.text
    assert _scope(pg.engine, gmail) == {BACKFILL_DAYS_KEY: 90}
    with pg.engine.connect() as conn:
        assert conn.execute(text("select count(*) from integration_preferences where org_id=:o"),
                            {"o": pg.org}).scalar() == 0


@pytest.mark.pg
def test_a_save_that_names_no_window_leaves_the_window_alone(pg):
    gmail = f"con_{pg.org}_gmail"
    _connection(pg.engine, gmail, pg.org, "gmail", {BACKFILL_DAYS_KEY: 365})

    res = _client(pg.org).put(f"/api/org/{pg.org}/integrations/gmail/config",
                              json={"syncSettings": {"configured_cadence": "1h"}})

    assert res.status_code == 200, res.text
    assert res.json()["backfill_days"] is None and res.json()["connections_updated"] == 0
    assert _scope(pg.engine, gmail) == {BACKFILL_DAYS_KEY: 365}


@pytest.mark.pg
def test_the_pick_survives_a_sync_click_and_seeds_a_later_connection(pg, monkeypatch):
    """The whole dashboard path: save (post-connect) → Sync click (the mirror) → the row the sync
    reads. And a tenant who picked before the connection row existed: the mirror creates it with
    the pick."""
    from genios_engine.capture.connections.store import PostgresConnectionStore

    store = PostgresConnectionStore(pg.url)
    monkeypatch.setattr(routes, "_connections", store)
    gmail = f"con_{pg.org}_gmail"
    _connection(pg.engine, gmail, pg.org, "gmail", {})

    assert _save(pg.org, "gmail", "365d").status_code == 200
    assert account_routes.chosen_capture_scope(pg.org, "gmail") == {BACKFILL_DAYS_KEY: 365}
    routes._mirror_connection(pg.org, "gmail")
    assert backfill_window_for(store.get(gmail)).days == 365

    assert _save(pg.org, "googlecalendar", "365d").status_code == 200   # no gcal row yet
    routes._mirror_connection(pg.org, "gcal")
    assert backfill_window_for(store.get(f"con_{pg.org}_gcal")).days == 365
