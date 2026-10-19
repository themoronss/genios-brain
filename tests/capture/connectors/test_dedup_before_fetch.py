"""L1 rebuild A2 — dedup BEFORE fetch.

A Gmail message whose dedup key has already landed meets `land_raw_object`'s `exists` check and
ends as a duplicate whatever is fetched for it. Before A2 every sweep still paid a full-body fetch
(and, on the fast path, a junk-gate call) for each such message: the date watermark re-lists the
whole boundary day every 15 minutes, and the first sweep after onboarding re-lists the 60-day
window because the backfill writes no cursor. These tests pin that a landed message costs neither,
on both connector paths, and that `run_sync` is what tells the connector which ids have landed.
"""

from __future__ import annotations

import pytest

from genios_engine.capture.acquire.sync_runner import run_sync
from genios_engine.capture.connectors.base import SourceBatch
from genios_engine.capture.connectors.composio import ComposioGmailConnector
from genios_engine.capture.gate.relevance import RelevanceVerdict
from genios_engine.capture.landing.repository import InMemorySourceEventRepository
from genios_engine.contracts.source_event import compute_dedup_key


class _KeepAll:
    """A primed S2 gate that keeps everything, so every NEW message is full-fetched."""

    def __init__(self):
        self.primed: list[str] = []

    def prime(self, objects):
        self.primed.extend(o.source_object_id for o in objects)

    def verdict_for(self, source_object_id):
        return RelevanceVerdict(relevant=True, relevance=0.9, disposition="keep")


class _Gmail(ComposioGmailConnector):
    def __init__(self, *, relevance=None, landed=None):
        self._ocr = None
        self._relevance = relevance
        self._account = None
        self.full_fetches: list[str] = []
        if landed is not None:
            self.bind_landed(lambda object_type, ids: {i for i in ids if i in landed})

    def _full_message(self, mid):
        self.full_fetches.append(mid)
        return {"id": mid, "from": "priya@acme.io", "subject": "renewal",
                "messageText": "full body"}


def _page(*ids: str) -> dict:
    return {"data": {"messages": [{"id": i, "from": "priya@acme.io", "subject": "renewal",
                                   "messageText": "snippet"} for i in ids]}}


def test_fast_path_skips_the_body_and_the_gate_for_a_landed_message():
    gate = _KeepAll()
    conn = _Gmail(relevance=gate, landed={"m1"})
    batch = conn._to_batch(_page("m1", "m2"))

    assert conn.full_fetches == ["m2"], "only the new message is fetched in full"
    assert gate.primed == ["m2"], "the landed message costs no junk-gate call"
    emails = {o.source_object_id for o in batch.objects if o.object_type == "email_message"}
    assert emails == {"m1", "m2"}, "the landed one still reaches landing, which records it"


def test_legacy_path_skips_the_body_for_a_landed_message():
    conn = _Gmail(relevance=None, landed={"m1"})
    conn._to_batch(_page("m1", "m2"))
    assert conn.full_fetches == ["m2"]


def test_an_unbound_connector_fetches_everything_as_before():
    conn = _Gmail(relevance=_KeepAll())
    conn._to_batch(_page("m1", "m2"))
    assert sorted(conn.full_fetches) == ["m1", "m2"]


def test_a_failing_lookup_costs_a_fetch_never_a_mail():
    conn = _Gmail(relevance=_KeepAll())

    def _boom(object_type, ids):
        raise RuntimeError("db down")

    conn.bind_landed(_boom)
    batch = conn._to_batch(_page("m1"))
    assert conn.full_fetches == ["m1"]
    assert [o.source_object_id for o in batch.objects] == ["m1"]


class _Recorder:
    """A connector that only records what `run_sync` bound and lists an empty page."""

    source = "gmail"

    def __init__(self):
        self.landed = None

    def bind_landed(self, fn):
        self.landed = fn

    def initial_snapshot(self, *a, **kw):
        return SourceBatch(objects=[], next_cursor=None)

    def incremental_changes(self, *a, **kw):
        return SourceBatch(objects=[], next_cursor=None)


@pytest.mark.parametrize("mode", ["incremental", "backfill"])
def test_run_sync_binds_the_ledger_lookup(mode):
    repo = InMemorySourceEventRepository()
    key = compute_dedup_key("gmail", "email_message", "m1")
    repo._by_key[("org_a", key)] = object()          # m1 already landed for org_a
    connector = _Recorder()

    run_sync(connector, org_id="org_a", connection_id="con_a", repo=repo, mode=mode)

    assert connector.landed is not None, "run_sync must tell the connector what has landed"
    assert connector.landed("email_message", ["m1", "m2"]) == {"m1"}


def test_the_lookup_is_tenant_scoped():
    repo = InMemorySourceEventRepository()
    repo._by_key[("org_other", compute_dedup_key("gmail", "email_message", "m1"))] = object()
    connector = _Recorder()
    run_sync(connector, org_id="org_a", connection_id="con_a", repo=repo, mode="incremental")
    assert connector.landed("email_message", ["m1"]) == set(), "another org's mail is not ours"


def test_existing_keys_on_postgres(live_db_url):
    """The page lookup on the real (org_id, dedup_key) index — the in-memory store cannot prove
    that `= any(:keys)` binds a Python list as an array."""
    import pytest as _pytest
    if not live_db_url:
        _pytest.skip("GENIOS_TEST_DATABASE_URL not set")
    from datetime import datetime, timezone
    from genios_engine.capture.landing.pg_repository import PostgresSourceEventRepository
    from genios_engine.capture.landing.normalize import to_source_event
    from genios_engine.capture.connectors.base import RawObject
    from genios_engine.contracts.source_event import SyncMode
    from genios_engine.platform.ids import new_id

    from sqlalchemy import create_engine, text
    repo = PostgresSourceEventRepository(live_db_url)
    org = new_id("org")
    eng = create_engine(live_db_url)
    with eng.begin() as c:
        c.execute(text("insert into orgs (id, name, email) values (:o, :o, :e)"),
                  {"o": org, "e": f"{org}@example.test"})
    raw = RawObject(source="gmail", object_type="email_message", source_object_id="pg_m1",
                    actor_type="human", actor_email="priya@acme.io",
                    occurred_at=datetime.now(timezone.utc), raw={"subject": "s"})
    event = to_source_event(raw, org_id=org, connection_id="con_pg",
                            sync_mode=SyncMode.incremental)
    repo.add(event, outcome="emitted")
    k1 = compute_dedup_key("gmail", "email_message", "pg_m1")
    k2 = compute_dedup_key("gmail", "email_message", "pg_m2")

    assert repo.existing_keys(org, [k1, k2]) == {k1}
    assert repo.existing_keys(new_id("org"), [k1]) == set(), "tenant-scoped"
    assert repo.existing_keys(org, []) == set()
    with eng.begin() as c:
        c.execute(text("delete from orgs where id = :o"), {"o": org})
