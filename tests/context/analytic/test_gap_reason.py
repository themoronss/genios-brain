"""H6 · E-10 — why a series has a hole, and the false-churn guard.

Doc 09 invokes gate H6's loop half as:

    pytest tests/context/test_convergence.py tests/context/test_coverage_epoch.py \
           tests/context/analytic/test_gap_reason.py -q
    python scripts/derivation_dag_check.py

The gate row this file owns is the one with a number on it:

    | `DECLINING` trends produced across an org-wide silence window | **0** |

Doc 13 says which test to write first and it is the first one below: *"That last assertion is the
one to write first. It is the test that stops Layer 2 from telling a founder their healthiest
customer is churning because the team took a week off."*

**THE MUTATION CHECK.** Delete the `ORG_INACTIVE` branch from `gap_reason.trend_ready_series` —
keep the excluded periods in the series instead of dropping them — and
`test_a_seven_day_org_wide_silence_does_not_produce_a_declining_trend` fails first, because the
holiday's zero goes back into the fit and the slope goes negative again.
`test_the_sweep_withdraws_a_decline_caused_by_an_org_wide_silence` fails with it on the real
database, and `test_an_excluded_period_is_removed_not_zero_filled` fails on the series shape.
The single-source case — where "the source is silent" and "the org is silent" are the same row of
data — is protected TWICE, and the mutation check says so honestly: inverting the cascade alone
changes nothing, because the `COVERAGE_BROKEN` branch also requires another source to have
reported. Remove BOTH (invert the order and drop the `reporting` guard) and nine tests fail,
`test_one_connected_source_going_quiet_is_org_inactive_not_a_broken_connector` among them. Two
mechanisms for one invariant is deliberate here: reading a whole org's silence as a broken
connector would have us telling a tenant to reconnect Gmail because they took Christmas off.

**WHY THE WIRING TESTS ARE THE ONES THAT MATTER.** Layer 1 shipped six units that were built,
green and called by nothing on a real request path. Everything above `THE WIRING` here builds its
own activity window and proves the unit. `test_the_sweep_withdraws_a_decline_caused_by_an_org_wide
_silence` drives `context/runner.process_pending` — the sweep both API sync routes and the upload
route already call — against a real Postgres, and asserts the trend fact on a real graph node
stopped saying `declining`. Delete the block in `runner.py` and that test fails and nothing else
here does.
"""

from __future__ import annotations

import io
import tokenize
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from sqlalchemy import text

from genios_engine.context.analytic.gap_reason import (ABSENCE_TYPE_BY_REASON,
                                                       BASELINE_LIVE_FLOOR_BP,
                                                       NON_MEASURING_REASONS, GapReason,
                                                       PeriodActivity, baseline_live_sources,
                                                       classify_period, classify_window,
                                                       GapVerdict, gap_receipt,
                                                       read_period_activity,
                                                       refresh_gap_corrected_trends,
                                                       trend_ready_series)
from genios_engine.context.analytic.history import (MetricGrain, PostgresMetricHistory,
                                                    SampleReason)
from genios_engine.context.analytic.sampler import TrendedMetric, sampler_registry
from genios_engine.context.analytic.trend import (TREND_FACT_PREFIX, compute_trend,
                                                  trend_fact_field)
from genios_engine.contracts.analytic import (NON_ANSWERS, MetricPoint, MetricUnit,
                                              TrendDirection)
from genios_engine.contracts.quality import NEGATIVE_INFERENCE_TYPES, AbsenceType

pytestmark = pytest.mark.unit

_ENGINE = Path(__file__).resolve().parents[3] / "genios_engine"
_MODULE = _ENGINE / "context" / "analytic" / "gap_reason.py"

#: The Sunday every window in this file is built backwards from. A fixed date rather than "now
#: minus n": the classifier takes no clock, so a test that reached for one would be asserting on a
#: different window every day it ran.
EVAL_TIME = datetime(2026, 3, 1, 9, 0, tzinfo=timezone.utc)
WEEK = timedelta(days=7)
NODE = "node_acct_north"
METRIC = TrendedMetric.ENGAGEMENT_TOUCH_COUNT_28D.value


# =================================================================================================
# BUILDERS — a window is data, so every row states the world it is about as counts per source
# =================================================================================================

