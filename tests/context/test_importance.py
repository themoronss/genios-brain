"""L2.7.4-U1 · the situation importance COMPOSER — BLG-18 steps 2 through 6.

The gate that scores this unit is H5 and it lives next door in `test_situation_importance.py`,
because doc 09 invokes that path by name. THIS file is the unit suite under it: the arithmetic,
the six modifiers and their thresholds, the component record, the readers, and the four pins that
stop this module drifting away from the modules it reads.

**What is deliberately NOT tested here.** Step 1. `situation_bso.gather_l1_signals` already reads
Layer 1's real score and takes the max over the situation's live scored signals, and
`tests/test_situation_bso.py` owns that. Re-asserting it here would be a second copy of a passing
test; what this file asserts about the base is that the composer takes it as given and never
recomputes it.

**Three things every test in here holds to, because the unit does.** No float appears in an
expected value; no test calls a clock (`eval_time` is the fixture); and every assertion about a
modifier checks the RECORD as well as the number — a modifier that fires without leaving a
receipt is the failure this unit exists to prevent, and it is invisible if you only assert on
`importance_bp`.
"""

from __future__ import annotations

import json
import re
from datetime import timedelta
from pathlib import Path

import pytest

from genios_engine.context.importance import (
    ANOMALY_BP, ANOMALY_FACT_PREFIX, BP_MAX, COHORT_BP, COHORT_FACT_PREFIX, CONFLICT_BP,
    CORROBORATION_CAP_BP, CORROBORATION_PER_EXTRA_SOURCE_BP, DEPENDENCY_BLOCKED_FIELD,
    DEPENDENCY_MAX_BLOCKED, DEPENDENCY_PER_BLOCKED_BP, FACT_WINDOW_AT, FLAT_BASE_BP,
    IMPORTANCE_VERSION, METRIC_POLARITY, MIN_TREND_CONFIDENCE_BP, MODIFIER_CAP_BP, RISK_METRICS,
    STALENESS_BP, STALENESS_DAYS, TREND_BP, TREND_FACT_PREFIX, UNRESOLVED_RESOLUTION,
    AnomalyInput, CohortInput, ComposedImportance, ConflictInput, ConstituentSignal,
    DependencyInput, ImportanceBase, MetricPolarity, ModifierInputs, ModifierName, ModifierReason,
    TrendInput, assess_l1_supply, compose_situation_importance, worst_band)

MODULE = Path(__file__).resolve().parents[2] / "genios_engine" / "context" / "importance.py"

#: A subject the whole file shares. Named rather than generated so a failure message says which
#: node the modifier was about.
NODE = "node_acct_north"
COLD = "engagement.days_since_contact"          # HIGHER_IS_WORSE — a risk metric
TOUCHES = "engagement.touch_count_28d"          # LOWER_IS_WORSE


# =================================================================================================
# BUILDERS — one shape per modifier, so a test says only what it is about
# =================================================================================================

def base(importance_bp: int = 6000, source: str = "l1_qualified_signals") -> ImportanceBase:
    return ImportanceBase(importance_bp=importance_bp, source=source,
                          signal_id="sig_l1_1", version="alg17.v2")


def one_source() -> tuple[ConstituentSignal, ...]:
    """A single-source situation: no corroboration, so a test about a modifier measures only it."""
    return (ConstituentSignal(id="evt_1", source_system="gmail"),)


def sources(*systems: str) -> tuple[ConstituentSignal, ...]:
    return tuple(ConstituentSignal(id=f"evt_{i}", source_system=s)
                 for i, s in enumerate(systems))


def trend(confidence_bp: int = 6000, direction: str = "declining",
          metric: str = TOUCHES) -> TrendInput:
    return TrendInput(metric=metric, subject_node_id=NODE, direction=direction,
                      trend_confidence_bp=confidence_bp, point_count=8,
                      fact_version_id="fv_trend_1")


def cohort(percentile_bp: int, population_size: int, metric: str = TOUCHES) -> CohortInput:
    return CohortInput(metric=metric, subject_node_id=NODE, percentile_bp=percentile_bp,
                       population_size=population_size, cohort_id="cohort_growth_plan",
                       fact_version_id="fv_cohort_1")


def anomaly(flagged: bool = True) -> AnomalyInput:
    return AnomalyInput(metric=TOUCHES, subject_node_id=NODE, flagged=flagged, periods_used=6,
                        z_like_bp=41_000, direction="below", fact_version_id="fv_anom_1")


def blocked(count: int, node: str = NODE) -> DependencyInput:
    return DependencyInput(subject_node_id=node, blocked_count=count,
                           fact_version_id=f"fv_dep_{node}")


def conflict(resolution: str = UNRESOLVED_RESOLUTION,
             conflict_id: str = "cf_1") -> ConflictInput:
    return ConflictInput(conflict_id=conflict_id, field="contract.value",
                         signal_id="sig_l1_1", resolution=resolution)


def compose(eval_time, *, importance_bp: int = 6000, signals=None, **modifier_kwargs):
    """The composer with everything defaulted to "no input", so a test states only its subject."""
    return compose_situation_importance(
        base=base(importance_bp), signals=one_source() if signals is None else signals,
        modifiers=ModifierInputs(**modifier_kwargs), eval_time=eval_time)


# =================================================================================================
# THE PINS — four constants this module spells rather than imports, and the two doctrines
# =================================================================================================

def test_the_polarity_register_covers_exactly_the_registered_metrics() -> None:
    """**The dead-modifier guard.** Modifier 3b cannot fire on a metric whose polarity is
    unregistered, and doc 07's "risk metric" has no register anywhere else in the codebase — so
    this module declares one. A thirteenth entry in `sampler.TRENDED_METRICS` that nobody adds
    here would be a metric the cohort modifier silently ignores for ever, which is exactly how 15
    of Layer 1's 21 deep sales rules ended up dead. Both directions, so a stale entry here fails
    too."""
    from genios_engine.context.analytic.sampler import TRENDED_METRICS

    registered = {m.value for m in TRENDED_METRICS}
    assert set(METRIC_POLARITY) == registered, (
        "METRIC_POLARITY has drifted from sampler.TRENDED_METRICS — a metric with no declared "
        "polarity is a cohort modifier that never fires on it")
    assert RISK_METRICS < registered and RISK_METRICS, "risk metrics are a subset, and non-empty"
    assert METRIC_POLARITY[COLD] is MetricPolarity.HIGHER_IS_WORSE
    assert METRIC_POLARITY[TOUCHES] is MetricPolarity.LOWER_IS_WORSE


def test_the_fact_prefixes_match_the_modules_that_own_them() -> None:
    """The four field names are spelled here to keep `context/analytic/` out of this module's
    import graph. Spelled means they can drift, so they are pinned to their owners."""
    from genios_engine.context.analytic.anomaly import ANOMALY_FACT_PREFIX as OWNED_ANOMALY
    from genios_engine.context.analytic.comparator import POSITION_FACT_PREFIX
    from genios_engine.context.analytic.trend import TREND_FACT_PREFIX as OWNED_TREND
    from genios_engine.context.correlation_dependency import FIELD_BLOCKED_COUNT

    assert TREND_FACT_PREFIX == OWNED_TREND
    assert COHORT_FACT_PREFIX == POSITION_FACT_PREFIX
    assert ANOMALY_FACT_PREFIX == OWNED_ANOMALY
    assert DEPENDENCY_BLOCKED_FIELD == FIELD_BLOCKED_COUNT


