"""L2.4.2 · the Metric Sampler (BLG-07) — the only WRITER of `metric_history`.

Everything above this file in L2.4 is a comparison: a trend, a percentile, a peer baseline, an
anomaly. Not one of them is computable from `graph_facts`, because `graph_facts` answers *"what is
true now?"* and overwrites — `context/derived.py:122-129` says so in its own words, and it was
right to: appending a row per drain would grow that table by three rows per node forever. The
consequence is that "engagement is declining", the phrase in six of the six customer expectations
this group exists for, has no input anywhere in the system.

This module produces that input. It reads the live graph, turns it into *readings*, and hands them
to L2.4.1's store, which owns the table, its grain and its retention. The division is strict:
**this file decides WHAT is measured and WHEN; `history.py` decides how a reading is stored.**

WHY A SAMPLER AND NOT A LOGGER, WHICH IS THE WHOLE DESIGN
---------------------------------------------------------
The cheap version of this file writes every metric for every node on every sweep. That version is
the `expertise_packages` incident with a different table name: 181 MB over 345 rows, production in
read-only, a lifecycle transition nobody had costed. So *when a reading is taken* is a decision
with a bill attached, and BLG-07 makes it a table rather than a habit:

    1  trended metric, node is account/deal/person with activity in 90d   -> weekly
    2  node is in an ACTIVE situation                                     -> daily
    3  value moved more than the metric's `changepoint_bp`                -> immediate
    4  node was dormant and became active                                 -> immediate
    5  month boundary                                                     -> monthly, always
    everything else                                                       -> not sampled

`decide()` below is that table, one `_Rule` per row, evaluated as data.

THE ROW-GROWTH ARITHMETIC, STATED RATHER THAN HOPED FOR
-------------------------------------------------------
Four things bound this table, and each lives in exactly one place:

* **The period grain, and it is the store's.** Eleven of the twelve metrics are registered at
  `MetricGrain.WEEK` (`deal.stage_age_days` is MONTH, because `history.CORE_METRICS` already
  defines it that way and one metric may have only one definition), and `history.period_start` —
  the ONE shared boundary function doc 04 names as the mitigation for "backfill and live sampling
  disagree on period boundaries -> phantom changepoints" — floors every `observed_at` to an ISO
  Monday or a month start. With the primary key `(org, node, metric, observed_at)`, that is the
  structural ceiling: **at most one row per node per metric per week, no matter how often the
  sweep runs.**
* **Cadence, which is about FRESHNESS, not about rows.** A daily rule does not produce seven rows
  a week; it re-reads the current week's point up to seven times, and the store's conditional
  upsert makes a re-read that agrees cost nothing at all. So rule 2 buys resolution on a live
  situation without buying storage — which is the only reason a daily rule is affordable.
* **The budget guard** (U3, `PointBudget`). One sweep on a 50k-node org must not become a
  500k-row insert, so a run stops at a declared cap, in a deterministic order, and reports what
  it dropped instead of silently truncating.
* **Retention**, which is L2.4.1's: 104 weekly periods per series, 24 months per org.

The arithmetic on the design partner's actual shape — ~1,500 nodes, ~150 with 90d activity,
12 registered metrics, weekly grain:

    active   : 150 nodes x 12 metrics x 4.3 weeks   =  ~7,700 rows / month
    floor    : nodes holding a series, monthly rule =  ~1,000 rows / month
    ----------------------------------------------------------------------
    total    : ~8,700 rows / org / month
    a SECOND sweep in the same week adds ZERO rows — it overwrites the same week's points.

At 390 B/row — MEASURED on a real table, 140 B of heap plus 249 B across the three indexes, see
`history.py`'s "WHAT A ROW ACTUALLY COSTS" — that is **~3.4 MB/month**, and the series caps bind
the total at 150 x 11 x 104 + 150 x 24 = ~175,000 rows, i.e. **~68 MB for one tenant of that
shape**. An earlier version of this note said 1 MB/month and 25 MB, from a 120 B/row estimate
that counted the heap and not the indexes; the corrected figure is the one to size against,
because `expertise_packages` was 181 MB when it took production read-only. The per-tenant number
is reportable at any time with `python -m scripts.history_density_report --org <id>`.

The CEILING per node, which is the number a new metric changes: a company node is eligible for
all twelve metrics, so it can hold 11 x 104 (weekly) + 1 x 24 (monthly) = 1,168 rows ~= 456 KB.
A thirteenth weekly metric adds 104 rows x every eligible node before it adds a single feature.

The term that would have run away is the monthly floor, because "every node gets at least one
point per month regardless" reads like *every node in the graph*. Applied literally to a
50k-node org that is 600k rows a month from rule 5 alone. It is scoped here to nodes that are
**metric-eligible and have ever been active, or already hold a series** — a node the graph has
never seen move does not start a series, and a series that exists never grows a hole. That is the
difference between a floor density and an unbounded write.

A METRIC WITH NO READING IS NOT ZERO
------------------------------------
`measure()` returns `Reading(None)` when the graph cannot answer, and the sampler then builds
`history.gap_point(...)` — `known=False`, no value — and **writes no row**. Absence IS the storage
of a gap (`history.to_row` refuses any other shape, and `read_series` materialises the missing
period back as `known=False`), so the honest gap costs nothing and reads back correctly.

This is not defensive politeness. `deal.value_minor_units` is absent on all but one node of the
live graph — `derived.py` refuses to infer it, correctly. If the sampler wrote 0 there, every
trend above it would report a portfolio collapsing to nothing, every percentile would rank real
deals against fabricated zeros, and the coverage ratio that exists to reveal the gap would say the
series was complete.

DETERMINISM
-----------
`eval_time` is a parameter everywhere; no function here calls a clock. Every measure is integer
arithmetic — medians take the LOWER middle element rather than averaging two, because averaging
two integers is where a `.5` and then a float enters a measurement path. Sampling the same graph
at the same `eval_time` twice produces byte-identical points, which is the property that makes a
re-run an overwrite rather than a second, disagreeing observation of the same period.

No LLM. The group's only model site is M-9 (cohort predicate authoring) and it is not here.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Callable, Iterable, Mapping, Sequence

from sqlalchemy import text

from genios_engine.contracts.analytic import MetricPoint, MetricUnit
#: What a deal value is denominated in when the graph never said. Imported from the same place
#: `contracts/units.Money` reads it, so the two cannot drift into accepting different codes for
#: the same absence.
from genios_engine.contracts.units import UNKNOWN_CURRENCY as UNKNOWN_CURRENCY_CODE
from genios_engine.context.analytic.history import (HISTORY_TABLE, MAX_RETAINED_PERIODS,
                                                    MetricDefinition, MetricGrain,
                                                    MetricHistoryStore, MetricRegistry,
                                                    PostgresMetricHistory, RETENTION_MONTHS,
                                                    SampleReason, default_registry, gap_point,
                                                    months_before, period_start)
from genios_engine.context.situations import DORMANT_AFTER_DAYS, STATUS_ACTIVE

# The direction map is IMPORTED rather than restated. `context/waiting.py` already establishes
# that `thread.last_outbound` / `thread.last_inbound` source refs ARE the directed message
# timeline; a second copy of that mapping here would fork the day either is edited, and the two
# would then disagree about which messages count as inbound — invisibly, in a comparison engine.
from genios_engine.context.waiting import _DIRECTION_FIELD as _TIMELINE_DIRECTION

__all__ = [
    "BACKFILLABLE", "Cadence", "DEFAULT_POINT_BUDGET", "LastPoint", "MetricSpec", "NodeSnapshot",
    "NotBackfillable", "OrgSnapshot", "PointBudget", "Reading", "SampleRun", "SamplingContext",
    "BACKFILL_MONTHS", "SamplingDecision", "TRENDED_METRICS", "TrendedMetric",
    "backfill_history_for_drain", "backfill_org", "decide", "measure",
    "read_last_points", "read_org_snapshot", "resolve_history_store", "sample_org",
    "sampler_definitions", "sampler_registry",
]


# =================================================================================================
# TIME — every boundary comes from the store's one shared function
# =================================================================================================

def _as_utc(moment: datetime) -> datetime:
    if moment.tzinfo is None:
        raise ValueError("eval_time must be timezone-aware — a naive instant means whatever the "
                         "host's locale happens to be, and a series stamped in two zones is two "
                         "series")
    return moment.astimezone(timezone.utc)


def _day_start(moment: datetime) -> datetime:
    """UTC midnight. Used ONLY for the daily cadence test, never as a period key.

    `history.MetricGrain` has no DAY member and says why: a daily series is 730 rows per node per
    metric over the retention window. A daily CADENCE is a different thing from a daily GRAIN —
    it re-reads the current week's point, it does not mint a new one — so the day boundary exists
    here as a comparison and reaches no `observed_at`.
    """
    return _as_utc(moment).replace(hour=0, minute=0, second=0, microsecond=0)


def _whole_days(later: datetime, earlier: datetime) -> int:
    """Whole days between two instants, floored at zero. Integer seconds only — no float."""
    return max(0, int((later - earlier).total_seconds()) // 86_400)


def _whole_hours(later: datetime, earlier: datetime) -> int:
    return max(0, int((later - earlier).total_seconds()) // 3_600)


def _lower_median(values: Sequence[int]) -> int | None:
    """The LOWER middle element of a sorted sequence, or None when there is nothing to read.

    Not `statistics.median`: on an even-length sequence that averages the two middles, which
    produces a `.5` and therefore a float inside a measure. A p50 that is always an element of the
    series it summarises is also the only p50 a reader can go and check.
    """
    if not values:
        return None
    ordered = sorted(values)
    return ordered[(len(ordered) - 1) // 2]


# =================================================================================================
# THE REGISTRY — `TRENDED_METRICS` is an enum, not free strings
# =================================================================================================

class TrendedMetric(str, Enum):
    """The registered trended set (BLG-07). Adding a member is a DELIBERATE ACT.

    Free strings were the alternative and doc 04 names what they cost: a renamed metric splits its
    own series silently, and the split is invisible — the old rows stay, the new rows accumulate,
    and a trend computer reading either half reports "insufficient history" about a metric that
    has three years of it. An enum makes a rename a code change, and `sampler_registry()` makes
    the store refuse to write a name that is not in it.

    Every member carries, in `TRENDED_METRICS` below, the customer question it serves. A metric
    that cannot name one is storage growth with no reader.
    """

    ENGAGEMENT_TOUCH_COUNT_28D = "engagement.touch_count_28d"
    ENGAGEMENT_INBOUND_COUNT_28D = "engagement.inbound_count_28d"
    ENGAGEMENT_OUTBOUND_COUNT_28D = "engagement.outbound_count_28d"
    ENGAGEMENT_DAYS_SINCE_CONTACT = "engagement.days_since_contact"
    RELATIONSHIP_RESPONSE_LATENCY_HOURS = "relationship.response_latency_hours"
    ACCOUNT_CONTACT_BREADTH = "account.contact_breadth"
    ACCOUNT_OPEN_COMMITMENT_COUNT = "account.open_commitment_count"
    ACCOUNT_OVERDUE_COMMITMENT_COUNT = "account.overdue_commitment_count"
    DEAL_STAGE_AGE_DAYS = "deal.stage_age_days"
    DEAL_VALUE_MINOR_UNITS = "deal.value_minor_units"
    SUPPORT_TICKET_COUNT_28D = "support.ticket_count_28d"
    SUPPORT_BACKLOG_AGE_P50_DAYS = "support.backlog_age_p50_days"


class Cadence(str, Enum):
    """How often a matching rule wants a READING taken. Ordered by frequency, most frequent first.

    A cadence is not a row count. With every metric registered at a weekly grain, a daily cadence
    refreshes the current week's point rather than adding six more — see the module docstring.
    """

    IMMEDIATE = "immediate"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"


#: Frequency rank — lower is more frequent. A node matching several rows is sampled at the
#: STRONGEST cadence any of them asks for: rule 2 (in an active situation, daily) must not be
#: diluted to weekly because rule 1 also matched. Stated as data rather than as an `if`, so the
#: ordering is one line to read and one line to change.
_CADENCE_RANK: Mapping[Cadence, int] = {
    Cadence.IMMEDIATE: 0, Cadence.DAILY: 1, Cadence.WEEKLY: 2, Cadence.MONTHLY: 3,
}


@dataclass(frozen=True, slots=True)
class MetricSpec:
    """One registered metric: what it counts, who it is about, and what moves it.

    `changepoint_bp` is a RELATIVE threshold in basis points against the previous reading, not an
    absolute one, for the same reason `derived.py` scores engagement as a ratio: "halved" has to
    mean halved for this node, whether it ran at forty touches a month or four.
    """

    metric: TrendedMetric
    unit: MetricUnit
    #: Node types this metric is about. A metric sampled on a node type it cannot describe is a
    #: series of gaps that costs a row a week forever.
    subject_types: frozenset[str]
    #: Relative move, in basis points of the previous reading, that earns an off-cadence sample.
    changepoint_bp: int
    #: The customer question this metric exists to answer. Required by BLG-07 for every addition.
    question: str
    #: Can this metric be reconstructed from the event ledger? (U2 — the backfill sampler.)
    backfillable: bool = False
    #: The store's period key for this series. WEEK for eleven of the twelve — see the module
    #: docstring's arithmetic; it is the structural row cap, not a preference.
    grain: MetricGrain = MetricGrain.WEEK
    #: How many periods of this series the store keeps. 104 weeks = the 24-month horizon.
    retention_periods: int = MAX_RETAINED_PERIODS


def _spec(metric: TrendedMetric, unit: MetricUnit, subject_types: Iterable[str],
          changepoint_bp: int, question: str, *, backfillable: bool = False,
          grain: MetricGrain = MetricGrain.WEEK,
          retention_periods: int = MAX_RETAINED_PERIODS) -> MetricSpec:
    return MetricSpec(metric=metric, unit=unit, subject_types=frozenset(subject_types),
                      changepoint_bp=changepoint_bp, question=question, backfillable=backfillable,
                      grain=grain, retention_periods=retention_periods)


#: The node types BLG-07 row 1 names: "an account/deal/person".
_COUNTERPARTY = ("company", "person", "deal")
_ACCOUNT = ("company",)
_DEAL = ("company", "deal")     # `derived.py` writes `deal.*` onto companies AND deal nodes

#: THE REGISTERED SET. Twelve metrics, each with the question it serves. This mapping IS the
#: storage budget: `len(TRENDED_METRICS)` is the multiplier on every row of the arithmetic in the
#: module docstring, so a thirteenth member is a storage decision before it is a feature.
TRENDED_METRICS: Mapping[TrendedMetric, MetricSpec] = {
    s.metric: s for s in (
        _spec(TrendedMetric.ENGAGEMENT_TOUCH_COUNT_28D, MetricUnit.COUNT, _COUNTERPARTY, 3_000,
              "is engagement with this account declining?", backfillable=True),
        _spec(TrendedMetric.ENGAGEMENT_INBOUND_COUNT_28D, MetricUnit.COUNT, _COUNTERPARTY, 3_000,
              "have THEY gone quiet, as distinct from us not writing?", backfillable=True),
        _spec(TrendedMetric.ENGAGEMENT_OUTBOUND_COUNT_28D, MetricUnit.COUNT, _COUNTERPARTY, 3_000,
              "have WE gone quiet on an account we said we were working?", backfillable=True),
        _spec(TrendedMetric.ENGAGEMENT_DAYS_SINCE_CONTACT, MetricUnit.DAYS, _COUNTERPARTY, 5_000,
              "is this relationship going cold, 30+ days before it is obvious?",
              backfillable=True),
        # GAP FLAG — BLG-07 registers this metric in HOURS and `MetricUnit` (D-02) is a closed
        # four-member enum with no HOURS. The reading is whole hours and the metric NAME carries
        # that, so nothing is lost at the seam; `COUNT` ("a cardinal count") is the only member
        # that does not misstate it. `DAYS` was the alternative and it is worse than a unit
        # mismatch: most replies land inside a day, so a days-grained latency is a series of
        # zeros, and "they now take three days instead of four hours" — the exact question this
        # metric exists for — becomes 0 -> 3 with no way to see the four hours. Adding
        # `MetricUnit.HOURS` is a contract change and belongs to whoever owns `analytic.py`.
        _spec(TrendedMetric.RELATIONSHIP_RESPONSE_LATENCY_HOURS, MetricUnit.COUNT, _COUNTERPARTY,
              5_000, "are they taking longer to answer than they used to?", backfillable=True),
        _spec(TrendedMetric.ACCOUNT_CONTACT_BREADTH, MetricUnit.COUNT, _ACCOUNT, 2_500,
              "is this account single-threaded on one champion?"),
        _spec(TrendedMetric.ACCOUNT_OPEN_COMMITMENT_COUNT, MetricUnit.COUNT, _ACCOUNT, 2_500,
              "how much have we promised this account and not delivered?"),
        _spec(TrendedMetric.ACCOUNT_OVERDUE_COMMITMENT_COUNT, MetricUnit.COUNT, _ACCOUNT, 2_500,
              "is our reliability with this account getting worse?"),
        # THE ONE MONTHLY METRIC, and it is not a preference — `history.CORE_METRICS` already
        # registers this exact name at a MONTH grain with 24 periods (doc 04 names it as one of
        # its two examples), and `MetricRegistry` refuses one metric with two definitions. That
        # refusal is right: `read_series` walks the boundaries the DEFINITION names, so a series
        # written weekly and read monthly is a dense read that finds a gap in every period.
        # Conforming here rather than overriding keeps one metric to one definition across the
        # whole layer. The cost is real and belongs in the report: BLG-08 needs four points, so a
        # monthly stage age cannot say "quietly stalling" inside four months. Changing it is a
        # change to `CORE_METRICS`, which is L2.4.1's file.
        _spec(TrendedMetric.DEAL_STAGE_AGE_DAYS, MetricUnit.DAYS, _DEAL, 5_000,
              "is this deal quietly stalling in its current stage?",
              grain=MetricGrain.MONTH, retention_periods=RETENTION_MONTHS),
        _spec(TrendedMetric.DEAL_VALUE_MINOR_UNITS, MetricUnit.MINOR_UNITS, _DEAL, 1_000,
              "is the deal being negotiated down?"),
        _spec(TrendedMetric.SUPPORT_TICKET_COUNT_28D, MetricUnit.COUNT, _ACCOUNT, 3_000,
              "is this customer asking for help more than they used to?"),
        _spec(TrendedMetric.SUPPORT_BACKLOG_AGE_P50_DAYS, MetricUnit.DAYS, _ACCOUNT, 3_000,
              "is our unanswered-request pile getting older?"),
    )
}

#: The subset U2 can reconstruct from `source_events`. Everything here is a pure function of the
#: directed message timeline, which the event ledger already holds — so an 18-month L1 backfill
#: becomes 18 months of computable metric history the moment `backfill_org` runs. The other seven
#: read `graph_facts` and `open_loops`, which hold only the CURRENT value: replaying them would
#: mean asserting today's deal value was also true last March, which is a fabricated observation
#: with a `sample_reason` on it.
BACKFILLABLE: frozenset[TrendedMetric] = frozenset(
    m for m, s in TRENDED_METRICS.items() if s.backfillable)


def sampler_definitions() -> tuple[MetricDefinition, ...]:
    """The twelve, in the store's own vocabulary. DERIVED from `TRENDED_METRICS`, never retyped.

    Two hand-maintained lists of twelve metrics is the renamed-metric failure with extra steps:
    the store would happily accept a unit the sampler no longer measures in, and `to_row`'s unit
    check — the thing that stops a series meaning two different numbers — would be checking one
    copy against itself.
    """
    return tuple(MetricDefinition(spec.metric.value, spec.unit, spec.grain,
                                  retention_periods=spec.retention_periods)
                 for spec in TRENDED_METRICS.values())


#: The store's `MetricDefinition` for each of the twelve, built once. `gap_point` needs one, and
#: re-deriving the whole registry per gap would rebuild twelve definitions to read one.
_DEFINITION_BY_METRIC: Mapping[TrendedMetric, MetricDefinition] = {
    TrendedMetric(d.metric): d for d in sampler_definitions()}


def sampler_registry() -> MetricRegistry:
    """The store's core metrics plus this module's twelve. Immutable, built per call."""
    return default_registry().with_definitions(*sampler_definitions())


def resolve_history_store(store) -> MetricHistoryStore:
    """L2.4.1's Postgres store, bound to this module's registry.

    The registry has to travel with the store because `history.to_row` refuses an unregistered
    metric name — which is the mechanism that makes "a renamed metric splits its series" a loud
    failure. A sampler that constructed the store without its own definitions would be refused on
    the first write, which is the correct direction to fail in and a poor way to find out.
    """
    return PostgresMetricHistory(store.engine, sampler_registry())


#: Windows. `_TOUCH_WINDOW_DAYS` is the "28d" in four metric names — stated once so the name and
#: the arithmetic cannot drift. `_ACTIVITY_WINDOW_DAYS` is BLG-07 row 1's "activity in 90d".
_TOUCH_WINDOW_DAYS = 28
_ACTIVITY_WINDOW_DAYS = 90

#: How recent an activity must be for rule 4's "became active" to be about NOW rather than about
#: some revival last spring. Seven days, matched to the weekly default cadence: a revival the
#: weekly rule would have caught anyway does not need an off-cadence reading.
_REVIVAL_RECENT_DAYS = 7

#: How far back `read_org_snapshot` reconstructs the message timeline. Long enough for the 28-day
#: counts, the 90-day activity test, a year of latency history and a `days_since_contact` that is
#: a number rather than a gap for anyone touched inside a year.
_TIMELINE_WINDOW_DAYS = 400

#: `graph_facts` fields the sampler reads. An explicit list rather than `select *`: the fact table
#: is the largest in the graph, and pulling every field of every node to compute two metrics is
#: the per-node round-trip problem in bulk-query clothing.
_FACT_FIELDS = ("deal.stage", "deal.status", "deal.value", "deal.currency", "commitment.due_at")


# =================================================================================================
# U1 · THE SAMPLING POLICY — BLG-07's decision table, as data
# =================================================================================================

@dataclass(frozen=True, slots=True)
class NodeSnapshot:
    """One node, as the policy sees it. Every field is derived from the graph, none from a clock.

    `prior_activity_at` exists only for rule 4. "Dormant and became active" is not a state anyone
    stores; it is the shape of two timestamps — a recent one, and a long gap before it — and
    carrying both is what lets the rule be a pure function instead of a query.
    """

    node_id: str
    node_type: str
    #: Most recent evidence of any kind on this node. `None` = the graph has never seen it move.
    last_activity_at: datetime | None = None
    #: The most recent activity BEFORE `last_activity_at`. `None` = this was the first.
    prior_activity_at: datetime | None = None
    #: Is this node the anchor of an ACTIVE situation right now? (rule 2)
    in_active_situation: bool = False


@dataclass(frozen=True, slots=True)
class LastPoint:
    """The newest row `metric_history` already holds for one (node, metric).

    Two timestamps, and they answer different questions. `observed_at` is the PERIOD the reading
    describes — what a trend reads. `sampled_at` is when we last looked, and it is what the
    cadence test needs: with a weekly grain, "have I already sampled today?" cannot be asked of
    `observed_at`, because every reading taken this week shares one period key.
    """

    observed_at: datetime
    sampled_at: datetime
    value_bp: int | None


@dataclass(frozen=True, slots=True)
class SamplingContext:
    """Everything `decide()` is allowed to look at. A frozen input makes the decision replayable."""

    node: NodeSnapshot
    metric: TrendedMetric
    #: What the graph says right now — `None` when it cannot answer (a gap, never a zero).
    current_value_bp: int | None
    last_point: LastPoint | None
    eval_time: datetime

    @property
    def spec(self) -> MetricSpec:
        return TRENDED_METRICS[self.metric]


@dataclass(frozen=True, slots=True)
class SamplingDecision:
    """Sampled or not, which row of BLG-07 said so, and a sentence saying why.

    `explanation` is not decoration. This table is the thing an operator interrogates when the
    history table is bigger or thinner than expected, and "rule 2: node is the anchor of an active
    situation, daily, last sampled 2026-02-28" is the difference between that being a five-minute
    question and a day of bisecting.
    """

    sampled: bool
    rule: int | None
    cadence: Cadence | None
    sample_reason: SampleReason | None
    explanation: str


@dataclass(frozen=True, slots=True)
class _Rule:
    """One row of BLG-07. `matches` is eligibility; the cadence decides whether it is due."""

    number: int
    cadence: Cadence
    reason: SampleReason
    rationale: str
    matches: Callable[[SamplingContext], bool]


def _has_recent_activity(ctx: SamplingContext, days: int) -> bool:
    at = ctx.node.last_activity_at
    return at is not None and _whole_days(_as_utc(ctx.eval_time), _as_utc(at)) <= days


def _rule_1(ctx: SamplingContext) -> bool:
    """Trended metric, on an account/deal/person with activity in 90d. The default set.

    The node-type test is what stops a `thread` or a synthetic `backlog_item` anchor — the graph
    holds thousands — from opening a twelve-metric series each.
    """
    return (ctx.node.node_type in ctx.spec.subject_types
            and _has_recent_activity(ctx, _ACTIVITY_WINDOW_DAYS))


def _rule_2(ctx: SamplingContext) -> bool:
    """The node anchors an ACTIVE situation. While something is live, resolution matters."""
    return ctx.node.in_active_situation and ctx.node.node_type in ctx.spec.subject_types


def _rule_3(ctx: SamplingContext) -> bool:
    """The value moved further than this metric's `changepoint_bp` since the last point.

    Three refusals are load-bearing. There is no changepoint without a CURRENT reading (a gap is
    not a move to zero); none against a previous point that carried no value; and none with no
    previous point at all — the first reading of a series is rule 1, 2 or 5's business, and
    calling it a changepoint would tag every new node in the graph as a revival.
    """
    last = ctx.last_point
    if ctx.current_value_bp is None or last is None or last.value_bp is None:
        return False
    return _relative_move_bp(last.value_bp, ctx.current_value_bp) > ctx.spec.changepoint_bp


def _rule_4(ctx: SamplingContext) -> bool:
    """The node was dormant and came back. Revival is a signal.

    Fires ONCE per revival, not once a day for a week: the guard is that nothing has been sampled
    since the revival landed. Without it a returning account would take an off-cadence reading
    every sweep for seven days — and while the weekly grain means those are overwrites rather than
    new rows, they are still a re-measure of the whole org's twelve metrics on every sweep, which
    is CPU spent to rewrite a number that has not changed.

    `DORMANT_AFTER_DAYS` is imported from `situations.py` rather than restated: that module
    already declares when a thing has gone quiet, and two modules disagreeing about the length of
    a silence is how a revival becomes invisible on one surface and loud on another.
    """
    node = ctx.node
    if node.node_type not in ctx.spec.subject_types or node.last_activity_at is None:
        return False
    if not _has_recent_activity(ctx, _REVIVAL_RECENT_DAYS):
        return False
    if node.prior_activity_at is not None:
        gap_days = _whole_days(_as_utc(node.last_activity_at), _as_utc(node.prior_activity_at))
        if gap_days < DORMANT_AFTER_DAYS:
            return False            # never went quiet; this is just an ordinary active node
    elif ctx.last_point is None:
        return False                # brand new node, no history to have been dormant from
    return ctx.last_point is None or ctx.last_point.sampled_at < _as_utc(node.last_activity_at)


def _rule_5(ctx: SamplingContext) -> bool:
    """The monthly floor: a guaranteed density for long-horizon trends.

    SCOPED, and the scope is the difference between a floor and an unbounded write. Read as
    "every node in the graph", rule 5 alone is 600k rows a month on a 50k-node org — the exact
    shape of the incident this file is written against. It applies to a node that is
    metric-eligible AND either ALREADY HOLDS A SERIES or is currently active.

    An existing series is the case this row exists for: a decline to nothing is only visible if
    the series keeps a point after the activity stops, and without this row the series would
    simply END and a trend computer would report "insufficient history" about the account that
    went dark — the most informative shape in the table read as an absence of data.

    A node that went quiet 200 days ago and never had a series does NOT start one here. Doc 09's
    acceptance row says such a node is not sampled weekly; sampling it monthly instead would be
    the same unbounded write at a twelfth of the rate, on every counterparty the business has
    ever exchanged a message with. Whatever is true about it will be measurable the moment it
    comes back, because rules 1 and 4 both fire then.
    """
    if ctx.node.node_type not in ctx.spec.subject_types:
        return False
    return ctx.last_point is not None or _has_recent_activity(ctx, _ACTIVITY_WINDOW_DAYS)


#: BLG-07, one entry per row, in the doc's own order. Table-driven so that "which rules fired" is
#: a comprehension rather than a chain of `if`s nobody can audit against the spec.
_RULES: tuple[_Rule, ...] = (
    _Rule(1, Cadence.WEEKLY, SampleReason.SCHEDULED,
          "trended metric on an account/deal/person with activity in 90d", _rule_1),
    _Rule(2, Cadence.DAILY, SampleReason.SCHEDULED,
          "node is the anchor of an active situation", _rule_2),
    _Rule(3, Cadence.IMMEDIATE, SampleReason.CHANGEPOINT,
          "value moved more than the metric's changepoint_bp", _rule_3),
    _Rule(4, Cadence.IMMEDIATE, SampleReason.CHANGEPOINT,
          "node was dormant and became active", _rule_4),
    _Rule(5, Cadence.MONTHLY, SampleReason.SCHEDULED,
          "month boundary — the floor density for long-horizon trends", _rule_5),
)

#: Larger than any `changepoint_bp` can be set to, so a move off a zero baseline always counts.
_OFF_SCALE_BP = 1_000_000


def _relative_move_bp(previous: int, current: int) -> int:
    """|current - previous| as basis points OF THE PREVIOUS READING. Integer division only.

    A previous reading of zero has no scale to be a proportion of, and 0 -> 1 overdue commitments
    is the single most informative sample this table can take. It is therefore reported as a move
    off the top of the scale rather than as a division by zero — the caller compares against
    `changepoint_bp`, which is bounded, so "off the scale" always wins.
    """
    delta = abs(current - previous)
    if previous == 0:
        return 0 if delta == 0 else _OFF_SCALE_BP
    return delta * 10_000 // abs(previous)


def _month_start(moment: datetime) -> datetime:
    return _day_start(moment).replace(day=1)


def _cadence_due(cadence: Cadence, last: LastPoint | None, eval_time: datetime) -> bool:
    """Has this cadence come round since we last LOOKED?

    Measured against `sampled_at`, not `observed_at`, and the difference is the whole reason both
    are carried: every metric here is stored at a weekly grain, so eight readings taken in one
    week share one `observed_at` and a due test written against it could never distinguish daily
    from weekly. `sampled_at` is when the sampler last ran on this series, which is exactly what a
    cadence is about.

    Rule 5's test is a MONTH BOUNDARY rather than "30 days ago". The two differ by up to a day and
    a half a year, and the difference is whether a monthly floor gives twelve points a year or
    drifts by one every February.
    """
    if last is None or cadence is Cadence.IMMEDIATE:
        return True
    if cadence is Cadence.DAILY:
        return last.sampled_at < _day_start(eval_time)
    if cadence is Cadence.WEEKLY:
        return last.sampled_at < period_start(eval_time, MetricGrain.WEEK)
    return last.sampled_at < _month_start(eval_time)


def decide(ctx: SamplingContext) -> SamplingDecision:
    """BLG-07: is this (node, metric) sampled at this `eval_time`, and under which row?

    "A metric is sampled if ANY row matches", so every row is evaluated and the STRONGEST cadence
    among the matches wins — a node that is both weekly-eligible and inside an active situation is
    sampled daily, not weekly. Ties break to the lowest rule number, so the answer is stable
    across runs and across a reordering of the table.
    """
    matched = [rule for rule in _RULES if rule.matches(ctx)]
    if not matched:
        return SamplingDecision(False, None, None, None, "no BLG-07 row matches — not sampled")

    due = [rule for rule in matched if _cadence_due(rule.cadence, ctx.last_point, ctx.eval_time)]
    seen_at = ctx.last_point.sampled_at.date().isoformat() if ctx.last_point else "never"
    if not due:
        cadences = ", ".join(f"rule {r.number} ({r.cadence.value})" for r in matched)
        return SamplingDecision(False, None, None, None,
                                f"matched {cadences} but none is due — last sampled {seen_at}")

    winner = min(due, key=lambda r: (_CADENCE_RANK[r.cadence], r.number))
    return SamplingDecision(
        True, winner.number, winner.cadence, winner.reason,
        f"rule {winner.number}: {winner.rationale} — {winner.cadence.value}, "
        f"last sampled {seen_at}")


# =================================================================================================
# MEASUREMENT — the live graph turned into readings
# =================================================================================================

@dataclass(frozen=True, slots=True)
class Reading:
    """One measurement attempt. `value_bp is None` means the graph COULD NOT ANSWER.

    The distinction this type exists to hold is the whole of "a metric with no reading is not
    zero". `engagement.touch_count_28d = 0` on a node we have corresponded with for two years is
    a real and alarming reading. The same 0 on a node we have never exchanged a message with is a
    lie that makes every trend above it wrong in the confident direction.
    """

    value_bp: int | None
    #: Could a connected source have carried this metric for this node at all? Tri-state, exactly
    #: as `MetricPoint.coverage_ready` — `None` is unhinted and is NOT a synonym for False.
    coverage_ready: bool | None = None
    currency: str | None = None

    @property
    def known(self) -> bool:
        return self.value_bp is not None


@dataclass(frozen=True, slots=True)
class OrgSnapshot:
    """Everything the sampler reads, pulled in a fixed number of bulk queries.

    Per-node round-trips are the documented L2 performance failure — a reasoning pass that made
    ~1,000 of them took thirty minutes and blocked emission. A sampler is the same shape but
    worse, because it runs on EVERY sweep, so the graph is read once into this object and every
    metric is computed against it in memory.
    """

    org_id: str
    eval_time: datetime
    nodes: Mapping[str, NodeSnapshot]
    #: node_id -> the directed message timeline, oldest first: ("in" | "out", occurred_at).
    timeline: Mapping[str, tuple[tuple[str, datetime], ...]]
    #: node_id -> field -> (value, occurred_at). Only `_FACT_FIELDS`.
    facts: Mapping[str, Mapping[str, tuple[Any, datetime | None]]]
    #: company node_id -> the person node_ids that work there.
    people_by_company: Mapping[str, tuple[str, ...]]
    #: node_id -> open-loop `opened_at`s, the closest thing this graph has to a support queue.
    open_asks: Mapping[str, tuple[datetime, ...]]
    #: Does this org have ANY open-loop ledger at all? False => the support metrics are unknown
    #: for every node, not zero. There is no helpdesk in this product's data model.
    has_support_desk: bool
    #: (node_id, metric name) -> the newest row already in `metric_history`.
    last_points: Mapping[tuple[str, str], LastPoint]


def _count_in_window(timeline: Sequence[tuple[str, datetime]], since: datetime,
                     direction: str | None = None) -> int:
    return sum(1 for d, at in timeline
               if at >= since and (direction is None or d == direction))


def _reply_latencies_hours(timeline: Sequence[tuple[str, datetime]], since: datetime) -> list[int]:
    """Whole hours from each outbound to the counterparty's NEXT inbound, inside the window.

    Copied in SHAPE from `waiting._reply_gaps` and integer-only here: only the first reply after
    an outbound counts, and consecutive outbounds with no reply between them contribute nothing.
    An unanswered message has no latency yet, and scoring it as zero would make a silent
    counterparty look fast — which would then read as an improving trend.
    """
    gaps: list[int] = []
    pending: datetime | None = None
    for direction, at in timeline:
        if at < since:
            continue
        if direction == "out":
            if pending is None:
                pending = at
        elif pending is not None:
            gaps.append(_whole_hours(at, pending))
            pending = None
    return gaps


def _as_int(value: Any) -> int | None:
    """A graph fact read as an integer measure, or None. Never a float, never a coercion of text.

    `graph_facts.value` is jsonb and a deal value has arrived as `250000`, as `"250000"` and as
    `250000.0` from three different writers. The first two are readings; the third is a float in a
    measure path, and it is accepted ONLY when it is exactly integral, because `2.5` reaching
    `MetricPoint` as `2` is a rounded measurement that cannot be compared to itself across a
    version.
    """
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value) if value.is_integer() else None
    if isinstance(value, str):
        try:
            return int(value.strip())
        except ValueError:
            return None
    return None


def _parse_moment(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return _as_utc(value) if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
        return _as_utc(parsed) if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    return None


def _touch_since(snapshot: OrgSnapshot) -> datetime:
    return _as_utc(snapshot.eval_time) - timedelta(days=_TOUCH_WINDOW_DAYS)


def _engagement_probe(direction: str | None) -> Callable[[OrgSnapshot, str], Reading]:
    """A 28-day directed message count. Zero is a READING; no timeline at all is a GAP.

    The dividing line: if the graph holds any directed message for this node inside the timeline
    window, then a 28-day window with none in it means they stopped, which is precisely the fact
    the metric exists to catch. If it holds none at all, we have no correspondence channel to this
    node and "0 touches" would be a statement about our connectors, not about the relationship.
    """
    def probe(snapshot: OrgSnapshot, node_id: str) -> Reading:
        timeline = snapshot.timeline.get(node_id)
        if not timeline:
            return Reading(None, coverage_ready=False)
        return Reading(_count_in_window(timeline, _touch_since(snapshot), direction),
                       coverage_ready=True)
    return probe


def _days_since_contact(snapshot: OrgSnapshot, node_id: str) -> Reading:
    """Whole days since the last message either way. Never contacted => a gap, not a big number."""
    timeline = snapshot.timeline.get(node_id)
    if not timeline:
        return Reading(None, coverage_ready=False)
    return Reading(_whole_days(_as_utc(snapshot.eval_time), max(at for _, at in timeline)),
                   coverage_ready=True)


def _response_latency_hours(snapshot: OrgSnapshot, node_id: str) -> Reading:
    """p50 reply latency in whole hours over the touch window. No reply in it => a gap.

    A relationship with no reply this month has no latency — it has a silence, which is what
    `engagement.days_since_contact` measures. Writing 0 here would make the least responsive
    counterparty in the graph the fastest.
    """
    timeline = snapshot.timeline.get(node_id)
    if not timeline:
        return Reading(None, coverage_ready=False)
    p50 = _lower_median(_reply_latencies_hours(timeline, _touch_since(snapshot)))
    return Reading(p50, coverage_ready=True)


def _contact_breadth(snapshot: OrgSnapshot, node_id: str) -> Reading:
    """How many distinct people at this account we have heard from or written to in 90 days.

    An account with people mapped but none active is single-threaded to zero, which is a reading.
    An account with no people mapped at all is a gap: we do not know its org chart, and 0 would
    read as "nobody works there".
    """
    people = snapshot.people_by_company.get(node_id)
    if not people:
        return Reading(None, coverage_ready=False)
    since = _as_utc(snapshot.eval_time) - timedelta(days=_ACTIVITY_WINDOW_DAYS)
    active = sum(1 for person in people
                 if any(at >= since for _, at in snapshot.timeline.get(person, ())))
    return Reading(active, coverage_ready=True)


def _commitment_moments(snapshot: OrgSnapshot, node_id: str) -> list[datetime] | None:
    """Every `commitment.due_at` on this account or its people, or None when nothing is known.

    A commitment is extracted onto the PERSON who made or received it and rolled up to the
    company by `derived.compute_deal_view`; reading only the account node would report zero
    promises for every account whose promises are all on its people, which is all of them.
    """
    subjects = [node_id, *snapshot.people_by_company.get(node_id, ())]
    seen_any_fact = False
    moments: list[datetime] = []
    for subject in subjects:
        fields = snapshot.facts.get(subject)
        if not fields:
            continue
        seen_any_fact = True
        raw = fields.get("commitment.due_at")
        if raw is None:
            continue
        due = _parse_moment(raw[0])
        if due is not None:
            moments.append(due)
    return moments if seen_any_fact else None


def _open_commitment_count(snapshot: OrgSnapshot, node_id: str) -> Reading:
    moments = _commitment_moments(snapshot, node_id)
    if moments is None:
        return Reading(None, coverage_ready=False)
    return Reading(len(moments), coverage_ready=True)


def _overdue_commitment_count(snapshot: OrgSnapshot, node_id: str) -> Reading:
    moments = _commitment_moments(snapshot, node_id)
    if moments is None:
        return Reading(None, coverage_ready=False)
    now = _as_utc(snapshot.eval_time)
    return Reading(sum(1 for due in moments if due < now), coverage_ready=True)


def _stage_age_days(snapshot: OrgSnapshot, node_id: str) -> Reading:
    """Days the deal has sat in its CURRENT stage — the "quietly stalling" metric.

    The clock is the stage fact's own `occurred_at`, which `graph_facts` rewrites whenever the
    stage is re-derived, so the age resets when the stage moves and only then. No stage fact means
    we do not know what stage it is in, which is not an age of zero.
    """
    fields = snapshot.facts.get(node_id) or {}
    for name in ("deal.stage", "deal.status"):
        entry = fields.get(name)
        if entry is None or entry[1] is None:
            continue
        return Reading(_whole_days(_as_utc(snapshot.eval_time), _as_utc(entry[1])),
                       coverage_ready=True)
    return Reading(None, coverage_ready=False)


def _deal_value(snapshot: OrgSnapshot, node_id: str) -> Reading:
    """The deal's value in minor units, or a gap — and it is a gap almost everywhere on purpose.

    `derived.py` refuses to infer `deal.value` ("there is no honest way to infer a number nobody
    stated"), so this metric is present on one node of the live graph and absent on the rest. That
    is the correct shape and it is why this file exists: a sampler that wrote 0 for the other
    thirty-two would have produced a pipeline that collapsed to nothing in March, and a cohort in
    which every real deal was compared against fabricated zeros.
    """
    fields = snapshot.facts.get(node_id) or {}
    entry = fields.get("deal.value")
    if entry is None:
        return Reading(None, coverage_ready=False)
    value = _as_int(entry[0])
    if value is None:
        return Reading(None, coverage_ready=False)
    currency = fields.get("deal.currency")
    code = currency[0] if currency and isinstance(currency[0], str) else None
    return Reading(value, coverage_ready=True, currency=(code or UNKNOWN_CURRENCY_CODE).upper())


def _support_subjects(snapshot: OrgSnapshot, node_id: str) -> list[str]:
    return [node_id, *snapshot.people_by_company.get(node_id, ())]


def _support_ticket_count(snapshot: OrgSnapshot, node_id: str) -> Reading:
    """Unmet requests opened against this account in the touch window.

    NOT a ticket count, and `support_situations.py` states the rule this obeys: this tenant has no
    helpdesk, no queue and no SLA, and asserting one is worse than a gap because it looks like
    coverage. The registered metric NAME comes from BLG-07 and is kept so the series is
    identifiable across the layer; the measurement is open asks, and when the org has no
    open-loop ledger at all the reading is unknown rather than zero.
    """
    if not snapshot.has_support_desk:
        return Reading(None, coverage_ready=False)
    since = _touch_since(snapshot)
    subjects = _support_subjects(snapshot, node_id)
    return Reading(sum(1 for s in subjects for at in snapshot.open_asks.get(s, ()) if at >= since),
                   coverage_ready=True)


def _backlog_age_p50(snapshot: OrgSnapshot, node_id: str) -> Reading:
    """p50 age in whole days of this account's still-open asks. An empty backlog has no age."""
    if not snapshot.has_support_desk:
        return Reading(None, coverage_ready=False)
    now = _as_utc(snapshot.eval_time)
    ages = [_whole_days(now, at)
            for s in _support_subjects(snapshot, node_id) for at in snapshot.open_asks.get(s, ())]
    return Reading(_lower_median(ages), coverage_ready=True)


_PROBES: Mapping[TrendedMetric, Callable[[OrgSnapshot, str], Reading]] = {
    TrendedMetric.ENGAGEMENT_TOUCH_COUNT_28D: _engagement_probe(None),
    TrendedMetric.ENGAGEMENT_INBOUND_COUNT_28D: _engagement_probe("in"),
    TrendedMetric.ENGAGEMENT_OUTBOUND_COUNT_28D: _engagement_probe("out"),
    TrendedMetric.ENGAGEMENT_DAYS_SINCE_CONTACT: _days_since_contact,
    TrendedMetric.RELATIONSHIP_RESPONSE_LATENCY_HOURS: _response_latency_hours,
    TrendedMetric.ACCOUNT_CONTACT_BREADTH: _contact_breadth,
    TrendedMetric.ACCOUNT_OPEN_COMMITMENT_COUNT: _open_commitment_count,
    TrendedMetric.ACCOUNT_OVERDUE_COMMITMENT_COUNT: _overdue_commitment_count,
    TrendedMetric.DEAL_STAGE_AGE_DAYS: _stage_age_days,
    TrendedMetric.DEAL_VALUE_MINOR_UNITS: _deal_value,
    TrendedMetric.SUPPORT_TICKET_COUNT_28D: _support_ticket_count,
    TrendedMetric.SUPPORT_BACKLOG_AGE_P50_DAYS: _backlog_age_p50,
}

#: Every registered metric must have a probe. A registry entry with no measurement is a series of
#: gaps that costs a row a week forever and reads, on a card, as "we looked and found nothing".
assert set(_PROBES) == set(TRENDED_METRICS), "every registered metric needs a probe"


def measure(snapshot: OrgSnapshot, node_id: str, metric: TrendedMetric) -> Reading:
    """The reading for one (node, metric) at `snapshot.eval_time`, or an honest gap.

    Dispatched through a table rather than a chain of `if metric ==`, so a registered metric with
    no probe is caught at import by the assertion above rather than becoming a silent gap series.
    """
    return _PROBES[metric](snapshot, node_id)


# =================================================================================================
# U3 · THE POINT BUDGET GUARD
# =================================================================================================

#: Points one org may write in one sweep. Sized against the arithmetic in the module docstring: an
#: ordinary sweep on a 1,500-node org writes low hundreds, and a 50k-node org's FIRST sweep — where
#: every eligible node is due its first point — is the case this number exists to stop becoming a
#: 500k-row insert. What is dropped is deterministic and is picked up on the next sweep.
DEFAULT_POINT_BUDGET = 20_000


@dataclass(slots=True)
class PointBudget:
    """A per-sweep, per-org cap on history points, with an audit of what it refused.

    Truncation is DETERMINISTIC: candidates are ordered by (node_id, metric) before the guard sees
    them, so the same graph at the same `eval_time` always drops the same tail. A random or
    hash-ordered truncation would make two identical sweeps produce different tables, which is the
    one property a comparison engine may not lose.
    """

    limit: int = DEFAULT_POINT_BUDGET
    spent: int = 0
    dropped: int = 0

    def take(self) -> bool:
        if self.spent >= self.limit:
            self.dropped += 1
            return False
        self.spent += 1
        return True

    @property
    def exhausted(self) -> bool:
        return self.spent >= self.limit


# =================================================================================================
# READING THE GRAPH — a fixed number of bulk queries, never one per node
# =================================================================================================

_NODES_SQL = text(
    "select node_id, node_type from graph_nodes "
    "where org_id = :o and valid_to is null and node_type = any(:types)")

_ACTIVITY_SQL = text(
    "select subject_node_id as node_id, occurred_at from graph_observations "
    "where org_id = :o and status = 'active' and subject_node_id is not null "
    "and occurred_at is not null and occurred_at >= :since")

_TIMELINE_SQL = text(
    "select f.subject_node_id as node_id, f.field as field, se.occurred_at as at "
    "from graph_source_refs r "
    "join graph_facts f on f.fact_version_id = r.fact_version_id and f.org_id = r.org_id "
    "join source_events se on se.event_id = r.event_id "
    "where r.org_id = :o and f.field = any(:fields) and se.occurred_at >= :since")

_FACTS_SQL = text(
    "select subject_node_id as node_id, field, value, occurred_at, valid_from "
    "from graph_facts where org_id = :o and valid_to is null and status = 'active' "
    "and field = any(:fields)")

_WORKS_AT_SQL = text(
    "select from_node_id as person, to_node_id as company from graph_edges "
    "where org_id = :o and valid_to is null and edge_type = 'works_at'")

_SITUATIONS_SQL = text(
    "select distinct anchor_node_id from context_situations "
    "where org_id = :o and status = :active and anchor_node_id is not null")

_OPEN_LOOPS_SQL = text(
    "select subject_node_id, opened_at, status from open_loops where org_id = :o")

#: The one place this module READS its own table. `MetricHistoryStore` exposes `get` and
#: `read_series`, both per-series — correct for a trend computer asking about one account, and
#: catastrophic here: the policy needs the newest point for EVERY (node, metric) before it can
#: decide anything, which is 18,000 round-trips on a 1,500-node org and is the O(nodes) failure
#: that made the reasoning pass take thirty minutes. One `distinct on` answers all of it.
_LAST_POINTS_SQL = text(
    f"select distinct on (subject_node_id, metric) subject_node_id, metric, observed_at, "
    f"       sampled_at, value_bp "
    f"from {HISTORY_TABLE} where org_id = :o and metric = any(:metrics) "
    f"order by subject_node_id, metric, observed_at desc, sampled_at desc")


def read_last_points(engine, org_id: str) -> dict[tuple[str, str], LastPoint]:
    """The newest stored point per (node, metric) for one org, in one query."""
    names = sorted(m.value for m in TRENDED_METRICS)
    with engine.connect() as conn:
        rows = conn.execute(_LAST_POINTS_SQL, {"o": org_id, "metrics": names}).all()
    return {(str(r.subject_node_id), str(r.metric)):
            LastPoint(observed_at=_as_utc(r.observed_at), sampled_at=_as_utc(r.sampled_at),
                      value_bp=_as_int(r.value_bp))
            for r in rows}


def _two_latest(moments: Sequence[datetime]) -> tuple[datetime | None, datetime | None]:
    """The most recent moment and the one before it — everything rule 4 needs, in one pass."""
    latest = prior = None
    for at in moments:
        if latest is None or at > latest:
            latest, prior = at, latest
        elif prior is None or at > prior:
            prior = at
    return latest, prior


def read_org_snapshot(store, org_id: str, *, eval_time: datetime,
                      last_points: Mapping[tuple[str, str], LastPoint] | None = None,
                      window_days: int = _TIMELINE_WINDOW_DAYS) -> OrgSnapshot:
    """Eight bulk reads, one org. No per-node query anywhere in this function or below it.

    `window_days` is how far back the message timeline and the activity moments are read. The
    default is the LIVE sampler's window and every metric it measures fits inside it (the widest
    is 90 days). The backfill passes a wider one because it is reconstructing periods that far
    predate the live window — sharing the sampler's 400 days would silently cap an 18-month
    reconstruction at thirteen, and the missing periods would look like gaps in the data rather
    than a window that was too small to see them.
    """
    eval_time = _as_utc(eval_time)
    subject_types = sorted({t for spec in TRENDED_METRICS.values() for t in spec.subject_types})
    activity_since = eval_time - timedelta(days=window_days)

    with store.engine.connect() as conn:
        node_rows = conn.execute(_NODES_SQL, {"o": org_id, "types": subject_types}).all()
        activity_rows = conn.execute(_ACTIVITY_SQL, {"o": org_id, "since": activity_since}).all()
        timeline_rows = conn.execute(
            _TIMELINE_SQL, {"o": org_id, "fields": sorted(_TIMELINE_DIRECTION),
                            "since": activity_since}).all()
        fact_rows = conn.execute(_FACTS_SQL, {"o": org_id, "fields": list(_FACT_FIELDS)}).all()
        edge_rows = conn.execute(_WORKS_AT_SQL, {"o": org_id}).all()
        situation_rows = conn.execute(_SITUATIONS_SQL,
                                      {"o": org_id, "active": STATUS_ACTIVE}).all()
        loop_rows = conn.execute(_OPEN_LOOPS_SQL, {"o": org_id}).all()

    timeline: dict[str, list[tuple[str, datetime]]] = {}
    for row in timeline_rows:
        direction = _TIMELINE_DIRECTION.get(str(row.field))
        at = _parse_moment(row.at)
        if direction is None or at is None:
            continue
        timeline.setdefault(str(row.node_id), []).append((direction, at))
    for entries in timeline.values():
        # Sorted by (moment, direction) rather than by moment alone: two messages carrying the
        # same timestamp would otherwise order by whatever the planner returned, and the reply
        # latency below reads the sequence. A stable order is what makes two identical sweeps
        # produce byte-identical points.
        entries.sort(key=lambda e: (e[1], e[0]))

    # Activity = an observation OR a message. Observations alone miss the structured lane (a
    # calendar event commits facts and no observation), and messages alone miss a node whose only
    # evidence is an extracted moment. Rules 1, 4 and 5 all hang off this, so a miss here reads as
    # "dormant" on a node the graph watched move yesterday.
    moments: dict[str, list[datetime]] = {}
    for row in activity_rows:
        at = _parse_moment(row.occurred_at)
        if at is not None:
            moments.setdefault(str(row.node_id), []).append(at)
    for node_id, entries in timeline.items():
        moments.setdefault(node_id, []).extend(at for _, at in entries)

    facts: dict[str, dict[str, tuple[Any, datetime | None]]] = {}
    for row in fact_rows:
        value = row.value
        if isinstance(value, str):
            try:
                value = json.loads(value)
            except (ValueError, TypeError):
                pass
        at = _parse_moment(row.occurred_at) or _parse_moment(row.valid_from)
        facts.setdefault(str(row.node_id), {})[str(row.field)] = (value, at)

    people_by_company: dict[str, list[str]] = {}
    for row in edge_rows:
        people_by_company.setdefault(str(row.company), []).append(str(row.person))

    active_anchors = {str(r.anchor_node_id) for r in situation_rows}

    open_asks: dict[str, list[datetime]] = {}
    for row in loop_rows:
        if str(row.status) != "open":
            continue
        at = _parse_moment(row.opened_at)
        if at is not None:
            open_asks.setdefault(str(row.subject_node_id), []).append(at)

    nodes: dict[str, NodeSnapshot] = {}
    for row in node_rows:
        node_id = str(row.node_id)
        latest, prior = _two_latest(moments.get(node_id, ()))
        nodes[node_id] = NodeSnapshot(
            node_id=node_id, node_type=str(row.node_type), last_activity_at=latest,
            prior_activity_at=prior, in_active_situation=node_id in active_anchors)

    return OrgSnapshot(
        org_id=org_id, eval_time=eval_time, nodes=nodes,
        timeline={k: tuple(v) for k, v in timeline.items()},
        facts=facts,
        people_by_company={k: tuple(sorted(v)) for k, v in people_by_company.items()},
        open_asks={k: tuple(sorted(v)) for k, v in open_asks.items()},
        has_support_desk=bool(loop_rows),
        last_points=dict(last_points) if last_points is not None
        else read_last_points(store.engine, org_id))


# =================================================================================================
# THE SWEEP ENTRY POINT
# =================================================================================================

@dataclass(frozen=True, slots=True)
class SampleRun:
    """What one sweep of the sampler did, in numbers an operator can act on.

    `by_rule` is the row-growth audit: it says which line of BLG-07 is producing the table, which
    is the first question anyone asks when `metric_history` is bigger or thinner than the
    arithmetic said. `written` is what the store reports CHANGED, so a second sweep in the same
    period reports 0 — that number is the idempotency proof, not a failure.
    """

    org_id: str
    eval_time: datetime
    written: int
    considered: int
    dropped_over_budget: int
    #: The points that were stored, in the order they were built. Deterministic.
    points: tuple[MetricPoint, ...] = ()
    #: The honest absences: `known=False`, no value, and NO ROW. Carried so a caller can see what
    #: the graph could not answer without having to diff the table against the registry.
    gap_points: tuple[MetricPoint, ...] = ()
    by_rule: Mapping[int, int] = field(default_factory=dict)

    @property
    def gaps(self) -> int:
        return len(self.gap_points)

    @property
    def budget_exhausted(self) -> bool:
        return self.dropped_over_budget > 0


def _build_point(node_id: str, metric: TrendedMetric, reading: Reading,
                 observed_at: datetime) -> MetricPoint:
    """A reading plus a period becomes a `MetricPoint`, and the contract refuses the bad shapes.

    Built through the real contract rather than a dict on purpose: V-3 (a gap carries no value, a
    reading carries one) and the minor-units currency rule are enforced HERE, at the seam that
    produced the object, rather than by whoever reads the table in March.
    """
    spec = TRENDED_METRICS[metric]
    return MetricPoint(
        subject_node_id=node_id,
        metric=metric.value,
        value_bp=reading.value_bp,
        unit=spec.unit,
        currency=reading.currency if spec.unit is MetricUnit.MINOR_UNITS else None,
        observed_at=observed_at,
        known=True,
        coverage_ready=reading.coverage_ready)


def _candidate_order(snapshot: OrgSnapshot) -> list[tuple[str, TrendedMetric]]:
    """Every (node, metric) pair, in ONE fixed order.

    Sorted before the budget guard sees it so truncation is deterministic — the same graph at the
    same `eval_time` drops the same tail every time, and the next sweep picks it up from there. A
    dict-order or hash-order traversal would make two identical sweeps of a budget-limited org
    write two different tables, which is the one property a comparison engine may not lose.
    """
    ordered_metrics = sorted(TRENDED_METRICS, key=lambda m: m.value)
    return [(node_id, metric)
            for node_id in sorted(snapshot.nodes)
            for metric in ordered_metrics]


def sample_org(store, *, org_id: str, eval_time: datetime,
               history: MetricHistoryStore | None = None,
               budget: PointBudget | None = None,
               snapshot: OrgSnapshot | None = None) -> SampleRun:
    """Take this sweep's readings for one org and land them in `metric_history`.

    `eval_time` is REQUIRED and there is no default: a sampler that reached for a clock would
    stamp every reading with when the sweep happened to run, two sweeps of one graph would
    disagree, and the primary key that makes a re-run an overwrite would stop matching.

    Points are written in two batches because `MetricHistoryStore.put` takes ONE `sample_reason`
    per call and the reason is per-point — an off-cadence changepoint and a scheduled reading are
    different provenance and the column exists to tell them apart.
    """
    eval_time = _as_utc(eval_time)
    history = history or resolve_history_store(store)
    snapshot = snapshot or read_org_snapshot(store, org_id, eval_time=eval_time)
    budget = budget or PointBudget()

    by_reason: dict[SampleReason, list[MetricPoint]] = {}
    gap_points: list[MetricPoint] = []
    by_rule: dict[int, int] = {}
    considered = 0

    for node_id, metric in _candidate_order(snapshot):
        node = snapshot.nodes[node_id]
        spec = TRENDED_METRICS[metric]
        if node.node_type not in spec.subject_types:
            continue                       # not about this kind of node; costs nothing to skip
        considered += 1
        reading = measure(snapshot, node_id, metric)
        observed_at = period_start(eval_time, spec.grain)
        if not reading.known:
            # A METRIC WITH NO READING IS NOT ZERO — and in this store it is not a row either.
            # `to_row` refuses `known=False` because `value_bp` is NOT NULL, so the honest
            # representation of a gap is the ABSENCE of a row, which `read_series` materialises
            # back as `known=False`. The point is still built, so a caller (and a test) can see
            # exactly what the graph could not answer, and it never reaches `put`.
            gap_points.append(gap_point(node_id, _DEFINITION_BY_METRIC[metric], observed_at))
            continue
        ctx = SamplingContext(node=node, metric=metric, current_value_bp=reading.value_bp,
                              last_point=snapshot.last_points.get((node_id, metric.value)),
                              eval_time=eval_time)
        decision = decide(ctx)
        if not decision.sampled or decision.sample_reason is None or decision.rule is None:
            continue
        if not budget.take():
            continue                       # U3: deterministic tail, retried next sweep
        by_reason.setdefault(decision.sample_reason, []).append(
            _build_point(node_id, metric, reading, observed_at))
        by_rule[decision.rule] = by_rule.get(decision.rule, 0) + 1

    written = 0
    stored: list[MetricPoint] = []
    for reason in sorted(by_reason, key=lambda r: r.value):
        batch = by_reason[reason]
        written += history.put(org_id, batch, reason=reason, sampled_at=eval_time)
        stored.extend(batch)

    return SampleRun(org_id=org_id, eval_time=eval_time, written=written, considered=considered,
                     dropped_over_budget=budget.dropped, points=tuple(stored),
                     gap_points=tuple(gap_points), by_rule=dict(sorted(by_rule.items())))


# =================================================================================================
# U2 · THE BACKFILL SAMPLER
# =================================================================================================

class NotBackfillable(ValueError):
    """Raised for a metric whose history is not in the event ledger.

    A refusal rather than a best effort. `deal.value_minor_units`, the commitment counts and the
    support readings are computed from `graph_facts` and `open_loops`, which hold only the CURRENT
    value — replaying them would assert that today's number was also true last March, stamped
    `sample_reason='backfill'` so it looked like history. That is a fabricated observation with
    paperwork, which is worse than no history at all.
    """


def _backfill_reading(metric: TrendedMetric, timeline: Sequence[tuple[str, datetime]],
                      as_of: datetime) -> Reading:
    """The metric as it stood at `as_of`, from the message timeline alone.

    Uses the SAME window arithmetic as the live probes, against a truncated timeline, so a
    backfilled point and a live point taken in the same period are the same number. Doc 04 names
    the alternative — "backfill and live sampling disagree on period boundaries -> phantom
    changepoints" — as a failure mode of this unit specifically, and the shared
    `history.period_start` is the other half of the mitigation.
    """
    history = tuple((d, at) for d, at in timeline if at <= as_of)
    if not history:
        return Reading(None, coverage_ready=False)
    since = as_of - timedelta(days=_TOUCH_WINDOW_DAYS)
    if metric is TrendedMetric.ENGAGEMENT_TOUCH_COUNT_28D:
        return Reading(_count_in_window(history, since), coverage_ready=True)
    if metric is TrendedMetric.ENGAGEMENT_INBOUND_COUNT_28D:
        return Reading(_count_in_window(history, since, "in"), coverage_ready=True)
    if metric is TrendedMetric.ENGAGEMENT_OUTBOUND_COUNT_28D:
        return Reading(_count_in_window(history, since, "out"), coverage_ready=True)
    if metric is TrendedMetric.ENGAGEMENT_DAYS_SINCE_CONTACT:
        return Reading(_whole_days(as_of, max(at for _, at in history)), coverage_ready=True)
    if metric is TrendedMetric.RELATIONSHIP_RESPONSE_LATENCY_HOURS:
        return Reading(_lower_median(_reply_latencies_hours(history, since)), coverage_ready=True)
    raise NotBackfillable(f"{metric.value} is not reconstructible from the event ledger")


def backfill_org(store, *, org_id: str, metric: TrendedMetric, since: datetime, until: datetime,
                 history: MetricHistoryStore | None = None, budget: PointBudget | None = None,
                 snapshot: OrgSnapshot | None = None) -> SampleRun:
    """Reconstruct one metric's history from the event ledger, one point per registered period.

    Buckets come from `history.periods_between` at the metric's own grain, which is the same
    function the dense reader walks — so every backfilled point lands on a boundary a reader will
    actually visit, and none of them is invisible.

    Idempotent through the same primary key as the live path: re-running a backfill over a range
    already covered overwrites those periods rather than duplicating them, and the store's
    conditional upsert makes a re-run that agrees cost zero writes. Where a backfilled week
    collides with a live sample in the same week, the later write wins and both were computed by
    the same window arithmetic, so they agree.

    An 18-month L1 event backfill at a weekly grain is ~78 points per node per metric. At a daily
    grain it would be ~550 for no extra answer: BLG-08 needs four points and BLG-13 needs six.
    """
    if metric not in BACKFILLABLE:
        raise NotBackfillable(
            f"{metric.value} is computed from current-value state (graph_facts / open_loops), not "
            "from the event ledger — replaying it would stamp today's number on last March")
    from genios_engine.context.analytic.history import next_period, periods_between

    since, until = _as_utc(since), _as_utc(until)
    history = history or resolve_history_store(store)
    snapshot = snapshot or read_org_snapshot(store, org_id, eval_time=until)
    budget = budget or PointBudget()
    spec = TRENDED_METRICS[metric]
    buckets = periods_between(since, until, spec.grain)

    points: list[MetricPoint] = []
    considered = 0
    for node_id in sorted(snapshot.nodes):
        node = snapshot.nodes[node_id]
        if node.node_type not in spec.subject_types:
            continue
        timeline = snapshot.timeline.get(node_id, ())
        if not timeline:
            continue                    # nothing in the ledger for this node: no history to make
        for bucket in buckets:
            considered += 1
            # Measured at the END of the period, not its start. `observed_at` names the period a
            # value DESCRIBES, so a weekly point stamped Monday has to account for that week's
            # messages — measuring as of the Monday itself would make every point describe the
            # week before its own label, and the newest bucket would always read empty. Clamped
            # to `until` so the current, incomplete period is measured exactly the way a live
            # sample at that instant measures it: same window arithmetic, same answer, which is
            # doc 04's mitigation for phantom changepoints at the seam between the two paths.
            period_end = min(next_period(bucket, spec.grain) - timedelta(microseconds=1), until)
            reading = _backfill_reading(metric, timeline, period_end)
            if not reading.known:
                # A period BEFORE this node's first message is not a gap in its series — the
                # series had not started. Writing anything there would manufacture a coverage
                # hole for every week since the retention horizon on every node.
                continue
            if not budget.take():
                continue
            points.append(_build_point(node_id, metric, reading, bucket))

    written = history.put(org_id, points, reason=SampleReason.BACKFILL, sampled_at=until)
    return SampleRun(org_id=org_id, eval_time=until, written=written, considered=considered,
                     dropped_over_budget=budget.dropped, points=tuple(points))


# =================================================================================================
# THE DRAIN'S BACKFILL — L2.4.2-U2's one production caller
# =================================================================================================

#: How far back the first sweep reconstructs. L1 keeps an 18-month event ledger, so this is the
#: whole of it and not a number chosen for comfort: a shorter window would leave computable
#: history on the floor, and a longer one would walk periods the ledger cannot answer.
BACKFILL_MONTHS = 18


def backfill_history_for_drain(store, org_id: str, *, eval_time: datetime,
                               history: MetricHistoryStore | None = None,
                               snapshot: OrgSnapshot | None = None) -> int:
    """Reconstruct history from the ledger ONCE per org, on the first sweep that finds it empty.

    WHY THIS EXISTS AT ALL. Without it `backfill_org` is a function nothing calls, and the
    consequence is not abstract: BLG-08 needs four points and BLG-13 needs six, so at a weekly
    grain a fresh tenant's every trend answers `INSUFFICIENT_HISTORY` for the first four to six
    WEEKS. A seven-day pilot would therefore end before the analytic stratum said one thing, and
    it would look like a quiet product rather than an uncalled function.

    THE GUARD IS EXISTENCE, NOT A MARKER. `has_points` is one index probe; a marker column or a
    "backfilled_at" table would be a second source of truth that can disagree with the rows it
    claims to describe — erase a tenant and the marker survives, so the backfill never runs
    again for an org with no history. Existence cannot drift from the thing it measures.

    THE SNAPSHOT IS SHARED WITH THE LIVE SAMPLER, which is what makes this affordable on the
    sweep path. `read_org_snapshot` is the expensive read here, and `sample_org` on the very next
    line already needs it; passing one snapshot to both means the backfill costs point
    construction and one write, not a second traversal of the graph.

    ONLY `BACKFILLABLE`. The other seven metrics read current-value state, so replaying them
    would stamp today's deal value on last March — a fabricated observation carrying a
    `sample_reason` that says it was measured. `backfill_org` refuses them at the seam; this
    function never offers them.

    `eval_time` is a parameter. There is no clock in here, so a sweep replayed at the same
    instant reconstructs the same periods and the primary key turns the second run into an
    overwrite that the conditional upsert then costs nothing.
    """
    eval_time = _as_utc(eval_time)
    history = history or resolve_history_store(store)
    if history.has_points(org_id):
        return 0                       # this org has been backfilled, or has simply been sampled
    since = months_before(eval_time, BACKFILL_MONTHS)
    # ITS OWN SNAPSHOT, AND A WIDER ONE. The live sampler's default window is 400 days; every
    # metric it takes fits in 90. Reconstructing eighteen months through that window would read
    # an empty ledger for the oldest five and write nothing for them — periods that would then be
    # indistinguishable from a customer who was simply quiet. The extra span is read once in a
    # tenant's life, behind the `has_points` guard above, so it is not a per-drain cost.
    snapshot = snapshot or read_org_snapshot(
        store, org_id, eval_time=eval_time,
        window_days=max(_TIMELINE_WINDOW_DAYS, (eval_time - since).days + 1))
    written = 0
    for metric in sorted(BACKFILLABLE, key=lambda m: m.value):
        written += backfill_org(store, org_id=org_id, metric=metric, since=since,
                                until=eval_time, history=history, snapshot=snapshot).written
    return written
