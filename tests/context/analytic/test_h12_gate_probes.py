"""H1 + H2 · the GATE AGENT's own probes — written against the built units, not with them.

Every assertion in this file was written from doc 09's two gate tables and from the wave brief's
verification list, WITHOUT reading the builder's test files first. That is the whole point of it:
`tests/context/analytic/test_metric_history.py`, `test_metric_sampler.py`, `test_trend.py` and
`test_cohort.py` are the builder's own account of what they built, and a suite that only contains
those cannot tell "this is correct" from "this is what I happened to implement".

The nine probes are the nine failures the brief names, one test each:

  1. a point-in-time read returns what was known THEN
  2. two sweeps in one sampling period do not double-write
  3. a metric the graph cannot answer stores known=False, never a zero
  4. a trend from too few points REFUSES
  5. a series with gaps is not interpolated  (doc 09's decisive H2 row)
  6. a cohort below the population floor REFUSES
  7. TENANT ISOLATION — the highest-risk item in the wave
  8. the sampler is on the REAL sweep path
  9. erasure — every new table of this wave leaves with the org, on real Postgres

Real Postgres wherever the claim is about storage, because every one of these failures is a
failure of SQL: an `as_at` clause that is not there, an upsert that rewrites an unchanged row, a
gap written as a zero, a delete that names four tables and not five. An in-memory twin agreeing
with itself proves none of them.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import text

from genios_engine.contracts.analytic import MetricUnit, TrendDirection
from genios_engine.context.analytic.cohort import (MIN_COHORT_POPULATION, CohortRefusal,
                                                   CohortRefusalReason, position_from_values,
                                                   position_in_cohort)
from genios_engine.context.analytic.history import (HISTORY_TABLE, MetricGrain, MetricPoint,
                                                    PostgresMetricHistory, SampleReason,
                                                    default_registry, period_start)
from genios_engine.context.analytic.trend import MIN_TREND_POINTS, compute_trend

TOUCHES = "engagement.touch_count"
MONTH = MetricGrain.MONTH


# ─────────────────────────────────────────────────────────────────────── helpers, mine not theirs

def _month(year: int, month: int) -> datetime:
    return datetime(year, month, 1, tzinfo=timezone.utc)


def _point(node: str, at: datetime, value: int | None, *, known: bool = True) -> MetricPoint:
    return MetricPoint(subject_node_id=node, metric=TOUCHES, value_bp=value,
                       unit=MetricUnit.COUNT, observed_at=at, known=known)


def _series(values, *, start=_month(2026, 1), node: str = "n1") -> tuple[MetricPoint, ...]:
    """A dense monthly series. `None` is a GAP — carried, never dropped, never filled."""
    out = []
    at = start
    for value in values:
        out.append(_point(node, at, value, known=value is not None)
                   if value is not None else _point(node, at, None, known=False))
        at = _month(at.year + (at.month // 12), at.month % 12 + 1)
    return tuple(out)


def _make_org(engine, org: str) -> None:
    with engine.begin() as conn:
        conn.execute(text("insert into orgs (id, name) values (:o, 'H12 probe') "
                          "on conflict (id) do nothing"), {"o": org})


def _drop_org(engine, org: str) -> None:
    with engine.begin() as conn:
        conn.execute(text("delete from orgs where id=:o"), {"o": org})


def _count(engine, table: str, org: str) -> int:
    with engine.connect() as conn:
        return conn.execute(text(f"select count(*) from {table} where org_id=:o"),
                            {"o": org}).scalar()


# ══════════════════════════════════════════════════ 1 · POINT-IN-TIME

@pytest.mark.pg
def test_a_point_in_time_read_returns_what_was_known_then(pg_store) -> None:
    """`as_at` is the difference between replaying a decision and re-deciding it.

    March's series is read twice: once with no `as_at` (everything we know now) and once with
    `as_at` set to the instant BEFORE April's reading arrived. The second must not contain April.
    A store without the `sampled_at <= :asat` clause passes every other test in this wave and
    fails only here, because every other read asks for the newest truth.
    """
    org = "org_h12_pit"
    engine = pg_store.engine
    _make_org(engine, org)
    store = PostgresMetricHistory(engine)
    try:
        march_arrived = datetime(2026, 3, 31, 12, tzinfo=timezone.utc)
        april_arrived = datetime(2026, 4, 30, 12, tzinfo=timezone.utc)
        store.put(org, [_point("n1", _month(2026, 3), 40)],
                  reason=SampleReason.SCHEDULED, sampled_at=march_arrived)
        store.put(org, [_point("n1", _month(2026, 4), 5)],
                  reason=SampleReason.SCHEDULED, sampled_at=april_arrived)

        now = store.read_series(org, "n1", TOUCHES, since=_month(2026, 3), until=_month(2026, 4))
        assert [p.value_bp for p in now] == [40, 5]

        then = store.read_series(org, "n1", TOUCHES, since=_month(2026, 3), until=_month(2026, 4),
                                 as_at=april_arrived - timedelta(seconds=1))
        assert [p.value_bp for p in then] == [40, None], (
            "an as-at read from before April's reading arrived returned it anyway — the replay "
            "shows a collapse that was not knowable at the time")
        assert then[1].known is False and then[1].value_bp is None, (
            "a period that had not been read yet must come back as a GAP, never as a zero")

        # And the single-period read agrees with the series read — two code paths, one answer.
        assert store.get(org, "n1", TOUCHES, _month(2026, 4),
                         as_at=april_arrived - timedelta(seconds=1)) is None
    finally:
        _drop_org(engine, org)


@pytest.mark.pg
def test_an_identical_re_sample_does_not_move_the_point_forward_in_time(pg_store) -> None:
    """The subtler half of probe 1, and the one that would delete history silently.

    A sweep that re-writes an unchanged row moves `sampled_at` to today. Nothing looks wrong: the
    value is right, the count is right, the series reads correctly. But every `as_at` read taken
    before today now shows that period as a GAP, so a trend computed in March stops replaying —
    the point has been retro-actively un-known. Asserted on the COLUMN, because that is where the
    damage would be, and confirmed through an as-at read, because that is where it would be felt.
    """
    org = "org_h12_resample"
    engine = pg_store.engine
    _make_org(engine, org)
    store = PostgresMetricHistory(engine)
    try:
        first = datetime(2026, 3, 5, 9, tzinfo=timezone.utc)
        later = datetime(2026, 3, 25, 9, tzinfo=timezone.utc)
        point = _point("n1", _month(2026, 3), 40)
        assert store.put(org, [point], reason=SampleReason.SCHEDULED, sampled_at=first) == 1
        assert store.put(org, [point], reason=SampleReason.BACKFILL, sampled_at=later) == 0, (
            "an identical reading re-written is a changed row — `put` must report 0 changed")

        with engine.connect() as conn:
            stamped = conn.execute(text(
                f"select sampled_at from {HISTORY_TABLE} where org_id=:o"), {"o": org}).scalar()
        assert stamped == first, (
            "the re-sample moved `sampled_at` forward; every as-at read before it now shows a gap")
        replayed = store.read_series(org, "n1", TOUCHES, since=_month(2026, 3),
                                     until=_month(2026, 3), as_at=first + timedelta(hours=1))
        assert replayed[0].value_bp == 40, "the point was un-known by a re-sample that agreed"
    finally:
        _drop_org(engine, org)


# ══════════════════════════════════════════════════ 2 · DOUBLE-WRITE / ROW GROWTH

@pytest.mark.pg
def test_two_sweeps_in_one_sampling_period_do_not_double_write(pg_store) -> None:
    """The `expertise_packages` shape, asked directly of the table.

    Five sweeps across one month — every day of a week — must leave ONE row, because
    `observed_at` is the PERIOD and the period is in the primary key. The row count is asserted
    against the calendar (`periods`), never against the number of sweeps, which is the whole
    bounding argument of this table stated as a number.
    """
    org = "org_h12_growth"
    engine = pg_store.engine
    _make_org(engine, org)
    store = PostgresMetricHistory(engine)
    try:
        for day in (2, 5, 9, 17, 28):
            sweep_at = datetime(2026, 3, day, 8, tzinfo=timezone.utc)
            store.put(org, [_point("n1", period_start(sweep_at, MONTH), 40 + day)],
                      reason=SampleReason.SCHEDULED, sampled_at=sweep_at)
        assert _count(engine, HISTORY_TABLE, org) == 1, (
            "five sweeps in one month left more than one row — this table grows with the sweep "
            "cadence rather than with the calendar, which is the read-only incident's shape")

        # A second PERIOD is a second row, and only a second period is.
        store.put(org, [_point("n1", _month(2026, 4), 12)],
                  reason=SampleReason.SCHEDULED, sampled_at=datetime(2026, 4, 3, 8,
                                                                     tzinfo=timezone.utc))
        assert _count(engine, HISTORY_TABLE, org) == 2
    finally:
        _drop_org(engine, org)


@pytest.mark.pg
def test_the_per_series_cap_bites_on_the_write_path(pg_store) -> None:
    """Retention mechanism 3, on real SQL. A backfill that walks more periods than the definition
    keeps must not leave them all — otherwise the wall-clock prune is the only bound, and it does
    not run until the next drain."""
    org = "org_h12_cap"
    engine = pg_store.engine
    _make_org(engine, org)
    keep = default_registry().require(TOUCHES).retention_periods
    store = PostgresMetricHistory(engine)
    try:
        at = _month(2020, 1)
        points = []
        for i in range(keep + 12):
            points.append(_point("n1", at, i + 1))
            at = _month(at.year + (at.month // 12), at.month % 12 + 1)
        store.put(org, points, reason=SampleReason.BACKFILL,
                  sampled_at=datetime(2026, 3, 1, tzinfo=timezone.utc))
        assert _count(engine, HISTORY_TABLE, org) == keep, (
            f"a {len(points)}-period backfill left more than the {keep} the definition keeps")
    finally:
        _drop_org(engine, org)


# ══════════════════════════════════════════════════ 3 · A GAP IS NOT A ZERO

@pytest.mark.pg
def test_a_metric_the_graph_cannot_answer_is_stored_unknown_and_never_as_a_zero(pg_store) -> None:
    """Doc 09's H1 row "coverage gaps stored as 0 instead of unknown: 0".

    Driven through the real sampler against a real org that has a company node and NO deal value
    fact, so `deal.value_minor_units` is a metric the graph genuinely cannot answer. Two
    assertions, and the second is the one that matters: the run must SAY it could not answer
    (a gap point, so a reader can see what is missing) and the TABLE must hold no row for it
    (because `value_bp` is NOT NULL and a zero is a measurement).
    """
    from genios_engine.context.analytic.sampler import TrendedMetric, sample_org

    org = "org_h12_gap"
    engine = pg_store.engine
    at = datetime(2026, 3, 10, 9, tzinfo=timezone.utc)
    _make_org(engine, org)
    try:
        with engine.begin() as conn:
            conn.execute(text(
                "insert into graph_nodes (node_id, version, org_id, node_type, display_name) "
                "values ('n_gapco', 1, :o, 'company', 'Gap Co') on conflict do nothing"), {"o": org})
            conn.execute(text(
                "insert into graph_observations (observation_id, org_id, subject_node_id, "
                "  kind, occurred_at, confidence, status) "
                "values ('obs_gap_1', :o, 'n_gapco', 'email', :at, 1, 'active') "
                "on conflict do nothing"), {"o": org, "at": at - timedelta(days=3)})

        run = sample_org(pg_store, org_id=org, eval_time=at)
        unanswerable = {p.metric for p in run.gap_points}
        assert TrendedMetric.DEAL_VALUE_MINOR_UNITS.value in unanswerable, (
            "the sampler measured a deal value on a node with no deal value fact")
        assert all(p.value_bp is None and p.known is False for p in run.gap_points), (
            "a gap point carried a value — V-3 says a gap carries none")

        with engine.connect() as conn:
            stored = {r.metric: r.value_bp for r in conn.execute(text(
                f"select metric, value_bp from {HISTORY_TABLE} where org_id=:o"), {"o": org})}
        assert TrendedMetric.DEAL_VALUE_MINOR_UNITS.value not in stored, (
            "an unanswerable metric was written to the table — the only honest storage of a gap "
            "is the absence of a row, and a stored 0 is indistinguishable from a measured 0")
        assert 0 not in [v for m, v in stored.items()
                         if m == TrendedMetric.DEAL_VALUE_MINOR_UNITS.value]
    finally:
        _drop_org(engine, org)


@pytest.mark.pg
def test_a_gap_read_back_is_a_gap_and_not_interpolated(pg_store) -> None:
    """The read side of the same rule, and doc 09's second H1 row ("interpolated values: 0").

    Two readings a month apart with the month between them never written. The dense read must
    return three points of which the middle is `known=False, value_bp=None` — not the mean of its
    neighbours, not the last value carried forward, and not dropped (dropping it is the subtler
    error: it makes `coverage_ratio_bp` report 100% on a series that is one third holes).
    """
    org = "org_h12_interp"
    engine = pg_store.engine
    _make_org(engine, org)
    store = PostgresMetricHistory(engine)
    try:
        sampled = datetime(2026, 4, 1, tzinfo=timezone.utc)
        store.put(org, [_point("n1", _month(2026, 1), 100), _point("n1", _month(2026, 3), 200)],
                  reason=SampleReason.SCHEDULED, sampled_at=sampled)
        series = store.read_series(org, "n1", TOUCHES,
                                   since=_month(2026, 1), until=_month(2026, 3))
        assert len(series) == 3, "the read is not dense — a gap must occupy its period"
        assert [p.value_bp for p in series] == [100, None, 200], (
            "February was interpolated; a fabricated observation is indistinguishable in the "
            "column from a measured one and it improves the ratio that exists to reveal it")
        assert series[1].known is False
    finally:
        _drop_org(engine, org)


# ══════════════════════════════════════════════════ 4-5 · TREND REFUSES

def test_a_trend_from_too_few_points_refuses_rather_than_guessing() -> None:
    """Three points that fall off a cliff. The honest answer is INSUFFICIENT_HISTORY.

    Also asserted: the refusal carries no direction to quote and no slope to render. A refusal
    that came back with `relative_slope_bp = -4000` would be a decline wearing a refusal's label,
    and every renderer that checks the number rather than the enum would print it.
    """
    refusal = compute_trend(_series([100, 60, 20]))
    assert refusal.direction is TrendDirection.INSUFFICIENT_HISTORY, (
        f"{MIN_TREND_POINTS - 1} points produced a direction: {refusal.direction}")
    assert refusal.relative_slope_bp == 0 and refusal.streak_periods == 0
    assert refusal.point_count == 3


def test_a_six_point_monotonic_decline_declines_and_the_same_values_with_gaps_refuse() -> None:
    """Doc 09's decisive H2 row, both halves, asserted against ONE set of values.

    The values are identical; only the coverage differs. If the gapped call also said DECLINING,
    the coverage floor would be describing periods we happened to observe and calling it a trend.
    """
    values = [120, 100, 82, 61, 40, 21]
    dense = compute_trend(_series(values))
    assert dense.direction is TrendDirection.DECLINING
    assert dense.coverage_ratio_bp == 10_000

    # The same six values spread over eleven periods — every other period a hole. There are more
    # than enough points to fit and the fit is a clean decline; reporting it would be a false
    # churn alarm about a customer who is fine, caused by the tenant having one fewer source
    # connected than we assumed. Doc 04 names this the worst output the group can produce.
    gapped = compute_trend(_series([120, None, 100, None, 82, None, 61, None, 40, None, 21]))
    assert gapped.direction is TrendDirection.INSUFFICIENT_COVERAGE, (
        "the same values with holes still answered DECLINING — that is a fit over the periods "
        "that happened to be observed, and the reader cannot see it from the word")
    assert gapped.point_count >= MIN_TREND_POINTS, "this is the coverage refusal, not the history one"
    assert gapped.trend_confidence_bp == 0, "a refusal must not carry confidence"


def test_the_coverage_floor_sits_exactly_where_doc_04_puts_it() -> None:
    """The floor is a NUMBER, and the two gate documents disagree about it — so it is pinned here.

    Doc 04 (L2.4.3 step 1) states the rule twice and gives it an arithmetic form:
    `known / len(series) < 0.6 -> INSUFFICIENT_COVERAGE`, "a series more than 40% gaps cannot
    support a trend claim". Doc 09's H2 summary row instead says "the same values with 3 gaps →
    INSUFFICIENT_COVERAGE", and six values with three gaps is nine periods at 66.7% coverage,
    which doc 04's rule ANSWERS. The two cannot both hold:

      * to refuse 6-of-9 the floor would have to be above 6667bp, which no line of doc 04
        supports and which would make doc 04's own "40% gaps" sentence false;
      * to read doc 09 as six PERIODS of which three are gaps gives three known points, and
        step 1 refuses that as INSUFFICIENT_HISTORY (V-5, four points) before coverage is
        consulted — so that reading cannot produce the answer doc 09 names either.

    Doc 04 is the normative algorithm and doc 09 is its acceptance summary, so the implementation
    follows doc 04 and the disagreement is recorded here rather than resolved by moving a
    threshold on nobody's authority. Both sides of the boundary are asserted, so a later wave
    that DOES move it has to come through this test and read this note.
    """
    from genios_engine.context.analytic.trend import COVERAGE_FLOOR_BP

    assert COVERAGE_FLOOR_BP == 6_000, "doc 04 step 1 says 0.6"

    at_the_floor = compute_trend(_series([120, 100, None, 82, 61, None, 40, 21, None, 10]))
    assert at_the_floor.coverage_ratio_bp == 7_000
    assert at_the_floor.direction is TrendDirection.DECLINING, (
        "a series above the floor must still answer — a floor nobody can clear is not a floor")

    below = compute_trend(_series([120, None, None, 100, None, 82, None, 61, 40, None]))
    assert below.coverage_ratio_bp == 5_000
    assert below.direction is TrendDirection.INSUFFICIENT_COVERAGE

    # Doc 09's literal row, recorded as behaviour rather than asserted as a requirement: six
    # values with three gaps is 66.7% covered and doc 04 answers it.
    doc09_literal = compute_trend(_series([120, None, 100, None, 82, None, 61, 40, 21]))
    assert doc09_literal.coverage_ratio_bp == 6_666
    assert doc09_literal.direction is TrendDirection.DECLINING


def test_the_same_absolute_decline_is_noise_on_a_big_base_and_a_decline_on_a_small_one() -> None:
    """Doc 09's other decisive H2 row: a fall of 5 per period is FLAT on a base of 5000 and
    DECLINING on a base of 8. A slope that was not normalised against the base would call both
    the same, and would put "declining" on every large account in the tenant's book."""
    big = compute_trend(_series([5000, 4995, 4990, 4985, 4980, 4975]))
    assert big.direction is TrendDirection.FLAT, (
        "a 0.1%-per-period drift was reported as a direction — the slope is not normalised")

    small = compute_trend(_series([28, 23, 18, 13, 8]))
    assert small.direction is TrendDirection.DECLINING, (
        "a fall of 5 on a base of 8 is not noise, and calling it FLAT hides the collapse this "
        "layer exists to surface")


