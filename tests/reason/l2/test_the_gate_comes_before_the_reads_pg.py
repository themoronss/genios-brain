"""L2 rebuild A1–A3 — the change gate and the cap come BEFORE the expensive reads; a carried re-entry is kept.

Before: every subject read its snapshot (up to ~42 round trips) and its history (up to 10) and only then asked
the change gate — so an unchanged subject, and every subject past `max_per_pass`, paid ~50 reads for nothing.
And a re-entry (a met evidence need) carried past the cap let the watermark move beyond the instant the need was
met, so it was never read again.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… pytest tests/reason/l2/test_the_gate_comes_before_the_reads_pg.py -q
"""
from __future__ import annotations

import os
from datetime import timedelta

import pytest
from sqlalchemy import text

from genios_engine.capture.esqe.bundle import build_bundles
from genios_engine.capture.esqe.bundle_store import PostgresBundleStore
from genios_engine.capture.esqe.signal_store import PostgresSignalStore, QualifiedSignalRow
from genios_engine.reason.l2 import sweep as SW
from genios_engine.reason.l2.sweep import l2_pass
from tests.reason.l2.test_the_l2_pass_pg import (NOW, ORG, QUOTE, _Client, _seed, _Sig2,  # noqa: F401
                                                 store)

pytestmark = pytest.mark.pg


@pytest.fixture
def reads(monkeypatch):
    seen = {"snapshot": 0, "history": 0}
    real_snapshot, real_history = SW.read_snapshot, SW.history_for

    def snapshot(*a, **k):
        seen["snapshot"] += 1
        return real_snapshot(*a, **k)

    def history(*a, **k):
        seen["history"] += 1
        return real_history(*a, **k)

    monkeypatch.setattr(SW, "read_snapshot", snapshot)
    monkeypatch.setattr(SW, "history_for", history)
    return seen


def _second_subject(store):
    row = QualifiedSignalRow(
        signal_id="sig_g008_2", org_id=ORG, subject_key="vendor:acme", event_id="evt_g008_2", trace_id="tr_g008",
        signal_type="contract_renewal", importance_bp=5000, importance_version="v", confidence_bp=8000,
        extraction_ref="struct:evt_g008_2", state="active", occurred_at=NOW - timedelta(hours=10),
        thread_key="th_other", direction="inbound", ball_in_court="us",
        evidence_refs=({"source_ref": "evt_g008_2", "quote": QUOTE, "start_offset": 0, "end_offset": len(QUOTE)},))
    PostgresSignalStore(os.environ["GENIOS_TEST_DATABASE_URL"]).put([row])
    PostgresBundleStore(engine=store.engine).put(build_bundles(ORG, "tr_g008", [_Sig2()]))


def test_an_unchanged_subject_reads_no_snapshot_and_no_history(store, reads):
    _seed(store)
    l2_pass(store=store, org_id=ORG, now=NOW, llm=_Client())
    assert reads == {"snapshot": 1, "history": 1}
    with store.engine.begin() as c:          # the same bundle read again: same inputs, same fingerprint
        c.execute(text("delete from post_pass_watermarks where org_id = :o"), {"o": ORG})
    again = _Client()
    receipt = l2_pass(store=store, org_id=ORG, now=NOW + timedelta(minutes=10), llm=again)
    assert receipt["subjects"] == 1 and receipt["unchanged"] == 1 and again.prompts == [], str(receipt)
    assert reads == {"snapshot": 1, "history": 1}, "the gate answered before the snapshot and history reads"


def test_a_subject_past_the_cap_reads_no_snapshot(store, reads):
    _seed(store)
    _second_subject(store)
    receipt = l2_pass(store=store, org_id=ORG, now=NOW, llm=_Client(), max_per_pass=1)
    assert receipt["carried"] == 1 and receipt["written"] == 1
    assert reads == {"snapshot": 1, "history": 1}, "only the subject that was judged read its snapshot"


def test_a_carried_reentry_holds_the_watermark_until_it_is_read(store):
    _seed(store)
    l2_pass(store=store, org_id=ORG, now=NOW, llm=_Client())
    with store.engine.begin() as c:
        c.execute(text("update evidence_needs set state = 'met', closed_at = now() where org_id = :o"), {"o": ORG})
    _second_subject(store)                    # a NEWER bundle arrives in the same pass as the re-entry
    carried = l2_pass(store=store, org_id=ORG, now=NOW + timedelta(minutes=5), llm=_Client(), max_per_pass=0)
    assert carried["reentries"] == 1 and carried["carried"] == 2
    third = _Client()
    receipt = l2_pass(store=store, org_id=ORG, now=NOW + timedelta(minutes=10), llm=third)
    assert receipt["reentries"] == 1, "the met need is read again: the watermark did not pass it"
    assert len(third.prompts) == 2
