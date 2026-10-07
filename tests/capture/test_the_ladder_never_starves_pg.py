"""STEP-06 · the re-read ladder takes the rows that are due — 200 waiting rows can no longer hide them.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… pytest tests/capture/test_the_ladder_never_starves_pg.py -q

Tree `yc2_w27_s06 · M24.C5.L-data.V1.U02` (`speedrun008/YC-II W27/` 03 F74). `find_parked_extractions`
took the NEWEST `limit` pending extraction parks and only then dropped, in Python, the ones not yet
due. 200 newer rows waiting out their backoff — a model outage parks a burst of them — hid every older
row that was due: the ladder read nothing until the burst came due. The due test now runs in the SQL,
so the limit counts only rows that are due; the Python check stays as a second reading of the same
rule, and the two are held equal here.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from cryptography.fernet import Fernet
from sqlalchemy import text

from genios_engine.capture.landing import unread
from genios_engine.contracts.source_event import compute_dedup_key
from genios_engine.platform.crypto import encrypt

KEY = Fernet.generate_key().decode()
NOW = datetime.now(timezone.utc)


@pytest.fixture
def engine(live_db_url):
    if not live_db_url:
        pytest.skip("GENIOS_TEST_DATABASE_URL not set — needs real Postgres")
    from genios_engine.platform.db import get_engine
    return get_engine(live_db_url)


@pytest.fixture
def org(engine):
    org_id = f"org_l{uuid.uuid4().hex[:12]}"
    with engine.begin() as c:
        c.execute(text("insert into orgs (id, name) values (:o, 'ladder test')"), {"o": org_id})
    yield org_id
    with engine.begin() as c:
        for table in ("parked_events", "raw_payloads", "source_events"):
            c.execute(text(f"delete from {table} where org_id = :o"), {"o": org_id})
        c.execute(text("delete from orgs where id = :o"), {"o": org_id})


def _parked_mail(c, org_id, *, occurred, parked, attempts=0, next_attempt=None,
                 code="extraction_call_failed"):
    event_id = f"evt_{uuid.uuid4().hex[:12]}"
    mid = f"m_{event_id}"
    c.execute(text(
        "insert into source_events (event_id, org_id, connection_id, source, object_type, "
        " source_object_id, dedup_key, actor, occurred_at, captured_at, sync_mode, payload_ref, "
        " recipients, outcome) values (:e, :o, 'con_x', 'gmail', 'email_message', :mid, :dk, "
        " cast(:actor as jsonb), :occ, :occ, 'backfill', :pay, :rcp, 'emitted')"),
        {"e": event_id, "o": org_id, "mid": mid,
         "dk": compute_dedup_key("gmail", "email_message", mid, None),
         "actor": json.dumps({"type": "external_contact", "email": "a@x.com", "name": "Ann"}),
         "occ": occurred, "pay": f"pay_{event_id}", "rcp": ["me@co.com"]})
    c.execute(text(
        "insert into raw_payloads (id, org_id, event_id, content_type, enc_content, expires_at) "
        "values (:id, :o, :e, 'application/json', :enc, :exp)"),
        {"id": f"pay_{event_id}", "o": org_id, "e": event_id,
         "enc": encrypt(json.dumps({"subject": "Hi", "body": "b"}), KEY),
         "exp": NOW + timedelta(days=30)})
    c.execute(text(
        "insert into parked_events (event_id, org_id, source, reason_code, stage, trace, status, "
        " created_at, refetch_attempts, refetch_next_attempt_at) values (:e, :o, 'gmail', :r, "
        " 'extraction', cast('[]' as jsonb), 'pending', :at, :att, :next)"),
        {"e": event_id, "o": org_id, "r": code, "at": parked, "att": attempts,
         "next": next_attempt})
    return event_id


def test_a_due_row_behind_two_hundred_waiting_ones_is_still_read(engine, org):
    with engine.begin() as c:
        due = _parked_mail(c, org, occurred=NOW - timedelta(days=5),
                           parked=NOW - timedelta(days=2), next_attempt=NOW - timedelta(minutes=1))
        for i in range(201):
            _parked_mail(c, org, occurred=NOW - timedelta(minutes=i + 1),
                         parked=NOW - timedelta(minutes=5), next_attempt=NOW + timedelta(hours=2))
    found = unread.find_parked_extractions(engine, org, limit=200, now=NOW)
    assert [r.event_id for r in found] == [due]


@pytest.mark.parametrize("attempts", [0, 1, 2])
def test_the_sql_and_the_python_agree_on_what_is_due(engine, org, attempts):
    """The wait doubles from one hour; a row with no next attempt waits from when it parked. The
    message's own park counts as its first attempt (`find_parked_extractions`)."""
    wait = unread._retry_wait(attempts + 1)
    with engine.begin() as c:
        just_due = _parked_mail(c, org, occurred=NOW - timedelta(days=1),
                                parked=NOW - wait - timedelta(minutes=1), attempts=attempts)
        not_yet = _parked_mail(c, org, occurred=NOW - timedelta(days=1),
                               parked=NOW - wait + timedelta(minutes=1), attempts=attempts)
    found = {r.event_id for r in unread.find_parked_extractions(engine, org, limit=50, now=NOW)}
    assert just_due in found and not_yet not in found


def test_the_ladders_two_reads_share_one_inner_select():
    """`_OVER_THE_LIMIT` (what the ladder gives up on) reads exactly the rows `_FIND_PARKED` now
    leaves out — spelled twice so the SQL resolver reads two whole statements, held identical here."""
    due = str(unread._FIND_PARKED.text).split(") due ")[0]
    spent = str(unread._OVER_THE_LIMIT.text).split(") spent ")[0]
    assert due == spent and due.startswith("select * from (select se.event_id")
