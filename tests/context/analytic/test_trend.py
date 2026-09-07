"""H2 · L2.4.3 — the TREND COMPUTER (BLG-08). The gate for `context/analytic/trend.py`.

Doc 09 invokes gate H2 as:

    pytest tests/context/analytic/test_trend.py tests/context/analytic/test_cohort.py -q

Organised the way doc 04's acceptance list is written: one test per row, then the cases the list
implies rather than states — the gap that is not a zero, the arithmetic at the boundary,
determinism, and the wiring.

**WHY THE WIRING TESTS ARE THE ONES THAT MATTER.** Layer 1 shipped six units that were built,
green and called by nothing on a real request path; each cost a full rework cycle and each was
found only by adversarial review. Every test above `THE WIRING` in this file constructs the series
itself and proves the UNIT. `test_the_sweep_writes_the_trend_fact` drives
`context/runner.process_pending` — the sweep both API sync routes and the upload route call —
against a real Postgres and asserts a `derived.trend.*` row exists afterwards. Delete the two
lines in `runner.py` and that test fails and nothing else here does.

**THE MUTATION CHECK.** Invert the sign of the slope in `compute_trend` — negate the return of
`_ls_slope_scaled` and `_robust_slope_scaled`, or swap the two comparisons in `_direction` — and
`test_a_monotonic_decline_over_six_periods_is_declining` fails first: it asserts DECLINING *and* a
negative `relative_slope_bp` on a series that only ever falls. `test_the_five_directions` fails
with it (RISING and DECLINING trade places), and `test_inverting_every_reading_mirrors_the_trend`
fails on the magnitude if the inversion is applied to only one of the two slopes. The contract
would catch the crudest version on its own — `Trend` refuses RISING with a negative slope — which
is exactly why the direction and the sign are asserted together here rather than one at a time.
"""

from __future__ import annotations

import io
import tokenize
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from sqlalchemy import text

from genios_engine.context.analytic.history import (MetricGrain, PostgresMetricHistory,
                                                    SampleReason, period_start)
from genios_engine.context.analytic.sampler import TrendedMetric, sampler_registry
from genios_engine.context.analytic.trend import (COVERAGE_FLOOR_BP, DIRECTION_THRESHOLD_BP,
                                                  MAX_TREND_FACTS_PER_SWEEP, TREND_FACT_PREFIX,
                                                  TREND_WINDOW_PERIODS, compute_trend,
                                                  find_changepoint, refresh_trend_facts,
                                                  trend_fact_field, trend_fact_value)
from genios_engine.contracts.analytic import (MAX_TREND_CONFIDENCE_BP, MIN_TREND_POINTS,
                                              MetricPoint, MetricUnit, TrendDirection)

pytestmark = pytest.mark.unit

ORG = "org_scratch_tests"
NODE = "node_acct_north"
METRIC = "engagement.touch_count"
_ENGINE = Path(__file__).resolve().parents[3] / "genios_engine"

#: The month every series in this file starts in. A fixed date rather than "now minus n": the
#: computer takes no clock, so a test that reached for one would be asserting on a different
#: series every day it ran.
EPOCH = datetime(2026, 1, 1, tzinfo=timezone.utc)


# =================================================================================================
# BUILDERS — a series is data, so every row states the world it is about as a list of numbers
# =================================================================================================

def month(offset: int) -> datetime:
    """The start of the month `offset` months after `EPOCH`. Integer month arithmetic."""
    year, remainder = divmod(EPOCH.year * 12 + (EPOCH.month - 1) + offset, 12)
    return EPOCH.replace(year=year, month=remainder + 1)


def series(values, *, node: str = NODE, metric: str = METRIC) -> tuple[MetricPoint, ...]:
    """A DENSE series from a list of readings, where `None` is an honest gap.

    Dense is the contract with `history.read_series`: one point per period in range, gaps carried
    as `known=False`. A builder that dropped the `None`s would hand `compute_trend` a series that
    claims 100% coverage and is nothing of the kind — which is the exact fault the coverage floor
    exists to catch, so the test suite must not be able to construct it by accident.
    """
    return tuple(MetricPoint(subject_node_id=node, metric=metric, value_bp=value,
                             unit=MetricUnit.COUNT, observed_at=month(index),
                             known=value is not None)
                 for index, value in enumerate(values))


