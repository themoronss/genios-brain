"""H3 · L2.4.5 — THE POPULATION COMPARATOR (BLG-10). The gate for `context/analytic/comparator.py`.

Doc 09 invokes gate H3 as:

    pytest tests/context/analytic/test_comparator.py -q

Organised the way doc 04's acceptance list is written: the refusals first, because a refusal is
the answer this component exists to give correctly; then the arithmetic at every band boundary;
then the lookalike's traits-by-name; then the wiring.

**WHY THE WIRING TEST IS THE ONE THAT MATTERS.** Layer 1 shipped six units that were green and
called by nothing on a real request path. Every test above `THE WIRING` here builds its own
population and proves the UNIT. `test_the_sweep_writes_the_position_fact` drives
`context/runner.process_pending` — the sweep every sync route and the upload route call — against
a real Postgres and asserts a `derived.cohort_position.*` row exists afterwards. Delete the two
lines in `runner.py` and that test fails and nothing else in this file does.

**THE MUTATION NOTE — which test fails if the percentile is computed off by one.**
`percentile_bp` is `rank = count(v <= value); rank * 10000 // n`. Change the comparison to
`v < value` (the classic off-by-one, and the one that produces the "everybody is above average"
card), or subtract one from `rank`:

  * `test_the_lowest_value_in_a_cohort_of_ten_is_the_first_decile` fails FIRST and most loudly:
    the lowest of ten is 1000 bp under the stated rule and 0 bp under `v < value`, which moves it
    from D2 to D1 — the label changes, not just the number.
  * `test_the_highest_value_is_always_the_top_of_the_scale` fails next: the maximum is 10000 bp
    exactly, and under `v < value` it becomes 9000, which is a different decile.
  * `test_ties_get_the_same_percentile` fails if the fix for either of those is to special-case
    ties, because two members on the same value must land on the identical basis point.
  * `test_every_decile_boundary_exactly` is the table that pins all ten labels at once, so an
    off-by-one anywhere in the band lookup shows up there rather than in one lucky case.

A single test would not distinguish "off by one rank" from "off by one band"; these four together
do, which is why the boundary table and the two extremes are separate rows.
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from sqlalchemy import text

from genios_engine.context.analytic.cohort import (COHORT_MEMBERSHIP_TABLE, SYSTEM_AUTHOR,
                                                   CohortRefusal, CohortRefusalReason,
                                                   default_fact_registry, define_cohort,
                                                   percentile_bp, save_definitions)
from genios_engine.context.analytic.comparator import (LOOKALIKE_FACT_PREFIX, MIN_LOOKALIKE_TRAITS,
                                                       NON_TRAIT_FACTS, POSITION_FACT_PREFIX,
                                                       ComparisonSweep, Lookalike,
                                                       LookalikeRefusal, LookalikeRefusalReason,
                                                       PositionedReading, ReferenceProfile,
                                                       cohort_readings, compare_in_cohort,
                                                       compare_reading, describe_position,
                                                       lookalike, lookalike_fact_field,
                                                       lookalike_fact_value, most_specific,
                                                       ordinal, position_fact_field,
                                                       position_fact_value,
                                                       publishable_distribution, reference_cohorts,
                                                       reference_profile, refresh_comparison_facts,
                                                       metric_grain,
                                                       staleness_horizon, STALE_AFTER_PERIODS,
                                                       VERSION_PREFIX)
from genios_engine.context.analytic.history import (MetricGrain, PostgresMetricHistory,
                                                    SampleReason, months_before, period_start)
from genios_engine.context.analytic.peer_baseline import (BASELINE_SMOOTHING_WINDOW,
                                                          MIN_BASELINE_POPULATION, smoothed_rung)
from genios_engine.context.analytic.peer_baseline import (
    STALE_AFTER_PERIODS as BASELINE_STALE_AFTER_PERIODS)
from genios_engine.context.analytic.peer_baseline import metric_grain as baseline_metric_grain
from genios_engine.context.analytic.peer_baseline import staleness_floor
from genios_engine.context.analytic.publish import derived_fact_version_id
from genios_engine.context.analytic.sampler import (TrendedMetric,
                                                    sampler_definitions,
                                                    sampler_registry)
from genios_engine.contracts.analytic import (MIN_COHORT_POPULATION, CohortBand, CohortPosition,
                                              MetricPoint, MetricUnit, expressible_divisions)

pytestmark = pytest.mark.unit

_ENGINE = Path(__file__).resolve().parents[3] / "genios_engine"

#: One fixed instant. The comparator takes no clock, so a test that reached for one would be
#: asserting on a different population every day it ran.
AT = datetime(2026, 3, 2, 9, 0, tzinfo=timezone.utc)
COHORT = "coh_growth_accounts"
METRIC = "engagement.touch_count"


def _population(values: list[int]) -> dict[str, int]:
    """`{node_00: v0, node_01: v1, ...}` — ids that sort in insertion order, so a test that cares
    about the tie-break rule can say which node it means."""
    return {f"node_{index:02d}": value for index, value in enumerate(values)}


# =================================================================================================
# THE FLOOR — a population below it is NOT a weak comparison, it is no comparison
# =================================================================================================

def test_a_population_of_exactly_the_floor_is_compared() -> None:
    """Five is the floor and the floor is INCLUSIVE. The boundary is asserted from both sides in
    this test and the next, because "at least five" and "more than five" are one character apart
    in the source and produce the same green suite if only one side is checked."""
    values = _population([10, 20, 30, 40, 50])
    assert len(values) == MIN_COHORT_POPULATION
    outcome = compare_reading(metric=METRIC, cohort_id=COHORT, values=values,
                              subject_node_id="node_02", eval_time=AT)
    assert isinstance(outcome, PositionedReading)
    assert outcome.population_size == MIN_COHORT_POPULATION
    assert outcome.percentile_bp == 6_000                 # rank 3 of 5


def test_a_population_one_below_the_floor_refuses() -> None:
    """Four members. Every percentile such a population can produce is 2500, 5000, 7500 or 10000 —
    the phrase on the card would be describing the arithmetic, not the business."""
    outcome = compare_reading(metric=METRIC, cohort_id=COHORT,
                              values=_population([10, 20, 30, 40]),
                              subject_node_id="node_01", eval_time=AT)
    assert isinstance(outcome, CohortRefusal)
    assert outcome.reason is CohortRefusalReason.INSUFFICIENT_POPULATION
    assert outcome.population_size == 4, "the refusal carries how close it was"
    assert outcome.cohort_id == COHORT and outcome.metric == METRIC


def test_the_refusal_is_a_return_value_not_an_exception() -> None:
    """A card can render "we cannot say"; it cannot render a traceback."""
    outcome = compare_reading(metric=METRIC, cohort_id=COHORT, values=_population([1, 2]),
                              subject_node_id="node_00", eval_time=AT)
    assert outcome.is_position is False
    assert "5" in outcome.detail, "the refusal says what the floor is"


def test_half_a_cohort_with_no_reading_refuses_for_coverage() -> None:
    """Population and COVERAGE are different refusals: "too few peers" and "too little known
    about the peers we have" are opposite fixes, and one enum member for both would hide that."""
    outcome = compare_reading(metric=METRIC, cohort_id=COHORT,
                              values=_population([10, 20, 30, 40, 50, 60]),
                              subject_node_id="node_00", eval_time=AT, unknown=6)
    assert isinstance(outcome, CohortRefusal)
    assert outcome.reason is CohortRefusalReason.INSUFFICIENT_COVERAGE


def test_a_subject_with_no_reading_refuses_rather_than_scoring_zero() -> None:
    """The fabricated zero would put the node in the bottom decile of a metric nobody measured."""
    outcome = compare_reading(metric=METRIC, cohort_id=COHORT,
                              values=_population([10, 20, 30, 40, 50]),
                              subject_node_id="node_stranger", eval_time=AT)
    assert isinstance(outcome, CohortRefusal)
    assert outcome.reason is CohortRefusalReason.SUBJECT_VALUE_UNKNOWN


# =================================================================================================
# THE ARITHMETIC — integer basis points, every boundary, and the tie rule
# =================================================================================================

def test_the_lowest_value_in_a_cohort_of_ten_is_the_first_tenth_of_the_scale() -> None:
    """Doc 04's own acceptance number: *the lowest value in a cohort of 10 -> percentile_bp near
    1000*. Under `rank = count(v <= value)` the lowest counts ITSELF, so it is exactly 1000 and
    not 0 — see the mutation note at the top of this file.

    CHANGED, AND WHY. This row used to end `assert outcome.band is CohortBand.D2`, which pinned
    the D8 defect rather than the rank: a cohort of ten cannot produce ANY percentile below 1000,
    so `D1` was an empty band and every decile label the sweep published on a cohort of ten or
    fewer overstated the resolution of its own arithmetic. `expressible_divisions` now narrows the
    scheme at construction, so ten members are labelled in QUARTILES. The number — the thing this
    test is named for and the thing an off-by-one in the rank moves — is asserted unchanged.
    """
    values = _population([5, 15, 25, 35, 45, 55, 65, 75, 85, 95])
    outcome = compare_reading(metric=METRIC, cohort_id=COHORT, values=values,
                              subject_node_id="node_00", eval_time=AT)
    assert isinstance(outcome, PositionedReading)
    assert outcome.percentile_bp == 1_000
    assert outcome.band is CohortBand.Q1, "ten members cannot say 'decile'; 1000 bp is in Q1"


def test_the_highest_value_is_always_the_top_of_the_scale() -> None:
    """The maximum counts every member including itself: `10 * 10000 // 10`."""
    values = _population([5, 15, 25, 35, 45, 55, 65, 75, 85, 95])
    outcome = compare_reading(metric=METRIC, cohort_id=COHORT, values=values,
                              subject_node_id="node_09", eval_time=AT)
    assert isinstance(outcome, PositionedReading)
    assert outcome.percentile_bp == 10_000
    assert outcome.band is CohortBand.Q4, "10000 is inclusive in the TOP band only"
    eleven = _population([5, 15, 25, 35, 45, 55, 65, 75, 85, 95, 105])
    top = compare_reading(metric=METRIC, cohort_id=COHORT, values=eleven,
                          subject_node_id="node_10", eval_time=AT)
    assert top.percentile_bp == 10_000 and top.band is CohortBand.D10, (
        "eleven members CAN say decile, and the top of the scale is still the top band")


