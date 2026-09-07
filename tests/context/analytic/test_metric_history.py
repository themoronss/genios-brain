"""H1 · L2.4.1 — the metric history store, against real PostgreSQL.

**Gate H1** (`02-Layer-2-Plan/09-Build-Order-and-Acceptance.md`):

    pytest tests/context/analytic/test_history.py tests/context/analytic/test_sampler.py -q

This file is the history half of that gate, and it is written against the real table rather than
a fake for one reason: every claim L2.4.1 makes is a claim about a PRIMARY KEY, an UPSERT's
`where` clause, an index-driven DELETE and a `timestamptz` comparison. A double-buffered dict
would pass all of them and prove none.

What is proven here, in the doc's own order:

* the same (node, metric, period) written twice is ONE row, second wins — and an IDENTICAL
  re-sample does not move `sampled_at`, because moving it deletes the point from every earlier
  point-in-time read;
* a coverage gap reads back as `known=False, value_bp=None`, never 0 and never interpolated;
* `read_series` is DENSE — every period in range present, gaps explicit;
* retention: a per-series cap on the write path and a 24-month horizon on the drain path, with
  the prune running from `context/runner.process_pending` on a REAL request path;
* the table leaves with its tenant, through `account_routes._wipe` (the /reset loop) and through
  the org cascade (account deletion);
* `graph_facts` still overwrites — history is a SEPARATE table (doc 09 must-not-regress item 6).
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from sqlalchemy import text

from genios_engine.contracts.analytic import MetricPoint, MetricUnit
from genios_engine.contracts.units import UNKNOWN_CURRENCY
from genios_engine.context.analytic.history import (CORE_METRICS, HISTORY_TABLE,
                                                    MAX_RETAINED_PERIODS, MAX_SERIES_PERIODS,
                                                    RETENTION_MONTHS, InMemoryMetricHistory,
                                                    MetricDefinition, MetricGrain,
                                                    MetricRegistry, PostgresMetricHistory,
                                                    SampleReason, default_registry, months_before,
                                                    next_period, period_start, periods_between)

UTC = timezone.utc

#: Every time in this file is a parameter. Nothing here reads a clock.
EVAL_TIME = datetime(2026, 9, 6, 11, 30, tzinfo=UTC)
SAMPLED_AT = datetime(2026, 9, 6, 12, 0, tzinfo=UTC)

TOUCHES = "engagement.touch_count"
STAGE_AGE = "deal.stage_age_days"
#: A money metric, registered only in this file: `CORE_METRICS` names the two doc 04 names, and
#: the MINOR_UNITS rules (currency required, and what a GAP in a money series is denominated in)
#: need a third that the core registry deliberately does not carry.
ARR = MetricDefinition("account.arr_minor", MetricUnit.MINOR_UNITS, MetricGrain.MONTH,
                       retention_periods=RETENTION_MONTHS)
WEEKLY = MetricDefinition("thread.reply_count", MetricUnit.COUNT, MetricGrain.WEEK,
                          retention_periods=8)

REGISTRY = default_registry().with_definitions(ARR, WEEKLY)

NODE = "node_acc_alpha"
OTHER_NODE = "node_acc_beta"


# ── real Postgres, a disposable org, and no fixture that could reach production ───────────────

@pytest.fixture(scope="module")
def url() -> str:
    target = os.environ.get("GENIOS_TEST_DATABASE_URL")
    if not target:
        pytest.skip("GENIOS_TEST_DATABASE_URL not set — real-Postgres history tests skipped")
    return target


@pytest.fixture(scope="module")
def engine(url):
    from genios_engine.platform.db import get_engine
    return get_engine(url)


def _seed_org(engine, org: str) -> None:
    """A tenant of our own. NOT-NULL columns are discovered rather than listed, so a later
    migration adding one does not turn this file into an error."""
    with engine.begin() as conn:
        required = conn.execute(text(
            "select column_name, data_type from information_schema.columns where "
            "table_name='orgs' and is_nullable='NO' and column_default is null "
            "and column_name<>'id'")).all()
        cols, ph, vals = ["id"], [":id"], {"id": org}
        for row in required:
            cols.append(row.column_name)
            ph.append(f":{row.column_name}")
            kind = row.data_type
            vals[row.column_name] = ("2026-01-01T00:00:00Z" if ("time" in kind or "date" in kind)
                                     else 0 if ("int" in kind or "numeric" in kind
                                                or "double" in kind)
                                     else False if kind == "boolean"
                                     else "{}" if kind in ("json", "jsonb") else "scratch")
        conn.execute(text(f"insert into orgs ({', '.join(cols)}) values ({', '.join(ph)}) "
                          "on conflict (id) do nothing"), vals)


@pytest.fixture()
def org(engine, request):
    """One disposable org per test, deleted afterwards — which also re-proves the cascade on
    every single test rather than only in the erasure one."""
    name = f"org_hist_{abs(hash(request.node.name)) % 10_000_000}"
    _seed_org(engine, name)
    with engine.begin() as conn:
        conn.execute(text(f"delete from {HISTORY_TABLE} where org_id=:o"), {"o": name})
    yield name
    with engine.begin() as conn:
        conn.execute(text("delete from orgs where id=:o"), {"o": name})


@pytest.fixture()
def store(engine):
    return PostgresMetricHistory(engine, REGISTRY)


def month(index: int) -> datetime:
    """The start of a month, counted from January 2026. `index` months in, always UTC."""
    year, offset = divmod(2026 * 12 + index, 12)
    return datetime(year, offset + 1, 1, tzinfo=UTC)


def point(*, value: int | None = 12, at: datetime | None = None, metric: str = TOUCHES,
          unit: MetricUnit = MetricUnit.COUNT, node: str = NODE, known: bool = True,
          currency: str | None = None, coverage_ready: bool | None = True) -> MetricPoint:
    return MetricPoint(subject_node_id=node, metric=metric, value_bp=value, unit=unit,
                       currency=currency, observed_at=at or month(8), known=known,
                       coverage_ready=coverage_ready)


def rows_for(engine, org: str) -> list:
    with engine.begin() as conn:
        return conn.execute(text(
            f"select subject_node_id, metric, value_bp, unit, currency, observed_at, sampled_at, "
            f"sample_reason, coverage_ready from {HISTORY_TABLE} where org_id=:o "
            "order by metric, observed_at"), {"o": org}).all()


# ── U1 · the period key, the one function both write paths share ─────────────────────────────

@pytest.mark.parametrize("label,instant,grain,expected", [
    ("mid-month", datetime(2026, 3, 17, 9, 41, 12, tzinfo=UTC), MetricGrain.MONTH,
     datetime(2026, 3, 1, tzinfo=UTC)),
    ("first instant of a month", datetime(2026, 3, 1, tzinfo=UTC), MetricGrain.MONTH,
     datetime(2026, 3, 1, tzinfo=UTC)),
    ("last instant of a month", datetime(2026, 3, 31, 23, 59, 59, tzinfo=UTC), MetricGrain.MONTH,
     datetime(2026, 3, 1, tzinfo=UTC)),
    ("a Thursday", datetime(2026, 3, 19, 14, 0, tzinfo=UTC), MetricGrain.WEEK,
     datetime(2026, 3, 16, tzinfo=UTC)),
    ("the Monday itself", datetime(2026, 3, 16, tzinfo=UTC), MetricGrain.WEEK,
     datetime(2026, 3, 16, tzinfo=UTC)),
    ("a Sunday", datetime(2026, 3, 22, 23, 30, tzinfo=UTC), MetricGrain.WEEK,
     datetime(2026, 3, 16, tzinfo=UTC)),
    ("a non-UTC offset is normalised, not truncated in its own zone",
     datetime(2026, 3, 1, 2, 0, tzinfo=timezone(timedelta(hours=5, minutes=30))),
     MetricGrain.MONTH, datetime(2026, 2, 1, tzinfo=UTC)),
])
def test_the_period_key_is_one_shared_function(label, instant, grain, expected):
    """Doc 04 names "backfill and live sampling disagree on period boundaries" as the failure that
    produces phantom changepoints, and its mitigation is that both paths compute the boundary
    HERE. Idempotence is what lets `put` and `get` floor their arguments without a caller having
    to remember to."""
    assert period_start(instant, grain) == expected
    assert period_start(period_start(instant, grain), grain) == expected


def test_a_naive_datetime_is_never_assumed_to_be_utc():
    with pytest.raises(ValueError):
        period_start(datetime(2026, 3, 17), MetricGrain.MONTH)


@pytest.mark.parametrize("grain,start,expected", [
    (MetricGrain.MONTH, datetime(2026, 12, 1, tzinfo=UTC), datetime(2027, 1, 1, tzinfo=UTC)),
    (MetricGrain.MONTH, datetime(2026, 1, 1, tzinfo=UTC), datetime(2026, 2, 1, tzinfo=UTC)),
    (MetricGrain.WEEK, datetime(2026, 12, 28, tzinfo=UTC), datetime(2027, 1, 4, tzinfo=UTC)),
])
def test_the_year_boundary_is_integer_arithmetic_not_a_calendar_library(grain, start, expected):
    assert next_period(start, grain) == expected


def test_the_retention_horizon_does_not_move_within_a_month():
    """`months_before` is anchored on the month START, which is what makes a prune run twice in
    one period delete the same rows the second time (i.e. none)."""
    early = months_before(datetime(2026, 9, 1, 0, 0, 1, tzinfo=UTC), RETENTION_MONTHS)
    late = months_before(datetime(2026, 9, 30, 23, 59, tzinfo=UTC), RETENTION_MONTHS)
    assert early == late == datetime(2024, 9, 1, tzinfo=UTC)


# ── U1 · what the store refuses, and why each refusal is not defensive coding ─────────────────

def test_only_a_registered_metric_can_be_written(store, org):
    """Doc 04's third failure mode: a renamed metric splits its series in silence. The registry
    is what turns that into a write that fails at the seam that produced it."""
    with pytest.raises(ValueError, match="not a registered metric"):
        store.put(org, [point(metric="engagement.touchcount")], reason=SampleReason.SCHEDULED,
                  sampled_at=SAMPLED_AT)
    assert rows_for(store.engine, org) == []


@pytest.mark.parametrize("label,build,message", [
    ("a gap is not a row",
     lambda: [point(value=None, known=False)], "stored as NO ROW"),
    ("a unit the metric is not measured in",
     lambda: [point(metric=STAGE_AGE, unit=MetricUnit.COUNT)], "registered in days"),
    ("a reading stamped mid-period",
     lambda: [point(at=datetime(2026, 9, 17, tzinfo=UTC))], "is not the start of a month"),
    ("a value that does not fit the column",
     lambda: [point(value=2 ** 63)], "bigint"),
    ("two readings for one period in one batch",
     lambda: [point(value=1), point(value=2)], "in one batch"),
])
def test_the_store_refuses_a_reading_that_would_corrupt_the_series(store, org, label, build,
                                                                   message):
    with pytest.raises((ValueError, TypeError), match=message):
        store.put(org, build(), reason=SampleReason.SCHEDULED, sampled_at=SAMPLED_AT)
    assert rows_for(store.engine, org) == [], "a refused batch must write nothing at all"


def test_a_batch_is_validated_before_any_of_it_is_written(store, org):
    """All-or-nothing: a batch that wrote four points and raised on the fifth would leave a series
    whose gaps are an artefact of the order the sampler happened to build it in."""
    good = [point(value=1, at=month(i)) for i in range(4)]
    with pytest.raises(ValueError):
        store.put(org, [*good, point(value=9, at=datetime(2026, 6, 17, tzinfo=UTC))],
                  reason=SampleReason.SCHEDULED, sampled_at=SAMPLED_AT)
    assert rows_for(store.engine, org) == []


# ── U1 · the primary key: two sweeps in one period ───────────────────────────────────────────

def test_two_sweeps_in_one_period_leave_one_row_and_do_not_move_its_arrival(store, org):
    """THE double-sweep test. The primary key `(org, node, metric, period)` makes a re-sample
    idempotent rather than a duplicate point — and the UPSERT's `where` clause makes an IDENTICAL
    re-sample a no-op, because refreshing `sampled_at` would delete the point from every
    point-in-time read taken between the two sweeps."""
    first = store.put(org, [point(value=12)], reason=SampleReason.SCHEDULED,
                      sampled_at=SAMPLED_AT)
    second = store.put(org, [point(value=12)], reason=SampleReason.SCHEDULED,
                       sampled_at=SAMPLED_AT + timedelta(hours=6))
    third = store.put(org, [point(value=12)], reason=SampleReason.BACKFILL,
                      sampled_at=SAMPLED_AT + timedelta(days=2))

    assert (first, second, third) == (1, 0, 0), "only the first sweep changed anything"
    held = rows_for(store.engine, org)
    assert len(held) == 1
    assert held[0].value_bp == 12
    assert held[0].sampled_at == SAMPLED_AT, "an identical re-sample must not move the arrival"
    assert held[0].sample_reason == "scheduled", "the reason describes how the value arrived"


def test_a_corrected_reading_wins_and_stamps_its_own_arrival(store, org):
    """"Second wins" — the other half. A backfill that DISAGREES is a new measurement, so the row
    takes the new value, the new reason and the new arrival time."""
    store.put(org, [point(value=12)], reason=SampleReason.SCHEDULED, sampled_at=SAMPLED_AT)
    changed = store.put(org, [point(value=15)], reason=SampleReason.BACKFILL,
                        sampled_at=SAMPLED_AT + timedelta(days=1))

    held = rows_for(store.engine, org)
    assert changed == 1 and len(held) == 1
    assert held[0].value_bp == 15
    assert held[0].sample_reason == "backfill"
    assert held[0].sampled_at == SAMPLED_AT + timedelta(days=1)


def test_two_subjects_and_two_metrics_are_four_independent_series(store, org):
    store.put(org, [point(node=NODE), point(node=OTHER_NODE),
                    point(metric=STAGE_AGE, unit=MetricUnit.DAYS, value=40),
                    point(metric=STAGE_AGE, unit=MetricUnit.DAYS, value=9, node=OTHER_NODE)],
              reason=SampleReason.SCHEDULED, sampled_at=SAMPLED_AT)
    assert len(rows_for(store.engine, org)) == 4


# ── U2 · the series reader: dense, gap-aware, never interpolated ─────────────────────────────

def test_a_missing_period_reads_back_as_a_gap_and_never_as_zero(store, org):
    """The rule the whole analytic stratum rests on. An interpolated value is a FABRICATED
    observation: indistinguishable in the column from a measured one, it improves the coverage
    ratio that exists to reveal it, and it makes a trend look better supported the more data is
    missing."""
    store.put(org, [point(value=10, at=month(0)), point(value=30, at=month(2))],
              reason=SampleReason.SCHEDULED, sampled_at=SAMPLED_AT)

    series = store.read_series(org, NODE, TOUCHES, since=month(0), until=month(2))

    assert [p.value_bp for p in series] == [10, None, 30]
    assert [p.known for p in series] == [True, False, True]
    gap = series[1]
    assert gap.value_bp is None, "a gap is not a zero"
    assert gap.coverage_ready is None, "unhinted — a gap cannot license a negative inference"
    assert gap.observed_at == month(1)
    assert gap.subject_node_id == NODE and gap.metric == TOUCHES


def test_the_series_is_dense_across_the_whole_range_including_its_empty_ends(store, org):
    store.put(org, [point(value=7, at=month(3))], reason=SampleReason.SCHEDULED,
              sampled_at=SAMPLED_AT)

    series = store.read_series(org, NODE, TOUCHES, since=month(1), until=month(5))

    assert len(series) == 5
    assert [p.observed_at for p in series] == [month(i) for i in range(1, 6)]
    assert sum(1 for p in series if p.known) == 1


def test_an_empty_series_is_all_gaps_and_not_an_empty_list(store, org):
    """A reader that returned nothing would let a caller compute a trend over zero points and
    call it FLAT. Five gaps is the answer that makes `INSUFFICIENT_HISTORY` reachable."""
    series = store.read_series(org, NODE, TOUCHES, since=month(0), until=month(4))
    assert len(series) == 5
    assert not any(p.known for p in series)


def test_a_money_gap_is_denominated_in_the_recorded_unknown_not_in_a_neighbours_currency(store,
                                                                                         org):
    store.put(org, [point(metric=ARR.metric, unit=MetricUnit.MINOR_UNITS, currency="INR",
                          value=8_400_000, at=month(0))],
              reason=SampleReason.SCHEDULED, sampled_at=SAMPLED_AT)

    series = store.read_series(org, NODE, ARR.metric, since=month(0), until=month(1))

    assert series[0].currency == "INR"
    assert series[1].currency == UNKNOWN_CURRENCY, "a gap has no reading to denominate"


def test_the_reader_never_crosses_a_tenant_or_a_subject(store, org, engine):
    other = f"{org}_neighbour"
    _seed_org(engine, other)
    try:
        store.put(other, [point(value=99)], reason=SampleReason.SCHEDULED, sampled_at=SAMPLED_AT)
        store.put(org, [point(value=1, node=OTHER_NODE)], reason=SampleReason.SCHEDULED,
                  sampled_at=SAMPLED_AT)

        mine = store.read_series(org, NODE, TOUCHES, since=month(8), until=month(8))
        assert mine[0].known is False, "another tenant's reading is not ours"
        assert store.get(org, NODE, TOUCHES, month(8)) is None
    finally:
        with engine.begin() as conn:
            conn.execute(text("delete from orgs where id=:o"), {"o": other})


def test_a_dense_read_refuses_a_range_retention_has_already_emptied(store, org):
    """A dense read allocates a point per period, so an unbounded range is an unbounded
    allocation driven by a caller's arithmetic — over periods this table no longer holds."""
    with pytest.raises(ValueError, match=str(MAX_SERIES_PERIODS)):
        store.read_series(org, NODE, WEEKLY.metric, since=datetime(2020, 1, 6, tzinfo=UTC),
                          until=datetime(2026, 1, 5, tzinfo=UTC))


