"""L1 rebuild C3 — a page's landing writes are ONE transaction, on real Postgres.

The same page is captured twice, once with `PageWrites` and once with it switched off, and the two
must land the SAME rows in `source_events`, `raw_payloads`, `prepared_content` and `event_trace`
while the batched run opens far fewer transactions. Plus the two behaviours a buffer can break:
a mail repeated inside one page lands once, and a page whose flush fails lands nothing.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import event, text

from genios_engine.capture.acquire.sync_runner import run_sync
from genios_engine.capture.connectors.base import RawObject, SourceBatch
from genios_engine.capture.landing import page_writes
from genios_engine.platform.ids import new_id

pytestmark = pytest.mark.pg


@pytest.fixture
def pg(live_db_url):
    if not live_db_url:
        pytest.skip("GENIOS_TEST_DATABASE_URL not set")
    from cryptography.fernet import Fernet
    from genios_engine.capture.landing.pg_repository import PostgresSourceEventRepository
    from genios_engine.capture.payload_store import PostgresRawPayloadStore
    from genios_engine.capture.prepared_store import PostgresPreparedContentStore
    from genios_engine.capture.trace_store import PostgresTraceRepository
    from genios_engine.platform.db import get_engine

    engine = get_engine(live_db_url)
    orgs: list[str] = []

    def new_org() -> str:
        org = new_id("org")
        with engine.begin() as c:
            c.execute(text("insert into orgs (id, name, email) values (:o, :o, :e)"),
                      {"o": org, "e": f"{org}@example.test"})
        orgs.append(org)
        return org

    stores = dict(repo=PostgresSourceEventRepository(live_db_url),
                  payload_store=PostgresRawPayloadStore(live_db_url, Fernet.generate_key().decode()),
                  prepared_store=PostgresPreparedContentStore(live_db_url),
                  trace_repo=PostgresTraceRepository(live_db_url))
    yield engine, stores, new_org
    with engine.begin() as c:
        for org in orgs:
            c.execute(text("delete from orgs where id = :o"), {"o": org})


class _Page:
    source = "gmail"

    def __init__(self, objects):
        self._objects = objects

    def incremental_changes(self, cursor, limit, since=None):
        return SourceBatch(objects=list(self._objects), next_cursor=None)


def _mails(n: int, *, repeat_first: bool = False) -> list[RawObject]:
    base = datetime(2026, 10, 1, 9, tzinfo=timezone.utc)
    out = [RawObject(source="gmail", object_type="email_message", source_object_id=f"m{i}",
                     actor_type="human", actor_email=f"person{i}@acme.test",
                     occurred_at=base + timedelta(minutes=i),
                     raw={"subject": f"Renewal {i}", "body": f"Can we discuss renewal {i}?",
                          "labelIds": ["INBOX"]})
           for i in range(n)]
    return out + ([out[0]] if repeat_first else [])


def _landed(engine, org) -> dict[str, int]:
    with engine.connect() as c:
        return {t: c.execute(text(f"select count(*) from {t} where org_id = :o"),
                             {"o": org}).scalar()
                for t in ("source_events", "raw_payloads", "prepared_content", "event_trace")}


def _run(engine, stores, org, objects):
    commits = {"n": 0}

    def _count(conn):
        commits["n"] += 1

    event.listen(engine, "commit", _count)
    try:
        summary = run_sync(_Page(objects), org_id=org, connection_id="con_c3", mode="incremental",
                           **stores)
    finally:
        event.remove(engine, "commit", _count)
    return summary, commits["n"]


def test_a_page_lands_the_same_rows_in_far_fewer_transactions(pg, monkeypatch):
    engine, stores, new_org = pg
    mails = _mails(25)

    batched_org = new_org()
    batched, batched_commits = _run(engine, stores, batched_org, mails)

    monkeypatch.setattr(page_writes.PageWrites, "for_page", classmethod(lambda cls, **kw: None))
    single_org = new_org()
    single, single_commits = _run(engine, stores, single_org, mails)

    assert _landed(engine, batched_org) == _landed(engine, single_org), "same rows, either way"
    assert _landed(engine, batched_org)["source_events"] == 25
    assert (batched.emitted, batched.duplicate) == (single.emitted, single.duplicate)
    print(f"\n25-mail page: {single_commits} commits one by one -> {batched_commits} batched")
    assert batched_commits < single_commits / 3, (batched_commits, single_commits)


def test_a_mail_repeated_inside_one_page_lands_once(pg):
    engine, stores, new_org = pg
    org = new_org()
    summary, _ = _run(engine, stores, org, _mails(3, repeat_first=True))
    assert _landed(engine, org)["source_events"] == 3
    assert summary.duplicate == 1, "the repeat is a duplicate, as it would be after a flush"


def test_a_page_whose_flush_fails_lands_nothing(pg, monkeypatch):
    engine, stores, new_org = pg
    org = new_org()

    def _boom(self):
        raise RuntimeError("database went away mid-flush")

    monkeypatch.setattr(page_writes.PageWrites, "flush", _boom)
    with pytest.raises(RuntimeError):
        _run(engine, stores, org, _mails(5))
    assert _landed(engine, org)["source_events"] == 0, "all-or-nothing: the next run reads it again"