def test_the_point_in_time_window_matches_the_graph_store() -> None:
    """Doc 02's acceptance row — "replaying a March decision against as_of=March reproduces its
    inputs" — is one SQL predicate wide, and this module writes its own copy of it."""
    from genios_engine.context.graph_store import _WINDOW_AT

    assert FACT_WINDOW_AT == _WINDOW_AT


def test_the_unresolved_verdict_is_one_the_database_allows() -> None:
    """Modifier 3e turns on one string out of `signal_conflicts`' closed vocabulary. If migration
    0087's check constraint ever renamed it, this modifier would read a value no row can hold and
    would be silently dead."""
    ddl = (MODULE.parents[2] / "migrations" / "0087_signal_conflicts.sql").read_text()
    assert UNRESOLVED_RESOLUTION in ddl
    assert "resolved_by_authority" in ddl and "resolved_by_recency" in ddl, (
        "the other two verdicts must still exist — 'unresolved' is only meaningful against them")


def test_layer_two_and_layer_one_agree_on_the_scale() -> None:
    """10000 bp is one scale across both layers; a second opinion here would silently rescale
    every composed number."""
    from genios_engine.capture.esqe.importance import BP_MAX as L1_BP_MAX

    assert BP_MAX == L1_BP_MAX == 10_000


def test_doctrine_two_no_float_anywhere_in_this_module() -> None:
    """Integer basis points — the source is the receipt. `float(`, `round(`, `statistics` and
    `numpy` are all absent, and so is true division, which is the one that slips in unnoticed
    because `8 / 10` typechecks exactly like `8 // 10`."""
    # Comments AND docstrings are stripped by tokenizing: this file's own prose names `round()`
    # and `float(` while explaining why they are absent, and a naive grep would fail on the
    # explanation rather than on the code.
    import io
    import tokenize

    source = MODULE.read_text()
    code = "".join(
        token.string for token in tokenize.generate_tokens(io.StringIO(source).readline)
        if token.type not in (tokenize.COMMENT, tokenize.STRING))
    for banned in ("float(", "round(", "import statistics", "import numpy", "Decimal"):
        assert banned not in code, f"{banned} in a unit that promises integer basis points"
    # TRUE DIVISION, excluding `//`. The lookaround is on the SLASHES only — tokenizing drops the
    # whitespace, so `a // b` arrives as `a//b` and a lookbehind for a non-word character would
    # never fire on real code, which is how this scan can pass while `int(x / y)` sits in the file.
    divisions = [m.start() for m in re.finditer(r"(?<!/)/(?!/)", code)]
    assert not divisions, f"true division at offsets {divisions} in the composed source"


def test_doctrine_four_no_clock_in_this_module() -> None:
    """`eval_time` is a parameter at every entry point, and neither Python nor SQL reads a clock
    here. A reader that called `now()` inside its window predicate would answer a replay of March
    with September's graph."""
    source = MODULE.read_text()
    for banned in ("datetime.now", "utcnow", "now()", "current_timestamp", "time.time"):
        assert banned not in source, f"{banned} in a unit whose whole job is replayable"


# =================================================================================================
# STEP 1 — the base is TAKEN, never recomputed
# =================================================================================================

def test_a_single_signal_at_8100_composes_from_8100_not_from_5000(eval_time) -> None:
    """Doc 07's first acceptance row. The constant is not the answer, and the record says which
    of the four sources the base came from."""
    composed = compose(eval_time, importance_bp=8100)

    assert composed.importance_bp == 8100
    assert composed.base_bp == 8100 and composed.base_source == "l1_qualified_signals"
    assert composed.base_signal_id == "sig_l1_1", "the base's receipt travels with it"
    assert composed.version == IMPORTANCE_VERSION


def test_the_composer_never_recomputes_the_base_from_the_signals(eval_time) -> None:
    """The constituent signals carry scores, and the composer must ignore them: step 1 belongs to
    `gather_l1_signals`, which applies ALG-19's state filter. Re-deriving the max here would read
    an EXPIRED signal's score, undoing that filter silently."""
    signals = (ConstituentSignal("evt_1", "gmail", importance_bp=9900),
               ConstituentSignal("evt_2", "gmail", importance_bp=200))

    composed = compose(eval_time, importance_bp=6000, signals=signals)

    assert composed.base_bp == 6000, "the passed base won, not the max of the signals"


# =================================================================================================
# STEP 2 — CORROBORATION
# =================================================================================================

def test_three_distinct_sources_add_one_thousand(eval_time) -> None:
    """Doc 07's third acceptance row: `(3 - 1) * 500`."""
    composed = compose(eval_time, signals=sources("gmail", "gcal", "drive"))

    assert composed.distinct_source_count == 3
    assert composed.corroboration_bp == 2 * CORROBORATION_PER_EXTRA_SOURCE_BP == 1_000
    assert composed.importance_bp == 7_000
    assert composed.source_systems == ("drive", "gcal", "gmail"), "the named evidence, sorted"


def test_corroboration_is_bounded_at_fifteen_hundred(eval_time) -> None:
    """Rule 11: the raise is bounded. A sixth source buys nothing."""
    composed = compose(eval_time, signals=sources("a", "b", "c", "d", "e", "f"))

    assert composed.corroboration_bp == CORROBORATION_CAP_BP


def test_one_source_repeated_is_not_corroboration(eval_time) -> None:
    """Forty mails in one thread are one source agreeing with itself. Counting EVENTS here would
    let a busy thread buy the whole cap without a second opinion existing."""
    composed = compose(eval_time, signals=sources("gmail", "gmail", "gmail", "gmail"))

    assert composed.distinct_source_count == 1 and composed.corroboration_bp == 0


# =================================================================================================
# STEP 3a — TREND
# =================================================================================================

def test_a_confident_decline_adds_a_thousand_and_names_the_trend(eval_time) -> None:
    composed = compose(eval_time, trends=(trend(confidence_bp=6000),))
    term = composed.term(ModifierName.TREND)

    assert composed.importance_bp == 6_000 + TREND_BP
    assert term.fired and term.delta_bp == TREND_BP and term.reason is ModifierReason.FIRED
    assert term.evidence["metric"] == TOUCHES
    assert term.evidence["fact_version_id"] == "fv_trend_1", "which trend — by primary key"
    assert term.evidence["trend_confidence_bp"] == 6000
    assert term.evidence["floor_bp"] == MIN_TREND_CONFIDENCE_BP


def test_a_decline_at_four_thousand_confidence_adds_nothing(eval_time) -> None:
    """Doc 07's fourth acceptance row, and the failure mode it mitigates: "noise amplified into
    importance". The REASON is stored, so a reader can see it was one threshold short rather than
    absent — those are different facts about the same situation."""
    composed = compose(eval_time, trends=(trend(confidence_bp=4000),))
    term = composed.term(ModifierName.TREND)

    assert composed.importance_bp == 6_000
    assert not term.fired and term.delta_bp == 0
    assert term.reason is ModifierReason.TREND_CONFIDENCE_BELOW_FLOOR
    assert term.evidence["trend_confidence_bp"] == 4000
    assert term.evidence["floor_bp"] == MIN_TREND_CONFIDENCE_BP


def test_a_rising_trend_is_not_a_reason_to_worry(eval_time) -> None:
    composed = compose(eval_time, trends=(trend(direction="rising"),))
    term = composed.term(ModifierName.TREND)

    assert not term.fired and term.reason is ModifierReason.TREND_NOT_DECLINING


