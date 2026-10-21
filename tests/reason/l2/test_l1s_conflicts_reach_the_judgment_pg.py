"""What L1 found disagreeing reaches the L2 judgment: printed both sides, a deeper plan, a fingerprint that moves.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… pytest tests/reason/l2/test_l1s_conflicts_reach_the_judgment_pg.py -q

L2 audit, 21 Oct 2026. L1 keeps an open disagreement (`signal_conflicts`, ALG-12 `unresolved_surface_both` — two
dates for one meeting, two amounts for one invoice) and names it on the signals (`conflict_ids`); prod, 21 Oct: 24
of 162 signals carried one. The L2 pass read neither — the dossier said nothing, `compile_plan(conflicts=)` was
always 0, and no fingerprint named one. Now each open conflict on the events a
subject rests on is printed in block F by both sides' own quotes, the plan goes deep, and the fingerprint names it
(only when there is one: a subject with none fingerprints as it did).
"""
from __future__ import annotations

import json

import pytest
from sqlalchemy import text

from genios_engine.reason.l2.inputs import Subject
from genios_engine.reason.l2.sweep import fingerprint_of, l2_pass
from tests.reason.l2.test_the_l2_pass_pg import NOW, ORG, _Client, _seed, store  # noqa: F401 — the fixture

pytestmark = pytest.mark.pg

MONDAY = "Thursday, Oct 8, 12:00–12:30 IST"
MOVED = "Thursday, October 22, 9:00–9:30 AM Pacific works for me"


def _conflict(store, cid="cfl_g008_dates", events=("evt_g008_1", "evt_g008_9")):
    claims = [{"value": {"earliest": "2026-10-08T06:30:00Z", "evidence": [{"quote": MONDAY}]}, "rank": 2},
              {"value": {"earliest": "2026-10-22T16:00:00Z", "evidence": [{"quote": MOVED}]}, "rank": 2}]
    with store.engine.begin() as c:
        c.execute(text(
            "insert into signal_conflicts (conflict_id, org_id, signal_id, field, subject_key, claims, resolution, "
            "event_ids) values (:c, :o, 'sig_g008_1', 'date.value', 'thread:th_vendor:date', cast(:cl as jsonb), "
            "'unresolved_surface_both', cast(:ev as jsonb))"),
            {"c": cid, "o": ORG, "cl": json.dumps(claims), "ev": json.dumps(list(events))})


def test_an_open_conflict_is_printed_both_sides_and_the_plan_goes_deep(store):
    _seed(store)
    _conflict(store)
    client = _Client()
    out = l2_pass(store=store, org_id=ORG, now=NOW, llm=client)
    [prompt] = client.prompts
    assert "L1 found sources that disagree on date.value" in prompt and "[cfl_g008_dates]" in prompt
    assert MONDAY in prompt and MOVED in prompt, "both sides, by their own words"
    assert out["depths"].get("deep") == 1, f"a conflict must make the run deep: {dict(out['depths'])}"


def test_a_resolved_conflict_and_another_subjects_conflict_are_not_printed(store):
    _seed(store)
    _conflict(store, cid="cfl_g008_other", events=("evt_somewhere_else",))
    with store.engine.begin() as c:
        c.execute(text("insert into signal_conflicts (conflict_id, org_id, signal_id, field, subject_key, claims, "
                       "resolution, event_ids) values ('cfl_g008_settled', :o, 'sig_g008_1', 'amount', 's', "
                       "'[]'::jsonb, 'resolved_by_authority', '[\"evt_g008_1\"]'::jsonb)"), {"o": ORG})
    client = _Client()
    l2_pass(store=store, org_id=ORG, now=NOW, llm=client)
    assert "L1 found sources that disagree" not in client.prompts[0]


def test_a_conflict_moves_the_fingerprint():
    """L1 files a conflict with the mail that makes it — a new bundle — and a re-entry or a handed-over file reads
    the subject again: either way the judgment standing on the old inputs must not answer for the new ones."""
    from genios_engine.reason.l2.inputs import L1Conflict
    plain = Subject(subject_ref="seed:x", file_id=None, seed_key="x", bundle_ids=(), signals=())
    disputed = Subject(subject_ref="seed:x", file_id=None, seed_key="x", bundle_ids=(), signals=(),
                       conflicts=(L1Conflict("cfl_1", "date.value", (MONDAY, MOVED), ("evt_1",)),))
    a, _ = fingerprint_of(plain, file_inputs=None, need_states={}, model="m", tools={})
    b, _ = fingerprint_of(disputed, file_inputs=None, need_states={}, model="m", tools={})
    assert a != b


def test_a_subject_with_no_conflict_fingerprints_as_it_did():
    plain = Subject(subject_ref="seed:x", file_id=None, seed_key="x", bundle_ids=(), signals=())
    fp, inputs = fingerprint_of(plain, file_inputs=None, need_states={}, model="m", tools={})
    assert "conflicts" not in inputs