def test_get_reads_one_period_exactly_and_floors_its_argument(store, org):
    store.put(org, [point(value=5, at=month(4))], reason=SampleReason.SCHEDULED,
              sampled_at=SAMPLED_AT)
    found = store.get(org, NODE, TOUCHES, month(4) + timedelta(days=19, hours=3))
    assert found is not None and found.value_bp == 5 and found.observed_at == month(4)
    assert store.get(org, NODE, TOUCHES, month(5)) is None


# ── U2 · point-in-time reads: what was known THEN ────────────────────────────────────────────

def test_a_point_in_time_read_returns_what_was_known_then(store, org):
    """What makes a trend REPLAYABLE. A trend computed in March must recompute in September from
    the points that existed in March — otherwise a disagreement between the two readings cannot
    be attributed to the business or to the data, which is the whole reason the measurement is
    deterministic in the first place."""
    march = datetime(2026, 3, 20, tzinfo=UTC)
    september = datetime(2026, 9, 20, tzinfo=UTC)
    store.put(org, [point(value=10, at=month(0)), point(value=20, at=month(1))],
              reason=SampleReason.SCHEDULED, sampled_at=march)
    # A backfill in September fills a period that was empty in March.
    store.put(org, [point(value=15, at=month(2))], reason=SampleReason.BACKFILL,
              sampled_at=september)

    as_march = store.read_series(org, NODE, TOUCHES, since=month(0), until=month(2),
                                 as_at=march + timedelta(days=1))
    as_now = store.read_series(org, NODE, TOUCHES, since=month(0), until=month(2))

    assert [p.value_bp for p in as_march] == [10, 20, None]
    assert [p.value_bp for p in as_now] == [10, 20, 15]
    assert store.get(org, NODE, TOUCHES, month(2), as_at=march + timedelta(days=1)) is None