def test_a_refusal_direction_never_fires_the_trend_modifier(eval_time) -> None:
    """`INSUFFICIENT_HISTORY` and `INSUFFICIENT_COVERAGE` are first-class RETURN VALUES of the
    trend computer, written into `graph_facts` like any other verdict. "We cannot see enough of
    this" must never be read as a decline."""
    for refusal in ("insufficient_history", "insufficient_coverage", "flat"):
        composed = compose(eval_time, trends=(trend(direction=refusal),))
        assert not composed.term(ModifierName.TREND).fired, refusal


def test_two_declines_are_still_one_modifier(eval_time) -> None:
    """+1000 is the TREND modifier, not a per-metric bounty; the strongest is the receipt and the
    rest are counted. Otherwise a node with six trended metrics out-earns a critical signal."""
    composed = compose(eval_time, trends=(trend(confidence_bp=5200, metric=TOUCHES),
                                          trend(confidence_bp=7100, metric=COLD)))
    term = composed.term(ModifierName.TREND)

    assert term.delta_bp == TREND_BP
    assert term.evidence["metric"] == COLD, "the most confident one is named"
    assert term.evidence["qualifying_count"] == 2


def test_the_trend_floor_is_reachable_by_the_real_trend_computer(
    eval_time, declining_series,
) -> None:
    """**THE MEETABILITY RECEIPT.** A threshold nobody's data can meet is a dead modifier that
    looks rigorous — Layer 1 shipped fifteen of those. So the floor is checked against the REAL
    producer: a clean, fully-covered declining series (the same one H2 uses) must clear 5000, and
    the same series with three gaps must not — that is the distinction the floor is for."""
    from genios_engine.contracts.analytic import MetricUnit, MetricPoint
    from genios_engine.context.analytic.trend import compute_trend

    def points(series):
        return [MetricPoint(subject_node_id=p.subject_node_id, metric=p.metric,
                            value_bp=p.value_bp, unit=MetricUnit.COUNT, observed_at=p.observed_at,
                            known=p.known) for p in series]

    clean = compute_trend(points(declining_series()))
    assert clean.direction.value == "declining"
    assert clean.trend_confidence_bp >= MIN_TREND_CONFIDENCE_BP, (
        f"a six-point full-coverage monotonic decline scores {clean.trend_confidence_bp} and the "
        f"floor is {MIN_TREND_CONFIDENCE_BP} — modifier 3a would be dead on real data")

    composed = compose(eval_time, trends=(TrendInput(
        metric=TOUCHES, subject_node_id=NODE, direction=clean.direction.value,
        trend_confidence_bp=clean.trend_confidence_bp, point_count=clean.point_count),))
    assert composed.term(ModifierName.TREND).fired

    gappy = compute_trend(points(declining_series(gaps=(0, 1, 2))))
    assert gappy.trend_confidence_bp < MIN_TREND_CONFIDENCE_BP


# =================================================================================================
# STEP 3b — COHORT POSITION, and the narrowed band scheme
# =================================================================================================

@pytest.mark.parametrize("population", [5, 6, 7, 8, 9, 10, 11, 12])
def test_the_worst_member_of_any_legal_cohort_fires_the_modifier(eval_time, population) -> None:
    """**THE DECISION D8 FORCED, pinned across the whole narrowing range.**

    Nearest rank cannot express a decile below n=11, so `CohortPosition` publishes QUARTILES on
    small cohorts and the worst member of a five-member cohort is `Q1`, not `D1`. A modifier that
    tested `band is CohortBand.D1` would therefore never fire on a small cohort — and the sweep
    publishes the SMALLEST population by design, so that is most cohorts. "Bottom decile" is read
    as the worst band the population can EXPRESS, and the record says which scheme applied so the
    claim is never stronger than the arithmetic behind it.

    Built through the real `position_from_values`, so this asserts against the percentile the
    production path actually produces rather than one this test made up.
    """
    from genios_engine.context.analytic.cohort import position_from_values

    values = {f"peer_{i}": 10 * (i + 1) for i in range(population)}
    values["peer_0"] = 1                      # the worst reading on a LOWER_IS_WORSE metric
    position = position_from_values(metric=TOUCHES, cohort_id="c", values=values,
                                    subject_node_id="peer_0", eval_time=eval_time)

    composed = compose(eval_time, cohort_positions=(cohort(position.percentile_bp, population),))
    term = composed.term(ModifierName.COHORT_POSITION)

    assert term.fired and term.delta_bp == COHORT_BP, (
        f"the worst member of a {population}-member cohort sits at "
        f"{position.percentile_bp} bp / band {position.band.value} and fired nothing")
    expected = worst_band(MetricPolarity.LOWER_IS_WORSE,
                          divisions=10 if population > 10 else 4)
    assert term.evidence["band"] == position.band.value == expected.value, (
        "the band the population can express, and the one the modifier tested for")
    assert term.evidence["divisions"] == expected.divisions
    assert term.evidence["population_size"] == population
    assert term.evidence["polarity"] == MetricPolarity.LOWER_IS_WORSE.value


def test_a_middling_position_fires_nothing(eval_time) -> None:
    composed = compose(eval_time, cohort_positions=(cohort(5_000, 40),))
    term = composed.term(ModifierName.COHORT_POSITION)

    assert not term.fired and term.reason is ModifierReason.COHORT_NOT_AT_WORST_EXTREME
    assert term.evidence["bands"] == ["D6"], "what it actually was, not just that it was not D1"


def test_the_top_of_a_risk_metric_is_the_bad_end(eval_time) -> None:
    """Doc 07's second cohort line. On `engagement.days_since_contact` a HIGH reading is the bad
    reading — the account nobody has spoken to — so the top band fires and the bottom does not."""
    top = compose(eval_time, cohort_positions=(cohort(9_800, 40, metric=COLD),))
    bottom = compose(eval_time, cohort_positions=(cohort(200, 40, metric=COLD),))

    assert top.term(ModifierName.COHORT_POSITION).fired
    assert top.term(ModifierName.COHORT_POSITION).evidence["risk_metric"] is True
    assert not bottom.term(ModifierName.COHORT_POSITION).fired


def test_the_top_of_an_engagement_metric_is_the_good_end(eval_time) -> None:
    """The converse, and the reason the register exists: the most-engaged account in the cohort
    must not be raised for it. A polarity-free "extreme band" rule would do exactly that."""
    composed = compose(eval_time, cohort_positions=(cohort(9_900, 40, metric=TOUCHES),))

    assert not composed.term(ModifierName.COHORT_POSITION).fired


def test_a_cohort_of_four_is_refused_not_scored(eval_time) -> None:
    """Doc 07's mitigation ("modifier 3b requires population >= 5") and contract law V-2. Below
    five, "bottom decile" is a ranking of individuals wearing a distribution's clothes."""
    composed = compose(eval_time, cohort_positions=(cohort(2_000, 4),))
    term = composed.term(ModifierName.COHORT_POSITION)

    assert not term.fired and term.reason is ModifierReason.COHORT_POPULATION_BELOW_FLOOR
    assert term.evidence["population_size"] == 4 and term.evidence["floor"] == 5