@pytest.mark.parametrize("index, expected_bp, expected_band", [
    (0, 909, CohortBand.D1),
    (1, 1_818, CohortBand.D2),
    (2, 2_727, CohortBand.D3),
    (3, 3_636, CohortBand.D4),
    (4, 4_545, CohortBand.D5),
    (5, 5_454, CohortBand.D6),
    (6, 6_363, CohortBand.D7),
    (7, 7_272, CohortBand.D8),
    (8, 8_181, CohortBand.D9),
    (9, 9_090, CohortBand.D10),
    (10, 10_000, CohortBand.D10),
])
def test_every_decile_boundary_exactly(index: int, expected_bp: int,
                                       expected_band: CohortBand) -> None:
    """ELEVEN distinct values, so every one of the ten deciles is occupied — the table that an
    off-by-one anywhere in the rank or the band lookup moves into a different label.

    CHANGED FROM TEN, AND WHY. At ten members the smallest percentile the arithmetic can produce
    is `10 * 10000 // 10 // 10`... i.e. exactly 1000, the first basis point of D2, so D1 was empty
    and this table was really nine bands plus a lie about the tenth. Eleven is the SMALLEST
    population that can express a decile scheme at all (`expressible_divisions`: every band of a
    d-scheme is reachable iff `population_size > d`), which is why it is the population this table
    is cut on now. The quartile counterpart at ten members is the row below.

    `bounds_bp` is `[low, high)`, so 909 bp is inside D1 and 1000 would be the first basis point
    of D2. Pinning that here is what stops a later "clearly the 1000th is the top decile" from
    silently relabelling ten percent of every cohort.
    """
    values = _population([5, 15, 25, 35, 45, 55, 65, 75, 85, 95, 105])
    outcome = compare_reading(metric=METRIC, cohort_id=COHORT, values=values,
                              subject_node_id=f"node_{index:02d}", eval_time=AT)
    assert isinstance(outcome, PositionedReading)
    assert outcome.percentile_bp == expected_bp
    assert outcome.band is expected_band
    assert outcome.band.contains(outcome.percentile_bp), "the contract's own coherence"


@pytest.mark.parametrize("index, expected_bp, expected_band", [
    (0, 1_000, CohortBand.Q1),
    (1, 2_000, CohortBand.Q1),
    (2, 3_000, CohortBand.Q2),
    (3, 4_000, CohortBand.Q2),
    (4, 5_000, CohortBand.Q3),
    (5, 6_000, CohortBand.Q3),
    (6, 7_000, CohortBand.Q3),
    (7, 8_000, CohortBand.Q4),
    (8, 9_000, CohortBand.Q4),
    (9, 10_000, CohortBand.Q4),
])
def test_ten_members_are_labelled_in_quartiles_because_a_decile_is_unreachable(
        index: int, expected_bp: int, expected_band: CohortBand) -> None:
    """The other half of the D8 table: the SAME ten readings that used to be published as D2..D10
    with an empty D1, now published in the finest scheme ten members can actually produce.

    Deciles are still what the caller ASKS for (`DEFAULT_DIVISIONS`); the population decides what
    it gets. This is the row that fails if the narrowing is ever removed or moved to a threshold
    of `population_size >= divisions`, which is off by one — at ten the smallest reachable
    percentile is exactly 1000, the first basis point of D2, so D1 would still be empty.
    """
    values = _population([5, 15, 25, 35, 45, 55, 65, 75, 85, 95])
    outcome = compare_reading(metric=METRIC, cohort_id=COHORT, values=values,
                              subject_node_id=f"node_{index:02d}", eval_time=AT)
    assert outcome.percentile_bp == expected_bp
    assert outcome.band is expected_band
    assert outcome.band.divisions == 4


@pytest.mark.parametrize("index, expected_bp, expected_band", [
    (0, 2_000, CohortBand.Q1),
    (1, 4_000, CohortBand.Q2),
    (2, 6_000, CohortBand.Q3),
    (3, 8_000, CohortBand.Q4),
    (4, 10_000, CohortBand.Q4),
])
def test_every_quartile_boundary_exactly(index: int, expected_bp: int,
                                         expected_band: CohortBand) -> None:
    """The same table in the FOUR-division scheme. Both schemes, because `divisions` is a
    parameter and a band lookup that is right for ten can still be wrong for four — 2500 is the
    first basis point of Q2 and the last of Q1 differ by one, and this row is what pins which.

    Five distinct values, so the percentiles are fifths (2000, 4000, ...) while the BANDS are
    quarters — the case where the rank and the label are cut on different denominators, which is
    exactly where an off-by-one in the band lookup hides.
    """
    values = _population([10, 20, 30, 40, 41])
    outcome = compare_reading(metric=METRIC, cohort_id=COHORT, values=values,
                              subject_node_id=f"node_{index:02d}", eval_time=AT, divisions=4)
    assert isinstance(outcome, PositionedReading)
    assert outcome.percentile_bp == expected_bp
    assert outcome.band is expected_band
    assert outcome.band.divisions == 4
    assert outcome.band.contains(outcome.percentile_bp)


# =================================================================================================
# D8 · THE BAND MUST BE ONE THE POPULATION CAN REACH — asserted through the PRODUCER
# =================================================================================================

@pytest.mark.parametrize("size", list(range(MIN_COHORT_POPULATION, 16)))
def test_the_published_band_table_has_no_empty_band_at_any_population(size: int) -> None:
    """EVERY band the scheme offers is occupied by some member — computed from `compare_reading`
    over a real population, which is the absence that let the defect ship.

    The old suite pinned bands through `CohortBand.for_percentile(0)` and hand-built
    `CohortPosition` objects, so no test could see what the PRODUCER can actually emit. Nearest
    rank counts the subject, so the smallest percentile a cohort of n can produce is `10000 // n`
    and never 0: with deciles, D1 was empty at every population up to ten and the worst account in
    a five-member cohort was published as `D3` — "below average, not alarming" — while
    `most_specific` deliberately publishes the SMALLEST population.

    The table below is therefore built the only way that could have caught it: ask the producer
    for every member's band and compare the set with the whole scheme. It fails if the narrowing
    is removed, and it fails if the narrowing threshold is loosened to `population_size >=
    divisions`, which is off by one at exactly ten.
    """
    values = _population([index * 10 for index in range(size)])
    bands = {compare_reading(metric=METRIC, cohort_id=COHORT, values=values,
                             subject_node_id=node, eval_time=AT).band for node in values}
    divisions = expressible_divisions(size, requested=10)
    letter = "Q" if divisions == 4 else "D"
    assert bands == {CohortBand(f"{letter}{index}") for index in range(1, divisions + 1)}, bands
    assert (10 in {band.divisions for band in bands}) is (size > 10), (
        "a decile label appears exactly when the population can produce every decile")


def test_the_worst_account_in_a_five_member_cohort_is_in_the_bottom_band() -> None:
    """The measured symptom, pinned. `2000` bp is the smallest percentile five members can
    produce, and under deciles that landed in D3, which a card renders as "below average". In the
    scheme five members CAN express it is the bottom band, which is what the reader needs to
    know."""
    values = _population([12, 34, 51, 78, 99])
    worst = compare_reading(metric=METRIC, cohort_id=COHORT, values=values,
                            subject_node_id="node_00", eval_time=AT)
    assert worst.percentile_bp == 2_000
    assert worst.band is CohortBand.Q1 and worst.band.index == 1
    assert "Q1" in worst.phrase, "and the sentence says the label the arithmetic can support"


def test_most_specific_prefers_the_smallest_cohort_and_still_cannot_pick_an_unreachable_band(
) -> None:
    """`most_specific` publishes the SMALLEST population on purpose, which is precisely where the
    unreachable decile did the most damage. Both candidates go through the producer, so the one it
    picks carries a band its own population can reach."""
    small = compare_reading(metric=METRIC, cohort_id="coh_small", eval_time=AT,
                            values=_population([1, 2, 3, 4, 5]), subject_node_id="node_00")
    large = compare_reading(metric=METRIC, cohort_id="coh_large", eval_time=AT,
                            values=_population(list(range(1, 41))), subject_node_id="node_00")
    chosen = most_specific([large, small])
    assert chosen is small and chosen.population_size == MIN_COHORT_POPULATION
    assert chosen.band.divisions == expressible_divisions(chosen.population_size, requested=10)
    assert chosen.band.contains(chosen.percentile_bp)


# =================================================================================================
# D1 · WHAT A COMPARISON CARD MAY CARRY — the ladder is the baseline's, and so are its terms
# =================================================================================================

def test_a_five_member_cards_body_does_not_carry_three_other_members_readings() -> None:
    """The demonstrated disclosure, refused at the seam that publishes.

    For the cohort `{1200, 3450, 5100, 7800, 9900}` the top member's card carried p25=3450,
    p50=5100, p75=7800 — three of the other four members' EXACT readings — beside an exact rank,
    which bounds the fourth. `peer_baseline` refuses to publish a ladder over the same population
    (`MIN_BASELINE_POPULATION = 10`, `BASELINE_SMOOTHING_WINDOW = 3`, and
    `require_publishable_window` makes narrowing it impossible) for exactly that reason. Two
    components of one wave cannot both be the rule; the published body now follows the baseline's.
    """
    values = {"node_a": 1_200, "node_b": 3_450, "node_c": 5_100, "node_d": 7_800,
              "node_e": 9_900}
    outcome = compare_reading(metric=METRIC, cohort_id=COHORT, values=values,
                              subject_node_id="node_e", eval_time=AT)
    body = position_fact_value(outcome)
    assert outcome.distribution is None
    assert body["p25_bp"] is None and body["p50_bp"] is None and body["p75_bp"] is None
    assert str(MIN_BASELINE_POPULATION) in body["distribution_withheld"]
    rendered = repr(body)
    for peer, reading in values.items():
        if peer != "node_e":
            assert str(reading) not in rendered, f"{peer}'s exact reading is on another's card"
    assert body["value_bp"] == 9_900, "the SUBJECT's own reading is not a disclosure"
    assert body["percentile_bp"] == 10_000 and body["population_size"] == 5


def test_a_cohort_of_ten_publishes_a_smoothed_ladder_not_its_members_readings() -> None:
    """At the baseline's floor the distribution IS publishable, and every rung is the mean of
    three adjacent readings rather than the reading of the member standing at that rank.

    `70` is the visible proof: it is p25 of this population under the smoothing window and it is
    nobody's number, where the raw quantile would have published `90`, which is one named
    account's exact reading.
    """
    readings = [10, 20, 90, 100, 110, 120, 130, 140, 150, 160]
    values = _population(readings)
    outcome = compare_reading(metric=METRIC, cohort_id=COHORT, values=values,
                              subject_node_id="node_09", eval_time=AT)
    body = position_fact_value(outcome)
    assert outcome.distribution == (70, 110, 130)
    assert (body["p25_bp"], body["p50_bp"], body["p75_bp"]) == (70, 110, 130)
    assert body["distribution_window"] == BASELINE_SMOOTHING_WINDOW
    assert body["distribution_withheld"] is None
    assert body["p25_bp"] not in readings, "a rung that is a member's reading is the disclosure"
    assert outcome.position.p25_bp == 90, (
        "the RAW quantile is still computed — it is simply not what gets published")
    assert str(outcome.position.p25_bp) not in repr(body)
    assert publishable_distribution(dict(list(values.items())[:9])) is None, (
        "one member below the floor and the ladder is withheld entirely, not narrowed")