def test_an_identical_re_sample_does_not_delete_the_point_from_an_earlier_as_at_read(store, org):
    """The reason the UPSERT carries a `where` clause. Refreshing `sampled_at` on a re-sample that
    changed nothing would move the point forward in time, and every as-at read between the two
    sweeps would suddenly show a gap where a measured value stood."""
    first = datetime(2026, 5, 2, tzinfo=UTC)
    store.put(org, [point(value=10, at=month(0))], reason=SampleReason.SCHEDULED,
              sampled_at=first)
    store.put(org, [point(value=10, at=month(0))], reason=SampleReason.SCHEDULED,
              sampled_at=datetime(2026, 6, 2, tzinfo=UTC))

    replay = store.read_series(org, NODE, TOUCHES, since=month(0), until=month(0),
                               as_at=first + timedelta(minutes=1))
    assert [p.value_bp for p in replay] == [10]


# ── BOUNDING · the two retention mechanisms ──────────────────────────────────────────────────

def test_the_per_series_cap_bounds_a_backfill_that_walks_years(store, org):
    """Mechanism 3, on the WRITE path: a series cannot exceed its cap even for one transaction.
    `thread.reply_count` keeps 8 weeks, so a 30-week backfill leaves 8 rows and the newest 8."""
    weeks = [MetricPoint(subject_node_id=NODE, metric=WEEKLY.metric, value_bp=index,
                         unit=MetricUnit.COUNT, currency=None,
                         observed_at=datetime(2026, 1, 5, tzinfo=UTC) + timedelta(weeks=index),
                         known=True, coverage_ready=True)
             for index in range(30)]
    store.put(org, weeks, reason=SampleReason.BACKFILL, sampled_at=SAMPLED_AT)

    held = rows_for(store.engine, org)
    assert len(held) == WEEKLY.retention_periods == 8
    assert [row.value_bp for row in held] == list(range(22, 30)), "the NEWEST 8 survive"