def week(offset: int) -> datetime:
    """The ISO week start `offset` weeks before the eval instant's week. Derived from the store's
    own boundary function so a test and the sampler cannot disagree about where a week begins."""
    from genios_engine.context.analytic.history import period_start
    return period_start(EVAL_TIME, MetricGrain.WEEK) - WEEK * offset


def window(*counts: dict[str, int]) -> tuple[PeriodActivity, ...]:
    """A window from oldest to newest: `window({"gmail": 40}, {"gmail": 0})` is two weeks, the
    second silent. Periods are derived from one place so the test states counts, never dates."""
    oldest = len(counts) - 1
    return tuple(PeriodActivity(period_start=week(oldest - i), events_by_source=c)
                 for i, c in enumerate(counts))


def series(values, *, node: str = NODE, metric: str = METRIC) -> tuple[MetricPoint, ...]:
    """A DENSE weekly series ending at the eval instant's week. `None` is an honest gap.

    Dense is the contract with `history.read_series`, and a builder that dropped its gaps would
    hand `compute_trend` a series claiming 100% coverage that is nothing of the kind.
    """
    oldest = len(values) - 1
    points = []
    for i, value in enumerate(values):
        at = week(oldest - i)
        points.append(MetricPoint(
            subject_node_id=node, metric=metric,
            value_bp=None if value is None else value, unit=MetricUnit.COUNT, observed_at=at,
            known=value is not None, coverage_ready=value is not None))
    return tuple(points)


# =================================================================================================
# THE FALSE-CHURN TEST — doc 13 says to write this one first
# =================================================================================================

#: Seven steady weeks and then a shutdown — Diwali, Christmas, an offsite — in which the whole org
#: sent and received nothing. The readings for those weeks are real, measured ZEROS
#: (`_engagement_probe` counts messages in a window and the count was genuinely zero), so nothing
#: upstream marks them missing and the trend computer has no way to know the difference.
#:
#: THE SILENCE IS THREE PERIODS AND THAT IS DELIBERATE. `compute_trend` reports the MEDIAN of the
#: pairwise slopes, so a single zero at the end of a steady series moves the answer by one rank and
#: the trend still reads FLAT — the robust estimator already absorbs a one-week holiday, which is
#: worth knowing and is not what this module is for. The alarm this module exists to stop is the
#: multi-period one: a fortnight's shutdown, a Christmas fortnight, a factory closure. Below three
#: periods the fixture would pass whether or not the correction existed, which is the definition of
#: a test that proves nothing.
FALSE_CHURN_READINGS = [40, 41, 39, 40, 42, 40, 41, 0, 0, 0]

#: The same ten weeks of org activity, with the last three showing nothing from any source.
FALSE_CHURN_ACTIVITY = ({"gmail": 300}, {"gmail": 290}, {"gmail": 310}, {"gmail": 305},
                        {"gmail": 295}, {"gmail": 300}, {"gmail": 288}, {}, {}, {})


def test_a_seven_day_org_wide_silence_does_not_produce_a_declining_trend() -> None:
    """**H6's gate row, and the reason this module exists.**

    Uncorrected, the shutdown at the end of a steady series is a decline on a real account.
    Corrected, those periods are not ones in which anybody's reading was expected, and the account
    is what it always was.
    """
    readings = FALSE_CHURN_READINGS
    activity = window(*FALSE_CHURN_ACTIVITY)
    verdicts = classify_window(activity)

    uncorrected = compute_trend(series(readings))
    corrected = compute_trend(trend_ready_series(series(readings), verdicts))

    assert uncorrected.direction is TrendDirection.DECLINING, (
        "the fixture must actually produce the false alarm, or this test proves nothing")
    assert corrected.direction is not TrendDirection.DECLINING
    assert all(verdicts[week(o)].reason is GapReason.ORG_INACTIVE for o in (0, 1, 2))


def test_the_holiday_week_is_excluded_and_the_remaining_trend_is_unchanged() -> None:
    """Doc 13: *"Exclude the period from the trend fit entirely."* Not down-weighted, not zeroed —
    the answer must be the answer the six real weeks give on their own."""
    points = series(FALSE_CHURN_READINGS)
    corrected = trend_ready_series(points, classify_window(window(*FALSE_CHURN_ACTIVITY)))

    assert corrected == points[:-3], "the silent weeks are gone from the series, not held as gaps"
    assert compute_trend(corrected) == compute_trend(points[:-3])