#: The five answers, one row each, as doc 04's step 4 and step 1 define them.
DIRECTION_ROWS = (
    # name, readings, expected direction
    ("a series that only rises", [10, 20, 30, 40, 50, 60], TrendDirection.RISING),
    ("a series that only falls", [60, 50, 40, 30, 20, 10], TrendDirection.DECLINING),
    ("a series that does not move", [100, 100, 100, 100, 100, 100], TrendDirection.FLAT),
    ("three readings and no more", [30, 20, 10], TrendDirection.INSUFFICIENT_HISTORY),
    ("six readings scattered over eleven periods",
     [60, None, 50, None, 40, None, 30, None, 20, None, 10],
     TrendDirection.INSUFFICIENT_COVERAGE),
)


# =================================================================================================
# U1 · THE FIVE DIRECTIONS
# =================================================================================================

@pytest.mark.parametrize("name,readings,expected",
                         DIRECTION_ROWS, ids=[row[0] for row in DIRECTION_ROWS])
def test_the_five_directions(name, readings, expected) -> None:
    """Every member of `TrendDirection`, including both refusals, reachable from a real series."""
    assert compute_trend(series(readings)).direction is expected, name


def test_a_monotonic_decline_over_six_periods_is_declining() -> None:
    """Doc 09's headline row — and THE MUTATION CHECK named in the module docstring.

    Direction and sign are asserted together on purpose. An inverted slope makes this series
    RISING with a positive `relative_slope_bp`, which is internally consistent and would survive
    a test that only looked at one of the two.

    `streak=6` is doc 09's literal wording: five consecutive down-moves are six periods of
    decline, counted in periods rather than in steps because that is the number a card prints.
    """
    trend = compute_trend(series([60, 50, 40, 30, 20, 10]))

    assert trend.direction is TrendDirection.DECLINING
    assert trend.relative_slope_bp < 0, "a decline that reported a positive slope is a sign flip"
    assert trend.streak_periods == 6
    assert trend.point_count == 6
    assert trend.coverage_ratio_bp == 10_000


def test_too_few_points_refuses_rather_than_answering_weakly() -> None:
    """V-5, and the reason it is a refusal instead of a hedge.

    Three readings on a straight line fit perfectly — a weak-answer design would report DECLINING
    with a lowered confidence and a card would print it. `INSUFFICIENT_HISTORY` says the thing
    that is actually true: we have not been watching long enough to know.
    """
    trend = compute_trend(series([30, 20, 10]))

    assert trend.direction is TrendDirection.INSUFFICIENT_HISTORY
    assert trend.point_count == 3 < MIN_TREND_POINTS
    assert trend.trend_confidence_bp == 0 and trend.streak_periods == 0
    assert trend.evidence_points, "even a refusal shows which periods it looked at"


def test_a_coverage_gap_is_refused_not_reported_as_a_decline() -> None:
    """**The decisive row.** Doc 04 names this the worst output the group can produce.

    Six falling readings, every other period missing. There are enough points to fit — the
    history floor is cleared — and the fit through them is a clean decline. Reporting it would be
    a false churn alarm about a customer who is fine, generated by the tenant having one fewer
    source connected than we assumed.
    """
    trend = compute_trend(series([60, None, 50, None, 40, None, 30, None, 20, None, 10]))

    assert trend.direction is TrendDirection.INSUFFICIENT_COVERAGE
    assert trend.point_count >= MIN_TREND_POINTS, "this is not the history refusal in disguise"
    assert trend.coverage_ratio_bp < COVERAGE_FLOOR_BP
    assert trend.trend_confidence_bp == 0


def test_exactly_the_coverage_floor_still_answers() -> None:
    """The floor is a `<` comparison, so 60% known answers and 59% does not. Pinned because an
    off-by-one here silently converts a whole class of real trends into refusals."""
    six_known_of_ten = compute_trend(series([10, 20, 30, 40, 50, 60, None, None, None, None]))

    assert six_known_of_ten.coverage_ratio_bp == COVERAGE_FLOOR_BP
    assert six_known_of_ten.direction is TrendDirection.RISING


# =================================================================================================
# U1 · GAPS ARE GAPS
# =================================================================================================

