"""D8 · `signal_conflicts` — the table doc 05 specified, doc 07 lists, and nothing ever created.

    GENIOS_TEST_DATABASE_URL=... ./.venv/bin/python -m pytest tests/capture/validate/test_conflict_store.py -q

THE DEFECT. ALG-12 detects a conflict in production — `sync_runner._detect_conflicts` runs over
every sweep — and the result dies with the `SyncSummary` that carried it. `contracts/conflict.py`
says of a `ConflictClaim`: *"Both of them are written to `signal_conflicts.claims` and neither is
ever pruned"*. There was no such table, so the design law that a conflict **always retains both
sides** was true only for the milliseconds between detection and garbage collection.

Two properties are tested against real PostgreSQL because neither can be proved anywhere else:

* a stored conflict READS BACK with both claims, both receipts and the same resolution — a
  round trip through jsonb is where a `Money` quietly becomes a dict and a rank becomes a float;
* the row LEAVES with the tenant. `api/account_routes._ORG_SCOPED_TABLES` executes
  `delete from {tbl}` with no try/except, so a table missing from that list leaks a deleted
  customer's contract amounts and quotes — and a table misspelled in it breaks every deletion.
  Both halves are asserted here, by running the erasure the route runs.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest

from genios_engine.capture.validate import conflict_store as S
from genios_engine.capture.validate.conflict import ConflictDetection, DetectedConflict
from genios_engine.contracts.conflict import (Authority, Conflict, ConflictClaim,
                                              ConflictResolution)
from genios_engine.contracts.evidence import EvidenceSpan
from genios_engine.contracts.units import Money

ORG = "org_conflict_store"
DETECTED = datetime(2026, 1, 21, 12, 0, tzinfo=timezone.utc)
SUBJECT = "contract:aws-enterprise-agreement"


def _span(quote: str, ref: str) -> EvidenceSpan:
    return EvidenceSpan(source_ref=ref, quote=quote, start_offset=0, end_offset=len(quote),
                        verified=True)


def _conflict() -> Conflict:
    """The headline fixture of doc 05: $74K signed against $84K in an email."""
    signed = ConflictClaim(value=Money(minor_units=7_400_000, currency="USD",
                                       as_written="$74,000"),
                           authority=Authority.SIGNED_DOCUMENT, authority_rank=6,
                           evidence=[_span("total annual commitment of $74,000",
                                           "chunk:aws_agreement.pdf:42")])
    email = ConflictClaim(value=Money(minor_units=8_400_000, currency="USD", as_written="$84K"),
                          authority=Authority.EMAIL_PROSE, authority_rank=2,
                          evidence=[_span("the $84K annual contract", "email:thread-8f2a")])
    return Conflict(field="contract.value", claims=[signed, email],
                    resolution=ConflictResolution.RESOLVED_BY_AUTHORITY,
                    resolved_value=signed.value, detected_at=DETECTED)


def _detection() -> ConflictDetection:
    return ConflictDetection(
        conflicts=(DetectedConflict(subject_key=SUBJECT, conflict=_conflict(),
                                    event_ids=("evt_attachment", "evt_message")),),
        total_detected=1)


# ── the shape, hermetically ───────────────────────────────────────────────────────────────────

def test_rows_carry_both_sides_and_a_deterministic_id():
    rows = S.rows_for(_detection(), org_id=ORG)

    assert len(rows) == 1
    row = rows[0]
    assert row.org_id == ORG and row.subject_key == SUBJECT
    assert row.field == "contract.value"
    assert row.resolution == "resolved_by_authority"
    assert len(row.claims) == 2, "a stored conflict that keeps one side is not a conflict record"
    assert row.event_ids == ("evt_attachment", "evt_message")
    # Content-addressed: the same detection re-run on a replay is the same row, not a second one.
    assert row.conflict_id == S.rows_for(_detection(), org_id=ORG)[0].conflict_id
    assert row.conflict_id != S.rows_for(_detection(), org_id="org_other")[0].conflict_id


def test_the_in_memory_store_round_trips_what_the_postgres_one_stores():
    store = S.InMemoryConflictStore()
    rows = S.rows_for(_detection(), org_id=ORG)

    assert store.put(rows) == 1
    back = store.get(ORG, rows[0].conflict_id)
    assert back is not None and back.claims == rows[0].claims
    assert store.get(ORG, "not-a-conflict") is None
    assert store.get("org_other", rows[0].conflict_id) is None, "a store with no tenant boundary"


# ── real PostgreSQL ───────────────────────────────────────────────────────────────────────────

@pytest.fixture()
def pg(live_db_url):
    if not live_db_url:
        pytest.skip("GENIOS_TEST_DATABASE_URL not set — real-Postgres conflict-store tests skipped")
    return live_db_url


def test_a_stored_conflict_reads_back_with_both_claims_and_both_receipts(pg):
    store = S.PostgresConflictStore(pg)
    org = _disposable_org(pg)
    rows = S.rows_for(_detection(), org_id=org)

    assert store.put(rows) == 1
    assert store.put(rows) == 1, "a replay must upsert its own row, never duplicate it"

    back = store.get(org, rows[0].conflict_id)
    assert back is not None
    assert back.resolution == "resolved_by_authority"
    assert back.detected_at == DETECTED
    values = sorted(c["value"]["minor_units"] for c in back.claims)
    assert values == [7_400_000, 8_400_000], "the losing claim did not survive the round trip"
    quotes = {c["evidence"][0]["quote"] for c in back.claims}
    assert "the $84K annual contract" in quotes, "the loser lost its receipt in storage"
    assert back.resolved_value["minor_units"] == 7_400_000
    _drop_org(pg, org)


def test_the_conflict_table_leaves_with_the_tenant(pg):
    """The erasure list at `api/account_routes.py` runs with no try/except. A table missing from
    it leaks; a table misspelled in it breaks every account deletion. Both are proved by running
    the real `_wipe` over a real row."""
    from sqlalchemy import text

    from genios_engine.api import account_routes
    from genios_engine.platform.db import get_engine

    assert S.CONFLICT_TABLE in account_routes._ORG_SCOPED_TABLES, (
        "signal_conflicts is not in the erasure list — a deleted tenant's contract amounts and "
        "quoted sentences stay in the database")

    store = S.PostgresConflictStore(pg)
    org = _disposable_org(pg)
    rows = S.rows_for(_detection(), org_id=org)
    store.put(rows)

    engine = get_engine(pg)
    with engine.begin() as conn:
        assert conn.execute(text(f"select count(*) from {S.CONFLICT_TABLE} where org_id=:o"),
                            {"o": org}).scalar() == 1
        # The route's own loop, over the route's own list — not a transcription of it.
        for table in account_routes._ORG_SCOPED_TABLES:
            conn.execute(text(f"delete from {table} where org_id=:o"), {"o": org})
        assert conn.execute(text(f"select count(*) from {S.CONFLICT_TABLE} where org_id=:o"),
                            {"o": org}).scalar() == 0
    _drop_org(pg, org)


def test_the_org_cascade_erases_conflicts_when_the_org_row_itself_goes(pg):
    """Belt and braces: `_wipe` is one path, `delete from orgs` is the other (migration 0033's
    doctrine). A conflict row must not be what blocks or survives an account deletion."""
    from sqlalchemy import text

    from genios_engine.platform.db import get_engine

    org = _disposable_org(pg)
    S.PostgresConflictStore(pg).put(S.rows_for(_detection(), org_id=org))
    engine = get_engine(pg)
    with engine.begin() as conn:
        conn.execute(text("delete from orgs where id=:o"), {"o": org})
        assert conn.execute(text(f"select count(*) from {S.CONFLICT_TABLE} where org_id=:o"),
                            {"o": org}).scalar() == 0


# ── the production caller ─────────────────────────────────────────────────────────────────────

def test_the_sweeps_conflicts_are_persisted_by_the_summary_writer():
    """WIRED. `sync_runner` computes `summary.conflicts` for every sweep and returned it to a
    caller that dropped it. `persist_sweep_conflicts` is the seam `api/routes` now calls after
    every `run_sync`, so a detected disagreement outlives the request that found it."""
    from genios_engine.capture.validate.conflict import ConflictOutcome

    store = S.InMemoryConflictStore()
    summary = type("S", (), {"conflicts": ConflictOutcome(detection=_detection(),
                                                          escalations=())})()

    assert S.persist_sweep_conflicts(summary, org_id=ORG, store=store) == 1
    assert S.persist_sweep_conflicts(type("S", (), {"conflicts": None})(), org_id=ORG,
                                     store=store) == 0
    assert len(store.list(ORG)) == 1


def test_the_api_persists_after_every_sweep_it_runs():
    """The route module must actually call it — a store nothing writes is the defect restated."""
    import inspect

    from genios_engine.api import routes

    source = inspect.getsource(routes)
    assert "persist_sweep_conflicts" in source, (
        "no production caller: `signal_conflicts` would be a table nothing writes")


# ── helpers ───────────────────────────────────────────────────────────────────────────────────

def _disposable_org(url: str) -> str:
    """A real `orgs` row of our own, cloned from whatever the scratch database holds, so the FK
    is satisfied and no shared tenant is touched."""
    from sqlalchemy import text

    from genios_engine.platform.db import get_engine

    org = f"org_conflict_{uuid.uuid4().hex[:12]}"
    engine = get_engine(url)
    with engine.begin() as conn:
        template = conn.execute(text("select id from orgs limit 1")).scalar()
        if not template:
            pytest.skip("no org in the scratch database to clone")
        columns = [r.column_name for r in conn.execute(text(
            "select column_name from information_schema.columns "
            "where table_schema='public' and table_name='orgs'")).all()]
        unique = {r.column_name for r in conn.execute(text(
            "select a.attname as column_name from pg_index i "
            "join pg_attribute a on a.attrelid=i.indrelid and a.attnum = any(i.indkey) "
            "where i.indrelid='public.orgs'::regclass and i.indisunique")).all()}
        projection = ", ".join(f":clone_{c} as {c}" if c in unique else c for c in columns)
        params = {"t": template}
        params.update({f"clone_{c}": (org if c == "id" else f"{org}@conflict.invalid")
                       for c in unique})
        conn.execute(text(f"insert into orgs ({', '.join(columns)}) select {projection} "
                          "from orgs where id=:t"), params)
    return org


def _drop_org(url: str, org: str) -> None:
    from sqlalchemy import text

    from genios_engine.platform.db import get_engine

    with get_engine(url).begin() as conn:
        conn.execute(text("delete from orgs where id=:o"), {"o": org})