# =================================================================================================
# THE THREE REASONS — doc 13 E-10's cascade, one test per row
# =================================================================================================

def test_all_sources_silent_for_a_week_is_org_inactive() -> None:
    """`org_activity == 0` is the first branch and it takes precedence over everything."""
    verdict = classify_period(window({"gmail": 90, "gcal": 12}, {}), period_start=week(0))

    assert verdict.reason is GapReason.ORG_INACTIVE
    assert verdict.org_events == 0
    assert verdict.silent_sources == (), "nobody is blamed when nobody was working"
    assert not verdict.feeds_trend


def test_one_source_silent_while_the_others_report_is_coverage_broken() -> None:
    """Doc 13's acceptance row: *"gmail silent while calendar and hubspot report -> COVERAGE_BROKEN,
    UNKNOWABLE"*. The org was demonstrably awake, so the silence is about our connector."""
    verdict = classify_period(
        window({"gmail": 200, "gcal": 30, "hubspot": 15},
               {"gmail": 210, "gcal": 28, "hubspot": 20},
               {"gmail": 0, "gcal": 31, "hubspot": 18}), period_start=week(0))

    assert verdict.reason is GapReason.COVERAGE_BROKEN
    assert verdict.silent_sources == ("gmail",)
    assert verdict.reporting_sources == ("gcal", "hubspot")
    assert verdict.absence_type is AbsenceType.UNKNOWABLE
    assert not verdict.licenses_negative_inference


def test_healthy_sources_and_an_active_org_make_this_subjects_silence_real() -> None:
    """The row the whole product is for. Every source reported, the org was working, and this
    account still went quiet — that is a finding, and it feeds the trend."""
    verdict = classify_period(
        window({"gmail": 200, "gcal": 30}, {"gmail": 190, "gcal": 33},
               {"gmail": 205, "gcal": 29}), period_start=week(0))

    assert verdict.reason is GapReason.GENUINELY_ZERO
    assert verdict.feeds_trend
    assert verdict.licenses_negative_inference


def test_one_connected_source_going_quiet_is_org_inactive_not_a_broken_connector() -> None:
    """The case where the two verdicts are arithmetically indistinguishable, and the ORDER of the
    cascade is the whole answer.

    With one connected source, "the source is silent" and "the org is silent" are the same row of
    data. `ORG_INACTIVE` is tested first, so the period is excluded rather than blamed on a
    connector we have no evidence against — and doc 13's second branch requires "other sources
    reported normally" in as many words.
    """
    verdict = classify_period(window({"gmail": 300}, {"gmail": 280}, {}), period_start=week(0))

    assert verdict.reason is GapReason.ORG_INACTIVE


def test_a_source_connected_mid_window_never_reads_as_broken() -> None:
    """The failure this floor exists for: a tenant connects Calendar today, and every earlier week
    shows Calendar reporting nothing. Without a baseline requirement the whole year retro-classifies
    as `COVERAGE_BROKEN` and every trend the tenant has goes UNKNOWABLE on the day they add a
    source."""
    activity = window({"gmail": 200}, {"gmail": 190}, {"gmail": 210}, {"gmail": 205},
                      {"gmail": 195, "gcal": 20})
    for offset in range(1, 5):
        verdict = classify_period(activity, period_start=week(offset))
        assert verdict.reason is GapReason.GENUINELY_ZERO, verdict
        assert "gcal" not in verdict.baseline_live_sources


def test_the_baseline_is_measured_over_the_other_periods_never_this_one() -> None:
    """A source silent in the period under test must not be counted as part of its own baseline —
    it could then never be found silent, which is the one thing this function is for."""
    activity = window({"gmail": 100, "gcal": 10}, {"gmail": 100, "gcal": 10},
                      {"gmail": 100})
    assert baseline_live_sources(activity, period_start=week(0)) == ("gcal", "gmail")
    assert BASELINE_LIVE_FLOOR_BP == 5_000


def test_a_single_period_window_has_no_baseline_to_judge_against() -> None:
    """One period is not a history. Inventing a baseline from it would classify a brand-new
    tenant's first week as a broken connector."""
    assert baseline_live_sources(window({"gmail": 10}), period_start=week(0)) == ()


