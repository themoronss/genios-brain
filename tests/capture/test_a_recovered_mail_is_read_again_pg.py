"""STEP-05 · every kept mail that was never read joins the re-read ladder — whatever recovered it.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… pytest tests/capture/test_a_recovered_mail_is_read_again_pg.py -q

`capture/landing/unread.queue_unread` (tree `yc2_w27_s05 · M23.C4.L-logic.V2.U01`). Every recovery path
only flipped `outcome` back to `emitted` — the parked drain's re-admission, a manual recover, a refetch, a
recapture — and L1 extraction runs only inline at capture, so a recovered mail got no extraction and no
signal, and `_pull` never took it: on the design partner's org 77 re-admitted parks and 69 re-admitted
junk verdicts sat emitted and unread (`speedrun008/YC-II W27/` STEP-05 §8.2). A promotion out of the
archive is the same state. The queue files every such mail into the ladder STEP-18 B18 built — an
`extraction_never_ran` park, due now — and the ladder re-reads it through the capture door, carrying why
(`rereading`), so the gate reads it rather than judging it out again (U05). Mail captured while the
tenant's Layer 1 was off is the same population, so `find_unread`'s door is this one.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import text

from genios_engine.capture.landing import unread
from genios_engine.capture.parked.drain import NEEDS_REEXTRACTION
from genios_engine.contracts.source_event import compute_dedup_key
from genios_engine.platform.crypto import encrypt

pytestmark = pytest.mark.pg

NOW = datetime(2026, 10, 6, 12, tzinfo=timezone.utc)
SWITCHED_ON = NOW - timedelta(days=20)


@pytest.fixture
def engine(live_db_url):
    if not live_db_url:
        pytest.skip("GENIOS_TEST_DATABASE_URL not set — needs real Postgres")
    from genios_engine.platform.db import get_engine
    return get_engine(live_db_url)


@pytest.fixture
def org(engine):
    from genios_engine.platform.config import get_settings
    org_id = f"org_reread_{uuid.uuid4().hex[:8]}"
    with engine.begin() as c:
        c.execute(text("insert into orgs (id, name) values (:o, 'recovered mail')"), {"o": org_id})
        c.execute(text("insert into l1_semantic_activation (org_id, enabled_at, enabled_by) "
                       "values (:o, :at, 'test')"), {"o": org_id, "at": SWITCHED_ON})
    yield org_id, get_settings().crypto_key
    with engine.begin() as c:
        for table in ("parked_events", "qualified_signals", "l1_extraction_results",
                      "l2_processing_runs", "raw_payloads", "source_events",
                      "l1_semantic_activation"):
            c.execute(text(f"delete from {table} where org_id = :o"), {"o": org_id})
        c.execute(text("delete from orgs where id = :o"), {"o": org_id})


def _mail(engine, org, *, captured=NOW - timedelta(days=2), source="gmail",
          object_type="email_message", version=None, attention_reason=None,
          payload_expires=NOW + timedelta(days=30), park=None, extracted=False,
          signal=False, l2_run=None) -> str:
    """One emitted mail, as a recovery leaves it: the ledger row, the kept payload — and whatever
    else the case names (a park row and its status, an extraction, a signal, an L2 run)."""
    org_id, key = org
    event_id = f"evt_{uuid.uuid4().hex[:12]}"
    mid = f"m_{event_id}"
    with engine.begin() as c:
        c.execute(text(
            "insert into source_events (event_id, org_id, connection_id, source, object_type, "
            " source_object_id, dedup_key, actor, occurred_at, captured_at, recipients, outcome, "
            " attention, attention_reason) values (:e, :o, 'con_x', :src, :ot, :mid, :dk, "
            " cast(:actor as jsonb), :at, :at, :rcp, 'emitted', 'deep', :why)"),
            {"e": event_id, "o": org_id, "src": source, "ot": object_type, "mid": mid,
             "dk": compute_dedup_key(source, object_type, mid, version),
             "actor": json.dumps({"type": "external_contact", "email": "pankaj@saka.test",
                                  "name": "Pankaj"}),
             "at": captured, "rcp": ["founder@kite.test"], "why": attention_reason})
        c.execute(text(
            "insert into raw_payloads (id, org_id, event_id, content_type, enc_content, expires_at) "
            "values (:id, :o, :e, 'application/json', :enc, :exp)"),
            {"id": f"pay_{event_id}", "o": org_id, "e": event_id, "exp": payload_expires,
             "enc": encrypt(json.dumps({"subject": "Intro", "body": "Pankaj, meet Meera."}), key)})
        if park:
            code, status = park
            c.execute(text(
                "insert into parked_events (event_id, org_id, source, reason_code, stage, trace, "
                " status, created_at) values (:e, :o, :src, :r, 'gate', cast('[]' as jsonb), :st, "
                " :at)"), {"e": event_id, "o": org_id, "src": source, "r": code, "st": status,
                           "at": captured})
        if extracted:
            c.execute(text(
                "insert into l1_extraction_results (processing_key, org_id, event_id, output, "
                " profile_id, tier) values (:k, :o, :e, cast('{}' as jsonb), 'email', 'T2')"),
                {"k": f"x_{event_id}", "o": org_id, "e": event_id})
        if signal:
            c.execute(text(
                "insert into qualified_signals (signal_id, org_id, event_id, trace_id, signal_type, "
                " importance_bp, importance_version, confidence_bp, visibility, extraction_ref, "
                " evidence_refs, state, occurred_at) values (:s, :o, :e, :t, 'approval_requested', "
                " 6000, 'alg17-v1', 8000, cast('{\"scope\": \"org\"}' as jsonb), :x, "
                " cast('[\"ev\"]' as jsonb), 'active', :at)"),
                {"s": f"sig_{event_id}", "o": org_id, "e": event_id, "t": f"t_{event_id}",
                 "x": f"x_missing_{event_id}", "at": captured})
        if l2_run:
            c.execute(text("insert into l2_processing_runs (org_id, event_id, status, attempts) "
                           "values (:o, :e, :st, 1)"), {"o": org_id, "e": event_id, "st": l2_run})
    return event_id


def _parks(engine, org) -> dict[str, tuple]:
    with engine.connect() as c:
        return {r.event_id: (r.reason_code, r.status, r.trace) for r in c.execute(text(
            "select event_id, reason_code, status, trace from parked_events where org_id = :o"),
            {"o": org[0]})}


def test_every_kept_mail_never_read_is_queued_and_nothing_else(engine, org):
    owed = {
        "readmitted_park": _mail(engine, org, park=("low_relevance", "recovered"),
                                 attention_reason="readmitted:low_relevance"),
        "readmitted_junk": _mail(engine, org, attention_reason="readmitted:llm_junk"),
        "promoted": _mail(engine, org, attention_reason="promoted:N-02", l2_run="done"),
        "refetched": _mail(engine, org, park=("DOC-05", "recovered")),
        "captured_while_off": _mail(engine, org, captured=SWITCHED_ON - timedelta(days=3)),
    }
    not_owed = {
        "read": _mail(engine, org, extracted=True),
        "signal_waiting_for_its_extraction": _mail(engine, org, signal=True),
        "calendar": _mail(engine, org, source="gcal", object_type="calendar_event"),
        "screen": _mail(engine, org, source="screen_session", object_type="screen_chat_thread"),
        "versioned": _mail(engine, org, version="v7"),
        "payload_gone": _mail(engine, org, payload_expires=NOW - timedelta(days=1)),
        "refetch_still_pending": _mail(engine, org, park=("DOC-05", "pending")),
        "given_up": _mail(engine, org, park=("extraction_parse_failed", "dead_letter")),
        "being_captured_now": _mail(engine, org, captured=NOW - timedelta(minutes=2)),
    }
    assert unread.queue_unread(engine, org[0], now=NOW) == len(owed)
    parks = _parks(engine, org)
    queued = {name for name, e in {**owed, **not_owed}.items()
              if parks.get(e, (None, None))[:2] == (unread.EXTRACTION_NEVER_RAN, "pending")}
    assert queued == set(owed), sorted(queued ^ set(owed))
    assert parks[not_owed["refetch_still_pending"]][:2] == ("DOC-05", "pending")
    assert parks[not_owed["given_up"]][1] == "dead_letter"
    assert unread.queue_unread(engine, org[0], now=NOW) == 0, "a second pass queued again"


def test_a_reopened_park_keeps_the_reason_it_was_parked_for(engine, org):
    event_id = _mail(engine, org, park=("low_relevance", "recovered"))
    unread.queue_unread(engine, org[0], now=NOW)
    _code, _status, trace = _parks(engine, org)[event_id]
    assert any(isinstance(t, dict) and t.get("requeued_from") == "low_relevance"
               for t in trace), trace


def test_the_ladder_takes_a_queued_mail_now_and_says_why_it_is_read_again(engine, org):
    assert unread.EXTRACTION_NEVER_RAN in NEEDS_REEXTRACTION, "the drain would call it terminal"
    event_id = _mail(engine, org, attention_reason="readmitted:llm_junk")
    unread.queue_unread(engine, org[0], now=NOW)
    due = unread.find_parked_extractions(engine, org[0], now=NOW)
    assert [r.event_id for r in due] == [event_id]
    raw = unread.to_raw_object(due[0], org[1])
    assert raw is not None and raw.rereading == unread.EXTRACTION_NEVER_RAN


def test_a_tenant_whose_reading_is_off_queues_nothing(engine, org):
    """A re-read with Layer 1 off would land unread again — and be queued again, for ever."""
    _mail(engine, org, attention_reason="readmitted:llm_junk")
    with engine.begin() as c:
        c.execute(text("update l1_semantic_activation set disabled_at = :at where org_id = :o"),
                  {"o": org[0], "at": NOW - timedelta(days=1)})
    assert unread.queue_unread(engine, org[0], now=NOW) == 0
