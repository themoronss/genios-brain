"""L2.4.7 · the METRIC CORRELATOR (BLG-12) — *"does A move with B?"*, and never *"A causes B"*.

Two units live here and they are one pipeline:

* **U1 — pairwise metric association.** Pure integer rank correlation. Two readings per member (or
  two readings per PERIOD, for the single-node form), in; a typed `MetricCorrelation` or a typed
  `CorrelationRefusal`, out. No database, no clock, no model, no float — including as an
  intermediate. **BOTH FORMS HAVE A READ AND A ROUTE.** For one wave the period form did not:
  `correlate_series` and `paired_periods` were built, tested and reachable from nothing, which is
  the shape Layer 1 shipped six times. `correlate_pair_for_node` is its read and
  `GET /api/org/{org}/nodes/{node_id}/correlations` is its request path — and the form matters
  most exactly where the member form is useless, on a tenant with nineteen accounts and two years
  of weekly points on each.
* **U2 — the registered pair set and the cohort read.** The pairs that may be tested are DECLARED
  in `REGISTERED_PAIRS` and the read path refuses any other. Doc 04 names the failure this exists
  to prevent: *"scan 12 metrics, find spurious pairs by chance"*. Twelve trended metrics make 66
  unordered pairs; at a 5% false-positive rate an open-ended scan produces three confident
  findings from pure noise on every tenant, every sweep, for ever.

**WHY RANK CORRELATION AND NOT PEARSON.** Doc 04 step 2 prescribes it — *"rank both metrics
independently, average ranks on ties"* — and the reason is this data. `deal.value_minor_units` is
a long tail in paise where one enterprise contract is a thousand times the median, and Pearson's
covariance is computed on the VALUES, so that one deal decides the coefficient by itself. Spearman
sees it as "the largest one", which is all it actually is. Rank correlation is also the only form
that stays honest in integers: ranks are small, bounded by `n`, and `sum(d^2)` cannot overflow
anything, whereas an integer covariance over paise squared would.

**RANKS ARE HELD DOUBLED** (`_doubled_ranks`). Averaging ranks on ties produces halves — three
members tied at the bottom share rank 2, two tied share 1.5 — and a half is exactly the kind of
value that arrives as a float and leaves as a non-reproducible score. Every rank in this module is
therefore twice its true value, an integer always, and the `6*sum(d^2)` numerator is divided by
the extra factor of four once, at the end, in `spearman_rho_bp`.

**THE THREE REFUSALS ARE THE PRODUCT.**

* `INSUFFICIENT_PAIRS` — the contract's `MIN_CORRELATION_SAMPLES` floor of 20, restated here as a
  sentence a card can render instead of an exception a route has to catch. Six points correlate at
  0.9 by chance routinely; a correlation over six points is noise wearing a coefficient.
* `DEGENERATE_SERIES` — every member reads the same on one of the two metrics. The `d^2` formula
  returns a perfect 10000 for that case (all ranks tie, so every `d` is zero), which is the single
  most dangerous arithmetic accident in this file: a metric no tenant has ever varied would be
  reported as STRONGLY correlated with everything.
* `NOT_REGISTERED` — the pair was not declared in advance. See U2.

**A GAP IS NOT A ZERO, AND IT IS NOT A PAIR EITHER.** Both entry points intersect: a member is
used only when BOTH metrics are known for it, and a period is used only when both series carry a
`known=True` point at that instant. Zero-filling the holes is not a smaller version of the right
answer — two metrics that are each missing on the same quiet accounts will correlate at nearly
10000 on the zeros alone, and the finding is entirely an artefact of which mailbox was connected.

**`is_causal` IS FALSE AND CANNOT BE SET.** The contract enforces it (V-7); this module never
supplies the field at all. Nothing here computes, infers or exposes a direction of causation, and
the ordering of `metric_a` / `metric_b` is the declaration's, not a claim about which moves first.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from types import SimpleNamespace
from typing import Any, Iterable, Mapping, Sequence

from sqlalchemy import text

from genios_engine.context.analytic.cohort import COHORT_MEMBERSHIP_TABLE
from genios_engine.context.analytic.history import (HISTORY_TABLE, MAX_RETAINED_PERIODS,
                                                    RETENTION_MONTHS, MetricGrain)
# ONE staleness policy for the analytic stratum. `STALE_AFTER_PERIODS` and its floor are derived
# and justified in `peer_baseline`; imported rather than restated so the correlator's population
# and the ladder's population cannot come to different conclusions about which members are dark.
from genios_engine.context.analytic.peer_baseline import (metric_grain, periods_back,
                                                          staleness_floor)
from genios_engine.context.analytic.sampler import (TrendedMetric, resolve_history_store,
                                                    sampler_registry)
from genios_engine.contracts.analytic import (MIN_CORRELATION_SAMPLES, CorrelationStrength,
                                              MetricCorrelation, MetricPoint)
from genios_engine.contracts.validators import require_aware, require_identifier

# =================================================================================================
# THE CONSTANTS THE ANSWER TURNS ON. Doc 04 step 4's bands, named rather than spelled inline at the
# comparison, because every one of them is a threshold a reviewer can argue with.
# =================================================================================================

#: |rho| at or above this is a WEAK association. Below it the answer is NONE — and NONE is a real
#: answer, returned with its `n`, not an absence.
WEAK_FLOOR_BP = 3_000

#: |rho| at or above this is MODERATE.
MODERATE_FLOOR_BP = 5_000

#: |rho| STRICTLY above this is STRONG. Doc 04 writes the top band as `> 7000`, so 7000 itself is
#: MODERATE; the bands are stated with the doc's own comparators so a reader can check them
#: against it line by line.
STRONG_FLOOR_BP = 7_000

#: Every rank in this module is twice its true value so that an averaged tie stays an integer.
#: `sum(d^2)` over doubled ranks is therefore four times the true sum, and this is the factor that
#: divides it back out in `spearman_rho_bp`.
_RANK_SCALE = 2

#: Ceiling on how many cohorts one read may sweep. The per-cohort work is two indexed queries per
#: pair, and a tenant may hold up to `cohort.MAX_COHORTS_PER_ORG` definitions; an unbounded
#: correlate-everything read is the shape that turns one request into a few hundred queries.
MAX_COHORTS_PER_READ = 25


class CorrelationRefusalReason(str, Enum):
    """Why no coefficient was produced. A refusal is a RETURN VALUE, the way `CohortRefusal` is
    one for a position: *"twelve members had both readings and a correlation needs twenty"* is an
    ANSWER a card can print honestly, and an exception is not — an exception forces the caller to
    choose between showing nothing and inventing something."""

    #: Fewer than `MIN_CORRELATION_SAMPLES` members (or periods) had BOTH readings known.
    INSUFFICIENT_PAIRS = "insufficient_pairs"
    #: One of the two metrics reads identically for every pair, so its ranks all tie and the `d^2`
    #: formula would report a perfect association with anything at all.
    DEGENERATE_SERIES = "degenerate_series"
    #: The pair was not declared in `REGISTERED_PAIRS`. Doc 04: pairs are declared, not discovered.
    NOT_REGISTERED = "not_registered"
    #: A metric correlates with itself at 10000 and says nothing.
    SAME_METRIC = "same_metric"
    #: The cohort id names no active membership for this tenant at `eval_time`.
    NO_SUCH_COHORT = "no_such_cohort"
    #: The TIME-SERIES form only. The two metrics are sampled at different grains, so their
    #: periods do not line up and there is nothing to pair. See `correlate_pair_for_node`.
    MIXED_GRAIN = "mixed_grain"


@dataclass(frozen=True, slots=True)
class CorrelationRefusal:
    """No coefficient. Carries the `n` it refused on, so a reader can see how close it was — "18
    of the 20 pairs this needs" is a sentence a founder can act on by connecting one more source,
    and a bare "not enough data" is not."""

    reason: CorrelationRefusalReason
    metric_a: str
    metric_b: str
    cohort_id: str
    n: int
    computed_at: datetime
    detail: str = ""

    @property
    def is_correlation(self) -> bool:
        return False


CorrelationOutcome = MetricCorrelation | CorrelationRefusal


# =================================================================================================
# U1 · PAIRWISE METRIC ASSOCIATION. Pure integer arithmetic; no float appears below, including as
# an intermediate.
# =================================================================================================

def strength_for(rho_bp: int) -> CorrelationStrength:
    """Doc 04 step 4's bands, on the MAGNITUDE. The sign travels separately, in `rho_bp` itself:
    a strong negative association is as strong as a strong positive one, and folding the sign into
    the label would leave a renderer no way to say which way it went."""
    magnitude = abs(int(rho_bp))
    if magnitude > STRONG_FLOOR_BP:
        return CorrelationStrength.STRONG
    if magnitude >= MODERATE_FLOOR_BP:
        return CorrelationStrength.MODERATE
    if magnitude >= WEAK_FLOOR_BP:
        return CorrelationStrength.WEAK
    return CorrelationStrength.NONE


def _doubled_ranks(values: Sequence[int]) -> list[int]:
    """Ascending ranks, ties averaged, every rank held at TWICE its true value.

    A run of tied values occupying true ranks `i+1 .. j+1` averages to `(i+j+2)/2`, so the doubled
    rank is `i+j+2` — an integer for every possible run length, which is the whole reason the
    scale is carried. Ties are given one shared rank rather than an arbitrary order because the
    order would otherwise be the sort's, and two runs of the same data could then disagree.
    """
    order = sorted(range(len(values)), key=lambda i: values[i])
    ranks = [0] * len(values)
    start = 0
    while start < len(order):
        stop = start
        while stop + 1 < len(order) and values[order[stop + 1]] == values[order[start]]:
            stop += 1
        doubled = (start + 1) + (stop + 1)
        for position in range(start, stop + 1):
            ranks[order[position]] = doubled
        start = stop + 1
    return ranks


def is_degenerate(values: Sequence[int]) -> bool:
    """Every reading identical — no variation to correlate. See `DEGENERATE_SERIES`."""
    return len(values) > 0 and all(value == values[0] for value in values)


def spearman_rho_bp(xs: Sequence[int], ys: Sequence[int]) -> int:
    """Doc 04 step 3, in integers: `rho_bp = 10000 - (6 * sum(d^2) * 10000) // (n * (n^2 - 1))`.

    Held at doubled ranks, `sum(d^2)` comes out four times too large, so the denominator carries
    the matching factor of four. One floor division at the end, on a numerator that is exact — no
    intermediate is rounded, so the same two sequences produce the same basis points on every
    machine, in every process, for ever.

    **The result is CLAMPED to the signed basis-point range.** The `d^2` shortcut is exact only
    when no rank ties; with ties it can overshoot slightly past -10000, and the contract's
    `require_signed_bp` would reject the row. Clamping is the honest repair here: at that
    magnitude the label is STRONG either way, and the alternative — the tie-corrected Pearson form
    over ranks — needs a square root this module is not willing to approximate.
    """
    n = len(xs)
    if n != len(ys):
        raise ValueError("a correlation needs the same number of readings on both metrics")
    if n < 2:
        raise ValueError("a correlation needs at least two pairs to rank")
    rank_x = _doubled_ranks(xs)
    rank_y = _doubled_ranks(ys)
    sum_d2 = sum((a - b) ** 2 for a, b in zip(rank_x, rank_y))
    denominator = (_RANK_SCALE ** 2) * n * (n * n - 1)
    rho_bp = 10_000 - (6 * sum_d2 * 10_000) // denominator
    return max(-10_000, min(10_000, rho_bp))


def _refuse(reason: CorrelationRefusalReason, *, metric_a: str, metric_b: str, cohort_id: str,
            n: int, eval_time: datetime, detail: str) -> CorrelationRefusal:
    return CorrelationRefusal(reason=reason, metric_a=metric_a, metric_b=metric_b,
                              cohort_id=cohort_id, n=n, computed_at=eval_time, detail=detail)


def correlate_values(*, metric_a: str, metric_b: str, cohort_id: str,
                     values_a: Mapping[str, int], values_b: Mapping[str, int],
                     eval_time: datetime) -> CorrelationOutcome:
    """U1 · does metric A move with metric B ACROSS A POPULATION? PURE — no database.

    The two mappings are keyed by member. **Only keys present in both are used**: a member with no
    reading of B is not a member with a B of zero, and admitting it would let the members a
    connector never covered decide the coefficient.

    `cohort_id` is required and travels into the result because Law 2 applies here as much as it
    does to a percentile — two metrics that correlate across all accounts and not within a segment
    is the FINDING, and an unnamed population cannot tell those two apart.
    """
    eval_time = require_aware(eval_time, "eval_time")
    metric_a = require_identifier(metric_a, "metric_a")
    metric_b = require_identifier(metric_b, "metric_b")
    cohort_id = require_identifier(cohort_id, "cohort_id")
    if metric_a == metric_b:
        return _refuse(CorrelationRefusalReason.SAME_METRIC, metric_a=metric_a, metric_b=metric_b,
                       cohort_id=cohort_id, n=0, eval_time=eval_time,
                       detail="a metric correlates with itself at 10000 and says nothing")
    members = sorted(set(values_a) & set(values_b))
    xs = [int(values_a[member]) for member in members]
    ys = [int(values_b[member]) for member in members]
    return _coefficient(metric_a=metric_a, metric_b=metric_b, cohort_id=cohort_id, xs=xs, ys=ys,
                        eval_time=eval_time, population="members")


def _coefficient(*, metric_a: str, metric_b: str, cohort_id: str, xs: Sequence[int],
                 ys: Sequence[int], eval_time: datetime, population: str) -> CorrelationOutcome:
    """The floor, the degeneracy check and the coefficient — shared by both U1 entry points so the
    member form and the period form can never diverge on what they refuse."""
    n = len(xs)
    if n < MIN_CORRELATION_SAMPLES:
        return _refuse(
            CorrelationRefusalReason.INSUFFICIENT_PAIRS, metric_a=metric_a, metric_b=metric_b,
            cohort_id=cohort_id, n=n, eval_time=eval_time,
            detail=f"{n} {population} have both readings and a correlation needs "
                   f"{MIN_CORRELATION_SAMPLES} — below that a coefficient describes the sample, "
                   "not the business")
    for metric, values in ((metric_a, xs), (metric_b, ys)):
        if is_degenerate(values):
            return _refuse(
                CorrelationRefusalReason.DEGENERATE_SERIES, metric_a=metric_a, metric_b=metric_b,
                cohort_id=cohort_id, n=n, eval_time=eval_time,
                detail=f"{metric} reads {values[0]} for every one of the {n} pairs — a constant "
                       "has no association with anything, and the rank formula would call it "
                       "perfect")
    rho_bp = spearman_rho_bp(xs, ys)
    return MetricCorrelation(metric_a=metric_a, metric_b=metric_b, cohort_id=cohort_id,
                             rho_bp=rho_bp, strength=strength_for(rho_bp), n=n)


def paired_periods(series_a: Sequence[MetricPoint],
                   series_b: Sequence[MetricPoint]) -> tuple[list[int], list[int]]:
    """The periods where BOTH series are known, in period order. PURE.

    Two dense series from `MetricHistoryStore.read_series` carry a point for every period in the
    window, including the ones nobody measured (`known=False`, `value_bp=None`). Those are the
    holes, and the holes are exactly where the two series usually disagree — a metric sampled
    weekly and one sampled monthly share a quarter of their periods. Intersecting on
    `observed_at`, and only where both points are known, is what makes the coefficient a statement
    about the periods that were actually measured on both sides.
    """
    known_b = {point.observed_at: point.value_bp for point in series_b if point.known}
    xs: list[int] = []
    ys: list[int] = []
    for point in sorted((p for p in series_a if p.known), key=lambda p: p.observed_at):
        other = known_b.get(point.observed_at)
        if other is None or point.value_bp is None:
            continue
        xs.append(int(point.value_bp))
        ys.append(int(other))
    return xs, ys


def correlate_series(*, metric_a: str, metric_b: str, cohort_id: str,
                     series_a: Sequence[MetricPoint], series_b: Sequence[MetricPoint],
                     eval_time: datetime) -> CorrelationOutcome:
    """U1 · do two metrics move together OVER TIME for one subject? PURE — no database.

    The same coefficient and the same refusals as the member form, over periods instead of
    members. `cohort_id` still travels: a co-movement measured on one account is a statement about
    that account, and the population it is read against has to be nameable even when it is a
    single node.
    """
    eval_time = require_aware(eval_time, "eval_time")
    metric_a = require_identifier(metric_a, "metric_a")
    metric_b = require_identifier(metric_b, "metric_b")
    cohort_id = require_identifier(cohort_id, "cohort_id")
    if metric_a == metric_b:
        return _refuse(CorrelationRefusalReason.SAME_METRIC, metric_a=metric_a, metric_b=metric_b,
                       cohort_id=cohort_id, n=0, eval_time=eval_time,
                       detail="a metric correlates with itself at 10000 and says nothing")
    xs, ys = paired_periods(series_a, series_b)
    return _coefficient(metric_a=metric_a, metric_b=metric_b, cohort_id=cohort_id, xs=xs, ys=ys,
                        eval_time=eval_time, population="periods")


# =================================================================================================
# U2 · THE REGISTERED PAIRS, AND THE COHORT READ.
#
# DOC 04: *"Registered pairs are declared, not discovered — the same discipline as cohorts. An
# open-ended scan across all metric pairs will always find something, and what it finds will
# usually be noise."* The twelve trended metrics make 66 unordered pairs. Testing all of them is
# not a richer product, it is a machine for generating confident sentences about nothing, and the
# sentences are indistinguishable from the real ones by construction.
#
# Adding a row below is a DELIBERATE ACT and costs a code change, exactly as adding a
# `TrendedMetric` does. Every row must name the customer question it serves; a pair that cannot
# name one is a multiple comparison with a docstring.
# =================================================================================================

@dataclass(frozen=True, slots=True)
class RegisteredPair:
    """One declared hypothesis. `question` is what a card would say if the coefficient came back
    strong — written BEFORE the number is known, which is the only moment it can be written
    honestly."""

    metric_a: str
    metric_b: str
    question: str

    @property
    def key(self) -> tuple[str, str]:
        """Order-insensitive identity. Correlation is symmetric, so `(a, b)` and `(b, a)` are one
        registration and must not be registrable twice."""
        return (self.metric_a, self.metric_b) if self.metric_a <= self.metric_b \
            else (self.metric_b, self.metric_a)


def _pair(metric_a: TrendedMetric, metric_b: TrendedMetric, question: str) -> RegisteredPair:
    return RegisteredPair(metric_a=metric_a.value, metric_b=metric_b.value, question=question)


REGISTERED_PAIRS: tuple[RegisteredPair, ...] = (
    _pair(TrendedMetric.ENGAGEMENT_TOUCH_COUNT_28D, TrendedMetric.DEAL_STAGE_AGE_DAYS,
          "do the deals we talk to least sit longest in a stage?"),
    _pair(TrendedMetric.RELATIONSHIP_RESPONSE_LATENCY_HOURS,
          TrendedMetric.ENGAGEMENT_INBOUND_COUNT_28D,
          "when we answer slower, do they write less?"),
    _pair(TrendedMetric.ACCOUNT_CONTACT_BREADTH, TrendedMetric.ENGAGEMENT_TOUCH_COUNT_28D,
          "are the accounts where we know more people the accounts we hear from more?"),
    _pair(TrendedMetric.ACCOUNT_CONTACT_BREADTH, TrendedMetric.DEAL_VALUE_MINOR_UNITS,
          "are the bigger deals the ones with more people in the room?"),
    _pair(TrendedMetric.ACCOUNT_OVERDUE_COMMITMENT_COUNT,
          TrendedMetric.ENGAGEMENT_DAYS_SINCE_CONTACT,
          "do the accounts we owe things to go quiet on us?"),
    _pair(TrendedMetric.SUPPORT_TICKET_COUNT_28D, TrendedMetric.SUPPORT_BACKLOG_AGE_P50_DAYS,
          "does a busier support week age the backlog, or does the backlog age on its own?"),
)


def _validated_registry(pairs: Iterable[RegisteredPair]) -> dict[tuple[str, str], RegisteredPair]:
    """Refuse a bad registration at IMPORT, not at the request that first tests the pair.

    Three ways a row can be wrong and all three are caught here: a metric name the sampler does
    not write (the correlation would be an eternal `INSUFFICIENT_PAIRS` nobody could explain), a
    metric paired with itself, and the same unordered pair declared twice — which is one
    hypothesis counted as two, the multiple-comparisons problem this registry exists to bound.
    """
    registry = sampler_registry()
    seen: dict[tuple[str, str], RegisteredPair] = {}
    for pair in pairs:
        for metric in (pair.metric_a, pair.metric_b):
            if metric not in registry:
                raise ValueError(f"{metric} is not a sampled metric — a correlation over a series "
                                 "nothing writes can only ever refuse")
        if pair.metric_a == pair.metric_b:
            raise ValueError(f"{pair.metric_a} is registered against itself")
        if pair.key in seen:
            raise ValueError(f"{pair.key} is registered twice — correlation is symmetric, so that "
                             "is one hypothesis counted as two")
        if not pair.question.strip():
            raise ValueError(f"{pair.key} names no customer question")
        seen[pair.key] = pair
    return seen


_PAIR_INDEX: dict[tuple[str, str], RegisteredPair] = _validated_registry(REGISTERED_PAIRS)


def registered_pair(metric_a: str, metric_b: str) -> RegisteredPair | None:
    """The declaration for this unordered pair, or None if it was never declared."""
    key = (metric_a, metric_b) if metric_a <= metric_b else (metric_b, metric_a)
    return _PAIR_INDEX.get(key)


def is_registered(metric_a: str, metric_b: str) -> bool:
    return registered_pair(metric_a, metric_b) is not None


# -------------------------------------------------------------------------------------------------
# THE READS. Every statement carries `org_id`; a correlation is within one tenant, always.
# -------------------------------------------------------------------------------------------------

_MEMBERS_AT_SQL = text(
    f"select node_id from {COHORT_MEMBERSHIP_TABLE} where org_id = :o and cohort_id = :c "
    "and joined_at <= :at and (left_at is null or left_at > :at)")

#: The LATEST FRESH reading of one metric per member at `eval_time`. A period with no reading is
#: stored as NO ROW (migration 0094), so a member missing from this result is a member with an
#: unknown reading — never a zero, and never a pair.
#:
#: `observed_at >= :since` is the second half of that sentence and it was missing. Bounded only
#: from above, this read returns the last row a dead connector ever wrote, so a member dark for
#: ten months is paired against another member's reading from this week and the coefficient is a
#: statement about two different years. `n` then counts members nobody has measured recently,
#: which is exactly the `n` `MIN_CORRELATION_SAMPLES` is a floor on. The horizon is
#: `peer_baseline.staleness_floor` — one policy, not two.
_VALUES_SQL = text(
    f"select distinct on (subject_node_id) subject_node_id as node_id, value_bp "
    f"from {HISTORY_TABLE} "
    "where org_id = :o and metric = :m and subject_node_id = any(:ids) "
    "  and observed_at <= :at and observed_at >= :since "
    "order by subject_node_id, observed_at desc, sampled_at desc")

_COHORTS_SQL = text(
    f"select distinct cohort_id from {COHORT_MEMBERSHIP_TABLE} where org_id = :o "
    "and joined_at <= :at and (left_at is null or left_at > :at) order by cohort_id")


def _engine(store: Any):
    return getattr(store, "engine", store)


def _readings(conn, org_id: str, metric: str, members: Sequence[str],
              eval_time: datetime) -> dict[str, int]:
    """Member -> latest reading, dark members ABSENT. The horizon is measured in this metric's own
    periods, so a weekly series goes stale in three weeks and the monthly one in three months."""
    since = staleness_floor(eval_time, metric_grain(metric))
    rows = conn.execute(_VALUES_SQL, {"o": org_id, "m": metric, "ids": sorted(members),
                                      "at": eval_time, "since": since}).all()
    return {str(row.node_id): int(row.value_bp) for row in rows if row.value_bp is not None}


def correlate_pair_in_cohort(store, *, org_id: str, cohort_id: str, metric_a: str, metric_b: str,
                             eval_time: datetime) -> CorrelationOutcome:
    """U2 · one DECLARED pair, in one named cohort of one tenant, as at `eval_time`.

    POINT-IN-TIME AND REPLAYABLE. `eval_time` bounds membership (`joined_at <= at < left_at`) and
    bounds the readings (`observed_at <= at`), so re-running this call with the same instant next
    month returns the same coefficient over the same members — which is what makes a correlation
    quotable in a document that outlives the sweep that produced it.
    """
    eval_time = require_aware(eval_time, "eval_time")
    if not is_registered(metric_a, metric_b):
        return _refuse(CorrelationRefusalReason.NOT_REGISTERED, metric_a=metric_a,
                       metric_b=metric_b, cohort_id=cohort_id, n=0, eval_time=eval_time,
                       detail="this pair was not declared in REGISTERED_PAIRS — an open-ended "
                              "scan across metric pairs always finds something and what it finds "
                              "is usually noise")
    with _engine(store).connect() as conn:
        members = [str(row.node_id) for row in
                   conn.execute(_MEMBERS_AT_SQL,
                                {"o": org_id, "c": cohort_id, "at": eval_time}).all()]
        if not members:
            return _refuse(CorrelationRefusalReason.NO_SUCH_COHORT, metric_a=metric_a,
                           metric_b=metric_b, cohort_id=cohort_id, n=0, eval_time=eval_time,
                           detail="no active membership for this tenant's cohort")
        values_a = _readings(conn, org_id, metric_a, members, eval_time)
        values_b = _readings(conn, org_id, metric_b, members, eval_time)
    inside = set(members)
    return correlate_values(metric_a=metric_a, metric_b=metric_b, cohort_id=cohort_id,
                            values_a={k: v for k, v in values_a.items() if k in inside},
                            values_b={k: v for k, v in values_b.items() if k in inside},
                            eval_time=eval_time)


def correlations_in_cohort(store, *, org_id: str, cohort_id: str, eval_time: datetime,
                           pairs: Sequence[RegisteredPair] | None = None,
                           ) -> tuple[CorrelationOutcome, ...]:
    """Every declared pair in one cohort, refusals included and in declaration order.

    The refusals are RETURNED, not filtered: "eleven of the twenty pairs this needs" is the answer
    that tells a founder to connect the other mailbox, and a list that silently dropped it would
    show a shorter, more confident page every time coverage got worse.
    """
    eval_time = require_aware(eval_time, "eval_time")
    return tuple(correlate_pair_in_cohort(store, org_id=org_id, cohort_id=cohort_id,
                                          metric_a=pair.metric_a, metric_b=pair.metric_b,
                                          eval_time=eval_time)
                 for pair in (pairs if pairs is not None else REGISTERED_PAIRS))


def correlations_for_org(store, *, org_id: str, eval_time: datetime,
                         limit: int = MAX_COHORTS_PER_READ,
                         ) -> dict[str, tuple[CorrelationOutcome, ...]]:
    """Every declared pair in every cohort this tenant has active membership in, bounded.

    Deterministic tail: cohorts are read in id order, so a tenant over the ceiling truncates at
    the same place on every run rather than showing a different subset each time.
    """
    eval_time = require_aware(eval_time, "eval_time")
    with _engine(store).connect() as conn:
        cohorts = [str(row.cohort_id) for row in
                   conn.execute(_COHORTS_SQL, {"o": org_id, "at": eval_time}).all()]
    return {cohort_id: correlations_in_cohort(store, org_id=org_id, cohort_id=cohort_id,
                                              eval_time=eval_time)
            for cohort_id in cohorts[:max(0, limit)]}


def _series_periods(grain: MetricGrain) -> int:
    """How far back the TIME-SERIES form reads, in periods of the pair's own grain.

    The RETENTION horizon and not a preference: reading further back reads periods
    `history.prune` has already deleted, which `read_series` materialises as gaps — so the
    coefficient would silently depend on when the last prune happened to run. 104 weeks and 24
    months are the same two years, which is how `history` states its own bound; both numbers are
    imported from there rather than restated here, so a change to retention moves this too.
    """
    return MAX_RETAINED_PERIODS if grain is MetricGrain.WEEK else RETENTION_MONTHS


def correlate_pair_for_node(store, *, org_id: str, subject_node_id: str, metric_a: str,
                            metric_b: str, eval_time: datetime) -> CorrelationOutcome:
    """U1's TIME-SERIES form, over one subject's own history. The read behind `correlate_series`.

    *"Do these two metrics move together FOR THIS ACCOUNT?"* — the question the member form
    cannot answer, because it holds `eval_time` fixed and varies the member, and a tenant with
    nineteen accounts has no member form at all while every one of those accounts may have two
    years of weekly points. Doc 04's L2.4.7 names both forms; only the member one had a read.

    THE POPULATION IS PERIODS AND IT IS NAMED AS SUCH. `cohort_id` travels as `node:{id}` rather
    than as a peer group, because Law 2 does not stop applying when the population is one
    account: a reader has to be able to tell "these move together across our customers" from
    "these moved together on this one", and an unnamed population makes the two render alike.

    GRAINS MUST MATCH, and this is where the refusal is. `paired_periods` intersects on
    `observed_at`, and `observed_at` is a period boundary: a weekly series lands on Mondays and a
    monthly one on the 1st, so the two intersect only by calendar accident. Exactly one declared
    pair is mixed today — touch count (weekly) against deal stage age (monthly, because
    `history.CORE_METRICS` fixes that name at a month) — and without this branch it would return
    `INSUFFICIENT_PAIRS` for ever, on every tenant, with a detail blaming the tenant's coverage
    for an arithmetic fact about the registry.

    POINT-IN-TIME. `eval_time` bounds the window on both ends and nothing here reads a clock.
    """
    eval_time = require_aware(eval_time, "eval_time")
    subject_node_id = require_identifier(subject_node_id, "subject_node_id")
    cohort_id = f"node:{subject_node_id}"
    if not is_registered(metric_a, metric_b):
        return _refuse(CorrelationRefusalReason.NOT_REGISTERED, metric_a=metric_a,
                       metric_b=metric_b, cohort_id=cohort_id, n=0, eval_time=eval_time,
                       detail="this pair was not declared in REGISTERED_PAIRS — an open-ended "
                              "scan across metric pairs always finds something and what it finds "
                              "is usually noise")
    grain_a, grain_b = metric_grain(metric_a), metric_grain(metric_b)
    if grain_a is not grain_b:
        return _refuse(
            CorrelationRefusalReason.MIXED_GRAIN, metric_a=metric_a, metric_b=metric_b,
            cohort_id=cohort_id, n=0, eval_time=eval_time,
            detail=f"{metric_a} is sampled per {grain_a.value} and {metric_b} per "
                   f"{grain_b.value}, so their periods do not line up — there is nothing to pair, "
                   "and this is a fact about the registry rather than about this tenant's data")
    # `resolve_history_store` binds the sampler's registry to the store, which is what makes
    # `read_series` walk the periods the METRIC defines. It reads `.engine`; every other read in
    # this module accepts a store or a bare engine through `_engine`, so the shim keeps the two
    # entry points accepting the same thing.
    history = resolve_history_store(SimpleNamespace(engine=_engine(store)))
    since = periods_back(eval_time, grain_a, _series_periods(grain_a))
    series_a = history.read_series(org_id, subject_node_id, metric_a, since=since,
                                   until=eval_time)
    series_b = history.read_series(org_id, subject_node_id, metric_b, since=since,
                                   until=eval_time)
    return correlate_series(metric_a=metric_a, metric_b=metric_b, cohort_id=cohort_id,
                            series_a=series_a, series_b=series_b, eval_time=eval_time)


def outcome_payload(outcome: CorrelationOutcome) -> dict[str, Any]:
    """One JSON shape for both answers, so a renderer branches on `refusal is None` and never on a
    missing key. The registered QUESTION travels with the finding: a coefficient with no question
    attached is the exact object a reader supplies a cause for."""
    pair = registered_pair(outcome.metric_a, outcome.metric_b)
    question = pair.question if pair is not None else None
    if isinstance(outcome, MetricCorrelation):
        return {"correlation": outcome.model_dump(mode="json"), "refusal": None,
                "question": question}
    return {"correlation": None, "question": question,
            "refusal": {"reason": outcome.reason.value, "metric_a": outcome.metric_a,
                        "metric_b": outcome.metric_b, "cohort_id": outcome.cohort_id,
                        "n": outcome.n, "detail": outcome.detail,
                        "computed_at": outcome.computed_at.isoformat()}}


__all__ = ["MAX_COHORTS_PER_READ", "MODERATE_FLOOR_BP", "REGISTERED_PAIRS", "STRONG_FLOOR_BP",
           "WEAK_FLOOR_BP", "CorrelationOutcome", "CorrelationRefusal",
           "CorrelationRefusalReason", "RegisteredPair", "correlate_pair_for_node",
           "correlate_pair_in_cohort", "correlate_series", "correlate_values",
           "correlations_for_org", "correlations_in_cohort", "is_degenerate", "is_registered",
           "outcome_payload", "paired_periods", "registered_pair", "spearman_rho_bp",
           "strength_for"]
