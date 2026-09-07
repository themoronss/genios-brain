"""L2.4.1 · the METRIC HISTORY STORE — the table that answers *"what was true then?"*.

`graph_facts` holds the current value of everything and overwrites it on every drain, for the
reason `context/derived.py:108-109` states: appending per drain would grow the largest table in
the system by three rows per node for ever. That decision is kept. This module adds the second
table beside it, and the split is the whole design:

    `graph_facts` answers "what is true NOW" and keeps overwriting.
    `metric_history` answers "what was true THEN" and only ever appends.

Without it "is engagement declining?" has no answer — not a hard one, no answer at all, because
the previous value was overwritten by the one that replaced it. Doc 04 walks six customer
expectations and six of the six need this table; none of them needs a language model.

WHAT IS IN THIS FILE
--------------------
* `period_start` — the ONE function that computes a period boundary. Doc 04 names "backfill and
  live sampling disagree on period boundaries" as the failure mode that produces phantom
  changepoints, and its mitigation is exactly this: one function, both paths.
* `MetricRegistry` — metric names are REGISTERED, not free strings (doc 04's third failure
  mode: a renamed metric splits its own series in silence). The definition also carries the
  grain, which is what makes the period key, the dense read and the retention cap agree.
* `MetricHistoryRow` / `MetricHistoryStore` — a typed store. `MetricPoint` crosses the boundary
  in both directions; no dict does.
* `prune_history_for_drain` — retention, wired to the sweep that already exists.

HOW THIS TABLE IS BOUNDED — read this before adding a writer
------------------------------------------------------------
An append-only store sampled on every sweep is the exact shape that put this database into
read-only once already (`expertise_packages`: 181 MB over 345 rows, because a lifecycle
transition rewrote a large row per pass). Four mechanisms, in the order they bite:

1. **A sweep does not write a row.** `observed_at` is the PERIOD the reading describes and it is
   part of the primary key, so a metric sampled on every drain for a month leaves ONE row,
   updated in place, not thirty. Row count is set by the calendar, never by the sweep cadence.
   Two sweeps in one period are the same row (see `put`, and the conditional update below).
2. **A gap costs no row at all.** `value_bp` is NOT NULL on purpose. A period with no reading is
   stored as NO ROW and materialised on read as `known=False, value_bp=None`. A metric the
   tenant has no connected source for therefore occupies nothing, and a zero is only ever a zero
   somebody measured — `read_series` cannot invent one, and never interpolates.
3. **A per-series cap on the write path** (`MetricDefinition.retention_periods`, hard-capped at
   `MAX_RETAINED_PERIODS`): every `put` trims the series it touched to its newest N points, so a
   series cannot exceed its cap even for one transaction, and a backfill that walks five years
   of history cannot leave five years of rows.
4. **A wall-clock horizon on the drain path** (`RETENTION_MONTHS`): `prune` deletes everything
   older than 24 months. This is the one that bounds a series that STOPPED being written — a
   node that went cold is never touched by (3) again. It runs from
   `context/runner.process_pending`, the sweep that already runs once per org per drain, so
   there is no new periodic task and nothing new on the quota-limited Upstash broker.

Steady state, monthly grain: `rows <= nodes_sampled x metrics x 24`. A 2,000-node org sampling
five monthly metrics settles at 240,000 rows and STOPS: 10,000 rows arrive each month and 10,000
fall out the back. At weekly grain the same org would settle at 104 points per series, which is
why `MAX_RETAINED_PERIODS` is 104 — 24 months either way.

WHAT A ROW ACTUALLY COSTS, measured rather than estimated. 110,000 rows were written to this
table on a real Postgres and the table measured with `pg_relation_size` / `pg_indexes_size`:

    heap      140 B/row
    indexes   249 B/row      (mh_by_metric + mh_by_node + mh_retention)
    ----------------------
    total     390 B/row

The index cost is larger than the row it indexes, which is the number to carry: an earlier
version of this note said "~30 MB" for the 240,000-row steady state above by counting the heap
alone, and the real figure is **~94 MB for one tenant**. `expertise_packages` was 181 MB when it
put this database into read-only, so a handful of tenants of that shape is the same order as the
incident. A FOURTH index on this table is therefore a storage decision, not a query decision, and
`scripts/history_density_report.py` is the command that reports the real number per tenant.

POINT-IN-TIME READS, and the one thing they cannot recover
-----------------------------------------------------------
`sampled_at` is when the reading ARRIVED. `read_series(..., as_at=T)` filters `sampled_at <= T`,
so a trend computed in March replays in September over the points that existed in March. Two
consequences, both deliberate:

* A re-sample that carries an IDENTICAL reading does not touch the row — the update carries a
  `where` clause on the values themselves. Refreshing `sampled_at` would move the point forward
  in time and silently delete it from every earlier as-at read, which is precisely the replay
  the column exists to support.
* A CORRECTED reading (a backfill that disagrees with what was stored) moves `sampled_at` to the
  correction. An as-at read from before the correction then shows that period as a GAP rather
  than as the superseded value: doc 04's primary key overwrites in place, so the old value is
  not retained anywhere. The error is conservative — a gap, never a wrong number — and it is a
  real limit of the doc's single-row-per-period design, recorded here rather than papered over.

PURITY. No clock: `sampled_at`, `eval_time` and `as_at` are parameters, filled in at the seam
(`runner.py` passes `datetime.now(timezone.utc)`, as `periodic.py` already does). No float: every
number is an int, `value_bp` is checked against the bigint range before it reaches a column that
would otherwise raise mid-transaction.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Protocol

from genios_engine.contracts.analytic import MetricPoint, MetricUnit
from genios_engine.contracts.units import UNKNOWN_CURRENCY
from genios_engine.contracts.validators import require_aware, require_identifier

#: The table migration 0094 creates. Named once so the store, the erasure list and the tests all
#: spell it the same way.
HISTORY_TABLE = "metric_history"

#: Doc 04's retention mitigation, in months. Measured from the START of `eval_time`'s month, so
#: the horizon is stable for the whole month and a prune run twice in one period deletes the
#: same rows the second time (i.e. none).
RETENTION_MONTHS = 24

#: The hard cap on points per series, whatever a definition asks for. 104 = 24 months of weeks,
#: so the wall-clock horizon and the per-series cap describe the same window at either grain.
MAX_RETAINED_PERIODS = 104

#: The largest span a single `read_series` will materialise. A dense read builds one `MetricPoint`
#: per period in range, so an unbounded range is an unbounded allocation driven by a caller's
#: arithmetic. 260 is two years of weeks with room to spare, and a caller that needs more is
#: asking for something retention has already deleted.
MAX_SERIES_PERIODS = 260

#: `value_bp` is a bigint column. Checked here so an out-of-range measurement is refused by the
#: store with a message naming the metric, rather than raising inside a transaction that has
#: already written half a batch.
_BIGINT_MAX = 2 ** 63 - 1


class MetricGrain(str, Enum):
    """The period a metric is sampled at. Two grains, closed, and a property of the METRIC.

    Not a per-write choice: the primary key is `(org, subject, metric, observed_at)`, so a metric
    written monthly on one path and weekly on another produces a single series whose points are
    four different sizes — a slope over it is arithmetic on incomparable readings, and every row
    in it is individually correct. Binding the grain to the metric definition makes that
    unconstructible instead of merely discouraged.

    There is deliberately NO DAY grain. A daily series is 730 rows per node per metric over the
    retention window, which is the write-amplification shape this table was bounded against, and
    no algorithm in L2.4 asks for one: BLG-08 needs four points, BLG-13 needs six.
    """

    WEEK = "week"
    MONTH = "month"


class SampleReason(str, Enum):
    """Why this point exists — doc 04's `sample_reason` column, as a closed set.

    It describes how the VALUE arrived, which is why a re-sample that agrees with what is stored
    does not rewrite it: the reading is still the one the first writer produced.
    """

    #: The sampling policy's ordinary cadence (L2.4.2).
    SCHEDULED = "scheduled"
    #: A value moved enough to be worth a point of its own outside the cadence.
    CHANGEPOINT = "changepoint"
    #: History reconstructed from data that was already in the graph.
    BACKFILL = "backfill"


def period_start(instant: datetime, grain: MetricGrain) -> datetime:
    """The boundary of the period `instant` falls in, in UTC. THE shared function.

    Doc 04's second failure mode is "backfill and live sampling disagree on period boundaries ->
    phantom changepoints", and its mitigation is that both paths compute the boundary here.
    Idempotent (`period_start(period_start(t)) == period_start(t)`), which is what lets `put` and
    `get` floor their arguments without a caller having to remember to.

    Integer arithmetic and no clock: a week starts on ISO Monday, a month on the 1st, both at
    00:00 UTC.
    """
    at = require_aware(instant, "instant")
    day = at.replace(hour=0, minute=0, second=0, microsecond=0)
    if grain is MetricGrain.MONTH:
        return day.replace(day=1)
    if grain is MetricGrain.WEEK:
        return day - timedelta(days=day.weekday())
    raise ValueError(f"unknown metric grain {grain!r}")


def next_period(start: datetime, grain: MetricGrain) -> datetime:
    """The period after this one. Integer month arithmetic, no calendar library."""
    if grain is MetricGrain.WEEK:
        return start + timedelta(days=7)
    year, month = divmod(start.year * 12 + start.month, 12)
    return start.replace(year=year, month=month + 1, day=1)


def months_before(instant: datetime, months: int) -> datetime:
    """The start of the month `months` before `instant`'s month.

    Anchored on the month START rather than on the instant so the horizon does not move within a
    period: two prunes in the same month compute the same cutoff, which is what makes the second
    one delete nothing rather than a few more rows than the first.
    """
    if isinstance(months, bool) or not isinstance(months, int) or months < 0:
        raise ValueError("months must be a non-negative integer")
    start = period_start(instant, MetricGrain.MONTH)
    year, month = divmod(start.year * 12 + (start.month - 1) - months, 12)
    return start.replace(year=year, month=month + 1)


def periods_between(since: datetime, until: datetime, grain: MetricGrain) -> tuple[datetime, ...]:
    """Every period boundary from `since` to `until`, inclusive of both ends' periods.

    This is what makes a series DENSE: the reader walks these and asks the rows what it holds,
    so a period with no row becomes an explicit gap instead of vanishing between two neighbours.
    A reader that simply listed its rows would turn a coverage gap into a false trend, which is
    the failure `Trend.coverage_ratio_bp` exists to make visible.
    """
    first = period_start(since, grain)
    last = period_start(until, grain)
    if last < first:
        raise ValueError(f"until ({until.isoformat()}) is before since ({since.isoformat()})")
    out: list[datetime] = []
    cursor = first
    while cursor <= last:
        out.append(cursor)
        if len(out) > MAX_SERIES_PERIODS:
            raise ValueError(
                f"a dense read of more than {MAX_SERIES_PERIODS} {grain.value} periods was "
                f"refused — {first.date()}..{last.date()} is past the retention horizon and "
                "would allocate a point per period for rows that were pruned")
        cursor = next_period(cursor, grain)
    return tuple(out)


@dataclass(frozen=True)
class MetricDefinition:
    """One registered metric: its name, its unit, its grain and how much of it we keep.

    Doc 04's third failure mode is "a metric renamed -> series silently splits", mitigated by
    "metric names are a registered enum, not free strings". A registry rather than a literal enum
    because L2.4.2 adds its own metrics and a `str` Enum in this file would make every new metric
    an edit to the store; the enforcement — the store refuses to write an unregistered name — is
    identical either way.

    `unit` is part of the DEFINITION, not of the write: a series whose unit changed halfway is a
    column of numbers meaning two different things, and only `unit` says which.
    """

    metric: str
    unit: MetricUnit
    grain: MetricGrain
    #: How many points of this series to keep, newest first. Capped at `MAX_RETAINED_PERIODS`.
    retention_periods: int = MAX_RETAINED_PERIODS

    def __post_init__(self) -> None:
        require_identifier(self.metric, "metric")
        if not isinstance(self.unit, MetricUnit):
            raise TypeError(f"{self.metric}: unit must be a MetricUnit")
        if not isinstance(self.grain, MetricGrain):
            raise TypeError(f"{self.metric}: grain must be a MetricGrain")
        periods = self.retention_periods
        if isinstance(periods, bool) or not isinstance(periods, int) or periods < 1:
            raise ValueError(f"{self.metric}: retention_periods must be a positive integer")
        if periods > MAX_RETAINED_PERIODS:
            raise ValueError(
                f"{self.metric}: retention_periods {periods} exceeds {MAX_RETAINED_PERIODS} — "
                "the cap is what stops one metric definition from being the reason this table "
                "becomes the largest in the database")


#: The two metrics doc 04 names by example. Monthly, because both feed BLG-08 (four points) and
#: BLG-13 (six periods), and both are counts over a window rather than instantaneous readings.
#: L2.4.2's sampling policy owns the rest and extends the registry with `with_definitions`.
CORE_METRICS: tuple[MetricDefinition, ...] = (
    MetricDefinition("engagement.touch_count", MetricUnit.COUNT, MetricGrain.MONTH,
                     retention_periods=RETENTION_MONTHS),
    MetricDefinition("deal.stage_age_days", MetricUnit.DAYS, MetricGrain.MONTH,
                     retention_periods=RETENTION_MONTHS),
)


class MetricRegistry:
    """The registered metrics, as an immutable value. `with_definitions` returns a new one.

    Immutable rather than a module-level dict with a `register()` function: a mutable global
    makes the set of writable metrics depend on which modules happened to be imported, which is
    the same class of bug as an import-time side effect and shows up as a metric that writes in
    production and raises in a test.
    """

    __slots__ = ("_by_name",)

    def __init__(self, definitions: Iterable[MetricDefinition] = ()) -> None:
        by_name: dict[str, MetricDefinition] = {}
        for definition in definitions:
            if not isinstance(definition, MetricDefinition):
                raise TypeError("a registry holds MetricDefinition values")
            held = by_name.get(definition.metric)
            if held is not None and held != definition:
                raise ValueError(
                    f"{definition.metric} is registered twice with different terms ({held} vs "
                    f"{definition}) — two definitions of one metric is the renamed-metric "
                    "failure wearing the same name")
            by_name[definition.metric] = definition
        self._by_name: Mapping[str, MetricDefinition] = dict(by_name)

    def __contains__(self, metric: object) -> bool:
        return metric in self._by_name

    def __len__(self) -> int:
        return len(self._by_name)

    @property
    def names(self) -> tuple[str, ...]:
        return tuple(sorted(self._by_name))

    def get(self, metric: str) -> MetricDefinition | None:
        return self._by_name.get(metric)

    def require(self, metric: str) -> MetricDefinition:
        definition = self._by_name.get(metric)
        if definition is None:
            raise ValueError(
                f"{metric!r} is not a registered metric (known: {', '.join(self.names) or 'none'})"
                " — an unregistered name writes a series nothing reads and, on a rename, splits "
                "the old one in silence")
        return definition

    def with_definitions(self, *definitions: MetricDefinition) -> MetricRegistry:
        return MetricRegistry((*self._by_name.values(), *definitions))


def default_registry() -> MetricRegistry:
    """The core metrics. A function rather than a module constant so a caller cannot mutate the
    shared instance out from under every other store in the process."""
    return MetricRegistry(CORE_METRICS)


@dataclass(frozen=True)
class MetricHistoryRow:
    """One stored point, in the shape the table holds it.

    The row exists beside `MetricPoint` rather than instead of it because the table carries three
    facts the contract deliberately does not: the tenant (`org_id` is ambient on the contract),
    and the two provenance columns `sampled_at` / `sample_reason`, which are about the SAMPLER
    rather than about the measurement. `point` converts back, so nothing but typed objects crosses
    the store boundary in either direction.
    """

    org_id: str
    subject_node_id: str
    metric: str
    value_bp: int
    unit: MetricUnit
    currency: str | None
    observed_at: datetime
    sampled_at: datetime
    sample_reason: SampleReason
    coverage_ready: bool | None = None

    @property
    def series_key(self) -> tuple[str, str, str]:
        return (self.org_id, self.subject_node_id, self.metric)

    @property
    def point(self) -> MetricPoint:
        """The contract object. `known=True` always: a row IS a reading — the store has no way to
        write one without a value, and a gap is the absence of a row."""
        return MetricPoint(subject_node_id=self.subject_node_id, metric=self.metric,
                           value_bp=self.value_bp, unit=self.unit, currency=self.currency,
                           observed_at=self.observed_at, known=True,
                           coverage_ready=self.coverage_ready)

    def as_params(self) -> dict[str, Any]:
        """The bind parameters for one upsert, built here so the column list and the values
        cannot drift apart at a call site."""
        return {"o": self.org_id, "n": self.subject_node_id, "m": self.metric,
                "v": self.value_bp, "u": self.unit.value, "c": self.currency,
                "obs": self.observed_at, "sat": self.sampled_at,
                "r": self.sample_reason.value, "cov": self.coverage_ready}


def to_row(org_id: str, point: MetricPoint, *, reason: SampleReason, sampled_at: datetime,
           definition: MetricDefinition) -> MetricHistoryRow:
    """One `MetricPoint` as a storable row, with every refusal this store makes.

    Five of them, and each is a state that would be unreadable rather than merely wrong:

    * **A gap is not a row.** `known=False` carries no value and `value_bp` is NOT NULL, so the
      only way to store a gap would be to invent a number for it. Absence is the representation.
    * **The unit must be the metric's own.** A series whose unit changed halfway is a column of
      numbers meaning two things, and every trend over it is arithmetic on incomparables.
    * **`observed_at` must be a period boundary.** Off-boundary points are invisible to a dense
      read (which walks boundaries) and would sit in the table unreferenced for ever.
    * **The value must fit a bigint**, checked before a batch is half written.
    * **The subject and metric must be identifiers**, which `MetricPoint` already guarantees; the
      registry check is the one that catches a name nothing will ever read back.
    """
    if not isinstance(point, MetricPoint):
        raise TypeError("metric history stores MetricPoint values, not dicts")
    if point.metric != definition.metric:
        raise ValueError(f"point is about {point.metric!r}, definition is {definition.metric!r}")
    if not point.known or point.value_bp is None:
        raise ValueError(
            f"{point.metric}: a point with no reading is stored as NO ROW, not as a row with an "
            "invented value — `read_series` materialises the gap as known=False, and a stored "
            "zero would be indistinguishable from a month in which nothing happened")
    if point.unit is not definition.unit:
        raise ValueError(
            f"{point.metric} is registered in {definition.unit.value} and this point is in "
            f"{point.unit.value} — a series that changes unit halfway is two metrics in one "
            "column")
    boundary = period_start(point.observed_at, definition.grain)
    if point.observed_at != boundary:
        raise ValueError(
            f"{point.metric}: observed_at {point.observed_at.isoformat()} is not the start of a "
            f"{definition.grain.value} ({boundary.isoformat()}) — an off-boundary point is "
            "invisible to every dense read and would never be seen again")
    if abs(point.value_bp) > _BIGINT_MAX:
        raise ValueError(f"{point.metric}: value_bp {point.value_bp} does not fit a bigint column")
    if not isinstance(reason, SampleReason):
        raise TypeError("sample_reason must be a SampleReason")
    return MetricHistoryRow(
        org_id=require_identifier(org_id, "org_id"), subject_node_id=point.subject_node_id,
        metric=point.metric, value_bp=point.value_bp, unit=point.unit, currency=point.currency,
        observed_at=boundary, sampled_at=require_aware(sampled_at, "sampled_at"),
        sample_reason=reason, coverage_ready=point.coverage_ready)


def gap_point(subject_node_id: str, definition: MetricDefinition,
              observed_at: datetime) -> MetricPoint:
    """The honest absence for one period. `known=False`, no value, and NEVER interpolated.

    `coverage_ready` is `None` — unhinted, the tri-state's middle. It is not `False`: a gap alone
    cannot tell "no source could have carried this" from "a connected source carried nothing",
    and `False` is the licence to make a negative inference. Only a row the sampler wrote can
    settle that, which is the honest position and a real limit of the doc's DDL — written down in
    `docs/plans/L2_MISSING_UNIT_SPECS.md` §3 A-11 (`value_bp not null` means a coverage-false
    observation has no row shape). This line used to defer to a build report that was never
    written, which is worse than deferring to nothing: the reader stops looking.

    A MINOR_UNITS gap carries `UNKNOWN_CURRENCY` because the contract requires a currency on that
    unit and a gap has no reading to denominate — borrowing a neighbour's currency would state a
    denomination nobody measured.
    """
    currency = UNKNOWN_CURRENCY if definition.unit is MetricUnit.MINOR_UNITS else None
    return MetricPoint(subject_node_id=subject_node_id, metric=definition.metric, value_bp=None,
                       unit=definition.unit, currency=currency, observed_at=observed_at,
                       known=False, coverage_ready=None)


class MetricHistoryStore(Protocol):
    """What L2.4.2 writes through and what L2.4.3/.5/.7/.8 read through. Nothing more."""

    def put(self, org_id: str, points: Sequence[MetricPoint], *, reason: SampleReason,
            sampled_at: datetime) -> int: ...

    def get(self, org_id: str, subject_node_id: str, metric: str, observed_at: datetime, *,
            as_at: datetime | None = None) -> MetricPoint | None: ...

    def read_series(self, org_id: str, subject_node_id: str, metric: str, *, since: datetime,
                    until: datetime,
                    as_at: datetime | None = None) -> tuple[MetricPoint, ...]: ...

    def prune(self, org_id: str, *, eval_time: datetime) -> int: ...

    def erase(self, org_id: str) -> int: ...

    def has_points(self, org_id: str) -> bool: ...


def _prepared(org_id: str, points: Sequence[MetricPoint], *, reason: SampleReason,
              sampled_at: datetime, registry: MetricRegistry) -> list[MetricHistoryRow]:
    """Validate a whole batch BEFORE any of it is written.

    All-or-nothing on purpose: a batch that wrote four points and then raised on the fifth would
    leave a series whose gaps are an artefact of the order the sampler happened to build it in,
    and the next run would compute a coverage ratio over that.
    """
    rows = [to_row(org_id, point, reason=reason, sampled_at=sampled_at,
                   definition=registry.require(point.metric)) for point in points]
    seen: set[tuple[str, str, datetime]] = set()
    for row in rows:
        key = (row.subject_node_id, row.metric, row.observed_at)
        if key in seen:
            raise ValueError(
                f"two points for {row.metric} on {row.subject_node_id} at "
                f"{row.observed_at.isoformat()} in one batch — the second would overwrite the "
                "first with no record that either existed")
        seen.add(key)
    return rows


class InMemoryMetricHistory:
    """A dict that lives for the process — a dev run with no database, and hermetic tests.

    It enforces the same rules the table does (primary key, per-series cap, conditional update),
    because the in-memory path must never be the one where a bad row first becomes possible.
    """

    def __init__(self, registry: MetricRegistry | None = None) -> None:
        self._registry = registry or default_registry()
        self._rows: dict[tuple[str, str, str, datetime], MetricHistoryRow] = {}

    @property
    def registry(self) -> MetricRegistry:
        return self._registry

    def put(self, org_id: str, points: Sequence[MetricPoint], *, reason: SampleReason,
            sampled_at: datetime) -> int:
        rows = _prepared(org_id, points, reason=reason, sampled_at=sampled_at,
                         registry=self._registry)
        changed = 0
        for row in rows:
            key = (row.org_id, row.subject_node_id, row.metric, row.observed_at)
            held = self._rows.get(key)
            if held is not None and _same_reading(held, row):
                continue                      # identical re-sample: `sampled_at` must not move
            self._rows[key] = row
            changed += 1
        for series in {row.series_key for row in rows}:
            self._trim(series)
        return changed

    def _trim(self, series: tuple[str, str, str]) -> None:
        keep = self._registry.require(series[2]).retention_periods
        held = sorted((k for k in self._rows if (k[0], k[1], k[2]) == series),
                      key=lambda k: k[3], reverse=True)
        for key in held[keep:]:
            del self._rows[key]

    def get(self, org_id: str, subject_node_id: str, metric: str, observed_at: datetime, *,
            as_at: datetime | None = None) -> MetricPoint | None:
        definition = self._registry.require(metric)
        key = (org_id, subject_node_id, metric,
               period_start(observed_at, definition.grain))
        row = self._rows.get(key)
        if row is None or (as_at is not None
                           and row.sampled_at > require_aware(as_at, "as_at")):
            return None
        return row.point

    def read_series(self, org_id: str, subject_node_id: str, metric: str, *, since: datetime,
                    until: datetime,
                    as_at: datetime | None = None) -> tuple[MetricPoint, ...]:
        definition = self._registry.require(metric)
        horizon = None if as_at is None else require_aware(as_at, "as_at")
        held = {row.observed_at: row
                for key, row in self._rows.items()
                if key[0] == org_id and key[1] == subject_node_id and key[2] == metric
                and (horizon is None or row.sampled_at <= horizon)}
        return tuple(held[period].point if period in held
                     else gap_point(subject_node_id, definition, period)
                     for period in periods_between(since, until, definition.grain))

    def prune(self, org_id: str, *, eval_time: datetime) -> int:
        cutoff = months_before(eval_time, RETENTION_MONTHS)
        doomed = [k for k, row in self._rows.items()
                  if k[0] == org_id and row.observed_at < cutoff]
        for key in doomed:
            del self._rows[key]
        return len(doomed)

    def erase(self, org_id: str) -> int:
        doomed = [k for k in self._rows if k[0] == org_id]
        for key in doomed:
            del self._rows[key]
        return len(doomed)

    def has_points(self, org_id: str) -> bool:
        return any(k[0] == org_id for k in self._rows)


def _same_reading(held: MetricHistoryRow, fresh: MetricHistoryRow) -> bool:
    """Is this re-sample the same measurement? The in-memory twin of the SQL `where` clause.

    `sample_reason` is NOT compared: a backfill confirming a scheduled reading has not changed
    the reading, and rewriting the row would move `sampled_at` — which deletes the point from
    every as-at read taken before the confirmation.
    """
    return (held.value_bp == fresh.value_bp and held.unit is fresh.unit
            and held.currency == fresh.currency and held.coverage_ready == fresh.coverage_ready)


_UPSERT = f"""
insert into {HISTORY_TABLE} (org_id, subject_node_id, metric, value_bp, unit, currency,
                             observed_at, sampled_at, sample_reason, coverage_ready)
