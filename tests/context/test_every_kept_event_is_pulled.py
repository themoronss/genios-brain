"""STEP-05 · the drain pulls every kept event that has a road into memory.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… pytest tests/context/test_every_kept_event_is_pulled.py -q

Tree `yc2_w27_s05 · M23.C2.L-data.V1.U01`. `context/runner._pull` inner-joined an ACTIVE qualified
signal and a payload, and took `outcome = 'emitted'` only — so a mail the qualification floor did not
publish, an archived mail and a calendar event whose deadline signal had expired never reached Layer 2,
and memory held ~27 of 395 mails and 2 of 34 meetings (`speedrun008/YC-II W27/` STEP-05 §8). Now it
admits every kept event that `context/memory_lanes` gives a road: a signal, an extraction below the
floor, an archive (metadata), a structured record (calendar) — and nothing else.
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

ORG = "every_kept_event_is_pulled_org"
NOW = datetime(2026, 9, 10, 10, 0, tzinfo=timezone.utc)


def _reset(store) -> None:
    from genios_engine.api.account_routes import _wipe

    with store.engine.begin() as c:
        _wipe(c, ORG)
        c.execute(text("delete from orgs where id = :o"), {"o": ORG})


@pytest.fixture
def store(pg_store):
    _reset(pg_store)
    with pg_store.engine.begin() as c:
        c.execute(text("insert into orgs (id, name, email) values (:o, :o, 'founder.pull@gmail.com')"),
                  {"o": ORG})
    yield pg_store
    _reset(pg_store)


def _event(c, event_id: str, *, outcome: str = "emitted", source: str = "gmail",
           object_type: str = "email_message", payload: bool = True) -> None:
    c.execute(text(
        "insert into source_events (event_id, org_id, connection_id, source, object_type, "
        "source_object_id, dedup_key, actor, recipients, occurred_at, outcome) values "
        "(:e, :o, 'conn_pull', :s, :t, :e, :e, cast(:a as jsonb), :r, :at, :out)"),
        {"e": event_id, "o": ORG, "s": source, "t": object_type,
         "a": json.dumps({"type": "external_contact", "email": "ira@northwind.test"}),
         "r": ["founder.pull@gmail.com"], "at": NOW, "out": outcome})
    if payload:
        c.execute(text(
            "insert into raw_payloads (id, org_id, event_id, content_type, enc_content, expires_at) "
            "values (:id, :o, :e, 'application/json', :enc, :exp)"),
            {"id": f"pay_{event_id}", "o": ORG, "e": event_id,
             "enc": encrypt(json.dumps({"subject": "s", "body": "b"}), get_settings().crypto_key),
             "exp": NOW + timedelta(days=180)})


def _extraction(c, event_id: str, key: str) -> None:
    c.execute(text(
        "insert into l1_extraction_results (processing_key, org_id, event_id, output, profile_id, tier) "
        "values (:k, :o, :e, cast(:out as jsonb), 'email', 'T2')"),
        {"k": key, "o": ORG, "e": event_id, "out": json.dumps({"intent": "request"})})


def _signal(c, event_id: str, key: str) -> None:
    c.execute(text(
        "insert into qualified_signals (signal_id, org_id, event_id, trace_id, signal_type, "
        "importance_bp, importance_version, confidence_bp, visibility, extraction_ref, evidence_refs, "
        "state, occurred_at) values (:s, :o, :e, :t, 'approval_requested', 6000, 'alg17-v1', 8000, "
        "cast('{\"scope\": \"org\"}' as jsonb), :x, cast('[\"ev\"]' as jsonb), 'active', :at)"),
        {"s": f"sig_{event_id}", "o": ORG, "e": event_id, "t": f"trace_{event_id}", "x": key,
         "at": NOW})


def _pulled(store, limit: int = 100) -> dict[str, object]:
    return {r.event_id: r for r in runner._pull(store, ORG, limit)}


def test_every_kept_event_with_a_road_is_pulled_and_nothing_else(store):
    with store.engine.begin() as c:
        _event(c, "e_signal"); _extraction(c, "e_signal", "x_signal"); _signal(c, "e_signal", "x_signal")
        _event(c, "e_below"); _extraction(c, "e_below", "x_below")          # read, no signal
        _event(c, "e_unread")                                                # nothing to read yet
        _event(c, "e_archived", outcome="archived")                          # noise: metadata only
        _event(c, "e_screen", source="screen_session", object_type="screen_chat_thread")
        _extraction(c, "e_screen", "x_screen")                               # a screen item, no signal
        _event(c, "e_screen_archived", outcome="archived", source="screen_session",
               object_type="screen_chat_thread")
        _event(c, "e_meeting", source="gcal", object_type="calendar_event")  # structured, no signal
        _event(c, "e_parked", outcome="parked"); _extraction(c, "e_parked", "x_parked")
        _event(c, "e_done"); _extraction(c, "e_done", "x_done")
        c.execute(text("insert into l2_processing_runs (org_id, event_id, status, attempts) "
                       "values (:o, 'e_done', 'done', 1)"), {"o": ORG})
    pulled = _pulled(store)
    assert set(pulled) == {"e_signal", "e_below", "e_archived", "e_meeting"}, sorted(pulled)
    assert pulled["e_signal"].has_signal and pulled["e_signal"].qes_output is not None
    assert not pulled["e_below"].has_signal and pulled["e_below"].own_output is not None
    assert pulled["e_archived"].outcome == "archived"
    assert pulled["e_archived"].recipients == ["founder.pull@gmail.com"]


def test_an_archived_mail_is_pulled_without_its_words(store):
    """An archive has no prepared text (STEP-03, F37), and its encrypted payload — which it keeps —
    is not handed to the drain at all: its memory is the ledger's own columns (STEP-05 §8.3)."""
    with store.engine.begin() as c:
        _event(c, "e_archived_only", outcome="archived")
        _event(c, "e_kept_control")
        _extraction(c, "e_kept_control", "x_kept_control")
    pulled = _pulled(store)
    assert pulled["e_archived_only"].prepared_text is None
    assert pulled["e_archived_only"].enc_content is None, "the drain was handed an archive's payload"
    assert pulled["e_kept_control"].enc_content is not None, "the control lost its payload"


