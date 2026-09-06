"""L1.7.5 · `source_coverage` — the table that had no reader and no writer.

Created in migration `0002`. Referenced afterwards by exactly one line of code:
`0033_org_data_cascade.sql`, which made sure it would be deleted when a tenant was. A table
nothing wrote, carefully cleaned up. Doc 07's storage map lists it with the retention line
"recomputed each sweep", which was a promise about a write that never happened.

The Postgres half is marked `pg` and runs against `GENIOS_TEST_DATABASE_URL` — never production.
A store whose SQL is only ever exercised by an in-memory double is a store whose SQL is untested,
and this one has an upsert, an array column and a jsonb cast in it.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone

import pytest

from genios_engine.capture.coverage.declaration import declare_coverage
from genios_engine.capture.coverage.store import (InMemoryCoverageStore, PostgresCoverageStore,
                                                  rows_for)
from genios_engine.contracts.connection import Connection

NOW = datetime(2026, 1, 14, 9, 0, tzinfo=timezone.utc)
LATER = datetime(2026, 1, 15, 9, 0, tzinfo=timezone.utc)


def _declaration(*sources: str, org_id: str = "org_scratch_tests", at: datetime = NOW):
    conns = [Connection(org_id=org_id, source_type=s, connection_id=f"con_{s}") for s in sources]
    return declare_coverage(org_id=org_id, connections=conns, computed_at=at)


# ---------------------------------------------------------------------------------------------
# rows_for — the shape both stores agree on
# ---------------------------------------------------------------------------------------------

def test_a_row_per_registered_domain_carrying_the_requirement_and_the_verdict():
    rows = {r.domain: r for r in rows_for(_declaration("gmail", "hubspot"))}
    assert set(rows) == {"sales", "support", "admin", "fundraising"}
    assert rows["sales"].required == ("communication", "crm")
    assert rows["sales"].connected == ("communication", "crm")
    assert rows["sales"].coverage_ready is True
    assert rows["support"].coverage_ready is False
    assert rows["sales"].computed_at == NOW


def test_required_is_read_from_the_pack_table_not_re_derived_from_the_verdict():
    """`capabilities` minus `missing_recommended` looks like the required set and is equal to it
    only while every recommended capability happens to be missing. Connect a calendar — a
    RECOMMENDED capability for sales — and a derivation like that files `calendar` as required."""
    rows = {r.domain: r for r in rows_for(_declaration("gmail", "hubspot", "gcal"))}
    assert rows["sales"].required == ("communication", "crm")
    assert "calendar" in rows["sales"].connected


def test_freshness_records_the_state_of_each_capability_not_just_its_presence():
    rows = {r.domain: r for r in rows_for(_declaration("gmail"))}
    assert rows["sales"].freshness == {"communication": "fresh"}


# ---------------------------------------------------------------------------------------------
# the in-memory store
# ---------------------------------------------------------------------------------------------

def test_the_in_memory_store_upserts_rather_than_appending():
    store = InMemoryCoverageStore()
    assert store.save(_declaration("gmail")) == 4
    assert store.save(_declaration("gmail", "hubspot", at=LATER)) == 4
    assert len(store.list("org_scratch_tests")) == 4, "a sweep RECOMPUTES coverage, it does not log it"
    sales = store.get("org_scratch_tests", "sales")
    assert sales is not None and sales.coverage_ready is True
    assert sales.computed_at == LATER


def test_one_tenants_rows_are_not_another_tenants():
    store = InMemoryCoverageStore()
    store.save(_declaration("gmail", "hubspot", org_id="org_a"))
    store.save(_declaration("gmail", org_id="org_b"))
    assert store.get("org_b", "sales").coverage_ready is False
    assert store.get("org_a", "sales").coverage_ready is True
    assert {r.org_id for r in store.list("org_a")} == {"org_a"}


# ---------------------------------------------------------------------------------------------
# the real one
# ---------------------------------------------------------------------------------------------

@pytest.mark.pg
def test_the_postgres_store_writes_and_reads_source_coverage():
    """The SQL, executed. Array columns, the jsonb cast and the (org_id, domain) upsert are three
    things an in-memory dict cannot get wrong and Postgres can."""
    url = os.environ.get("GENIOS_TEST_DATABASE_URL")
    if not url:
        pytest.skip("GENIOS_TEST_DATABASE_URL not set — the real coverage store is not exercised")
    store = PostgresCoverageStore(url)
    org = "org_scratch_tests"                      # seeded by tests/conftest.py; FK-satisfying

    assert store.save(_declaration("gmail", org_id=org)) == 4
    first = store.get(org, "sales")
    assert first is not None
    assert first.required == ("communication", "crm")
    assert first.connected == ("communication",)
    assert first.freshness == {"communication": "fresh"}
    assert first.coverage_ready is False
    assert first.computed_at is not None

    # the sweep runs again with a CRM connected — the same row is updated, not duplicated
    assert store.save(_declaration("gmail", "hubspot", org_id=org, at=LATER)) == 4
    second = store.get(org, "sales")
    assert second is not None and second.coverage_ready is True
    assert second.connected == ("communication", "crm")
    assert len(store.list(org)) == 4
    assert store.get(org, "no_such_domain") is None


# ---------------------------------------------------------------------------------------------
# The READER, wired. A store nothing reads is half a unit.
# ---------------------------------------------------------------------------------------------

@pytest.mark.gate
def test_the_declaration_a_sweep_files_is_readable_back_without_recomputing_it():
    """Writer and reader, through the production module rather than around it.

    `_coverage_fn_for` is what every capture entry in `api/routes.py` calls, and filing is its
    side effect; `GET /coverage/declared` is the only thing that reads `source_coverage` back.
    Asserting them together is what proves the table is a round trip and not a write-only log —
    which is what it was, in the other direction, for its whole life.
    """
    import genios_engine.api.routes as R

    org = "org_reader"
    store = InMemoryCoverageStore()
    conns = [Connection(org_id=org, source_type=s, connection_id=f"con_{s}")
             for s in ("gmail", "hubspot")]

    class _Connections:
        def list_active(self):
            return conns

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(R, "_coverage_store", store)
        mp.setattr(R, "_connections", _Connections())
        mp.setattr(R, "_graph", None)
        verdict = R._coverage_fn_for(org)                 # a capture entry declaring, as it sweeps
        assert verdict("sales")["coverage_ready"] is True
        read_back = R.coverage_declared(org_id=org)

    filed = {d["domain"]: d for d in read_back["declared"]}
    assert set(filed) == {"sales", "support", "admin", "fundraising"}
    assert filed["sales"]["coverage_ready"] is True
    assert filed["support"]["coverage_ready"] is False, "no support desk is a real, filed False"
    assert filed["sales"]["required"] == ["communication", "crm"]
    assert filed["sales"]["connected"] == ["communication", "crm"]
    assert filed["sales"]["computed_at"], (
        "an undated coverage row is indistinguishable from one that stopped being recomputed")


@pytest.mark.gate
def test_a_tenant_that_has_never_been_declared_reads_empty_rather_than_guessing():
    """An absent row means "never declared", and the reader must say so instead of inventing a
    verdict — the whole point of coverage is that absence is not evidence."""
    import genios_engine.api.routes as R

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(R, "_coverage_store", InMemoryCoverageStore())
        assert R.coverage_declared(org_id="org_never_swept") == {"declared": []}
