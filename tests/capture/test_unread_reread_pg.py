"""Mail captured while a tenant's L1 was off is queued, rebuilt and set aside safely — real Postgres.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://postgres@localhost:5433/<scratch> \\
        pytest tests/capture/test_unread_reread_pg.py -q

RESTATED (STEP-05, `yc2_w27_s05 · M23.C4.L-integration.V3.U03`). `find_unread` was this mail's door: it
is the same population as every other kept mail nothing read (`queue_unread`, `M23.C4.L-logic.V2.U01`),
so it now joins the one re-read ladder and `find_unread` is gone. Each claim below is held as before,
asked of the queue and the ladder instead.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from cryptography.fernet import Fernet
from sqlalchemy import text

from genios_engine.capture.landing import unread
from genios_engine.contracts.source_event import compute_dedup_key
from genios_engine.platform.crypto import encrypt

KEY = Fernet.generate_key().decode()
NOW = datetime.now(timezone.utc)


@pytest.fixture
def engine(live_db_url):
    if not live_db_url:
        pytest.skip("GENIOS_TEST_DATABASE_URL not set — needs real Postgres")
    from genios_engine.platform.db import get_engine
    return get_engine(live_db_url)


@pytest.fixture
def org(engine):
    org_id = f"org_t{uuid.uuid4().hex[:12]}"
    with engine.begin() as c:
        c.execute(text("insert into orgs (id, name) values (:o, 'unread test')"), {"o": org_id})
        c.execute(text("insert into l1_semantic_activation (org_id, enabled_at, enabled_by) "
                       "values (:o, :at, 'test')"), {"o": org_id, "at": NOW})
    yield org_id
    with engine.begin() as c:
        for table in ("parked_events", "l1_extraction_results", "raw_payloads",
                      "l2_processing_runs", "source_events", "l1_semantic_activation"):
            c.execute(text(f"delete from {table} where org_id = :o"), {"o": org_id})
        c.execute(text("delete from orgs where id = :o"), {"o": org_id})


def _event(engine, org_id, mid, *, captured_at, payload=None, source="gmail",
           object_type="email_message", content_version=None):
    event_id = f"evt_{uuid.uuid4().hex[:12]}"
    with engine.begin() as c:
        c.execute(text(
            "insert into source_events (event_id, org_id, connection_id, source, object_type, "
            " source_object_id, dedup_key, actor, occurred_at, captured_at, sync_mode, "
            " payload_ref, recipients, outcome) "
            "values (:e, :o, 'con_x', :src, :ot, :mid, :dk, cast(:actor as jsonb), :occ, :cap, "
            " 'backfill', :pay, :rcp, 'emitted')"),
            {"e": event_id, "o": org_id, "src": source, "ot": object_type, "mid": mid,
             "dk": compute_dedup_key(source, object_type, mid, content_version),
             "actor": json.dumps({"type": "external_contact", "email": "a@x.com",
                                  "name": "Ann"}),
             "occ": NOW - timedelta(days=3), "cap": captured_at, "pay": f"pay_{event_id}",
             "rcp": ["me@co.com"]})
        c.execute(text(
            "insert into raw_payloads (id, org_id, event_id, content_type, enc_content, "
            " expires_at) values (:id, :o, :e, 'application/json', :enc, :exp)"),
            {"id": f"pay_{event_id}", "o": org_id, "e": event_id,
             "enc": encrypt(json.dumps(payload or {"subject": "Hi", "body": "Quote by Friday"}),
                            KEY),
             "exp": NOW + timedelta(days=30)})
    return event_id


def _due(engine, org) -> list:
    """Queue what nothing read, then the ladder's due rows — the pass `_reread_unread` makes."""
    unread.queue_unread(engine, org)
    return unread.find_parked_extractions(engine, org)