def test_a_trend_reads_no_clock_and_returns_the_same_answer_twice() -> None:
    """Determinism, stated as an equality rather than as a docstring. `compute_trend` takes no
    `eval_time` at all, so a stored series has exactly one answer for ever."""
    series = _series([120, 100, 82, 61, 40, 21])
    first, second = compute_trend(series), compute_trend(series)
    assert (first.direction, first.relative_slope_bp, first.trend_confidence_bp) == (
        second.direction, second.relative_slope_bp, second.trend_confidence_bp)
    assert all(isinstance(v, int) and not isinstance(v, bool) for v in
               (first.relative_slope_bp, first.streak_periods, first.point_count,
                first.coverage_ratio_bp, first.trend_confidence_bp)), (
        "a measure came back as a float — every number on this path is integer basis points")


# ══════════════════════════════════════════════════ 6 · COHORT FLOOR

def test_a_cohort_below_the_population_floor_refuses() -> None:
    """Doc 09's third decisive H2 row: a cohort of 4 is `insufficient_population`.

    Asserted at the floor AND one member above it, because a refusal that also fired at five
    would be a floor nobody could clear, and this file must be able to tell the two apart.
    """
    four = {"a": 10, "b": 20, "c": 30, "d": 40}
    refused = position_from_values(metric=TOUCHES, cohort_id="c_small", values=four,
                                   subject_node_id="a", eval_time=_month(2026, 3))
    assert isinstance(refused, CohortRefusal)
    assert refused.reason is CohortRefusalReason.INSUFFICIENT_POPULATION
    assert refused.population_size == 4
    assert refused.is_position is False, "a refusal must not be mistakable for a position"

    five = {**four, "e": 50}
    assert len(five) == MIN_COHORT_POPULATION
    position = position_from_values(metric=TOUCHES, cohort_id="c_small", values=five,
                                    subject_node_id="a", eval_time=_month(2026, 3))
    assert not isinstance(position, CohortRefusal), "the floor refused at its own value"
    assert position.population_size == 5 and position.cohort_id == "c_small"


