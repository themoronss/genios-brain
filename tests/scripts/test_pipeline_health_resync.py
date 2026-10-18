"""STEP-08 · the health check that every Gmail message in the window has its content, or says why not.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… pytest tests/scripts/test_pipeline_health_resync.py -q

`scripts/pipeline_health.check_every_gmail_message_in_the_window_has_its_content` (tree
`yc2_w27_s08 · M26.C4.L-interface.V1.U02`). Before STEP-03 the gate deleted what it called noise, body
and all: 258 of the design partner's Gmail messages are a ledger row, outcome `dropped`, no content. The
re-sync brings each back or says why not, so the promise is a number — messages inside the Gmail
connection's window with no content and no stated reason: 0. A stated reason is a scope exclusion or
the re-sync's own `resync_not_listed`; a message older than the window is counted, not failed. It is red
until STEP-08 has run, by design. Read-only, like every check: the connection is rolled back here.
"""
from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine, text

pytestmark = pytest.mark.pg
NOW = datetime(2026, 10, 7, 12, tzinfo=timezone.utc)


def _module():
    import importlib
    return importlib.import_module("scripts.pipeline_health")


@pytest.fixture
def ledger():
    url = os.environ.get("GENIOS_TEST_DATABASE_URL")
    if not url:
        pytest.skip("needs GENIOS_TEST_DATABASE_URL pointing at a scratch database")
    from genios_engine.platform.db import get_engine
    engine = get_engine(url)
    org = f"org_health_resync_{uuid.uuid4().hex[:8]}"
    with engine.begin() as c:
        c.execute(text("insert into orgs (id, name) values (:o, 'health resync')"), {"o": org})
        c.execute(text(
            "insert into connections (connection_id, org_id, source_type, status, capture_scope) "
            "values (:c, :o, 'gmail', 'connected', cast('{\"backfill_days\": 60}' as jsonb))"),
            {"c": f"con_{org}", "o": org})
    yield engine, org
    with engine.begin() as c:
        for table in ("event_trace", "raw_payloads", "source_events", "connections"):
            c.execute(text(f"delete from {table} where org_id = :o"), {"o": org})
        c.execute(text("delete from orgs where id = :o"), {"o": org})


def _row(engine, org, mid, *, days=10, outcome="dropped", code="N-02", stage="S1",
         body=False, object_type="email_message", source="gmail") -> str:
    from genios_engine.contracts.source_event import compute_dedup_key
    event_id = f"evt_{uuid.uuid4().hex[:12]}"
    at = NOW - timedelta(days=days)
    with engine.begin() as c:
        c.execute(text(
            "insert into source_events (event_id, org_id, connection_id, source, object_type, "
            " source_object_id, dedup_key, actor, occurred_at, captured_at, outcome) values "
            " (:e, :o, 'con_x', :src, :ot, :mid, :dk, cast(:actor as jsonb), :at, :at, :out)"),
            {"e": event_id, "o": org, "src": source, "ot": object_type, "mid": mid,
             "dk": compute_dedup_key(source, object_type, mid),
             "actor": json.dumps({"email": "hello@boardy.ai"}), "at": at, "out": outcome})
        if code:
            c.execute(text("insert into event_trace (org_id, event_id, stage, action, reason_code) "
                           "values (:o, :e, :s, :a, :r)"),
                      {"o": org, "e": event_id, "s": stage, "r": code,
                       "a": {"dropped": "drop", "archived": "archive"}.get(outcome, "pass")})
        if body:
            c.execute(text("insert into raw_payloads (id, org_id, event_id, content_type, "
                           "enc_content, expires_at) values (:id, :o, :e, 'application/json', "
                           "'x', :exp)"),
                      {"id": f"pay_{event_id}", "o": org, "e": event_id,
                       "exp": NOW + timedelta(days=30)})
    return event_id


def _check(engine, org):
    with engine.connect() as c:
        try:
            return _module().check_every_gmail_message_in_the_window_has_its_content(c, org, now=NOW)
        finally:
            c.rollback()


def test_a_tenant_with_nothing_deleted_passes(ledger):
    engine, org = ledger
    _row(engine, org, "a1", outcome="archived", body=True)
    _row(engine, org, "e1", outcome="emitted", code=None, body=True)
    check = _check(engine, org)
    assert check.ok and check.measured.startswith("0 Gmail message(s) inside the 60-day window")


def test_a_deleted_message_inside_the_window_fails_and_names_the_oldest_and_the_rule(ledger):
    engine, org = ledger
    _row(engine, org, "d1", days=20, code="N-02")
    _row(engine, org, "d2", days=30, code="llm_junk", stage="S2")
    check = _check(engine, org)
    assert not check.ok
    oldest = (NOW - timedelta(days=30)).date().isoformat()
    assert check.measured.startswith("2 Gmail message(s) inside the 60-day window")
    assert f"the oldest {oldest}" in check.measured
    assert any("never freed: 2" in line and "N-02 1" in line and "llm_junk 1" in line
               for line in check.detail), check.detail
    assert "resync_deleted_mail.py" in check.fix


def test_a_message_older_than_the_window_is_counted_not_failed(ledger):
    engine, org = ledger
    _row(engine, org, "old", days=90)
    check = _check(engine, org)
    assert check.ok and "1 more older than the window" in check.measured


def test_what_carries_its_content_or_a_stated_reason_passes(ledger):
    engine, org = ledger
    _row(engine, org, "scope", code="out_of_scope", stage="S0")
    _row(engine, org, "judged", code="llm_junk", stage="S2", body=True)       # kept its body
    _row(engine, org, "att", object_type="email_attachment")                  # not a message
    _row(engine, org, "cal", source="gcal", object_type="calendar_event")     # not Gmail
    _row(engine, org, "ol", source="outlook")                                  # nor this
    assert _check(engine, org).ok


def test_the_resync_turns_it_green_freed_is_not_enough(ledger):
    from genios_engine.capture.landing import resync
    engine, org = ledger
    _row(engine, org, "b1", days=10)
    _row(engine, org, "g1", days=12)
    resync.free_deleted(engine, org, days=60, now=NOW)
    freed = _check(engine, org)
    assert not freed.ok and any("freed, not yet back or finished: 2" in line
                                for line in freed.detail), freed.detail
    assert not any(line.startswith("never freed") for line in freed.detail), freed.detail
    # the drain lands b1 again under its own key; the finish supersedes it and reports g1
    _row(engine, org, "b1", days=10, outcome="archived", body=True)
    resync.finish(engine, org, now=NOW)
    assert _check(engine, org).ok


def test_a_body_past_its_expiry_is_no_content(ledger):
    engine, org = ledger
    event = _row(engine, org, "judged", code="llm_junk", stage="S2", body=True)
    with engine.begin() as c:
        c.execute(text("update raw_payloads set expires_at = :t where event_id = :e"),
                  {"t": NOW - timedelta(days=1), "e": event})
    assert not _check(engine, org).ok


def test_the_window_is_the_connections(ledger):
    engine, org = ledger
    with engine.begin() as c:
        c.execute(text("update connections set capture_scope = '{\"backfill_days\": 365}' "
                       "where org_id = :o"), {"o": org})
    _row(engine, org, "old", days=90)
    check = _check(engine, org)
    assert not check.ok and check.measured.startswith("1 Gmail message(s) inside the 365-day window")


def test_the_check_runs_with_the_others():
    assert _module().check_every_gmail_message_in_the_window_has_its_content in _module().CHECKS