def test_a_definition_cannot_ask_for_more_than_the_hard_cap():
    with pytest.raises(ValueError, match=str(MAX_RETAINED_PERIODS)):
        MetricDefinition("engagement.touch_count", MetricUnit.COUNT, MetricGrain.WEEK,
                         retention_periods=MAX_RETAINED_PERIODS + 1)


def test_retention_prunes_past_the_horizon_and_leaves_the_series_readable(store, org):
    """Mechanism 4, the wall-clock horizon — the one that bounds a series that STOPPED being
    written, which the per-series cap never touches again."""
    old = datetime(2023, 5, 1, tzinfo=UTC)
    store.put(org, [MetricPoint(subject_node_id=NODE, metric=TOUCHES, value_bp=3,
                                unit=MetricUnit.COUNT, currency=None, observed_at=old,
                                known=True, coverage_ready=True),
                    point(value=9, at=month(7)), point(value=11, at=month(8))],
              reason=SampleReason.SCHEDULED, sampled_at=SAMPLED_AT)

    pruned = store.prune(org, eval_time=EVAL_TIME)

    assert pruned == 1
    assert [row.observed_at for row in rows_for(store.engine, org)] == [month(7), month(8)]
    series = store.read_series(org, NODE, TOUCHES, since=month(7), until=month(8))
    assert [p.value_bp for p in series] == [9, 11], "the surviving series still reads"