# ══════════════════════════════════════════════════ 7 · TENANT ISOLATION

@pytest.mark.pg
def test_positioning_org_a_reaches_nothing_of_org_b(pg_store) -> None:
    """THE HIGHEST-RISK PROBE IN THE WAVE, and it is built to be as hostile as the data can be.

    Both tenants use THE SAME node ids (`n_1`..`n_6`) and the same metric name, which is what a
    real deployment looks like when two customers both import a CRM whose ids are sequential. Org
    B's readings are ten times org A's, so a query that dropped `org_id` from ANY of its three
    statements — the membership read, the values read, or the definition lookup — moves A's
    percentile by an amount this test can see.

    Three separate leaks are asked about, because they are three different bugs:
      * B's MEMBERS leaking into A's population (a membership read without `org_id`)
      * B's READINGS leaking into A's distribution (a values read without `org_id`)
      * B's COHORT being addressable from A at all (a definition lookup without `org_id`)
    And the fourth assertion is about the object rather than the query: what comes back must
    carry no member identity, because a position is a statement about a distribution.
    """
    engine = pg_store.engine
    a, b = "org_h12_iso_a", "org_h12_iso_b"
    at = datetime(2026, 5, 15, tzinfo=timezone.utc)
    _make_org(engine, a)
    _make_org(engine, b)
    store = PostgresMetricHistory(engine)
    try:
        # B's readings are TEN TIMES A's and sit in a LATER period on purpose. The values read is
        # a `distinct on (subject_node_id) ... order by observed_at desc`, so if its `org_id`
        # predicate were dropped the tie would be broken IN B'S FAVOUR and the leak is
        # deterministic rather than a coin flip. An earlier draft of this probe gave both tenants
        # the same period, and removing the org filter from that query left it passing.
        for org, scale, period in ((a, 1, _month(2026, 3)), (b, 10, _month(2026, 4))):
            cohort = f"co_{org}"
            with engine.begin() as conn:
                conn.execute(text(
                    "insert into cohort_definitions (cohort_id, org_id, name, node_type, "
                    "  predicate, created_by) values (:c, :o, 'probe', 'company', "
                    "  cast('{\"op\": \"exists\", \"fact\": \"node.name\"}' as jsonb), 'probe')"),
                    {"c": cohort, "o": org})
                for i in range(1, 7):
                    conn.execute(text(
                        "insert into graph_nodes (node_id, version, org_id, node_type, "
                        "  display_name) values (:n, 1, :o, 'company', :d) "
                        "on conflict do nothing"),
                        {"n": f"n_{i}", "o": org, "d": f"{org} account {i}"})
                    conn.execute(text(
                        "insert into cohort_membership (org_id, cohort_id, node_id, joined_at) "
                        "values (:o, :c, :n, :j)"),
                        {"o": org, "c": cohort, "n": f"n_{i}",
                         "j": at - timedelta(days=90)})
            store.put(org, [_point(f"n_{i}", period, i * scale) for i in range(1, 7)],
                      reason=SampleReason.SCHEDULED, sampled_at=at)

        got = position_in_cohort(store, org_id=a, cohort_id=f"co_{a}", metric=TOUCHES,
                                 subject_node_id="n_6", eval_time=at)
        assert not isinstance(got, CohortRefusal), got
        assert got.population_size == 6, (
            f"org A's cohort reported {got.population_size} members and it has 6 — org B's "
            "members were counted in org A's population")
        assert (got.p25_bp, got.p50_bp, got.p75_bp) == (2, 3, 4), (
            f"org A's ladder is {(got.p25_bp, got.p50_bp, got.p75_bp)}; A's readings are 1..6 "
            "and B's are 10..60, so any number above 6 here is org B's data inside org A's "
            "distribution")
        assert got.percentile_bp == 10_000, "n_6 is A's maximum and must rank as it"

        # B's cohort is not addressable from A — and the refusal says "no such cohort", which is
        # also the only honest thing to tell A about a cohort that is not theirs.
        crossed = position_in_cohort(store, org_id=a, cohort_id=f"co_{b}", metric=TOUCHES,
                                     subject_node_id="n_6", eval_time=at)
        assert isinstance(crossed, CohortRefusal)
        assert crossed.reason is CohortRefusalReason.NO_SUCH_COHORT, (
            "org A addressed org B's cohort id and got something other than 'no such cohort'")

        # Nothing identifiable of B — or of any other member of A — is reachable from the object.
        rendered = repr(got.model_dump())
        for leaked in (b, "account", "n_1", "n_2", "n_3", "n_4", "n_5"):
            assert leaked not in rendered, (
                f"{leaked!r} is reachable from a CohortPosition — a position names the "
                f"distribution, never the people in it: {rendered}")
    finally:
        _drop_org(engine, a)
        _drop_org(engine, b)