def test_a_gap_is_never_read_as_a_zero() -> None:
    """The same six rising readings, then four periods we could not see — against the same six
    readings followed by four measured zeros. **The two must not agree.**

    This is the whole gap discipline in one assertion, and it is stated as a comparison rather
    than as a single expectation because that is how the bug would actually arrive: an
    implementation that filled `known=False` with `0` produces a perfectly well-formed `Trend`
    whose every field typechecks. It just says DECLINING about an account that is growing.
    """
    with_gaps = compute_trend(series([10, 20, 30, 40, 50, 60, None, None, None, None]))
    with_zeros = compute_trend(series([10, 20, 30, 40, 50, 60, 0, 0, 0, 0]))

    assert with_gaps.direction is TrendDirection.RISING
    assert with_zeros.direction is TrendDirection.DECLINING
    assert with_gaps.point_count == 6 and with_zeros.point_count == 10
    assert with_gaps.coverage_ratio_bp < with_zeros.coverage_ratio_bp, (
        "the gaps must count AGAINST coverage — an interpolated value improves the very ratio "
        "that exists to reveal it")


def test_a_gap_breaks_the_streak() -> None:
    """Six falling readings run together are six periods of decline; the same six readings with
    holes between them are not consecutive periods and must not be counted as one run.

    The direction survives — the fit is over the period INDEX, so the gaps widen the spacing
    rather than pulling the later readings backwards — but the streak collapses, which is the
    honest reading: we cannot claim an unbroken run through periods we did not observe.
    """
    contiguous = compute_trend(series([60, 50, 40, 30, 20, 10]))
    holed = compute_trend(series([60, None, 50, 40, None, 30, 20, None, 10]))

    assert contiguous.direction is holed.direction is TrendDirection.DECLINING
    assert contiguous.streak_periods == 6
    assert holed.streak_periods == 1, "a hole ends the run; it does not span it"
    assert holed.trend_confidence_bp < contiguous.trend_confidence_bp


def test_a_gap_carries_no_value_at_all() -> None:
    """The builder cannot construct the fabricated observation, because the CONTRACT refuses it.
    Pinned here so the guarantee this module leans on is visible from the module that leans on it.
    """
    with pytest.raises(ValueError, match="known=False"):
        MetricPoint(subject_node_id=NODE, metric=METRIC, value_bp=0, unit=MetricUnit.COUNT,
                    observed_at=month(0), known=False)


# =================================================================================================
# U1 · STEP 3, THE ONE PEOPLE SKIP — a slope means nothing without a base
# =================================================================================================

@pytest.mark.parametrize("name,readings,expected", (
    ("a drop of five on a base of five thousand",
     [5000, 4995, 4990, 4985, 4980, 4975], TrendDirection.FLAT),
    ("the same drop of five on a base of eight", [23, 18, 13, 8], TrendDirection.DECLINING),
), ids=("base 5000", "base 8"))
def test_the_same_absolute_drop_is_normalised_against_its_own_base(name, readings,
                                                                   expected) -> None:
    """Doc 04's pair, verbatim. The absolute slope is -5 per period in both rows.

    Without step 3 both are the same number and both get the same word, which makes "declining"
    incomparable between `engagement.touch_count` and `deal.value_minor_units` and useless on a
    card that shows them side by side.
    """
    trend = compute_trend(series(readings))

    assert trend.direction is expected, name
    if expected is TrendDirection.FLAT:
        assert abs(trend.relative_slope_bp) <= DIRECTION_THRESHOLD_BP, (
            "flat is a statement about the NORMALISED slope; a large one under a flat label would "
            "mean the threshold and the direction are being read off different numbers")
    else:
        assert trend.relative_slope_bp < -DIRECTION_THRESHOLD_BP


def test_an_all_zero_series_is_flat_and_not_a_division_error() -> None:
    """The base is floored at 1 for exactly this series. A metric that has read zero for six
    months is a real and common reading — a dormant account — and it must produce an answer."""
    trend = compute_trend(series([0, 0, 0, 0, 0, 0]))

    assert trend.direction is TrendDirection.FLAT
    assert trend.relative_slope_bp == 0


def test_the_slope_survives_integer_division_on_small_values() -> None:
    """Doc 04's fourth failure mode: "integer division precision loss -> slope rounds to zero".

    One touch fewer every three months is a slope of -1/3 per period. Unscaled integer division
    reports that as 0 and the account looks stable while it goes quiet; the x10000 scaling applied
    BEFORE the divide is what keeps it visible.
    """
    trend = compute_trend(series([4, 4, 3, 3, 3, 2, 2, 2, 1]))

    assert trend.relative_slope_bp < 0, "a sub-unit slope must not round to zero"
    assert trend.direction is TrendDirection.DECLINING


