"""L2.4.6 · PEER BASELINE (BLG-11) — what "normal" looks like for a named peer group.

Doc 04 gives this component two units and they pull in opposite directions:

* **U1 · the per-cohort baseline ladder.** Cached p10/p25/p50/p75/p90 per `(cohort, metric)`,
  recomputed on the drain, keyed by `computed_at` so a percentile computed in March is still
  reproducible in September against MARCH's ladder. It exists so that "high" and "low" are said
  against something real rather than against a number somebody guessed, and so that every
  comparison does not re-scan the population — L1 v2's importance formula (ALG-17) reads the org's
  p50 for a metric on a path that cannot afford a percentile sweep per signal.
* **U2 · the cross-org baseline — EXPLICITLY DEFERRED.** Doc 04 calls it "the most tempting
  feature in this document and the most dangerous". It is not built here. `cross_org_baseline`
  exists in order to REFUSE, because a deferral that is only a sentence in a document is one
  helpful pull request away from being undone, and a refusal that returns a named reason is a
  thing a caller can be tested against.

**EVERY BASELINE IN V2 IS WITHIN ONE TENANT.** No statement in this module reads two `org_id`s;
`compute_baseline` takes exactly one and stamps it on the object; `PeerBaseline` refuses a blank
one. That is the whole of what crosses the tenant boundary: nothing.

WHAT A BASELINE MAY NOT DISCLOSE — the part the tenant boundary does not cover, because it bites
INSIDE one tenant too. A five-rung nearest-rank ladder over a small population **is** the sorted
population: with six members, p10 is the minimum and p90 the maximum, and a reader who is one of
the six now holds the other five readings. "It is only an aggregate" is exactly the sentence that
makes that ship. Two mechanisms, both enforced here rather than described:

1. `MIN_BASELINE_POPULATION` — a k-anonymity floor. Under it there is no ladder, there is a
   refusal with the population it refused on. A weak answer where the contract says refuse is the
   defect this layer is built to avoid, and here it is also a disclosure.
2. `BASELINE_SMOOTHING_WINDOW` — every rung is the integer mean of at least three members'
   readings, so no rung is any one member's ORDER STATISTIC, and the extremes (the two readings a
   peer baseline most obviously leaks) are never published at all. The floor is enforced where the
   ladder is PUBLISHED (`compute_baseline`, `baseline_from_points`), not merely defaulted there: a
   default is not a control, and one keyword — `window=1` — turned five rungs back into five named
   accounts' readings. Widening is allowed; narrowing is a disclosure and is refused.

   **What this does and does not buy, stated exactly, because the weaker claim was made once and
   is not true.** The map from population to ladder is not injective — `test_peer_baseline.py`
   changes a member who sits outside every window and the ladder does not move — but it is not
   constant either: a member INSIDE a window moves that rung by their delta divided by the window,
   so a reader holding the other nineteen readings can bound the twentieth. That is a property of
   every published aggregate and the mitigations against it are the two floors, not an arithmetic
   impossibility. `MIN_BASELINE_POPULATION` is what makes "the other nineteen" an implausible
   thing to hold; the window is what stops the ladder handing over an exact reading to somebody
   holding nothing at all. Neither is described here as more than it is.

   **And the width of that channel is measured, not estimated.** H3's disclosure probe runs the
   attack in its strongest single-snapshot form — one published ladder at the k-floor of ten, an
   adversary holding the other nine readings — by brute-forcing every value the tenth member
   could hold and keeping the ones that reproduce the ladder exactly. Three survive, spanning two
   units: the remainder `sum // 3` discards, and nothing more. That is the bound. It is a
   property of publishing any aggregate over a known population rather than of this arithmetic,
   and the mitigations available to a deterministic stratum are the two floors — noise is the
   other one, and a measure that changes per machine is not a measuring instrument.

DETERMINISM. Integer basis points end to end — `sum // k`, never `sum / k` — no clock (`eval_time`
is a parameter, `computed_at` is derived from it), and no model. The same peer group at the same
`eval_time` yields a byte-identical baseline, on every machine and in every build.

GAPS ARE NOT ZEROS. `MetricPoint.known=False` carries no value by contract, and this module counts
such a member as UNKNOWN rather than as a reading of nought. A population where half the members
have no reading gets `INSUFFICIENT_COVERAGE`, not a ladder dragged toward zero by the half that
were never measured — which is the same failure `Trend.coverage_ratio_bp` exists to reveal one
component over.

WHO READS THIS TABLE — because for one wave nobody did, and that is the failure Layer 1 shipped
six times. `refresh_baselines_for_drain` wrote `peer_baselines` on every drain and the only
caller of `load_baseline` was a test. A table filled on a real path with no reader on a real path
is not a cache, it is storage cost with a docstring; and X5 was about to compose importance from
it. It now has two readers, and the honest accounting of them is this:

* **`GET /api/org/{org}/cohorts/{cohort_id}/baselines`** (`api/correlation_routes.py`) — a real
  request path, single-tenant, point-in-time via `as_of`. It is what makes a published rung
  CHECKABLE: a cached number nobody can fetch cannot be argued with, and "the ladder this
  percentile was judged against, as it stood in March" is the one question the `computed_at`
  key exists to answer.
* **ALG-17 — NOT YET.** Doc 04 L2.4.6-U1's stated WHY is that L1 v2's importance formula reads
  the org's p50 on a path that cannot afford a percentile sweep per signal. That formula has not
  landed, so `load_baseline` is not yet on that path, and this docstring says so rather than
  implying the cache is already earning its keep. What has to be true before it is: ALG-17 exists
  and calls `load_baseline(...).p50_bp` with the `as_of` of the decision it is scoring.

And the ladder is deliberately NOT wired into `comparator`'s distribution, which is the other
correction that was on the table. The two disagree ON PURPOSE: a cohort position is a nearest-rank
percentile over the raw population at a floor of 5, and a published ladder is a smoothed one at a
floor of 10 (`BASELINE_SMOOTHING_WINDOW`, `MIN_BASELINE_POPULATION`). Feeding the smoothed rungs
into the percentile would move every subject's rank by the smoothing and silently raise the
comparator's population floor from 5 to 10 — a change to what a card SAYS, made to give a cache a
customer.

GAP FLAG against doc 04. The doc's DDL carries no `unit`/`currency` and names no population floor
for the ladder — L2.4.5's `n >= 5` is a floor for a PERCENTILE, where the reader already knows
their own value and learns only their rank. A published ladder is a different disclosure and takes
a higher floor; ten is the smallest population where "p10" names a decile at all. Both additions
are recorded here rather than assumed.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Iterable, Mapping, Sequence

from sqlalchemy import text

from genios_engine.contracts.analytic import MetricPoint, MetricUnit
from genios_engine.contracts.units import ISO_4217, UNKNOWN_CURRENCY
from genios_engine.contracts.validators import require_aware, require_identifier
from genios_engine.context.analytic.cohort import (COHORT_DEFINITION_TABLE,
                                                   COHORT_MEMBERSHIP_TABLE, MAX_COHORTS_PER_ORG,
                                                   MAX_UNKNOWN_SHARE_BP)
from genios_engine.context.analytic.history import (HISTORY_TABLE, RETENTION_MONTHS, MetricGrain,
                                                    MetricRegistry,
                                                    months_before, period_start)
from genios_engine.context.analytic.sampler import sampler_registry

#: Doc 04 L2.4.6-U1's storage.
BASELINE_TABLE = "peer_baselines"

#: The rungs, in basis points of the population. Doc 04 names exactly these five.
BASELINE_RUNGS_BP: tuple[int, int, int, int, int] = (1_000, 2_500, 5_000, 7_500, 9_000)

#: THE K-ANONYMITY FLOOR. Ten, not five: `MIN_COHORT_POPULATION` bounds a PERCENTILE, where a
#: subject learns their own rank and nothing else, whereas a published ladder hands every reader
#: five order statistics of the population. Ten is also the smallest population in which "p10"
#: describes a decile rather than a person.
MIN_BASELINE_POPULATION = 10

#: Every rung is the mean of at least this many adjacent readings. Three is the smallest window
#: that (a) is never a single member's value and (b) cannot be unwound by knowing one's own
#: reading and the population count. It also stops the ladder publishing the minimum and the
#: maximum, which are the two readings a peer baseline leaks first.
BASELINE_SMOOTHING_WINDOW = 3

#: Same coverage rule as the cohort position: past this share of members with no reading, the
#: ladder describes whoever happened to be instrumented.
MAX_BASELINE_UNKNOWN_SHARE_BP = MAX_UNKNOWN_SHARE_BP

#: Per-sweep bound. Cohorts are already capped at `MAX_COHORTS_PER_ORG`; this caps the other
#: factor so one org's ladder pass cannot become a metric-by-cohort cross product.
MAX_BASELINE_METRICS = 32

#: Per-sweep write bound, for the same reason `cohort.MEMBERSHIP_WRITE_BUDGET` exists: what is
#: not written this sweep is written by the next. A baseline is state, not a queue.
MAX_BASELINE_WRITES = 2_000

#: Baselines age out with the history they were computed from — a ladder older than the points
#: behind it cannot be re-derived, so keeping it is keeping an unauditable number.
BASELINE_RETENTION_MONTHS = RETENTION_MONTHS

#: `computed_at` is the ISO WEEK START, not the sweep instant — the same boundary function the
#: rest of L2.4 uses. A week of sweeps therefore writes ONE row per (cohort, metric) instead of
#: one per drain, which is the mechanism that bounds this table.
BASELINE_GRAIN = MetricGrain.WEEK

#: THE STALENESS HORIZON, in PERIODS OF THE METRIC'S OWN GRAIN.
#:
#: THE DEFECT IT CLOSES. Every cross-member read in this stratum answers *"what does the
#: population read NOW"* with a `latest reading at or before :at` lateral. Bounded only from
#: above, that lateral has no notion of DARK: a member whose connector died ten months ago still
#: has a row, so it arrives as a reading, `unknown` stays 0, and
#: `MAX_BASELINE_UNKNOWN_SHARE_BP` — the floor that exists to refuse a ladder describing whoever
#: happened to be instrumented — is unreachable on the read path. Measured, not supposed: a
#: 10-member cohort with 5 members dark for 300 days reported `known 10, unknown 0`. The same
#: stratum then mixes an eighteen-month-old reading with this week's and publishes the result as
#: a peer group.
#:
#: WHY THREE, AND WHY IN PERIODS. The sampler writes one point per period per member, so a member
#: with a live source produces a reading EVERY period. One missing period is jitter — a drain
#: that did not run, a source that lagged past a boundary. Two consecutive misses is a pattern
#: rather than an accident. The horizon therefore admits the current period and the two before
#: it; a member that produced nothing across three consecutive periods is not late, it is dark,
#: which is precisely the state `unknown` was invented to carry. It is counted in the METRIC'S
#: grain and not in days because the two grains are a factor of four apart — 21 days for a weekly
#: metric, three months for a monthly one — and one day count would be either useless on the
#: monthly series or brutal on the weekly ones.
#:
#: This constant and `staleness_floor` are the ONE staleness policy for the analytic stratum:
#: `correlator` imports them rather than deriving a second horizon of its own. Their natural home
#: is `history.py`, which owns grain arithmetic and retention; they live here because this wave
#: does not own that file, and moving them is a follow-up, not a second policy.
STALE_AFTER_PERIODS = 3


def metric_grain(metric: str, registry: MetricRegistry | None = None) -> MetricGrain:
    """The grain the staleness horizon is measured in — WEEK when the metric is not registered.

    The fallback is the FINER grain deliberately. It makes the horizon shorter and therefore the
    refusal EASIER to reach, and the two failure directions are not symmetric: calling a live
    member dark shows up as a named refusal carrying its population, while calling a dark member
    live shows up as a confident ladder nobody can tell from a real one.

    THE REGISTRY IS `sampler_registry()`, NOT `history.default_registry()`, AND THAT IS THE WHOLE
    POINT OF THIS FUNCTION BEING SHARED. `default_registry()` holds the core metrics only; the
    twelve names the sampler actually writes are added by `sampler_definitions()`, so a resolver
    built on the core registry finds NONE of them and falls through to its default for every
    single one. `comparator` had exactly that: its own copy of this function, over
    `default_registry()`, defaulting to MONTH. Measured on the eleven weekly sampler metrics, the
    two answers in the same drain, at eval_time 2026-03-01, were:

        peer_baseline  floor = 2026-02-09   (three ISO weeks — the metric's real grain)
        comparator     floor = 2026-01-01   (three calendar months — a default for a name it
                                             could not find in the registry it happened to ask)

    So a member last read in mid-January was DARK to the ladder and KNOWN to the cohort position,
    on the same org, in the same sweep, for the same metric — one stratum, two answers about who
    is instrumented, which is the defect the horizon was added to close, four times looser.

    `registry` is an OVERRIDE for a caller that ships its own definitions (the comparator's
    on-demand read takes one); left out, the sampler's registry is the answer, because the
    sampler is what wrote the rows the horizon is judging.
    """
    definition = (registry or sampler_registry()).get(metric)
    return definition.grain if definition is not None else MetricGrain.WEEK


def periods_back(at: datetime, grain: MetricGrain, periods: int) -> datetime:
    """The START of the period `periods - 1` before the period `at` falls in.

    `periods=1` is `at`'s own period start, so the count is INCLUSIVE of the current period —
    "the last three weeks" is this week and the two before it, not this week and three more.

    Anchored on the period boundary rather than on `at` itself, so the answer does not move
    within a period: two sweeps in the same week compute the same floor and therefore classify
    the same members as dark, which is what keeps `refresh_baselines_for_drain` replayable.
    No clock — `at` is a parameter, and the boundary comes from `history.period_start`, the one
    function this layer computes period boundaries with.
    """
    at = require_aware(at, "at")
    if isinstance(periods, bool) or not isinstance(periods, int) or periods < 1:
        raise ValueError("periods must be a positive integer")
    if grain is MetricGrain.MONTH:
        return months_before(at, periods - 1)
    if grain is MetricGrain.WEEK:
        return period_start(at, MetricGrain.WEEK) - timedelta(days=7 * (periods - 1))
    raise ValueError(f"unknown metric grain {grain!r}")


def staleness_floor(at: datetime, grain: MetricGrain, *,
                    periods: int = STALE_AFTER_PERIODS) -> datetime:
    """The earliest `observed_at` a reading may carry and still count as KNOWN at `at`.

    A member whose newest reading is older than this is not read as a low number or a stale one —
    it is read as NO reading, which is what makes `unknown` count it and the coverage floor able
    to refuse. See `STALE_AFTER_PERIODS` for the derivation.
    """
    return periods_back(at, grain, periods)


class BaselineRefusalReason(str, Enum):
    """Why no ladder. A RETURN VALUE, the way `TrendDirection.INSUFFICIENT_HISTORY` is one: "we
    cannot say, and here is the population we could not say it on" is renderable and honest, and
    an exception is neither."""

    #: Under the k-anonymity floor. Both a statistical and a DISCLOSURE refusal.
    INSUFFICIENT_POPULATION = "insufficient_population"
    #: Too many members have no reading. A gap is not a zero and will not be counted as one.
    INSUFFICIENT_COVERAGE = "insufficient_coverage"
    #: The readings are not in one unit, so the ladder would be a mixture of counts and money.
    MIXED_UNITS = "mixed_units"
    #: U2. Comparing a tenant against other tenants is deferred in v2, by decision, not by
    #: omission — see the module docstring.
    CROSS_ORG_DEFERRED = "cross_org_deferred"


@dataclass(frozen=True, slots=True)
class BaselineRefusal:
    """No ladder, with the population it refused on so the reader can see how close it was."""

    reason: BaselineRefusalReason
    org_id: str
    cohort_id: str
    metric: str
    population: int
    computed_at: datetime
    detail: str = ""

    @property
    def is_baseline(self) -> bool:
        return False


@dataclass(frozen=True, slots=True)
class PeerBaseline:
    """U1 · one cohort's ladder for one metric at one instant. An AGGREGATE, and only that.

    It carries a population and no member: no node id, no name, no count of anything smaller than
    the whole cohort. `population` is present so a reader can dismiss a thin baseline — the same
    reason `CohortPosition` carries `population_size` — and the floor above guarantees the number
    is never small enough to make the rungs a roll call.
    """

    org_id: str
    cohort_id: str
    metric: str
    unit: MetricUnit
    p10_bp: int
    p25_bp: int
    p50_bp: int
    p75_bp: int
    p90_bp: int
    population: int
    computed_at: datetime
    currency: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "org_id", require_identifier(self.org_id, "org_id"))
        object.__setattr__(self, "cohort_id", require_identifier(self.cohort_id, "cohort_id"))
        object.__setattr__(self, "metric", require_identifier(self.metric, "metric"))
        object.__setattr__(self, "computed_at", require_aware(self.computed_at, "computed_at"))
        if not isinstance(self.unit, MetricUnit):
            raise TypeError("unit must be a MetricUnit — a ladder without one is five numbers")
        for name in ("p10_bp", "p25_bp", "p50_bp", "p75_bp", "p90_bp", "population"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int):
                raise TypeError(f"{name} must be an integer measurement, never a float")
        if self.population < MIN_BASELINE_POPULATION:
            raise ValueError(
                f"a peer baseline needs at least {MIN_BASELINE_POPULATION} members with a "
                f"reading (got {self.population}) — below that the ladder is the sorted "
                "population and publishing it discloses its members")
        if not (self.p10_bp <= self.p25_bp <= self.p50_bp <= self.p75_bp <= self.p90_bp):
            raise ValueError(
                f"the ladder must be ordered p10 <= p25 <= p50 <= p75 <= p90, got "
                f"{self.ladder} — an unordered ladder is not a distribution and every comparison "
                "drawn against it is meaningless in a way that typechecks")
        if self.unit is MetricUnit.MINOR_UNITS:
            if self.currency is None:
                raise ValueError(
                    "a baseline in minor units must name its currency — an amount whose currency "
                    "is unknown renders as whatever the reader's locale guesses")
            if self.currency != UNKNOWN_CURRENCY and not ISO_4217.fullmatch(self.currency):
                raise ValueError(f"currency must be ISO 4217 or {UNKNOWN_CURRENCY!r}")
        elif self.currency is not None:
            raise ValueError(
                f"currency is meaningless on a {self.unit.value} baseline — a count of tickets "
                "denominated in USD is a unit error that would survive every later check")

    @property
    def is_baseline(self) -> bool:
        return True

    @property
    def ladder(self) -> tuple[int, int, int, int, int]:
        """The five rungs in rung order, for a caller that wants to zip them with
        `BASELINE_RUNGS_BP` rather than name five fields."""
        return (self.p10_bp, self.p25_bp, self.p50_bp, self.p75_bp, self.p90_bp)

    def as_row(self) -> dict[str, Any]:
        """The `peer_baselines` row. Deterministic — this is what "byte-identical" is checked on."""
        return {"org_id": self.org_id, "cohort_id": self.cohort_id, "metric": self.metric,
                "p10_bp": self.p10_bp, "p25_bp": self.p25_bp, "p50_bp": self.p50_bp,
                "p75_bp": self.p75_bp, "p90_bp": self.p90_bp, "unit": self.unit.value,
                "currency": self.currency, "population": self.population,
                "computed_at": self.computed_at}


def smoothed_rung(sorted_values: Sequence[int], q_bp: int,
                  window: int = BASELINE_SMOOTHING_WINDOW) -> int:
    """One rung: the integer mean of the `window` readings centred on the nearest-rank index.

    The nearest-rank index is `cohort._quantile`'s, deliberately — a baseline and a percentile
    that disagreed on where p50 sits would put a card's rank and its distribution in different
    populations. What differs is what is PUBLISHED at that index: `_quantile` returns the member's
    own reading, which is the disclosure this component may not make, so the window is averaged
    instead and clamped inward at the ends (so p10 is never the minimum and p90 never the
    maximum).

    `//` and not `/`: a rung decided by a binary expansion is a boundary that reclassifies
    everyone near it depending on which machine computed it. Floor division is exact, total, and
    monotone, so a ladder built from sliding windows over a sorted series stays ordered.
    """
    n = len(sorted_values)
    if n == 0:
        raise ValueError("a baseline rung over an empty population")
    if isinstance(window, bool) or not isinstance(window, int) or window < 1:
        raise ValueError("window must be a positive integer")
    span = min(window, n)
    index = (q_bp * (n - 1)) // 10_000
    lo = index - (span - 1) // 2
    lo = min(max(lo, 0), n - span)
    return sum(sorted_values[lo:lo + span]) // span


def require_publishable_window(window: int) -> int:
    """The smoothing floor, enforced where a ladder is PUBLISHED rather than merely defaulted.

    `smoothed_rung` keeps the parameter open at 1 because it is the primitive and because
    `test_peer_baseline.py` uses `window=1` to demonstrate precisely what is being avoided: at a
    window of one, every rung is an order statistic — the exact reading of the member standing at
    that rank. The publishing path may not do that on a caller's say-so. A default is not a
    control; this is.

    WIDER is allowed and deliberately so: a noisy metric legitimately wants more smoothing, and
    more smoothing discloses strictly less. Narrower is a disclosure and has no legitimate caller.
    """
    if isinstance(window, bool) or not isinstance(window, int):
        raise ValueError("window must be a positive integer")
    if window < BASELINE_SMOOTHING_WINDOW:
        raise ValueError(
            f"a published ladder needs a smoothing window of at least "
            f"{BASELINE_SMOOTHING_WINDOW} (got {window}) — under it a rung is one member's own "
            "reading, and five rungs are five named accounts' numbers")
    return window


def _unit_of(points: Iterable[MetricPoint]) -> tuple[MetricUnit | None, str | None, bool]:
    """The one unit these readings share, or a flag saying they do not share one."""
    units = {(p.unit, p.currency) for p in points}
    if not units:
        return None, None, True
    if len(units) > 1:
        return None, None, False
    unit, currency = next(iter(units))
    return unit, currency, True


def compute_baseline(*, org_id: str, cohort_id: str, metric: str, values: Mapping[str, int],
                     unit: MetricUnit, eval_time: datetime, currency: str | None = None,
                     unknown: int = 0, window: int = BASELINE_SMOOTHING_WINDOW,
                     ) -> PeerBaseline | BaselineRefusal:
    """U1, PURE — no database, no clock, one tenant.

    `values` is member -> reading for the members that HAVE one; `unknown` counts the members that
    do not. They are separate arguments and not one dict with holes for a reason: a caller cannot
    accidentally pass a gap as a zero, and the coverage ratio the refusal is made of is computable
    at all.

    The floors are checked in this order — population, then coverage — so the more specific
    refusal wins: a cohort of four with perfect coverage is refused for being four, which is the
    thing its owner can act on.
    """
    eval_time = require_aware(eval_time, "eval_time")
    window = require_publishable_window(window)
    computed_at = period_start(eval_time, BASELINE_GRAIN)
    if isinstance(unknown, bool) or not isinstance(unknown, int) or unknown < 0:
        raise ValueError("unknown must be a non-negative integer")
    for node_id, value in values.items():
        if isinstance(value, bool) or not isinstance(value, int):
            raise TypeError(
                f"reading for {node_id!r} must be an integer measurement, never a float")
    known = sorted(values.values())
    population = len(known)
    total = population + unknown
    if population < MIN_BASELINE_POPULATION:
        return BaselineRefusal(
            BaselineRefusalReason.INSUFFICIENT_POPULATION, org_id, cohort_id, metric, population,
            computed_at,
            f"{population} members have a reading of {metric} and a baseline needs "
            f"{MIN_BASELINE_POPULATION} — below that the ladder is the sorted population and "
            "publishing it discloses its members")
    if total and unknown * 10_000 // total > MAX_BASELINE_UNKNOWN_SHARE_BP:
        return BaselineRefusal(
            BaselineRefusalReason.INSUFFICIENT_COVERAGE, org_id, cohort_id, metric, population,
            computed_at,
            f"{unknown} of {total} members have no reading of {metric} — a gap is not a zero and "
            "will not be counted as one")
    rungs = tuple(smoothed_rung(known, q, window) for q in BASELINE_RUNGS_BP)
    return PeerBaseline(
        org_id=org_id, cohort_id=cohort_id, metric=metric, unit=unit, currency=currency,
        p10_bp=rungs[0], p25_bp=rungs[1], p50_bp=rungs[2], p75_bp=rungs[3], p90_bp=rungs[4],
        population=population, computed_at=computed_at)


def baseline_from_points(*, org_id: str, cohort_id: str, metric: str,
                         points: Sequence[MetricPoint], eval_time: datetime,
                         window: int = BASELINE_SMOOTHING_WINDOW,
                         ) -> PeerBaseline | BaselineRefusal:
    """U1 over a raw series: latest KNOWN reading per subject at or before `eval_time`.

    A subject whose only points are gaps is counted as unknown, never as zero — `known=False`
    carries no value by contract, and inventing one for it would be a fabricated observation that
    also improves the coverage ratio built to reveal it.
    """
    eval_time = require_aware(eval_time, "eval_time")
    window = require_publishable_window(window)
    latest: dict[str, MetricPoint] = {}
    seen: set[str] = set()
    for point in points:
        if point.metric != metric:
            raise ValueError(
                f"a baseline of {metric!r} was given a point of {point.metric!r} — two metrics in "
                "one ladder is a distribution of nothing")
        if point.observed_at > eval_time:
            continue
        seen.add(point.subject_node_id)
        if not point.known:
            continue
        held = latest.get(point.subject_node_id)
        if held is None or point.observed_at > held.observed_at:
            latest[point.subject_node_id] = point
    unit, currency, coherent = _unit_of(latest.values())
    computed_at = period_start(eval_time, BASELINE_GRAIN)
    if not coherent:
        return BaselineRefusal(
            BaselineRefusalReason.MIXED_UNITS, org_id, cohort_id, metric, len(latest), computed_at,
            f"{metric} was read in more than one unit across this cohort — a ladder mixing counts "
            "and money is five numbers with no meaning")
    if unit is None:
        return BaselineRefusal(
            BaselineRefusalReason.INSUFFICIENT_POPULATION, org_id, cohort_id, metric, 0,
            computed_at, f"no member of this cohort has a known reading of {metric}")
    values = {node: point.value_bp for node, point in latest.items()
              if point.value_bp is not None}
    return compute_baseline(org_id=org_id, cohort_id=cohort_id, metric=metric, values=values,
                            unit=unit, currency=currency, eval_time=eval_time,
                            unknown=len(seen) - len(values), window=window)


def cross_org_baseline(*, org_ids: Sequence[str], cohort_id: str, metric: str,
                       eval_time: datetime) -> BaselineRefusal:
    """U2 · comparing a tenant against OTHER TENANTS. Deferred in v2, and this is the refusal.

    Doc 04: *"It is the most tempting feature in this document and the most dangerous. It requires
    a k-anonymity floor, an explicit opt-in, a legal review and a privacy contract... Every
    baseline in v2 is within one tenant."*

    A function that refuses is worth more than the absence of a function, on both sides. For the
    caller, "cross-org baselines are deferred" arrives as a value it can render instead of an
    ImportError somebody routes around. For this module, it is the one place the decision is
    written as CODE, with a test on it — so restoring the feature means deleting a refusal that a
    test asserts on, which is a conversation, rather than adding an `org_id in (...)` to a query,
    which is an afternoon.

    It refuses whatever it is handed, including a single org: a caller that reached for the
    cross-org door wants the cross-org answer, and quietly serving a within-tenant ladder through
    it is how the door ends up load-bearing.
    """
    return BaselineRefusal(
        BaselineRefusalReason.CROSS_ORG_DEFERRED, org_ids[0] if org_ids else "", cohort_id, metric,
        0, require_aware(eval_time, "eval_time"),
        f"a baseline across {len(org_ids)} tenants is deferred in v2 by decision (doc 04 "
        "L2.4.6-U2): it needs an explicit opt-in, a k-anonymity floor, a legal review and a "
        "privacy contract. Every baseline in v2 is within one tenant.")


# =================================================================================================
# STORAGE — one tenant per statement, and the ladder is HISTORICAL
# =================================================================================================

_UPSERT_SQL = text(
    f"insert into {BASELINE_TABLE} "
    "  (org_id, cohort_id, metric, p10_bp, p25_bp, p50_bp, p75_bp, p90_bp, unit, currency, "
    "   population, computed_at) "
    "values (:org_id, :cohort_id, :metric, :p10_bp, :p25_bp, :p50_bp, :p75_bp, :p90_bp, :unit, "
    "        :currency, :population, :computed_at) "
    "on conflict (org_id, cohort_id, metric, computed_at) do update set "
    "  p10_bp = excluded.p10_bp, p25_bp = excluded.p25_bp, p50_bp = excluded.p50_bp, "
    "  p75_bp = excluded.p75_bp, p90_bp = excluded.p90_bp, unit = excluded.unit, "
    "  currency = excluded.currency, population = excluded.population")

_READ_SQL = text(
    f"select p10_bp, p25_bp, p50_bp, p75_bp, p90_bp, unit, currency, population, computed_at "
    f"from {BASELINE_TABLE} "
    "where org_id = :o and cohort_id = :c and metric = :m and computed_at <= :at "
    "order by computed_at desc limit 1")

#: Every metric this cohort has a ladder for, at the newest `computed_at` at or before an
#: instant. One statement rather than N calls to `load_baseline`, because the caller that wants
#: "what does this peer group look like" does not know the metric list in advance — and a route
#: that had to guess it would either miss ladders or scan every registered metric per request.
_READ_ALL_SQL = text(
    f"select distinct on (metric) metric, p10_bp, p25_bp, p50_bp, p75_bp, p90_bp, unit, "
    f"       currency, population, computed_at from {BASELINE_TABLE} "
    "where org_id = :o and cohort_id = :c and computed_at <= :at "
    "order by metric, computed_at desc")

_PRUNE_SQL = text(
    f"delete from {BASELINE_TABLE} where org_id = :o and computed_at < :cutoff")

_COHORTS_SQL = text(
    f"select cohort_id from {COHORT_DEFINITION_TABLE} where org_id = :o and active "
    "order by cohort_id limit :k")

_METRICS_SQL = text(
    f"select distinct metric from {HISTORY_TABLE} where org_id = :o and observed_at <= :at "
    "order by metric limit :k")

#: Members of this org's cohorts with their latest FRESH reading of ONE metric at an instant.
#: A LEFT join, because a member with no reading must arrive as a gap to be counted as unknown —
#: an inner join would silently shrink the population and make coverage look perfect.
#:
#: TWO BOUNDS, NOT ONE. `observed_at <= :at` is what makes the ladder replayable; `>= :since` is
#: what makes it CURRENT. With only the upper bound a member whose source died ten months ago
#: still returns a row, so it is counted as known, `unknown` stays 0, and
#: `MAX_BASELINE_UNKNOWN_SHARE_BP` can never trip — see `STALE_AFTER_PERIODS`. The lower bound is
#: inside the lateral rather than outside it on purpose: outside, a stale row would still win the
#: `limit 1` and then be filtered, which is the same as dropping the member; inside, the lateral
#: returns NO row and the left join delivers the member as the gap it is.
_MEMBER_VALUES_SQL = text(
    "select m.cohort_id as cohort_id, m.node_id as node_id, h.value_bp as value_bp, "
    "       h.unit as unit, h.currency as currency, h.observed_at as observed_at "
    f"from {COHORT_MEMBERSHIP_TABLE} m "
    "left join lateral ("
    f"  select value_bp, unit, currency, observed_at from {HISTORY_TABLE} h "
    "   where h.org_id = m.org_id and h.subject_node_id = m.node_id and h.metric = :m "
    "     and h.observed_at <= :at and h.observed_at >= :since "
    "   order by h.observed_at desc, h.sampled_at desc limit 1) h on true "
    "where m.org_id = :o and m.cohort_id = any(:cids) and m.joined_at <= :at "
    "  and (m.left_at is null or m.left_at > :at)")


def save_baselines(engine, baselines: Sequence[PeerBaseline]) -> int:
    """Append this run's ladders. Idempotent within a period: `computed_at` is the week start, so
    a sweep replayed in the same week rewrites one row per (cohort, metric) rather than appending
    one per drain."""
    if not baselines:
        return 0
    with engine.begin() as conn:
        for baseline in baselines:
            conn.execute(_UPSERT_SQL, baseline.as_row())
    return len(baselines)


def load_baseline(engine, org_id: str, cohort_id: str, metric: str, *,
                  as_of: datetime) -> PeerBaseline | None:
    """The ladder that was in force at `as_of` — the newest row at or before it, never the newest
    row full stop. This is what makes a March percentile reproducible in September: the reader
    names the moment and gets the distribution that moment was judged against.

    `ALG-17`'s entry point: L1 v2's importance formula reads `load_baseline(...).p50_bp` rather
    than re-scanning a population per signal.
    """
    as_of = require_aware(as_of, "as_of")
    with engine.connect() as conn:
        row = conn.execute(_READ_SQL,
                           {"o": org_id, "c": cohort_id, "m": metric, "at": as_of}).first()
    if row is None:
        return None
    return PeerBaseline(
        org_id=org_id, cohort_id=cohort_id, metric=metric, unit=MetricUnit(row.unit),
        currency=row.currency, p10_bp=int(row.p10_bp), p25_bp=int(row.p25_bp),
        p50_bp=int(row.p50_bp), p75_bp=int(row.p75_bp), p90_bp=int(row.p90_bp),
        population=int(row.population), computed_at=row.computed_at)


def load_baselines(engine, org_id: str, cohort_id: str, *,
                   as_of: datetime) -> tuple[PeerBaseline, ...]:
    """Every metric this cohort has a ladder for, as the ladders stood at `as_of`, in metric order.

    The plural of `load_baseline` and the same point-in-time rule: one row per metric, the newest
    at or before the instant, never the newest full stop. A metric with no ladder at that instant
    is ABSENT rather than present-and-empty — the refusals are not stored, so this reader cannot
    tell "under the k-anonymity floor" from "never swept", and inventing a row that said either
    would be a claim the table does not hold.
    """
    as_of = require_aware(as_of, "as_of")
    with engine.connect() as conn:
        rows = conn.execute(_READ_ALL_SQL, {"o": org_id, "c": cohort_id, "at": as_of}).all()
    return tuple(
        PeerBaseline(
            org_id=org_id, cohort_id=cohort_id, metric=str(row.metric), unit=MetricUnit(row.unit),
            currency=row.currency, p10_bp=int(row.p10_bp), p25_bp=int(row.p25_bp),
            p50_bp=int(row.p50_bp), p75_bp=int(row.p75_bp), p90_bp=int(row.p90_bp),
            population=int(row.population), computed_at=row.computed_at)
        for row in rows)


def prune_baselines(engine, org_id: str, *, eval_time: datetime) -> int:
    """Retention, on the drain path. A ladder older than the points behind it cannot be
    re-derived, so keeping it is keeping a number nobody can audit."""
    cutoff = months_before(require_aware(eval_time, "eval_time"), BASELINE_RETENTION_MONTHS)
    with engine.begin() as conn:
        return conn.execute(_PRUNE_SQL, {"o": org_id, "cutoff": cutoff}).rowcount or 0


@dataclass(frozen=True, slots=True)
class BaselineSweep:
    """What one drain's baseline pass did. Refusals are COUNTED, not discarded: a tenant whose
    every cohort is under the floor should be visible as that, not as a pass that did nothing."""

    written: int
    refused: int
    pruned: int
    refusals: tuple[BaselineRefusal, ...] = ()


def refresh_baselines_for_drain(store: Any, org_id: str, *, eval_time: datetime,
                                metrics: Sequence[str] | None = None) -> BaselineSweep:
    """ONE tenant's ladders, on the sweep that already happens.

    Here and not on a schedule, for the reasons the neighbouring passes give: the Celery broker is
    a quota-limited Upstash instance, and the drain is the only thing that knows an org is active.
    Every statement below carries `org_id`; the cross product is bounded by `MAX_COHORTS_PER_ORG`
    on one side and `MAX_BASELINE_METRICS` on the other, and the write budget caps what one org
    may write in a pass — what is not written this sweep is written by the next.

    THE POPULATION IS THE MEMBERS WHO HAVE BEEN MEASURED RECENTLY, not the members who were ever
    measured. Each metric's read is bounded below by `staleness_floor` in that metric's own
    periods, so a member behind a dead connector arrives as a gap and is counted by `unknown` —
    which is what lets `MAX_BASELINE_UNKNOWN_SHARE_BP` refuse a ladder over a population half of
    which nobody has looked at since last winter. See `STALE_AFTER_PERIODS`.
    """
    eval_time = require_aware(eval_time, "eval_time")
    engine = getattr(store, "engine", store)
    with engine.connect() as conn:
        cohort_ids = [str(r.cohort_id) for r in
                      conn.execute(_COHORTS_SQL, {"o": org_id, "k": MAX_COHORTS_PER_ORG}).all()]
        names = list(metrics) if metrics is not None else [
            str(r.metric) for r in
            conn.execute(_METRICS_SQL,
                         {"o": org_id, "at": eval_time, "k": MAX_BASELINE_METRICS}).all()]
        rows_by_metric: dict[str, list[Any]] = {}
        if cohort_ids:
            for metric in names[:MAX_BASELINE_METRICS]:
                # The staleness horizon is per METRIC because it is measured in that metric's own
                # periods: three weeks for a weekly series, three months for the monthly one.
                since = staleness_floor(eval_time, metric_grain(metric))
                rows_by_metric[metric] = conn.execute(
                    _MEMBER_VALUES_SQL,
                    {"o": org_id, "m": metric, "at": eval_time, "since": since,
                     "cids": sorted(cohort_ids)}).all()

    ready: list[PeerBaseline] = []
    refusals: list[BaselineRefusal] = []
    for metric in sorted(rows_by_metric):
        # ROWS BECOME TYPED POINTS AND THE LADDER COMES OUT OF ONE FUNCTION. This loop used to
        # re-implement `baseline_from_points`: its own mixed-unit check, its own gap counter, its
        # own "no member has a reading" refusal. Two copies of the coverage rule is two places
        # for it to be relaxed, and the copy on the SWEEP — the one that actually writes rows —
        # was the copy no pure test could reach. `baseline_from_points` is now the single
        # points-to-ladder path, used by the drain, and its refusals are the sweep's refusals.
        gap_at = period_start(eval_time, metric_grain(metric))
        by_cohort: dict[str, list[MetricPoint]] = {}
        for row in rows_by_metric[metric]:
            bucket = by_cohort.setdefault(str(row.cohort_id), [])
            if row.value_bp is None:
                # A member with no reading INSIDE the horizon — no source, or a dead one. It is
                # carried as an EXPLICIT gap rather than dropped: `unknown` is what the coverage
                # floor counts, and a dropped member would improve the very ratio built to reveal
                # it. `unit` is required by the contract and is inert on a gap: `known=False`
                # carries no value (V-3), and `baseline_from_points` reads the ladder's unit off
                # KNOWN points only, so nothing downstream can see this placeholder.
                bucket.append(MetricPoint(subject_node_id=str(row.node_id), metric=metric,
                                          value_bp=None, unit=MetricUnit.COUNT,
                                          observed_at=gap_at, known=False))
                continue
            bucket.append(MetricPoint(
                subject_node_id=str(row.node_id), metric=metric, value_bp=int(row.value_bp),
                unit=MetricUnit(str(row.unit)), currency=row.currency,
                observed_at=row.observed_at, known=True))
        for cohort_id in sorted(by_cohort):
            if len(ready) >= MAX_BASELINE_WRITES:
                break
            outcome = baseline_from_points(org_id=org_id, cohort_id=cohort_id, metric=metric,
                                           points=by_cohort[cohort_id], eval_time=eval_time)
            (ready if outcome.is_baseline else refusals).append(outcome)  # type: ignore[arg-type]

    written = save_baselines(engine, ready)
    pruned = prune_baselines(engine, org_id, eval_time=eval_time)
    return BaselineSweep(written=written, refused=len(refusals), pruned=pruned,
                         refusals=tuple(refusals))


__all__ = ["BASELINE_GRAIN", "BASELINE_RETENTION_MONTHS", "BASELINE_RUNGS_BP",
           "BASELINE_SMOOTHING_WINDOW", "BASELINE_TABLE", "BaselineRefusal",
           "BaselineRefusalReason", "BaselineSweep", "MAX_BASELINE_METRICS",
           "MAX_BASELINE_UNKNOWN_SHARE_BP", "MAX_BASELINE_WRITES", "MIN_BASELINE_POPULATION",
           "PeerBaseline", "STALE_AFTER_PERIODS", "baseline_from_points", "compute_baseline",
           "cross_org_baseline", "load_baseline", "load_baselines", "metric_grain",
           "periods_back", "prune_baselines", "refresh_baselines_for_drain",
           "require_publishable_window", "save_baselines", "smoothed_rung", "staleness_floor"]