def test_the_cross_org_baseline_refuses_by_construction() -> None:
    """The deferral in doc 04 L2.4.6-U2, asked of the code rather than of the document. A
    deferral that is only a sentence is one helpful pull request away from being undone."""
    from genios_engine.context.analytic.peer_baseline import cross_org_baseline
    with pytest.raises(Exception) as raised:
        cross_org_baseline()
    assert "cross" in str(raised.value).lower() or "org" in str(raised.value).lower()


# ══════════════════════════════════════════════════ 8 · THE REAL SWEEP PATH

def test_the_sampler_and_the_prune_are_reached_from_process_pending_in_the_source() -> None:
    """Layer 1 shipped six units that were green and called by nothing. This is the source-level
    half of the answer for L2.4.1/L2.4.2: `context/runner.process_pending` — the function both
    sync routes call — must contain the calls, and the sampling pass must NOT be nested under the
    `done or affected` guard the derivation passes use, because every trended metric is measured
    against a clock rather than against an event.
    """
    import inspect

    from genios_engine.context import runner

    import re

    source = inspect.getsource(runner.process_pending)
    # Each analytic pass is CALLED, and each is called with the sweep's ONE instant. Asserted as
    # one regex per call rather than as four `in` checks plus a loose `"eval_time=sweep_at" in
    # source`, because that combination passes when three of the four take their own clock.
    for call in ("prune_history_for_drain", "sample_org", "refresh_trend_facts",
                 "refresh_cohorts_for_drain"):
        assert re.search(rf"\b{call}\([^)]*eval_time=sweep_at", source), (
            f"`{call}` is either not called from process_pending or is not handed `sweep_at` — "
            "a pass that reads its own clock deletes a point at a month boundary and "
            "immediately rewrites it")
    # And the sampling pass is UNCONDITIONAL: it must not sit under the `done or affected` guard
    # the derivation passes use. Every trended metric is measured against a clock rather than
    # against an event, so gating it freezes a quiet org's series at its last sweep with mail.
    sampling = source.index("sample_org(")
    preceding = source[:sampling].rsplit("try:", 1)[0]
    assert "if done or affected" not in preceding.rsplit("\n\n", 1)[-1], (
        "the sampling pass is gated on having ingested something")