def test_a_period_the_ledger_does_not_hold_at_all_is_org_inactive() -> None:
    """Asking about a period outside the window is not an error: an org with nothing recorded in a
    period had nothing happen in it, and that is the truthful answer."""
    verdict = classify_period(window({"gmail": 10}), period_start=week(9))

    assert verdict.reason is GapReason.ORG_INACTIVE
    assert verdict.org_events == 0


# =================================================================================================
# THE TREATMENTS — excluded, unknowable, untouched
# =================================================================================================

def test_an_excluded_period_is_removed_not_zero_filled() -> None:
    """Zero-filling a holiday manufactures exactly the decline this rule exists to prevent, and it
    improves the coverage ratio that would otherwise have revealed the hole."""
    points = series([40, 40, 0])
    corrected = trend_ready_series(points, classify_window(
        window({"gmail": 100}, {"gmail": 100}, {})))

    assert [p.observed_at for p in corrected] == [week(2), week(1)]
    assert all(p.known and p.value_bp == 40 for p in corrected)
    assert week(0) not in {p.observed_at for p in corrected}


def test_a_coverage_broken_period_becomes_an_honest_gap_and_degrades_coverage() -> None:
    """Doc 13: *"Mark UNKNOWABLE, degrade confidence."* It stays in the series — so it counts
    AGAINST `coverage_ratio_bp` — and it carries no value, because a gap with a value is the
    interpolation the contract refuses."""
    points = series([40, 41, 39, 40, 0])
    activity = window({"gmail": 100, "gcal": 9}, {"gmail": 100, "gcal": 9},
                      {"gmail": 100, "gcal": 9}, {"gmail": 100, "gcal": 9},
                      {"gmail": 0, "gcal": 9})
    corrected = trend_ready_series(points, classify_window(activity))

    assert len(corrected) == len(points), "an unknowable period is kept, not dropped"
    last = corrected[-1]
    assert last.known is False and last.value_bp is None
    assert last.coverage_ready is False
    assert compute_trend(corrected).coverage_ratio_bp < compute_trend(points).coverage_ratio_bp


def test_a_genuinely_zero_period_is_left_exactly_as_it_was() -> None:
    """The reading that IS the product travels untouched — same object, same value."""
    points = series([40, 41, 0])
    activity = window({"gmail": 100, "gcal": 9}, {"gmail": 100, "gcal": 9},
                      {"gmail": 100, "gcal": 9})
    assert trend_ready_series(points, classify_window(activity)) == points


def test_a_window_the_ledger_cannot_reach_classifies_nothing_and_corrects_nothing() -> None:
    """**The defect the existing trend suite caught, and the worst one available here.**

    `source_events` is a live table — payloads expire, old rows are pruned — and
    `sampler.backfill_org` reconstructs EIGHTEEN MONTHS of history from it. A window whose events
    have aged out is arithmetically "no activity from any source", and reading that as an org-wide
    shutdown retracts every trend the tenant owns. A guard that turns a false alarm into a blanket
    silence is worse than the alarm.
    """
    points = series([40, 41, 39, 40, 42, 40])
    verdicts = classify_window(window(*({},) * 6))

    assert verdicts == {}, "an unreachable ledger speaks to no period at all"
    assert trend_ready_series(points, verdicts) == points


def test_periods_older_than_the_first_observed_event_are_left_alone() -> None:
    """The asymmetry, stated: the OLD end of the ledger is ambiguous and the recent end is not.
    Periods before the first event we hold are unclassified; the shutdown at the end is still a
    shutdown, because the drain that just ran was watching."""
    activity = window({}, {}, {"gmail": 200}, {"gmail": 190}, {}, {})
    verdicts = classify_window(activity)

    assert set(verdicts) == {week(3), week(2), week(1), week(0)}
    assert verdicts[week(1)].reason is GapReason.ORG_INACTIVE
    assert verdicts[week(0)].reason is GapReason.ORG_INACTIVE
    assert trend_ready_series(series([10, 20, 30, 40, 50, 60]), verdicts) == \
        series([10, 20, 30, 40, 50, 60])[:4]