def test_the_ladder_is_ordered_and_integral() -> None:
    """A distribution whose p25 exceeds its p50 is not a distribution, and a rung decided by a
    binary expansion is a boundary that moves between machines."""
    ladder = publishable_distribution(_population([3, 9, 9, 14, 20, 27, 31, 44, 51, 88, 91]))
    assert ladder is not None and ladder[0] <= ladder[1] <= ladder[2]
    for rung in ladder:
        assert isinstance(rung, int) and not isinstance(rung, bool)


# =================================================================================================
# D6 · THE STALENESS HORIZON — the arithmetic of it (the plumbing proof is in the pg section)
# =================================================================================================

def test_the_horizon_is_counted_in_the_metrics_own_periods() -> None:
    """Periods, not days, and floored by the SAME boundary functions the sampler floors
    `observed_at` with — a horizon in days lands mid-period and moves with the length of a
    calendar month, so a February reading would be dark and a July one alive at the same age."""
    assert STALE_AFTER_PERIODS == 3
    assert staleness_horizon(AT, MetricGrain.MONTH) == datetime(2026, 1, 1, tzinfo=timezone.utc)
    assert staleness_horizon(AT, MetricGrain.WEEK) == datetime(2026, 2, 16, tzinfo=timezone.utc)
    assert staleness_horizon(AT, MetricGrain.MONTH) == months_before(AT, STALE_AFTER_PERIODS - 1)
    assert staleness_horizon(AT, MetricGrain.MONTH, periods=1) == period_start(
        AT, MetricGrain.MONTH), "one period is the current period alone"
    with pytest.raises(ValueError):
        staleness_horizon(AT, MetricGrain.MONTH, periods=0)


def test_the_two_modules_agree_on_which_members_are_dark() -> None:
    """THE COLLISION TEST. One staleness policy, one constant, one place — asserted, not asserted
    about.

    This module and `peer_baseline` read the SAME `metric_history` rows for the SAME cohort in the
    SAME drain, and both have to decide which members are dark. They used to decide it with two
    copies of the same idea that were not the same rule: this module resolved the grain against
    `history.default_registry()`, which holds the core metrics only, so all twelve names the
    sampler actually writes fell through to a MONTH default and got a three-MONTH horizon where
    the ladder gave the same metric three WEEKS. Measured at `AT`, that was 2026-01-01 here and
    2026-02-09 there — a member last read in mid-January was known to the cohort position and dark
    to the ladder, off one set of rows.

    Pinned per metric rather than "the constants are equal", because the constant was never the
    part that diverged: both said 3. The divergence was in which registry answered the grain, and
    only a per-metric comparison can see that.
    """
    for definition in sampler_definitions():
        metric = definition.metric
        assert metric_grain(metric) is baseline_metric_grain(metric), metric
        assert staleness_horizon(AT, metric_grain(metric)) == staleness_floor(
            AT, baseline_metric_grain(metric)), metric
        # and the answer is the metric's REAL grain, not either module's fallback
        assert metric_grain(metric) is definition.grain, metric
    # and there is only one constant, not two that happen to be equal today
    assert STALE_AFTER_PERIODS is BASELINE_STALE_AFTER_PERIODS


def test_the_horizon_is_a_parameter_of_eval_time_and_not_of_a_clock() -> None:
    """March's question asked in September gets March's horizon, so it gets March's answer about
    who was dark. A `datetime.now()` anywhere on this path would make an as-of read of last spring
    return today's coverage."""
    september = AT + timedelta(days=180)
    assert staleness_horizon(september, MetricGrain.MONTH) > staleness_horizon(
        AT, MetricGrain.MONTH)
    assert staleness_horizon(AT, MetricGrain.MONTH) == staleness_horizon(
        AT, MetricGrain.MONTH), "and it is a pure function of its arguments"


def test_ties_get_the_same_percentile() -> None:
    """THE TIE RULE, ASSERTED: `rank` counts `v <= value`, so equal members count each other and
    land on the identical basis point.

    This is the rule the product needs. A percentile is a statement about a VALUE, so two accounts
    both sitting at 22% cannot be told "31st" and "38th" — one of them would act on a difference
    that does not exist. The visible consequence is that a tied group takes the percentile of the
    TOP of its run, which is why the assertion below is 8000 and not 6000.
    """
    values = _population([10, 22, 22, 22, 50])
    positions = {node: compare_reading(metric=METRIC, cohort_id=COHORT, values=values,
                                       subject_node_id=node, eval_time=AT).percentile_bp
                 for node in ("node_01", "node_02", "node_03")}
    assert set(positions.values()) == {8_000}, positions
    assert percentile_bp(sorted(values.values()), 22) == 8_000, "and the primitive agrees"


def test_a_population_of_identical_values_puts_everyone_at_the_top() -> None:
    """The honest consequence of the tie rule, stated rather than discovered: where nobody
    differs, nobody is behind. A card that wanted "everyone is average" would be inventing a
    spread the data does not have — the DISTRIBUTION carried alongside (p25 == p50 == p75) is
    what tells a reader the ranking is meaningless here."""
    values = _population([7, 7, 7, 7, 7, 7])
    outcome = compare_reading(metric=METRIC, cohort_id=COHORT, values=values,
                              subject_node_id="node_00", eval_time=AT)
    assert isinstance(outcome, PositionedReading)
    assert outcome.percentile_bp == 10_000
    assert (outcome.position.p25_bp, outcome.position.p50_bp,
            outcome.position.p75_bp) == (7, 7, 7)


def test_no_float_reaches_any_measure() -> None:
    """Integer basis points, everywhere, and asserted by TYPE rather than by value: a percentile
    computed as `rank / n` and cast back is right in almost every case and wrong at exactly the
    boundary that decides a band."""
    outcome = compare_reading(metric=METRIC, cohort_id=COHORT,
                              values=_population([1, 3, 3, 7, 11, 13, 17]),
                              subject_node_id="node_03", eval_time=AT)
    assert isinstance(outcome, PositionedReading)
    for measure in (outcome.percentile_bp, outcome.value_bp, outcome.position.p25_bp,
                    outcome.position.p50_bp, outcome.position.p75_bp,
                    outcome.position.population_size):
        assert isinstance(measure, int) and not isinstance(measure, bool), measure


def test_the_source_contains_no_float_literal_and_no_true_division() -> None:
    """The rule enforced against the FILE, not only against one path through it. `/` on two
    integers produces a float in Python 3 and nothing downstream would notice until a band
    flipped."""
    source = (_ENGINE / "context" / "analytic" / "comparator.py").read_text()
    code = "\n".join(line.split("#")[0] for line in source.splitlines())
    body = code.split('"""', 2)[-1] if code.count('"""') >= 2 else code
    assert "float(" not in body
    for line in body.splitlines():
        stripped = line.strip()
        if stripped.startswith(("#", '"', "'")):
            continue
        assert "/ " not in stripped.replace("// ", ""), stripped


# =================================================================================================
# THE SENTENCE — a positioned reading, not a bare number
# =================================================================================================

def test_the_reading_becomes_a_positioned_reading() -> None:
    """The whole point of BLG-10: "22%" becomes "22%, the 31st percentile of ...". The VALUE
    travels with the position, because a percentile with no number beside it is unfalsifiable."""
    values = {f"node_{i:02d}": (i + 1) * 100 for i in range(10)}
    values["node_subject"] = 2_200
    outcome = compare_reading(metric="deal.close_rate", cohort_id=COHORT, values=values,
                              subject_node_id="node_subject", eval_time=AT, unit=MetricUnit.BP,
                              cohort_name="your Growth plan")
    assert isinstance(outcome, PositionedReading)
    assert outcome.value_bp == 2_200
    assert outcome.phrase.startswith("22%, the ")
    assert "percentile of 11 in your Growth plan" in outcome.phrase
    assert outcome.band.value in outcome.phrase


@pytest.mark.parametrize("number, word", [(0, "0th"), (1, "1st"), (2, "2nd"), (3, "3rd"),
                                          (4, "4th"), (11, "11th"), (12, "12th"), (13, "13th"),
                                          (21, "21st"), (31, "31st"), (42, "42nd"),
                                          (53, "53rd"), (100, "100th"), (111, "111th")])
def test_the_ordinal_table(number: int, word: str) -> None:
    """11th/12th/13th are the rows a suffix chain gets wrong, and 111th is the row a `% 10` fix
    for those gets wrong in turn."""
    assert ordinal(number) == word


def test_the_phrase_is_built_from_the_numbers_beside_it() -> None:
    """No model, no template a model filled in: `describe_position` is a pure function of the
    position, so the words on the card cannot drift from the numbers under it."""
    position = CohortPosition(metric=METRIC, cohort_id=COHORT, population_size=47,
                              percentile_bp=3_100, band=CohortBand.D4, p25_bp=10, p50_bp=20,
                              p75_bp=30, computed_at=AT)
    assert describe_position(position, 2_200, unit=MetricUnit.BP, cohort_name="your peers") == (
        "22%, the 31st percentile of 47 in your peers (D4)")
    assert describe_position(position, 5, unit=MetricUnit.DAYS).endswith(
        f"5 days, the 31st percentile of 47 in {COHORT} (D4)")


# =================================================================================================
# DETERMINISM — the same input, replayed, byte for byte
# =================================================================================================

def test_the_same_input_replays_byte_identical() -> None:
    """The published FACT BODY is compared, not just the object: it is what reaches `graph_facts`,
    and a dict that serialises differently on a second run is a row rewritten on every sweep."""
    values = _population([3, 9, 9, 14, 20, 27, 31])
    first = compare_reading(metric=METRIC, cohort_id=COHORT, values=values,
                            subject_node_id="node_04", eval_time=AT, unit=MetricUnit.COUNT)
    second = compare_reading(metric=METRIC, cohort_id=COHORT, values=dict(reversed(list(
        values.items()))), subject_node_id="node_04", eval_time=AT, unit=MetricUnit.COUNT)
    assert position_fact_value(first) == position_fact_value(second)
    assert first.phrase == second.phrase
    assert first == second, "the whole object, not only the number"


