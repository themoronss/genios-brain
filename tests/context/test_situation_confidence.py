"""L2.5.1-U1 · the sixth confidence axis — how good were the COMPARATIVE inputs?

The defect this axis exists to close is invisible by construction. After L2.7.4's modifiers land,
these two situations carry the SAME importance number:

    A  +1000 from a cohort position over 5 members, +1000 from a trend at trend_confidence_bp 5000
    B  +1000 from a cohort position over 200 members, +1000 from an eight-period trend

B's importance was earned; A's was arithmetic over a distribution that barely exists. Nothing in
the five existing axes says so, because none of them looks at what the COMPARISONS rested on —
they ask whether the situation is true, not whether the ranking of it was worth computing.

Three things here are easy to get subtly, invisibly wrong, and each has a test below:

  * AVERAGING the four sub-scores. Three strong trends hide the one thin cohort, and the axis
    reports certainty about the exact input the importance leaned on.
  * Scoring "no comparison was made" as 0. That is a claim about a measurement nobody took, and
    it drags a sixth of the vector to the floor for every situation predating the analytic
    stratum.
  * COLLAPSING the vector — the axis existing on paper and not in `Confidence`, which is doc 09's
    must-not-regress item 3.
"""
from __future__ import annotations

import ast
import dataclasses
import inspect
import re
import textwrap
from datetime import datetime, timezone

import pytest

from genios_engine.context import situations
from genios_engine.context.situations import (ANALYTIC_FLOOR, ANALYTIC_FULL_ANOMALY_PERIODS,
                                              ANALYTIC_FULL_HISTORY_POINTS,
                                              ANALYTIC_FULL_POPULATION, ANALYTIC_NONE,
                                              COVERAGE_UNKNOWN, SCORE_MAX, Confidence,
                                              analytic_score, coverage_is_known, score_situation)

NOW = datetime(2026, 9, 5, 12, 0, tzinfo=timezone.utc)

#: The two situations below carry the SAME importance. That is the point of the unit: the axis is
#: the only field that can tell them apart, so the acceptance case holds importance constant and
#: varies nothing but the quality of what the modifiers read.
IMPORTANCE_BP = 6_000


class _Trend:
    """The two fields this axis reads off `analytic.trend.Trend`. A stand-in rather than the real
    computer because the axis must not depend on a trend being computable in a unit test — it
    reads named fields, and `test_the_axis_reads_a_stored_fact_as_well_as_an_object` pins that the
    jsonb form those fields round-trip through reads identically."""

    def __init__(self, *, trend_confidence_bp: int, point_count: int) -> None:
        self.trend_confidence_bp = trend_confidence_bp
        self.point_count = point_count


class _Cohort:
    def __init__(self, *, population_size: int) -> None:
        self.population_size = population_size


class _Anomaly:
    def __init__(self, *, periods_used: int, flagged: bool = True) -> None:
        self.periods_used = periods_used
        self.flagged = flagged          # sits beside periods_used on the real AnomalyVerdict


def _code_of(fn) -> str:
    """A function's source with its comments and docstring parsed away — what the float scan
    reads. `ast.unparse` of the stripped tree, so the check sees expressions and nothing else."""
    tree = ast.parse(textwrap.dedent(inspect.getsource(fn)))
    for node in ast.walk(tree):
        body = getattr(node, "body", None)
        if (isinstance(node, (ast.FunctionDef, ast.Module)) and body
                and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant)
                and isinstance(body[0].value.value, str)):
            node.body = body[1:] or [ast.Pass()]
    return ast.unparse(tree)


def _score(**overrides) -> Confidence:
    args = dict(event_count=5, source_count=2, last_seen_at=NOW, open_discrepancies=0,
                open_merge_proposals=0, present_fields=set(), expected_fields={}, now=NOW)
    args.update(overrides)
    return score_situation(**args)


# ── the acceptance cases ─────────────────────────────────────────────────────────