def test_pruning_twice_in_one_month_deletes_the_same_rows_once(store, org):
    """The prune's own double-sweep property: the horizon is anchored on the month start, so a
    second prune in the same period is a no-op rather than a slightly deeper cut."""
    store.put(org, [MetricPoint(subject_node_id=NODE, metric=TOUCHES, value_bp=3,
                                unit=MetricUnit.COUNT, currency=None,
                                observed_at=datetime(2023, 5, 1, tzinfo=UTC), known=True,
                                coverage_ready=True), point(value=9, at=month(7))],
              reason=SampleReason.SCHEDULED, sampled_at=SAMPLED_AT)

    first = store.prune(org, eval_time=EVAL_TIME)
    second = store.prune(org, eval_time=EVAL_TIME + timedelta(days=20))

    assert (first, second) == (1, 0)
    assert len(rows_for(store.engine, org)) == 1


def test_the_prune_is_scoped_to_one_tenant(store, org, engine):
    other = f"{org}_neighbour"
    _seed_org(engine, other)
    ancient = MetricPoint(subject_node_id=NODE, metric=TOUCHES, value_bp=3, unit=MetricUnit.COUNT,
                          currency=None, observed_at=datetime(2023, 5, 1, tzinfo=UTC), known=True,
                          coverage_ready=True)
    try:
        store.put(other, [ancient], reason=SampleReason.SCHEDULED, sampled_at=SAMPLED_AT)
        store.put(org, [ancient], reason=SampleReason.SCHEDULED, sampled_at=SAMPLED_AT)
        assert store.prune(org, eval_time=EVAL_TIME) == 1
        assert len(rows_for(engine, other)) == 1
    finally:
        with engine.begin() as conn:
            conn.execute(text("delete from orgs where id=:o"), {"o": other})


