"""A three-hour sweep, and this loop is where it sat.

    pytest tests/context/test_receipts_are_written_in_one_round_trip.py -q

MEASURED, NOT GUESSED. A full `process_pending` on the pilot took ~3 hours on 2026-09-16. Eleven
stack dumps taken 300 seconds apart through that run land on:

    4  support_situations._write_fact
    4  outreach_situations.refresh_state_situations
    3  derived_provenance.write_fact_source_refs   <- the leaf both of the above call
    2  support_situations.refresh_support_situations

`write_fact_source_refs` issued ONE INSERT PER RECEIPT inside a Python loop. The pilot holds 8,532
`graph_source_refs` rows and a sweep rewrites most of them, so that is thousands of separate round
trips to a remote pooler where each one costs tens of milliseconds. Nothing about the SQL was
wrong; it was executed one row at a time.

WHAT THIS CHANGES AND WHAT IT MUST NOT. The rows written, their ids, their conflict behaviour and
the delete that precedes them are IDENTICAL — same deterministic `source_ref_id`, same
`on conflict do update`, same "other writers' refs are never deleted here". The only difference is
that the driver is handed every row at once instead of being asked once per row.

THE DETERMINISTIC ID IS THE WHOLE SAFETY. `ref_derived_<sha256(org|fact|event)[:32]>` means a
replayed sweep addresses exactly the rows it addressed before, so batching cannot duplicate
anything that single-stepping would not have duplicated.
"""
from __future__ import annotations

import hashlib

import pytest
from sqlalchemy import create_engine, text

from genios_engine.context.derived_provenance import EventReceipt, write_fact_source_refs

pytestmark = pytest.mark.unit

ORG = "org1"
FACT = "fv_1"


@pytest.fixture
def conn():
    engine = create_engine("sqlite://")
    with engine.begin() as c:
        c.execute(text("""create table graph_source_refs (
            source_ref_id text primary key, org_id text, fact_version_id text, event_id text,
            source text, source_object_id text, independence_group text, evidence text,
            extractor_version text)"""))
        yield c


def receipt(event_id, *, source="gmail", group=None, evidence=None):
    return EventReceipt(event_id=event_id, source=source, independence_group=group or "g1",
                        occurred_at=None, source_object_id=f"obj_{event_id}",
                        evidence=evidence or {"text": f"quote for {event_id}"})


def rows(conn):
    return [tuple(r) for r in conn.execute(text(
        "select source_ref_id, event_id, source from graph_source_refs order by event_id"))]


def test_every_receipt_is_written(conn) -> None:
    write_fact_source_refs(conn, org_id=ORG, fact_version_id=FACT,
                           receipts=tuple(receipt(f"evt_{i}") for i in range(5)))
    assert len(rows(conn)) == 5


def test_the_ids_are_the_same_deterministic_ids_as_before(conn) -> None:
    """THE SAFETY THAT MAKES BATCHING SOUND. A replayed sweep must address exactly the rows it
    addressed before — that is what makes `on conflict do update` an update rather than a
    duplicate."""
    write_fact_source_refs(conn, org_id=ORG, fact_version_id=FACT, receipts=(receipt("evt_a"),))
    digest = hashlib.sha256(f"{ORG}|{FACT}|evt_a".encode()).hexdigest()[:32]
    assert rows(conn)[0][0] == f"ref_derived_{digest}"


def test_a_repeat_write_updates_rather_than_duplicates(conn) -> None:
    write_fact_source_refs(conn, org_id=ORG, fact_version_id=FACT,
                           receipts=(receipt("evt_a", source="gmail"),))
    write_fact_source_refs(conn, org_id=ORG, fact_version_id=FACT,
                           receipts=(receipt("evt_a", source="gcal"),))
    assert rows(conn) == [(rows(conn)[0][0], "evt_a", "gcal")]


def test_a_receipt_that_disappears_is_removed(conn) -> None:
    """The delete before the insert is why this is a REPLACE. A membership change must not leave
    evidence from an older value of the same deterministic fact version standing."""
    write_fact_source_refs(conn, org_id=ORG, fact_version_id=FACT,
                           receipts=(receipt("evt_a"), receipt("evt_b")))
    write_fact_source_refs(conn, org_id=ORG, fact_version_id=FACT, receipts=(receipt("evt_a"),))
    assert [r[1] for r in rows(conn)] == ["evt_a"]


def test_duplicate_event_ids_collapse(conn) -> None:
    """Two receipts for one event are one row — the loop deduplicated by event id and the batch
    must too."""
    write_fact_source_refs(conn, org_id=ORG, fact_version_id=FACT,
                           receipts=(receipt("evt_a", source="gmail"),
                                     receipt("evt_a", source="gcal")))
    assert len(rows(conn)) == 1


def test_the_batch_never_carries_one_id_twice(conn) -> None:
    """CHECKED ON THE PARAMETERS, NOT ON THE RESULT, and the difference is a production outage.

    This suite runs on SQLite, which accepts a batch containing the same primary key twice and
    quietly applies the last one. POSTGRES DOES NOT: `ON CONFLICT DO UPDATE` raises "cannot affect
    row a second time", and the whole fact's write aborts. So a lost de-duplication passes every
    behavioural assertion here and fails on the only database that matters — the same SQLite
    blind spot that let a `repr()` into a jsonb column earlier in this work and killed a pass
    invisibly.

    The rows handed to the driver are therefore inspected directly."""
    seen: list = []
    real = conn.execute

    def capture(statement, params=None, *a, **k):
        if isinstance(params, list):
            seen.append(params)
        return real(statement, params, *a, **k) if params is not None else real(statement)

    conn.execute = capture                       # type: ignore[method-assign]
    try:
        write_fact_source_refs(conn, org_id=ORG, fact_version_id=FACT,
                               receipts=(receipt("evt_a", source="gmail"),
                                         receipt("evt_a", source="gcal"),
                                         receipt("evt_b")))
    finally:
        conn.execute = real                      # type: ignore[method-assign]
    assert seen, "no batch was sent"
    ids = [row["id"] for row in seen[0]]
    assert len(ids) == len(set(ids)), (
        f"the batch carries a duplicate source_ref_id: {ids} — SQLite tolerates this and "
        f"Postgres aborts the fact's entire write")


def test_no_receipts_writes_nothing_and_still_clears(conn) -> None:
    write_fact_source_refs(conn, org_id=ORG, fact_version_id=FACT, receipts=(receipt("evt_a"),))
    write_fact_source_refs(conn, org_id=ORG, fact_version_id=FACT, receipts=())
    assert rows(conn) == []


def test_it_does_not_execute_once_per_receipt(conn) -> None:
    """THE POINT OF THE UNIT. Counted at the connection, because that is what a round trip is.
    Six receipts must not cost six executes — one delete plus one batched insert is the shape."""
    calls = {"n": 0}
    real = conn.execute

    def counting(*a, **k):
        calls["n"] += 1
        return real(*a, **k)

    conn.execute = counting                      # type: ignore[method-assign]
    try:
        write_fact_source_refs(conn, org_id=ORG, fact_version_id=FACT,
                               receipts=tuple(receipt(f"evt_{i}") for i in range(6)))
    finally:
        conn.execute = real                      # type: ignore[method-assign]
    assert calls["n"] <= 2, (
        f"{calls['n']} executes for 6 receipts — this is the per-row shape that put a sweep at "
        f"three hours")