def test_the_population_floor_holds_at_the_helper_too_not_only_at_its_caller() -> None:
    """THE SAME FLOOR, PINNED AT ITS SECOND SITE — found by mutation, not by reading.

    `_cohort_term` filters on `MIN_COHORT_POPULATION` before it calls `_qualifying_cohorts`, and
    `_qualifying_cohorts` checks it again. Deleting the SECOND check changed no behaviour and
    broke no test, which is the signature of a guard that has quietly become unreachable: the
    line reads as protection, a reviewer counts it as protection, and it protects nothing. The
    next caller of the helper — a per-metric render, a debug route, a second modifier that wants
    the same "at the bad extreme" set — inherits a floor that was never proven to work.

    So the helper is driven DIRECTLY here. Doc 07's mitigation is that modifier 3b requires
    `population >= 5`, and contract law V-2 says the same thing: below five, a percentile is a
    ranking of named individuals wearing a distribution's clothes, and publishing a band for it
    discloses where four identifiable peers sit. That is a property of the ANSWER, not of the one
    function that happens to ask for it today.
    """
    from genios_engine.context.importance import _qualifying_cohorts
    from genios_engine.contracts.analytic import MIN_COHORT_POPULATION

    # Worst-extreme positions in every respect but size: a registered LOWER_IS_WORSE metric at the
    # bottom of its cohort. Only the population separates them.
    below = tuple(cohort(200, n) for n in range(1, MIN_COHORT_POPULATION))
    at_floor = cohort(200, MIN_COHORT_POPULATION)

    assert _qualifying_cohorts(below) == (), (
        "a cohort under the five-member floor qualified at the helper — the caller's filter is "
        "the only thing standing between a four-peer 'cohort' and a published band")
    assert _qualifying_cohorts((at_floor,)) == (at_floor,), (
        "the floor is INCLUSIVE at five; a helper that refused the floor itself would delete "
        "the smallest legal cohort, which is most cohorts (`most_specific` publishes the "
        "smallest population by design)")


def test_an_unregistered_metric_says_so_rather_than_going_quiet(eval_time) -> None:
    unregistered = cohort(100, 40, metric="marketing.mql_count")
    composed = compose(eval_time, cohort_positions=(unregistered,))
    term = composed.term(ModifierName.COHORT_POSITION)

    assert not term.fired and term.reason is ModifierReason.COHORT_POLARITY_UNKNOWN


def test_a_stored_decile_on_a_small_cohort_cannot_smuggle_a_claim_through(eval_time) -> None:
    """The band is RECOMPUTED from the percentile and the population, never trusted. A row written
    before V-8 landed can carry `D1` on a cohort of six — arithmetic that population could not
    produce — and reading it would republish the overclaim D8 was fixed to delete."""
    composed = compose(eval_time, cohort_positions=(
        CohortInput(metric=TOUCHES, subject_node_id=NODE, percentile_bp=1_600,
                    population_size=6, cohort_id="c", band="D1"),))
    term = composed.term(ModifierName.COHORT_POSITION)

    assert term.fired, "1600 bp is the bottom quartile of six, which IS the worst expressible band"
    assert term.evidence["band"] == "Q1", "recomputed; the stored D1 was unreachable at n=6"


def test_no_component_ever_carries_a_cohort_distribution(eval_time) -> None:
    """**Defect D1's guard, one layer up.** `CohortPosition` stores raw p25/p50/p75 and every
    sanctioned exit gates them through `comparator.publishable_distribution`, because an order
    statistic over a small population discloses named peers' exact readings. The component record
    is a fourth exit unless it refuses to carry them."""
    composed = compose(eval_time, cohort_positions=(cohort(200, 40),))
    body = json.dumps(composed.as_record())

    for leak in ("p25_bp", "p50_bp", "p75_bp", "distribution"):
        assert leak not in body, f"{leak} reached a stored component record"


# =================================================================================================
# STEP 3c/3d/3e/3f — the other four
# =================================================================================================

def test_a_flagged_anomaly_adds_eight_hundred(eval_time) -> None:
    composed = compose(eval_time, anomalies=(anomaly(),))
    term = composed.term(ModifierName.ANOMALY)

    assert composed.importance_bp == 6_000 + ANOMALY_BP
    assert term.evidence["z_like_bp"] == 41_000 and term.evidence["periods_used"] == 6


def test_an_unflagged_anomaly_row_adds_nothing(eval_time) -> None:
    """The detector writes its NEGATIVE verdicts as facts too, so that a node which returned to
    normal has its old flag retracted. Reading the row's presence rather than its `flagged` would
    raise every node the detector has ever looked at."""
    composed = compose(eval_time, anomalies=(anomaly(flagged=False),))

    assert composed.term(ModifierName.ANOMALY).reason is ModifierReason.ANOMALY_NOT_FLAGGED


def test_the_anomaly_conjunction_is_reachable_on_a_real_series(eval_time) -> None:
    """Meetability again — modifier 3c inherits the detector's own two-condition flag (z_like >
    30000 AND deviation > 2000). Six flat months and a collapse must clear both."""
    from genios_engine.contracts.analytic import MetricUnit, MetricPoint
    from genios_engine.context.analytic.anomaly import detect_anomaly

    values = (40, 41, 39, 40, 42, 40, 3)          # oldest period first; the last one is today's
    series = [MetricPoint(subject_node_id=NODE, metric=TOUCHES, value_bp=v,
                          unit=MetricUnit.COUNT,
                          observed_at=eval_time - timedelta(days=30 * (len(values) - 1 - i)),
                          known=True)
              for i, v in enumerate(values)]
    verdict = detect_anomaly(series)

    assert verdict.flagged, "the detector's own conjunction did not fire on a 40 -> 3 collapse"
    composed = compose(eval_time, anomalies=(AnomalyInput(
        metric=TOUCHES, subject_node_id=NODE, flagged=verdict.flagged,
        periods_used=verdict.periods_used, z_like_bp=verdict.z_like_bp),))
    assert composed.term(ModifierName.ANOMALY).fired


@pytest.mark.parametrize("count,expected", [(1, 200), (3, 600), (5, 1_000), (9, 1_000)])
def test_blocked_work_is_priced_per_item_and_capped_at_five(eval_time, count, expected) -> None:
    composed = compose(eval_time, dependencies=(blocked(count),))
    term = composed.term(ModifierName.DEPENDENCY)

    assert term.delta_bp == expected == DEPENDENCY_PER_BLOCKED_BP * min(count,
                                                                       DEPENDENCY_MAX_BLOCKED)
    assert term.evidence["blocked_count"] == count and term.evidence["counted"] == min(count, 5)


def test_blocked_counts_across_a_situation_are_maxed_not_summed(eval_time) -> None:
    """`derived.py` writes `deal.*` onto the company node AND the deal node, so one blocked item
    routinely waits on two of a situation's own subjects. Summing would let node duplication buy
    +400 for one piece of blocked work and let a company with three deal nodes reach the ceiling
    with two real blockers."""
    composed = compose(eval_time, dependencies=(blocked(2, "node_company"),
                                                blocked(3, "node_deal")))
    term = composed.term(ModifierName.DEPENDENCY)

    assert term.delta_bp == 3 * DEPENDENCY_PER_BLOCKED_BP, "max(2, 3), never 2 + 3"
    assert term.evidence["subject_node_id"] == "node_deal"


def test_a_zero_blocked_count_is_a_measured_absence(eval_time) -> None:
    """The dependency sweep writes `{"count": 0}` when a chain resolves. Fired-at-0 and never-fired
    are different facts, and this is the row that proves the record can tell them apart."""
    composed = compose(eval_time, dependencies=(blocked(0),))
    term = composed.term(ModifierName.DEPENDENCY)

    assert not term.fired and term.reason is ModifierReason.DEPENDENCY_NOTHING_BLOCKED
    assert compose(eval_time).term(ModifierName.DEPENDENCY).reason is ModifierReason.NO_INPUT