# =================================================================================================
# U1 · THE SHAPES THAT MUST NOT PRODUCE A DIRECTION
# =================================================================================================

def test_a_v_shaped_series_is_flat() -> None:
    """Doc 04 asks which answer a rise-then-fall gives and asks for it to be documented: **FLAT**.

    A single direction over the whole window is the only claim this unit makes, and a symmetric V
    has no such direction — the rise and the fall cancel in both estimators. The honest reading of
    "it went up and then it came down" is a CHANGEPOINT, which is U2's answer and which
    `test_the_changepoint_is_the_longest_suffix_that_differs` gets for this same series.
    """
    assert compute_trend(series([10, 20, 30, 40, 50, 40, 30, 20, 10])).direction \
        is TrendDirection.FLAT


def test_one_huge_outlier_does_not_flip_a_flat_series_to_rising() -> None:
    """Doc 04's outlier row — the one plain least squares cannot pass.

    Nine readings of 100 and a tenth of 100000. Least squares alone normalises to +5400 bp, eleven
    times the direction threshold, and reports RISING on the strength of one number. The median of
    the 45 pairwise slopes is 0, because thirty-six of those pairs are flat. Both are computed and
    both must agree, so the answer is FLAT — see `_robust_slope_scaled` for the arithmetic.
    """
    trend = compute_trend(series([100] * 9 + [100_000]))

    assert trend.direction is TrendDirection.FLAT
    assert trend.point_count == 10, "the outlier is still a reading; it is not discarded"


# =================================================================================================
# U1 · THE CAP, THE REFUSALS AND DETERMINISM
# =================================================================================================

@pytest.mark.parametrize("readings", [
    [10, 20, 30, 40, 50, 60],                                    # a clean rise
    list(range(10, 130, 10)),                                    # twelve perfect periods
    list(range(10, 610, 10)),                                    # sixty perfect periods
    [60, 50, 40, 30, 20, 10],
    [100] * 20,
    [10, 20, 30, 40, 50, 60, None, None, None, None],
    [30, 20, 10],
    [60, None, 50, None, 40, None, 30, None, 20, None, 10],
], ids=["rise", "twelve", "sixty", "fall", "flat", "gapped", "too few", "too holed"])
def test_confidence_never_exceeds_the_cap(readings) -> None:
    """V-4, across every shape in this file including the ones designed to maximise it.

    A sixty-period series with perfect coverage, a perfect fit and a sixty-period streak is the
    most support this system can ever have for a trend, and it still cannot reach certainty: the
    components are scaled INTO the cap rather than clipped at it, so `MAX_TREND_CONFIDENCE_BP` is
    unexceedable by construction rather than by a check a later edit can move.
    """
    assert compute_trend(series(readings)).trend_confidence_bp <= MAX_TREND_CONFIDENCE_BP


def test_the_ceiling_is_reachable_by_a_saturated_series() -> None:
    """The cap is a real ceiling and not an unreachable one — otherwise the top of the confidence
    range would be dead space and a ranker would never distinguish the best-supported trends."""
    assert compute_trend(series(list(range(10, 130, 10)))).trend_confidence_bp \
        == MAX_TREND_CONFIDENCE_BP


@pytest.mark.parametrize("readings", [[30, 20, 10],
                                      [60, None, 50, None, 40, None, 30, None, 20, None, 10]],
                         ids=["insufficient history", "insufficient coverage"])
def test_a_refusal_carries_no_confidence_and_no_streak(readings) -> None:
    """A number attached to an answer we declined to give is a number a ranker will sort on."""
    trend = compute_trend(series(readings))

    assert trend.trend_confidence_bp == 0
    assert trend.streak_periods == 0
    assert trend.relative_slope_bp == 0


def test_identical_input_replayed_is_byte_identical() -> None:
    """Two separately-built copies of one series, serialised, compared as bytes.

    Byte-identical rather than field-equal: the whole reason this measurement refuses a model is
    that a March reading and a September reading of the same stored series have to be the same
    reading, and "the same" has to mean the same all the way down to what gets written into a fact.
    """
    readings = [60, 55, 41, 44, 30, None, 22, 18]

    first = compute_trend(series(readings)).model_dump_json()
    second = compute_trend(series(readings)).model_dump_json()

    assert first.encode() == second.encode()