# ── THE WIRING · a real request path reaches the prune ───────────────────────────────────────

def test_the_l2_drain_prunes_metric_history(engine, url, org, monkeypatch):
    """**The wiring test.** `context/runner.process_pending` is what `POST /api/org/{id}/sync`
    and the upload route call after every sync (`api/routes.py:402`, `api/upload_routes.py:120`),
    and `runner.py:374-383` is where retention runs. The store is NOT constructed here: the drain
    builds it from the graph store it was handed, so this proves the production path and not a
    collaborator a test assembled for itself.

    Retention on a schedule nobody owns would be a comment; the Celery broker is a quota-limited
    Upstash instance, so the horizon is enforced on the sweep that already runs per org.
    """
    from genios_engine.context.graph_store import GraphStore
    from genios_engine.context.runner import process_pending
    from genios_engine.platform.config import get_settings

    graph = GraphStore(url)
    store = PostgresMetricHistory(graph.engine, REGISTRY)
    store.put(org, [MetricPoint(subject_node_id=NODE, metric=TOUCHES, value_bp=3,
                                unit=MetricUnit.COUNT, currency=None,
                                observed_at=datetime(2023, 5, 1, tzinfo=UTC), known=True,
                                coverage_ready=True), point(value=9, at=month(7))],
              reason=SampleReason.SCHEDULED, sampled_at=SAMPLED_AT)

    result = process_pending(org_id=org, store=graph, llm=None,
                             crypto_key=get_settings().crypto_key)

    assert result["history_points_pruned"] == 1, "the drain must have called the prune itself"
    assert [row.observed_at for row in rows_for(engine, org)] == [month(7)]