values (:o, :n, :m, :v, :u, :c, :obs, :sat, :r, :cov)
on conflict (org_id, subject_node_id, metric, observed_at) do update set
    value_bp = excluded.value_bp,
    unit = excluded.unit,
    currency = excluded.currency,
    sampled_at = excluded.sampled_at,
    sample_reason = excluded.sample_reason,
    coverage_ready = excluded.coverage_ready
where {HISTORY_TABLE}.value_bp is distinct from excluded.value_bp
   or {HISTORY_TABLE}.unit is distinct from excluded.unit
   or {HISTORY_TABLE}.currency is distinct from excluded.currency
   or {HISTORY_TABLE}.coverage_ready is distinct from excluded.coverage_ready
"""

#: The per-series cap, as one statement. `min(observed_at)` over the newest N is the oldest point
#: worth keeping; everything strictly older goes. Driven by `mh_by_node`, so the cost is the
#: points deleted rather than the size of the series.
_TRIM = f"""
delete from {HISTORY_TABLE}
 where org_id = :o and subject_node_id = :n and metric = :m
   and observed_at < (select min(observed_at) from (
           select observed_at from {HISTORY_TABLE}
            where org_id = :o and subject_node_id = :n and metric = :m
            order by observed_at desc limit :k) recent)
"""


class PostgresMetricHistory:
    """The real store. Upsert on the period key, and every read is org-scoped.

    Constructed from a URL or from an existing Engine (`GraphStore.engine`), because the one
    production caller already holds an engine and a second pool per drain would be a connection
    leak on a database whose measured ceiling is 60.
    """

    def __init__(self, target: Any, registry: MetricRegistry | None = None) -> None:
        if isinstance(target, str):
            from genios_engine.platform.db import get_engine
            self._engine = get_engine(target)
        else:
            self._engine = target
        self._registry = registry or default_registry()

    @property
    def engine(self):
        """The pool this store writes through — the same shape `GraphStore.engine` exposes, so a
        caller holding one store can run its own statement in the same connection pool instead of
        opening a second one against a database whose measured ceiling is 60 connections."""
        return self._engine

    @property
    def registry(self) -> MetricRegistry:
        return self._registry

    def put(self, org_id: str, points: Sequence[MetricPoint], *, reason: SampleReason,
            sampled_at: datetime) -> int:
        """Write a batch. Returns how many rows CHANGED — an identical re-sample counts 0.

        That return value is the double-sweep answer in a number: a sampler that runs twice in
        one period gets `n` then `0`, the row count is unchanged, and `sampled_at` still says
        when the reading first arrived.
        """
        from sqlalchemy import text

        rows = _prepared(org_id, points, reason=reason, sampled_at=sampled_at,
                         registry=self._registry)
        if not rows:
            return 0
        changed = 0
        with self._engine.begin() as conn:
            for row in rows:
                changed += conn.execute(text(_UPSERT), row.as_params()).rowcount
            for org, node, metric in {row.series_key for row in rows}:
                conn.execute(text(_TRIM), {
                    "o": org, "n": node, "m": metric,
                    "k": self._registry.require(metric).retention_periods})
        return changed

    def get(self, org_id: str, subject_node_id: str, metric: str, observed_at: datetime, *,
            as_at: datetime | None = None) -> MetricPoint | None:
        """One period, exactly. `None` means "no row" — `read_series` is what turns that into an
        explicit gap, because only a range knows which periods were asked about."""
        from sqlalchemy import text

        definition = self._registry.require(metric)
        with self._engine.begin() as conn:
            found = conn.execute(text(
                f"select value_bp, unit, currency, observed_at, coverage_ready from "
                f"{HISTORY_TABLE} where org_id=:o and subject_node_id=:n and metric=:m "
                "and observed_at=:obs and (cast(:asat as timestamptz) is null "
                "or sampled_at <= cast(:asat as timestamptz))"), {
                    "o": org_id, "n": subject_node_id, "m": metric,
                    "obs": period_start(observed_at, definition.grain),
                    "asat": None if as_at is None else require_aware(as_at, "as_at")}).first()
        if found is None:
            return None
        return MetricPoint(subject_node_id=subject_node_id, metric=metric,
                           value_bp=int(found.value_bp), unit=MetricUnit(found.unit),
                           currency=found.currency, observed_at=found.observed_at, known=True,
                           coverage_ready=found.coverage_ready)

    def read_series(self, org_id: str, subject_node_id: str, metric: str, *, since: datetime,
                    until: datetime,
                    as_at: datetime | None = None) -> tuple[MetricPoint, ...]:
        """A DENSE series: one point per period in range, gaps explicit, never interpolated."""
        from sqlalchemy import text

        definition = self._registry.require(metric)
        periods = periods_between(since, until, definition.grain)
        with self._engine.begin() as conn:
            found = conn.execute(text(
                f"select value_bp, unit, currency, observed_at, coverage_ready from "
                f"{HISTORY_TABLE} where org_id=:o and subject_node_id=:n and metric=:m "
                "and observed_at >= :lo and observed_at <= :hi "
                "and (cast(:asat as timestamptz) is null "
                "or sampled_at <= cast(:asat as timestamptz)) order by observed_at"), {
                    "o": org_id, "n": subject_node_id, "m": metric,
                    "lo": periods[0], "hi": periods[-1],
                    "asat": None if as_at is None else require_aware(as_at, "as_at")}).all()
        held = {row.observed_at: row for row in found}
        out: list[MetricPoint] = []
        for period in periods:
            row = held.get(period)
            if row is None:
                out.append(gap_point(subject_node_id, definition, period))
            else:
                out.append(MetricPoint(
                    subject_node_id=subject_node_id, metric=metric, value_bp=int(row.value_bp),
                    unit=MetricUnit(row.unit), currency=row.currency,
                    observed_at=row.observed_at, known=True, coverage_ready=row.coverage_ready))
        return tuple(out)

    def prune(self, org_id: str, *, eval_time: datetime) -> int:
        """Retention, mechanism 4. Everything older than `RETENTION_MONTHS` for this tenant.

        Runs on the `mh_retention` index, so a prune with nothing to delete costs one probe —
        which is what makes it affordable on every drain instead of on a schedule nobody owns.
        """
        from sqlalchemy import text

        cutoff = months_before(eval_time, RETENTION_MONTHS)
        with self._engine.begin() as conn:
            return conn.execute(text(
                f"delete from {HISTORY_TABLE} where org_id=:o and observed_at < :cut"),
                {"o": org_id, "cut": cutoff}).rowcount

    def erase(self, org_id: str) -> int:
        """What `/reset` does to this table, callable directly. The route's own loop
        (`api/account_routes._ORG_SCOPED_TABLES`) is the production path; this exists so a caller
        holding a store can erase without importing an API module."""
        from sqlalchemy import text

        with self._engine.begin() as conn:
            return conn.execute(text(f"delete from {HISTORY_TABLE} where org_id=:o"),
                                {"o": org_id}).rowcount

    def has_points(self, org_id: str) -> bool:
        """Does this tenant have ANY reading at all? The backfill's once-per-org guard.

        `limit 1` on the primary key's leading column, so the answer costs one index probe on
        every drain for ever — which is the price of the guard being read on the sweep path
        rather than kept in a marker table that could disagree with the rows it describes.
        Deliberately NOT `count(*)`: the question is existence, and a tenant with 240,000 rows
        must not pay for a scan to be told what its first row already proves.
        """
        from sqlalchemy import text

        with self._engine.connect() as conn:
            return conn.execute(text(
                f"select 1 from {HISTORY_TABLE} where org_id=:o limit 1"),
                {"o": org_id}).first() is not None


def prune_history_for_drain(store: Any, org_id: str, *, eval_time: datetime) -> int:
    """Retention, called from `context/runner.process_pending` once per org per drain.

    On the DRAIN rather than on a schedule because the Celery broker is a quota-limited Upstash
    instance and this layer's rule is to prefer in-process work on a path that already runs. It
    is also the correct place on its own terms: the drain is the only thing that knows an org is
    active, and an org that is not draining is not growing this table either.

    `eval_time` is a parameter all the way down; the clock is read at the call site.
    """
    return PostgresMetricHistory(store.engine).prune(org_id, eval_time=eval_time)


__all__ = ["CORE_METRICS", "HISTORY_TABLE", "MAX_RETAINED_PERIODS", "MAX_SERIES_PERIODS",
           "RETENTION_MONTHS", "InMemoryMetricHistory", "MetricDefinition", "MetricGrain",
           "MetricHistoryRow", "MetricHistoryStore", "MetricRegistry", "PostgresMetricHistory",
           "SampleReason", "default_registry", "gap_point", "months_before", "next_period",
           "period_start", "periods_between", "prune_history_for_drain", "to_row"]