def test_inverting_every_reading_mirrors_the_trend() -> None:
    """`compute_trend(-series)` is the exact negation of `compute_trend(series)`.

    This is what truncation-toward-zero buys (`_idiv`): Python's `//` floors, which would bias
    every negative slope one unit further from zero than its positive mirror and make the two
    directions cross the threshold at different magnitudes. It is also the second line of defence
    on the sign mutation — an inversion applied to one of the two slopes but not the other breaks
    the mirror here even when the direction happens to survive.
    """
    rising = compute_trend(series([10, 22, 31, 44, 50, 61]))
    falling = compute_trend(series([-10, -22, -31, -44, -50, -61]))

    assert rising.direction is TrendDirection.RISING
    assert falling.direction is TrendDirection.DECLINING
    assert falling.relative_slope_bp == -rising.relative_slope_bp
    assert falling.streak_periods == rising.streak_periods
    assert falling.trend_confidence_bp == rising.trend_confidence_bp


def test_min_points_cannot_be_lowered_below_the_contract_floor() -> None:
    """V-5 is a contract rule, so the parameter that looks like it could relax it cannot."""
    with pytest.raises(ValueError, match="cannot be lowered"):
        compute_trend(series([30, 20, 10]), min_points=3)


def test_an_empty_series_is_a_caller_bug_not_a_refusal() -> None:
    """A refusal is a statement about the tenant's data. An empty range is a statement about the
    caller's arithmetic, and `Trend` cannot carry it — a trend with no receipt is unconstructible.
    """
    with pytest.raises(ValueError, match="needs a series"):
        compute_trend([])


def test_no_float_arithmetic_anywhere_in_the_module() -> None:
    """Source-level, and tokenised rather than grepped so a `/` inside a docstring cannot fool it.

    A single true division would put a float into a measurement that is compared against itself
    across versions, and nothing downstream would notice until two runs of one series disagreed
    in the last decimal place on a card.
    """
    source = (_ENGINE / "context" / "analytic" / "trend.py").read_text()
    assert "float(" not in source and "numpy" not in source and "import statistics" not in source

    divisions = [token for token in tokenize.generate_tokens(io.StringIO(source).readline)
                 if token.type == tokenize.OP and token.string in ("/", "/=")]
    assert not divisions, f"true division at line(s) {[t.start[0] for t in divisions]}"


# =================================================================================================
# U2 · CHANGEPOINT DETECTION
# =================================================================================================

def test_the_changepoint_is_the_longest_suffix_that_differs() -> None:
    """"Since March" rather than "declining" — and the LONGEST such suffix, not the last one.

    The same V-shaped series `compute_trend` calls FLAT. The turn is at index 4, and index 5, 6
    and 7 would all also produce a declining suffix against a rising prefix; returning any of them
    would date the change to the last period the arithmetic still noticed it.
    """
    changepoint = find_changepoint(series([10, 20, 30, 40, 50, 40, 30, 20, 10]))

    assert changepoint is not None
    assert changepoint.index == 4
    assert changepoint.at == month(4)
    assert changepoint.before.direction is TrendDirection.RISING
    assert changepoint.after.direction is TrendDirection.DECLINING
    assert changepoint.turned == "rising->declining"


def test_a_series_that_never_turned_has_no_changepoint() -> None:
    """`None` is the ordinary answer, not a failure. A steady decline changed at no point in it."""
    assert find_changepoint(series([80, 70, 60, 50, 40, 30, 20, 10])) is None


def test_a_changepoint_is_never_dated_to_a_period_we_could_not_see() -> None:
    """Dating a change to a month with no reading is the gap-as-observation fault with a calendar
    on it. The split at the hole is skipped and the answer is either a known period or nothing."""
    readings = [10, 20, 30, 40, None, 40, 30, 20, 10]
    points = series(readings)
    changepoint = find_changepoint(points)

    assert changepoint is None or changepoint.at != month(4), "index 4 is the hole"
    if changepoint is not None:
        assert points[changepoint.index].known


def test_both_sides_of_a_changepoint_must_clear_the_four_point_floor() -> None:
    """A three-period suffix cannot be one side of "it changed": under the floor there is no
    trend to have changed INTO, and the claim would rest on the same two-readings-and-a-line the
    whole unit refuses."""
    assert find_changepoint(series([10, 20, 30, 40, 50, 60, 50])) is None


def test_a_changepoint_needs_both_segments_to_answer_at_all() -> None:
    """A prefix full of holes refuses, and a refusal cannot be the "before" of a change — we do
    not know what it was before."""
    assert find_changepoint(series([10, None, 30, None, 50, None, 20, 15, 10, 5])) is None