# ── ERASURE · the table leaves with its tenant, both ways ────────────────────────────────────

def test_metric_history_is_named_in_the_erasure_list():
    """`_ORG_SCOPED_TABLES` executes with NO try/except by design, so a name missing from it
    leaks silently rather than failing loudly — which makes "is it in the list" a real test."""
    from genios_engine.api import account_routes
    assert HISTORY_TABLE in account_routes._ORG_SCOPED_TABLES


def test_the_reset_route_loop_erases_every_row(engine, org):
    """Not the list — the DELETE, through the same `_wipe` the /reset route runs."""
    from genios_engine.api.account_routes import _wipe

    PostgresMetricHistory(engine, REGISTRY).put(
        org, [point(value=4, at=month(1)), point(value=5, at=month(2))],
        reason=SampleReason.SCHEDULED, sampled_at=SAMPLED_AT)
    assert len(rows_for(engine, org)) == 2

    with engine.begin() as conn:
        wiped = _wipe(conn, org)

    assert wiped[HISTORY_TABLE] == 2
    assert rows_for(engine, org) == []


def test_deleting_the_org_removes_every_metric_history_row(engine):
    """Account deletion, which does not run the list at all — the org FK cascade is what erases
    this table there. A cascade that was declared and never exercised is a promise, not a fact."""
    doomed = "org_hist_cascade_probe"
    _seed_org(engine, doomed)
    PostgresMetricHistory(engine, REGISTRY).put(
        doomed, [point(value=4, at=month(1))], reason=SampleReason.SCHEDULED,
        sampled_at=SAMPLED_AT)
    assert len(rows_for(engine, doomed)) == 1

    with engine.begin() as conn:
        conn.execute(text("delete from orgs where id=:o"), {"o": doomed})

    assert rows_for(engine, doomed) == []


# ── THE TWO-TABLE RULE · doc 09 must-not-regress item 6 ──────────────────────────────────────

def test_history_appends_a_row_per_period_while_the_recompute_path_still_overwrites(store, org):
    """`graph_facts` answers "what is true NOW" and keeps overwriting; `metric_history` answers
    "what was true THEN" and only ever appends. The two halves, in one test: three periods leave
    three rows here, and `context/derived.py` — the recompute path whose overwrite behaviour doc
    09 forbids regressing — does not write this table at all."""
    store.put(org, [point(value=v, at=month(i)) for i, v in enumerate((5, 8, 2))],
              reason=SampleReason.SCHEDULED, sampled_at=SAMPLED_AT)
    assert len(rows_for(store.engine, org)) == 3

    derived = (Path(__file__).resolve().parents[3]
               / "genios_engine" / "context" / "derived.py").read_text()
    assert HISTORY_TABLE not in derived


# ── THE IN-MEMORY TWIN · a dev run must not be where a bad row first becomes possible ─────────

