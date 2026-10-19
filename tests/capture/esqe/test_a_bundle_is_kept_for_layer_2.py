"""GeniOS-008 L1 E1 · the bundle a sweep builds is KEPT, and Layer 2 can read it back.

    pytest tests/capture/esqe/test_a_bundle_is_kept_for_layer_2.py -q

Before: `publish_sweep` built bundles and `finalize_l1` passed it no store, so `signal_bundles` (0186)
stayed empty and Layer 2 had no contract to start from.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone

import pytest

from genios_engine.capture.esqe import finalize as F
from genios_engine.capture.esqe.bundle import build_bundles
from genios_engine.capture.esqe.bundle_store import InMemoryBundleStore, PostgresBundleStore

pytestmark = pytest.mark.unit

_T0 = datetime(2026, 10, 18, 9, 0, tzinfo=timezone.utc)


class _Sig:
    def __init__(self, signal_id, thread_key=None, subject_key=None):
        self.signal_id = signal_id
        self.thread_key = thread_key
        self.subject_key = subject_key
        self.trace_id = "trace-1"
        self.occurred_at = _T0
        self.extraction = None
        self.coverage = {"sources": [{"source": "gmail", "completeness_bp": 800}]}


def _bundles():
    return build_bundles("org_x", "trace-1", [_Sig("s1", thread_key="t1"), _Sig("s2", thread_key="t1"),
                                              _Sig("s3", thread_key="t9")])


def test_finalize_hands_the_bundle_store_to_publication(monkeypatch):
    seen = {}

    def _publish(summary, qualification, **kw):
        seen.update(kw)
        return type("R", (), {"stored": 0})()

    monkeypatch.setattr(F, "persist_sweep_conflicts", lambda *a, **k: None)
    monkeypatch.setattr(F, "qualify_sweep", lambda *a, **k: object())
    monkeypatch.setattr(F, "sweep_lifecycle", lambda *a, **k: type("L", (), {"transitions": (), "records": ()})())
    monkeypatch.setattr(F, "publish_sweep", _publish)
    store = InMemoryBundleStore()
    F.finalize_l1(F.ManualSweep(org_id="org_x"), org_id="org_x", stores=F.L1Stores(bundles=store))
    assert seen["bundle_store"] is store


def test_no_bundle_store_is_still_a_sweep(monkeypatch):
    seen = {}
    monkeypatch.setattr(F, "persist_sweep_conflicts", lambda *a, **k: None)
    monkeypatch.setattr(F, "qualify_sweep", lambda *a, **k: object())
    monkeypatch.setattr(F, "sweep_lifecycle", lambda *a, **k: type("L", (), {"transitions": (), "records": ()})())
    monkeypatch.setattr(F, "publish_sweep", lambda s, q, **kw: seen.update(kw) or type("R", (), {"stored": 0})())
    F.finalize_l1(F.ManualSweep(org_id="org_x"), org_id="org_x", stores=F.L1Stores())
    assert seen["bundle_store"] is None


def test_a_replayed_page_is_one_bundle_not_two():
    store = InMemoryBundleStore()
    assert store.put(_bundles()) == 2
    assert store.put(_bundles()) == 0
    rows = store.since("org_x", after=None)
    assert [r.signal_ids for r in rows] == [("s1", "s2"), ("s3",)]
    assert rows[0].coverage["sources"][0]["source"] == "gmail"


def test_a_tenant_reads_only_its_own_bundles():
    store = InMemoryBundleStore()
    store.put(_bundles())
    assert store.since("org_other", after=None) == []


def test_the_routes_wire_a_bundle_store():
    """Both capture doors pass one — a door without it is the defect E1 fixes, one door wide."""
    from pathlib import Path
    root = Path(__file__).resolve().parents[3] / "genios_engine" / "api"
    assert "bundles=_bundle_store" in (root / "routes.py").read_text()
    assert "bundles=make_bundle_store()" in (root / "upload_routes.py").read_text()


@pytest.mark.pg
def test_postgres_keeps_and_reads_back_a_bundle():
    url = os.environ.get("GENIOS_TEST_DATABASE_URL")
    if not url:
        pytest.skip("GENIOS_TEST_DATABASE_URL not set — real-Postgres L2 tests skipped")
    from sqlalchemy import text

    from genios_engine.platform.db import get_engine
    engine = get_engine(url)
    with engine.connect() as conn:
        org = conn.execute(text("select id from orgs limit 1")).scalar()
    if not org:
        pytest.skip("no org in the scratch database")
    bundles = build_bundles(org, "trace-e1", [_Sig("e1-s1", thread_key="e1-t"), _Sig("e1-s2", thread_key="e1-t")])
    store = PostgresBundleStore(engine=engine)
    try:
        store.put(bundles)
        assert store.put(bundles) == 0
        rows = [r for r in store.since(org, after=None, limit=1000) if r.trace_id == "trace-e1"]
        assert len(rows) == 1 and rows[0].signal_ids == ("e1-s1", "e1-s2")
        assert rows[0].created_at is not None
    finally:
        with engine.begin() as conn:
            conn.execute(text("delete from signal_bundles where trace_id = 'trace-e1'"))