# =================================================================================================
# U3 · THE TREND AS A GRAPH FACT — the shape of what L3 reads
# =================================================================================================

def test_the_fact_field_is_namespaced_per_metric() -> None:
    """One field per metric, not one blob per node: L3 selects on `field`, and a blob makes
    "is engagement declining" a read of every trend the node has."""
    assert trend_fact_field(METRIC) == f"{TREND_FACT_PREFIX}{METRIC}"
    assert trend_fact_field(METRIC).startswith("derived.")


def test_the_fact_body_carries_the_answer_its_strength_and_a_pointer_to_the_series() -> None:
    """Doc 04 U3: the fact carries `trend_confidence_bp` and a pointer to the series.

    The pointer is `metric_history`'s primary key minus the ambient tenant, so "where did this
    decline come from" is a query a reader can run rather than a claim that stops at the card.
    """
    points = series([60, 50, 40, 30, 20, 10])
    trend = compute_trend(points)
    body = trend_fact_value(trend, find_changepoint(points))

    assert body["direction"] == "declining"
    assert body["trend_confidence_bp"] == trend.trend_confidence_bp
    assert body["relative_slope_bp"] == trend.relative_slope_bp < 0
    assert body["series"]["subject_node_id"] == NODE
    assert body["series"]["metric"] == METRIC
    assert body["series"]["first_period"] == month(0).isoformat()
    assert body["series"]["last_period"] == month(5).isoformat()
    assert body["series"]["periods"] == 6
    assert "changepoint" not in body, "a straight decline turned at no point in it"


def test_a_refusal_is_written_as_a_fact_too() -> None:
    """The stale-fact rule. Writing only real directions leaves last week's DECLINING sitting on a
    node whose series has since gone dark, and nothing ever retracts it."""
    body = trend_fact_value(compute_trend(series([30, 20, 10])))

    assert body["direction"] == "insufficient_history"
    assert body["trend_confidence_bp"] == 0


# =================================================================================================
# THE WIRING — a REAL sweep, on a REAL database, reaching the trend computer
# =================================================================================================

def test_the_drain_calls_the_trend_refresh() -> None:
    """`process_pending` is what every sync route and the upload route call. A trend computer
    nothing invokes is a function, not a feature — this is the cheap absence guard; the row below
    is the real one."""
    runner = (_ENGINE / "context" / "runner.py").read_text()
    assert "refresh_trend_facts" in runner
    assert "trend_facts" in runner


@pytest.mark.pg
def test_the_sweep_writes_the_trend_fact(pg_store) -> None:
    """**THIS IS THE TEST THAT MATTERS.** `context/runner.process_pending` reaches U3.

    Eleven monthly readings of `deal.stage_age_days` are seeded through the real store — a deal
    whose stage age has been falling — and the sweep itself samples the twelfth. Nothing above
    this line would notice if the two lines in `runner.py` were deleted, because every one of them
    builds its series by hand.

    The sweep is driven with no pending events on purpose: a trend is measured against a CLOCK,
    so the org whose inbox went quiet is exactly the org whose decline is worth surfacing, and
    gating the pass on "did we ingest anything" would freeze its trend at the last sweep that
    happened to have mail.
    """
    from genios_engine.context.runner import process_pending
    from genios_engine.platform.config import get_settings

    org = "org_trend_wiring"
    at = datetime(2026, 3, 1, 9, 0, tzinfo=timezone.utc)
    _seed_org_with_a_deal(pg_store, org, at)
    _seed_declining_history(pg_store, org, at)
    try:
        out = process_pending(org_id=org, store=pg_store, llm=None,
                              crypto_key=get_settings().crypto_key, eval_time=at)
        assert out["processed"] == 0, "no events: this sweep drained nothing"
        assert out["trend_facts"] > 0, (
            "the sweep reached no trend computer — `refresh_trend_facts` is not on the real "
            "request path")

        field = trend_fact_field(TrendedMetric.DEAL_STAGE_AGE_DAYS.value)
        with pg_store.engine.connect() as conn:
            rows = conn.execute(text(
                "select field, value from graph_facts "
                "where org_id=:o and field like :p order by field"),
                {"o": org, "p": f"{TREND_FACT_PREFIX}%"}).all()
        written = {row.field: row.value for row in rows}
        assert field in written, f"no {field} fact: the series was there and no trend was written"

        body = written[field]
        assert body["direction"] == "declining", body
        assert body["relative_slope_bp"] < 0
        assert body["point_count"] == TREND_WINDOW_PERIODS, (
            "eleven seeded periods plus the one this sweep sampled")
        assert body["coverage_ratio_bp"] == 10_000
        assert 0 < body["trend_confidence_bp"] <= MAX_TREND_CONFIDENCE_BP
        assert body["series"]["subject_node_id"] == "node_acct_wire"

        # THE WRITE-AMPLIFICATION PROOF. `expertise_packages` reached 181 MB over 345 rows and put
        # this database into read-only, and the shape that did it was a writer that appended a row
        # every time it ran. A trend is recomputed on EVERY drain, so this is the same shape
        # unless the version-keyed upsert holds. A second sweep in the same period must not add a
        # single row.
        with pg_store.engine.connect() as conn:
            before = conn.execute(text(
                "select count(*) from graph_facts where org_id=:o and field like :p"),
                {"o": org, "p": f"{TREND_FACT_PREFIX}%"}).scalar()
        process_pending(org_id=org, store=pg_store, llm=None,
                        crypto_key=get_settings().crypto_key, eval_time=at)
        with pg_store.engine.connect() as conn:
            after = conn.execute(text(
                "select count(*) from graph_facts where org_id=:o and field like :p"),
                {"o": org, "p": f"{TREND_FACT_PREFIX}%"}).scalar()
        assert after == before > 0, "two sweeps in one period must not grow graph_facts"
    finally:
        _drop_org(pg_store, org)