def test_a_thin_comparison_is_visibly_less_certain_than_a_deep_one() -> None:
    """Doc 05's sentence, made a number: "A situation whose importance leaned on a 5-member
    cohort should be visibly less certain than one that leaned on 200." Same importance, and the
    axis is the only thing that separates them."""
    deep, _ = analytic_score([_Trend(trend_confidence_bp=9_000, point_count=8)],
                             [_Cohort(population_size=200)], [])
    thin, _ = analytic_score([_Trend(trend_confidence_bp=5_000, point_count=4)],
                             [_Cohort(population_size=5)], [])
    importance_deep = importance_bp_thin = IMPORTANCE_BP     # identical by construction
    assert importance_deep == importance_bp_thin
    assert deep > thin
    # "Materially", not "at all": a two-point gap would be a rounding artefact a renderer would
    # never surface, and the whole unit would be decorative.
    assert deep - thin >= 40


def test_three_strong_trends_do_not_hide_one_thin_cohort() -> None:
    """The averaging failure, named. The importance may well have moved because of the cohort,
    and a mean would report the three trends' certainty about it."""
    trends = [_Trend(trend_confidence_bp=9_500, point_count=12) for _ in range(3)]
    score, weakest = analytic_score(trends, [_Cohort(population_size=5)], [])
    assert weakest == "population"
    strong, _ = analytic_score(trends, [], [])
    assert score < strong, "the thin cohort must pull the axis down, not be averaged away"


def test_no_comparison_is_not_a_bad_comparison() -> None:
    """0 would say the comparative evidence is bad. The truth is that none was taken — a
    different fact, carried by the same sentinel `coverage_score` uses for an unregistered
    domain, and deliberately outside 0..100 so nobody can average it back in."""
    score, reason = analytic_score([], [], [])
    assert score == COVERAGE_UNKNOWN
    assert not coverage_is_known(score)
    assert score != 0
    assert reason == ANALYTIC_NONE
    assert not 0 <= score <= SCORE_MAX


def test_the_vector_has_six_axes_and_still_reports_a_weakest() -> None:
    """Doc 09's must-not-regress item 3: the vector is a vector. An axis that exists only in a
    spec is the same defect as one collapsed into a scalar."""
    axes = {f.name for f in dataclasses.fields(Confidence)} - {"overall", "missing", "inputs"}
    assert axes == {"evidence", "freshness", "consistency", "identity", "coverage", "analytic"}
    c = _score(open_discrepancies=2)
    assert c.inputs["weakest"] == "consistency"


def test_no_float_anywhere_in_the_axis_path() -> None:
    """Doctrine 2, checked at the source rather than by sampling outputs: an integer-valued float
    passes every equality test in this file and still poisons the first comparison it reaches.

    Scoped to the axis's own four functions — `coverage_score` next door genuinely does divide,
    and widening this grep to the module would either fail on that or have to whitelist it, which
    is how a real float sneaks in later. Docstrings and comments are parsed away rather than
    regexed away, so prose about ratios cannot fail the check and a `1.0` cannot hide in it.
    """
    body = "\n".join(_code_of(fn) for fn in (
        situations.analytic_score, situations._analytic_sub_score, situations._analytic_min,
        situations._analytic_reading))
    assert "//" in body, "the ramp must divide, and it must divide with //"
    assert "/" not in body.replace("//", ""), "true division in the analytic axis path"
    assert not re.search(r"\d\.\d|\bfloat\b|\bround\b|statistics|numpy", body), body


# ── the composition rule ─────────────────────────────────────────────────────────

def test_the_axis_is_the_minimum_of_the_four_not_their_mean() -> None:
    """Every sub-score present, one of them thin: the answer is the thin one, whichever it is."""
    score, weakest = analytic_score([_Trend(trend_confidence_bp=10_000, point_count=12)],
                                    [_Cohort(population_size=200)],
                                    [_Anomaly(periods_used=1)])
    assert weakest == "anomaly_periods"
    assert score == analytic_score([], [], [_Anomaly(periods_used=1)])[0]