def test_a_past_instant_gets_the_past_answer() -> None:
    """`eval_time` is a parameter with no default and no clock: the position is stamped with the
    instant it was asked about, so March's question re-asked in September is still March's."""
    values = _population([1, 2, 3, 4, 5])
    march = compare_reading(metric=METRIC, cohort_id=COHORT, values=values,
                            subject_node_id="node_02", eval_time=AT)
    september = compare_reading(metric=METRIC, cohort_id=COHORT, values=values,
                                subject_node_id="node_02", eval_time=AT + timedelta(days=180))
    assert march.position.computed_at == AT
    assert september.position.computed_at == AT + timedelta(days=180)
    assert march.percentile_bp == september.percentile_bp


# =================================================================================================
# WHICH COHORT — a node in five populations publishes ONE comparison
# =================================================================================================

def test_the_most_specific_cohort_wins() -> None:
    """The rule, stated in `most_specific` and pinned here: among positions the SMALLEST
    population wins, because "the 31st percentile of the 12 enterprise accounts" says more than
    "of all 4,000 nodes"."""
    wide = compare_reading(metric=METRIC, cohort_id="coh_all", eval_time=AT,
                           values=_population(list(range(1, 41))), subject_node_id="node_09")
    narrow = compare_reading(metric=METRIC, cohort_id="coh_enterprise", eval_time=AT,
                             values=_population([10, 20, 30, 40, 50, 60]),
                             subject_node_id="node_02")
    assert most_specific([wide, narrow]) is narrow
    assert most_specific([narrow, wide]) is narrow, "and not whichever came back first"


def test_a_position_beats_a_refusal_and_the_nearest_refusal_wins() -> None:
    """A refusal is published only when there is nothing to publish — and then the one that came
    CLOSEST, because "your enterprise cohort has 4 members" is the actionable version of "we
    cannot say"."""
    refusal_far = CohortRefusal(CohortRefusalReason.INSUFFICIENT_POPULATION, "coh_a", METRIC, 1,
                                AT)
    refusal_near = CohortRefusal(CohortRefusalReason.INSUFFICIENT_POPULATION, "coh_b", METRIC, 4,
                                 AT)
    position = compare_reading(metric=METRIC, cohort_id="coh_c", values=_population([1, 2, 3, 4, 5]),
                               subject_node_id="node_00", eval_time=AT)
    assert most_specific([refusal_far, refusal_near]) is refusal_near
    assert most_specific([refusal_near, position]) is position
    assert most_specific([]) is None


def test_the_tie_break_does_not_depend_on_input_order() -> None:
    """Two cohorts of the same size: the smallest `cohort_id` wins, in both orders."""
    values = _population([10, 20, 30, 40, 50])
    left = compare_reading(metric=METRIC, cohort_id="coh_aaa", values=values,
                           subject_node_id="node_00", eval_time=AT)
    right = compare_reading(metric=METRIC, cohort_id="coh_bbb", values=values,
                            subject_node_id="node_00", eval_time=AT)
    assert most_specific([left, right]).cohort_id == "coh_aaa"
    assert most_specific([right, left]).cohort_id == "coh_aaa"
    a = CohortRefusal(CohortRefusalReason.INSUFFICIENT_POPULATION, "coh_aaa", METRIC, 3, AT)
    b = CohortRefusal(CohortRefusalReason.INSUFFICIENT_POPULATION, "coh_bbb", METRIC, 3, AT)
    assert most_specific([a, b]).cohort_id == "coh_aaa"
    assert most_specific([b, a]).cohort_id == "coh_aaa"


def test_the_fact_body_of_a_refusal_names_the_reason() -> None:
    """Refusals are WRITTEN, so last week's "top decile" is overwritten by "we cannot say" rather
    than left standing on a cohort that has since shrunk below the floor."""
    body = position_fact_value(CohortRefusal(CohortRefusalReason.INSUFFICIENT_COVERAGE, COHORT,
                                             METRIC, 6, AT, "half of them are unread"))
    assert body["refused"] == "insufficient_coverage"
    assert body["population_size"] == 6 and body["cohort_id"] == COHORT
    assert "percentile_bp" not in body, "a refusal carries no rank"


# =================================================================================================
# U2 · THE LOOKALIKE — traits by name, never a similarity score
# =================================================================================================

def _best_customers(count: int = 6) -> dict[str, dict[str, object]]:
    """A reference cohort: six accounts, all fintech, all on enterprise, ARR 100..600."""
    return {f"ref_{i:02d}": {"account.industry": "fintech", "account.plan": "enterprise",
                             "account.arr_minor_units": (i + 1) * 100_000,
                             "node.name": f"Reference {i}"}
            for i in range(count)}


def test_a_reference_profile_is_modal_for_text_and_an_iqr_for_numbers() -> None:
    profile = reference_profile(cohort_id="coh_top_arr", node_type="company",
                                member_facts=_best_customers(), eval_time=AT)
    assert isinstance(profile, ReferenceProfile)
    bands = {band.fact: band for band in profile.bands}
    assert bands["account.industry"].modal == "fintech"
    assert bands["account.plan"].modal == "enterprise"
    arr = bands["account.arr_minor_units"]
    # Nearest-rank on six ordered values: index `(q_bp * (n - 1)) // 10000`, so p25 is the 2nd
    # and p75 the 4th. The SAME quantile the percentile card cuts on — the band and the
    # distribution shown beside it cannot come from two different rules.
    assert (arr.low, arr.high) == (200_000, 400_000), "the cohort's own p25..p75, inclusive"
    assert isinstance(arr.low, int) and isinstance(arr.high, int)


def test_the_profile_never_carries_identity() -> None:
    """`node.name` is the identity, not a trait: profiling on it would either be a tautology or
    one node's name leaking onto another node's card. `node.type` is constant inside a cohort and
    would hand every candidate a free matching trait."""
    profile = reference_profile(cohort_id="coh_top_arr", node_type="company",
                                member_facts=_best_customers(), eval_time=AT)
    assert set(profile.facts).isdisjoint(NON_TRAIT_FACTS)
    assert NON_TRAIT_FACTS == {"node.name", "node.type"}


def test_a_reference_cohort_below_the_floor_refuses() -> None:
    outcome = reference_profile(cohort_id="coh_top_arr", node_type="company",
                                member_facts=_best_customers(4), eval_time=AT)
    assert isinstance(outcome, LookalikeRefusal)
    assert outcome.reason is LookalikeRefusalReason.INSUFFICIENT_POPULATION


def test_a_lookalike_returns_the_matching_traits_by_name() -> None:
    """Doc 04 step 5 IS the unit: *"matches on industry, company size and entry channel; differs
    on region"* is checkable and `0.87 similar` is not."""
    profile = reference_profile(cohort_id="coh_top_arr", node_type="company",
                                member_facts=_best_customers(), eval_time=AT)
    outcome = lookalike(profile, subject_node_id="node_lead", eval_time=AT,
                        facts={"account.industry": "fintech", "account.plan": "starter",
                               "account.arr_minor_units": 300_000})
    assert isinstance(outcome, Lookalike)
    assert outcome.matching == ("account.arr_minor_units", "account.industry")
    assert outcome.differing == ("account.plan",)
    assert outcome.match_bp == 2 * 10_000 // 3
    assert "matches on account.arr_minor_units, account.industry" in outcome.phrase
    assert "differs on account.plan" in outcome.phrase


def test_an_absent_trait_is_not_a_mismatch_and_the_denominator_says_so() -> None:
    """Counting an unrecorded trait as a difference would make a sparsely-known node look unlike
    your best customers because of what nobody wrote down. `2 of 2` and `2 of 11` are the same
    `match_bp` and completely different claims, which is why the count travels with it."""
    profile = reference_profile(cohort_id="coh_top_arr", node_type="company",
                                member_facts=_best_customers(), eval_time=AT)
    outcome = lookalike(profile, subject_node_id="node_lead", eval_time=AT,
                        facts={"account.industry": "fintech", "account.plan": "enterprise",
                               "account.arr_minor_units": 300_000, "account.churned_at": None})
    assert outcome.evaluated_traits == 3
    assert outcome.match_bp == 10_000


def test_too_few_known_traits_refuses_rather_than_scoring_a_coin_flip() -> None:
    profile = reference_profile(cohort_id="coh_top_arr", node_type="company",
                                member_facts=_best_customers(), eval_time=AT)
    outcome = lookalike(profile, subject_node_id="node_lead", eval_time=AT,
                        facts={"account.industry": "fintech"})
    assert isinstance(outcome, LookalikeRefusal)
    assert outcome.reason is LookalikeRefusalReason.TOO_FEW_TRAITS
    assert outcome.evaluated_traits == 1 < MIN_LOOKALIKE_TRAITS


def test_the_numeric_band_is_inclusive_at_both_ends() -> None:
    """The account that defines the edge of your best customers must not fall outside the profile
    of your best customers."""
    profile = reference_profile(cohort_id="coh_top_arr", node_type="company",
                                member_facts=_best_customers(), eval_time=AT)
    band = {b.fact: b for b in profile.bands}["account.arr_minor_units"]
    assert band.contains(band.low) and band.contains(band.high)
    assert not band.contains(band.low - 1) and not band.contains(band.high + 1)


def test_the_modal_tie_breaks_on_the_value_not_the_dict_order() -> None:
    members = {f"ref_{i:02d}": {"account.industry": "fintech" if i % 2 else "adtech",
                                "account.plan": "growth"} for i in range(6)}
    forwards = reference_profile(cohort_id="c", node_type="company", member_facts=members,
                                 eval_time=AT)
    backwards = reference_profile(cohort_id="c", node_type="company",
                                  member_facts=dict(reversed(list(members.items()))),
                                  eval_time=AT)
    modal = {b.fact: b.modal for b in forwards.bands}["account.industry"]
    assert modal == "adtech", "three each: the smaller value by its string form wins"
    assert modal == {b.fact: b.modal for b in backwards.bands}["account.industry"]


def test_the_lookalike_replays_byte_identical() -> None:
    profile = reference_profile(cohort_id="coh_top_arr", node_type="company",
                                member_facts=_best_customers(), eval_time=AT)
    facts = {"account.industry": "fintech", "account.plan": "starter",
             "account.arr_minor_units": 300_000}
    first = lookalike(profile, subject_node_id="n", facts=facts, eval_time=AT)
    second = lookalike(profile, subject_node_id="n", facts=dict(reversed(list(facts.items()))),
                       eval_time=AT)
    assert lookalike_fact_value(first) == lookalike_fact_value(second)


