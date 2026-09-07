"""Migration 0115 · the four provenance answers, from the capture path to the HTTP surface.

    pytest tests/capture/esqe/test_qes_provenance.py -q     (pg tests need GENIOS_TEST_DATABASE_URL)

Each of the four was computed during capture and then dropped at the seam, so a stored signal
could not answer a question somebody was always going to ask:

    ingested_at           did this reach us late? (`occurred_at` is when it HAPPENED)
    content_hash          has the source changed since we concluded this?
    qualification_reason  why did the floor let this through, rather than merely that it did?
    superseded_by         what replaced this? — the forward half of a link that only pointed back

A column written by a publisher and read by no surface is the same defect as a unit called by no
request path, so every assertion below either drives the sweep seam or reads the route.
"""

from __future__ import annotations

import json
from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import text

from genios_engine.api import routes
from genios_engine.capture.esqe.signal_store import (InMemorySignalStore, PostgresSignalStore,
                                                     QualifiedSignalRow)
from genios_engine.capture.semantic.cache import content_digest
from genios_engine.platform.auth import AuthCtx, get_auth_ctx
from genios_engine.platform.db import get_engine

ORG = "org_qes_provenance"
NOW = datetime(2026, 6, 1, 9, 0, tzinfo=timezone.utc)
SENT = NOW - timedelta(days=2)
DIGEST = content_digest("Northwind renewal: $84,000 due 28 March.")


def _row(signal_id: str, **over) -> QualifiedSignalRow:
    base = dict(
        signal_id=signal_id, org_id=ORG, event_id=f"evt_{signal_id}", trace_id=f"evt_{signal_id}",
        signal_type="contract_renewal", importance_bp=7800, importance_version="alg17-v1",
        confidence_bp=8000, extraction_ref="l1x_9f2c", state="active", occurred_at=SENT,
        evidence_refs=({"quote": "the $84,000 fee", "start_offset": 0, "end_offset": 15,
                        "source_ref": "prepared_content:pc_1", "verified": True},),
        ingested_at=NOW, content_hash=DIGEST, qualification_reason="at_or_above_floor")
    base.update(over)
    return QualifiedSignalRow(**base)


# =============================================================================================
# The row itself — the two shapes that must not be storable
# =============================================================================================
def test_a_truncated_or_upper_cased_digest_is_refused():
    """The column exists to be COMPARED with the extraction cache's digest, and a differently
    spelled hash of the same bytes compares unequal — which is worse than storing nothing,
    because it reads as a mismatch that never happened."""
    with pytest.raises(ValueError, match="content_hash"):
        _row("sig_a", content_hash=DIGEST[:32])
    with pytest.raises(ValueError, match="content_hash"):
        _row("sig_a", content_hash=DIGEST.upper())


def test_a_signal_cannot_be_superseded_by_itself():
    with pytest.raises(ValueError, match="superseded by itself"):
        _row("sig_a", superseded_by="sig_a")


# =============================================================================================
# The forward link — written by the STORE, because the publisher never holds the old row
# =============================================================================================
def test_publishing_a_replacement_links_the_row_it_replaced():
    """ALG-19 stamps `supersedes` on the NEW signal; from the OLD id there was then no way to
    reach the new one without scanning the table for a row pointing at you."""
    store = InMemorySignalStore()
    store.put([_row("sig_old")])
    store.put([_row("sig_new", supersedes="sig_old")])

    assert store.get(ORG, "sig_old").superseded_by == "sig_new"
    assert store.get(ORG, "sig_new").superseded_by is None       # nothing has replaced it yet


def test_a_second_replacement_keeps_the_first_link():
    """A signal replaced twice was replaced by the EARLIER one, and that one was then replaced.
    Overwriting would report the chain's last link as its first and lose the middle."""
    store = InMemorySignalStore()
    store.put([_row("sig_old")])
    store.put([_row("sig_new", supersedes="sig_old")])
    store.put([_row("sig_newer", supersedes="sig_old")])
    assert store.get(ORG, "sig_old").superseded_by == "sig_new"


def test_superseding_a_signal_this_tenant_does_not_hold_writes_no_orphan():
    """Erased, or published before the column existed. A pointer to a row that is not there is
    worse than no pointer: it reads as a chain that can be followed."""
    store = InMemorySignalStore()
    store.put([_row("sig_new", supersedes="sig_gone")])
    assert store.get(ORG, "sig_gone") is None
    assert store.get(ORG, "sig_new").superseded_by is None


# =============================================================================================
# The database, and the surface
# =============================================================================================
@pytest.fixture
def pg_url(live_db_url):
    if not live_db_url:
        pytest.skip("GENIOS_TEST_DATABASE_URL not set — 0115's columns need real Postgres")
    return live_db_url


