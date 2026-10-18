"""STEP-18 B18 · a mail whose extraction parked is read again — bounded, and never silently.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… pytest tests/capture/test_a_failed_extraction_is_read_again_pg.py -q

⛔ WHAT WAS WRONG. The extractor parks a message whose model answer cannot be used, and no drain
claimed its four park codes: on the design partner's org two mails waited at `pending` from 3 Oct
with zero attempts and no next attempt, and the funnel probe counted them as *kept unread*. The
event is already `emitted`, so the parked drain's own recovery — flipping `outcome` — would change
nothing. They are read again through the unread re-read's door, under a ladder that follows the
MESSAGE: a re-land mints a new event, and a second parse failure is a second park row for it.
"""
from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import text

from genios_engine.capture.landing import unread
from genios_engine.contracts.source_event import compute_dedup_key
from genios_engine.platform.crypto import encrypt

URL = os.environ.get("GENIOS_TEST_DATABASE_URL")
pytestmark = [pytest.mark.pg,
              pytest.mark.skipif(not URL, reason="GENIOS_TEST_DATABASE_URL not set")]

NOW = datetime(2026, 10, 5, 12, tzinfo=timezone.utc)


@pytest.fixture
def engine():
    from genios_engine.platform.db import get_engine
    return get_engine(URL)


@pytest.fixture
def org(engine):
    from genios_engine.platform.config import get_settings
    org_id = f"org_parked_x_{uuid.uuid4().hex[:8]}"
    with engine.begin() as c:
        c.execute(text("insert into orgs (id, name) values (:o, 'parked extraction test')"),
                  {"o": org_id})
    yield org_id, get_settings().crypto_key
    with engine.begin() as c:
        for table in ("parked_events", "l1_extraction_results", "raw_payloads", "source_events"):
            c.execute(text(f"delete from {table} where org_id = :o"), {"o": org_id})
        c.execute(text("delete from orgs where id = :o"), {"o": org_id})


def _parked_mail(engine, org_id, key, mid, *, parked_at, reason="extraction_parse_failed",
                 outcome="emitted", dedup_key=None):
    event_id = f"evt_{uuid.uuid4().hex[:12]}"
    with engine.begin() as c:
        c.execute(text(
            "insert into source_events (event_id, org_id, connection_id, source, object_type, "
            " source_object_id, dedup_key, actor, occurred_at, captured_at, sync_mode, "
            " payload_ref, recipients, outcome) "
            "values (:e, :o, 'con_x', 'gmail', 'email_message', :mid, :dk, cast(:actor as jsonb), "
            " :occ, :cap, 'push', :pay, :rcp, :out)"),
            {"e": event_id, "o": org_id, "mid": mid,
             "dk": dedup_key or compute_dedup_key("gmail", "email_message", mid, None),
             "actor": json.dumps({"type": "external_contact", "email": "a@x.com", "name": "Ann"}),
             "occ": parked_at - timedelta(minutes=5), "cap": parked_at, "pay": f"pay_{event_id}",
             "rcp": ["me@co.com"], "out": outcome})
        c.execute(text(
            "insert into raw_payloads (id, org_id, event_id, content_type, enc_content, expires_at) "
            "values (:id, :o, :e, 'application/json', :enc, :exp)"),
            {"id": f"pay_{event_id}", "o": org_id, "e": event_id,
             "enc": encrypt(json.dumps({"subject": "Phase-1 review", "body": "Due Friday"}), key),
             "exp": NOW + timedelta(days=30)})
        c.execute(text(
            "insert into parked_events (event_id, org_id, source, reason_code, stage, trace, "
            " status, created_at) values (:e, :o, 'gmail', :r, 's2_semantic_extraction', "
            " cast('{}' as jsonb), 'pending', :at)"),
            {"e": event_id, "o": org_id, "r": reason, "at": parked_at})
    return event_id