def test_an_unresolved_conflict_adds_seven_hundred_and_names_it(eval_time) -> None:
    composed = compose(eval_time, conflicts=(conflict(),))
    term = composed.term(ModifierName.CONFLICT)

    assert composed.importance_bp == 6_000 + CONFLICT_BP
    assert term.evidence["conflict_ids"] == ["cf_1"] and term.evidence["fields"] == \
        ["contract.value"]


def test_a_settled_disagreement_is_not_a_reason_to_raise(eval_time) -> None:
    """`resolved_by_authority` and `resolved_by_recency` HAVE an answer. Raising importance for a
    disagreement we already settled charges the customer for our own resolution logic."""
    for settled in ("resolved_by_authority", "resolved_by_recency"):
        composed = compose(eval_time, conflicts=(conflict(resolution=settled),))
        term = composed.term(ModifierName.CONFLICT)
        assert not term.fired and term.reason is ModifierReason.CONFLICT_NONE_MATERIAL, settled


def test_evidence_older_than_ninety_days_discounts_the_situation(eval_time) -> None:
    composed = compose(eval_time,
                       newest_evidence_at=eval_time - timedelta(days=STALENESS_DAYS + 1))
    term = composed.term(ModifierName.STALENESS)

    assert composed.importance_bp == 6_000 + STALENESS_BP == 4_500
    assert term.fired and term.delta_bp == STALENESS_BP
    assert term.evidence["measured_on"] == "situation"


def test_evidence_inside_the_window_does_not(eval_time) -> None:
    composed = compose(eval_time,
                       newest_evidence_at=eval_time - timedelta(days=STALENESS_DAYS - 1))

    assert composed.importance_bp == 6_000
    assert composed.term(ModifierName.STALENESS).reason is ModifierReason.STALENESS_WITHIN_WINDOW


def test_undated_evidence_is_not_stale(eval_time) -> None:
    """Absence of a date is not evidence of age. Discounting an undated situation would penalise
    the tenant for a capture gap, which is the "absence read as negative evidence" this codebase
    refuses everywhere."""
    term = compose(eval_time, newest_evidence_at=None).term(ModifierName.STALENESS)

    assert not term.fired and term.reason is ModifierReason.STALENESS_UNDATED


def test_the_staleness_record_stores_the_date_and_never_the_age(eval_time) -> None:
    """**The 995 MB guard.** The component record reaches `BusinessSituationObject.metadata`,
    which is hashed into the expertise package's content address. An age in days changes on every
    sweep, so storing one would mint a fresh ~238 kB package row per stale situation per sweep —
    the exact mechanism that took a tenant's database read-only. The date is stable; the age is a
    subtraction the reader can do."""
    stale = eval_time - timedelta(days=200)
    today = compose(eval_time, newest_evidence_at=stale).as_record()
    tomorrow = compose_situation_importance(
        base=base(), signals=one_source(),
        modifiers=ModifierInputs(newest_evidence_at=stale),
        eval_time=eval_time + timedelta(days=1)).as_record()

    assert today == tomorrow, "the record moved without the situation moving"
    assert "age_days" not in json.dumps(today) and "eval_time" not in json.dumps(today)


# =================================================================================================
# STEPS 3 (cap), 4 (coverage) and 5 (clamp)
# =================================================================================================

def test_the_five_positive_modifiers_are_capped_at_four_thousand(eval_time) -> None:
    """Doc 07's mitigation for "modifiers dominate the base": they sum to 4500 when all five fire,
    so the cap bites and the amount it took is STORED — a reader must be able to see that the
    situation had more evidence than the number shows."""
    composed = compose(eval_time, trends=(trend(),), cohort_positions=(cohort(200, 40),),
                       anomalies=(anomaly(),), dependencies=(blocked(5),),
                       conflicts=(conflict(),))

    raw = TREND_BP + COHORT_BP + ANOMALY_BP + 5 * DEPENDENCY_PER_BLOCKED_BP + CONFLICT_BP
    assert raw == 4_500 > MODIFIER_CAP_BP
    assert composed.modifier_total_bp == MODIFIER_CAP_BP
    assert composed.modifier_cap_removed_bp == raw - MODIFIER_CAP_BP == 500
    assert composed.importance_bp == 6_000 + MODIFIER_CAP_BP
    assert all(t.fired for t in composed.modifiers if t.name is not ModifierName.STALENESS)


def test_the_staleness_discount_is_outside_the_cap(eval_time) -> None:
    """Capping the negative term with the positives would mean a situation that fired four
    modifiers got LESS of a staleness discount than one that fired none — the discount would be
    spent on the cap. A discount for three months of silence is not negotiable."""
    composed = compose(eval_time, trends=(trend(),), cohort_positions=(cohort(200, 40),),
                       anomalies=(anomaly(),), dependencies=(blocked(5),),
                       conflicts=(conflict(),),
                       newest_evidence_at=eval_time - timedelta(days=400))

    assert composed.modifier_total_bp == MODIFIER_CAP_BP + STALENESS_BP == 2_500


def test_missing_coverage_is_an_honest_eighty_percent(eval_time) -> None:
    """Doc 07's fifth acceptance row. "We are less sure this matters, because we cannot see all
    of it" — and the penalty is stored as a term so it is visible rather than inferable."""
    covered = compose(eval_time, trends=(trend(),), coverage_ready=True)
    uncovered = compose(eval_time, trends=(trend(),), coverage_ready=False,
                        coverage_domain="sales")

    assert covered.importance_bp == 7_000
    assert uncovered.importance_bp == 7_000 * 8 // 10 == 5_600
    assert uncovered.coverage_penalty_bp == -1_400 and uncovered.coverage_domain == "sales"
    assert covered.coverage_penalty_bp == 0


def test_unknown_coverage_does_not_discount(eval_time) -> None:
    """TRI-STATE, like `coverage_ready` on the signal contract and on `MetricPoint`. `None` means
    no coverage row for this domain — the coverage pass has not run — and discounting for that
    would report a gap we have not measured."""
    assert compose(eval_time, coverage_ready=None).importance_bp == 6_000
    assert compose(eval_time, coverage_ready=None).coverage_penalty_bp == 0


def test_the_clamp_bites_at_ten_thousand_and_says_so(eval_time) -> None:
    composed = compose(eval_time, importance_bp=9_800, trends=(trend(),),
                       signals=sources("gmail", "gcal", "drive"))

    assert composed.subtotal_bp == 9_800 + 1_000 + 1_000 == 11_800
    assert composed.importance_bp == BP_MAX
    assert composed.clamp_delta_bp == -1_800


def test_the_clamp_holds_at_zero(eval_time) -> None:
    composed = compose(eval_time, importance_bp=500,
                       newest_evidence_at=eval_time - timedelta(days=400))

    assert composed.subtotal_bp == -1_000 and composed.importance_bp == 0
    assert composed.clamp_delta_bp == 1_000


# =================================================================================================
# STEP 6 — THE COMPONENT RECORD
# =================================================================================================

