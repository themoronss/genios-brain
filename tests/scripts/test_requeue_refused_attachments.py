"""STEP-18 B19 · the attachments the file_name refusal dead-lettered go back on the ladder — only those.

    pytest tests/scripts/test_requeue_refused_attachments.py -q
    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… pytest … -q          # + the behavioural half

After the connector sends `file_name` (yc2_w27/M17.C3.U02) the 50 attachment parks the old refusal
dead-lettered on the design partner's org will not retry on their own: a dead letter is terminal.
This script puts back exactly those — the refusal is named in the stored error — and nothing else.
"""
from __future__ import annotations

import ast
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "requeue_refused_attachments.py"
REFUSAL = ("RuntimeError: gmail attachment fetch failed for m1::a1: Invalid request data provided "
           "- Value error, Missing required fields: file_name. To get an attachment: …")


def _module():
    import importlib.util
    spec = importlib.util.spec_from_file_location("requeue_refused_attachments", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_the_target_is_resolved_through_the_guard_with_no_fallback():
    tree = ast.parse(SCRIPT.read_text(encoding="utf-8"))
    called = {getattr(n.func, "id", None) for n in ast.walk(tree) if isinstance(n, ast.Call)}
    assert "resolve_database_url" in called, "the target must go through scripts/_db"
    assert "get_settings" not in called, "a script must never fall back to the app's database"


def test_the_org_is_required():
    mod = _module()
    with pytest.raises(SystemExit):
        mod.parse_args([])


def test_the_selection_names_the_refusal_the_status_and_the_tenant():
    mod = _module()
    sql = " ".join(mod.SELECT.split()).lower()
    for part in ("status = 'dead_letter'", "org_id = :org", "source = 'gmail'",
                 "reason_code like 'doc-%'", "refetch_last_error like :refusal"):
        assert part in sql, f"the selection does not say {part!r}: {sql}"
    assert mod.REFUSAL_MARK in REFUSAL


@pytest.mark.pg
@pytest.mark.skipif(not os.environ.get("GENIOS_TEST_DATABASE_URL"),
                    reason="needs GENIOS_TEST_DATABASE_URL pointing at a scratch database")
def test_only_the_refused_dead_letters_of_one_tenant_go_back_on_the_ladder():
    from sqlalchemy import text

    from genios_engine.platform.db import get_engine

    mod = _module()
    engine = get_engine(os.environ["GENIOS_TEST_DATABASE_URL"])
    org, other = (f"org_rq_{uuid.uuid4().hex[:8]}" for _ in range(2))
    at = datetime(2026, 10, 3, 10, 14, tzinfo=timezone.utc)
    rows = {  # event id: (org, status, error)
        "evt_refused": (org, "dead_letter", REFUSAL),
        "evt_other_reason": (org, "dead_letter", "RuntimeError: 404 message not found"),
        "evt_still_pending": (org, "pending", REFUSAL),
        "evt_other_tenant": (other, "dead_letter", REFUSAL),
    }
    with engine.begin() as c:
        for o in (org, other):
            c.execute(text("insert into orgs (id, name) values (:o, 'requeue test')"), {"o": o})
        for e, (o, status, error) in rows.items():
            c.execute(text(
                "insert into parked_events (event_id, org_id, source, reason_code, stage, trace, "
                " status, created_at, refetch_attempts, refetch_last_error, refetch_failure_kind) "
                "values (:e, :o, 'gmail', 'DOC-05', 'S1', cast('{}' as jsonb), :s, :at, 5, :err, "
                " 'transient')"), {"e": e, "o": o, "s": status, "at": at, "err": error})
    try:
        assert mod.requeue(engine, org, apply=False) == 1      # the dry run writes nothing
        with engine.connect() as c:
            assert c.execute(text("select status from parked_events where event_id = 'evt_refused'")
                             ).scalar() == "dead_letter"
        assert mod.requeue(engine, org, apply=True) == 1
        with engine.connect() as c:
            got = dict(c.execute(text(
                "select event_id, status from parked_events where event_id = any(:e)"),
                {"e": list(rows)}).fetchall())
            attempts, nxt, error = c.execute(text(
                "select refetch_attempts, refetch_next_attempt_at, refetch_last_error "
                "from parked_events where event_id = 'evt_refused'")).one()
        assert got == {"evt_refused": "pending", "evt_other_reason": "dead_letter",
                       "evt_still_pending": "pending", "evt_other_tenant": "dead_letter"}, got
        assert attempts == 0 and nxt is not None
        assert "requeued" in error and "file_name" in error, "the history of why must stay"
    finally:
        with engine.begin() as c:
            c.execute(text("delete from parked_events where event_id = any(:e)"), {"e": list(rows)})
            c.execute(text("delete from orgs where id in (:a, :b)"), {"a": org, "b": other})
