"""STEP-08's reach, measured · how far back memory goes, against the window Rohit named.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… pytest tests/scripts/test_pipeline_health_reach.py -q

`yc2_w27_align` M34.C2.L-interface.V1.U04. STEP-08's 365 days (`06` D16, `09` G3) was a
recommendation, not a check: the health check passed at 60 days, because it asks only that every mail
INSIDE the connection's window has its content — it never asked how far back memory goes. This one
does: the oldest Gmail mail in memory against the start of the connection's window, failing while
memory stops short of it, with the mail per month beside it so a gap is a month you can see. Read-only,
like every check: the connection is rolled back here.
"""
from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import text

pytestmark = pytest.mark.pg
NOW = datetime(2026, 10, 7, 12, tzinfo=timezone.utc)


def _module():
    import importlib
    return importlib.import_module("scripts.pipeline_health")


@pytest.fixture
def mailbox():
    url = os.environ.get("GENIOS_TEST_DATABASE_URL")
    if not url:
        pytest.skip("needs GENIOS_TEST_DATABASE_URL pointing at a scratch database")
    from genios_engine.platform.db import get_engine
    engine = get_engine(url)
    org = f"org_health_reach_{uuid.uuid4().hex[:8]}"
    with engine.begin() as c:
        c.execute(text("insert into orgs (id, name) values (:o, 'health reach')"), {"o": org})
        c.execute(text(
            "insert into connections (connection_id, org_id, source_type, status, capture_scope) "
            "values (:c, :o, 'gmail', 'connected', cast('{\"backfill_days\": 365}' as jsonb))"),
            {"c": f"con_{org}", "o": org})
    yield engine, org
    with engine.begin() as c:
        for table in ("source_events", "connections"):
            c.execute(text(f"delete from {table} where org_id = :o"), {"o": org})
        c.execute(text("delete from orgs where id = :o"), {"o": org})


def _mail(engine, org, *, days: float, outcome: str = "emitted", source: str = "gmail") -> None:
    from genios_engine.contracts.source_event import compute_dedup_key
    mid = uuid.uuid4().hex[:10]
    with engine.begin() as c:
        c.execute(text(
            "insert into source_events (event_id, org_id, connection_id, source, object_type, "
            " source_object_id, dedup_key, actor, occurred_at, captured_at, outcome) values "
            " (:e, :o, 'con_x', :src, 'email_message', :mid, :dk, cast(:actor as jsonb), :at, :at, :out)"),
            {"e": f"evt_{mid}", "o": org, "src": source, "mid": mid,
             "dk": compute_dedup_key(source, "email_message", mid),
             "actor": json.dumps({"email": "someone@fund.test"}), "at": NOW - timedelta(days=days),
             "out": outcome})


def _check(engine, org):
    with engine.connect() as c:
        try:
            return _module().check_memory_reaches_the_window(c, org, now=NOW)
        finally:
            c.rollback()


def test_memory_that_stops_at_a_hundred_days_fails_a_year_window(mailbox):
    engine, org = mailbox
    for days in (10, 40, 100):
        _mail(engine, org, days=days)
    check = _check(engine, org)
    assert not check.ok
    assert "365-day window" in check.measured and "265 days short" in check.measured, check.measured
    assert any(line.startswith("mail per month:") for line in check.detail), check.detail


def test_memory_that_reaches_the_window_passes(mailbox):
    engine, org = mailbox
    for days in (10, 200, 358):
        _mail(engine, org, days=days)
    check = _check(engine, org)
    assert check.ok, check.measured


def test_only_kept_gmail_mail_counts_as_memory(mailbox):
    """A deleted ledger row (STEP-03's past) and another source's object are not Gmail memory."""
    engine, org = mailbox
    _mail(engine, org, days=10)
    _mail(engine, org, days=360, outcome="dropped")
    _mail(engine, org, days=360, source="gcal")
    assert not _check(engine, org).ok
    _mail(engine, org, days=360, outcome="archived")      # kept, with its content (STEP-03)
    assert _check(engine, org).ok


def test_a_mailbox_with_no_mail_in_memory_fails_and_says_so(mailbox):
    engine, org = mailbox
    check = _check(engine, org)
    assert not check.ok and "no Gmail mail in memory" in check.measured


def test_the_check_runs_with_the_others():
    assert _module().check_memory_reaches_the_window in _module().CHECKS