def test_reference_cohorts_are_the_system_top_quartile_slots_only() -> None:
    """An authored cohort a founder happened to call "top quartile" is their own definition, and
    turning it into the reference population would be this module deciding what "best" means."""
    registry = default_fact_registry()
    shipped = define_cohort(org_id="org_x", name="account.arr_minor_units · top quartile",
                            node_type="company",
                            predicate={"all": [{"fact": "account.arr_minor_units", "op": "gt",
                                                "value": 10}]},
                            created_by=SYSTEM_AUTHOR, eval_time=AT, registry=registry)
    authored = define_cohort(org_id="org_x", name="My own top quartile", node_type="company",
                             predicate={"all": [{"fact": "account.plan", "op": "eq",
                                                 "value": "growth"}]},
                             created_by="harsh@thegenios.com", eval_time=AT, registry=registry)
    lower = define_cohort(org_id="org_x", name="account.arr_minor_units · bottom quartile",
                          node_type="company",
                          predicate={"all": [{"fact": "account.arr_minor_units", "op": "lte",
                                              "value": 10}]},
                          created_by=SYSTEM_AUTHOR, eval_time=AT, registry=registry)
    assert reference_cohorts([shipped, authored, lower]) == (shipped,)


# =================================================================================================
# THE FIELD NAMES
# =================================================================================================

def test_the_fact_fields() -> None:
    assert position_fact_field(METRIC) == f"{POSITION_FACT_PREFIX}{METRIC}"
    assert lookalike_fact_field(COHORT) == f"{LOOKALIKE_FACT_PREFIX}{COHORT}"
    with pytest.raises(ValueError):
        position_fact_field("")


# =================================================================================================
# THE WIRING — a REAL sweep, on a REAL database, reaching the comparator
# =================================================================================================

def test_the_drain_calls_the_comparison_refresh() -> None:
    """The cheap absence guard; the row below is the real one."""
    runner = (_ENGINE / "context" / "runner.py").read_text()
    assert "refresh_comparison_facts" in runner
    assert "comparison_facts" in runner


def _seed_cohort_of_accounts(store, org: str, at: datetime, *, count: int = 8,
                             dark: int = 0, dark_days: int = 300, joined_days_ago: int = 7,
                             cohort_name: str = "All active accounts",
                             prefix: str = "node_cmp_") -> str:
    """One org, `count` company nodes, one declared cohort holding all of them, and a reading of
    `deal.stage_age_days` for each — written through the REAL history store, so the fixture cannot
    seed a series the sampler itself could never have produced.

    `dark` members get their ONLY reading `dark_days` ago and nothing since — a connector that
    died, which is the state D6 says the plumbing could not distinguish from a live member. The
    row exists, so a test that finds them `unknown` is reading the horizon and not an empty table.
    """
    registry = default_fact_registry()
    definition = define_cohort(
        org_id=org, name=cohort_name, node_type="company",
        predicate={"all": [{"fact": "node.type", "op": "eq", "value": "company"}]},
        created_by=SYSTEM_AUTHOR, eval_time=at, registry=registry)
    nodes = [f"{prefix}{index:02d}" for index in range(count)]
    with store.engine.begin() as conn:
        conn.execute(text("insert into orgs (id, name) values (:o, 'Comparator Wiring') "
                          "on conflict (id) do nothing"), {"o": org})
        for index, node in enumerate(nodes):
            conn.execute(text(
                "insert into graph_nodes (node_id, version, org_id, node_type, display_name) "
                "values (:n, 1, :o, 'company', :d) on conflict do nothing"),
                {"n": node, "o": org, "d": f"Account {index}"})
            conn.execute(text(
                "insert into graph_facts (fact_version_id, fact_id, org_id, subject_node_id, "
                "  field, value, value_type, status, occurred_at, valid_from) values "
                "(:vid, :fid, :o, :n, 'account.industry', cast('\"fintech\"' as jsonb), 'string', "
                " 'active', :at, :at) on conflict (fact_version_id) do nothing"),
                {"vid": f"fv_ind_{node}", "fid": f"f_ind_{node}", "o": org,
                 "n": node, "at": at - timedelta(days=30)})
    save_definitions(store.engine, [definition])
    week = period_start(at - timedelta(days=joined_days_ago), MetricGrain.WEEK)
    with store.engine.begin() as conn:
        for node in nodes:
            conn.execute(text(
                f"insert into {COHORT_MEMBERSHIP_TABLE} (org_id, cohort_id, node_id, joined_at, "
                "  left_at, miss_streak, evaluated_at) "
                "values (:o, :c, :n, :j, null, 0, :j) on conflict do nothing"),
                {"o": org, "c": definition.cohort_id, "n": node, "j": week})

    history = PostgresMetricHistory(store.engine, sampler_registry())
    metric = TrendedMetric.DEAL_STAGE_AGE_DAYS.value
    month = period_start(at, MetricGrain.MONTH)
    long_ago = period_start(at - timedelta(days=dark_days), MetricGrain.MONTH)
    # TWO writes, because a dead connector's last SAMPLE is as old as its last reading. Writing
    # the dark points with a recent `sampled_at` would seed a series the sampler could not have
    # produced, and would make the point-in-time read in the coverage tests untestable.
    if dark:
        history.put(org, [MetricPoint(subject_node_id=node, metric=metric,
                                      value_bp=10 + index * 10, unit=MetricUnit.DAYS,
                                      observed_at=long_ago, known=True)
                          for index, node in enumerate(nodes[:dark])],
                    reason=SampleReason.SCHEDULED, sampled_at=long_ago + timedelta(days=1))
    history.put(org, [MetricPoint(subject_node_id=node, metric=metric,
                                  value_bp=10 + index * 10, unit=MetricUnit.DAYS,
                                  observed_at=month, known=True)
                      for index, node in enumerate(nodes) if index >= dark],
                reason=SampleReason.BACKFILL, sampled_at=at - timedelta(days=2))
    return definition.cohort_id


def _drop_org(store, org: str) -> None:
    with store.engine.begin() as conn:
        for table in ("cohort_membership", "cohort_definitions", "metric_history",
                      "graph_observations", "graph_facts", "graph_nodes"):
            conn.execute(text(f"delete from {table} where org_id=:o"), {"o": org})
        conn.execute(text("delete from orgs where id=:o"), {"o": org})


@pytest.mark.pg
def test_cohort_readings_are_point_in_time(pg_store) -> None:
    """The population AS IT WAS. A member who left before the instant is not in it, and a reading
    observed after the instant is not in it either — asked in September, March's answer."""
    org = "org_cmp_pit"
    cohort = _seed_cohort_of_accounts(pg_store, org, AT)
    try:
        now = cohort_readings(pg_store, org_id=org, cohort_id=cohort,
                              metric=TrendedMetric.DEAL_STAGE_AGE_DAYS.value, eval_time=AT)
        assert now.member_count == 8 and len(now.values) == 8 and now.unknown == 0

        before = cohort_readings(pg_store, org_id=org, cohort_id=cohort,
                                 metric=TrendedMetric.DEAL_STAGE_AGE_DAYS.value,
                                 eval_time=AT - timedelta(days=40))
        assert before.member_count == 0, "nobody had joined yet at that instant"

        with pg_store.engine.begin() as conn:
            conn.execute(text(f"update {COHORT_MEMBERSHIP_TABLE} set left_at = :l "
                              "where org_id=:o and node_id='node_cmp_00'"),
                         {"o": org, "l": AT - timedelta(days=1)})
        after = cohort_readings(pg_store, org_id=org, cohort_id=cohort,
                                metric=TrendedMetric.DEAL_STAGE_AGE_DAYS.value, eval_time=AT)
        assert after.member_count == 7, "the departed member is out of TODAY's population"
        still = cohort_readings(pg_store, org_id=org, cohort_id=cohort,
                                metric=TrendedMetric.DEAL_STAGE_AGE_DAYS.value,
                                eval_time=AT - timedelta(days=2))
        assert still.member_count == 8, "and back in the population of the instant before"
    finally:
        _drop_org(pg_store, org)


@pytest.mark.pg
def test_comparing_against_a_cohort_the_subject_is_not_in_refuses(pg_store) -> None:
    org = "org_cmp_stranger"
    cohort = _seed_cohort_of_accounts(pg_store, org, AT)
    try:
        outcome = compare_in_cohort(pg_store, org_id=org, cohort_id=cohort,
                                    metric=TrendedMetric.DEAL_STAGE_AGE_DAYS.value,
                                    subject_node_id="node_not_here", eval_time=AT)
        assert isinstance(outcome, CohortRefusal)
        assert outcome.reason is CohortRefusalReason.SUBJECT_NOT_A_MEMBER
        member = compare_in_cohort(pg_store, org_id=org, cohort_id=cohort,
                                   metric=TrendedMetric.DEAL_STAGE_AGE_DAYS.value,
                                   subject_node_id="node_cmp_03", eval_time=AT,
                                   unit=MetricUnit.DAYS)
        assert isinstance(member, PositionedReading)
        assert member.percentile_bp == 5_000 and member.value_bp == 40
        assert member.phrase.startswith("40 days, the 50th percentile of 8 in")
    finally:
        _drop_org(pg_store, org)


