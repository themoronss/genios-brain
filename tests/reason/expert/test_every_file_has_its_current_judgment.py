"""STEP-15 · every file's CURRENT judgment, in one read — never an older valid review standing in for a newer refusal.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… .venv/bin/python -m pytest -q tests/reason/expert/test_every_file_has_its_current_judgment.py

`reason/expert/store.current_judgments` (tree `yc2_w27_s15` M44.C2.L-data.V0.U01; `03` s15-F13). The brief reads every
file's judgment at once. A file's current judgment is its newest STANDING review — valid, with its check (the fate,
the checked words, the question), or refused or truncated, with its reason — as of the instant asked about, and
the lane its decision was taken on: the change gate's record (`reasoning_fingerprints`, `<file>|expert.file_review`)
says `shadow` when the file's domain is not switched on (`06` D2, s15-F5), any other word for the live lane, and
nothing when no decision was taken. `latest_valid`, read per file, returns an older valid review when the newest
standing one was refused: a brief built on it would show a judgment the expert no longer stands behind.
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine, text

from genios_engine.contracts import claim_check as C
from genios_engine.contracts.expert_review import ExpertReview
from genios_engine.reason import fingerprint_store as fs
from genios_engine.reason.expert import store as R

pytestmark = pytest.mark.pg

ORG, OTHER = "org_s15_current", "org_s15_current_other"
AT = datetime(2026, 9, 30, 12, 0, tzinfo=timezone.utc)
REVIEW = ExpertReview.from_mapping({
    "facts": [{"claim": "Meera asked for the reference calls", "evidence": ["evt_1"]}],
    "frames": {"primary": "a buyer doing diligence", "rivals": ["a polite stall"]},
    "expected_vs_actual": {"stage": None, "expected": "the calls set", "actual": "not set"},
    "scenarios": {"do_nothing": "it stalls", "act": "it moves", "best": "a pilot", "worst": "a pass",
                  "signals_to_watch": ["a call request"]},
    "appraisal": {"stakes": "high", "urgency": "high", "reversibility": "reversible", "reasons": ["she asked"]},
    "mode": "act", "next_move": {"who": "you", "what": "introduce Meera to the two pilot leads",
                                 "for_whom": "Meera", "by_when": None},
    "wait_or_stop": "do not wait", "done_when": "the calls are set"})
CHECKED = C.CheckedReview(verdicts=(C.LineVerdict("fact:1", C.KEPT),), fate=C.SHOWN, cited=("evt_1",),
                          words=C.CardWords(headline="Introduce Meera to the two pilot leads",
                                            situation="a buyer doing diligence", done_when="the calls are set",
                                            draft=None, to=None))


@pytest.fixture
def engine():
    url = os.environ.get("GENIOS_TEST_DATABASE_URL")
    if not url:
        pytest.skip("GENIOS_TEST_DATABASE_URL not set — needs a scratch Postgres database")
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


def _review(c, file, fp, *, at, status=R.VALID, org=ORG, checked=CHECKED):
    R.write_review(c, org_id=org, file_id=file, fingerprint=fp, model="claude-sonnet-5",
                   prompt_version="expert-review.v1", dossier_digest="d", status=status,
                   reason=None if status == R.VALID else f"{status}: why", review=REVIEW if status == R.VALID
                   else {"facts": []}, input_tokens=1, output_tokens=1, cost_micro_usd=1, at=at,
                   inputs={"file_id": file}, triggers=[{"kind": "new_evidence", "says": "new: evt_1"}],
                   checked=checked if status == R.VALID else None)


def _decided(c, file, outcome, *, at=AT, org=ORG):
    fs.record_decided(c, org_id=org, subject_key=f"{file}|expert.file_review", lane="compiled",
                      fingerprint="gfp", outcome=outcome, run_id="run_1", decided_at=at)


def test_every_file_reads_its_newest_standing_review_in_one_read(engine):
    with engine.begin() as c:
        _review(c, "node_a", "a1", at=AT - timedelta(days=3))
        _review(c, "node_a", "a2", at=AT - timedelta(days=1))
        _review(c, "node_b", "b1", at=AT - timedelta(days=2))
        _review(c, "node_x", "x1", at=AT - timedelta(days=1), org=OTHER)
    with engine.connect() as c:
        current = R.current_judgments(c, ORG, now=AT)
    assert set(current) == {"node_a", "node_b"}
    assert current["node_a"].stored.fingerprint == "a2" and current["node_a"].stored.review == REVIEW
    assert current["node_a"].stored.checked == CHECKED
    assert current["node_a"].checked.words.headline == "Introduce Meera to the two pilot leads"
    assert current["node_b"].stored.fingerprint == "b1"


def test_a_newer_refusal_is_the_current_judgment_never_an_older_valid_review(engine):
    with engine.begin() as c:
        _review(c, "node_a", "a1", at=AT - timedelta(days=3))
        _review(c, "node_a", "a2", at=AT - timedelta(days=1), status=R.REFUSED)
        _review(c, "node_t", "t1", at=AT - timedelta(days=3))
        _review(c, "node_t", "t2", at=AT - timedelta(days=1), status=R.TRUNCATED)
    with engine.connect() as c:
        current = R.current_judgments(c, ORG, now=AT)
        older = R.latest_valid(c, ORG, "node_a")
    assert older.fingerprint == "a1"                           # what a per-file read would have shown
    a = current["node_a"]
    assert a.stored.status == R.REFUSED and a.stored.review is None and a.stored.reason == "refused: why"
    assert not a.valid and a.checked is None
    assert current["node_t"].stored.status == R.TRUNCATED


def test_a_failed_or_carried_row_judged_nothing(engine):
    with engine.begin() as c:
        _review(c, "node_a", "a1", at=AT - timedelta(days=3))
        _review(c, "node_a", "a2", at=AT - timedelta(days=1), status=R.FAILED)
        _review(c, "node_c", "c1", at=AT - timedelta(days=1), status=R.OVER_BUDGET)
    with engine.connect() as c:
        current = R.current_judgments(c, ORG, now=AT)
    assert current["node_a"].stored.fingerprint == "a1" and current["node_a"].valid
    assert "node_c" not in current


def test_as_of_an_instant_a_later_review_is_not_yet_written(engine):
    with engine.begin() as c:
        _review(c, "node_a", "a1", at=AT - timedelta(days=3))
        _review(c, "node_a", "a2", at=AT + timedelta(hours=1))
        _review(c, "node_late", "l1", at=AT + timedelta(hours=1))
    with engine.connect() as c:
        current = R.current_judgments(c, ORG, now=AT)
    assert current["node_a"].stored.fingerprint == "a1" and "node_late" not in current


def test_the_lane_is_the_change_gates_record_as_of_the_instant(engine):
    with engine.begin() as c:
        for file in ("node_live", "node_shadow", "node_undecided", "node_later"):
            _review(c, file, f"{file}-1", at=AT - timedelta(days=1))
        _decided(c, "node_live", fs.EMITTED)
        _decided(c, "node_shadow", fs.SHADOW)
        _decided(c, "node_later", fs.SHADOW, at=AT + timedelta(hours=2))
        _decided(c, "node_undecided", fs.SHADOW, org=OTHER)     # another tenant's record is not ours
    with engine.connect() as c:
        current = R.current_judgments(c, ORG, now=AT)
    assert (current["node_live"].lane, current["node_live"].outcome) == ("live", fs.EMITTED)
    assert (current["node_shadow"].lane, current["node_shadow"].outcome) == ("shadow", fs.SHADOW)
    assert current["node_undecided"].lane is None and current["node_undecided"].outcome is None
    assert current["node_later"].lane is None


@pytest.mark.parametrize("outcome", [fs.STANDING, fs.SUPPRESSED, fs.DEFERRED, fs.INDETERMINATE])
def test_every_word_but_shadow_is_the_live_lane(engine, outcome):
    with engine.begin() as c:
        _review(c, "node_a", "a1", at=AT - timedelta(days=1))
        _decided(c, "node_a", outcome)
    with engine.connect() as c:
        assert R.current_judgments(c, ORG, now=AT)["node_a"].lane == "live"


def test_two_standing_reviews_at_one_instant_read_the_same_way_every_time(engine):
    with engine.begin() as c:
        _review(c, "node_a", "a1", at=AT - timedelta(days=1))
        _review(c, "node_a", "a9", at=AT - timedelta(days=1))
    with engine.connect() as c:
        reads = {R.current_judgments(c, ORG, now=AT)["node_a"].stored.fingerprint for _ in range(3)}
    assert reads == {"a9"}


def test_a_tenant_with_no_review_has_no_judgment(engine):
    with engine.connect() as c:
        assert R.current_judgments(c, ORG, now=AT) == {}
