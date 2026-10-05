"""STEP-18 B20 / B18 · a fingerprint claim held by an event that was set aside is void.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… pytest tests/capture/test_a_claim_by_a_gone_event_is_void_pg.py -q

⛔ WHAT WAS WRONG. A message's first copy claims its fingerprint, and every later copy is skipped as
`seen_on_screen`. Event ids are minted fresh on every landing, and the claim outlived its event —
so a message re-landed to be read again (the unread re-read, the re-read of a parked extraction, a
targeted re-fetch) found itself "already claimed" by the copy it was replacing, and was never read.
The L1 G7/G8/G10 gates failed exactly this way: their second sweep skipped 132 of 132 messages.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine, text

from genios_engine.capture.screen.fingerprint import claim, message_fp

URL = os.environ.get("GENIOS_TEST_DATABASE_URL")
pytestmark = [pytest.mark.pg,
              pytest.mark.skipif(not URL, reason="GENIOS_TEST_DATABASE_URL not set")]

ORG = "org_fp_gone_event"
T = datetime(2026, 10, 3, 11, 17, tzinfo=timezone.utc)
FP = message_fp("founder@genios.test", T, "Can we move the review to Thursday?")


@pytest.fixture
def engine():
    from genios_engine.platform.db import get_engine
    eng = get_engine(URL)
    with eng.begin() as c:
        reqd = c.execute(text(
            "select column_name, data_type from information_schema.columns where table_name='orgs' "
            "and is_nullable='NO' and column_default is null and column_name<>'id'")).all()
        cols, vals = ["id"], {"id": ORG}
        for r in reqd:
            cols.append(r.column_name)
            vals[r.column_name] = ("2026-01-01T00:00:00Z" if "time" in r.data_type
                                   or "date" in r.data_type
                                   else 0 if "int" in r.data_type or "numeric" in r.data_type
                                   else ORG)
        c.execute(text(f"insert into orgs ({','.join(cols)}) values "
                       f"({','.join(':' + k for k in cols)}) on conflict do nothing"), vals)
        c.execute(text("delete from message_fingerprints where org_id = :o"), {"o": ORG})
        c.execute(text("delete from source_events where org_id = :o"), {"o": ORG})
    yield eng


def _event(c, event_id: str, *, source: str = "gmail", outcome: str = "emitted") -> None:
    """A real `source_events` row, every NOT NULL column filled."""
    reqd = c.execute(text(
        "select column_name, data_type from information_schema.columns "
        "where table_name='source_events' and is_nullable='NO' and column_default is null")).all()
    vals = {"event_id": event_id, "org_id": ORG, "source": source, "object_type": "email_message",
            "outcome": outcome, "occurred_at": T}
    for r in reqd:
        if r.column_name not in vals:
            vals[r.column_name] = (T if "time" in r.data_type or "date" in r.data_type
                                   else 0 if "int" in r.data_type or "numeric" in r.data_type
                                   else "{}" if "json" in r.data_type
                                   else f"{r.column_name}_{event_id}")
    c.execute(text(f"insert into source_events ({','.join(vals)}) values "
                   f"({','.join(':' + k for k in vals)})"), vals)


def test_a_claim_by_a_set_aside_event_is_void_and_the_new_copy_is_read(engine):
    with engine.begin() as c:
        _event(c, "evt_first")
        assert claim(c, ORG, [FP], "gmail", "evt_first") == {FP: "evt_first"}
    with engine.begin() as c:
        # `capture/landing/unread.set_aside` — the copy is being replaced, not deleted
        c.execute(text("update source_events set outcome = 'superseded' where event_id = 'evt_first'"))
        _event(c, "evt_relanded")
        assert claim(c, ORG, [FP], "gmail", "evt_relanded") == {FP: "evt_relanded"}, (
            "the re-landed copy was skipped as already claimed by the copy it replaced")
    with engine.connect() as c:
        rows = c.execute(text("select event_id from message_fingerprints where org_id = :o"),
                         {"o": ORG}).scalars().all()
    assert rows == ["evt_relanded"], f"the void claim is still on the table: {rows}"


def test_a_claim_by_a_live_copy_still_suppresses(engine):
    """The rule P2 §3.3 exists for is unchanged: a live screen copy stays canonical."""
    with engine.begin() as c:
        _event(c, "evt_screen", source="screen_session")
        assert claim(c, ORG, [FP], "screen_session", "evt_screen") == {FP: "evt_screen"}
        _event(c, "evt_gmail")
        assert claim(c, ORG, [FP], "gmail", "evt_gmail") == {FP: "evt_screen"}


def test_a_claim_by_an_event_with_no_row_is_still_honoured(engine):
    """The boundary, stated. A deletion is the deleting path's to clean up (the tenant reset and
    the disconnect-with-wipe delete their fingerprints); a claim written in isolation carries an id
    that never had a row, and it keeps today's meaning."""
    with engine.begin() as c:
        assert claim(c, ORG, [FP], "screen_session", "evt_no_row") == {FP: "evt_no_row"}
        _event(c, "evt_gmail_2")
        assert claim(c, ORG, [FP], "gmail", "evt_gmail_2") == {FP: "evt_no_row"}
