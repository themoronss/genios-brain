"""L1.1-U2 · the waitlist — a source a tenant wants and cannot connect is RECORDED, not lost.

"Coming soon" with no action behind it is the same silence the hardcoded tile produced, one
screen later: the founder still cannot connect Slack, and we still do not know they wanted it.
These tests pin the three refusals (a connectable source, a by-design deliberate one, a
malformed id), the one acceptance that matters most (an id we have never described is KEPT —
that is demand no internal list can produce), and the two properties the table's value rests
on: re-asking is a louder vote rather than a duplicate row, and family/capability/built-yet are
DERIVED from the registry at read time rather than frozen into the row.

The Postgres lane at the bottom is not a formality. The upsert increments in SQL, the id has a
CHECK constraint, and the org FK is what makes tenant erasure real — none of which an in-memory
store can be wrong about.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from genios_engine.api import account_routes, routes
from genios_engine.capture.source_waitlist import (MAX_NOTE_CHARS, MAX_SOURCE_CHARS,
                                                   InMemorySourceWaitlist, WaitlistRefused,
                                                   normalize_source, request_source)
from genios_engine.platform import auth, wiring
from genios_engine.platform.auth import AuthCtx, get_auth_ctx

NOW = datetime(2026, 1, 14, 9, 0, tzinfo=timezone.utc)
LATER = NOW + timedelta(days=3)
ORG = "org_waitlist"


@pytest.fixture()
def store() -> InMemorySourceWaitlist:
    return InMemorySourceWaitlist()


# ── what may be recorded, and what may not ───────────────────────────────────────────────
@pytest.mark.parametrize("source,reason", [
    ("gmail", "connectable"), ("hubspot", "connectable"), ("gcal", "connectable"),
    ("upload", "no connector by design"), ("internal", "no connector by design"),
    ("human", "no connector by design"), ("agent", "no connector by design"),
])
def test_a_source_that_needs_no_waitlist_is_refused(store, source, reason):
    """Two different lies, one refusal each. Waitlisting Gmail means the caller is reading a
    stale catalog and the tenant will never be told to just go connect it; waitlisting
    `upload` promises a shipped feature is coming."""
    with pytest.raises(WaitlistRefused) as exc:
        request_source(store, org_id=ORG, source=source, eval_time=NOW)
    assert source in str(exc.value)
    assert store.entries_for(ORG) == ()


@pytest.mark.parametrize("source", ["slack", "jira", "gsheets", "gdocs", "salesforce"])
def test_a_described_but_unbuilt_source_is_recorded(store, source):
    entry = request_source(store, org_id=ORG, source=source, eval_time=NOW)
    assert entry.source == source and entry.requests == 1 and entry.registered is True


def test_a_source_we_never_described_is_recorded_not_refused(store):
    """The highest-signal row in the table: a system we have not even listed. Refusing it
    for being unknown would throw away the only demand no internal list can produce."""
    entry = request_source(store, org_id=ORG, source="ClickUp", eval_time=NOW)
    assert entry.source == "clickup"
    assert entry.registered is False and entry.family == "unclassified"
    assert entry.capability is None


@pytest.mark.parametrize("bad", [
    "", "   ", "drop table source_waitlist", "sla ck", "we use Zoho for everything",
    "-leading", "x" * (MAX_SOURCE_CHARS + 1),
])
def test_a_malformed_source_id_is_refused(store, bad):
    """Open vocabulary, bounded shape — otherwise the column decays into free text and the
    demand report has nothing to group on."""
    with pytest.raises(WaitlistRefused):
        request_source(store, org_id=ORG, source=bad, eval_time=NOW)


def test_an_alias_collapses_to_its_canonical_id(store):
    """Ten tenants asking in three spellings must be ten votes for one row."""
    assert normalize_source("Google_Sheets") == "gsheets"
    first = request_source(store, org_id=ORG, source="google_sheets", eval_time=NOW)
    second = request_source(store, org_id=ORG, source="GSHEETS", eval_time=LATER)
    assert first.source == second.source == "gsheets"
    assert second.requests == 2
    assert len(store.entries_for(ORG)) == 1


def test_an_oversized_note_is_refused_and_a_blank_one_becomes_none(store):
    with pytest.raises(WaitlistRefused):
        request_source(store, org_id=ORG, source="slack", note="x" * (MAX_NOTE_CHARS + 1),
                       eval_time=NOW)
    assert request_source(store, org_id=ORG, source="slack", note="   ",
                          eval_time=NOW).latest_note is None


def test_an_org_id_is_required(store):
    with pytest.raises(WaitlistRefused):
        request_source(store, org_id="", source="slack", eval_time=NOW)


# ── what a row means once it is there ────────────────────────────────────────────────────
def test_reasking_is_a_louder_vote_and_keeps_the_first_note(store):
    """`requests` is strength of demand. And a re-request with no note must not erase the
    sentence that explained the first one — that sentence is the whole reason to read it."""
    request_source(store, org_id=ORG, source="slack", requested_by="seat_a",
                   note="our whole sales team lives there", eval_time=NOW)
    again = request_source(store, org_id=ORG, source="slack", requested_by="seat_b",
                           eval_time=LATER)
    assert again.requests == 2
    assert again.latest_note == "our whole sales team lives there"
    assert again.latest_requested_by == "seat_b"
    assert again.first_requested_at == NOW and again.last_requested_at == LATER


def test_entries_are_ordered_by_demand(store):
    request_source(store, org_id=ORG, source="jira", eval_time=NOW)
    for _ in range(3):
        request_source(store, org_id=ORG, source="slack", eval_time=NOW)
    assert [e.source for e in store.entries_for(ORG)] == ["slack", "jira"]


def test_one_orgs_demand_is_never_another_orgs(store):
    request_source(store, org_id=ORG, source="slack", eval_time=NOW)
    assert store.entries_for("org_other") == ()


def test_the_row_stores_no_registry_facts_so_they_cannot_go_stale(store, monkeypatch):
    """family/capability/registered are read back from the registry, not frozen into the
    row. The day a source ships, every standing row must reflect it — a stored `built:
    false` would make the "tell these tenants it is ready" report say nothing."""
    entry = request_source(store, org_id=ORG, source="slack", eval_time=NOW)
    assert entry.family == "communication" and entry.capability == "communication"
    stored = store._rows[(ORG, "slack")]
    assert stored.family == "communication"
    # the derivation, not a copy: the same read after the registry changes answers anew
    import genios_engine.capture.source_waitlist as unit
    monkeypatch.setattr(unit, "capability_of", lambda source: "renamed_capability")
    assert unit._entry(org_id=ORG, source="slack", requests=1, first_requested_at=NOW,
                       last_requested_at=NOW, latest_note=None,
                       latest_requested_by=None).capability == "renamed_capability"


# ── the endpoint ─────────────────────────────────────────────────────────────────────────
@pytest.fixture()
def client(monkeypatch, store):
    monkeypatch.setattr(auth, "check_org_kill", lambda org_id: None)
    monkeypatch.setattr(wiring, "make_source_waitlist_store", lambda: store)
    app = FastAPI()
    app.include_router(routes.router)
    app.dependency_overrides[get_auth_ctx] = lambda: AuthCtx(
        org_id=ORG, actor_id="seat_founder", scopes=None)
    return TestClient(app)


def test_post_records_and_get_reads_back(client, store):
    posted = client.post("/sources/waitlist",
                         json={"source": "slack", "note": "sales lives there"})
    assert posted.status_code == 200
    body = posted.json()
    assert body["source"] == "slack" and body["requests"] == 1
    assert body["requested_by"] == "seat_founder"          # taken from the credential
    listed = client.get("/sources/waitlist").json()["entries"]
    assert [e["source"] for e in listed] == ["slack"]
    assert listed[0]["note"] == "sales lives there"


@pytest.mark.parametrize("source,detail", [("gmail", "connectable today"),
                                           ("upload", "no connector by design"),
                                           ("not a slug", "slug")])
def test_a_refused_request_is_a_400_that_says_why(client, store, source, detail):
    got = client.post("/sources/waitlist", json={"source": source})
    assert got.status_code == 400 and detail in got.json()["detail"]
    assert client.get("/sources/waitlist").json()["entries"] == []


def test_a_scoped_credential_cannot_write_the_waitlist(monkeypatch, store):
    monkeypatch.setattr(auth, "check_org_kill", lambda org_id: None)
    monkeypatch.setattr(wiring, "make_source_waitlist_store", lambda: store)
    app = FastAPI()
    app.include_router(routes.router)
    app.dependency_overrides[get_auth_ctx] = lambda: AuthCtx(
        org_id=ORG, actor_id="key", scopes=["cards.read"])
    client = TestClient(app)
    assert client.post("/sources/waitlist", json={"source": "slack"}).status_code == 403
    assert store.entries_for(ORG) == ()


def test_the_table_is_on_the_tenant_erasure_list():
    """That loop runs with no try/except by design, so a table missing from it leaks a named
    org's rows past an account deletion."""
    assert "source_waitlist" in account_routes._ORG_SCOPED_TABLES


