"""L2.4.6 — the peer baseline (BLG-11). The gate for `context/analytic/peer_baseline.py`.

    pytest tests/context/analytic/test_peer_baseline.py -q

Doc 04 gives this component two units, and the tests below are grouped by the thing each one can
get wrong:

* **the ladder** (U1) — a healthy population, the floor, gaps that are not zeros, determinism;
* **the deferral** (U2) — `cross_org_baseline` refuses, always, by decision;
* **DISCLOSURE** — the test this component exists to survive. A baseline is an aggregate, and an
  aggregate over a small population is a roll call in a hat: five nearest-rank rungs over six
  members ARE the sorted six. `test_a_member_s_reading_cannot_be_recovered_from_the_ladder`
  builds two populations that differ in one member's reading and asserts the two ladders are
  byte-identical — so the arithmetic that would recover that member does not exist.

`test_the_sweep_computes_baselines` is the one that matters most: it drives
`context/runner.process_pending`, the function every sync and upload route calls, against a real
Postgres. Every other test here constructs the module itself and would pass in a build where the
call in `runner.py` had been deleted.
"""

from __future__ import annotations

import ast
import inspect
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from sqlalchemy import text

from genios_engine.contracts.analytic import MetricPoint, MetricUnit
from genios_engine.context.analytic.cohort import (COHORT_DEFINITION_TABLE,
                                                   COHORT_MEMBERSHIP_TABLE, SYSTEM_AUTHOR)
from genios_engine.context.analytic.history import MetricGrain, period_start
from genios_engine.context.analytic.peer_baseline import (BASELINE_RUNGS_BP,
                                                          BASELINE_SMOOTHING_WINDOW,
                                                          BASELINE_TABLE,
                                                          MIN_BASELINE_POPULATION,
                                                          STALE_AFTER_PERIODS,
                                                          BaselineRefusal, BaselineRefusalReason,
                                                          PeerBaseline, baseline_from_points,
                                                          compute_baseline, cross_org_baseline,
                                                          load_baseline, load_baselines,
                                                          metric_grain, periods_back,
                                                          prune_baselines,
                                                          refresh_baselines_for_drain,
                                                          save_baselines, smoothed_rung,
                                                          staleness_floor)

AT = datetime(2026, 3, 11, 9, 0, tzinfo=timezone.utc)
ORG = "org_peer_baseline"
COHORT = "cohort_growth_accounts"
METRIC = "account.arr_minor_units"


def _values(readings: list[int], prefix: str = "n") -> dict[str, int]:
    return {f"{prefix}_{i:02d}": v for i, v in enumerate(readings)}


def _baseline(readings: list[int], *, unknown: int = 0, cohort: str = COHORT):
    return compute_baseline(org_id=ORG, cohort_id=cohort, metric=METRIC,
                            values=_values(readings), unit=MetricUnit.COUNT, eval_time=AT,
                            unknown=unknown)


# =================================================================================================
# U1 · THE LADDER OVER A HEALTHY POPULATION
# =================================================================================================

def test_a_healthy_population_gets_an_ordered_five_rung_ladder() -> None:
    readings = [100 * i for i in range(1, 21)]          # 100..2000, twenty members
    out = _baseline(readings)
    assert isinstance(out, PeerBaseline) and out.is_baseline
    assert out.population == 20
    assert out.p10_bp <= out.p25_bp <= out.p50_bp <= out.p75_bp <= out.p90_bp
    assert out.ladder == tuple(sorted(out.ladder))
    assert out.org_id == ORG and out.cohort_id == COHORT and out.metric == METRIC
    # `computed_at` is DERIVED from eval_time (the ISO week start), never read from a clock.
    assert out.computed_at == period_start(AT, MetricGrain.WEEK)


def test_the_ladder_brackets_the_population_it_was_cut_from() -> None:
    """A baseline that did not sit inside its own population would be arithmetic, not a norm."""
    readings = [7, 11, 13, 20, 24, 31, 33, 40, 44, 51, 58, 62, 70, 77, 81, 90, 96, 101, 110, 118]
    out = _baseline(readings)
    assert isinstance(out, PeerBaseline)
    assert min(readings) < out.p10_bp < out.p50_bp < out.p90_bp < max(readings)