def test_the_pull_admits_exactly_what_has_a_road(store):
    """The pull is `memory_lanes.lane_for` spelled in SQL — two spellings of one rule, which is how
    the drain and the progress bar disagreed twice before. Every combination is seeded, and the
    pull must admit an event exactly when `lane_for` gives it a road: a row it admitted with no road
    would be re-pulled at the head of every sweep, and a road it refused would never be walked."""
    from itertools import product

    from genios_engine.context.memory_lanes import SCREEN_SOURCE, lane_for

    kinds = {"mail": ("gmail", "email_message"), "screen": (SCREEN_SOURCE, "screen_chat_thread"),
             "meeting": ("gcal", "calendar_event")}
    expected: dict[str, bool] = {}
    with store.engine.begin() as c:
        for outcome, kind, signal, extraction in product(("emitted", "archived", "parked", "dropped"),
                                                        kinds, (True, False), (True, False)):
            eid = f"e_{outcome}_{kind}_{int(signal)}{int(extraction)}"
            source, object_type = kinds[kind]
            _event(c, eid, outcome=outcome, source=source, object_type=object_type)
            if extraction:
                _extraction(c, eid, f"x_{eid}")
            if signal:
                _signal(c, eid, f"x_{eid}")                 # with no extraction: a hollow signal
            expected[eid] = lane_for(outcome=outcome, source=source, structured=kind == "meeting",
                                     has_signal=signal, has_extraction=extraction) is not None
    pulled = set(_pulled(store, limit=1000))
    admitted_without_a_road = sorted(e for e in pulled if not expected[e])
    road_never_walked = sorted(e for e, road in expected.items() if road and e not in pulled)
    assert not admitted_without_a_road and not road_never_walked, (
        admitted_without_a_road, road_never_walked)


def test_the_pending_question_is_unchanged_for_a_signal_with_no_extraction(store):
    """A signal whose extraction row is missing is still pulled, and held by the drain, as before —
    "no signal" and "a signal with nothing behind it" stay two different states."""
    with store.engine.begin() as c:
        _event(c, "e_hollow"); _signal(c, "e_hollow", "x_missing")
    row = _pulled(store)["e_hollow"]
    assert row.has_signal and row.qes_output is None and row.own_output is None
