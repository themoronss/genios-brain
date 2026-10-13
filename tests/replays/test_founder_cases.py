"""STEP-01 · the founder golden set, replayed through the real chain and marked.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… pytest tests/replays/test_founder_cases.py -q

Forty synthetic cases, one per row of `speedrun008/YC-II W27/golden-labels.md`, each replayed with
its cassette through `engine_runner.run_case` — the production sync door, `finalize_l1`,
`_run_l2_chain` at the case's instants — and marked by `marking.judge` on what the founder would
see.

How a case reads in this file:

  * PASS or NOT EXPRESSIBLE → the test passes. A not-expressible case declared why, and the board
    counts it apart;
  * FAIL or NOT EXERCISED, with `blocked_on` naming the gap → a strict xfail. The day the gap
    closes, the case passes, the xfail fails, and `blocked_on` has to go. Only an
    `AssertionError` counts as the expected failure: a crash or a cassette miss is a real one;
  * FAIL or NOT EXERCISED without `blocked_on` → a failure. Every failing case says why.

The set-level checks hold the exam to its answer key: one case per labelled row, each the kind
its row's answer makes it, labelled by whoever labelled the row, with a synthetic cassette.

Without a scratch database the per-case tests skip, as every database test in this suite does —
EXCEPT where `GENIOS_GOLDEN_REQUIRED=1` (the `golden-pg` job), which turns the skip into a failure:
a golden set that skipped would be "a pass over an empty table".
"""
from __future__ import annotations

import os

import pytest

from tests.replays import cassettes
from tests.replays.founder_case import CASSETTE_DIR, load_cases, real_names_in
from tests.replays.marking import FAIL, NOT_EXERCISED, NOT_EXPRESSIBLE, PASS, judge
from tests.test_golden_labels_sheet import answer, rows

CASES = load_cases()
SHEET = {r["number"]: r for r in rows()}


def _scratch_db() -> None:
    if os.environ.get("GENIOS_TEST_DATABASE_URL"):
        return
    if os.environ.get("GENIOS_GOLDEN_REQUIRED") == "1":
        pytest.fail("GENIOS_GOLDEN_REQUIRED=1 and no GENIOS_TEST_DATABASE_URL — the golden set "
                    "never skips in its own job")
    pytest.skip("needs GENIOS_TEST_DATABASE_URL pointing at a scratch database")


# =================================================================================================
# 1 · the set is the answer key
# =================================================================================================
def test_one_case_per_labelled_row():
    by_row = {}
    for case in CASES:
        assert case.label_row not in by_row, (
            f"{case.case_id} and {by_row.get(case.label_row)} both claim row {case.label_row}")
        by_row[case.label_row] = case.case_id
    assert sorted(by_row) == sorted(SHEET), (
        f"rows without a case: {sorted(set(SHEET) - set(by_row))}; "
        f"cases naming no row: {sorted(set(by_row) - set(SHEET))}")
    assert len(CASES) >= 40


@pytest.mark.parametrize("case", CASES, ids=lambda c: c.case_id)
def test_a_case_is_the_kind_its_row_answers(case):
    row = SHEET[case.label_row]
    said = answer(row)
    if said == "no":
        assert case.kind == "must_abstain", f"row {row['number']} says no; {case.case_id} detects"
    else:
        assert case.kind == "must_detect", f"row {row['number']} says {said}; {case.case_id} abstains"
    if said == "brief only":
        assert not case.expressible("cards") and not case.expressible("brief"), (
            f"{case.case_id}: a brief-only answer is scored not expressible until STEP-15 (D12d)")
    if said == "yes":
        assert case.expressible("cards"), (
            f"{case.case_id}: row {row['number']} says yes — its cards must be judged")


@pytest.mark.parametrize("case", CASES, ids=lambda c: c.case_id)
def test_a_case_is_labelled_by_whoever_labelled_its_row(case):
    assert case.labelled_by == SHEET[case.label_row]["by"]


@pytest.mark.parametrize("case", CASES, ids=lambda c: c.case_id)
def test_every_case_has_a_synthetic_cassette_that_says_what_wrote_it(case):
    path = cassettes.path_for(case)
    assert path.is_file(), f"{case.case_id} has no cassette — scripts/golden_eval.py --record"
    source = cassettes.source_of(case)
    assert source == cassettes.IDEAL_READER or source.startswith(cassettes.LIVE_PREFIX), source
    assert not real_names_in(cassettes.load(case)), f"{case.case_id}: a real name in the cassette"


def test_no_cassette_belongs_to_no_case():
    known = {f"{c.case_id}.json" for c in CASES}
    stray = sorted(p.name for p in CASSETTE_DIR.glob("*.json") if p.name not in known)
    assert not stray, f"cassettes for no case: {stray}"


# =================================================================================================
# 2 · each case, through the real chain
# =================================================================================================
def _param(case):
    marks = [pytest.mark.pg, pytest.mark.golden]
    if case.blocked_on:
        marks.append(pytest.mark.xfail(strict=True, raises=AssertionError,
                                       reason=f"blocked: {case.blocked_on}"))
    return pytest.param(case, id=case.case_id, marks=marks)


@pytest.mark.parametrize("case", [_param(c) for c in CASES])
def test_founder_case(case):
    _scratch_db()
    run = cassettes.replayed(case)
    assert run.misses == (), f"{case.case_id}: cassette misses {run.misses}"
    mark = judge(case, run)
    assert mark.verdict in (PASS, NOT_EXPRESSIBLE, FAIL, NOT_EXERCISED)
    assert mark.verdict in (PASS, NOT_EXPRESSIBLE), (
        f"{case.case_id} ({case.title}) — {mark.verdict}"
        + (f", lost at {mark.lost_at}" if mark.lost_at else "") + f": {mark.reason}"
        + ("" if case.blocked_on else
           "\n  This case fails and names no gap: set `blocked_on` to the finding or step, or "
           "fix the engine."))
