"""STEP-08 · a deleted mail that came back names the event that replaced it — and the new one names it.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… pytest tests/capture/test_a_resynced_mail_names_its_replacement.py -q

`capture/journey.event_journey` (tree `yc2_w27_s08 · M26.C4.L-logic.V1.U01`). The re-sync
(`capture/landing/resync`) frees a deleted message's key, the backfill drain lands it again as a NEW
event, and the finish supersedes the old row. Without this the walk of the old row ended at
`superseded` and said nothing more, and the walk of the new event did not know there had been an old
one: "why did I never see X?" had two halves nobody joined. Now the old row's end names its
replacement, the new event names the row it replaced, a row still waiting says it is freed, and a row
Gmail no longer lists stops at the re-sync with that reason. The re-sync writes only `pass` and
`drop`, so no step of it is unclassified.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import text

from genios_engine.capture.journey import event_journey, unclassified_actions
from genios_engine.capture.landing import resync
from genios_engine.contracts.source_event import compute_dedup_key

pytestmark = pytest.mark.pg

NOW = datetime(2026, 10, 7, 12, tzinfo=timezone.utc)


@pytest.fixture
def engine(live_db_url):
    if not live_db_url:
        pytest.skip("GENIOS_TEST_DATABASE_URL not set — needs real Postgres")
    from genios_engine.platform.db import get_engine
    return get_engine(live_db_url)


@pytest.fixture
def org(engine):
    org_id = f"org_resync_walk_{uuid.uuid4().hex[:8]}"
    with engine.begin() as c:
        c.execute(text("insert into orgs (id, name) values (:o, 'resync walk')"), {"o": org_id})
    yield org_id
    with engine.begin() as c:
        for table in ("event_trace", "raw_payloads", "source_events"):
            c.execute(text(f"delete from {table} where org_id = :o"), {"o": org_id})
        c.execute(text("delete from orgs where id = :o"), {"o": org_id})


def _row(engine, org: str, mid: str, *, outcome: str, code: str, stage: str = "S1",
         body: bool = False) -> str:
    event_id = f"evt_{uuid.uuid4().hex[:12]}"
    at = NOW - timedelta(days=9)
    with engine.begin() as c:
        c.execute(text(
            "insert into source_events (event_id, org_id, connection_id, source, object_type, "
            " source_object_id, dedup_key, actor, occurred_at, captured_at, outcome, attention, "
            " attention_reason) values (:e, :o, 'con_x', 'gmail', 'email_message', :mid, :dk, "
            " cast(:actor as jsonb), :at, :at, :out, :att, :why)"),
            {"e": event_id, "o": org, "mid": mid,
             "dk": compute_dedup_key("gmail", "email_message", mid),
             "actor": json.dumps({"type": "external_contact", "email": "hello@introly.test"}),
             "at": at, "out": outcome, "att": "archive" if outcome == "archived" else None,
             "why": code if outcome == "archived" else None})
        action = {"dropped": "drop", "archived": "archive"}[outcome]
        c.execute(text("insert into event_trace (org_id, event_id, stage, action, reason_code, at) "
                       "values (:o, :e, :s, :a, :r, :at)"),
                  {"o": org, "e": event_id, "s": stage, "a": action, "r": code,
                   "at": NOW - timedelta(days=9)})
        if body:
            c.execute(text("insert into raw_payloads (id, org_id, event_id, content_type, "
                           "enc_content, expires_at) values (:id, :o, :e, 'application/json', "
                           "'x', :exp)"),
                      {"id": f"pay_{event_id}", "o": org, "e": event_id,
                       "exp": NOW + timedelta(days=180)})
    return event_id


def test_the_old_row_names_its_replacement_and_the_new_event_names_the_old_row(engine, org):
    old = _row(engine, org, "m1", outcome="dropped", code="N-02")
    resync.free_deleted(engine, org, days=60, now=NOW)
    new = _row(engine, org, "m1", outcome="archived", code="N-02", body=True)
    resync.finish(engine, org, now=NOW)

    walk = event_journey(engine, org_id=org, event_id=old)
    assert walk["end"] == {"end": "superseded", "replaced_by": new}
    assert walk["resync"]["replaced_by"] == new and walk["resync"]["freed"]
    assert "replaces" not in walk["resync"], "the old row replaced nothing"
    assert [s["reason_code"] for s in walk["steps"] if s["stage"] == "resync"] == [
        "resync_freed", "resync_replaced"]

    back = event_journey(engine, org_id=org, event_id=new)
    assert back["resync"] == {"replaces": old}
    assert back["end"]["end"] != "superseded"


def test_a_freed_row_still_waiting_says_so_and_still_stops_where_it_was_deleted(engine, org):
    old = _row(engine, org, "m1", outcome="dropped", code="N-02")
    resync.free_deleted(engine, org, days=60, now=NOW)
    walk = event_journey(engine, org_id=org, event_id=old)
    assert walk["resync"]["freed"] and "replaced_by" not in walk["resync"]
    assert walk["end"] == {"end": "stopped", "stage": "S1", "action": "drop", "reason_code": "N-02"}


def test_a_row_gmail_no_longer_lists_stops_at_the_resync_with_that_reason(engine, org):
    old = _row(engine, org, "m1", outcome="dropped", code="N-02")
    resync.free_deleted(engine, org, days=60, now=NOW)
    resync.finish(engine, org, now=NOW)
    walk = event_journey(engine, org_id=org, event_id=old)
    assert walk["end"] == {"end": "stopped", "stage": "resync", "action": "drop",
                           "reason_code": "resync_not_listed"}
    assert walk["resync"]["not_listed"] == {"inside_window": True, "window_days": 60}


def test_a_row_the_ladder_set_aside_is_superseded_with_no_replacement_named(engine, org):
    """The re-read ladder's own `superseded` writes no resync trace — its end is unchanged."""
    event = _row(engine, org, "m1", outcome="archived", code="N-02", body=True)
    with engine.begin() as c:
        c.execute(text("update source_events set outcome = 'superseded' where event_id = :e"),
                  {"e": event})
    walk = event_journey(engine, org_id=org, event_id=event)
    assert walk["end"] == {"end": "superseded"} and walk["resync"] is None


def test_an_event_the_resync_never_touched_carries_no_resync(engine, org):
    event = _row(engine, org, "m1", outcome="archived", code="N-02", body=True)
    assert event_journey(engine, org_id=org, event_id=event)["resync"] is None


def test_the_resync_adds_no_unclassified_step(engine, org):
    _row(engine, org, "m1", outcome="dropped", code="N-02")
    _row(engine, org, "m2", outcome="dropped", code="N-03")
    resync.free_deleted(engine, org, days=60, now=NOW)
    _row(engine, org, "m1", outcome="archived", code="N-02", body=True)
    resync.finish(engine, org, now=NOW)
    assert unclassified_actions(engine, org_id=org) == []