def test_a_parked_extraction_is_due_after_its_wait_and_not_before(engine, org):
    org_id, key = org
    fresh = _parked_mail(engine, org_id, key, "m_fresh", parked_at=NOW - timedelta(minutes=10))
    due = _parked_mail(engine, org_id, key, "m_due", parked_at=NOW - timedelta(hours=2))
    found = {r.event_id for r in unread.find_parked_extractions(engine, org_id, now=NOW)}
    assert due in found and fresh not in found, found


def test_an_extraction_that_landed_since_is_not_read_again(engine, org):
    org_id, key = org
    e = _parked_mail(engine, org_id, key, "m_landed", parked_at=NOW - timedelta(hours=2))
    with engine.begin() as c:
        cols = {r[0] for r in c.execute(text(
            "select column_name from information_schema.columns "
            "where table_name = 'l1_extraction_results'"))}
        vals = {"org_id": org_id, "event_id": e}
        reqd = c.execute(text(
            "select column_name, data_type from information_schema.columns where "
            "table_name='l1_extraction_results' and is_nullable='NO' and column_default is null"))
        for r in reqd:
            if r.column_name not in vals:
                vals[r.column_name] = (NOW if "time" in r.data_type or "date" in r.data_type
                                       else 0 if "int" in r.data_type or "numeric" in r.data_type
                                       else "{}" if "json" in r.data_type else "x")
        assert {"org_id", "event_id"} <= cols
        c.execute(text(f"insert into l1_extraction_results ({','.join(vals)}) values "
                       f"({','.join(':' + k for k in vals)})"), vals)
    assert not unread.find_parked_extractions(engine, org_id, now=NOW)


def test_a_relanded_copy_settles_the_old_park_and_a_restored_one_advances_its_ladder(engine, org):
    org_id, key = org
    replaced = _parked_mail(engine, org_id, key, "m_replaced", parked_at=NOW - timedelta(hours=2))
    came_back = _parked_mail(engine, org_id, key, "m_back", parked_at=NOW - timedelta(hours=2))
    unread.set_aside(engine, org_id, [replaced, came_back])
    # only m_replaced lands again: its original key is now taken by the new copy
    _parked_mail(engine, org_id, key, "m_replaced", parked_at=NOW, reason="x_not_a_park",
                 dedup_key=compute_dedup_key("gmail", "email_message", "m_replaced", None))
    unread.restore(engine, org_id, [replaced, came_back])
    out = unread.settle_parked_extractions(engine, org_id, [replaced, came_back], now=NOW)
    assert out == {"superseded": 1, "advanced": 1}, out
    with engine.connect() as c:
        status = dict(c.execute(text(
            "select event_id, status from parked_events where org_id = :o and event_id in (:a, :b)"),
            {"o": org_id, "a": replaced, "b": came_back}).fetchall())
        attempts, nxt = c.execute(text(
            "select refetch_attempts, refetch_next_attempt_at from parked_events "
            "where event_id = :e"), {"e": came_back}).one()
    assert status == {replaced: "superseded", came_back: "pending"}
    assert attempts == 1 and nxt > NOW
    assert came_back not in {r.event_id for r in
                             unread.find_parked_extractions(engine, org_id, now=NOW)}, (
        "the restored row was offered again before its wait")


def test_a_message_that_keeps_failing_is_given_up_with_its_reason(engine, org):
    org_id, key = org
    mid = "m_hopeless"
    for i in range(3):                                   # three earlier copies, each parked
        old = _parked_mail(engine, org_id, key, mid, parked_at=NOW - timedelta(hours=20 - i),
                           outcome="superseded", dedup_key=f"gmail:old:{mid}:{i}")
        with engine.begin() as c:
            c.execute(text("update parked_events set status = 'superseded' where event_id = :e"),
                      {"e": old})
    last = _parked_mail(engine, org_id, key, mid, parked_at=NOW - timedelta(hours=12))
    assert last not in {r.event_id for r in unread.find_parked_extractions(engine, org_id, now=NOW)}
    assert unread.give_up_parked_extractions(engine, org_id, now=NOW) == 1
    with engine.connect() as c:
        status, why = c.execute(text(
            "select status, refetch_last_error from parked_events where event_id = :e"),
            {"e": last}).one()
    assert status == "dead_letter" and "given up" in why, (status, why)