@pytest.mark.pg
def test_deleting_an_org_erases_its_trend_facts(pg_store) -> None:
    """U3 adds NO TABLE — the trend is a `graph_facts` row, and `graph_facts` is already on the
    org-scoped erasure list. Proven rather than asserted from the list: the loop in
    `api/account_routes` runs with no try/except, so an omission there is silent, and a derived
    trend left behind is a deleted customer's engagement history in the one shape a card reads.
    """
    from genios_engine.api.account_routes import _ORG_SCOPED_TABLES

    assert "graph_facts" in _ORG_SCOPED_TABLES

    org = "org_trend_erasure"
    at = datetime(2026, 3, 1, 9, 0, tzinfo=timezone.utc)
    _seed_org_with_a_deal(pg_store, org, at)
    _seed_declining_history(pg_store, org, at)
    try:
        assert refresh_trend_facts(pg_store, org, eval_time=at) > 0
        with pg_store.engine.connect() as conn:
            assert conn.execute(text(
                "select count(*) from graph_facts where org_id=:o and field like :p"),
                {"o": org, "p": f"{TREND_FACT_PREFIX}%"}).scalar() > 0

        with pg_store.engine.begin() as conn:
            for table in _ORG_SCOPED_TABLES:
                conn.execute(text(f"delete from {table} where org_id=:o"), {"o": org})

        with pg_store.engine.connect() as conn:
            assert conn.execute(text(
                "select count(*) from graph_facts where org_id=:o"), {"o": org}).scalar() == 0
            assert conn.execute(text(
                "select count(*) from metric_history where org_id=:o"), {"o": org}).scalar() == 0
    finally:
        _drop_org(pg_store, org)


@pytest.mark.pg
def test_the_refresh_reads_point_in_time(pg_store) -> None:
    """Replayability is the whole reason the history store exists.

    The same org, refreshed at an `eval_time` BEFORE the series was sampled, must see none of it.
    A refresh that reached for `now()` inside the read would compute a past instant's trend from
    today's readings and the stored fact would be undated evidence for a claim about March.
    """
    org = "org_trend_asat"
    at = datetime(2026, 3, 1, 9, 0, tzinfo=timezone.utc)
    _seed_org_with_a_deal(pg_store, org, at)
    _seed_declining_history(pg_store, org, at)
    try:
        assert refresh_trend_facts(pg_store, org, eval_time=at) > 0
        with pg_store.engine.begin() as conn:
            conn.execute(text("delete from graph_facts where org_id=:o and field like :p"),
                         {"o": org, "p": f"{TREND_FACT_PREFIX}%"})

        # Every point above was SAMPLED at `at`; an as-at read a year earlier sees nothing, so
        # there is a (node, metric) pair with a series and no readable points in the window.
        written = refresh_trend_facts(pg_store, org, eval_time=at - timedelta(days=365))
        with pg_store.engine.connect() as conn:
            rows = conn.execute(text(
                "select value from graph_facts where org_id=:o and field like :p"),
                {"o": org, "p": f"{TREND_FACT_PREFIX}%"}).all()
        assert written == len(rows) > 0
        assert all(row.value["direction"] == "insufficient_history" for row in rows), (
            "a read as-at a past instant must not see readings sampled later")
    finally:
        _drop_org(pg_store, org)