def test_each_input_is_read_at_its_thinnest_not_its_average() -> None:
    """Two cohorts, one deep and one shallow: the axis reports the shallow one. The importance
    may have leaned on either, and the deep one does not vouch for the shallow one."""
    mixed, _ = analytic_score([], [_Cohort(population_size=200), _Cohort(population_size=5)], [])
    shallow, _ = analytic_score([], [_Cohort(population_size=5)], [])
    assert mixed == shallow


def test_a_dimension_no_input_carries_is_left_out_not_zeroed() -> None:
    """An AnomalyVerdict has no `point_count` and never will. Reading that absence as 0 would
    make every anomaly-only situation report a zero-period history it never claimed — the same
    mistake `freshness_score` refuses for undated evidence."""
    score, weakest = analytic_score([], [], [_Anomaly(periods_used=ANALYTIC_FULL_ANOMALY_PERIODS)])
    assert weakest == "anomaly_periods"
    assert score == SCORE_MAX
    assert score_situation(**dict(event_count=5, source_count=2, last_seen_at=NOW,
                                  open_discrepancies=0, open_merge_proposals=0,
                                  present_fields=set(), expected_fields={}, now=NOW,
                                  anomalies=[_Anomaly(periods_used=6)])
                           ).inputs["analytic_inputs"]["fewest_points"] is None


def test_a_thin_input_that_was_used_never_reads_as_zero() -> None:
    """A five-member cohort is thin, not absent. Zero is reserved for nothing, and nothing has
    its own sentinel."""
    for score, _ in (analytic_score([], [_Cohort(population_size=0)], []),
                     analytic_score([_Trend(trend_confidence_bp=0, point_count=0)], [], []),
                     analytic_score([], [], [_Anomaly(periods_used=0)])):
        assert score == ANALYTIC_FLOOR > 0


def test_saturation_stops_at_enough() -> None:
    """A 4000-member cohort is not four times surer than a 1000-member one, and a reader handed
    a still-climbing number would believe it was."""
    at_full, _ = analytic_score([], [_Cohort(population_size=ANALYTIC_FULL_POPULATION)], [])
    beyond, _ = analytic_score([], [_Cohort(population_size=ANALYTIC_FULL_POPULATION * 20)], [])
    assert at_full == beyond == SCORE_MAX


def test_a_boolean_beside_the_field_is_not_a_reading() -> None:
    """`flagged` is a bool and a bool is an int in Python. A True read as a one-period baseline
    is a number nobody measured, presented as a measurement."""
    class _Bogus:
        periods_used = True

    assert analytic_score([], [], [_Bogus()]) == (COVERAGE_UNKNOWN, ANALYTIC_NONE)


def test_ties_break_on_a_declared_order_not_on_the_reason_string() -> None:
    """Two sub-scores equal: the answer must not depend on which reason sorts first
    alphabetically, or a rename of a reason string silently changes what the card blames."""
    tied = analytic_score([_Trend(trend_confidence_bp=10_000, point_count=6)],
                          [_Cohort(population_size=100)], [])
    assert tied[0] == 55 and tied[1] == "population"


def test_the_axis_is_pure_and_repeatable() -> None:
    args = ([_Trend(trend_confidence_bp=7_000, point_count=9)], [_Cohort(population_size=40)],
            [_Anomaly(periods_used=4)])
    assert analytic_score(*args) == analytic_score(*args)


# ── the seams the rest of the layer joins on ─────────────────────────────────────