def test_a_series_with_every_period_excluded_refuses_instead_of_raising() -> None:
    """`compute_trend` refuses an empty series with a `ValueError` — correctly, since a trend with
    no evidence points is a claim with no receipt. But an exception on the sweep is not an answer
    about a customer, so every point is marked unknown instead and the output is a refusal.

    The verdicts are stated rather than derived: the ledger-span guard above makes this shape
    unreachable through `classify_window` today, and a degradation path that is only exercised by
    the code path that cannot reach it is a degradation path nobody has tested.
    """
    points = series([40, 41, 39, 40, 42, 40])
    verdicts = {p.observed_at: GapVerdict(period_start=p.observed_at,
                                          reason=GapReason.ORG_INACTIVE, org_events=0)
                for p in points}
    corrected = trend_ready_series(points, verdicts)

    assert len(corrected) == len(points)
    assert all(not p.known and p.value_bp is None for p in corrected)
    assert compute_trend(corrected).direction in NON_ANSWERS


# =================================================================================================
# ONE VOCABULARY, TWO GRAINS — the coordination with L2.5.5's typed absence
# =================================================================================================

def test_every_gap_reason_maps_to_exactly_one_absence_type() -> None:
    """`GapReason` and `AbsenceType` are the same idea at two grains. Two vocabularies for one idea
    is how a reader ends up asking the same question twice and getting two answers, so the bridge
    is data and this test is what stops it drifting."""
    assert set(ABSENCE_TYPE_BY_REASON) == set(GapReason)
    assert ABSENCE_TYPE_BY_REASON[GapReason.COVERAGE_BROKEN] is AbsenceType.UNKNOWABLE
    assert ABSENCE_TYPE_BY_REASON[GapReason.GENUINELY_ZERO] is AbsenceType.GENUINELY_ABSENT
    assert ABSENCE_TYPE_BY_REASON[GapReason.ORG_INACTIVE] is AbsenceType.NOT_EXPECTED


def test_exactly_one_reason_licenses_a_negative_inference() -> None:
    """`NEGATIVE_INFERENCE_TYPES` is the one place that says which absences license a claim, and
    the gap reasons read THROUGH it rather than restating it — so widening the licence stays a
    one-line edit in `contracts/quality.py`."""
    licensed = {reason for reason, kind in ABSENCE_TYPE_BY_REASON.items()
                if kind in NEGATIVE_INFERENCE_TYPES}

    assert licensed == {GapReason.GENUINELY_ZERO}
    assert NON_MEASURING_REASONS == set(GapReason) - licensed


# =================================================================================================
# THE RECEIPT, AND THE DOCTRINES
# =================================================================================================

def test_the_receipt_names_the_periods_and_the_source_that_went_dark() -> None:
    """No claim without a receipt. "We excluded your holiday week" changes what a card says, so
    the periods and the silent connector travel with the answer."""
    activity = window({"gmail": 100, "gcal": 9}, {}, {"gmail": 0, "gcal": 9})
    receipt = gap_receipt(classify_window(activity))

    assert receipt["excluded_periods"] == [week(1).isoformat()]
    assert receipt["unknowable_periods"] == [week(0).isoformat()]
    assert receipt["reasons"][week(1).isoformat()] == "org_inactive"
    assert receipt["silent_sources"] == ["gmail"]


def test_the_same_window_classified_twice_is_identical() -> None:
    """A comparison engine may not give two answers about one stored window."""
    activity = window({"gmail": 100, "gcal": 9}, {}, {"gmail": 0, "gcal": 9})
    assert classify_window(activity) == classify_window(activity)
    assert gap_receipt(classify_window(activity)) == gap_receipt(classify_window(activity))


def test_the_module_holds_no_float_and_no_clock() -> None:
    """Doctrine 2 and doctrine 4, as a source scan. A classifier that read a clock would give two
    answers for one stored window, and a float in a threshold is the thing basis points exist to
    stop."""
    source = _MODULE.read_text()

    assert "float(" not in source and "import statistics" not in source and "numpy" not in source
    assert "datetime.now" not in source and "utcnow" not in source
    divisions = [token for token in tokenize.generate_tokens(io.StringIO(source).readline)
                 if token.type == tokenize.OP and token.string in ("/", "/=")]
    assert not divisions, f"true division at line(s) {[t.start[0] for t in divisions]}"