# ── the real database ────────────────────────────────────────────────────────────────────
@pytest.fixture()
def pg(live_db_url):
    """A rolled-back transaction on the scratch database, with a real org to hang the FK on."""
    if not live_db_url:
        pytest.skip("no scratch database configured")
    from sqlalchemy import text

    from genios_engine.platform.db import get_engine
    conn = get_engine(live_db_url).connect()
    tx = conn.begin()
    if not conn.execute(text("select to_regclass('public.source_waitlist')")).scalar():
        tx.rollback(); conn.close(); pytest.skip("0083 not applied")
    org = conn.execute(text("select id from orgs limit 1")).scalar()
    if not org:
        tx.rollback(); conn.close(); pytest.skip("no org")
    try:
        yield conn, org
    finally:
        tx.rollback(); conn.close()


def _pg_store(conn):
    """A PostgresSourceWaitlist bound to the test's OWN open transaction, so every row it
    writes is rolled back with it — the store's SQL is what is under test, not its engine."""
    from genios_engine.capture.source_waitlist import PostgresSourceWaitlist

    class _Bound:
        def begin(self):
            return _NoCommit(conn)

        def connect(self):
            return _NoCommit(conn)

    class _NoCommit:
        def __init__(self, c):
            self._c = c

        def __enter__(self):
            return self._c

        def __exit__(self, *exc):
            return False

    store = PostgresSourceWaitlist.__new__(PostgresSourceWaitlist)
    store._engine = _Bound()
    return store


