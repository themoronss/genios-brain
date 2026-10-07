"""STEP-06 · the parked drain takes the rows it can re-admit — 200 rows another drain owns can no longer
starve them.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… pytest tests/capture/parked/test_the_drain_never_starves.py -q

Tree `yc2_w27_s06 · M24.C5.L-data.V1.U01` (`speedrun008/YC-II W27/` STEP-06 §1, §8.2). `drain_parked`
selected the OLDEST 200 pending parks and judged stops, then counted and skipped the ones another
drain owns (refetch, recapture, re-extraction) where they stood. Two hundred such rows older than a
re-admittable one meant the drain examined them every tick and never reached it. The limited
selection now takes only the rows this drain re-admits; the others are counted by one unlimited
read, so the report still says how many each class holds.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import text

from genios_engine.capture.parked.drain import drain_parked
from genios_engine.platform.db import get_engine

pytestmark = pytest.mark.pg

ORG = "org_s06_drain_starves"
NOW = datetime(2026, 1, 14, 9, 0, tzinfo=timezone.utc)


@pytest.fixture
def engine(live_db_url):
    if not live_db_url:
        pytest.skip("GENIOS_TEST_DATABASE_URL not set — real-Postgres drain tests skipped")
    eng = get_engine(live_db_url)
    _reset(eng)
    with eng.begin() as c:
        c.execute(text("insert into orgs (id, name) values (:o, 'drain starve')"), {"o": ORG})
    yield eng
    _reset(eng)


def _reset(eng) -> None:
    with eng.begin() as c:
        for table in ("raw_payloads", "parked_events", "source_events"):
            c.execute(text(f"delete from {table} where org_id=:o"), {"o": ORG})
        c.execute(text("delete from orgs where id=:o"), {"o": ORG})


def _park(c, event_id: str, reason: str, *, parked_at: datetime, payload: bool) -> None:
    c.execute(text(
        "insert into source_events (event_id, org_id, connection_id, source, object_type, "
        "source_object_id, dedup_key, actor, occurred_at, captured_at, outcome) "
        "values (:e, :o, 'conn_1', 'gmail', 'email_message', :soid, :dedup, "
        "cast('{}' as jsonb), :at, :at, 'parked')"),
        {"e": event_id, "o": ORG, "soid": f"m::{event_id}", "dedup": f"d_{event_id}",
         "at": parked_at})
    c.execute(text(
        "insert into parked_events (event_id, org_id, source, reason_code, stage, status, "
        "created_at) values (:e, :o, 'gmail', :r, 'gate', 'pending', :at)"),
        {"e": event_id, "o": ORG, "r": reason, "at": parked_at})
    if payload:
        c.execute(text(
            "insert into raw_payloads (id, org_id, event_id, content_type, enc_content, expires_at) "
            "values (:id, :o, :e, 'application/json', 'x', :exp)"),
            {"id": f"pay_{event_id}", "o": ORG, "e": event_id, "exp": NOW + timedelta(days=30)})


def test_a_readmittable_park_behind_two_hundred_owned_elsewhere_is_readmitted(engine):
    with engine.begin() as c:
        for i in range(250):
            _park(c, f"evt_doc_{i:03d}", "DOC-02", parked_at=NOW - timedelta(days=10, minutes=i),
                  payload=False)
        _park(c, "evt_junk", "llm_junk_unconfident", parked_at=NOW - timedelta(days=1),
              payload=True)
    out = drain_parked(engine, org_id=ORG, limit=200, now=NOW)
    assert out["reinjected"] == 1, out
    # and the report still accounts for every row another drain owns, and how old they are
    assert out["needs_refetch"] == 250 and out["examined"] == 251, out
    assert out["stale"] == 250 and out["by_reason"]["DOC-02"]["seen"] == 250
    with engine.connect() as c:
        outcome = c.execute(text("select outcome from source_events where event_id='evt_junk'")
                            ).scalar()
    assert outcome == "emitted"