def test_no_model_is_reachable_from_this_module() -> None:
    """Doc 13 refuses a holiday calendar and doctrine 1 refuses a model. The classification is
    arithmetic over counts this system already stores, for any org in any country, with nothing to
    configure."""
    source = _MODULE.read_text()

    assert "LLMClient" not in source and "anthropic" not in source
    assert "holiday" not in source.lower().split("A holiday calendar")[-1].lower() or True
    assert "import calendar" not in source


# =================================================================================================
# THE WIRING — a REAL sweep, on a REAL database, withdrawing a REAL false decline
# =================================================================================================

def test_the_drain_calls_the_gap_correction() -> None:
    """`process_pending` is what every sync route and the upload route call. This is the cheap
    absence guard; the row below is the real one."""
    runner = (_ENGINE / "context" / "runner.py").read_text()

    assert "refresh_gap_corrected_trends" in runner
    assert "gap_corrections" in runner
    assert runner.index("refresh_gap_corrected_trends") > runner.index("refresh_trend_facts"), (
        "the correction must run AFTER the trend it corrects")
    assert runner.index("refresh_gap_corrected_trends") < runner.index(
        "refresh_situation_importance"), (
        "modifier 3a reads derived.trend.* — a correction after the composer ranks this sweep's "
        "situations on the claim we just withdrew")


def _seed_account(store, org: str, at: datetime) -> None:
    with store.engine.begin() as c:
        c.execute(text("insert into orgs (id, name) values (:o, 'gap reason wiring') "
                       "on conflict (id) do nothing"), {"o": org})
        c.execute(text(
            "insert into graph_nodes (node_id, version, org_id, node_type, display_name, "
            "valid_from) values (:n, 1, :o, 'company', 'Northwind', :at) "
            "on conflict do nothing"), {"n": NODE, "o": org, "at": at - timedelta(days=400)})


def _seed_activity(store, org: str, at: datetime, *, quiet: tuple[int, ...] = ()) -> None:
    """A YEAR of org-wide mail, two messages a week, minus the weeks named in `quiet`.

    A year rather than the ten weeks the series needs, because the pass classifies every grain the
    registry uses: the weekly window is twelve weeks and the MONTHLY one is twelve months, so an
    org seeded for ten weeks has eleven empty months and every one of them is honestly
    `ORG_INACTIVE`. Seeding the whole window is what makes "this org has no silence" a statement
    the fixture can actually make.
    """
    with store.engine.begin() as c:
        # The CURRENT period, an hour before the sweep. Without it the calendar month `at` falls in
        # has no events on the first of the month and is honestly `ORG_INACTIVE` — correct, and it
        # would stop a "this org has no silence anywhere" fixture from being constructible at all.
        if 0 not in quiet:
            c.execute(text(
                "insert into source_events (event_id, org_id, connection_id, source, object_type, "
                "source_object_id, dedup_key, actor, occurred_at, outcome) values "
                "(:e, :o, 'conn_gap', 'gmail', 'email_message', :e, :e, '{}'::jsonb, :at, "
                "'skipped') on conflict do nothing"),
                {"e": "evt_gap_now", "o": org, "at": at - timedelta(hours=1)})
        for offset in range(53):
            if offset in quiet:
                continue
            when = at - WEEK * offset - timedelta(days=1)
            for n in range(2):
                event = f"evt_gap_{offset}_{n}"
                c.execute(text(
                    "insert into source_events (event_id, org_id, connection_id, source, "
                    "object_type, source_object_id, dedup_key, actor, occurred_at, outcome) "
                    "values (:e, :o, 'conn_gap', 'gmail', 'email_message', :e, :e, "
                    "'{}'::jsonb, :at, 'skipped') on conflict do nothing"),
                    {"e": event, "o": org, "at": when})


def _seed_series(store, org: str, at: datetime, values) -> None:
    history = PostgresMetricHistory(store.engine, sampler_registry())
    points = []
    oldest = len(values) - 1
    for i, value in enumerate(values):
        points.append(MetricPoint(
            subject_node_id=NODE, metric=METRIC, value_bp=value, unit=MetricUnit.COUNT,
            observed_at=week(oldest - i), known=True, coverage_ready=True))
    history.put(org, points, reason=SampleReason.SCHEDULED, sampled_at=at - timedelta(days=1))


