"""STEP-05 · every kept event has entered memory — the receipt that holds the drain to its promise.

    pytest tests/platform/test_every_kept_event_entered_memory.py -q
    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… pytest tests/platform/test_every_kept_event_entered_memory.py -q

`platform/receipts.py` (tree `yc2_w27_s05 · M23.C6.L-logic.V2.U01`). Memory held ~27 of 395 mails and 2
of 34 meetings, and nothing said so: an event no drain ever took leaves no row anywhere a reader looks.
STEP-05 gives every kept event a road; this receipt counts the kept events — emitted or archived — that
have been with us a day and still have no settled L2 run. A screen item is not owed: it enters memory
only on a signal (`06` D22). 0 is the promise; a non-zero count names mail the drain never took, a run
that failed or is held, or a mail still waiting for its re-read.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import text

from genios_engine.platform.receipts import Receipt, receipts

CLAIM = "every kept event has entered memory"
ORG = "org_kept_entered_memory"


def _receipt(org: str | None = "org_x") -> Receipt:
    return next(r for r in receipts(org) if r.claim == CLAIM)


def test_the_receipt_exists_once_and_belongs_to_context():
    from genios_engine.platform.receipt_coverage import RECEIPT_PACKAGE

    assert sum(r.claim == CLAIM for r in receipts("org_x")) == 1
    assert RECEIPT_PACKAGE[CLAIM][0] == "context"


def test_one_kept_event_outside_memory_fails_it():
    assert _receipt().expect(0) is True and _receipt().expect(1) is False


def test_it_is_scoped_to_the_tenant():
    assert ":org" in _receipt().sql and ":org" not in _receipt(org=None).sql


@pytest.fixture
def engine(live_db_url):
    if not live_db_url:
        pytest.skip("GENIOS_TEST_DATABASE_URL not set — the receipt needs real Postgres")
    from genios_engine.platform.db import get_engine

    eng = get_engine(live_db_url)
    _clear(eng)
    with eng.begin() as c:
        c.execute(text("insert into orgs (id, name, email) values (:o, :o, 'f@kept.test')"),
                  {"o": ORG})
    yield eng
    _clear(eng)


def _clear(eng) -> None:
    with eng.begin() as c:
        for tbl in ("l2_processing_runs", "qualified_signals", "source_events"):
            c.execute(text(f"delete from {tbl} where org_id = :o"), {"o": ORG})
        c.execute(text("delete from orgs where id = :o"), {"o": ORG})


def _event(eng, event_id: str, *, outcome: str = "emitted", source: str = "gmail",
           age: timedelta = timedelta(days=2), run: str | None = None,
           signal: bool = False) -> None:
    at = datetime.now(timezone.utc) - age
    with eng.begin() as c:
        c.execute(text(
            "insert into source_events (event_id, org_id, connection_id, source, object_type, "
            "source_object_id, dedup_key, actor, occurred_at, captured_at, outcome) values "
            "(:e, :o, 'conn_kept', :s, 'email_message', :e, :e, cast(:a as jsonb), :at, :at, :out)"),
            {"e": event_id, "o": ORG, "s": source, "at": at, "out": outcome,
             "a": json.dumps({"email": "x@kept.test"})})
        if run:
            c.execute(text("insert into l2_processing_runs (org_id, event_id, status, attempts) "
                           "values (:o, :e, :st, 1)"), {"o": ORG, "e": event_id, "st": run})
        if signal:
            c.execute(text(
                "insert into qualified_signals (signal_id, org_id, event_id, trace_id, signal_type, "
                "importance_bp, importance_version, confidence_bp, visibility, extraction_ref, "
                "evidence_refs, state, occurred_at) values (:s, :o, :e, :t, 'approval_requested', "
                "6000, 'alg17-v1', 8000, cast('{\"scope\": \"org\"}' as jsonb), :x, "
                "cast('[\"ev\"]' as jsonb), 'active', :at)"),
                {"s": f"sig_{event_id}", "o": ORG, "e": event_id, "t": f"t_{event_id}",
                 "x": f"x_{event_id}", "at": at})


def _count(eng) -> int:
    with eng.connect() as c:
        return int(c.execute(text(_receipt(org=ORG).sql), {"org": ORG}).scalar())


@pytest.mark.pg
def test_what_entered_memory_or_is_not_owed_is_not_counted(engine):
    _event(engine, "k_done", run="done")
    _event(engine, "k_archived_done", outcome="archived", run="done")
    _event(engine, "k_fresh", age=timedelta(hours=3))              # under a day: the drain's turn
    _event(engine, "k_parked", outcome="parked")                   # not kept yet: in the park queue
    _event(engine, "k_screen", source="screen_session")            # D22: a screen item is not owed
    assert _count(engine) == 0


@pytest.mark.pg
@pytest.mark.parametrize("kind", ["never_taken", "archived_never_taken", "held", "failed",
                                  "l2_parked", "screen_with_a_signal"])
def test_a_kept_event_a_day_old_outside_memory_is_counted(engine, kind):
    _event(engine, "k_done", run="done")
    {"never_taken": lambda: _event(engine, "k_x"),
     "archived_never_taken": lambda: _event(engine, "k_x", outcome="archived"),
     "held": lambda: _event(engine, "k_x", run="held"),
     "failed": lambda: _event(engine, "k_x", run="failed"),
     "l2_parked": lambda: _event(engine, "k_x", run="parked"),
     "screen_with_a_signal": lambda: _event(engine, "k_x", source="screen_session",
                                            signal=True)}[kind]()
    assert _count(engine) == 1
