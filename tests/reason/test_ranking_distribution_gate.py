"""The K1 gate report — a gate that cannot fail is not a gate.

`scripts/ranking_distribution.py` is what says whether K1 holds on a real pilot, and doc 08 says
K1 must hold on the same tenant and in the same fortnight as G7 and H5. So the thing that decides
that has to be exercised against rows that FAIL it as well as rows that pass — the flat
distribution the wave exists to end, the missing `formula_utility`, the manifest-fallback
`do_nothing`, and the empty window that must never read as success.

`measure()` takes rows, so every case below is the real verdict function over the real row shape
without a database. The connection is proved read-only by `tests/test_scripts_db_guard.py`.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from scripts.ranking_distribution import (
    MIN_DISTINCT_UTILITIES,
    MIN_DO_NOTHING_COMPUTED_BP,
    measure,
)

SINCE = datetime(2026, 9, 1, tzinfo=timezone.utc)
UNTIL = SINCE + timedelta(days=7)


def _candidate(index: int, *, utility: int, day: int = 0, importance: int | None = None,
               formula: int | None = 5_000, override: int | None = 9_000,
               capability: str = "expertise.deal"):
    components = {"impact": 6_000, "urgency": 5_000, "success": 6_000,
                  "effort": 2_000, "risk": 1_000}
    if importance is not None:
        components["importance"] = importance
    if formula is not None:
        components["formula_utility"] = formula
    if override is not None:
        components["priority_override"] = override
    return {"candidate_id": f"cand_{index}", "run_id": f"run_{index}",
            "final_utility_bp": utility, "score_components": components,
            "disposition": "eligible", "rank_position": 1, "capability_id": capability,
            "evaluation_time": SINCE + timedelta(days=day)}


def _output(index: int, *, source: str | None = "computed", day: int = 0,
            outcome: str = "decision", version: str | None = "ranking_weights@2"):
    core = {"uncertainty": [], "do_nothing_consequence": "..."}
    if version is not None:
        core["ranking_weights_version"] = version
    if source is not None:
        core["do_nothing"] = {"cost_bp": 4_000, "horizon": None,
                              "statement": "...", "source": source}
    return {"run_id": f"run_{index}", "outcome_kind": outcome, "decision_core": core,
            "capability_id": "expertise.deal", "evaluation_time": SINCE + timedelta(days=day)}


def _passing(count: int = 80):
    candidates = [_candidate(i, utility=3_000 + i * 17, importance=500 + i * 23)
                  for i in range(count)]
    outputs = [_output(i) for i in range(count)]
    return candidates, outputs


def _report(candidates, outputs):
    return measure(candidates, outputs, org_id="org_pilot", since=SINCE, until=UNTIL)


def test_a_healthy_population_passes_every_row():
    report = _report(*_passing())

    assert report.distinct_passed and report.divergence_passed
    assert report.importance_ranking_passed and report.do_nothing_passed
    assert report.passed
    assert report.ranking_versions == ("ranking_weights@2",)


def test_the_flat_distribution_this_wave_exists_to_end_fails():
    """Every ranked candidate at one identical utility — what the engine did before Z3."""
    candidates = [_candidate(i, utility=9_000, importance=None, formula=5_000)
                  for i in range(200)]
    report = _report(candidates, [_output(i) for i in range(200)])

    assert report.distinct_overall == 1
    assert not report.distinct_passed
    assert not report.passed


def test_the_gate_is_per_day_and_the_worst_day_decides():
    """Seven flat days that differ from each other would pass a pooled set and must not."""
    candidates = [_candidate(i, utility=9_000 + day, day=day, importance=5_000)
                  for day, i in enumerate(range(7))]
    report = _report(candidates, [_output(i) for i in range(7)])

    assert report.distinct_overall == 7
    assert report.worst_day == ("2026-09-01", 1)
    assert not report.distinct_passed


def test_a_single_candidate_without_formula_utility_fails_the_hundred_percent_row():
    candidates, outputs = _passing()
    candidates[13]["score_components"].pop("formula_utility")
    report = _report(candidates, outputs)

    assert report.with_formula == len(candidates) - 1
    assert not report.divergence_passed
    assert not report.passed


def test_importance_that_never_varies_cannot_demonstrate_the_ranking():
    candidates = [_candidate(i, utility=3_000 + i * 17, importance=5_000) for i in range(80)]
    report = _report(candidates, [_output(i) for i in range(80)])

    assert report.with_importance == 80
    assert report.ranked_by_importance == (("expertise.deal", 1, 80),)
    assert not report.importance_ranking_passed


def test_importance_that_never_arrived_at_all_fails_the_same_row():
    candidates = [_candidate(i, utility=3_000 + i * 17, importance=None) for i in range(80)]
    report = _report(candidates, [_output(i) for i in range(80)])

    assert report.with_importance == 0
    assert not report.importance_ranking_passed
    assert not report.passed


def test_the_do_nothing_threshold_binds_at_exactly_eighty_percent():
    candidates, _ = _passing(100)
    at_gate = [_output(i, source="computed" if i < 80 else "manifest_fallback")
               for i in range(100)]
    below = [_output(i, source="computed" if i < 79 else "manifest_fallback")
             for i in range(100)]

    assert _report(candidates, at_gate).computed_bp == MIN_DO_NOTHING_COMPUTED_BP
    assert _report(candidates, at_gate).do_nothing_passed
    assert not _report(candidates, below).do_nothing_passed


def test_a_decision_carrying_no_do_nothing_counts_against_the_rate_rather_than_vanishing():
    """An absent record is not a computed one, and dropping it from the denominator would let a
    lane that stopped recording read as 100%."""
    candidates, _ = _passing(10)
    report = _report(candidates, [_output(i, source=None) for i in range(10)])

    assert report.do_nothing_absent == 10
    assert report.computed_bp == 0
    assert not report.do_nothing_passed


def test_a_non_decision_outcome_is_not_a_published_decision():
    candidates, _ = _passing(10)
    report = _report(candidates, [_output(i, outcome="defer", source=None) for i in range(10)])

    assert report.decisions == 0
    assert report.do_nothing_total == 0
    assert not report.do_nothing_passed


def test_an_empty_window_is_a_failure_and_never_a_pass():
    report = _report([], [])

    assert report.candidates == 0
    assert report.worst_day is None
    assert not report.passed


def test_a_legacy_decision_reports_the_version_its_absence_means():
    candidates, _ = _passing(60)
    report = _report(candidates, [_output(i, version=None) for i in range(60)])

    assert report.ranking_versions == ("ranking_weights@1",)


def test_the_digest_is_stable_across_row_order_and_moves_with_a_score():
    candidates, outputs = _passing(30)
    shuffled = list(reversed(candidates))
    moved = [dict(row) for row in candidates]
    moved[3] = {**moved[3], "final_utility_bp": moved[3]["final_utility_bp"] + 1}

    assert _report(candidates, outputs).digest == _report(shuffled, outputs).digest
    assert _report(moved, outputs).digest != _report(candidates, outputs).digest


def test_a_score_components_map_stored_as_json_text_is_read_the_same_way():
    """psycopg hands jsonb back as a dict; a driver or an export that hands back text must not
    silently report every candidate as missing its formula."""
    candidates, outputs = _passing(60)
    as_text = [{**row, "score_components": json.dumps(row["score_components"])}
               for row in candidates]

    assert _report(as_text, outputs).with_formula == 60
    assert _report(as_text, outputs).passed


def test_the_report_serialises_every_gate_row_it_was_asked_about():
    body = _report(*_passing()).as_dict()

    assert body["gate"] == "K1"
    assert body["min_distinct"] == MIN_DISTINCT_UTILITIES
    assert body["do_nothing"]["min_computed_bp"] == MIN_DO_NOTHING_COMPUTED_BP
    assert set(body["checks"]) == {"distinct", "divergence", "importance_ranks", "do_nothing"}
    assert json.dumps(body)          # printable with --json


def test_an_empty_window_reads_as_no_data_and_not_as_a_failing_engine():
    """`passed` is False for an empty window and MUST stay False — the property's own docstring
    says why: *"a gate that returns green for an empty table is how 'the model never ran' reads as
    success"*. Nothing here relaxes that.

    What this pins is the RENDERED verdict, because the two states need opposite work and the
    report used to print the same word for both. `--days` counts back from the WALL clock, so a
    seeded or historical population — which is how every K1 measurement in this repository is
    built — reports zero candidates and read `VERDICT FAIL`, i.e. "the ranking is broken", when
    the truth was "you looked in the wrong week". A gate that can say FAIL for having looked in
    the wrong week gets disbelieved once and ignored afterwards.
    """
    from scripts.ranking_distribution import NO_DATA_VERDICT, _render, _verdict

    empty = _report([], [])
    assert empty.passed is False                       # unchanged, and it must stay unchanged
    assert empty.candidates == 0
    assert _verdict(empty) == NO_DATA_VERDICT
    assert "NO DATA" in _render(empty)
    assert "VERDICT           FAIL" not in _render(empty)

    # A population that IS there and fails a row still says FAIL, so the new branch cannot hide a
    # real defect: one distinct utility across 60 candidates is the flat lane K1 exists to catch.
    candidates, outputs = _passing(60)
    flat = [{**row, "final_utility_bp": 4000} for row in candidates]
    report = _report(flat, outputs)
    assert report.candidates == 60 and report.passed is False
    assert _verdict(report) == "FAIL"
