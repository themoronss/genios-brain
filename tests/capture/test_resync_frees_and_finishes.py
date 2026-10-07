"""STEP-08 · the mail the old gate deleted is freed to land again, and every freed row's end is named.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… pytest tests/capture/test_resync_frees_and_finishes.py -q

`capture/landing/resync` (tree `yc2_w27_s08 · M26.C1.L-data.V0.U01`). Production holds 258 Gmail
messages the gate deleted before STEP-03: a ledger row, outcome `dropped`, no payload. Listed again,
each lands as `duplicate`, because dedup ignores the outcome (`speedrun008/YC-II W27/` STEP-08 §8.1:
15 of 15). `free_deleted` marks the key of each such message inside the window and keeps the row
`dropped` — `superseded` before the new capture lands would let `unread.recover_orphans` forge it
into an emitted row with no content (§8.1, six of six). The backfill drain then lands the message
through today's gate, and `finish` supersedes the old row once the new capture holds its key, or
says why it did not come back.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import text

from genios_engine.capture.landing import resync, unread
from genios_engine.contracts.source_event import compute_dedup_key

pytestmark = pytest.mark.pg

NOW = datetime(2026, 10, 7, 12, tzinfo=timezone.utc)


@pytest.fixture
def engine(live_db_url):
    if not live_db_url:
        pytest.skip("GENIOS_TEST_DATABASE_URL not set — needs real Postgres")
    from genios_engine.platform.db import get_engine
    return get_engine(live_db_url)


def _tenant(engine, *, window: int | None = 60) -> str:
    org = f"org_resync_{uuid.uuid4().hex[:8]}"
    with engine.begin() as c:
        c.execute(text("insert into orgs (id, name) values (:o, 'resync')"), {"o": org})
        if window is not None:
            c.execute(text(
                "insert into connections (connection_id, org_id, source_type, status, capture_scope) "
                "values (:c, :o, 'gmail', 'connected', cast(:scope as jsonb))"),
                {"c": f"con_{org}", "o": org, "scope": json.dumps({"backfill_days": window})})
    return org


def _remove(engine, org: str) -> None:
    with engine.begin() as c:
        for table in ("event_trace", "raw_payloads", "source_events", "connections"):
            c.execute(text(f"delete from {table} where org_id = :o"), {"o": org})
        c.execute(text("delete from orgs where id = :o"), {"o": org})


@pytest.fixture
def org(engine):
    org_id = _tenant(engine)
    yield org_id
    _remove(engine, org_id)


def _row(engine, org: str, mid: str, *, outcome: str = "dropped", day: int = 10,
         source: str = "gmail", object_type: str = "email_message", code: str | None = "N-02",
         stage: str = "S1", payload_expires: datetime | None = None, key: str | None = None) -> str:
    """One ledger row the way the gate wrote it, with the trace row of the stage that stopped it."""
    event_id = f"evt_{uuid.uuid4().hex[:12]}"
    at = NOW - timedelta(days=day)
    with engine.begin() as c:
        c.execute(text(
            "insert into source_events (event_id, org_id, connection_id, source, object_type, "
            " source_object_id, dedup_key, actor, occurred_at, captured_at, outcome) "
            "values (:e, :o, 'con_x', :src, :ot, :mid, :dk, cast(:actor as jsonb), :at, :at, :out)"),
            {"e": event_id, "o": org, "src": source, "ot": object_type, "mid": mid,
             "dk": key or compute_dedup_key(source, object_type, mid, None),
             "actor": json.dumps({"type": "external_contact", "email": "hello@introly.test"}),
             "at": at, "out": outcome})
        if code:
            action = {"dropped": "drop", "archived": "archive"}.get(outcome, "pass")
            c.execute(text("insert into event_trace (org_id, event_id, dedup_key, source, stage, "
                           "action, reason_code) values (:o, :e, :k, :src, :s, :a, :r)"),
                      {"o": org, "e": event_id, "k": compute_dedup_key(source, object_type, mid),
                       "src": source, "s": stage, "a": action, "r": code})
        if payload_expires is not None:
            c.execute(text(
                "insert into raw_payloads (id, org_id, event_id, content_type, enc_content, "
                " expires_at) values (:id, :o, :e, 'application/json', :enc, :exp)"),
                {"id": f"pay_{event_id}", "o": org, "e": event_id, "enc": b"x",
                 "exp": payload_expires})
    return event_id


def _land_again(engine, org: str, mid: str, *, key: str | None = None) -> str:
    """The drain's capture of the same message: a NEW row under the message's own key."""
    return _row(engine, org, mid, outcome="archived", code="N-02",
                payload_expires=NOW + timedelta(days=180), key=key)


def _ledger(engine, org: str, event_id: str):
    with engine.connect() as c:
        return c.execute(text("select outcome, dedup_key from source_events "
                              "where org_id = :o and event_id = :e"),
                         {"o": org, "e": event_id}).one()


def _resync_trace(engine, org: str, event_id: str) -> list:
    with engine.connect() as c:
        return c.execute(text(
            "select action, reason_code, dedup_key, detail from event_trace "
            " where org_id = :o and event_id = :e and stage = 'resync' order by at, id"),
            {"o": org, "e": event_id}).fetchall()


# ── free_deleted ─────────────────────────────────────────────────────────────────────────────────

def test_a_deleted_message_inside_the_window_is_freed_and_stays_dropped(engine, org):
    deleted = _row(engine, org, "m1")
    original = compute_dedup_key("gmail", "email_message", "m1")
    assert resync.free_deleted(engine, org, days=60, now=NOW) == 1
    outcome, key = _ledger(engine, org, deleted)
    assert outcome == "dropped", "superseded before the new capture lands is what recover_orphans forges"
    assert key == f"{original}#resync:{deleted}"
    [trace] = _resync_trace(engine, org, deleted)
    assert (trace.action, trace.reason_code, trace.dedup_key) == ("pass", "resync_freed", original)
    assert trace.detail["window_days"] == 60 and trace.detail["dropped_by"] == "N-02"


def test_only_a_deleted_gmail_message_inside_the_window_is_freed(engine, org):
    deleted = _row(engine, org, "deleted")
    expired = _row(engine, org, "expired", payload_expires=NOW - timedelta(days=1))
    untouched = {
        "kept_its_body": _row(engine, org, "judged", code="llm_junk",
                              payload_expires=NOW + timedelta(days=30)),
        "archived": _row(engine, org, "arch", outcome="archived"),
        "emitted": _row(engine, org, "emit", outcome="emitted", code=None),
        "outside_the_window": _row(engine, org, "old", day=61),
        "an_attachment": _row(engine, org, "m9::att1", object_type="email_attachment"),
        "a_calendar_event": _row(engine, org, "ev1", source="gcal", object_type="calendar_event"),
        "another_mailbox": _row(engine, org, "ol1", source="outlook"),       # STEP-08 is Gmail only
        "a_scope_exclusion": _row(engine, org, "scope", code="out_of_scope", stage="S0"),
    }
    other = _tenant(engine)
    try:
        elsewhere = _row(engine, other, "theirs")
        assert resync.free_deleted(engine, org, days=60, now=NOW) == 2
        assert "#resync:" in _ledger(engine, org, deleted).dedup_key
        assert "#resync:" in _ledger(engine, org, expired).dedup_key, "an expired body is no content"
        for why, event_id in untouched.items():
            assert "#resync:" not in _ledger(engine, org, event_id).dedup_key, why
            assert not _resync_trace(engine, org, event_id), why
        assert "#resync:" not in _ledger(engine, other, elsewhere).dedup_key
    finally:
        _remove(engine, other)


def test_freeing_twice_frees_nothing_more(engine, org):
    deleted = _row(engine, org, "m1")
    assert resync.free_deleted(engine, org, days=60, now=NOW) == 1
    key = _ledger(engine, org, deleted).dedup_key
    assert resync.free_deleted(engine, org, days=60, now=NOW) == 0
    assert _ledger(engine, org, deleted).dedup_key == key
    assert len(_resync_trace(engine, org, deleted)) == 1


def test_a_freed_key_lets_the_landing_door_take_the_message_again(engine, org, live_db_url):
    from genios_engine.capture.connectors.base import RawObject
    from genios_engine.capture.landing.pg_repository import PostgresSourceEventRepository
    from genios_engine.capture.pipeline import land_raw_object

    _row(engine, org, "m1")
    raw = RawObject(source="gmail", object_type="email_message", source_object_id="m1",
                    occurred_at=NOW - timedelta(days=10), actor_email="hello@introly.test",
                    raw={"subject": "Intro", "body": "Pankaj, meet Meera"})
    repo = PostgresSourceEventRepository(live_db_url)
    assert not land_raw_object(raw, org_id=org, connection_id="con_x", repo=repo).landed, (
        "the deleted row's key still blocks the message — a re-listing lands it as a duplicate")
    resync.free_deleted(engine, org, days=60, now=NOW)
    assert land_raw_object(raw, org_id=org, connection_id="con_x", repo=repo).landed


def test_the_orphan_recovery_never_forges_a_freed_row_into_an_emitted_one(engine, org):
    deleted = _row(engine, org, "m1")
    resync.free_deleted(engine, org, days=60, now=NOW)
    assert unread.recover_orphans(engine, org) == 0
    assert _ledger(engine, org, deleted).outcome == "dropped"
    _land_again(engine, org, "m1")
    resync.finish(engine, org, now=NOW)
    key = _ledger(engine, org, deleted).dedup_key
    assert unread.recover_orphans(engine, org) == 0
    assert _ledger(engine, org, deleted) == ("superseded", key)


# ── finish ───────────────────────────────────────────────────────────────────────────────────────

def test_finish_supersedes_a_row_whose_key_a_new_capture_holds_and_names_it(engine, org):
    deleted = _row(engine, org, "m1")
    resync.free_deleted(engine, org, days=60, now=NOW)
    new = _land_again(engine, org, "m1")
    done = resync.finish(engine, org, now=NOW)
    assert (done.superseded, done.not_listed, done.replaced) == (1, 0, ((deleted, new),))
    assert _ledger(engine, org, deleted).outcome == "superseded"
    assert _ledger(engine, org, new) == ("archived", compute_dedup_key("gmail", "email_message", "m1"))
    replaced = _resync_trace(engine, org, deleted)[-1]
    assert (replaced.action, replaced.reason_code) == ("pass", "resync_replaced")
    assert replaced.detail["replaced_by"] == new
    assert not _resync_trace(engine, org, new), "the new capture's own trace is its gate's"


def test_a_freed_message_that_never_came_back_is_reported_once_and_stays_dropped(engine, org):
    deleted = _row(engine, org, "m1")
    resync.free_deleted(engine, org, days=60, now=NOW)
    first = resync.finish(engine, org, now=NOW)
    assert (first.superseded, first.not_listed, first.newly_reported) == (0, 1, 1)
    assert _ledger(engine, org, deleted).outcome == "dropped"
    reported = _resync_trace(engine, org, deleted)[-1]
    assert (reported.action, reported.reason_code) == ("drop", "resync_not_listed")
    assert reported.detail == {"inside_window": True, "window_days": 60}
    second = resync.finish(engine, org, now=NOW)
    assert (second.not_listed, second.newly_reported) == (1, 0)
    assert len(_resync_trace(engine, org, deleted)) == 2, "freed once, reported once"
    # It comes back on a later drain — the key is still free — and the next finish takes it.
    new = _land_again(engine, org, "m1")
    third = resync.finish(engine, org, now=NOW)
    assert (third.superseded, third.not_listed, third.replaced) == (1, 0, ((deleted, new),))


def test_a_message_older_than_the_connections_window_is_reported_as_outside_it(engine):
    org = _tenant(engine, window=30)
    try:
        deleted = _row(engine, org, "m1", day=40)
        assert resync.free_deleted(engine, org, days=60, now=NOW) == 1
        done = resync.finish(engine, org, now=NOW)
        assert (done.not_listed, done.window_days) == (1, 30)
        assert _resync_trace(engine, org, deleted)[-1].detail == {"inside_window": False,
                                                                  "window_days": 30}
    finally:
        _remove(engine, org)


def test_no_gmail_connection_reads_the_default_window(engine):
    from genios_engine.capture.connectors.backfill import DEFAULT_BACKFILL_DAYS

    org = _tenant(engine, window=None)
    try:
        _row(engine, org, "m1")
        resync.free_deleted(engine, org, days=60, now=NOW)
        assert resync.finish(engine, org, now=NOW).window_days == DEFAULT_BACKFILL_DAYS
    finally:
        _remove(engine, org)


def test_a_replacement_the_ladder_has_set_aside_still_counts(engine, org):
    """Mid re-read the new capture's key is set aside (`unread.set_aside`); the message is back."""
    deleted = _row(engine, org, "m1")
    resync.free_deleted(engine, org, days=60, now=NOW)
    original = compute_dedup_key("gmail", "email_message", "m1")
    aside = _land_again(engine, org, "m1", key=f"{original}#superseded:evt_aside")
    done = resync.finish(engine, org, now=NOW)
    assert (done.superseded, done.replaced) == (1, ((deleted, aside),))


def test_finishing_twice_changes_nothing(engine, org):
    deleted = _row(engine, org, "m1")
    resync.free_deleted(engine, org, days=60, now=NOW)
    _land_again(engine, org, "m1")
    assert resync.finish(engine, org, now=NOW).superseded == 1
    again = resync.finish(engine, org, now=NOW)
    assert (again.superseded, again.not_listed, again.replaced) == (0, 0, ())
    assert len(_resync_trace(engine, org, deleted)) == 2


def test_the_set_aside_mark_is_the_ladders():
    """`finish` recognises a replacement the re-read ladder has set aside by the ladder's own mark."""
    assert resync.SET_ASIDE_MARK == unread._MARK
    assert resync.FREED_MARK not in unread._MARK and unread._MARK not in resync.FREED_MARK