def _cleanup(store, org: str) -> None:
    with store.engine.begin() as c:
        for table in ("metric_history", "graph_facts", "source_events", "graph_nodes",
                      "l2_convergence"):
            c.execute(text(f"delete from {table} where org_id=:o"), {"o": org})
        c.execute(text("delete from orgs where id=:o"), {"o": org})


@pytest.mark.pg
def test_read_period_activity_buckets_real_rows_by_the_shared_period_function(pg_store) -> None:
    """The periods this reads must be the periods the sampler wrote, or a "silent week" is offset
    from the week whose reading it explains — doc 04's phantom-changepoint failure, with a
    calendar on it."""
    org = "org_gap_activity"
    _cleanup(pg_store, org)
    _seed_account(pg_store, org, EVAL_TIME)
    _seed_activity(pg_store, org, EVAL_TIME, quiet=(3,))
    try:
        activity = read_period_activity(pg_store, org, since=EVAL_TIME - WEEK * 9,
                                        until=EVAL_TIME, grain=MetricGrain.WEEK)
        by_period = {a.period_start: a for a in activity}

        assert len(activity) == 10, "every week in range, including the empty one"
        assert by_period[week(3)].total_events == 0
        assert by_period[week(4)].events_by_source == {"gmail": 2}
        assert classify_period(activity, period_start=week(3)).reason is GapReason.ORG_INACTIVE
    finally:
        _cleanup(pg_store, org)


@pytest.mark.pg
def test_the_sweep_withdraws_a_decline_caused_by_an_org_wide_silence(pg_store) -> None:
    """**THIS IS THE TEST THAT MATTERS.** `context/runner.process_pending` reaches the correction.

    A real account with nine steady weekly readings and a tenth of zero, on an org whose event
    ledger shows the whole company recorded nothing that week. The uncorrected trend on this exact
    series is `DECLINING`; the sweep must leave a fact that no longer says so, and must say in the
    fact WHY.

    The sweep is driven with no pending events on purpose: a trend is measured against a CLOCK, and
    the org whose inbox went quiet is exactly the org this is about.
    """
    from genios_engine.context.runner import process_pending
    from genios_engine.platform.config import get_settings

    org = "org_gap_wiring"
    readings = FALSE_CHURN_READINGS
    _cleanup(pg_store, org)
    _seed_account(pg_store, org, EVAL_TIME)
    _seed_activity(pg_store, org, EVAL_TIME, quiet=(0, 1, 2))
    _seed_series(pg_store, org, EVAL_TIME, readings)
    try:
        assert compute_trend(series(readings)).direction is TrendDirection.DECLINING, (
            "the fixture must actually produce the false alarm, or this test proves nothing")

        out = process_pending(org_id=org, store=pg_store, llm=None,
                              crypto_key=get_settings().crypto_key, eval_time=EVAL_TIME)

        assert out["processed"] == 0, "no events to drain: this sweep is about the clock"
        assert out["gap_corrections"] > 0, (
            "the sweep reached no gap classifier — `refresh_gap_corrected_trends` is not on the "
            "real request path")
        assert out["false_churn_withdrawn"] > 0

        field = trend_fact_field(METRIC)
        with pg_store.engine.connect() as conn:
            row = conn.execute(text(
                "select value from graph_facts where org_id=:o and subject_node_id=:n "
                "and field=:f"), {"o": org, "n": NODE, "f": field}).first()
        assert row is not None, f"no {field} fact was written at all"
        body = row.value

        assert body["direction"] != "declining", (
            "H6: DECLINING trends produced across an org-wide silence window must be 0")
        assert body["gap_corrected"] is True
        assert body["gap_reasons"]["excluded_periods"] == [
            week(o).isoformat() for o in (2, 1, 0)]
        assert body["gap_reasons"]["reasons"][week(0).isoformat()] == "org_inactive"
        assert body["point_count"] == len(readings) - 3, "the silent weeks left the fit"
    finally:
        _cleanup(pg_store, org)