@pytest.mark.pg
def test_the_sweep_writes_the_position_fact(pg_store) -> None:
    """**THIS IS THE TEST THAT MATTERS.** `context/runner.process_pending` — the sweep every sync
    route and the upload route call — reaches L2.4.5 and leaves a `derived.cohort_position.*` row
    behind. Nothing above this line would notice if the two lines in `runner.py` were deleted.

    Driven with NO pending events on purpose: a comparison moves because the population moved, so
    the org whose inbox went quiet is exactly the org whose position is worth recomputing.
    """
    from genios_engine.context.runner import process_pending
    from genios_engine.platform.config import get_settings

    org = "org_cmp_wiring"
    _seed_cohort_of_accounts(pg_store, org, AT)
    try:
        out = process_pending(org_id=org, store=pg_store, llm=None,
                              crypto_key=get_settings().crypto_key, eval_time=AT)
        assert out["processed"] == 0, "no events: this sweep drained nothing"
        assert out["comparison_facts"] > 0, (
            "the sweep reached no comparator — `refresh_comparison_facts` is not on the real "
            "request path")

        with pg_store.engine.connect() as conn:
            rows = conn.execute(text(
                "select subject_node_id, field, value from graph_facts "
                "where org_id=:o and field like :p order by subject_node_id"),
                {"o": org, "p": f"{POSITION_FACT_PREFIX}%"}).all()
        assert rows, "a population of eight and no position written"
        bodies = {row.subject_node_id: row.value for row in rows}
        assert len(bodies) >= 8
        one = bodies["node_cmp_00"]
        assert one["population_size"] >= MIN_COHORT_POPULATION
        assert one["cohort_id"], "Law 2 — a percentile without its population is not returned"
        assert 0 <= one["percentile_bp"] <= 10_000
        assert CohortBand(one["band"]).contains(one["percentile_bp"])
        # CHANGED from `one["p25_bp"] <= one["p50_bp"] <= one["p75_bp"]`, and the change IS the
        # D1 fix rather than a weakening: this fixture has EIGHT members, and a three-rung ladder
        # over eight readings is three of those eight accounts' exact numbers printed on a fourth
        # account's card — which `peer_baseline` refuses to publish over the same population, at
        # the same floor, in the same wave. Withheld, and the body says so, so a reader can tell
        # "too small to describe" from "written by an older writer". The publishable case is
        # asserted in `test_a_cohort_of_ten_publishes_a_smoothed_ladder_not_its_members_readings`.
        assert one["p25_bp"] is None and one["p50_bp"] is None and one["p75_bp"] is None
        assert str(MIN_BASELINE_POPULATION) in one["distribution_withheld"]
        assert "percentile of" in one["phrase"]

        # THE WRITE-AMPLIFICATION PROOF. A comparison is recomputed on EVERY drain, so an
        # appending writer is the `expertise_packages` shape that put this database into
        # read-only. A second sweep at the same instant must not add a single row.
        with pg_store.engine.connect() as conn:
            before = conn.execute(text(
                "select count(*) from graph_facts where org_id=:o and field like :p"),
                {"o": org, "p": "derived.%"}).scalar()
        process_pending(org_id=org, store=pg_store, llm=None,
                        crypto_key=get_settings().crypto_key, eval_time=AT)
        with pg_store.engine.connect() as conn:
            after = conn.execute(text(
                "select count(*) from graph_facts where org_id=:o and field like :p"),
                {"o": org, "p": "derived.%"}).scalar()
        assert after == before > 0, "two sweeps at one instant must not grow graph_facts"
    finally:
        _drop_org(pg_store, org)


@pytest.mark.pg
def test_the_sweep_refuses_on_a_cohort_below_the_floor(pg_store) -> None:
    """Four accounts is not a weak comparison, it is no comparison — and the REFUSAL is written,
    so a card that said "top decile" last week retracts it rather than keeping it."""
    org = "org_cmp_floor"
    _seed_cohort_of_accounts(pg_store, org, AT, count=4)
    try:
        sweep = refresh_comparison_facts(pg_store, org, eval_time=AT)
        assert isinstance(sweep, ComparisonSweep)
        assert sweep.positions == 0, "four members: nothing may be positioned"
        with pg_store.engine.connect() as conn:
            rows = conn.execute(text(
                "select value from graph_facts where org_id=:o and field like :p"),
                {"o": org, "p": f"{POSITION_FACT_PREFIX}%"}).all()
        assert not rows, "the pair never reaches the writer: the floor is in the SQL too"
    finally:
        _drop_org(pg_store, org)


@pytest.mark.pg
def test_deleting_an_org_erases_its_comparison_facts(pg_store) -> None:
    """L2.4.5 adds NO TABLE: the position is a `graph_facts` row and `graph_facts` is already on
    the org-scoped erasure list. Proven rather than read off the list, because the loop in
    `api/account_routes` has no try/except and an omission there is silent."""
    from genios_engine.api.account_routes import _ORG_SCOPED_TABLES

    assert "graph_facts" in _ORG_SCOPED_TABLES
    org = "org_cmp_erasure"
    _seed_cohort_of_accounts(pg_store, org, AT)
    try:
        assert refresh_comparison_facts(pg_store, org, eval_time=AT).positions > 0
        with pg_store.engine.begin() as conn:
            conn.execute(text("delete from graph_facts where org_id=:o"), {"o": org})
        with pg_store.engine.connect() as conn:
            assert conn.execute(text(
                "select count(*) from graph_facts where org_id=:o and field like :p"),
                {"o": org, "p": f"{POSITION_FACT_PREFIX}%"}).scalar() == 0
    finally:
        _drop_org(pg_store, org)


def _seed_reference_cohort(store, org: str, at: datetime) -> str:
    """Six "best customers" in a SYSTEM top-quartile cohort, and three candidates outside it.

    Declared by hand rather than grown through `refresh_cohorts_for_drain`, because the shipped
    quartile family needs twenty accounts to cut at all (`MIN_QUARTILE_POPULATION`) and this test
    is about what U2 does with a reference population, not about how one comes to exist.
    """
    registry = default_fact_registry()
    definition = define_cohort(
        org_id=org, name="account.arr_minor_units · top quartile", node_type="company",
        predicate={"all": [{"fact": "account.arr_minor_units", "op": "gt", "value": 150_000}]},
        created_by=SYSTEM_AUTHOR, eval_time=at, registry=registry)
    members = [f"node_ref_{i:02d}" for i in range(6)]
    candidates = {"node_lead_alike": ("fintech", "enterprise", 300_000),
                  "node_lead_unlike": ("retail", "starter", 1_000),
                  "node_lead_thin": (None, None, None)}
    with store.engine.begin() as conn:
        conn.execute(text("insert into orgs (id, name) values (:o, 'Lookalike') "
                          "on conflict (id) do nothing"), {"o": org})
        rows: list[tuple[str, str, str, object]] = []
        for index, node in enumerate(members):
            rows += [(node, "account.industry", "string", '"fintech"'),
                     (node, "account.plan", "string", '"enterprise"'),
                     (node, "account.arr_minor_units", "number", str((index + 2) * 100_000))]
        for node, (industry, plan, arr) in candidates.items():
            if industry is not None:
                rows += [(node, "account.industry", "string", f'"{industry}"'),
                         (node, "account.plan", "string", f'"{plan}"'),
                         (node, "account.arr_minor_units", "number", str(arr))]
        for node in (*members, *candidates):
            conn.execute(text(
                "insert into graph_nodes (node_id, version, org_id, node_type, display_name) "
                "values (:n, 1, :o, 'company', :d) on conflict do nothing"),
                {"n": node, "o": org, "d": node})
        for serial, (node, field, kind, raw) in enumerate(rows):
            conn.execute(text(
                "insert into graph_facts (fact_version_id, fact_id, org_id, subject_node_id, "
                "  field, value, value_type, status, occurred_at, valid_from) values "
                "(:vid, :fid, :o, :n, :f, cast(:v as jsonb), :t, 'active', :at, :at) "
                "on conflict (fact_version_id) do nothing"),
                {"vid": f"fv_look_{serial}", "fid": f"f_look_{serial}", "o": org, "n": node,
                 "f": field, "v": raw, "t": kind, "at": at - timedelta(days=30)})
    save_definitions(store.engine, [definition])
    week = period_start(at - timedelta(days=7), MetricGrain.WEEK)
    with store.engine.begin() as conn:
        for node in members:
            conn.execute(text(
                f"insert into {COHORT_MEMBERSHIP_TABLE} (org_id, cohort_id, node_id, joined_at, "
                "  left_at, miss_streak, evaluated_at) values (:o, :c, :n, :j, null, 0, :j) "
                "on conflict do nothing"),
                {"o": org, "c": definition.cohort_id, "n": node, "j": week})
    return definition.cohort_id


@pytest.mark.pg
def test_the_sweep_writes_the_lookalike_fact(pg_store) -> None:
    """U2 ON THE REAL PATH. `refresh_comparison_facts` — the call `runner.process_pending` makes —
    profiles the shipped top-quartile population and scores the candidates OUTSIDE it.

    A member of the reference cohort is skipped on purpose: "your best customer looks like your
    best customers" is not a finding, and writing it would fill the table with tautologies.
    """
    org = "org_cmp_lookalike"
    cohort = _seed_reference_cohort(pg_store, org, AT)
    try:
        sweep = refresh_comparison_facts(pg_store, org, eval_time=AT)
        assert sweep.lookalikes > 0, "no lookalike written: U2 is not on the sweep path"
        with pg_store.engine.connect() as conn:
            rows = conn.execute(text(
                "select subject_node_id, value from graph_facts "
                "where org_id=:o and field = :f"),
                {"o": org, "f": lookalike_fact_field(cohort)}).all()
        bodies = {row.subject_node_id: row.value for row in rows}
        assert set(bodies) == {"node_lead_alike", "node_lead_unlike"}, (
            "members are skipped, and the trait-less candidate is REFUSED rather than scored")

        alike = bodies["node_lead_alike"]
        assert alike["match_bp"] == 10_000
        assert "account.industry" in alike["matching"] and alike["differing"] == []
        assert "matches on" in alike["phrase"], "the traits by NAME, not a similarity score"

        unlike = bodies["node_lead_unlike"]
        # Four traits, not three: `node.tenure_days` is computed by `load_node_facts` from the
        # node row and every node in this fixture was created at the same instant, so the
        # candidate genuinely matches the reference cohort on tenure and differs on the other
        # three. `1 of 4` is the honest answer and asserting `0 of 3` here would have been the
        # test pretending a real trait is not one.
        assert sorted(unlike["differing"]) == ["account.arr_minor_units", "account.industry",
                                               "account.plan"]
        assert unlike["matching"] == ["node.tenure_days"]
        assert unlike["evaluated_traits"] == 4
        assert unlike["match_bp"] == 1 * 10_000 // 4
    finally:
        _drop_org(pg_store, org)


# =================================================================================================
# D6 / D7 · THE COVERAGE REFUSAL, PRODUCED BY THE PLUMBING RATHER THAN HAND-FED
# =================================================================================================
#
# Every `INSUFFICIENT_COVERAGE` assertion in this suite used to call the PURE function with a
# literal `unknown=6`, which is why the defect survived a green suite: `unknown` is computed in
# `cohort_readings`, from a read that had no lower bound on `observed_at`, and no test ever made it
# come out of that read. Measured on real Postgres before the fix — a ten-member cohort with five
# members dark for 300 days reported `known: 10, unknown: 0` and published a percentile at 1000 bp.
# The two tests below seed exactly that org and let the plumbing produce the number.

