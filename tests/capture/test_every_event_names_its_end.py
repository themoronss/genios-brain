"""STEP-06 · one event, one end — the journey reads past Layer 1, into memory.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… pytest tests/capture/test_every_event_names_its_end.py -q

Tree `yc2_w27_s06 · M24.C3.L-logic.V1.U01`. `capture/journey.event_journey` (`GET /events/{id}/journey`)
already answered "why did I never see X?" — up to Layer 1: it read no memory run and no attention tier
(`speedrun008/YC-II W27/` STEP-06 §8.2). A mail that reached memory below the floor, or waited in the
re-read ladder, read as unexplained. It now names exactly one `end` per event, from what each layer
recorded: not_captured · superseded · in_memory · failed · parked · waiting (for the drain, the
re-read, or memory) · archived (a screen item, the one kept item with no road) · stopped · none.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import text

from genios_engine.capture.journey import ENDS, event_journey

pytestmark = pytest.mark.pg

ORG = "org_s06_event_ends"
AT = datetime(2026, 10, 7, 9, 0, tzinfo=timezone.utc)


@pytest.fixture
def engine(live_db_url):
    if not live_db_url:
        pytest.skip("GENIOS_TEST_DATABASE_URL not set — needs real Postgres")
    from genios_engine.platform.db import get_engine
    eng = get_engine(live_db_url)
    _reset(eng)
    with eng.begin() as c:
        c.execute(text("insert into orgs (id, name) values (:o, 'event ends')"), {"o": ORG})
    yield eng
    _reset(eng)


def _reset(eng):
    with eng.begin() as c:
        for table in ("event_trace", "parked_events", "l2_processing_runs", "source_events"):
            c.execute(text(f"delete from {table} where org_id = :o"), {"o": ORG})
        c.execute(text("delete from orgs where id = :o"), {"o": ORG})


def _event(c, event_id, outcome, *, source="gmail", attention=None, reason=None):
    c.execute(text(
        "insert into source_events (event_id, org_id, connection_id, source, object_type, "
        " source_object_id, dedup_key, actor, occurred_at, captured_at, outcome, attention, "
        " attention_reason) values (:e, :o, 'con_1', :src, 'email_message', :soid, :dk, "
        " cast(:actor as jsonb), :at, :at, :out, :att, :why)"),
        {"e": event_id, "o": ORG, "src": source, "soid": f"m_{event_id}", "dk": f"d_{event_id}",
         "actor": json.dumps({"email": "a@x.test"}), "at": AT, "out": outcome, "att": attention,
         "why": reason})


def _run(c, event_id, status, *, error=None):
    c.execute(text("insert into l2_processing_runs (org_id, event_id, status, attempts, last_error) "
                   "values (:o, :e, :s, 1, :err)"),
              {"o": ORG, "e": event_id, "s": status, "err": error})


def _park(c, event_id, code, status="pending"):
    c.execute(text("insert into parked_events (event_id, org_id, source, reason_code, stage, "
                   " trace, status, created_at) values (:e, :o, 'gmail', :r, 'gate', "
                   " cast('[]' as jsonb), :s, :at)"),
              {"e": event_id, "o": ORG, "r": code, "s": status, "at": AT})


def _trace(c, event_id, stage, action, reason):
    c.execute(text("insert into event_trace (org_id, event_id, stage, action, reason_code, at) "
                   "values (:o, :e, :st, :a, :r, :at)"),
              {"o": ORG, "e": event_id, "st": stage, "a": action, "r": reason,
               "at": AT + timedelta(seconds=1)})


def test_every_event_names_exactly_one_end(engine):
    with engine.begin() as c:
        _event(c, "e_superseded", "superseded")
        _event(c, "e_memory", "emitted", attention="deep")
        _run(c, "e_memory", "done")
        _event(c, "e_archive_memory", "archived", attention="archive", reason="N-02")
        _trace(c, "e_archive_memory", "s1_noise", "archive", "N-02")
        _run(c, "e_archive_memory", "done")
        _event(c, "e_failed", "emitted")
        _run(c, "e_failed", "failed", error="EdgeTypeRefused")
        _event(c, "e_parked", "parked")
        _park(c, "e_parked", "DOC-02")
        _event(c, "e_reread", "emitted")
        _park(c, "e_reread", "extraction_never_ran")
        _event(c, "e_drain", "emitted", attention="skim")
        _event(c, "e_held", "emitted")
        _run(c, "e_held", "held", error="held_missing_qes_extraction")
        _event(c, "e_screen", "archived", source="screen_session", attention="archive",
               reason="llm_junk")
        _event(c, "e_dropped", "dropped")
        _trace(c, "e_dropped", "s0_scope", "drop", "out_of_scope")
        _event(c, "e_nothing", "dropped")
    ends = {e: event_journey(engine, org_id=ORG, event_id=e)["end"] for e in (
        "e_unknown", "e_superseded", "e_memory", "e_archive_memory", "e_failed", "e_parked",
        "e_reread", "e_drain", "e_held", "e_screen", "e_dropped", "e_nothing")}
    assert {e: v["end"] for e, v in ends.items()} == {
        "e_unknown": "not_captured", "e_superseded": "superseded", "e_memory": "in_memory",
        "e_archive_memory": "in_memory", "e_failed": "failed", "e_parked": "parked",
        "e_reread": "waiting", "e_drain": "waiting", "e_held": "waiting", "e_screen": "archived",
        "e_dropped": "stopped", "e_nothing": "none"}
    assert ends["e_archive_memory"]["attention"] == "archive"
    assert ends["e_failed"]["error"] == "EdgeTypeRefused"
    assert ends["e_parked"]["reason_code"] == "DOC-02"
    assert (ends["e_reread"]["for"], ends["e_reread"]["reason_code"]) == (
        "re-read", "extraction_never_ran")
    assert ends["e_drain"]["for"] == "the drain" and ends["e_held"]["for"] == "memory"
    assert ends["e_screen"]["reason"] == "llm_junk"
    assert (ends["e_dropped"]["stage"], ends["e_dropped"]["reason_code"]) == (
        "s0_scope", "out_of_scope")


def test_the_walk_shows_the_memory_run_and_the_attention_tier(engine):
    with engine.begin() as c:
        _event(c, "e_memory", "emitted", attention="deep", reason="W-01")
        _run(c, "e_memory", "done")
    walk = event_journey(engine, org_id=ORG, event_id="e_memory")
    assert walk["memory"]["status"] == "done"
    assert (walk["event"]["attention"], walk["event"]["attention_reason"]) == ("deep", "W-01")


def test_the_ends_are_a_closed_list():
    assert set(ENDS) == {"not_captured", "superseded", "in_memory", "failed", "parked", "waiting",
                         "archived", "stopped", "none"}