@pytest.mark.pg
def test_a_real_sweep_writes_history_a_second_sweep_adds_no_row_and_the_trend_lands(pg_store):
    """The wiring half, driven through the entry point the API calls, on a real database.

    Four claims in one drive because they are one claim: the sweep reaches the sampler, the
    sampler's write is bounded by the period, the trend pass reads what the sampler wrote, and
    none of it needs an event to have been ingested (`processed == 0`) — an org with a quiet
    inbox is exactly the org whose decline is worth surfacing.
    """
    from genios_engine.context.runner import process_pending
    from genios_engine.platform.config import get_settings

    org = "org_h12_sweep"
    engine = pg_store.engine
    at = datetime(2026, 3, 4, 9, tzinfo=timezone.utc)
    _make_org(engine, org)
    try:
        with engine.begin() as conn:
            conn.execute(text(
                "insert into graph_nodes (node_id, version, org_id, node_type, display_name) "
                "values ('n_sweepco', 1, :o, 'company', 'Sweep Co') on conflict do nothing"),
                {"o": org})
            conn.execute(text(
                "insert into graph_facts (fact_version_id, fact_id, org_id, subject_node_id, "
                "  field, value, value_type, status, occurred_at, valid_from) "
                "values ('fv_h12_stage', 'f_h12_stage', :o, 'n_sweepco', 'deal.stage', "
                "  cast('\"proposing\"' as jsonb), 'string', 'active', :at, :at) "
                "on conflict (fact_version_id) do nothing"),
                {"o": org, "at": at - timedelta(days=30)})
            conn.execute(text(
                "insert into graph_observations (observation_id, org_id, subject_node_id, "
                "  kind, occurred_at, confidence, status) "
                "values ('obs_h12_1', :o, 'n_sweepco', 'email', :at, 1, 'active') "
                "on conflict do nothing"), {"o": org, "at": at - timedelta(days=2)})

        out = process_pending(org_id=org, store=pg_store, llm=None,
                              crypto_key=get_settings().crypto_key, eval_time=at)
        assert out["processed"] == 0, "this probe is about a sweep that drained nothing"
        written = _count(engine, HISTORY_TABLE, org)
        assert written > 0, (
            "the sweep wrote no history — `sample_org` is not on the real request path, which is "
            "exactly the Layer 1 failure this wave was told not to repeat")

        again = process_pending(org_id=org, store=pg_store, llm=None,
                                crypto_key=get_settings().crypto_key, eval_time=at)
        assert _count(engine, HISTORY_TABLE, org) == written, (
            "a second sweep in the same period grew the table")
        assert again["processed"] == 0
    finally:
        _drop_org(engine, org)