def test_the_per_sweep_read_is_capped() -> None:
    """The bound on the READ, which is the one U3's version-keyed write does not cover. An org
    with fifty thousand nodes must not turn one drain into fifty thousand dense series reads."""
    assert MAX_TREND_FACTS_PER_SWEEP == 2_000
    assert TREND_WINDOW_PERIODS == 12


# =================================================================================================
# FIXTURES — the smallest world in which a sweep has a trend to compute
# =================================================================================================

def _seed_org_with_a_deal(store, org: str, at: datetime) -> None:
    """One org, one company node, one stage fact aged 21 days, one observation to make it active.

    The same world `test_metric_sampler` seeds, restated here rather than imported: the sampler's
    fixture is about what makes a metric SAMPLEABLE, and importing it would couple this gate to a
    file that is free to change its mind about that.
    """
    with store.engine.begin() as conn:
        conn.execute(text("insert into orgs (id, name) values (:o, 'Trend Wiring') "
                          "on conflict (id) do nothing"), {"o": org})
        conn.execute(text(
            "insert into graph_nodes (node_id, version, org_id, node_type, display_name) "
            "values ('node_acct_wire', 1, :o, 'company', 'Northwind') "
            "on conflict do nothing"), {"o": org})
        conn.execute(text(
            "insert into graph_facts (fact_version_id, fact_id, org_id, subject_node_id, field, "
            "  value, value_type, status, occurred_at, valid_from) "
            "values ('fv_trendwire_stage', 'f_trendwire_stage', :o, 'node_acct_wire', "
            "  'deal.stage', cast('\"proposing\"' as jsonb), 'string', 'active', :at, :at) "
            "on conflict (fact_version_id) do nothing"),
            {"o": org, "at": at - timedelta(days=21)})
        conn.execute(text(
            "insert into graph_observations (observation_id, org_id, subject_node_id, kind, "
            "  occurred_at, status) "
            "values ('obs_trendwire_1', :o, 'node_acct_wire', 'meeting_request', :at, 'active') "
            "on conflict (observation_id) do nothing"),
            {"o": org, "at": at - timedelta(days=3)})


def _seed_declining_history(store, org: str, at: datetime) -> None:
    """Eleven prior monthly readings of `deal.stage_age_days`, falling — the twelve-period window
    minus the period this sweep will sample for itself.

    Written through the REAL store rather than by raw insert: `to_row` refuses an unregistered
    metric and a value that will not fit the column, so a fixture that went round it could seed a
    series the sampler itself could never have produced.
    """
    history = PostgresMetricHistory(store.engine, sampler_registry())
    metric = TrendedMetric.DEAL_STAGE_AGE_DAYS.value
    this_month = period_start(at, MetricGrain.MONTH)
    points = []
    for back in range(11, 0, -1):
        year, remainder = divmod(this_month.year * 12 + (this_month.month - 1) - back, 12)
        points.append(MetricPoint(
            subject_node_id="node_acct_wire", metric=metric, value_bp=30 + back * 10,
            unit=MetricUnit.DAYS, observed_at=this_month.replace(year=year, month=remainder + 1),
            known=True))
    # `sampled_at` is 45 days back, not `at`. The sampler's cadence test reads `sampled_at` —
    # "has this cadence come round since we last LOOKED" — so a fixture that stamped the seeded
    # history with the sweep's own instant would tell the sampler it had just run, and the sweep
    # would take no reading for the current period. The fixture must describe a series that was
    # last sampled a month and a half ago, which is what a real org's history looks like.
    history.put(org, points, reason=SampleReason.BACKFILL, sampled_at=at - timedelta(days=45))


def _drop_org(store, org: str) -> None:
    with store.engine.begin() as conn:
        for table in ("metric_history", "graph_observations", "graph_facts", "graph_nodes"):
            conn.execute(text(f"delete from {table} where org_id=:o"), {"o": org})
        conn.execute(text("delete from orgs where id=:o"), {"o": org})