@pytest.mark.pg
def test_a_member_dark_past_the_horizon_is_unknown_in_a_real_read(pg_store) -> None:
    """The rows ARE there — the assertion below counts them — so `unknown` is coming from the
    staleness horizon and not from an empty table. That is the difference between this test and
    every coverage test that preceded it."""
    org = "org_cmp_dark"
    metric = TrendedMetric.DEAL_STAGE_AGE_DAYS.value
    cohort = _seed_cohort_of_accounts(pg_store, org, AT, count=10, dark=5, dark_days=300)
    try:
        with pg_store.engine.connect() as conn:
            seeded = conn.execute(text(
                "select count(distinct subject_node_id) from metric_history "
                "where org_id=:o and metric=:m"), {"o": org, "m": metric}).scalar()
        assert seeded == 10, "all ten members have a reading on disk; five of them are ancient"

        readings = cohort_readings(pg_store, org_id=org, cohort_id=cohort, metric=metric,
                                   eval_time=AT)
        assert readings.member_count == 10
        assert len(readings.values) == 5, "the five dark members are not counted as known"
        assert readings.unknown == 5, (
            "before the horizon this was 0 and the coverage floor could never trip")
        assert set(readings.values) == {f"node_cmp_{i:02d}" for i in range(5, 10)}
    finally:
        _drop_org(pg_store, org)


@pytest.mark.pg
def test_a_half_dark_cohort_refuses_for_coverage_from_the_read_path(pg_store) -> None:
    """The refusal, produced end to end: no `unknown=` is passed by hand anywhere in this test.

    Five of ten dark is 5000 bp of the population unread, past `MAX_UNKNOWN_SHARE_BP`, so the
    honest answer is "we cannot say" rather than a peer position computed over whoever happened to
    still be instrumented — which is what a percentile mixing an 18-month-old reading with this
    week's actually is.
    """
    org = "org_cmp_dark_refusal"
    metric = TrendedMetric.DEAL_STAGE_AGE_DAYS.value
    cohort = _seed_cohort_of_accounts(pg_store, org, AT, count=10, dark=5, dark_days=300)
    try:
        outcome = compare_in_cohort(pg_store, org_id=org, cohort_id=cohort, metric=metric,
                                    subject_node_id="node_cmp_09", eval_time=AT)
        assert isinstance(outcome, CohortRefusal)
        assert outcome.reason is CohortRefusalReason.INSUFFICIENT_COVERAGE
        assert "5 of 10" in outcome.detail

        sweep = refresh_comparison_facts(pg_store, org, eval_time=AT)
        with pg_store.engine.connect() as conn:
            bodies = [row.value for row in conn.execute(text(
                "select value from graph_facts where org_id=:o and field like :p "
                "and valid_to is null"), {"o": org, "p": f"{POSITION_FACT_PREFIX}%"}).all()]
        assert bodies, "the refusal is WRITTEN, so a stale 'top decile' retracts itself"
        assert all(body.get("refused") == "insufficient_coverage" for body in bodies), bodies
        assert sweep.refusals == len(bodies) and sweep.positions == len(bodies)

        # And a cohort where only one member is dark is still comparable — the floor is a SHARE,
        # not "any gap refuses", so one dead connector does not silence a healthy org.
        healthy = _seed_cohort_of_accounts(pg_store, "org_cmp_one_dark", AT, count=10, dark=1)
        try:
            live = compare_in_cohort(pg_store, org_id="org_cmp_one_dark", cohort_id=healthy,
                                     metric=metric, subject_node_id="node_cmp_09", eval_time=AT)
            assert isinstance(live, PositionedReading)
            assert live.population_size == 9
        finally:
            _drop_org(pg_store, "org_cmp_one_dark")
    finally:
        _drop_org(pg_store, org)


@pytest.mark.pg
def test_the_horizon_moves_with_eval_time_so_a_past_read_gets_the_past_coverage(pg_store) -> None:
    """The same org read at two instants. Asked at the dark members' own period they are KNOWN, and
    asked in March they are not — the horizon is a function of `eval_time`, so a replay of an old
    decision reproduces the coverage that decision was made with."""
    org = "org_cmp_dark_pit"
    metric = TrendedMetric.DEAL_STAGE_AGE_DAYS.value
    cohort = _seed_cohort_of_accounts(pg_store, org, AT, count=10, dark=5, dark_days=300,
                                      joined_days_ago=400)
    try:
        then = period_start(AT - timedelta(days=300), MetricGrain.MONTH) + timedelta(days=15)
        past = cohort_readings(pg_store, org_id=org, cohort_id=cohort, metric=metric,
                               eval_time=then)
        assert past.member_count == 10, "everyone had joined by then"
        assert len(past.values) == 5 and past.unknown == 5, (
            "at that instant the dark five were the FRESH ones and the other five were unread — "
            "the mirror image of the read at AT, off exactly the same rows")
        assert set(past.values) == {f"node_cmp_{i:02d}" for i in range(5)}
        now = cohort_readings(pg_store, org_id=org, cohort_id=cohort, metric=metric, eval_time=AT)
        assert set(now.values) == {f"node_cmp_{i:02d}" for i in range(5, 10)}
    finally:
        _drop_org(pg_store, org)


# =================================================================================================
# D5 · THE WRITER — a March position still reads at March after a September sweep
# =================================================================================================

def _positions_of(store, org: str) -> list:
    with store.engine.connect() as conn:
        return conn.execute(text(
            "select fact_version_id, valid_from, valid_to, status, value from graph_facts "
            "where org_id=:o and field like :p order by valid_from, fact_version_id"),
            {"o": org, "p": f"{POSITION_FACT_PREFIX}%"}).all()


@pytest.mark.pg
def test_a_march_position_still_reads_at_march_after_a_september_sweep(pg_store) -> None:
    """**THE D5 TEST.** Read through `graph_store.read_graph(as_of=...)` — X7's own reader — and
    not through a window predicate this test wrote itself.

    The writer this module used to own ended `on conflict ... set valid_from = excluded.valid_from`,
    which MOVES the window of a row that already exists. A position published in March therefore
    read back as `[September, inf)` after one September sweep, `read_graph(as_of=March)` returned
    nothing, and the audit answered "GeniOS knew nothing about this node's position in March"
    about a fact GeniOS published in March. Doc 02's acceptance row — replaying a March decision
    against `as_of=March` reproduces its inputs — failed for exactly the facts L2.4.5 exists to
    produce.
    """
    org = "org_cmp_asof"
    metric = TrendedMetric.DEAL_STAGE_AGE_DAYS.value
    september = AT + timedelta(days=190)
    _seed_cohort_of_accounts(pg_store, org, AT, count=8)
    field = position_fact_field(metric)
    try:
        march_sweep = refresh_comparison_facts(pg_store, org, eval_time=AT)
        assert march_sweep.positions == 8 and march_sweep.written == 8

        march_view = pg_store.read_graph(org, as_of=AT)
        march_fact = next(f for f in march_view.facts
                          if f.subject_node_id == "node_cmp_00" and f.field == field)
        assert march_fact.value["percentile_bp"] == 1_250, "lowest of eight"

        # September: fresh readings for everyone, and node_cmp_00 is now the HIGHEST, so its
        # position genuinely changes rather than being recomputed to the same answer.
        history = PostgresMetricHistory(pg_store.engine, sampler_registry())
        history.put(org, [MetricPoint(subject_node_id=f"node_cmp_{i:02d}", metric=metric,
                                      value_bp=900 if i == 0 else 10 + i * 10,
                                      unit=MetricUnit.DAYS,
                                      observed_at=period_start(september, MetricGrain.MONTH),
                                      known=True) for i in range(8)],
                    reason=SampleReason.SCHEDULED, sampled_at=september - timedelta(days=1))
        refresh_comparison_facts(pg_store, org, eval_time=september)

        replay = pg_store.read_graph(org, as_of=AT)
        replayed = [f for f in replay.facts
                    if f.subject_node_id == "node_cmp_00" and f.field == field]
        assert len(replayed) == 1, "exactly one row is open at March — no gap, no double count"
        assert replayed[0].value["percentile_bp"] == 1_250, (
            "March's answer, unchanged, after September rewrote the node's position")
        assert replayed[0].valid_from == march_fact.valid_from, "valid_from NEVER moves"

        now_view = pg_store.read_graph(org, as_of=september)
        current = next(f for f in now_view.facts
                       if f.subject_node_id == "node_cmp_00" and f.field == field)
        assert current.value["percentile_bp"] == 10_000, "and September sees September's"
        assert current.fact_version_id != replayed[0].fact_version_id

        closed = [row for row in _positions_of(pg_store, org)
                  if row.fact_version_id == replayed[0].fact_version_id]
        assert closed[0].status == "superseded" and closed[0].valid_to is not None, (
            "the old stint is CLOSED, never deleted — a hard delete makes history unreadable")
    finally:
        _drop_org(pg_store, org)


@pytest.mark.pg
def test_many_sweeps_in_one_period_are_one_row_and_write_nothing_after_the_first(pg_store) -> None:
    """The write-amplification bound, restated as arithmetic: rows per (node, field) equal the
    number of ISO WEEKS IN WHICH THE VALUE CHANGED, not the number of sweeps.

    Six sweeps at six different instants inside one ISO week. `expertise_packages` reached 181 MB
    over 345 rows and put this database into read-only because a writer on a recurring path
    appended; the second through sixth sweeps here write nothing at all, and the first row's
    `valid_from` does not move under any of them.
    """
    org = "org_cmp_bound"
    _seed_cohort_of_accounts(pg_store, org, AT, count=8)
    try:
        first = refresh_comparison_facts(pg_store, org, eval_time=AT)
        opening = {row.fact_version_id: row.valid_from for row in _positions_of(pg_store, org)}
        assert len(opening) == 8 and first.written == 8

        for hour in range(1, 6):
            later = refresh_comparison_facts(pg_store, org, eval_time=AT + timedelta(hours=hour))
            assert later.positions == 8, "the sweep still POSITIONS every node"
            assert later.written == 0, (
                "and writes nothing: an agreeing sweep is not evidence and leaves no dead tuple")
        after = {row.fact_version_id: row.valid_from for row in _positions_of(pg_store, org)}
        assert after == opening, "same rows, same windows, after six sweeps"

        # And the id is period-keyed, which is what makes a LATER change a new row rather than an
        # edit to this one's window.
        week = period_start(AT, MetricGrain.WEEK)
        assert derived_fact_version_id(VERSION_PREFIX, "node_cmp_00",
                                       position_fact_field(
                                           TrendedMetric.DEAL_STAGE_AGE_DAYS.value),
                                       week) in opening
    finally:
        _drop_org(pg_store, org)


# =================================================================================================
# D9 · THE BUDGET DEFERS WORK; IT DOES NOT DELETE IT
# =================================================================================================