def test_every_modifier_is_recorded_whether_or_not_it_fired(eval_time) -> None:
    """The gate measures `importance_components` populated at 100%, and "populated" has to mean
    all six terms: a `{name: delta}` dict of the ones that fired cannot distinguish "no trend on
    this subject" from "a decline we were not confident enough in", and both are answers a reader
    needs to "why is this only a 6200"."""
    composed = compose(eval_time, trends=(trend(confidence_bp=4_000),))

    assert [t.name for t in composed.modifiers] == list(ModifierName)
    assert {t.name.value for t in composed.modifiers} == {m.value for m in ModifierName}
    unfired = [t for t in composed.modifiers if not t.fired]
    assert len(unfired) == 6 and all(t.reason is not ModifierReason.FIRED for t in unfired)


def test_the_stored_record_reproduces_the_arithmetic_with_no_recomputation(eval_time) -> None:
    """**"Why is this a 7400?" answered from STORED DATA.** The record is read back out of JSON —
    nothing from the live objects — and the whole sum is re-derived from it. If a term were
    missing from `as_record`, the identity below could not close."""
    composed = compose(eval_time, importance_bp=7_000, signals=sources("gmail", "gcal"),
                       trends=(trend(),), dependencies=(blocked(2),),
                       newest_evidence_at=eval_time - timedelta(days=120),
                       coverage_ready=False, coverage_domain="sales")
    stored = json.loads(json.dumps(composed.as_record()))

    deltas = sum(t["delta_bp"] for t in stored["modifiers"])
    subtotal = (stored["base_bp"] + stored["corroboration_bp"] + deltas
                - stored["modifier_cap_removed_bp"])
    assert subtotal == stored["subtotal_bp"]
    assert subtotal + stored["coverage_penalty_bp"] + stored["clamp_delta_bp"] == \
        stored["importance_bp"]
    assert stored["importance_bp"] == composed.importance_bp


def test_the_record_survives_a_round_trip_through_json(eval_time) -> None:
    """It is stored as JSONB — `situations.importance_components` and the BSO's metadata — so a
    field that cannot serialise is a field that silently disappears from the explanation."""
    composed = compose(eval_time, trends=(trend(),), cohort_positions=(cohort(200, 40),),
                       anomalies=(anomaly(),), dependencies=(blocked(3),),
                       conflicts=(conflict(),), coverage_ready=False, coverage_domain="sales",
                       newest_evidence_at=eval_time - timedelta(days=10))

    assert ComposedImportance.from_record(
        json.loads(json.dumps(composed.as_record()))) == composed


def test_identical_inputs_compose_byte_identically(eval_time) -> None:
    """Doc 07's determinism row. Two runs, one JSON string — the property that lets a composed
    importance be content-addressed at all."""
    kwargs = dict(trends=(trend(),), dependencies=(blocked(4),),
                  newest_evidence_at=eval_time - timedelta(days=5))

    first = json.dumps(compose(eval_time, **kwargs).as_record(), sort_keys=True)
    second = json.dumps(compose(eval_time, **kwargs).as_record(), sort_keys=True)
    assert first == second


def test_the_record_names_the_version_that_produced_it(eval_time) -> None:
    """Doc 07's failure-mode row: after a weight moves, a historical importance is not comparable
    to a new one, and without the version on the row nobody can tell which formula made which."""
    assert compose(eval_time).as_record()["version"] == IMPORTANCE_VERSION


def test_the_fired_comparisons_are_what_the_sixth_confidence_axis_reads(eval_time) -> None:
    """L2.5.1's analytic axis is documented as reading "the comparisons an importance number
    LEANED ON — the ones whose modifiers actually fired, not every trend the org holds", and
    nothing produced that set until `leaned_on`. Handed straight to the real `score_situation`, so
    a renamed field on either side fails here rather than in production."""
    from genios_engine.context.situations import coverage_is_known, score_situation

    inputs = ModifierInputs(trends=(trend(confidence_bp=6_000), trend(confidence_bp=4_000)),
                            cohort_positions=(cohort(200, 40),),
                            anomalies=(anomaly(flagged=False),))
    composed = compose_situation_importance(base=base(), signals=one_source(), modifiers=inputs,
                                            eval_time=eval_time)
    leaned = composed.leaned_on(inputs)

    assert len(leaned["trends"]) == 1, "the 4000-confidence trend moved nothing and is not cited"
    assert len(leaned["cohort_positions"]) == 1
    assert leaned["anomalies"] == (), "an unflagged verdict was not leaned on"

    confidence = score_situation(
        event_count=4, source_count=2, last_seen_at=eval_time, open_discrepancies=0,
        open_merge_proposals=0, present_fields=set(), expected_fields={}, now=eval_time,
        trends=leaned["trends"], cohort_positions=leaned["cohort_positions"],
        anomalies=leaned["anomalies"])
    assert coverage_is_known(confidence.analytic), (
        "the axis read nothing off the inputs the importance leaned on — the field names have "
        "drifted between the two modules")


# =================================================================================================
# THE SUPPLY GUARD — doc 07 hard rule 7
# =================================================================================================

def test_a_flat_supply_suppresses_the_modifiers_rather_than_faking_a_spread(eval_time) -> None:
    """"A fake distribution is worse than a flat one, because it looks like it works." The base
    passes through, every term is recorded as SUPPRESSED, and the record says so — so a reader of
    a flat month can tell it from a month where nothing happened to fire."""
    composed = compose_situation_importance(
        base=base(FLAT_BASE_BP), signals=sources("gmail", "gcal", "drive"),
        modifiers=ModifierInputs(trends=(trend(),), dependencies=(blocked(5),)),
        eval_time=eval_time, l1_active=False)

    assert composed.importance_bp == FLAT_BASE_BP
    assert composed.corroboration_bp == 0 and composed.modifier_total_bp == 0
    assert composed.l1_importance_not_active is True
    assert all(t.reason is ModifierReason.SUPPRESSED for t in composed.modifiers)
    assert len(composed.modifiers) == len(ModifierName), "a suppressed record is still complete"


def test_the_guard_measures_the_supply_and_not_one_situation(caplog) -> None:
    """Over 90% at exactly 5000 is the trip wire, it is measured on the org's own output, and it
    LOGS — doc 07 asks for loud, because a silent flat month is indistinguishable from a broken
    scorer."""
    flat = assess_l1_supply([FLAT_BASE_BP] * 95 + [6100, 4200, 3300, 7700, 8800])
    assert flat.flat_share_bp == 9_500 and not flat.active

    with caplog.at_level("WARNING"):
        assess_l1_supply([FLAT_BASE_BP] * 95 + [6100, 4200, 3300, 7700, 8800])
    assert "L1_IMPORTANCE_NOT_ACTIVE" in caplog.text

    healthy = assess_l1_supply([FLAT_BASE_BP] * 8 + [6100, 4200] * 46)
    assert healthy.active and healthy.flat_share_bp < 9_000


def test_an_empty_supply_is_unknown_and_not_flat() -> None:
    """A tenant with no scored signals has published no evidence that the scorer is broken.
    Suppressing there would leave a pre-L1-v2 tenant with no ranking at all, while the L2 facts
    that could rank it — a declining trend, five blocked items — sit unread in the graph."""
    supply = assess_l1_supply([None, None])

    assert supply.active and supply.scored_count == 0 and supply.flat_share_bp == 0


# =================================================================================================
# THE MAX-NOT-MEAN PAIR, composed
# =================================================================================================

