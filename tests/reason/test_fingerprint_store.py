"""STEP-02 · the change gate's store: read a subject's last decision, record a run, record a skip.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… pytest tests/reason/test_fingerprint_store.py -q

`reason/fingerprint_store.py` (tree `yc2_w27_s02/M20.C2.L-data.V1.U02`) over migration 0191. A run
REPLACES the row — its fingerprint, run, outcome and instant — and zeroes the skips; a skip only
moves `last_checked_at` and counts. The sweep reads every row of a tenant once, not one per
subject. The vocabularies are the migration's, held equal here so the Python and the check
constraint cannot drift.
"""
from __future__ import annotations

import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text

from genios_engine.reason import fingerprint_store as fs

ORG, OTHER = "fpstore_org", "fpstore_other"
AT = datetime(2026, 10, 6, 12, 0, tzinfo=timezone.utc)
MIGRATION = Path(__file__).resolve().parents[2] / "migrations" / "0191_reasoning_fingerprints.sql"


def _check_values(name: str) -> set[str]:
    sql = MIGRATION.read_text(encoding="utf-8")
    block = re.search(rf"constraint reasoning_fingerprints_{name}_check\s+check \({name} in \((.*?)\)\)",
                      sql, re.S)
    assert block, name
    return set(re.findall(r"'([a-z_]+)'", block.group(1)))


def test_the_vocabularies_are_the_migrations():
    assert set(fs.LANES) == _check_values("lane")
    assert set(fs.OUTCOMES) == _check_values("outcome")


def test_an_outcome_outside_the_vocabulary_is_refused_before_any_write():
    class _NoConn:
        def execute(self, *a, **k):
            raise AssertionError("wrote before validating")
    with pytest.raises(ValueError, match="outcome"):
        fs.record_decided(_NoConn(), org_id=ORG, subject_key="k", lane="compiled",
                          fingerprint="f", outcome="skipped", run_id=None, decided_at=AT)
    with pytest.raises(ValueError, match="lane"):
        fs.record_decided(_NoConn(), org_id=ORG, subject_key="k", lane="v2",
                          fingerprint="f", outcome="emitted", run_id=None, decided_at=AT)


@pytest.fixture
def engine():
    url = os.environ.get("GENIOS_TEST_DATABASE_URL")
    if not url:
        pytest.skip("needs GENIOS_TEST_DATABASE_URL pointing at a scratch database")
    eng = create_engine(url)
    with eng.begin() as c:
        for org in (ORG, OTHER):
            c.execute(text("delete from orgs where id = :o"), {"o": org})
            c.execute(text("insert into orgs (id, name, email) values (:o, :o, :e)"),
                      {"o": org, "e": f"{org}@example.test"})
    yield eng
    with eng.begin() as c:
        for org in (ORG, OTHER):
            c.execute(text("delete from orgs where id = :o"), {"o": org})


@pytest.mark.pg
def test_a_subject_never_decided_has_no_row(engine):
    with engine.connect() as c:
        assert fs.load_all(c, ORG) == {}


@pytest.mark.pg
def test_a_run_is_recorded_and_read_back(engine):
    with engine.begin() as c:
        fs.record_decided(c, org_id=ORG, subject_key="sit_1|cap", lane="compiled",
                          fingerprint="fp_a", outcome="emitted", run_id="run_1", decided_at=AT)
    with engine.connect() as c:
        row = fs.load_all(c, ORG)["sit_1|cap"]
    assert row == fs.StoredFingerprint(subject_key="sit_1|cap", lane="compiled",
                                       fingerprint="fp_a", outcome="emitted", run_id="run_1",
                                       decided_at=AT, last_checked_at=AT, skips=0)


@pytest.mark.pg
def test_a_skip_moves_only_the_receipt(engine):
    with engine.begin() as c:
        fs.record_decided(c, org_id=ORG, subject_key="k", lane="legacy", fingerprint="fp_a",
                          outcome="standing", run_id="run_1", decided_at=AT)
        fs.record_skipped(c, org_id=ORG, subject_key="k", checked_at=AT + timedelta(minutes=15))
        fs.record_skipped(c, org_id=ORG, subject_key="k", checked_at=AT + timedelta(minutes=30))
    with engine.connect() as c:
        row = fs.load_all(c, ORG)["k"]
    assert (row.fingerprint, row.outcome, row.run_id, row.decided_at) == ("fp_a", "standing",
                                                                         "run_1", AT)
    assert row.skips == 2 and row.last_checked_at == AT + timedelta(minutes=30)


@pytest.mark.pg
def test_a_new_decision_replaces_the_row_and_zeroes_the_skips(engine):
    later = AT + timedelta(hours=2)
    with engine.begin() as c:
        fs.record_decided(c, org_id=ORG, subject_key="k", lane="legacy", fingerprint="fp_a",
                          outcome="standing", run_id="run_1", decided_at=AT)
        fs.record_skipped(c, org_id=ORG, subject_key="k", checked_at=AT + timedelta(minutes=15))
        fs.record_decided(c, org_id=ORG, subject_key="k", lane="legacy", fingerprint="fp_b",
                          outcome="deferred", run_id=None, decided_at=later)
    with engine.connect() as c:
        row = fs.load_all(c, ORG)["k"]
    assert row == fs.StoredFingerprint(subject_key="k", lane="legacy", fingerprint="fp_b",
                                       outcome="deferred", run_id=None, decided_at=later,
                                       last_checked_at=later, skips=0)


@pytest.mark.pg
def test_a_sweep_reads_a_tenant_once_and_only_that_tenant(engine):
    with engine.begin() as c:
        for org, key in ((ORG, "a"), (ORG, "b"), (OTHER, "a")):
            fs.record_decided(c, org_id=org, subject_key=key, lane="native", fingerprint=f"fp_{key}",
                              outcome="shadow", run_id=None, decided_at=AT)
    with engine.connect() as c:
        rows = fs.load_all(c, ORG)
    assert set(rows) == {"a", "b"} and rows["b"].fingerprint == "fp_b"


@pytest.mark.pg
def test_a_skip_for_a_subject_with_no_row_writes_nothing(engine):
    with engine.begin() as c:
        assert fs.record_skipped(c, org_id=ORG, subject_key="nobody", checked_at=AT) == 0
    with engine.connect() as c:
        assert fs.load_all(c, ORG) == {}
