"""STEP-05 · the health check that every kept event entered memory — on real rows, split by cause.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… pytest tests/scripts/test_pipeline_health_memory.py -q

`scripts/pipeline_health.check_every_kept_event_entered_memory` (tree
`yc2_w27_s05 · M23.C6.L-interface.V3.U02`). Memory held ~27 of the design partner's 395 mails and 2 of
its 34 meetings. The check's population is the receipt's — kept events a day old with no settled L2 run
(`platform/receipts` "every kept event has entered memory") — split by what holds each one, so a failure
names its lever; every calendar event must be a meeting; and the re-read ladder's backlog is measured.

Read-only, like every check in the script: the connection it is handed is rolled back here.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine, text

pytestmark = pytest.mark.pg
ORG = "health_memory_org"


def _module():
    import importlib
    return importlib.import_module("scripts.pipeline_health")


@pytest.fixture
def conn():
    url = os.environ.get("GENIOS_TEST_DATABASE_URL")
    if not url:
        pytest.skip("needs GENIOS_TEST_DATABASE_URL pointing at a scratch database")
    engine = create_engine(url)
    with engine.begin() as c:
        c.execute(text("delete from orgs where id = :o"), {"o": ORG})
        c.execute(text("insert into orgs (id, name, email) values (:o, :o, 'hm@example.test')"),
                  {"o": ORG})
    with engine.connect() as c:
        yield c
        c.rollback()
    with engine.begin() as c:
        c.execute(text("delete from orgs where id = :o"), {"o": ORG})


def _event(c, key: str, *, outcome: str = "emitted", source: str = "gmail",
           object_type: str = "email_message", run: str | None = None,
           park: tuple[str, str] | None = None, extracted: bool = False,
           age: timedelta = timedelta(days=2)) -> None:
    at = datetime.now(timezone.utc) - age
    event_id = f"evt_{key}"
    c.execute(text(
        "insert into source_events (event_id, org_id, connection_id, source, object_type, "
        "source_object_id, dedup_key, actor, occurred_at, captured_at, outcome) values "
        "(:e, :o, 'conn_x', :s, :t, :k, :d, cast(:a as jsonb), :at, :at, :out)"),
        {"e": event_id, "o": ORG, "s": source, "t": object_type, "k": key,
         "d": f"{source}:{object_type}:{key}", "a": json.dumps({"email": "x@y.test"}), "at": at,
         "out": outcome})
    if run:
        c.execute(text("insert into l2_processing_runs (org_id, event_id, status, attempts) "
                       "values (:o, :e, :st, 1)"), {"o": ORG, "e": event_id, "st": run})
    if park:
        c.execute(text("insert into parked_events (event_id, org_id, source, reason_code, status) "
                       "values (:e, :o, :s, :r, :st)"),
                  {"e": event_id, "o": ORG, "s": source, "r": park[0], "st": park[1]})
    if extracted:
        c.execute(text("insert into l1_extraction_results (processing_key, org_id, event_id, "
                       "output, profile_id) values (:k, :o, :e, cast('{}' as jsonb), 'email')"),
                  {"k": f"x_{event_id}", "o": ORG, "e": event_id})


def _meeting(c, key: str) -> None:
    c.execute(text("insert into graph_nodes (node_id, org_id, node_type, canonical_key) "
                   "values (:n, :o, 'meeting', :k)"), {"n": f"n_{key}", "o": ORG, "k": f"gcal:{key}"})


def _check(c):
    return _module().check_every_kept_event_entered_memory(c, ORG)


def test_a_tenant_whose_kept_events_are_all_in_memory_passes(conn):
    _event(conn, "m1", run="done")
    _event(conn, "a1", outcome="archived", run="done")
    _event(conn, "cal1", source="gcal", object_type="calendar_event", run="done")
    _meeting(conn, "cal1")
    _event(conn, "fresh", age=timedelta(hours=2))                     # the drain's turn still
    _event(conn, "screen", source="screen_session", object_type="screen_chat_thread")  # D22
    _event(conn, "q1", park=("extraction_never_ran", "pending"), run="done")
    check = _check(conn)
    assert check.ok, check
    assert "1 kept mail(s) waiting for their re-read" in check.measured


def test_each_cause_is_named_and_the_count_is_the_receipts(conn):
    from genios_engine.platform.receipts import receipts

    _event(conn, "drain_lag", extracted=True)                         # a road, never taken
    _event(conn, "held", run="held")
    _event(conn, "queued", park=("extraction_never_ran", "pending"))
    _event(conn, "given_up", park=("extraction_parse_failed", "dead_letter"))
    _event(conn, "orphan")                                            # unread, in no ladder
    check = _check(conn)
    assert not check.ok
    assert sorted(check.detail) == sorted([
        "never taken by the drain: 1", "its L2 run is held: 1", "waiting for its re-read: 1",
        "given up by the re-read ladder: 1", "never read, and not in the ladder: 1"])
    receipt = next(r for r in receipts(ORG) if r.claim == "every kept event has entered memory")
    assert int(conn.execute(text(receipt.sql), {"org": ORG}).scalar()) == 5, (
        "the check and the receipt count different populations")


def test_a_calendar_event_with_no_meeting_fails_it(conn):
    _event(conn, "cal2", source="gcal", object_type="calendar_event", run="done")
    check = _check(conn)
    assert not check.ok and "1 calendar event(s) with no meeting" in check.measured
    _meeting(conn, "cal2")
    assert _check(conn).ok
