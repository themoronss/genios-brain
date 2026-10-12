"""STEP-18 B13 · a screen follow-up is ONE active observation in memory, however often it changes.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… pytest tests/test_a_followup_has_one_observation_pg.py -q

`yc2_w27_s18` M48.C2.L-contract.V0.U12 (`0211`) and M48.C2.L-data.V0.U06 (`reason/moments/
screen_memory`, L2 Plane R writing into L3 Context Graph).

⛔ WHAT WAS WRONG. `reason/moments/followups.upsert` clears `graph_written_at` when a follow-up's
words, date or person change, so the next promotion writes it to memory again — and each write mints
a fresh observation id (`context/graph_store.write_observation`). Every version stayed an ACTIVE
observation beside the next: one ask, three observations, counted three times by every reader of a
person's evidence. The follow-up now names the observation it became (`0211`), and the next write
retires that one before it writes its own.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import text

from genios_engine.reason.moments import followups
from genios_engine.reason.moments.screen_memory import write_items

pytestmark = pytest.mark.pg

ORG = "org_s18_one_followup"
SEAT = "seat_s18"
THREAD = "wa:priya"
T0 = datetime(2026, 10, 12, 9, 0, tzinfo=timezone.utc)


@pytest.fixture
def engine(pg_store):
    _reset(pg_store.engine)
    with pg_store.engine.begin() as c:
        c.execute(text("insert into orgs (id, name) values (:o, 'One follow-up')"), {"o": ORG})
    yield pg_store.engine
    _reset(pg_store.engine)


def _reset(engine) -> None:
    with engine.begin() as c:
        for table in ("graph_source_refs", "graph_observations", "screen_followups"):
            c.execute(text(f"delete from {table} where org_id = :o"), {"o": ORG})
        c.execute(text("delete from orgs where id = :o"), {"o": ORG})


def _upsert(engine, note: str, *, now: datetime, due: datetime | None = None) -> dict:
    return followups.upsert(engine, org_id=ORG, seat_id=SEAT, kind="ask", note=note, who=None,
                            due_at=due, thread_key=THREAD, app="whatsapp", topic="the deck",
                            tz_name=None, now=now)


def _write(engine, event_id: str, *, now: datetime) -> int:
    return write_items(engine, org_id=ORG, seat_id=SEAT, seat_email=None, thread_key=THREAD,
                       event_id=event_id, now=now)


def _observations(engine, followup_id: str) -> list[tuple[str, str]]:
    """(status, the words the observation carries) for every observation of one follow-up."""
    with engine.connect() as c:
        rows = c.execute(text(
            "select o.status, r.evidence from graph_observations o "
            "join graph_source_refs r on r.org_id = o.org_id and r.observation_id = o.observation_id "
            "where o.org_id = :o order by o.created_at, o.observation_id"), {"o": ORG}).all()
    out = []
    for status, evidence in rows:
        evidence = evidence if isinstance(evidence, dict) else json.loads(evidence)
        if evidence.get("followup_id") == followup_id:
            out.append((status, evidence.get("text")))
    return out


def test_a_follow_up_that_changes_twice_is_one_active_observation(engine):
    item = _upsert(engine, "Send Priya the deck", now=T0)
    assert _write(engine, "evt_screen_1", now=T0) == 1
    _upsert(engine, "Send Priya the deck and the model", now=T0 + timedelta(hours=1))
    assert _write(engine, "evt_screen_2", now=T0 + timedelta(hours=1)) == 1
    _upsert(engine, "Send Priya the deck and the model", now=T0 + timedelta(hours=2),
            due=T0 + timedelta(days=2))
    assert _write(engine, "evt_screen_3", now=T0 + timedelta(hours=2)) == 1
    seen = _observations(engine, item["id"])
    assert [s for s, _ in seen] == ["superseded", "superseded", "active"], seen
    assert seen[-1][1] == "Send Priya the deck and the model", "the active one says what is true now"


def test_an_unchanged_sighting_writes_nothing_and_retires_nothing(engine):
    item = _upsert(engine, "Send Priya the deck", now=T0)
    _write(engine, "evt_screen_1", now=T0)
    _upsert(engine, "Send Priya the deck", now=T0 + timedelta(hours=1))
    assert _write(engine, "evt_screen_2", now=T0 + timedelta(hours=1)) == 0
    assert _observations(engine, item["id"]) == [("active", "Send Priya the deck")]


def test_the_follow_up_names_the_observation_it_became(engine):
    item = _upsert(engine, "Send Priya the deck", now=T0)
    _write(engine, "evt_screen_1", now=T0)
    with engine.connect() as c:
        named = c.execute(text("select observation_id from screen_followups where id = :i"),
                          {"i": item["id"]}).scalar()
        active = c.execute(text(
            "select observation_id from graph_observations where org_id = :o and status = 'active'"),
            {"o": ORG}).scalars().all()
    assert named is not None and active == [named]


def test_another_follow_ups_observation_is_never_retired(engine):
    """The retirement is by the row's own named observation — never by kind, person or thread."""
    first = _upsert(engine, "Send Priya the deck", now=T0)
    other = followups.upsert(engine, org_id=ORG, seat_id=SEAT, kind="ask", note="Book the call",
                             who=None, due_at=None, thread_key=THREAD, app="whatsapp",
                             topic="the call", tz_name=None, now=T0)
    assert _write(engine, "evt_screen_1", now=T0) == 2
    _upsert(engine, "Send Priya the deck today", now=T0 + timedelta(hours=1))
    _write(engine, "evt_screen_2", now=T0 + timedelta(hours=1))
    assert _observations(engine, other["id"]) == [("active", "Book the call")]
    assert [s for s, _ in _observations(engine, first["id"])] == ["superseded", "active"]