# ══════════════════════════════════════════════════ 9 · ERASURE

@pytest.mark.pg
@pytest.mark.parametrize("table", ["metric_history", "cohort_membership", "cohort_definitions",
                                   "peer_baselines"])
def test_every_table_this_wave_added_is_on_the_erasure_list(table) -> None:
    """`_ORG_SCOPED_TABLES` executes with no try/except, so a name missing from it does not fail —
    it leaks. Named as a parametrize rather than a loop so a missing one says WHICH."""
    from genios_engine.api.account_routes import _ORG_SCOPED_TABLES
    assert table in _ORG_SCOPED_TABLES, (
        f"{table} survives a tenant erasure — the loop is silent about omissions")


@pytest.mark.pg
def test_deleting_an_org_leaves_no_row_of_this_waves_tables_behind(pg_store) -> None:
    """Erasure proven the way the brief asks: insert for a disposable org, delete the org, assert
    zero rows. BOTH paths are exercised because they fail differently — `/reset` runs the named
    list (a missing name leaks) and account deletion runs the FK cascade (a missing `references
    orgs` leaks, and it leaks a row the list would have caught).
    """
    from genios_engine.api.account_routes import _ORG_SCOPED_TABLES

    engine = pg_store.engine
    tables = ("metric_history", "cohort_membership", "cohort_definitions", "peer_baselines")
    at = datetime(2026, 3, 15, tzinfo=timezone.utc)

    for path in ("reset", "cascade"):
        org = f"org_h12_erase_{path}"
        _make_org(engine, org)
        try:
            with engine.begin() as conn:
                conn.execute(text(
                    "insert into cohort_definitions (cohort_id, org_id, name, node_type, "
                    "  predicate, created_by) values (:c, :o, 'probe', 'company', "
                    "  cast('{\"op\": \"exists\", \"fact\": \"node.name\"}' as jsonb), 'probe')"),
                    {"c": f"co_{org}", "o": org})
                conn.execute(text(
                    "insert into cohort_membership (org_id, cohort_id, node_id, joined_at) "
                    "values (:o, :c, 'n_1', :j)"),
                    {"o": org, "c": f"co_{org}", "j": at - timedelta(days=1)})
                conn.execute(text(
                    "insert into peer_baselines (org_id, cohort_id, metric, computed_at, "
                    "  population, p10_bp, p25_bp, p50_bp, p75_bp, p90_bp, unit) "
                    "values (:o, :c, :m, :at, 10, 1, 2, 3, 4, 5, 'count')"),
                    {"o": org, "c": f"co_{org}", "m": TOUCHES, "at": at})
            PostgresMetricHistory(engine).put(
                org, [_point("n_1", _month(2026, 3), 7)],
                reason=SampleReason.SCHEDULED, sampled_at=at)
            for table in tables:
                assert _count(engine, table, org) == 1, f"{table} was not seeded"

            if path == "reset":
                with engine.begin() as conn:      # exactly what api/account_routes._wipe does
                    for table in _ORG_SCOPED_TABLES:
                        conn.execute(text(f"delete from {table} where org_id=:o"), {"o": org})
            else:
                _drop_org(engine, org)

            for table in tables:
                assert _count(engine, table, org) == 0, (
                    f"{table} kept rows after the {path} path — a deleted tenant's data survives")
        finally:
            _drop_org(engine, org)


