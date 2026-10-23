"""`scripts/backfill_signal_threads.py` gives a stored signal the thread capture would have given it (G012 H-02).

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… pytest tests/scripts/test_backfill_signal_threads_pg.py -q

Before H-02 every stored signal had no thread (1,383 of 1,383 on the design partner's org). The backfill computes the
five facts with capture's own `_thread_context` over the event rebuilt from its stored payload; these tests seed one
inbound and one outbound message of a thread and one calendar event, and read the rows back.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import text

from genios_engine.capture.esqe.signal_store import PostgresSignalStore, QualifiedSignalRow
from genios_engine.platform.crypto import encrypt

pytestmark = pytest.mark.pg

ORG = "org_h02_backfill"
KEY = "vyvwLTv8gm0hvBMdUqXIsOVobmTWat_tV3Ek655Yoi4="          # generated for this test; never a deployment's key
NOW = datetime(2026, 10, 20, 9, 0, tzinfo=timezone.utc)
QUOTE = "Please send the deck by Friday"


@pytest.fixture
def url():
    url = os.environ.get("GENIOS_TEST_DATABASE_URL")
    if not url:
        pytest.skip("GENIOS_TEST_DATABASE_URL not set")
    from sqlalchemy import create_engine
    eng = create_engine(url)
    with eng.begin() as c:
        c.execute(text("delete from orgs where id = :o"), {"o": ORG})
        c.execute(text("insert into orgs (id, name, email) values (:o, 'Founder', 'founder@nimbus.test')"), {"o": ORG})
    yield url
    with eng.begin() as c:
        for t in ("qualified_signals", "raw_payloads", "source_events"):
            c.execute(text(f"delete from {t} where org_id = :o"), {"o": ORG})
        c.execute(text("delete from orgs where id = :o"), {"o": ORG})


def _event(url, eid, *, object_type, sender, parent, at):
    from sqlalchemy import create_engine
    with create_engine(url).begin() as c:
        c.execute(text(
            "insert into source_events (event_id, org_id, connection_id, source, object_type, source_object_id, "
            "parent_object_id, dedup_key, actor, occurred_at, recipients) values (:e, :o, 'con_h02', 'gmail', :ot, :e, "
            ":p, :e, cast(:a as jsonb), :at, '{}')"),
            {"e": eid, "o": ORG, "ot": object_type, "p": parent, "a": json.dumps({"email": sender, "type": "external_contact"}),
             "at": at})
        c.execute(text("insert into raw_payloads (id, org_id, event_id, enc_content, expires_at) "
                       "values (:i, :o, :e, :c, :x)"),
                  {"i": f"rp_{eid}", "o": ORG, "e": eid, "c": encrypt(json.dumps({"subject": "Deck"}), KEY),
                   "x": NOW + timedelta(days=90)})
    assert PostgresSignalStore(url).put([QualifiedSignalRow(
        signal_id=f"sig_{eid}", org_id=ORG, subject_key="thread:any", event_id=eid, trace_id="tr_h02",
        signal_type="contract_renewal", importance_bp=5000, importance_version="v", confidence_bp=8000,
        extraction_ref=f"struct:{eid}", state="active", occurred_at=at,
        evidence_refs=({"source_ref": eid, "quote": QUOTE, "start_offset": 0, "end_offset": len(QUOTE)},))]) == 1


def _rows(url):
    from sqlalchemy import create_engine
    with create_engine(url).connect() as c:
        return {r.event_id: r for r in c.execute(text(
            "select event_id, thread_key, direction, ball_in_court from qualified_signals where org_id = :o"), {"o": ORG})}


def test_a_stored_signal_gets_the_thread_capture_would_have_given_it(url, capsys):
    from scripts.backfill_signal_threads import main
    _event(url, "evt_h02_in", object_type="email_message", sender="priya@acme.test", parent="th_1", at=NOW)
    _event(url, "evt_h02_out", object_type="email_message", sender="founder@nimbus.test", parent="th_1",
           at=NOW + timedelta(hours=1))
    _event(url, "evt_h02_cal", object_type="calendar_event", sender="priya@acme.test", parent=None, at=NOW)
    assert main(["--database-url", url, "--org", ORG, f"--crypto-key={KEY}"]) == 0
    assert all(r.thread_key is None for r in _rows(url).values()), "a dry run wrote"
    assert main(["--database-url", url, "--org", ORG, f"--crypto-key={KEY}", "--apply"]) == 0
    rows = _rows(url)
    assert (rows["evt_h02_in"].thread_key, rows["evt_h02_in"].direction, rows["evt_h02_in"].ball_in_court) == (
        "thread:th_1", "inbound", "us")
    assert (rows["evt_h02_out"].thread_key, rows["evt_h02_out"].direction, rows["evt_h02_out"].ball_in_court) == (
        "thread:th_1", "outbound", "them")
    assert rows["evt_h02_cal"].thread_key is None                         # not a conversation: no thread to invent
    capsys.readouterr()
    assert main(["--database-url", url, "--org", ORG, f"--crypto-key={KEY}"]) == 0
    assert "signals with no thread: 0" in capsys.readouterr().out          # a second run finds none


def test_an_unreadable_payload_is_left_as_it_is_and_counted(url, capsys):
    from scripts.backfill_signal_threads import main
    _event(url, "evt_h02_bad", object_type="email_message", sender="priya@acme.test", parent="th_2", at=NOW)
    assert main(["--database-url", url, "--org", ORG, f"--crypto-key=XeFPR4cGtS27-bYSLhUr7yzd8XLAoJQXf0QVQeykRNM=",
                 "--apply"]) == 0
    assert _rows(url)["evt_h02_bad"].thread_key is None
    assert "payload_unreadable" in capsys.readouterr().out