@pytest.mark.parametrize("readings, q_bp, expected", [
    # Twelve members, window of three: p50's nearest-rank index is (5000*11)//10000 = 5, and the
    # rung is the mean of members 4, 5 and 6.
    ([10 * i for i in range(1, 13)], 5_000, (50 + 60 + 70) // 3),
    # p10's index is 1, so the window CLAMPS to the three lowest — never the minimum alone.
    ([10 * i for i in range(1, 13)], 1_000, (10 + 20 + 30) // 3),
    # p90's index is 9, window [8, 9, 10]; the maximum is never published either.
    ([10 * i for i in range(1, 13)], 9_000, (90 + 100 + 110) // 3),
    # Integer division only: a sum that does not divide evenly FLOORS, on every machine.
    ([1, 1, 2, 3, 3, 3, 4, 5, 6, 7, 8, 9], 5_000, (3 + 3 + 4) // 3),
    # Negative readings floor too (a metric may be signed) and stay ordered.
    ([-9, -8, -7, -6, -5, -4, -3, -2, -1, 0, 1, 2], 2_500, (-8 + -7 + -6) // 3),
])
def test_a_rung_is_the_mean_of_its_window(readings, q_bp, expected) -> None:
    assert smoothed_rung(sorted(readings), q_bp) == expected


def test_no_rung_publishes_an_extreme_and_every_rung_spans_three_members() -> None:
    """The disclosure mechanism at the rung level.

    Two claims, and only two, because only two are true. The extremes are the readings a peer
    baseline leaks first — the largest customer and the smallest — and they are never published.
    And every rung is an average over at least `BASELINE_SMOOTHING_WINDOW` members, so no rung is
    a republication of one member's number. A rung may still COINCIDE with some member's reading
    (a mean of three lands where a fourth happens to sit); that is arithmetic, not disclosure, and
    the claim that matters is non-invertibility, proved in
    `test_a_members_reading_cannot_be_recovered_from_the_ladder`.
    """
    readings = [3, 17, 29, 44, 61, 78, 95, 110, 131, 152, 170, 199, 210, 233, 260, 288]
    out = _baseline(readings)
    assert isinstance(out, PeerBaseline)
    assert min(readings) not in out.ladder and max(readings) not in out.ladder
    assert out.ladder == tuple(smoothed_rung(sorted(readings), q) for q in BASELINE_RUNGS_BP)
    for q_bp in BASELINE_RUNGS_BP:
        one = smoothed_rung(sorted(readings), q_bp, window=1)      # the raw order statistic
        assert one in readings, "window=1 is the member's own reading — that is what is avoided"
        assert BASELINE_SMOOTHING_WINDOW >= 3


def test_the_window_never_exceeds_the_population() -> None:
    assert smoothed_rung([5, 9], 5_000, window=7) == (5 + 9) // 2
    with pytest.raises(ValueError):
        smoothed_rung([], 5_000)
    with pytest.raises(ValueError):
        smoothed_rung([1, 2, 3], 5_000, window=0)


# =================================================================================================
# THE FLOOR — a refusal is information
# =================================================================================================

def test_at_the_floor_a_baseline_is_produced() -> None:
    out = _baseline([10 * i for i in range(1, MIN_BASELINE_POPULATION + 1)])
    assert isinstance(out, PeerBaseline)
    assert out.population == MIN_BASELINE_POPULATION


def test_below_the_floor_it_refuses_and_names_the_population() -> None:
    out = _baseline([10 * i for i in range(1, MIN_BASELINE_POPULATION)])
    assert isinstance(out, BaselineRefusal) and not out.is_baseline
    assert out.reason is BaselineRefusalReason.INSUFFICIENT_POPULATION
    assert out.population == MIN_BASELINE_POPULATION - 1
    assert out.cohort_id == COHORT and out.metric == METRIC
    assert str(MIN_BASELINE_POPULATION) in out.detail


def test_a_baseline_object_under_the_floor_is_unconstructible() -> None:
    """The floor is enforced twice: once as a refusal a card can render, once in the type, so a
    thin ladder cannot be assembled by a caller that skipped `compute_baseline`."""
    with pytest.raises(ValueError, match="discloses its members"):
        PeerBaseline(org_id=ORG, cohort_id=COHORT, metric=METRIC, unit=MetricUnit.COUNT,
                     p10_bp=1, p25_bp=2, p50_bp=3, p75_bp=4, p90_bp=5,
                     population=MIN_BASELINE_POPULATION - 1, computed_at=AT)


def test_an_unordered_ladder_is_refused_by_the_type() -> None:
    with pytest.raises(ValueError, match="ordered"):
        PeerBaseline(org_id=ORG, cohort_id=COHORT, metric=METRIC, unit=MetricUnit.COUNT,
                     p10_bp=9, p25_bp=2, p50_bp=3, p75_bp=4, p90_bp=5, population=20,
                     computed_at=AT)


def test_a_money_ladder_must_name_its_currency() -> None:
    with pytest.raises(ValueError, match="currency"):
        PeerBaseline(org_id=ORG, cohort_id=COHORT, metric=METRIC, unit=MetricUnit.MINOR_UNITS,
                     p10_bp=1, p25_bp=2, p50_bp=3, p75_bp=4, p90_bp=5, population=20,
                     computed_at=AT)
    with pytest.raises(ValueError, match="meaningless"):
        PeerBaseline(org_id=ORG, cohort_id=COHORT, metric=METRIC, unit=MetricUnit.COUNT,
                     currency="USD", p10_bp=1, p25_bp=2, p50_bp=3, p75_bp=4, p90_bp=5,
                     population=20, computed_at=AT)


def test_a_float_reading_is_refused_rather_than_rounded() -> None:
    with pytest.raises(TypeError):
        compute_baseline(org_id=ORG, cohort_id=COHORT, metric=METRIC,
                         values={**_values([10 * i for i in range(1, 20)]), "n_99": 4.5},
                         unit=MetricUnit.COUNT, eval_time=AT)


# =================================================================================================
# GAPS ARE NOT ZEROS
# =================================================================================================

def test_a_gap_is_not_a_zero_and_does_not_drag_the_ladder_down() -> None:
    readings = [1_000 + 100 * i for i in range(20)]
    with_gaps = _baseline(readings, unknown=6)
    clean = _baseline(readings)
    assert isinstance(with_gaps, PeerBaseline) and isinstance(clean, PeerBaseline)
    assert with_gaps.ladder == clean.ladder, (
        "six members with no reading changed the ladder — they were counted as readings of nought")
    assert with_gaps.population == 20, "population counts KNOWN readings, not members"


def test_too_many_gaps_refuse_rather_than_describe_whoever_was_instrumented() -> None:
    out = _baseline([1_000 + 100 * i for i in range(20)], unknown=40)
    assert isinstance(out, BaselineRefusal)
    assert out.reason is BaselineRefusalReason.INSUFFICIENT_COVERAGE
    assert "not a zero" in out.detail


def test_unknown_points_are_carried_through_baseline_from_points() -> None:
    """`known=False` carries no value by contract; the series path must count such a member as a
    gap, and a member whose ONLY points are gaps must not become a zero in the ladder."""
    points = []
    for i in range(20):
        points.append(MetricPoint(subject_node_id=f"n_{i:02d}", metric=METRIC,
                                  value_bp=1_000 + 100 * i, unit=MetricUnit.COUNT,
                                  observed_at=AT - timedelta(days=7), known=True))
    for i in range(20, 24):                     # four members measured at nothing
        points.append(MetricPoint(subject_node_id=f"n_{i:02d}", metric=METRIC, value_bp=None,
                                  unit=MetricUnit.COUNT, observed_at=AT - timedelta(days=7),
                                  known=False))
    out = baseline_from_points(org_id=ORG, cohort_id=COHORT, metric=METRIC, points=points,
                               eval_time=AT)
    assert isinstance(out, PeerBaseline)
    assert out.population == 20
    assert out.ladder == _baseline([1_000 + 100 * i for i in range(20)]).ladder
    assert out.p10_bp > 0, "a member with no reading was counted as zero"


def test_the_series_path_takes_the_latest_reading_at_or_before_eval_time() -> None:
    points = []
    for i in range(20):
        points.append(MetricPoint(subject_node_id=f"n_{i:02d}", metric=METRIC, value_bp=10,
                                  unit=MetricUnit.COUNT, observed_at=AT - timedelta(days=30),
                                  known=True))
        points.append(MetricPoint(subject_node_id=f"n_{i:02d}", metric=METRIC,
                                  value_bp=1_000 + 100 * i, unit=MetricUnit.COUNT,
                                  observed_at=AT - timedelta(days=1), known=True))
        points.append(MetricPoint(subject_node_id=f"n_{i:02d}", metric=METRIC, value_bp=999_999,
                                  unit=MetricUnit.COUNT, observed_at=AT + timedelta(days=1),
                                  known=True))          # the future is not read
    out = baseline_from_points(org_id=ORG, cohort_id=COHORT, metric=METRIC, points=points,
                               eval_time=AT)
    assert isinstance(out, PeerBaseline)
    assert out.ladder == _baseline([1_000 + 100 * i for i in range(20)]).ladder


def test_mixed_units_refuse_rather_than_average_money_with_counts() -> None:
    points = [MetricPoint(subject_node_id=f"n_{i:02d}", metric=METRIC, value_bp=100 + i,
                          unit=MetricUnit.COUNT, observed_at=AT, known=True) for i in range(19)]
    points.append(MetricPoint(subject_node_id="n_99", metric=METRIC, value_bp=100,
                              unit=MetricUnit.MINOR_UNITS, currency="USD", observed_at=AT,
                              known=True))
    out = baseline_from_points(org_id=ORG, cohort_id=COHORT, metric=METRIC, points=points,
                               eval_time=AT)
    assert isinstance(out, BaselineRefusal)
    assert out.reason is BaselineRefusalReason.MIXED_UNITS


def test_a_point_of_another_metric_in_the_ladder_is_a_programming_error() -> None:
    points = [MetricPoint(subject_node_id="n_00", metric="support.ticket_count_28d", value_bp=1,
                          unit=MetricUnit.COUNT, observed_at=AT, known=True)]
    with pytest.raises(ValueError, match="two metrics in one ladder"):
        baseline_from_points(org_id=ORG, cohort_id=COHORT, metric=METRIC, points=points,
                             eval_time=AT)


# =================================================================================================
# DISCLOSURE — the law this component is built around
# =================================================================================================

def test_a_members_reading_cannot_be_recovered_from_the_ladder() -> None:
    """THE TEST. Two populations that differ in a member's reading, one identical ladder.

    A reader holding the baseline, the population count, the rung definitions and their OWN
    reading still cannot solve for anybody else's, because the map from population to ladder is
    not injective: the readings at index 6 below are different in the two runs and every published
    rung is the same. There is no arithmetic to invert, which is a stronger statement than "the
    numbers look aggregated".
    """
    base = [10, 20, 30, 40, 50, 60, 70, 80, 90, 100, 110, 120, 130, 140, 150, 160, 170, 180, 190,
            200]
    other = list(base)
    other[6] = 74                       # one member's reading, changed, order preserved
    assert base != other

    first, second = _baseline(base), _baseline(other)
    assert isinstance(first, PeerBaseline) and isinstance(second, PeerBaseline)
    assert first.as_row() == second.as_row(), (
        "the ladder moved with one member's reading — a reader who knows the rest of the "
        "population can subtract their way to that member")
    assert 74 not in first.ladder and 70 not in first.ladder


def test_the_ladder_carries_no_member_identity() -> None:
    out = _baseline([10 * i for i in range(1, 21)], cohort="cohort_named_group")
    assert isinstance(out, PeerBaseline)
    row = out.as_row()
    # Everything that leaves this module: five aggregates, a population count, a unit, a period,
    # and the two names (tenant + cohort) that make the aggregate checkable. No node ids.
    assert set(row) == {"org_id", "cohort_id", "metric", "p10_bp", "p25_bp", "p50_bp", "p75_bp",
                        "p90_bp", "unit", "currency", "population", "computed_at"}
    assert not any(isinstance(v, str) and v.startswith("n_") for v in row.values())


def test_cross_org_baseline_refuses_by_decision_not_by_omission() -> None:
    """U2. Doc 04: *"Every baseline in v2 is within one tenant."*"""
    out = cross_org_baseline(org_ids=["org_a", "org_b", "org_c"], cohort_id=COHORT, metric=METRIC,
                             eval_time=AT)
    assert isinstance(out, BaselineRefusal)
    assert out.reason is BaselineRefusalReason.CROSS_ORG_DEFERRED
    assert "deferred" in out.detail and "one tenant" in out.detail
    # Even for a single org: the cross-org door never serves a within-tenant answer.
    single = cross_org_baseline(org_ids=["org_a"], cohort_id=COHORT, metric=METRIC, eval_time=AT)
    assert single.reason is BaselineRefusalReason.CROSS_ORG_DEFERRED


def test_no_statement_in_the_module_reads_more_than_one_tenant() -> None:
    """The isolation law, read off the source. Every SQL string here filters on exactly one
    `org_id`, and none of them takes a LIST of tenants."""
    source = Path(inspect.getsourcefile(compute_baseline)).read_text()
    tree = ast.parse(source)
    statements = [n.value for n in ast.walk(tree)
                  if isinstance(n, ast.Assign) and isinstance(n.value, ast.Call)
                  and getattr(n.value.func, "id", "") == "text"]
    assert statements, "no SQL found — this test has stopped checking anything"
    seen_reads = 0
    for call in statements:
        sql = " ".join("".join(part.value for part in ast.walk(call.args[0])
                               if isinstance(part, ast.Constant)
                               and isinstance(part.value, str)).split())
        assert "org_id = any" not in sql and "org_id in (" not in sql, (
            f"a statement reads a LIST of tenants: {sql}")
        if sql.startswith("insert"):
            # The write names its tenant per row and cannot be pointed at a second one.
            assert ":org_id" in sql and sql.count("org_id") >= 2, sql
            continue
        seen_reads += 1
        assert "org_id = :o" in sql or "m.org_id = :o" in sql, (
            f"a read that does not filter on exactly one tenant: {sql}")
    assert seen_reads >= 4, "the reads this test guards have moved out of the module"


# =================================================================================================
# DETERMINISM
# =================================================================================================

def test_the_same_population_at_the_same_eval_time_is_byte_identical() -> None:
    readings = [17 * i + (i * i) % 13 for i in range(1, 41)]
    runs = [_baseline(readings) for _ in range(5)]
    shuffled = compute_baseline(org_id=ORG, cohort_id=COHORT, metric=METRIC,
                                values=dict(reversed(list(_values(readings).items()))),
                                unit=MetricUnit.COUNT, eval_time=AT)
    assert all(r.as_row() == runs[0].as_row() for r in runs)
    assert shuffled.as_row() == runs[0].as_row(), "the ladder depended on dict insertion order"


def test_no_float_appears_in_the_measure_path() -> None:
    source = Path(inspect.getsourcefile(compute_baseline)).read_text()
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, float):
            pytest.fail(f"a float literal reached the measure path: {node.value}")
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
            pytest.fail("true division in a measure path — a rung decided by a binary expansion")


def test_eval_time_is_a_parameter_and_the_module_reads_no_clock() -> None:
    source = Path(inspect.getsourcefile(compute_baseline)).read_text()
    assert "datetime.now" not in source and "utcnow" not in source
    assert "eval_time" in inspect.signature(compute_baseline).parameters
    assert "eval_time" in inspect.signature(refresh_baselines_for_drain).parameters


# =================================================================================================
# STORAGE AND THE REAL REQUEST PATH
# =================================================================================================

def _seed(store, org: str, *, count: int, at: datetime, cohort: str, metric: str,
          first: int = 1_000_000, step: int = 100_000, missing: int = 0, dark: int = 0,
          money: int = 0) -> None:
    """One tenant: an org, `count` nodes, a cohort they all belong to, and one metric point each
    (bar `missing` of them, which get no row at all — the gap the ladder must not read as zero).

    `dark` writes a REAL row for the first N members, dated 300 days back — a connector that died
    last winter and never wrote again. It is deliberately not the same thing as `missing`: the row
    exists, so a read bounded only from above finds it and counts the member as measured. That is
    the whole of D6, and it is why this parameter is here rather than a second `missing`.

    `money` writes the first N members' readings in minor units instead of counts, so the sweep
    sees one cohort read in two units.
    """
    week = period_start(at, MetricGrain.WEEK)
    with store.engine.begin() as conn:
        conn.execute(text("insert into orgs (id, name) values (:o, 'Baseline tests') "
                          "on conflict (id) do nothing"), {"o": org})
        conn.execute(text(
            f"insert into {COHORT_DEFINITION_TABLE} "
            "  (cohort_id, org_id, name, node_type, predicate, created_by, created_at, active) "
            "values (:c, :o, :n, 'company', cast('{}' as jsonb), :by, :at, true) "
            "on conflict (cohort_id) do nothing"),
            {"c": cohort, "o": org, "n": "Baseline peer group", "by": SYSTEM_AUTHOR, "at": at})
        for i in range(count):
            node_id = f"{org}_n_{i:02d}"
            conn.execute(text(
                "insert into graph_nodes (node_id, version, org_id, node_type, display_name, "
                "  valid_from) values (:n, 1, :o, 'company', :d, :vf) on conflict do nothing"),
                {"n": node_id, "o": org, "d": f"Account {i}", "vf": at - timedelta(days=90)})
            conn.execute(text(
                f"insert into {COHORT_MEMBERSHIP_TABLE} "
                "  (org_id, cohort_id, node_id, joined_at, left_at, miss_streak, evaluated_at) "
                "values (:o, :c, :n, :j, null, 0, :j) on conflict do nothing"),
                {"o": org, "c": cohort, "n": node_id, "j": week - timedelta(days=14)})
            if i >= count - missing:
                continue                                   # no metric row: an honest gap
            observed = week - timedelta(days=300 if i < dark else 7)
            unit, currency = ("minor_units", "USD") if i < money else ("count", None)
            conn.execute(text(
                "insert into metric_history (org_id, subject_node_id, metric, value_bp, unit, "
                "  currency, observed_at, sampled_at, sample_reason) "
                "values (:o, :n, :m, :v, :u, :cur, :at, :at, 'scheduled') "
                "on conflict do nothing"),
                {"o": org, "n": node_id, "m": metric, "v": first + step * i, "u": unit,
                 "cur": currency, "at": observed})


def _drop_org(store, org: str) -> None:
    from genios_engine.api.account_routes import _ORG_SCOPED_TABLES
    with store.engine.begin() as conn:
        for table in _ORG_SCOPED_TABLES:
            conn.execute(text(f"delete from {table} where org_id=:o"), {"o": org})
        conn.execute(text("delete from orgs where id=:o"), {"o": org})


@pytest.mark.pg
def test_a_baseline_round_trips_and_is_read_as_of_a_moment(pg_store) -> None:
    """A March ladder must still be readable in September AS March's ladder."""
    org = f"{ORG}_storage"
    _drop_org(pg_store, org)
    _seed(pg_store, org, count=20, at=AT, cohort=COHORT, metric=METRIC)
    try:
        march = compute_baseline(org_id=org, cohort_id=COHORT, metric=METRIC,
                                 values=_values([100 * i for i in range(1, 21)]),
                                 unit=MetricUnit.COUNT, eval_time=AT)
        september = compute_baseline(org_id=org, cohort_id=COHORT, metric=METRIC,
                                     values=_values([900 * i for i in range(1, 21)]),
                                     unit=MetricUnit.COUNT,
                                     eval_time=AT + timedelta(days=180))
        assert save_baselines(pg_store.engine, [march, september]) == 2

        read_march = load_baseline(pg_store.engine, org, COHORT, METRIC, as_of=AT)
        read_sept = load_baseline(pg_store.engine, org, COHORT, METRIC,
                                  as_of=AT + timedelta(days=200))
        assert read_march is not None and read_march.as_row() == march.as_row()
        assert read_sept.as_row() == september.as_row()
        assert load_baseline(pg_store.engine, org, COHORT, METRIC,
                             as_of=AT - timedelta(days=30)) is None
        # Idempotent within a period: the same week's ladder overwrites, never appends.
        save_baselines(pg_store.engine, [march])
        with pg_store.engine.connect() as conn:
            rows = conn.execute(text(f"select count(*) from {BASELINE_TABLE} where org_id=:o"),
                                {"o": org}).scalar()
        assert rows == 2
    finally:
        _drop_org(pg_store, org)


@pytest.mark.pg
def test_retention_drops_ladders_past_the_history_horizon(pg_store) -> None:
    org = f"{ORG}_retention"
    _drop_org(pg_store, org)
    _seed(pg_store, org, count=20, at=AT, cohort=COHORT, metric=METRIC)
    try:
        old = compute_baseline(org_id=org, cohort_id=COHORT, metric=METRIC,
                               values=_values([100 * i for i in range(1, 21)]),
                               unit=MetricUnit.COUNT, eval_time=AT - timedelta(days=365 * 3))
        save_baselines(pg_store.engine, [old])
        assert prune_baselines(pg_store.engine, org, eval_time=AT) == 1
        assert prune_baselines(pg_store.engine, org, eval_time=AT) == 0
    finally:
        _drop_org(pg_store, org)


@pytest.mark.pg
def test_one_tenants_readings_never_reach_another_tenants_baseline(pg_store) -> None:
    """The isolation law against a real database. Two orgs, the same cohort id, wildly different
    readings: each ladder must be computable from its own tenant alone."""
    a, b = f"{ORG}_iso_a", f"{ORG}_iso_b"
    for org in (a, b):
        _drop_org(pg_store, org)
    _seed(pg_store, a, count=20, at=AT, cohort=f"{a}_c", metric=METRIC, first=1_000, step=10)
    _seed(pg_store, b, count=20, at=AT, cohort=f"{b}_c", metric=METRIC,
          first=90_000_000, step=1_000_000)
    try:
        refresh_baselines_for_drain(pg_store, a, eval_time=AT)
        refresh_baselines_for_drain(pg_store, b, eval_time=AT)
        ladder_a = load_baseline(pg_store.engine, a, f"{a}_c", METRIC, as_of=AT)
        ladder_b = load_baseline(pg_store.engine, b, f"{b}_c", METRIC, as_of=AT)
        assert ladder_a is not None and ladder_b is not None
        assert ladder_a.p90_bp < 100_000, "tenant B's readings reached tenant A's ladder"
        assert ladder_b.p10_bp > 1_000_000, "tenant A's readings reached tenant B's ladder"
        assert ladder_a.population == 20 and ladder_b.population == 20
        # And neither tenant's ladder is even visible from the other's cohort id.
        assert load_baseline(pg_store.engine, a, f"{b}_c", METRIC, as_of=AT) is None
    finally:
        for org in (a, b):
            _drop_org(pg_store, org)


@pytest.mark.pg
def test_a_thin_cohort_is_refused_not_written(pg_store) -> None:
    org = f"{ORG}_thin"
    _drop_org(pg_store, org)
    _seed(pg_store, org, count=MIN_BASELINE_POPULATION - 1, at=AT, cohort=COHORT, metric=METRIC)
    try:
        sweep = refresh_baselines_for_drain(pg_store, org, eval_time=AT)
        assert sweep.written == 0 and sweep.refused == 1
        assert sweep.refusals[0].reason is BaselineRefusalReason.INSUFFICIENT_POPULATION
        assert load_baseline(pg_store.engine, org, COHORT, METRIC, as_of=AT) is None
    finally:
        _drop_org(pg_store, org)


@pytest.mark.pg
def test_members_with_no_metric_row_are_gaps_not_zeros_on_the_real_read(pg_store) -> None:
    org = f"{ORG}_gaps"
    _drop_org(pg_store, org)
    _seed(pg_store, org, count=24, at=AT, cohort=COHORT, metric=METRIC, missing=4)
    try:
        refresh_baselines_for_drain(pg_store, org, eval_time=AT)
        ladder = load_baseline(pg_store.engine, org, COHORT, METRIC, as_of=AT)
        assert ladder is not None
        assert ladder.population == 20, "a member with no row was counted as a reading"
        assert ladder.p10_bp >= 1_000_000, "a missing row was read as a zero and sank p10"
    finally:
        _drop_org(pg_store, org)


@pytest.mark.pg
def test_the_sweep_computes_baselines(pg_store) -> None:
    """`context/runner.process_pending` — the sweep both API routes call — reaches the baseline
    pass. Every other test in this file constructs the module itself and would pass in a build
    where the call in `runner.py` had been deleted.

    Driven with NO pending events on purpose: a baseline moves because the population moved, not
    because mail arrived, so the pass must run on a sweep that drained nothing.
    """
    from genios_engine.context.runner import process_pending
    from genios_engine.platform.config import get_settings

    org = f"{ORG}_wiring"
    _drop_org(pg_store, org)
    _seed(pg_store, org, count=20, at=AT, cohort=COHORT, metric=METRIC)
    try:
        out = process_pending(org_id=org, store=pg_store, llm=None,
                              crypto_key=get_settings().crypto_key, eval_time=AT)
        assert out["processed"] == 0, "no events: this sweep drained nothing"
        assert out["baselines_written"] > 0, (
            "the sweep reached no baseline pass — `refresh_baselines_for_drain` is not on the "
            "real request path")
        ladder = load_baseline(pg_store.engine, org, COHORT, METRIC, as_of=AT)
        assert ladder is not None and ladder.population == 20
        assert ladder.computed_at == period_start(AT, MetricGrain.WEEK)

        # A second sweep in the same week is an OVERWRITE, not a second row.
        process_pending(org_id=org, store=pg_store, llm=None,
                        crypto_key=get_settings().crypto_key, eval_time=AT + timedelta(hours=2))
        with pg_store.engine.connect() as conn:
            rows = conn.execute(text(
                f"select count(*) from {BASELINE_TABLE} where org_id=:o and cohort_id=:c"),
                {"o": org, "c": COHORT}).scalar()
        assert rows == 1, "a sweep replayed in one week appended a second ladder"
    finally:
        _drop_org(pg_store, org)


@pytest.mark.pg
def test_the_wiring_call_is_present_in_the_runner_source() -> None:
    """A structural backstop for the test above: it fails loudly if the call is deleted, even in a
    build where the sweep happens to write nothing."""
    from genios_engine.context import runner
    source = Path(inspect.getsourcefile(runner)).read_text()
    assert "refresh_baselines_for_drain" in source
    assert "baselines_written" in source


# =================================================================================================
# D6 · THE STALENESS HORIZON — the bound that makes INSUFFICIENT_COVERAGE reachable at all
# =================================================================================================

def test_the_staleness_horizon_is_three_periods_of_the_metrics_own_grain() -> None:
    """The arithmetic, pinned. Three periods INCLUSIVE of the current one, in the metric's grain,
    anchored on the period boundary so it cannot move inside a period."""
    assert STALE_AFTER_PERIODS == 3
    week_floor = staleness_floor(AT, MetricGrain.WEEK)
    assert week_floor == period_start(AT, MetricGrain.WEEK) - timedelta(days=14), (
        "the weekly horizon is this week and the two before it")
    assert staleness_floor(AT, MetricGrain.MONTH) == datetime(2026, 1, 1, tzinfo=timezone.utc), (
        "the monthly horizon is this month and the two before it")

    # ANCHORED, not sliding: every instant inside one week yields the same floor, which is what
    # makes two sweeps in a week classify the same members as dark.
    for hours in (0, 5, 71, 110):          # AT is a Wednesday; 110h is still inside its week
        assert staleness_floor(AT + timedelta(hours=hours), MetricGrain.WEEK) == week_floor

    # `periods=1` is the current period itself — the count includes it.
    assert periods_back(AT, MetricGrain.WEEK, 1) == period_start(AT, MetricGrain.WEEK)
    with pytest.raises(ValueError):
        periods_back(AT, MetricGrain.WEEK, 0)


def test_an_unregistered_metric_gets_the_finer_grain_so_the_refusal_is_easier_to_reach() -> None:
    """`account.arr_minor_units` is not in the sampler's registry. The fallback must be WEEK: a
    shorter horizon errs toward a named refusal, and the opposite error is a confident ladder."""
    assert metric_grain(METRIC) is MetricGrain.WEEK
    assert metric_grain("deal.stage_age_days") is MetricGrain.MONTH, "a registered grain is read"
    assert metric_grain("account.contact_breadth") is MetricGrain.WEEK


@pytest.mark.pg
def test_a_member_dark_for_ten_months_is_unknown_and_the_coverage_floor_refuses(pg_store) -> None:
    """D6/D7 · THE REFUSAL, PRODUCED BY THE PLUMBING AND NOT BY A LITERAL.

    Every `INSUFFICIENT_COVERAGE` test in this file before this one passed `unknown=` by hand, so
    the floor was proved in the arithmetic and never on the read path — which is exactly how a
    read bounded only by `observed_at <= :at` survived a green suite. Here nine of twenty members
    have a REAL metric row that a dead connector wrote 300 days ago. With no lower bound they come
    back as readings, `unknown` is 0, and the sweep publishes a twenty-member ladder over a
    population half of which nobody has measured since last winter.
    """
    org = f"{ORG}_dark"
    _drop_org(pg_store, org)
    _seed(pg_store, org, count=20, at=AT, cohort=COHORT, metric=METRIC, dark=9)
    try:
        sweep = refresh_baselines_for_drain(pg_store, org, eval_time=AT)
        assert sweep.written == 0, (
            "a ladder was published over a population nine of whose members have been dark for "
            "ten months — the read is not bounded from below")
        assert sweep.refused == 1
        refusal = sweep.refusals[0]
        assert refusal.reason is BaselineRefusalReason.INSUFFICIENT_COVERAGE
        assert refusal.population == 11, "the nine dark members were counted as readings"
        assert "9 of 20" in refusal.detail
        assert load_baseline(pg_store.engine, org, COHORT, METRIC, as_of=AT) is None
    finally:
        _drop_org(pg_store, org)


@pytest.mark.pg
def test_a_reading_at_the_edge_of_the_horizon_still_counts(pg_store) -> None:
    """The other side of the same bound: three periods is INCLUSIVE, so a member sampled two weeks
    ago is late, not dark, and the ladder is published. A horizon that cut here would delete real
    populations rather than dark ones."""
    org = f"{ORG}_edge"
    _drop_org(pg_store, org)
    _seed(pg_store, org, count=20, at=AT, cohort=COHORT, metric=METRIC)
    edge = staleness_floor(AT, MetricGrain.WEEK)
    with pg_store.engine.begin() as conn:
        conn.execute(text("update metric_history set observed_at = :e where org_id = :o"),
                     {"e": edge, "o": org})
    try:
        sweep = refresh_baselines_for_drain(pg_store, org, eval_time=AT)
        assert sweep.written == 1 and sweep.refused == 0
        ladder = load_baseline(pg_store.engine, org, COHORT, METRIC, as_of=AT)
        assert ladder is not None and ladder.population == 20
    finally:
        _drop_org(pg_store, org)


# =================================================================================================
# D4 · THE SWEEP PUBLISHES THROUGH `baseline_from_points`, WHICH IS WHY IT HAS A CALLER
# =================================================================================================

@pytest.mark.pg
def test_the_sweep_refuses_mixed_units_through_the_one_ladder_function(pg_store) -> None:
    """The sweep used to carry its own copy of the mixed-unit check, its own gap counter and its
    own "nobody has a reading" refusal, while `baseline_from_points` — which has all three — had
    no caller at all. The copy on the sweep was the copy that actually wrote rows and the one no
    pure test could reach.

    The detail string below belongs to `baseline_from_points` and to nothing else, so this asserts
    the drain really goes through it rather than through a second implementation that agrees today.
    """
    org = f"{ORG}_units"
    _drop_org(pg_store, org)
    _seed(pg_store, org, count=20, at=AT, cohort=COHORT, metric=METRIC, money=1)
    try:
        sweep = refresh_baselines_for_drain(pg_store, org, eval_time=AT)
        assert sweep.written == 0 and sweep.refused == 1
        refusal = sweep.refusals[0]
        assert refusal.reason is BaselineRefusalReason.MIXED_UNITS
        assert "five numbers with no meaning" in refusal.detail, (
            "the sweep is not publishing through `baseline_from_points` — there are two copies "
            "of the mixed-unit rule again")
    finally:
        _drop_org(pg_store, org)


# =================================================================================================
# D3 · THE LADDER HAS A READER ON A REAL REQUEST PATH
# =================================================================================================

@pytest.mark.pg
def test_the_baselines_route_reads_the_table_the_drain_writes(pg_store) -> None:
    """THE D3 TEST. `peer_baselines` was written on every drain and read back by NOTHING except a
    test — Layer 1's exact failure, and the reason X5 could not compose importance from it.

    This drives `GET /api/org/{org}/cohorts/{cohort_id}/baselines` through the FastAPI app against
    a real Postgres, so it fails in a build where the route is deleted, where `main.py` stops
    including the router, or where `load_baselines` stops reading rows the sweep wrote.

    Seeded against the CLOCK, because the route reads it at the process boundary and a March
    fixture is correctly dark from any later month (see `STALE_AFTER_PERIODS`).
    """
    from fastapi.testclient import TestClient

    from genios_engine.api import correlation_routes as R
    from genios_engine.context.graph_store import GraphStore
    from genios_engine.main import app
    from genios_engine.platform.auth import get_current_org

    org = f"{ORG}_route"
    now = datetime.now(timezone.utc)
    previous = R._graph
    R._graph = GraphStore(os.environ["GENIOS_TEST_DATABASE_URL"])
    app.dependency_overrides[get_current_org] = lambda: org
    _drop_org(pg_store, org)
    _seed(pg_store, org, count=20, at=now, cohort=COHORT, metric=METRIC)
    try:
        sweep = refresh_baselines_for_drain(pg_store, org, eval_time=now)
        assert sweep.written == 1, "nothing was written, so this test cannot prove a read"
        stored = load_baseline(pg_store.engine, org, COHORT, METRIC, as_of=now)
        assert stored is not None

        client = TestClient(app)
        body = client.get(f"/api/org/{org}/cohorts/{COHORT}/baselines").json()
        [ladder] = body["baselines"]
        assert ladder["metric"] == METRIC
        assert ladder["ladder"] == list(stored.ladder), (
            "the route did not return the ladder the drain wrote")
        assert ladder["rungs_bp"] == list(BASELINE_RUNGS_BP)
        assert ladder["population"] == 20

        # DISCLOSURE: five aggregates and a population — no member ever leaves through here.
        assert not any(isinstance(v, str) and v.startswith(f"{org}_n_")
                       for v in ladder.values())

        # The single-metric form reads the same row.
        one = client.get(f"/api/org/{org}/cohorts/{COHORT}/baselines",
                         params={"metric": METRIC}).json()
        assert one["baselines"] == body["baselines"]
        assert client.get(f"/api/org/{org}/cohorts/{COHORT}/baselines",
                          params={"metric": "support.ticket_count_28d"}).json()["baselines"] == []

        # POINT-IN-TIME: before the ladder was computed there is no ladder, and the emptiness is
        # explained rather than rendered as a failure.
        earlier = client.get(f"/api/org/{org}/cohorts/{COHORT}/baselines",
                             params={"as_of": (now - timedelta(days=30)).isoformat()})
        assert earlier.status_code == 200
        assert earlier.json()["baselines"] == []
        assert str(MIN_BASELINE_POPULATION) in earlier.json()["detail"]

        # A naive instant is refused rather than assumed UTC.
        assert client.get(f"/api/org/{org}/cohorts/{COHORT}/baselines",
                          params={"as_of": "2026-03-11T09:00:00"}).status_code == 422
        assert client.get(f"/api/org/other_org/cohorts/{COHORT}/baselines"
                          ).status_code == 403, "the path org must match the credential"
    finally:
        app.dependency_overrides.pop(get_current_org, None)
        _drop_org(pg_store, org)
        R._graph = previous


@pytest.mark.pg
def test_one_tenant_cannot_read_another_tenants_ladder_through_the_reader(pg_store) -> None:
    """`load_baselines` is a new statement and it carries the tenant like every other one here."""
    a, b = f"{ORG}_multi_a", f"{ORG}_multi_b"
    for org in (a, b):
        _drop_org(pg_store, org)
    _seed(pg_store, a, count=20, at=AT, cohort=COHORT, metric=METRIC, first=1_000, step=10)
    _seed(pg_store, b, count=20, at=AT, cohort=COHORT, metric=METRIC,
          first=90_000_000, step=1_000_000)
    try:
        refresh_baselines_for_drain(pg_store, a, eval_time=AT)
        refresh_baselines_for_drain(pg_store, b, eval_time=AT)
        mine = load_baselines(pg_store.engine, a, COHORT, as_of=AT)
        assert [l.metric for l in mine] == [METRIC]
        assert mine[0].p90_bp < 100_000, "tenant B's ladder was returned to tenant A"
        assert load_baselines(pg_store.engine, a, "cohort_nobody_has", as_of=AT) == ()
    finally:
        for org in (a, b):
            _drop_org(pg_store, org)