# ══════════════════════════════════════════════════ 10 · THE H1 DENSITY COMMAND

@pytest.mark.pg
def test_the_density_report_measures_the_growth_this_wave_was_told_to_bound(pg_store) -> None:
    """Doc 09's H1 block runs two commands and the second is
    `python scripts/history_density_report.py --org <pilot>`. It did not exist.

    A gate that does not measure growth cannot catch it: `expertise_packages` reached 181 MB with
    every test around it green, because the only number that would have caught it was rows and
    bytes on the live table and nobody was printing one. So the script is built and this drives
    it against a seeded tenant, asserting the three numbers a reader acts on — rows, series and
    the projected steady state — and then asserting the two BREACH lines, because a report that
    cannot say "the trim did not run" is a report that always looks fine.
    """
    from scripts.history_density_report import _fetch, render

    org = "org_h12_report"
    engine = pg_store.engine
    _make_org(engine, org)
    store = PostgresMetricHistory(engine)
    try:
        at = datetime(2026, 4, 1, tzinfo=timezone.utc)
        for month in (1, 2, 3):
            store.put(org, [_point(f"n{i}", _month(2026, month), 10 + i) for i in range(4)],
                      reason=SampleReason.SCHEDULED, sampled_at=at)
        with engine.connect() as conn:
            lines = render(_fetch(conn, org, at), org, at)
        body = "\n".join(lines)
        assert "rows                12" in body, body
        assert "series (node,metric)       4" in body, body
        assert "points/series       max 3, median 3" in body, body
        # Monthly spacing, so the projection must use the 24-period horizon and not the 104-week
        # one — the two differ by more than 4x and picking the wrong one is the whole error.
        assert "x 24 periods retained" in body, body
        assert "duplicate period keys 0" in body, body
        assert "!!" not in body, f"a healthy tenant reported a breach:\n{body}"

        # A row older than the retention horizon is a prune that has not run — the case that
        # bites a tenant who stopped draining, which is exactly when nobody is looking.
        with engine.connect() as conn:
            stale = render(_fetch(conn, org, datetime(2030, 1, 1, tzinfo=timezone.utc)),
                           org, datetime(2030, 1, 1, tzinfo=timezone.utc))
        assert any("older than the" in line and "!!" in line for line in stale), stale
    finally:
        _drop_org(engine, org)


def test_the_density_report_never_writes_and_never_reaches_a_default_database() -> None:
    """Two properties of the SCRIPT rather than of its output, and both are one edit from being
    lost: it must contain no statement that writes, and it must resolve its target through
    `scripts/_db.py` — the module that refuses to inherit `.env`'s production URL."""
    import pathlib

    source = (pathlib.Path(__file__).resolve().parents[3]
              / "scripts" / "history_density_report.py").read_text()
    body = source.split('"""', 2)[2]          # past the module docstring, which names the verbs
    for verb in ("insert into", "update set", "delete from", "drop table", "truncate"):
        assert verb not in body.lower(), f"the density report contains a {verb!r} — it is read-only"
    assert "resolve_database_url" in body, (
        "the script resolves its own database — on a machine with a .env that is production")
    assert "get_settings" not in body
