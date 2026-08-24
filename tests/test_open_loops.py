"""L2-16: completion closes ONE request, never a person.

`thread.ball_in_court` was the entire completion authority — one bit per human — so answering
any of somebody's three questions read as answering all of them, and a card expiring was
indistinguishable from the request resolving. The ledger gives each request its own row.
"""
from datetime import datetime, timedelta, timezone

import pytest

pytest.importorskip("sqlalchemy")
from sqlalchemy import create_engine, text  # noqa: E402

from genios_engine.context.open_loops import (  # noqa: E402
    close_loops_for_reply,
    open_loop_counts,
    record_ask,
)

NOW = datetime(2026, 8, 24, 12, 0, tzinfo=timezone.utc)


@pytest.fixture()
def conn():
    engine = create_engine("sqlite://")
    with engine.begin() as c:
        c.execute(text("""
            create table open_loops (
                org_id text not null, loop_id text not null,
                subject_node_id text not null, kind text not null, thread_id text,
                status text not null default 'open',
                opened_at timestamp not null, last_seen_at timestamp not null,
                ask_count int not null default 1, opened_by_event text not null,
                closed_at timestamp, closed_by_event text,
                primary key (org_id, loop_id))"""))
    with engine.begin() as c:
        yield c


def test_a_repeat_ask_is_the_same_loop_not_a_second_one(conn):
    a = record_ask(conn, org_id="o", subject_node_id="n1", kind="question",
                   thread_id="t1", event_id="e1", at=NOW)
    b = record_ask(conn, org_id="o", subject_node_id="n1", kind="question",
                   thread_id="t1", event_id="e2", at=NOW + timedelta(days=1))
    assert a == b
    row = conn.execute(text("select ask_count, status from open_loops")).one()
    assert row.ask_count == 2 and row.status == "open"


def test_our_reply_closes_only_that_threads_loops(conn):
    """Answering ONE conversation must not mark every other conversation answered."""
    record_ask(conn, org_id="o", subject_node_id="n1", kind="question",
               thread_id="t1", event_id="e1", at=NOW)
    record_ask(conn, org_id="o", subject_node_id="n1", kind="demo_requested",
               thread_id="t2", event_id="e2", at=NOW)
    closed = close_loops_for_reply(conn, org_id="o", subject_node_id="n1",
                                   thread_id="t1", event_id="e3", at=NOW + timedelta(hours=1))
    assert closed == 1
    assert open_loop_counts(conn, "o") == {"n1": 1}      # t2's demo ask is still open


def test_asking_again_after_our_answer_reopens_the_loop(conn):
    """Their asking again is direct evidence our answer did not resolve it."""
    record_ask(conn, org_id="o", subject_node_id="n1", kind="question",
               thread_id="t1", event_id="e1", at=NOW)
    close_loops_for_reply(conn, org_id="o", subject_node_id="n1",
                          thread_id="t1", event_id="e2", at=NOW + timedelta(hours=1))
    assert open_loop_counts(conn, "o") == {}
    record_ask(conn, org_id="o", subject_node_id="n1", kind="question",
               thread_id="t1", event_id="e3", at=NOW + timedelta(hours=2))
    assert open_loop_counts(conn, "o") == {"n1": 1}


def test_a_reply_cannot_answer_a_question_not_yet_asked(conn):
    record_ask(conn, org_id="o", subject_node_id="n1", kind="question",
               thread_id="t1", event_id="e1", at=NOW + timedelta(days=1))
    closed = close_loops_for_reply(conn, org_id="o", subject_node_id="n1",
                                   thread_id="t1", event_id="e2", at=NOW)
    assert closed == 0


def test_a_threadless_ask_closes_on_any_direct_reply(conn):
    """A person-wide loop has no conversation identity — a direct reply to that person is the
    best completion evidence it can ever have."""
    record_ask(conn, org_id="o", subject_node_id="n1", kind="question",
               thread_id=None, event_id="e1", at=NOW)
    closed = close_loops_for_reply(conn, org_id="o", subject_node_id="n1",
                                   thread_id="t9", event_id="e2", at=NOW + timedelta(hours=1))
    assert closed == 1


def test_the_regeneration_gate_defers_to_the_ledger_for_ask_rules():
    """An OPEN loop with no new evidence is exactly the case that SHOULD re-surface — they
    asked, we never answered, silence is not resolution. The ledger going quiet on our reply is
    what stops an ANSWERED ask from returning."""
    import inspect

    from genios_engine.reason import runner

    assert "unanswered_email" in runner._LOOP_GATED_REASON_CODES
    src = inspect.getsource(runner.run)
    assert "loop_still_open" in src
    assert "open_loop_counts" in src


# ── L2-01: the situation is pack-readable, not just engine-attached ─────────────
def test_situation_fields_enter_the_fact_envelope_rules_already_read():
    """`ctx.situation` served two hardcoded consumers (dormancy suppress, confidence
    pass-through). As facts, the PACK can consume the substrate: an author writes
    `{"path": "situation.status", ...}` in rule data with zero engine change — the actual
    "flip the consumer" the audit asked for."""
    import inspect

    from genios_engine.reason import runner

    src = inspect.getsource(runner.run)
    for field in ("situation.status", "situation.type", "situation.confidence",
                  "situation.coverage"):
        assert f'"{field}"' in src
    # setdefault, never overwrite: a captured fact outranks a derived mirror
    assert "ctx.facts.setdefault(_field" in src
