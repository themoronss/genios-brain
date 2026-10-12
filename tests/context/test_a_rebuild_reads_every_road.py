"""STEP-18 B12 · a rebuild reads every kept event that has a road into memory — with the drain's columns.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… pytest tests/context/test_a_rebuild_reads_every_road.py -q

`yc2_w27_s18` M48.C2.L-data.V0.U04 (L3 Context Graph, `context/`).

⛔ WHAT WAS WRONG. `scripts/rebuild_graph.py` replays the ledger through the drain's own
`_process_one`, but pulled its rows with a query of its own: `outcome = 'emitted'` only, and no
cached extraction, prepared text, recipients or thread. A mail that had reached memory through a
signal arrived with no `qes_output` and was held `held_missing_qes_extraction` — so a rebuild
restored the calendar and none of the mail — and the archived and below-floor roads STEP-05 opened
were never replayed at all.

`context/runner._rows_for_rebuild` is the drain's pull with the same columns over the same roads
(`memory_lanes.lane_for`), minus the one thing a rebuild must not ask: whether memory already
holds the event. One spelling of the columns, so the two cannot drift.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import text

from genios_engine.context import runner
from genios_engine.platform.config import get_settings
from genios_engine.platform.crypto import encrypt

pytestmark = pytest.mark.pg

ORG = "org_s18_rebuild_roads"
OTHER = "org_s18_rebuild_other"
NOW = datetime(2026, 9, 10, 10, 0, tzinfo=timezone.utc)


def _reset(store) -> None:
    from genios_engine.api.account_routes import _wipe

    with store.engine.begin() as c:
        for org in (ORG, OTHER):
            _wipe(c, org)
            c.execute(text("delete from orgs where id = :o"), {"o": org})


@pytest.fixture
def store(pg_store):
    _reset(pg_store)
    with pg_store.engine.begin() as c:
        for org in (ORG, OTHER):
            c.execute(text("insert into orgs (id, name, email) values (:o, :o, :e)"),
                      {"o": org, "e": f"founder.{org}@gmail.com"})
    yield pg_store
    _reset(pg_store)


def _event(c, event_id: str, *, at: datetime, org: str = ORG, outcome: str = "emitted",
           source: str = "gmail", object_type: str = "email_message") -> None:
    c.execute(text(
        "insert into source_events (event_id, org_id, connection_id, source, object_type, "
        "source_object_id, dedup_key, actor, recipients, occurred_at, outcome, parent_object_id) "
        "values (:e, :o, 'conn_rebuild', :s, :t, :e, :e, cast(:a as jsonb), :r, :at, :out, :th)"),
        {"e": event_id, "o": org, "s": source, "t": object_type,
         "a": json.dumps({"type": "external_contact", "email": "ira@northwind.test",
                          "name": "Ira"}),
         "r": ["founder.rebuild@gmail.com"], "at": at, "out": outcome, "th": f"th_{event_id}"})
    c.execute(text(
        "insert into raw_payloads (id, org_id, event_id, content_type, enc_content, expires_at) "
        "values (:id, :o, :e, 'application/json', :enc, :exp)"),
        {"id": f"pay_{event_id}", "o": org, "e": event_id,
         "enc": encrypt(json.dumps({"subject": "s", "body": "b"}), get_settings().crypto_key),
         "exp": at + timedelta(days=180)})


def _prepared(c, event_id: str) -> None:
    c.execute(text("insert into prepared_content (event_id, org_id, prepared_content_id, clean_text) "
                   "values (:e, :o, :p, 'the words the mail said')"),
              {"e": event_id, "o": ORG, "p": f"pc_{event_id}"})


def _extraction(c, event_id: str, key: str, *, org: str = ORG, profile: str | None = "email") -> None:
    c.execute(text(
        "insert into l1_extraction_results (processing_key, org_id, event_id, output, profile_id, tier) "
        "values (:k, :o, :e, cast(:out as jsonb), :p, 'T2')"),
        {"k": key, "o": org, "e": event_id, "out": json.dumps({"intent": f"read {event_id}"}),
         "p": profile})


def _signal(c, event_id: str, key: str, *, org: str = ORG) -> None:
    c.execute(text(
        "insert into qualified_signals (signal_id, org_id, event_id, trace_id, signal_type, "
        "importance_bp, importance_version, confidence_bp, visibility, extraction_ref, evidence_refs, "
        "state, occurred_at) values (:s, :o, :e, :t, 'approval_requested', 6000, 'alg17-v1', 8000, "
        "cast('{\"scope\": \"org\"}' as jsonb), :x, cast('[\"ev\"]' as jsonb), 'active', :at)"),
        {"s": f"sig_{event_id}", "o": org, "e": event_id, "t": f"trace_{event_id}", "x": key,
         "at": NOW})


def _world(store) -> None:
    """Every road, some of it already in memory — the state a rebuild is run against."""
    at = {name: NOW - timedelta(days=n) for n, name in enumerate(
        ("e_signal_done", "e_below", "e_archived", "e_meeting_done", "e_signal_new",
         "e_unread", "e_parked", "e_dropped"))}
    with store.engine.begin() as c:
        # a mail that reached memory through its signal — memory already holds it
        _event(c, "e_signal_done", at=at["e_signal_done"]); _prepared(c, "e_signal_done")
        _extraction(c, "e_signal_done", "x_signal_done"); _signal(c, "e_signal_done", "x_signal_done")
        c.execute(text("insert into l2_processing_runs (org_id, event_id, status, attempts) "
                       "values (:o, 'e_signal_done', 'done', 1)"), {"o": ORG})
        # a mail below the floor, read by Layer 1 and never published
        _event(c, "e_below", at=at["e_below"]); _extraction(c, "e_below", "x_below")
        # an archive: metadata only
        _event(c, "e_archived", at=at["e_archived"], outcome="archived")
        # a calendar event Layer 2 already filed (its own cache row, `profile_id` null)
        _event(c, "e_meeting_done", at=at["e_meeting_done"], source="gcal",
               object_type="calendar_event")
        _extraction(c, "e_meeting_done", "struct:e_meeting_done", profile=None)
        # a mail with a signal memory does not hold yet
        _event(c, "e_signal_new", at=at["e_signal_new"]); _extraction(c, "e_signal_new", "x_new")
        _signal(c, "e_signal_new", "x_new")
        # no road: nothing read yet, not kept, not kept
        _event(c, "e_unread", at=at["e_unread"])
        _event(c, "e_parked", at=at["e_parked"], outcome="parked"); _extraction(c, "e_parked", "x_p")
        _event(c, "e_dropped", at=at["e_dropped"], outcome="dropped")
        # another tenant's signal-bearing mail
        _event(c, "e_other", at=NOW, org=OTHER); _extraction(c, "e_other", "x_other", org=OTHER)
        _signal(c, "e_other", "x_other", org=OTHER)


def test_a_rebuild_reads_every_kept_event_with_a_road_and_nothing_else(store):
    _world(store)
    rows = runner._rows_for_rebuild(store, ORG)
    assert [r.event_id for r in rows] == [
        "e_signal_new", "e_meeting_done", "e_archived", "e_below", "e_signal_done"], (
        "every kept event with a road, oldest first — what memory already holds included")


def test_the_drain_still_skips_what_memory_already_holds(store):
    """The other half of the split: `_pull` keeps its two exclusions."""
    _world(store)
    assert {r.event_id for r in runner._pull(store, ORG, 100)} == {
        "e_signal_new", "e_archived", "e_below"}


def test_a_rebuilt_mail_carries_what_the_drain_reads(store):
    _world(store)
    rows = {r.event_id: r for r in runner._rows_for_rebuild(store, ORG)}
    done = rows["e_signal_done"]
    assert done.has_signal and done.qes_output == {"intent": "read e_signal_done"}, (
        "a rebuilt mail without its cached extraction is held `held_missing_qes_extraction`")
    assert done.prepared_text == "the words the mail said"
    assert done.recipients == ["founder.rebuild@gmail.com"]
    assert done.parent_object_id == "th_e_signal_done" and done.sender_name == "Ira"
    assert rows["e_below"].own_output == {"intent": "read e_below"}
    assert rows["e_archived"].enc_content is None, "an archive's payload never leaves the database"


def test_one_spelling_the_drain_and_the_rebuild_read_the_same_columns(store):
    _world(store)
    pulled = {r.event_id: dict(r._mapping) for r in runner._pull(store, ORG, 100)}
    rebuilt = {r.event_id: dict(r._mapping) for r in runner._rows_for_rebuild(store, ORG)}
    assert pulled and all(rebuilt[e] == row for e, row in pulled.items())