def test_one_critical_and_four_routine_signals_stay_critical(eval_time) -> None:
    """Doc 07's second acceptance row, at this unit's seam. `gather_l1_signals` hands over the max
    (9000); the composer must not dilute it. The mean of the same five is 4200, so a composer that
    averaged anywhere would be visible here — and burying a critical signal under four routine
    ones is the exact "small critical things get buried" failure Globe names at L4."""
    signals = sources("gmail", "gcal")
    composed = compose_situation_importance(
        base=base(9_000), signals=signals, modifiers=ModifierInputs(coverage_ready=True),
        eval_time=eval_time)

    assert composed.importance_bp >= 9_000
    assert composed.importance_bp != (9_000 + 3_000 * 4) // 5 == 4_200


# =================================================================================================
# THE READERS — real Postgres, because a bulk read is SQL and SQL is not tested by mocking it
# =================================================================================================
#
# Every test below writes its own org and drops it in `finally`. The rows these readers consume
# (`graph_facts` windows, a jsonb refusal body, a resolved conflict, a missing coverage row) are
# the ones a unit test with a hand-built bundle cannot reach — and they are where a modifier
# goes quietly dead in production while the composer's own suite stays green.

READER_ORG = "org_l2_importance_readers"

_TREND_BODY = {"metric": TOUCHES, "direction": "declining", "trend_confidence_bp": 6400,
               "point_count": 9, "coverage_ratio_bp": 10_000}
_COHORT_BODY = {"metric": TOUCHES, "cohort_id": "cohort_growth", "percentile_bp": 400,
                "band": "D1", "population_size": 40, "value_bp": 2,
                # The three the reader must NOT carry forward — see `CohortInput`.
                "p25_bp": 11, "p50_bp": 19, "p75_bp": 30}
_ANOMALY_BODY = {"metric": TOUCHES, "flagged": True, "z_like_bp": 44_000, "direction": "below",
                 "periods_used": 6, "refusal": None}


def _fact(conn, org, node, field_name, value, *, version_id, valid_from, valid_to=None,
          status="active"):
    from sqlalchemy import text as sql

    conn.execute(sql(
        "insert into graph_facts (fact_version_id, fact_id, org_id, subject_node_id, field, "
        " value, value_type, status, valid_from, valid_to) "
        "values (:v, :f, :o, :n, :fl, cast(:val as jsonb), 'derived', :st, :vf, :vt)"),
        {"v": version_id, "f": f"fact_{version_id}", "o": org, "n": node, "fl": field_name,
         "val": json.dumps(value), "st": status, "vf": valid_from, "vt": valid_to})


def _drop_reader_org(engine, org: str) -> None:
    from sqlalchemy import text as sql

    with engine.begin() as conn:
        for table in ("graph_facts", "signal_conflicts", "source_coverage",
                      "context_correlation_members", "source_events"):
            conn.execute(sql(f"delete from {table} where org_id = :o"), {"o": org})
        conn.execute(sql("delete from orgs where id = :o"), {"o": org})


def _seed_reader_org(engine, org: str) -> None:
    from sqlalchemy import text as sql

    with engine.begin() as conn:
        conn.execute(sql("insert into orgs (id, name) values (:o, 'importance readers') "
                         "on conflict (id) do nothing"), {"o": org})


@pytest.mark.pg
def test_the_readers_assemble_a_situation_bundle_from_real_rows(pg_store, eval_time) -> None:
    """**THE TEST THAT MATTERS for step 3's plumbing.** Four fact families, a conflict, a coverage
    row and two source systems — read the way the sweep reads them — and composed. Nothing above
    this line would notice if a `field like` pattern or a jsonb key were misspelled, because every
    other test builds its bundle by hand."""
    from sqlalchemy import text as sql

    from genios_engine.context.importance import (SituationRef, load_modifier_inputs,
                                                  read_constituent_signals)

    org, before = READER_ORG, eval_time - timedelta(days=30)
    _seed_reader_org(pg_store.engine, org)
    try:
        with pg_store.engine.begin() as conn:
            _fact(conn, org, "node_company", f"{TREND_FACT_PREFIX}{TOUCHES}", _TREND_BODY,
                  version_id="fv_t1", valid_from=before)
            _fact(conn, org, "node_company", f"{COHORT_FACT_PREFIX}{TOUCHES}", _COHORT_BODY,
                  version_id="fv_c1", valid_from=before)
            _fact(conn, org, "node_deal", f"{ANOMALY_FACT_PREFIX}{TOUCHES}", _ANOMALY_BODY,
                  version_id="fv_a1", valid_from=before)
            _fact(conn, org, "node_deal", DEPENDENCY_BLOCKED_FIELD, {"count": 3},
                  version_id="fv_d1", valid_from=before)
            conn.execute(sql(
                "insert into signal_conflicts (conflict_id, org_id, signal_id, field, "
                " subject_key, claims, resolution, detected_at) values "
                "(:c, :o, :s, 'contract.value', 'contract:acme', '[]'::jsonb, :r, :t)"),
                {"c": "cf_live", "o": org, "s": "sig_1", "r": UNRESOLVED_RESOLUTION,
                 "t": before})
            conn.execute(sql(
                "insert into signal_conflicts (conflict_id, org_id, signal_id, field, "
                " subject_key, claims, resolution, detected_at) values "
                "(:c, :o, :s, 'contract.date', 'contract:acme', '[]'::jsonb, "
                " 'resolved_by_authority', :t)"),
                {"c": "cf_settled", "o": org, "s": "sig_1", "t": before})
            conn.execute(sql(
                "insert into source_coverage (org_id, domain, coverage_ready) "
                "values (:o, 'sales', false)"), {"o": org})
            for event_id, source in (("evt_a", "gmail"), ("evt_b", "gmail"), ("evt_c", "gcal")):
                conn.execute(sql(
                    "insert into source_events (event_id, org_id, connection_id, source, "
                    " object_type, source_object_id, dedup_key, actor, occurred_at) values "
                    "(:e, :o, 'conn', :s, 'email_message', :e, :e, '{}'::jsonb, :t)"),
                    {"e": event_id, "o": org, "s": source, "t": before})
                conn.execute(sql(
                    "insert into context_correlation_members (org_id, correlation_id, event_id) "
                    "values (:o, 'corr_1', :e)"), {"o": org, "e": event_id})

        ref = SituationRef(situation_id="sit_1", domain="sales",
                           subject_node_ids=("node_company", "node_deal"),
                           signal_ids=("sig_1",),
                           newest_evidence_at=eval_time - timedelta(days=200))
        with pg_store.engine.connect() as conn:
            bundles = load_modifier_inputs(conn, org, [ref], eval_time=eval_time)
            constituents = read_constituent_signals(conn, org, ["corr_1"])

        inputs = bundles["sit_1"]
        assert len(inputs.trends) == 1 and inputs.trends[0].trend_confidence_bp == 6_400
        assert inputs.trends[0].fact_version_id == "fv_t1"
        assert len(inputs.cohort_positions) == 1
        assert inputs.cohort_positions[0].population_size == 40
        assert len(inputs.anomalies) == 1 and inputs.anomalies[0].flagged
        assert [d.blocked_count for d in inputs.dependencies] == [3]
        assert [c.conflict_id for c in inputs.conflicts] == ["cf_live"], (
            "a settled disagreement was read as a live one")
        assert inputs.coverage_ready is False and inputs.coverage_domain == "sales"

        composed = compose_situation_importance(
            base=base(6_000), signals=constituents["corr_1"], modifiers=inputs,
            eval_time=eval_time)

        # trend +1000, cohort +1000, anomaly +800, dependency +600, conflict +700 = 4100 -> capped
        # at 4000; staleness -1500; corroboration +500 for the second source; then 80% coverage.
        assert composed.distinct_source_count == 2, "gmail twice is one source, gcal is the second"
        assert composed.modifier_cap_removed_bp == 100
        assert composed.subtotal_bp == 6_000 + 500 + (4_000 - 1_500) == 9_000
        assert composed.importance_bp == 9_000 * 8 // 10 == 7_200
        assert "p25_bp" not in json.dumps(composed.as_record())
    finally:
        _drop_reader_org(pg_store.engine, org)