@pytest.mark.pg
def test_postgres_upsert_counts_in_sql_and_keeps_one_row(pg):
    from sqlalchemy import text

    conn, org = pg
    store = _pg_store(conn)
    first = request_source(store, org_id=org, source="slack", requested_by="seat_a",
                           note="sales lives there", eval_time=NOW)
    second = request_source(store, org_id=org, source="slack", eval_time=LATER)
    assert (first.requests, second.requests) == (1, 2)
    assert second.latest_note == "sales lives there"       # coalesce kept it
    assert second.latest_requested_by == "seat_a"
    rows = conn.execute(text("select count(*) from source_waitlist where org_id=:o and "
                             "source='slack'"), {"o": org}).scalar()
    assert rows == 1
    assert [e.source for e in store.entries_for(org)] == ["slack"]


@pytest.mark.pg
def test_postgres_refuses_a_non_slug_id_at_the_constraint_too(pg):
    """The application validates; the column also does. A future caller that bypasses
    `request_source` must not be able to write a sentence into this column."""
    from sqlalchemy import text
    from sqlalchemy.exc import IntegrityError

    conn, org = pg
    with pytest.raises(IntegrityError):
        with conn.begin_nested():
            conn.execute(text(
                "insert into source_waitlist (org_id, source) values (:o, 'not a slug')"),
                {"o": org})


@pytest.mark.pg
def test_postgres_rows_are_org_scoped(pg):
    conn, org = pg
    store = _pg_store(conn)
    request_source(store, org_id=org, source="jira", eval_time=NOW)
    assert store.entries_for("org_no_such_tenant") == ()