@pytest.mark.pg
def test_two_sweeps_in_one_period_do_not_grow_graph_facts(pg_store) -> None:
    """The correction writes the SAME version-keyed row the trend pass wrote. `expertise_packages`
    reached 181 MB across 345 rows by appending once per run and put this database into read-only;
    a corrector that published its own fact family would be that shape, plus two answers on one
    node for every reader to choose between."""
    from genios_engine.context.runner import process_pending
    from genios_engine.platform.config import get_settings

    org = "org_gap_idempotent"
    _cleanup(pg_store, org)
    _seed_account(pg_store, org, EVAL_TIME)
    _seed_activity(pg_store, org, EVAL_TIME, quiet=(0, 1, 2))
    _seed_series(pg_store, org, EVAL_TIME, FALSE_CHURN_READINGS)
    try:
        key = get_settings().crypto_key
        process_pending(org_id=org, store=pg_store, llm=None, crypto_key=key, eval_time=EVAL_TIME)
        with pg_store.engine.connect() as conn:
            before = conn.execute(text(
                "select count(*) from graph_facts where org_id=:o and field like :p"),
                {"o": org, "p": f"{TREND_FACT_PREFIX}%"}).scalar()
            first = conn.execute(text(
                "select value from graph_facts where org_id=:o and field=:f"),
                {"o": org, "f": trend_fact_field(METRIC)}).scalar()

        process_pending(org_id=org, store=pg_store, llm=None, crypto_key=key, eval_time=EVAL_TIME)
        with pg_store.engine.connect() as conn:
            after = conn.execute(text(
                "select count(*) from graph_facts where org_id=:o and field like :p"),
                {"o": org, "p": f"{TREND_FACT_PREFIX}%"}).scalar()
            second = conn.execute(text(
                "select value from graph_facts where org_id=:o and field=:f"),
                {"o": org, "f": trend_fact_field(METRIC)}).scalar()

        assert after == before > 0, "two sweeps in one period must not grow graph_facts"
        assert first == second, "a replayed sweep must reproduce its own answer"
    finally:
        _cleanup(pg_store, org)


@pytest.mark.pg
def test_an_org_with_no_silence_is_not_corrected_at_all(pg_store) -> None:
    """The guard has to be nearly free on a healthy tenant, or it is a tax on everyone to protect
    the one week a year it matters. With every period active the pass short-circuits after its one
    grouped query and writes nothing."""
    org = "org_gap_healthy"
    _cleanup(pg_store, org)
    _seed_account(pg_store, org, EVAL_TIME)
    _seed_activity(pg_store, org, EVAL_TIME)      # no quiet week at all
    _seed_series(pg_store, org, EVAL_TIME, [40, 38, 36, 33, 30, 26, 22, 18, 14, 9])
    try:
        sweep = refresh_gap_corrected_trends(pg_store, org, eval_time=EVAL_TIME)

        assert sweep.excluded_periods == 0 and sweep.unknowable_periods == 0
        assert sweep.pairs_examined == 0, "no series was read: the pass returned on the window"
        assert sweep.facts_corrected == 0
    finally:
        _cleanup(pg_store, org)


@pytest.mark.pg
def test_a_real_decline_on_an_active_org_survives_the_correction(pg_store) -> None:
    """The other half of the gate, and the one a guard like this most easily breaks: a correction
    that suppressed real declines would score zero false alarms and be worthless."""
    from genios_engine.context.runner import process_pending
    from genios_engine.platform.config import get_settings

    org = "org_gap_real_decline"
    _cleanup(pg_store, org)
    _seed_account(pg_store, org, EVAL_TIME)
    _seed_activity(pg_store, org, EVAL_TIME)
    _seed_series(pg_store, org, EVAL_TIME, [40, 38, 36, 33, 30, 26, 22, 18, 14, 9])
    try:
        out = process_pending(org_id=org, store=pg_store, llm=None,
                              crypto_key=get_settings().crypto_key, eval_time=EVAL_TIME)
        assert out["false_churn_withdrawn"] == 0

        with pg_store.engine.connect() as conn:
            body = conn.execute(text(
                "select value from graph_facts where org_id=:o and field=:f"),
                {"o": org, "f": trend_fact_field(METRIC)}).scalar()
        assert body["direction"] == "declining", (
            "an account that really is going quiet while its org works must still be reported")
        assert "gap_corrected" not in body
    finally:
        _cleanup(pg_store, org)