@pytest.mark.pg
def test_the_fact_read_is_point_in_time(pg_store, eval_time) -> None:
    """Replayability, against real rows. A stint that closed BEFORE `eval_time` is invisible; the
    stint that was open AT `eval_time` is the answer even though a newer row exists now. A reader
    that took the latest row per (node, field) would answer March's question with September's
    cohort, which is doc 02's acceptance row failing silently."""
    from genios_engine.context.importance import read_derived_modifier_facts

    org = READER_ORG + "_asof"
    march, september = eval_time, eval_time + timedelta(days=180)
    _seed_reader_org(pg_store.engine, org)
    try:
        with pg_store.engine.begin() as conn:
            _fact(conn, org, "node_company", DEPENDENCY_BLOCKED_FIELD, {"count": 4},
                  version_id="fv_march", valid_from=march - timedelta(days=1),
                  valid_to=september, status="superseded")
            _fact(conn, org, "node_company", DEPENDENCY_BLOCKED_FIELD, {"count": 1},
                  version_id="fv_september", valid_from=september)

        with pg_store.engine.connect() as conn:
            at_march = read_derived_modifier_facts(conn, org, ["node_company"], eval_time=march)
            at_september = read_derived_modifier_facts(conn, org, ["node_company"],
                                                       eval_time=september)
            before_anything = read_derived_modifier_facts(
                conn, org, ["node_company"], eval_time=march - timedelta(days=30))

        assert [d.blocked_count for d in at_march["node_company"].dependencies] == [4]
        assert [d.blocked_count for d in at_september["node_company"].dependencies] == [1]
        assert before_anything["node_company"].dependencies == ()
    finally:
        _drop_reader_org(pg_store.engine, org)


@pytest.mark.pg
def test_a_cohort_refusal_row_is_not_read_as_a_position(pg_store, eval_time) -> None:
    """`position_fact_value` writes REFUSALS as facts too, so a shrunken cohort's old "top decile"
    is retracted rather than left standing. The body then carries `refused` and no percentile —
    and reading its presence as a position would invent a rank out of a retraction."""
    from genios_engine.context.importance import read_derived_modifier_facts

    org = READER_ORG + "_refusal"
    _seed_reader_org(pg_store.engine, org)
    try:
        with pg_store.engine.begin() as conn:
            _fact(conn, org, "node_company", f"{COHORT_FACT_PREFIX}{TOUCHES}",
                  {"metric": TOUCHES, "cohort_id": "c", "refused": "insufficient_population",
                   "population_size": 3, "detail": "3 members have a reading"},
                  version_id="fv_refused", valid_from=eval_time - timedelta(days=1))
            # A HYBRID body: `refused` set AND a percentile still present. `position_fact_value`
            # does not write one today, and the reader must still refuse it — a retraction that
            # carries a stale rank is the one shape where "read the numbers, ignore the verdict"
            # silently republishes the claim the refusal exists to withdraw.
            _fact(conn, org, "node_deal", f"{COHORT_FACT_PREFIX}{TOUCHES}",
                  {"metric": TOUCHES, "cohort_id": "c", "refused": "insufficient_coverage",
                   "percentile_bp": 200, "population_size": 40, "band": "D1"},
                  version_id="fv_hybrid", valid_from=eval_time - timedelta(days=1))
            _fact(conn, org, "node_company", f"{TREND_FACT_PREFIX}{COLD}",
                  {"metric": COLD, "direction": "insufficient_history",
                   "trend_confidence_bp": 0, "point_count": 2},
                  version_id="fv_nohistory", valid_from=eval_time - timedelta(days=1))

        with pg_store.engine.connect() as conn:
            read = read_derived_modifier_facts(conn, org, ["node_company", "node_deal"],
                                               eval_time=eval_time)
        bundle = read["node_company"]

        assert bundle.cohort_positions == (), "a refusal was read as a position"
        assert read["node_deal"].cohort_positions == (), (
            "a refusal carrying a stale percentile was read as a position")
        # The trend refusal IS carried — the composer records `not_declining` for it, which is a
        # different and more useful fact than the row never having existed.
        assert len(bundle.trends) == 1 and bundle.trends[0].direction == "insufficient_history"
        composed = compose_situation_importance(base=base(), signals=one_source(),
                                                modifiers=bundle, eval_time=eval_time)
        assert composed.modifier_total_bp == 0
    finally:
        _drop_reader_org(pg_store.engine, org)


@pytest.mark.pg
def test_a_missing_coverage_row_stays_unknown(pg_store, eval_time) -> None:
    """The tri-state, end to end. A domain with no `source_coverage` row must reach the composer as
    `None` — the coverage pass has not run — and must NOT be discounted as if we had measured a
    gap."""
    from genios_engine.context.importance import SituationRef, load_modifier_inputs

    org = READER_ORG + "_coverage"
    _seed_reader_org(pg_store.engine, org)
    try:
        with pg_store.engine.connect() as conn:
            bundles = load_modifier_inputs(
                conn, org, [SituationRef(situation_id="s", domain="sales")], eval_time=eval_time)

        assert bundles["s"].coverage_ready is None
        assert compose_situation_importance(
            base=base(6_000), signals=one_source(), modifiers=bundles["s"],
            eval_time=eval_time).importance_bp == 6_000
    finally:
        _drop_reader_org(pg_store.engine, org)


@pytest.mark.pg
def test_two_hundred_situations_cost_a_constant_number_of_queries(pg_store, eval_time) -> None:
    """**THE PERF RECEIPT, and it is not decoration.** `PERFORMANCE_HARDENING.md` records L3 doing
    ~1000 per-node reads per org, which pushed a reasoning pass past thirty minutes and blocked
    emission entirely. A modifier bundle assembled one situation at a time reproduces that exactly.
    So the statement count is asserted, not the wall clock: 200 situations over 400 nodes must cost
    the same three statements as one situation does."""
    from sqlalchemy import event
    from genios_engine.context.importance import SituationRef, load_modifier_inputs

    org = READER_ORG + "_bulk"
    _seed_reader_org(pg_store.engine, org)
    statements: list[str] = []

    def _count(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement)

    try:
        refs = [SituationRef(situation_id=f"sit_{i}", domain="sales",
                             subject_node_ids=(f"node_{i}_a", f"node_{i}_b"),
                             signal_ids=(f"sig_{i}",))
                for i in range(200)]
        with pg_store.engine.connect() as conn:
            event.listen(conn.engine, "before_cursor_execute", _count)
            try:
                bundles = load_modifier_inputs(conn, org, refs, eval_time=eval_time)
            finally:
                event.remove(conn.engine, "before_cursor_execute", _count)

        assert len(bundles) == 200
        assert len(statements) == 3, (
            f"{len(statements)} statements for 200 situations — the readers are per-situation "
            "again, which is the L3 round-trip bottleneck with a new name")
    finally:
        _drop_reader_org(pg_store.engine, org)
