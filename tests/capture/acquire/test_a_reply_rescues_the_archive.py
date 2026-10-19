"""L1 rebuild B4 — writing to someone sends their archived mail back to be read (real Postgres).

An investor's first note met an unsubscribe header and was archived (N-02). The founder later
writes to that address. From that run on, the investor's archived note is KEPT again
(`outcome='emitted'`, `attention_reason='promoted:N-02'`) and the re-read ladder reads it. What does
NOT come back: mail the provider filed as SPAM (a FINAL rule), and mail from anyone the founder did
not write to.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import text

from genios_engine.capture.acquire.sync_runner import run_sync
from genios_engine.capture.connectors.base import RawObject, SourceBatch
from genios_engine.platform.ids import new_id

pytestmark = pytest.mark.pg

OWNER = "founder@ourco.test"
INVESTOR = "sama@ankurcapital.test"
T0 = datetime(2026, 10, 1, 9, tzinfo=timezone.utc)


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
    org = new_id("org")
    with engine.begin() as c:
        c.execute(text("insert into orgs (id, name, email) values (:o, :o, :e)"),
                  {"o": org, "e": OWNER})
    stores = dict(repo=PostgresSourceEventRepository(live_db_url),
                  payload_store=PostgresRawPayloadStore(live_db_url, Fernet.generate_key().decode()),
                  prepared_store=PostgresPreparedContentStore(live_db_url),
                  trace_repo=PostgresTraceRepository(live_db_url))
    yield engine, stores, org
    with engine.begin() as c:
        c.execute(text("delete from orgs where id = :o"), {"o": org})


class _Page:
    source = "gmail"

    def __init__(self, objects):
        self._objects = objects

    def incremental_changes(self, cursor, limit, since=None):
        return SourceBatch(objects=list(self._objects), next_cursor=None)


def _mail(oid, sender, *, minutes=0, recipients=(), headers=None, labels=("INBOX",)):
    return RawObject(source="gmail", object_type="email_message", source_object_id=oid,
                     actor_type="human", actor_email=sender, recipients=tuple(recipients),
                     occurred_at=T0 + timedelta(minutes=minutes),
                     raw={"subject": f"note {oid}", "body": "Following up on our call.",
                          "headers": dict(headers or {}), "labelIds": list(labels)})


def _row(engine, org, oid):
    with engine.connect() as c:
        return c.execute(text("select outcome, attention_reason from source_events "
                              "where org_id = :o and source_object_id = :s"),
                         {"o": org, "s": oid}).one()


def _sync(stores, org, objects):
    return run_sync(_Page(objects), org_id=org, connection_id="con_b4", mode="incremental",
                    mailbox_owner=OWNER, **stores)


def test_writing_to_a_sender_brings_their_archived_mail_back(pg):
    engine, stores, org = pg
    unsub = {"List-Unsubscribe": "<mailto:u@esp.test>"}
    _sync(stores, org, [
        _mail("inv1", INVESTOR, headers=unsub),                         # archived N-02
        _mail("spam1", INVESTOR, minutes=1, labels=("SPAM",)),          # archived N-09, FINAL
        _mail("other1", "news@else.test", minutes=2, headers=unsub),    # archived, never written to
    ])
    assert _row(engine, org, "inv1") == ("archived", "N-02")

    summary = _sync(stores, org, [_mail("out1", OWNER, minutes=60, recipients=[INVESTOR])])

    assert _row(engine, org, "out1")[0] == "emitted"
    assert summary.promoted_on_reply == 1
    assert _row(engine, org, "inv1") == ("emitted", "promoted:N-02"), "the investor's note is back"
    assert _row(engine, org, "spam1") == ("archived", "N-09"), "a FINAL rule is never undone"
    assert _row(engine, org, "other1")[0] == "archived", "nobody wrote to this sender"


def test_mail_from_someone_else_rescues_nothing(pg):
    engine, stores, org = pg
    _sync(stores, org, [_mail("inv2", INVESTOR, headers={"List-Unsubscribe": "<mailto:u@e.t>"})])
    summary = _sync(stores, org, [_mail("in2", "colleague@acme.test", minutes=5,
                                        recipients=[INVESTOR])])
    assert summary.promoted_on_reply == 0, "only the mailbox owner's own outbound mail rescues"
    assert _row(engine, org, "inv2")[0] == "archived"