@pytest.mark.parametrize("label,drive,expected", [
    ("a double sweep is one row",
     lambda s, o: (s.put(o, [point(value=12)], reason=SampleReason.SCHEDULED,
                         sampled_at=SAMPLED_AT),
                   s.put(o, [point(value=12)], reason=SampleReason.SCHEDULED,
                         sampled_at=SAMPLED_AT + timedelta(days=1))), (1, 0)),
    ("a correction wins",
     lambda s, o: (s.put(o, [point(value=12)], reason=SampleReason.SCHEDULED,
                         sampled_at=SAMPLED_AT),
                   s.put(o, [point(value=13)], reason=SampleReason.SCHEDULED,
                         sampled_at=SAMPLED_AT + timedelta(days=1)),
                   s.get(o, NODE, TOUCHES, month(8)).value_bp), (1, 1, 13)),
    ("a gap is a gap in both",
     lambda s, o: (s.put(o, [point(value=10, at=month(0))], reason=SampleReason.SCHEDULED,
                         sampled_at=SAMPLED_AT),
                   tuple(p.value_bp for p in s.read_series(o, NODE, TOUCHES, since=month(0),
                                                           until=month(2)))),
     (1, (10, None, None))),
    ("retention cuts at the same horizon",
     lambda s, o: (s.put(o, [MetricPoint(subject_node_id=NODE, metric=TOUCHES, value_bp=3,
                                         unit=MetricUnit.COUNT, currency=None,
                                         observed_at=datetime(2023, 5, 1, tzinfo=UTC),
                                         known=True, coverage_ready=True),
                             point(value=9, at=month(7))],
                         reason=SampleReason.SCHEDULED, sampled_at=SAMPLED_AT),
                   s.prune(o, eval_time=EVAL_TIME),
                   s.prune(o, eval_time=EVAL_TIME)), (2, 1, 0)),
    ("an as-at read hides a later backfill",
     lambda s, o: (s.put(o, [point(value=10, at=month(0))], reason=SampleReason.SCHEDULED,
                         sampled_at=datetime(2026, 3, 20, tzinfo=UTC)),
                   s.put(o, [point(value=15, at=month(1))], reason=SampleReason.BACKFILL,
                         sampled_at=datetime(2026, 9, 20, tzinfo=UTC)),
                   tuple(p.value_bp for p in s.read_series(
                       o, NODE, TOUCHES, since=month(0), until=month(1),
                       as_at=datetime(2026, 4, 1, tzinfo=UTC)))),
     (1, 1, (10, None))),
])
def test_the_in_memory_store_answers_exactly_as_the_table_does(store, org, label, drive,
                                                               expected):
    memory = InMemoryMetricHistory(REGISTRY)
    assert drive(memory, org) == expected
    assert drive(store, org) == expected


def test_the_in_memory_store_refuses_what_the_table_refuses():
    memory = InMemoryMetricHistory(REGISTRY)
    with pytest.raises(ValueError, match="not a registered metric"):
        memory.put("org_x", [point(metric="nope.at.all")], reason=SampleReason.SCHEDULED,
                   sampled_at=SAMPLED_AT)
    with pytest.raises(ValueError, match="stored as NO ROW"):
        memory.put("org_x", [point(value=None, known=False)], reason=SampleReason.SCHEDULED,
                   sampled_at=SAMPLED_AT)


def test_the_in_memory_store_enforces_the_same_per_series_cap():
    memory = InMemoryMetricHistory(REGISTRY)
    memory.put("org_x", [MetricPoint(subject_node_id=NODE, metric=WEEKLY.metric, value_bp=i,
                                     unit=MetricUnit.COUNT, currency=None,
                                     observed_at=datetime(2026, 1, 5, tzinfo=UTC)
                                     + timedelta(weeks=i), known=True, coverage_ready=True)
                         for i in range(20)],
               reason=SampleReason.BACKFILL, sampled_at=SAMPLED_AT)
    kept = memory.read_series("org_x", NODE, WEEKLY.metric,
                              since=datetime(2026, 1, 5, tzinfo=UTC),
                              until=datetime(2026, 1, 5, tzinfo=UTC) + timedelta(weeks=19))
    assert sum(1 for p in kept if p.known) == 8
    assert memory.erase("org_x") == 8


# ── THE REGISTRY ─────────────────────────────────────────────────────────────────────────────

def test_the_registry_is_a_value_and_extending_it_leaves_the_original_alone():
    """A mutable global would make the set of writable metrics depend on which modules happened to
    be imported — a metric that writes in production and raises in a test."""
    base = default_registry()
    extended = base.with_definitions(ARR)
    assert base.names == tuple(sorted(d.metric for d in CORE_METRICS))
    assert ARR.metric in extended and ARR.metric not in base


def test_one_metric_cannot_hold_two_definitions():
    with pytest.raises(ValueError, match="registered twice"):
        MetricRegistry([ARR, MetricDefinition(ARR.metric, MetricUnit.COUNT, MetricGrain.WEEK)])


def test_every_core_metric_is_monthly_and_within_the_horizon():
    """The row-growth budget in one assertion: monthly grain and <= 24 kept points means a series
    settles at 24 rows and stops. A day grain does not exist, and no algorithm in L2.4 asks for
    one — BLG-08 needs four points, BLG-13 needs six."""
    for definition in CORE_METRICS:
        assert definition.grain is MetricGrain.MONTH
        assert definition.retention_periods <= RETENTION_MONTHS


def test_periods_between_refuses_a_backwards_range():
    with pytest.raises(ValueError, match="before"):
        periods_between(month(4), month(1), MetricGrain.MONTH)