def test_the_axis_reads_a_stored_fact_as_well_as_an_object() -> None:
    """`trend_fact_value()` and `anomaly_fact_value()` store these numbers as jsonb, so a caller
    that read the fact back holds a dict where the computer held a dataclass. Both must answer
    identically or the axis silently reports "no comparison" for every situation assembled from
    stored facts."""
    as_object = analytic_score([_Trend(trend_confidence_bp=5_000, point_count=4)],
                               [_Cohort(population_size=30)], [_Anomaly(periods_used=5)])
    as_jsonb = analytic_score([{"trend_confidence_bp": 5_000, "point_count": 4}],
                              [{"population_size": 30}], [{"periods_used": 5}])
    assert as_object == as_jsonb


def test_the_saturation_points_are_the_analytic_stratum_s_own_numbers() -> None:
    """The constants are spelled in `situations.py` rather than imported, to keep a confidence
    axis from pulling in `context/analytic/`. Pinned here so the two cannot drift apart in
    silence: the day `trend.CONFIDENT_POINTS` moves, this fails instead of the axis quietly
    saturating at the wrong depth."""
    from genios_engine.context.analytic.anomaly import BASELINE_PERIODS
    from genios_engine.context.analytic.cohort import MIN_COHORT_POPULATION
    from genios_engine.context.analytic.trend import CONFIDENT_POINTS

    assert ANALYTIC_FULL_HISTORY_POINTS == CONFIDENT_POINTS
    assert ANALYTIC_FULL_ANOMALY_PERIODS == BASELINE_PERIODS
    # The smallest population a CohortPosition can legally be built on must land near the bottom
    # of the ramp — that is the whole complaint doc 05 files about 5-member cohorts.
    floor_position, _ = analytic_score([], [_Cohort(population_size=MIN_COHORT_POPULATION)], [])
    assert floor_position < SCORE_MAX // 4


def test_the_axis_reports_its_receipts() -> None:
    """Doctrine 3. A reader who disagrees with the number can re-derive it without going back to
    the analytic stratum for the inputs."""
    c = _score(trends=[_Trend(trend_confidence_bp=5_000, point_count=4)],
               cohort_positions=[_Cohort(population_size=5)],
               anomalies=[_Anomaly(periods_used=6)])
    assert c.inputs["analytic_known"] is True
    assert c.inputs["analytic_weakest"] == "population"
    assert c.inputs["analytic_inputs"] == {"smallest_population": 5,
                                           "lowest_trend_confidence_bp": 5_000,
                                           "fewest_points": 4,
                                           "fewest_anomaly_periods": 6}


def test_a_situation_that_compared_nothing_says_so_in_its_inputs() -> None:
    c = _score()
    assert c.analytic == COVERAGE_UNKNOWN
    assert c.inputs["analytic_known"] is False
    assert c.inputs["analytic_weakest"] == ANALYTIC_NONE


def test_a_thin_comparison_does_not_make_the_situation_less_true() -> None:
    """The axis is reported BESIDE `overall`, where `coverage` already sits, and for the same
    reason: a five-member cohort says nothing about whether the deal exists or who it is with.
    Folding it in would answer a question about a comparison with a number that reads as doubt
    about the facts, and would move every existing `overall` the day a modifier starts firing."""
    bare = _score()
    compared = _score(cohort_positions=[_Cohort(population_size=5)])
    assert compared.analytic < SCORE_MAX
    assert compared.overall == bare.overall


def test_the_five_older_axes_are_untouched_by_the_sixth() -> None:
    """Doc 09 must-not-regress item 3 protects the whole scorer, not just the vector's length."""
    bare = _score()
    compared = _score(trends=[_Trend(trend_confidence_bp=1_000, point_count=1)])
    for axis in ("evidence", "freshness", "consistency", "identity", "coverage"):
        assert getattr(bare, axis) == getattr(compared, axis)


@pytest.mark.parametrize("kwargs", [{"trends": []}, {"cohort_positions": ()}, {"anomalies": []}])
def test_the_new_arguments_are_optional_for_every_existing_caller(kwargs) -> None:
    """`refresh_situations` and eight other callers score situations that compare nothing. The
    axis must not make them pass an empty list to keep working."""
    assert _score(**kwargs).analytic == COVERAGE_UNKNOWN
