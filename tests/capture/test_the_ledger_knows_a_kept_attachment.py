"""STEP-08 · the ledger answers one more question: has an attachment of this message landed KEPT?

    pytest tests/capture/test_the_ledger_knows_a_kept_attachment.py -q                       # memory
    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… pytest tests/capture/test_the_ledger_knows_a_kept_attachment.py -q

Both source-event repositories (tree `yc2_w27_s08 · M26.C2.L-data.V0.U01`, minted building C2). Gmail
hands out a fresh `attachmentId` on every read, so a re-read attachment never carries its old key, and
the re-read check (`capture/landing/reread`) asked whether the PARENT message's key exists. STEP-08
frees a deleted message's key, and an attachment that survived its deleted message would then land a
second time. So the ledger is asked whether an attachment of the message landed KEPT — emitted, parked
or archived. Never a dropped one: that was deleted with its message, and is what the re-sync is for.
The in-memory twin answers exactly as Postgres does, so a test on it fails where production would.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest

from genios_engine.capture.connectors.base import RawObject
from genios_engine.capture.landing.normalize import to_source_event
from genios_engine.capture.landing.repository import InMemorySourceEventRepository

NOW = datetime(2026, 10, 7, 12, tzinfo=timezone.utc)


def _attachment(org: str, message: str, n: int, *, source: str = "gmail",
                object_type: str = "email_attachment"):
    return to_source_event(RawObject(source=source, object_type=object_type,
                                     source_object_id=f"{message}::att{n}-{uuid.uuid4().hex[:6]}",
                                     parent_object_id=message,
                                     occurred_at=NOW - timedelta(days=3)),
                           org_id=org, connection_id="con_x")


def _message(org: str, message: str):
    return to_source_event(RawObject(source="gmail", object_type="email_message",
                                     source_object_id=message, parent_object_id="thread-1",
                                     occurred_at=NOW - timedelta(days=3)),
                           org_id=org, connection_id="con_x")


def _memory(_url):
    return InMemorySourceEventRepository(), None


def _postgres(url):
    if not url:
        pytest.skip("GENIOS_TEST_DATABASE_URL not set — needs real Postgres")
    from genios_engine.capture.landing.pg_repository import PostgresSourceEventRepository
    return PostgresSourceEventRepository(url), url


@pytest.fixture(params=[_memory, pytest.param(_postgres, marks=pytest.mark.pg)],
                ids=["memory", "postgres"])
def ledger(request, live_db_url):
    repo, url = request.param(live_db_url)
    org = f"org_kept_att_{uuid.uuid4().hex[:8]}"
    if url:
        from sqlalchemy import create_engine, text
        engine = create_engine(url)
        with engine.begin() as c:
            c.execute(text("insert into orgs (id, name) values (:o, 'kept attachment')"), {"o": org})
    yield repo, org
    if url:
        with engine.begin() as c:
            c.execute(text("delete from source_events where org_id = :o"), {"o": org})
            c.execute(text("delete from orgs where id = :o"), {"o": org})


@pytest.mark.parametrize("outcome", ["emitted", "parked", "archived"])
def test_an_attachment_that_landed_kept_is_known(ledger, outcome):
    repo, org = ledger
    repo.add(_attachment(org, "m1", 1), outcome=outcome)
    assert repo.kept_child_exists(org, "gmail", "email_attachment", "m1")


@pytest.mark.parametrize("outcome", ["dropped", "superseded"])
def test_an_attachment_deleted_with_its_message_or_set_aside_is_not(ledger, outcome):
    repo, org = ledger
    repo.add(_attachment(org, "m1", 1), outcome=outcome)
    assert not repo.kept_child_exists(org, "gmail", "email_attachment", "m1")


def test_it_asks_about_this_message_this_source_and_this_tenant_only(ledger):
    repo, org = ledger
    repo.add(_attachment(org, "m1", 1), outcome="emitted")
    repo.add(_attachment(org, "m2", 1, source="outlook"), outcome="emitted")
    repo.add(_message(org, "m3"), outcome="emitted")             # a message is not an attachment
    assert not repo.kept_child_exists(org, "gmail", "email_attachment", "m2")
    assert not repo.kept_child_exists(org, "gmail", "email_attachment", "m9")
    assert not repo.kept_child_exists(org, "gmail", "email_attachment", "thread-1")
    assert not repo.kept_child_exists(f"{org}_other", "gmail", "email_attachment", "m1")
    assert repo.kept_child_exists(org, "gmail", "email_attachment", "m1")


def test_the_protocol_names_the_question():
    from genios_engine.capture.landing.repository import SourceEventRepository
    assert "kept_child_exists" in SourceEventRepository.__dict__