def test_only_mail_captured_before_the_switch_and_never_read_is_found(engine, org):
    """Restated: m2 (captured at switch-on, still inside the grace — a capture that may still be
    reading it) and the versioned object are left out as before; m3 was read — by Layer 2's own
    legacy extraction (its row carries no profile), which is what an L2 run with no L1 extraction
    meant here. A done L2 run alone no longer means read: an archive's metadata write is one."""
    before = _event(engine, org, "m1", captured_at=NOW - timedelta(hours=2))
    _event(engine, org, "m2", captured_at=NOW + timedelta(minutes=1))       # after switch-on
    read = _event(engine, org, "m3", captured_at=NOW - timedelta(hours=2))
    _event(engine, org, "c1", captured_at=NOW - timedelta(hours=2), source="gcal",
           object_type="calendar_event", content_version="v7")              # versioned object
    with engine.begin() as c:
        c.execute(text("insert into l2_processing_runs (org_id, event_id, status) "
                       "values (:o, :e, 'done')"), {"o": org, "e": read})
        c.execute(text("insert into l1_extraction_results (processing_key, org_id, event_id, "
                       "output) values (:k, :o, :e, cast('{}' as jsonb))"),
                  {"k": f"l2_{read}", "o": org, "e": read})

    assert [r.event_id for r in _due(engine, org)] == [before]


def test_the_raw_object_is_rebuilt_from_what_was_stored(engine, org):
    _event(engine, org, "m1", captured_at=NOW - timedelta(hours=2),
           payload={"subject": "Pricing", "body": "Send the quote"})
    row = _due(engine, org)[0]

    raw = unread.to_raw_object(row, KEY)

    assert (raw.source, raw.object_type, raw.source_object_id) == ("gmail", "email_message", "m1")
    assert raw.rereading == unread.EXTRACTION_NEVER_RAN       # kept already: the gate reads it
    assert raw.raw == {"subject": "Pricing", "body": "Send the quote"}
    assert (raw.actor_email, raw.actor_name) == ("a@x.com", "Ann")
    assert raw.recipients == ("me@co.com",)
    assert raw.occurred_at.tzinfo is not None


def test_a_wrong_key_is_a_skip_not_a_crash(engine, org):
    _event(engine, org, "m1", captured_at=NOW - timedelta(hours=2))
    row = _due(engine, org)[0]

    assert unread.to_raw_object(row, Fernet.generate_key().decode()) is None


def test_set_aside_frees_the_key_and_restore_returns_only_what_did_not_land(engine, org):
    landed = _event(engine, org, "m1", captured_at=NOW - timedelta(hours=2))
    failed = _event(engine, org, "m2", captured_at=NOW - timedelta(hours=2))

    assert unread.set_aside(engine, org, [landed, failed]) == 2
    # The re-capture of m1 lands under its original key; m2's capture failed.
    _event(engine, org, "m1", captured_at=NOW + timedelta(minutes=1))
    assert unread.restore(engine, org, [landed, failed]) == 1

    with engine.connect() as c:
        rows = dict(c.execute(text("select event_id, outcome from source_events "
                                   "where org_id = :o and event_id in (:a, :b)"),
                              {"o": org, "a": landed, "b": failed}).fetchall())
    assert rows == {landed: "superseded", failed: "emitted"}
    assert [r.event_id for r in _due(engine, org)] == [failed]        # tried again next pass


def test_a_pass_killed_before_restore_is_recovered_by_the_next_pass(engine, org):
    """A deploy between `set_aside` and `restore` leaves rows superseded with a free key."""
    landed = _event(engine, org, "m1", captured_at=NOW - timedelta(hours=2))
    orphan = _event(engine, org, "m2", captured_at=NOW - timedelta(hours=2))
    unread.set_aside(engine, org, [landed, orphan])
    _event(engine, org, "m1", captured_at=NOW + timedelta(minutes=1))   # m1 re-landed, then death

    assert _due(engine, org) == []                                     # the orphan is invisible
    assert unread.recover_orphans(engine, org) == 1

    assert [r.event_id for r in _due(engine, org)] == [orphan]
    with engine.connect() as c:
        assert c.execute(text("select outcome from source_events where event_id = :e"),
                         {"e": landed}).scalar() == "superseded"
