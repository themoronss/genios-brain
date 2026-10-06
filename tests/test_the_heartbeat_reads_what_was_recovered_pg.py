"""STEP-05 · the chain's re-read reads what a recovery left — no script, no operator.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… pytest tests/test_the_heartbeat_reads_what_was_recovered_pg.py -q

`api/routes._reread_unread` (tree `yc2_w27_s05 · M23.C4.L-integration.V3.U03`), which every chain pass
runs before Layer 2 drains. It used to read two kinds of mail — captured while L1 was off
(`find_unread`) and extraction parks — and nothing a RECOVERY left: a park the drain re-admitted, a
promotion out of the archive, a refetch stayed emitted and unread for ever. Now each pass files every
kept mail nothing read into the ladder (`unread.queue_unread`) and reads the ladder's due rows through
the capture door, each one carrying why it is read again so the gate reads it instead of judging it out
(W-06). Here the door itself is the test's: it lands each object as a fresh capture would, so the
ledger, the restore and the settle are the real ones.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from sqlalchemy import text

from genios_engine.contracts.source_event import compute_dedup_key
from genios_engine.platform.crypto import encrypt

pytestmark = pytest.mark.pg

NOW = datetime.now(timezone.utc)


@pytest.fixture
def wired(pg_store, monkeypatch):
    """`api/routes` on the scratch database, a tenant with Layer 1 on and one Gmail connection, and
    a capture door that lands what it is handed under the object's own key."""
    from genios_engine.api import routes
    from genios_engine.platform.config import get_settings

    org = f"org_hb_{uuid.uuid4().hex[:8]}"
    with pg_store.engine.begin() as c:
        c.execute(text("insert into orgs (id, name) values (:o, 'heartbeat re-read')"), {"o": org})
        c.execute(text("insert into l1_semantic_activation (org_id, enabled_at, enabled_by) "
                       "values (:o, :at, 'test')"), {"o": org, "at": NOW - timedelta(days=30)})
    conn = SimpleNamespace(connection_id=f"con_{org}_gmail", org_id=org, source_type="gmail")
    handed: list = []

    def _ingest(objects, *, org_id, connection_id, wiring):
        with pg_store.engine.begin() as c:
            for raw in objects:
                handed.append(raw)
                c.execute(text(
                    "insert into source_events (event_id, org_id, connection_id, source, "
                    " object_type, source_object_id, dedup_key, actor, occurred_at, outcome) "
                    "values (:e, :o, :c, :s, :t, :sid, :dk, cast(:a as jsonb), :at, 'emitted')"),
                    {"e": f"evt_new_{uuid.uuid4().hex[:8]}", "o": org_id, "c": connection_id,
                     "s": raw.source, "t": raw.object_type, "sid": raw.source_object_id,
                     "dk": compute_dedup_key(raw.source, raw.object_type, raw.source_object_id,
                                             None),
                     "a": json.dumps({"email": raw.actor_email}), "at": raw.occurred_at})
        return SimpleNamespace(results=[SimpleNamespace(outcome="emitted")] * len(objects))

    monkeypatch.setattr(routes, "_graph", pg_store)
    monkeypatch.setattr(routes, "_connections", SimpleNamespace(
        get=lambda cid: conn if cid == conn.connection_id else None,
        list_active=lambda source_type=None: [conn]))
    monkeypatch.setattr(routes, "_llm_over_daily_cap", lambda _org: False)
    monkeypatch.setattr(routes, "_push_wiring_for", lambda _conn: "wiring")
    monkeypatch.setattr(routes, "_l1_stores", lambda: None)
    monkeypatch.setattr(routes, "ingest_pushed_objects", _ingest)
    monkeypatch.setattr(routes, "finalize_l1", lambda *_a, **_k: None)
    yield SimpleNamespace(routes=routes, org=org, engine=pg_store.engine, handed=handed,
                          key=get_settings().crypto_key, connection=conn.connection_id)
    with pg_store.engine.begin() as c:
        for table in ("parked_events", "raw_payloads", "source_events", "l1_semantic_activation"):
            c.execute(text(f"delete from {table} where org_id = :o"), {"o": org})
        c.execute(text("delete from orgs where id = :o"), {"o": org})


def _kept(w, *, why: str, park: str | None = None) -> str:
    """A kept mail a recovery left emitted and unread, captured a day ago."""
    event_id = f"evt_{uuid.uuid4().hex[:12]}"
    at = NOW - timedelta(days=1)
    with w.engine.begin() as c:
        c.execute(text(
            "insert into source_events (event_id, org_id, connection_id, source, object_type, "
            " source_object_id, dedup_key, actor, occurred_at, captured_at, recipients, outcome, "
            " attention, attention_reason) values (:e, :o, :c, 'gmail', 'email_message', :e, :dk, "
            " cast(:a as jsonb), :at, :at, :r, 'emitted', 'deep', :why)"),
            {"e": event_id, "o": w.org, "c": w.connection,
             "dk": compute_dedup_key("gmail", "email_message", event_id, None),
             "a": json.dumps({"type": "external_contact", "email": "pankaj@saka.test"}),
             "at": at, "r": ["meera@kite.test"], "why": why})
        c.execute(text(
            "insert into raw_payloads (id, org_id, event_id, content_type, enc_content, expires_at) "
            "values (:id, :o, :e, 'application/json', :enc, :exp)"),
            {"id": f"pay_{event_id}", "o": w.org, "e": event_id, "exp": NOW + timedelta(days=150),
             "enc": encrypt(json.dumps({"subject": "Intro", "body": "Pankaj, meet Meera."}), w.key)})
        if park:
            c.execute(text(
                "insert into parked_events (event_id, org_id, source, reason_code, stage, trace, "
                " status, created_at) values (:e, :o, 'gmail', :r, 'gate', cast('[]' as jsonb), "
                " 'recovered', :at)"), {"e": event_id, "o": w.org, "r": park, "at": at})
    return event_id


def _ledger(w) -> dict[str, tuple]:
    with w.engine.connect() as c:
        return {r.event_id: (r.outcome, r.status) for r in c.execute(text(
            "select se.event_id, se.outcome, pe.status from source_events se "
            "left join parked_events pe on pe.event_id = se.event_id where se.org_id = :o"),
            {"o": w.org})}


def test_a_pass_reads_what_every_recovery_left_and_says_why(wired):
    readmitted = _kept(wired, why="readmitted:low_relevance", park="low_relevance")
    promoted = _kept(wired, why="promoted:N-02")
    assert wired.routes._reread_unread(wired.org) == 2
    assert sorted(r.source_object_id for r in wired.handed) == sorted([readmitted, promoted])
    assert {r.rereading for r in wired.handed} == {"extraction_never_ran"}
    ledger = _ledger(wired)
    for old in (readmitted, promoted):
        assert ledger[old] == ("superseded", "superseded"), (old, ledger[old])


def test_a_second_pass_reads_nothing_twice(wired):
    _kept(wired, why="promoted:N-02")
    wired.routes._reread_unread(wired.org)
    wired.handed.clear()
    assert wired.routes._reread_unread(wired.org) == 0
    assert wired.handed == []