@pytest.mark.pg
def test_an_org_above_the_position_budget_eventually_positions_every_node(pg_store) -> None:
    """The permanently dark tail, and the proof that it is gone.

    `sorted(by_node)` is stable across sweeps, so an org above `position_limit` published the same
    two nodes on every drain and the other six could NEVER receive a position — while this module
    and `runner.py` both asserted "work not done this sweep is done by the next one". Ordering the
    publication by staleness makes that sentence true: a node with no open fact sorts before every
    node that has one, so the unpositioned set drains monotonically with no cursor table to keep.

    Four sweeps at a budget of two over eight nodes. The assertion is not "more got done" — it is
    that the SET of positioned nodes is the whole population, which the old order could not reach.
    """
    org = "org_cmp_budget"
    _seed_cohort_of_accounts(pg_store, org, AT, count=8)
    try:
        seen: set[str] = set()
        for sweep_index in range(4):
            sweep = refresh_comparison_facts(pg_store, org, eval_time=AT, position_limit=2,
                                             lookalike_limit=0)
            assert sweep.positions == 2
            assert sweep.budget_exhausted, (
                "the flag still says the pass stopped at its cap — what changed is that the two "
                "it publishes are not the same two every time")
            assert sweep.written == 2, "and both of them are NEW rows, not re-confirmations"
            with pg_store.engine.connect() as conn:
                seen = {str(row.subject_node_id) for row in conn.execute(text(
                    "select subject_node_id from graph_facts "
                    "where org_id=:o and field like :p and valid_to is null"),
                    {"o": org, "p": f"{POSITION_FACT_PREFIX}%"}).all()}
            assert len(seen) == 2 * (sweep_index + 1), (
                f"sweep {sweep_index} re-published nodes that already had a position while "
                f"others had none: {sorted(seen)}")
        assert seen == {f"node_cmp_{i:02d}" for i in range(8)}
    finally:
        _drop_org(pg_store, org)


@pytest.mark.pg
def test_a_pair_below_the_pair_budget_is_reached_by_a_later_sweep(pg_store) -> None:
    """The same defect one level up, in `_COMPARED_PAIRS_SQL`. `order by m.cohort_id, h.metric`
    is stable, so on an org with more (cohort, metric) pairs than `MAX_COMPARED_PAIRS_PER_SWEEP`
    the tail cohorts were never compared at all. The order key is now "some member of this pair
    has no open position", which is read off the data — no cursor, nothing to lose on a restart.
    """
    org = "org_cmp_pairs"
    first = _seed_cohort_of_accounts(pg_store, org, AT, count=6, cohort_name="Alpha accounts",
                                     prefix="node_aa_")
    second = _seed_cohort_of_accounts(pg_store, org, AT, count=6, cohort_name="Zulu accounts",
                                      prefix="node_zz_")
    try:
        assert first != second
        refresh_comparison_facts(pg_store, org, eval_time=AT, pair_limit=1, lookalike_limit=0)
        with pg_store.engine.connect() as conn:
            after_one = {str(row.subject_node_id) for row in conn.execute(text(
                "select subject_node_id from graph_facts where org_id=:o and field like :p"),
                {"o": org, "p": f"{POSITION_FACT_PREFIX}%"}).all()}
        assert len(after_one) == 6, "one pair's worth of nodes, whichever cohort sorted first"

        refresh_comparison_facts(pg_store, org, eval_time=AT, pair_limit=1, lookalike_limit=0)
        with pg_store.engine.connect() as conn:
            after_two = {str(row.subject_node_id) for row in conn.execute(text(
                "select subject_node_id from graph_facts where org_id=:o and field like :p"),
                {"o": org, "p": f"{POSITION_FACT_PREFIX}%"}).all()}
        assert len(after_two) == 12, (
            "the second sweep reached the OTHER cohort — under the old id order it would have "
            "re-read the same pair for ever and these six nodes would have no position at all")
    finally:
        _drop_org(pg_store, org)


# =================================================================================================
# THE POSITION ROUTE — the two defects it was serving, measured against the handler itself
# =================================================================================================

def _position_route(pg_store, org: str, cohort: str, metric: str, node: str, at: datetime):
    """Drive `GET /api/org/{org}/cohorts/{cohort_id}/position` through the ROUTER.

    Through the router and not through `compare_in_cohort`, because the defect was never in the
    function: both of these were served by a handler that called a DIFFERENT function, and a test
    that constructs the right one directly passes in a build where the route still calls the
    wrong one.
    """
    from fastapi.testclient import TestClient

    from genios_engine.api import cohort_routes as R
    from genios_engine.context.graph_store import GraphStore
    from genios_engine.main import app
    from genios_engine.platform.auth import get_current_org

    previous_graph, previous_now = R._graph, R._now
    R._graph = GraphStore(os.environ["GENIOS_TEST_DATABASE_URL"])
    R._now = lambda: at          # the clock is read at the request boundary; pin it there
    app.dependency_overrides[get_current_org] = lambda: org
    try:
        return TestClient(app).get(f"/api/org/{org}/cohorts/{cohort}/position",
                                   params={"metric": metric, "node_id": node}).json()
    finally:
        R._graph, R._now = previous_graph, previous_now
        app.dependency_overrides.pop(get_current_org, None)


@pytest.mark.pg
def test_the_position_route_refuses_a_half_dark_cohort(pg_store) -> None:
    """D6 ON THE ROUTE, which is where it survived this wave's first fix.

    `cohort_readings` got its staleness horizon and `cohort._VALUES_SQL` did not — and the route
    called the second one. Measured against this handler before the rewire, with five of ten
    members dark for 300 days, it answered

        {"position": {"population_size": 10, "percentile_bp": 10000, "band": "Q4", ...}}

    which is the reviewer's `known: 10, unknown: 0` served to a customer. The five dark members
    are now UNKNOWN, that is 5000 bp of the population unread, past `MAX_UNKNOWN_SHARE_BP`, and
    the honest answer is the refusal — carrying the count, so a reader can see WHY.
    """
    org = "org_cmp_route_dark"
    metric = TrendedMetric.DEAL_STAGE_AGE_DAYS.value
    _drop_org(pg_store, org)
    cohort = _seed_cohort_of_accounts(pg_store, org, AT, count=10, dark=5, dark_days=300)
    try:
        body = _position_route(pg_store, org, cohort, metric, "node_cmp_09", AT)
        assert body["position"] is None
        assert body["refusal"]["reason"] == "insufficient_coverage"
        assert body["refusal"]["detail"] == (
            f"5 of 10 members have no reading of {metric}")
        assert body["refusal"]["population_size"] == 5, "the five that CAN be read"
    finally:
        _drop_org(pg_store, org)


@pytest.mark.pg
def test_the_position_route_withholds_a_ladder_it_may_not_publish(pg_store) -> None:
    """D1 ON THE ROUTE. `CohortPosition.model_dump()` served p25/p50/p75 straight out.

    Those three numbers are `_quantile` over the sorted population — the literal readings of three
    named members — and the route published them from a floor of FIVE, on the same populations
    `peer_baseline` refuses to build a ladder over below TEN. Measured before the rewire on a
    five-member cohort the payload carried `p25_bp / p50_bp / p75_bp` equal to three of the other
    members' exact readings, beside an exact rank that bounds the fourth.

    The route now serves `PositionedReading`, whose `distribution` is `publishable_distribution` —
    withheld below the ladder's floor, and smoothed above it. The SUBJECT still gets everything
    that is about the subject: its own reading, its rank, its band, and how many it was compared
    against.
    """
    org = "org_cmp_route_ladder"
    metric = TrendedMetric.DEAL_STAGE_AGE_DAYS.value
    _drop_org(pg_store, org)
    cohort = _seed_cohort_of_accounts(pg_store, org, AT, count=MIN_COHORT_POPULATION)
    try:
        body = _position_route(pg_store, org, cohort, metric, "node_cmp_04", AT)
        position = body["position"]
        assert position is not None and body["refusal"] is None
        assert position["distribution"] is None, (
            "five members is under MIN_BASELINE_POPULATION, so the ladder IS the sorted "
            "population and there is nothing to publish that is not three members' readings")
        # the raw order statistics are not in the payload under any name
        assert not {"p25_bp", "p50_bp", "p75_bp"} & set(position)
        # and everything about the SUBJECT survives — the fix withholds a disclosure, not an answer
        assert position["population_size"] == MIN_COHORT_POPULATION
        assert position["percentile_bp"] == 10_000 and position["band"] == "Q4"
        assert position["subject_node_id"] == "node_cmp_04"
        assert isinstance(position["value_bp"], int)
    finally:
        _drop_org(pg_store, org)


@pytest.mark.pg
def test_the_position_route_publishes_a_smoothed_ladder_when_it_may(pg_store) -> None:
    """The other half: withholding is not the policy, publishing the BASELINE's form is.

    Ten live members clears `MIN_BASELINE_POPULATION`, so the distribution travels — and each rung
    is `peer_baseline.smoothed_rung`, the mean of three adjacent readings, rather than the reading
    of the one member standing at that rank.

    Asserted by RECOMPUTING the ladder from `smoothed_rung` over the population the route read,
    rather than by "at least one rung differs from the raw quantile": on an evenly spaced fixture
    the mean of three adjacent values IS the middle one, so that weaker check would fail on a
    correct implementation and pass on an incorrect one with a lumpier fixture. Where the two
    forms coincide they coincide because the population is uniform, which is not a disclosure.
    """
    org = "org_cmp_route_ladder_ok"
    metric = TrendedMetric.DEAL_STAGE_AGE_DAYS.value
    _drop_org(pg_store, org)
    cohort = _seed_cohort_of_accounts(pg_store, org, AT, count=MIN_BASELINE_POPULATION)
    try:
        body = _position_route(pg_store, org, cohort, metric, "node_cmp_04", AT)
        position = body["position"]
        assert position is not None
        ladder = position["distribution"]
        assert ladder is not None and len(ladder) == 3
        assert ladder[0] <= ladder[1] <= ladder[2], "a ladder is ordered or it is not a ladder"
        readings = cohort_readings(pg_store, org_id=org, cohort_id=cohort, metric=metric,
                                   eval_time=AT)
        known = sorted(readings.values.values())
        assert ladder == [smoothed_rung(known, q, BASELINE_SMOOTHING_WINDOW)
                          for q in (2_500, 5_000, 7_500)], (
            "the route must publish peer_baseline's ladder, not a second copy of the arithmetic")
        assert ladder != [known[len(known) * q // 10_000 - 1] for q in (2_500, 5_000, 7_500)] or (
            len(set(known)) < len(known)), (
            "if the smoothed ladder equals the raw one the population is uniform; on a population "
            "that is not, they must differ, or smoothing is a name and not a rule")
    finally:
        _drop_org(pg_store, org)
