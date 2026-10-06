"""STEP-03 · the health check that the gate deletes nothing — on real rows.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… pytest tests/scripts/test_pipeline_health_no_mail_deleted.py -q

`scripts/pipeline_health.check_nothing_was_deleted_at_the_gate` (tree
`yc2_w27_s03/M21.C6.L-interface.V5.U01`). Before STEP-03, 258 of the design partner's 395 mails were
deleted at the first gate with their content gone. After it, the gate ARCHIVES what a noise rule or
the AI filter calls noise, and the only drop left is S0's scope exclusion (`out_of_scope`). So the
production number the step promises — "new mail with its content deleted at the gate → 0" — is a
check: any object captured since the archiving gate started (and in the last 24 hours) with outcome
`dropped` and no scope exclusion in its trace FAILS it, and names the codes that dropped it.

Read-only, like every check in the script: the connection it is handed is rolled back here.
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine, text

pytestmark = pytest.mark.pg
ORG = "health_no_delete_org"


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
        c.execute(text("delete from event_trace where org_id = :o"), {"o": ORG})
        c.execute(text("delete from orgs where id = :o"), {"o": ORG})
        c.execute(text("insert into orgs (id, name, email) values (:o, :o, 'hn@example.test')"),
                  {"o": ORG})
    with engine.connect() as c:
        yield c
        c.rollback()
    with engine.begin() as c:
        c.execute(text("delete from event_trace where org_id = :o"), {"o": ORG})
        c.execute(text("delete from orgs where id = :o"), {"o": ORG})


def _event(c, key: str, outcome: str, *, code: str | None, stage: str = "S1",
           age: timedelta = timedelta(hours=1)) -> None:
    at = datetime.now(timezone.utc) - age
    c.execute(text(
        "insert into source_events (event_id, org_id, connection_id, source, object_type, "
        "source_object_id, dedup_key, actor, occurred_at, captured_at, outcome) values "
        "(:e, :o, 'conn_gmail', 'gmail', 'email_message', :k, :d, cast('{}' as jsonb), :t, :t, "
        ":out)"), {"e": f"evt_{key}", "o": ORG, "k": key, "d": f"gmail:email_message:{key}",
                   "t": at, "out": outcome})
    if code:
        action = {"dropped": "drop", "archived": "archive"}.get(outcome, "pass")
        c.execute(text("insert into event_trace (org_id, event_id, stage, action, reason_code) "
                       "values (:o, :e, :s, :a, :r)"),
                  {"o": ORG, "e": f"evt_{key}", "s": stage, "a": action, "r": code})


def _check(c):
    return _module().check_nothing_was_deleted_at_the_gate(c, ORG)


def test_a_tenant_that_archives_and_deletes_nothing_passes(conn):
    _event(conn, "a1", "archived", code="N-02")
    _event(conn, "e1", "emitted", code=None)
    check = _check(conn)
    assert check.ok and "0 " in check.measured


def test_one_mail_dropped_by_a_rule_fails_and_names_the_rule(conn):
    _event(conn, "a1", "archived", code="N-02", age=timedelta(hours=3))
    _event(conn, "d1", "dropped", code="N-06")
    check = _check(conn)
    assert not check.ok
    assert "1 " in check.measured and any("N-06" in line for line in check.detail)


def test_a_scope_exclusion_is_not_a_deletion(conn):
    _event(conn, "a1", "archived", code="N-02", age=timedelta(hours=3))
    _event(conn, "s1", "dropped", code="out_of_scope", stage="S0")
    assert _check(conn).ok


def test_a_drop_from_before_the_archiving_gate_is_history_not_a_failure(conn):
    """The deploy day: mail the OLD gate dropped this morning is not this gate's deletion."""
    _event(conn, "old", "dropped", code="N-02", age=timedelta(hours=10))
    _event(conn, "a1", "archived", code="N-02", age=timedelta(hours=2))
    assert _check(conn).ok


def test_drops_with_no_archive_ever_fail_the_gate_is_still_the_old_one(conn):
    """Nothing archived and mail still dropped in the last day: STEP-03 is not running here."""
    _event(conn, "d1", "dropped", code="N-02", age=timedelta(hours=5))
    check = _check(conn)
    assert not check.ok and "deployed" in check.fix


def test_a_drop_older_than_a_day_is_outside_the_window(conn):
    _event(conn, "d1", "dropped", code="N-02", age=timedelta(days=2))
    assert _check(conn).ok


def test_the_check_runs_with_the_others():
    assert _module().check_nothing_was_deleted_at_the_gate in _module().CHECKS