@pytest.fixture
def stored(pg_url):
    engine = get_engine(pg_url)
    with engine.begin() as conn:
        conn.execute(text("delete from qualified_signals where org_id = :o"), {"o": ORG})
        conn.execute(text("delete from orgs where id = :o"), {"o": ORG})
        # `qualified_signals` cascades from `orgs`. Required columns read off the live schema, so
        # a table that gains one breaks the product rather than this fixture.
        names = [r.column_name for r in conn.execute(text(
            "select column_name from information_schema.columns where table_name='orgs' "
            "and is_nullable='NO' and column_default is null and column_name<>'id'"))]
        cols = ["id"] + names
        conn.execute(text(f"insert into orgs ({', '.join(cols)}) values "
                          f"({', '.join(':' + c for c in cols)})"),
                     {"id": ORG, **{n: "scratch" for n in names}})
    store = PostgresSignalStore(pg_url)
    assert store.put([_row("sig_old")]) == 1
    assert store.put([_row("sig_new", supersedes="sig_old", occurred_at=NOW)]) == 1
    yield store, engine
    with engine.begin() as conn:
        conn.execute(text("delete from qualified_signals where org_id = :o"), {"o": ORG})
        conn.execute(text("delete from orgs where id = :o"), {"o": ORG})


def test_the_four_columns_round_trip_through_postgres(stored):
    store, _ = stored
    row = store.get(ORG, "sig_old")
    assert row.ingested_at == NOW
    assert row.content_hash == DIGEST
    assert row.qualification_reason == "at_or_above_floor"
    assert row.superseded_by == "sig_new", "the forward link did not commit with the rows"


def test_a_replay_of_the_same_sweep_does_not_erase_the_link(stored):
    """The upsert re-states every judgement column from `excluded`; taking `superseded_by` from
    there too would wipe the link every time a sweep is replayed, because the replayed signal
    still does not know what replaced it."""
    store, _ = stored
    store.put([_row("sig_old")])                       # the same publish, again
    assert store.get(ORG, "sig_old").superseded_by == "sig_new"


def test_the_database_refuses_a_malformed_digest(stored):
    """The CHECK constraint, not just the dataclass: a hand-written UPDATE is the other writer."""
    _, engine = stored
    with pytest.raises(Exception, match="content_hash_shape"):
        with engine.begin() as conn:
            conn.execute(text("update qualified_signals set content_hash = 'nope' "
                              "where org_id = :o and signal_id = 'sig_old'"), {"o": ORG})


def test_the_route_returns_all_four(stored, monkeypatch):
    """Written and READ. A provenance column no surface serves is a column nobody can act on."""
    store, _ = stored
    monkeypatch.setattr(routes, "_signal_store", store)
    app = FastAPI()
    app.include_router(routes.router)
    app.dependency_overrides[get_auth_ctx] = lambda: AuthCtx(org_id=ORG, actor_id="seat_founder")

    body = TestClient(app).get("/qualification/signals?limit=10").json()
    served = {s["signal_id"]: s for s in body["signals"]}
    # Compared as an INSTANT, not as a string: psycopg hands the row back in the session's
    # timezone, so the same moment is spelled `...T09:00+00:00` on one host and `...T14:30+05:30`
    # on another. A string assertion here would pass in CI and fail on a laptop.
    assert datetime.fromisoformat(served["sig_old"]["ingested_at"]) == NOW
    assert served["sig_old"]["content_hash"] == DIGEST
    assert served["sig_old"]["qualification_reason"] == "at_or_above_floor"
    assert served["sig_old"]["superseded_by"] == "sig_new"
    assert served["sig_new"]["supersedes"] == "sig_old"


def test_an_older_row_reports_none_rather_than_a_default(stored):
    """Nothing is backfilled. A signal published before 0115 genuinely does not know when it was
    ingested or what its source hashed to, and a filled-in default would be invented history."""
    store, engine = stored
    with engine.begin() as conn:
        conn.execute(text(
            "update qualified_signals set ingested_at = null, content_hash = null, "
            "qualification_reason = null where org_id = :o and signal_id = 'sig_new'"),
            {"o": ORG})
    row = store.get(ORG, "sig_new")
    assert (row.ingested_at, row.content_hash, row.qualification_reason) == (None, None, None)
    assert row.importance_bp == 7800            # the rest of the row is untouched
    assert replace(row, ingested_at=NOW).ingested_at == NOW      # and still a normal record


def test_the_json_the_signal_carries_is_the_digest_the_cache_computes():
    """The whole value of storing the hash is that the two sides agree. One function, called by
    both — `capture/semantic/cache.content_digest`."""
    from genios_engine.capture.semantic.cache import cache_key

    key = cache_key(org_id=ORG, content="hello", profile_id="email", prompt_version="p1",
                    schema_version="s1", vocab_fingerprint="v1", envelope="",
                    model_snapshot="fake-model")
    assert json.loads(json.dumps(key.content_hash)) == content_digest("hello")
