"""D-02..D-06 · the analytic stratum's types — what is true ACROSS entities and ACROSS time.

Layer 1 answers *what happened in this message*. Nothing in `contracts/` could answer *how does
this compare* until this module: a percentile, a trend, a peer baseline and a correlation are all
statements about a POPULATION or a SERIES, and neither has a home on a per-event contract. Doc 04
puts it plainly — six of the six customer expectations the product is sold on ("this cohort shows
early churn signals", "engagement is declining", "at-risk flagged 30+ days early") need this group
and none of them needs a language model. Until these types exist those claims are not merely hard,
they are *unrepresentable*: there is no field on any boundary object that could carry them.

**The group law, and why it is a type and not a code review.** *Every comparison names its
population.* A percentile without a stated cohort is a number nobody can check — the reader cannot
ask "bottom decile of what?", so they cannot disagree, so the number is unfalsifiable on a card.
`CohortPosition` therefore makes `cohort_id` and `population_size` REQUIRED fields with no
defaults (V-1) and refuses a population under five (V-2). Neither is defensive coding: the failure
they prevent is a founder being told they are in the bottom decile of a cohort of three.

**Why the measurement is 100% deterministic and integer-only.** A comparison needs a stable
measuring instrument. If a trend were judged by a model in March and again in September, a
disagreement between the two readings could not be attributed to the business or to the model —
which makes the whole reading worthless in the only situation where it matters. Every number here
is therefore an integer, and the `*_bp` suffix means basis points in the field's own scale (see
the three helpers below for the three scales, which are NOT interchangeable).

**Three different integer scales live in this module, deliberately not unified.**

* `require_bp` (0..10000, imported from `validators.py`, never re-implemented) — a PROPORTION:
  `percentile_bp`, `coverage_ratio_bp`, `trend_confidence_bp`.
* `require_signed_bp` (-10000..10000) — a signed proportion: `rho_bp`. A correlation of -0.8 is a
  real, useful answer, and clamping it at zero would turn "these move in opposite directions" into
  "these are unrelated".
* `require_ratio_bp` (>= 0, NO upper bound) — a RATIO that may legitimately exceed 1: `z_like_bp`
  is `|current - baseline| * 10000 // max(mad, 1)` and doc 04 flags an anomaly above 30000, three
  times the top of the 0..10000 range. Range-checking it as a proportion would reject every
  anomaly the detector exists to find.

A fourth scale is `MetricPoint.value_bp`, which is the metric's OWN unit (see `MetricUnit`) and is
therefore an unbounded signed integer: a count of 40,000 tickets, an ARR of 8,400,000 minor units
and a 15000 bp growth rate are all legal values of the same field, and only `unit` says which.

**What this module does NOT own.** The same boundary `signal.py` draws. The thresholds are the
algorithms': BLG-08's `min_points = 4` and its 0.6 coverage floor, BLG-12's rho -> strength label
cutoffs, BLG-13's `z_like > 30000` flag test, BLG-09's quartile predicates. Only the ones doc 08
states as CONTRACT rules are here (V-4, V-5, V-6, plus D-06's `periods_used >= 6`), because a
second copy of a tunable table in a contract forks from the first the day either is edited and
both sides still typecheck. The one apparent exception is `CohortBand`, and it is not a threshold
at all: a decile IS the tenth of a distribution, by definition, and that definition cannot be
retuned without the word changing meaning.

GAP FLAG — doc 08 declares `Trend.direction`, `CohortPosition.band`, `MetricCorrelation.strength`
and `Anomaly.direction` as `str` with the closed set written in a comment. They are `str` Enums
here (house style, and the wire form is byte-identical), because a comment is not enforcement and
every one of the four is read by a renderer that branches on the exact word. `signal.py` made the
opposite call for `state` and said why: there, a DDL column pinned the wire form. No DDL exists
for these four yet, so the enum is free.

GAP FLAG — doc 08 gives `MetricPoint` no `evidence` and no id, so a point cannot cite the row it
was sampled from. X1 CLOSED HALF OF THIS by adding the field the doc omitted: with
`subject_node_id`, a point carries `(subject_node_id, metric, observed_at)`, which is
`metric_history`'s primary key minus the ambient `org_id` — so the row IS re-queryable and the
join back exists (`context/analytic/history.py::MetricHistoryStore.get`). What is still absent is
the receipt UNDER the row: the store records what was sampled, not which observations were counted
to produce it, so "where did this 42 come from" bottoms out at the sampler. That is L2.4.2's to
answer, and it is a real gap, not a resolved one.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Mapping

from pydantic import BaseModel, ConfigDict, ValidationInfo, field_validator, model_validator

from genios_engine.contracts.units import ISO_4217, UNKNOWN_CURRENCY
from genios_engine.contracts.validators import (require_aware, require_bool, require_bp,
                                                require_enum, require_identifier,
                                                require_non_negative, require_text)

#: BLG-08's floor, and the one number from that algorithm doc 08 promotes to a CONTRACT rule
#: (V-5): under four points there is no trend, only two readings and a line drawn between them.
MIN_TREND_POINTS = 4

#: V-4's ceiling. A trend is never certain: four points and a slope is an extrapolation, and the
#: cap is what stops it being rendered beside a fact that was actually read from a document.
MAX_TREND_CONFIDENCE_BP = 8_000

#: V-2's floor — Law 2. Five is the smallest population where a quartile means anything at all;
#: below it "bottom decile" is a ranking of individuals wearing the clothes of a distribution.
#: Five is also exactly the smallest population that can EXPRESS a quartile — see
#: `expressible_divisions`, where the same `n > divisions` arithmetic produces both numbers.
MIN_COHORT_POPULATION = 5

#: The band schemes, ordered FINEST FIRST. `expressible_divisions` walks this, so adding a scheme
#: (say twentiles) is one entry here rather than a new branch in three places.
BAND_SCHEMES: tuple[int, ...] = (10, 4)


def expressible_divisions(population_size: int, *, requested: int) -> int:
    """The finest band scheme this population can actually PRODUCE. V-8's arithmetic, once.

    **The defect this exists to close.** `percentile_bp` is nearest rank —
    `rank = |{v <= subject}|`, `percentile_bp = rank * 10000 // n` — and the subject counts
    itself, so `rank` runs 1..n and the reachable set is

        P(n) = { r * 10000 // n : r = 1..n },   min P(n) = 10000 // n,   NEVER 0.

    A band `k` of a `d`-scheme covers `[(k-1)*w, k*w)` with `w = 10000 // d` (exact for 4 and
    10). So

        band 1 is reachable  <=>  10000 // n < w  <=>  10000/n < 10000/d  <=>  n > d.

    And `n > d` makes every OTHER band reachable too: consecutive members of P(n) differ by at
    most `ceil(10000/n) <= w`, and a step of at most `w` cannot jump a half-open interval of
    width `w` (skipping band k would need `p[r+1] - p[r] >= w + 1`), while `r = n` lands exactly
    on 10000, the top band. Therefore **every band of a d-scheme is reachable iff
    `population_size > d`**, and band 1 is the binding case.

    Measured, deciles, which is the table `test_l2_contracts` pins from `position_from_values`::

        n=5  -> {D3,D5,D7,D9,D10}          n=9  -> D1 absent
        n=6  -> {D2,D4,D6,D7,D9,D10}       n=10 -> D1 absent
        n=7  -> {D2,D3,D5,D6,D8,D9,D10}    n=11 -> all ten, first n that can say "bottom decile"
        n=8  -> {D2,D3,D4,D6,D7,D8,D9,D10}

    So at the cohort floor of five the WORST member of the population published as `D3`, which a
    card renders as "below average, not alarming", and the phrase the product promises — "bottom
    decile" — was unsayable for every cohort with ten or fewer members. `most_specific` publishes
    the SMALLEST population on purpose, so the sweep selects precisely the cohorts where this is
    worst.

    NOTE the off-by-one against the obvious rule: `population_size >= divisions` is NOT the
    condition. At n=10 the smallest reachable percentile is exactly 1000 — the first basis point
    of D2 — so D1 is still empty. The floor is strict: `population_size > divisions`.

    Refusing outright was the alternative and it is worse: a five-member cohort has a real,
    checkable quartile position, `MIN_COHORT_POPULATION` exists to license exactly that, and
    turning it into an exception would delete the position rather than the overclaim. So the
    scheme DEGRADES to the finest one the population supports, and the label the card prints is
    one the arithmetic can actually produce.
    """
    if isinstance(population_size, bool) or not isinstance(population_size, int):
        raise TypeError("population_size must be an integer")
    if requested not in BAND_SCHEMES:
        raise ValueError(f"a cohort band scheme is one of {BAND_SCHEMES}, got {requested!r}")
    for scheme in BAND_SCHEMES:
        if scheme <= requested and population_size > scheme:
            return scheme
    raise ValueError(
        f"a population of {population_size} can express no band scheme — the coarsest is "
        f"{BAND_SCHEMES[-1]} and every band of it needs at least {BAND_SCHEMES[-1] + 1} members; "
        "a position over a population this small is refused by V-2, not relabelled")

#: V-6's floor. Twenty pairs is the smallest sample where a rank correlation is not mostly an
#: artefact of the ordering. Five points can be made to correlate at 0.9 by chance and routinely
#: are, which is how a spurious "these two always move together" reaches a card.
MIN_CORRELATION_SAMPLES = 20

#: D-06's floor. Six known periods is the minimum baseline a median absolute deviation can be
#: computed from; below it the "normal band" is whatever the last two months happened to be.
MIN_ANOMALY_PERIODS = 6


def require_signed_bp(value: Any, label: str) -> int:
    """A SIGNED proportion, -10000..10000. `rho_bp` only.

    Separate from `require_bp` rather than a widening of it: every other basis-point field in the
    codebase is a magnitude where a negative value is meaningless, and relaxing the shared helper
    to admit one would silently legalise a negative confidence everywhere it is used.
    """
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{label} must be integer basis points")
    if not -10_000 <= value <= 10_000:
        raise ValueError(f"{label} must be between -10000 and 10000")
    return value


def require_ratio_bp(value: Any, label: str) -> int:
    """A non-negative RATIO in basis points, with NO upper bound.

    `z_like_bp` and `deviation_bp` are ratios against a baseline, not proportions of a whole:
    doc 04 flags an anomaly at `z_like > 30000`, so a 0..10000 check here would reject precisely
    the objects the anomaly detector exists to produce. Negative is still refused — both are
    magnitudes, and `direction` carries the sign as a word a card can print.
    """
    return require_non_negative(value, label)


def require_measure(value: Any, label: str) -> int:
    """A metric's own value: an unbounded SIGNED integer that is not a float and not a bool.

    A metric value has no natural range — 40,000 tickets, 8,400,000 minor units and a 15000 bp
    growth rate are all legal readings of `MetricPoint.value_bp`, and only `unit` says which one
    is meant. The whole job here is refusing the float: pydantic's lax mode turns `0.87` into `0`
    and stores it as a measurement, and a metric history built on rounded ratios cannot be
    compared to itself across a version.
    """
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{label} must be an integer measurement, never a float")
    return value


class Measurement(BaseModel):
    """The base every analytic measure is built on: frozen, closed, and REVALIDATED ON COPY.

    Frozen is not enough on its own, and the gap is narrow enough to be missed by exactly the
    review that would have caught an assignment. `model_copy(update=...)` is pydantic's ordinary
    way to derive one frozen model from another and it runs NO validator — so on a plain frozen
    model the one line

        correlation.model_copy(update={"is_causal": True})

    produces a well-typed `MetricCorrelation` carrying the causal claim V-7 exists to make
    unconstructible, and `situation.py`'s V-7 catch only fires if that object is later attached to
    a BSO and put through `validate_situation`. One published straight out of a route would not
    be. The same hole widens every other law in this module: an `n` under the sample floor, a
    `population_size` under the cohort floor, a `known=False` point that acquires a value.

    So `model_copy` re-enters the constructor here whenever it is given an update. A copy with no
    update is the same object's fields and skips the work. `model_construct` remains a bypass and
    is deliberately left alone — it is pydantic's documented "I know what I am doing" door, and the
    thing that exists for objects that came through it is `validate_situation`, which runs the same
    eight laws over an assembled situation. This closes the door somebody would walk through by
    accident; that one catches what came through the door marked as such.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    def model_copy(self, *, update: Mapping[str, Any] | None = None, deep: bool = False):
        copied = super().model_copy(update=dict(update) if update else None, deep=deep)
        if not update:
            return copied
        return type(self).model_validate(dict(copied.__dict__))


class MetricUnit(str, Enum):
    """What `MetricPoint.value_bp` is actually counting. Four units, closed.

    The field name says `_bp` and the value is frequently not a proportion at all, which is why
    this enum is required rather than defaulted: a stored `5000` is either fifty percent, fifty
    dollars, five thousand days or five thousand tickets, and a consumer that guesses is the
    `$84K` / `$8.4K` fault in a new coat.
    """

    #: A cardinal count — tickets, meetings, replies. Never negative in practice; not enforced,
    #: because a differenced series legitimately carries negatives.
    COUNT = "count"
    #: Whole days. Cycle time, days-since-last-touch, days-to-renewal.
    DAYS = "days"
    #: A proportion in basis points, which MAY exceed 10000 (a metric that doubled is 20000).
    BP = "bp"
    #: Money in the currency's smallest unit, exactly as `contracts/units.Money` stores it.
    #: `currency` is REQUIRED alongside it — see `MetricPoint`.
    MINOR_UNITS = "minor_units"


class TrendDirection(str, Enum):
    """Five answers, and two of them are refusals.

    `INSUFFICIENT_HISTORY` and `INSUFFICIENT_COVERAGE` are first-class RETURN VALUES, not error
    states: doc 04 is explicit that step 1 refuses rather than guesses. The distinction they draw
    is the one that decides whether a negative inference is licensed at all — "engagement is flat"
    and "we cannot see enough of this to say" are opposite claims that a single `FLAT` would make
    indistinguishable, and the second one silently becomes the first the moment a tenant has a
    channel we are not connected to.
    """

    RISING = "rising"
    DECLINING = "declining"
    FLAT = "flat"
    #: Fewer than `MIN_TREND_POINTS` known points. There is no series to fit.
    INSUFFICIENT_HISTORY = "insufficient_history"
    #: Enough points, too many gaps. The known fraction is below BLG-08's coverage floor, and an
    #: interpolated value is a fabricated observation the coverage ratio exists to refuse.
    INSUFFICIENT_COVERAGE = "insufficient_coverage"


#: The two directions V-5 governs. A trend that names a direction is making a claim about where
#: the number is going; `FLAT` is a claim that it is going nowhere and needs the same points, but
#: doc 08's V-5 names only these two and the set is kept as data so the rule reads off it.
DIRECTIONAL: frozenset[TrendDirection] = frozenset({TrendDirection.RISING,
                                                    TrendDirection.DECLINING})

#: The two refusals. A refusal carries no strength — see `Trend`'s whole-object rule.
NON_ANSWERS: frozenset[TrendDirection] = frozenset({TrendDirection.INSUFFICIENT_HISTORY,
                                                    TrendDirection.INSUFFICIENT_COVERAGE})


class CohortBand(str, Enum):
    """The quartile and decile labels, and the ONE lookup table this module does encode.

    Every other threshold in L2.4 is a tunable weight that belongs to its algorithm and is
    deliberately absent here (see the module docstring). This one is not tunable: the fourth
    decile IS the band from the 30th to the 40th percentile, by definition, and a `CohortPosition`
    whose `band` and `percentile_bp` disagree is a card that prints "bottom decile" next to a
    median. `bounds_bp` is what makes that disagreement unconstructible rather than merely
    discouraged.
    """

    Q1 = "Q1"
    Q2 = "Q2"
    Q3 = "Q3"
    Q4 = "Q4"
    D1 = "D1"
    D2 = "D2"
    D3 = "D3"
    D4 = "D4"
    D5 = "D5"
    D6 = "D6"
    D7 = "D7"
    D8 = "D8"
    D9 = "D9"
    D10 = "D10"

    @property
    def divisions(self) -> int:
        """4 for a quartile label, 10 for a decile label."""
        return 4 if self.value.startswith("Q") else 10

    @property
    def index(self) -> int:
        """1-based position of this band within its scheme."""
        return int(self.value[1:])

    @property
    def bounds_bp(self) -> tuple[int, int]:
        """`[low, high)` in basis points — the top band's high bound is inclusive at 10000.

        Integer arithmetic only: `10000 // divisions` divides exactly for both 4 and 10, so no
        rounding rule is needed and no float ever appears.
        """
        width = 10_000 // self.divisions
        return (width * (self.index - 1), width * self.index)

    def contains(self, percentile_bp: int) -> bool:
        low, high = self.bounds_bp
        return low <= percentile_bp < high or (self.index == self.divisions
                                               and percentile_bp == 10_000)

    @classmethod
    def for_percentile(cls, percentile_bp: int, *, divisions: int,
                       population_size: int | None = None) -> CohortBand:
        """The band a percentile falls in. Deterministic, integer, no clock, no float.

        `population_size` is optional and is the ONLY way to get a label the population can
        actually produce: given it, the scheme is first narrowed by `expressible_divisions`, so a
        caller asking for deciles over a cohort of five is answered in quartiles rather than in a
        decile that its own arithmetic can never reach. Left out, this is the pure lookup it
        always was — which is right for a caller that already knows its scheme is expressible, and
        wrong for one that does not, so the population form is the one a writer should reach for.
        """
        if divisions not in BAND_SCHEMES:
            raise ValueError("a cohort band scheme is quartiles (4) or deciles (10)")
        if population_size is not None:
            divisions = expressible_divisions(population_size, requested=divisions)
        width = 10_000 // divisions
        index = min(require_bp(percentile_bp, "percentile_bp") // width, divisions - 1) + 1
        return cls(f"{'Q' if divisions == 4 else 'D'}{index}")


class CorrelationStrength(str, Enum):
    """The label BLG-12 puts on `rho_bp`.

    The cutoffs that MAP a rho to one of these are the algorithm's and are deliberately not
    duplicated here — they are tunable, and a second copy in a contract forks from the first the
    day either moves. What the contract owns is that the vocabulary is closed, so a renderer
    branching on the word cannot meet a fifth one.
    """

    NONE = "none"
    WEAK = "weak"
    MODERATE = "moderate"
    STRONG = "strong"


class AnomalyDirection(str, Enum):
    """Which side of its own baseline the metric fell on. The sign, as a word a card can print."""

    ABOVE = "above"
    BELOW = "below"


class MetricPoint(Measurement):
    """D-02 · one sampled reading of one metric at one PERIOD.

    **`observed_at` is the period, not the compute time.** A sampler that stamped its own run
    time would make every backfilled month look like this morning, and a trend over those stamps
    would be a trend over when we happened to look.

    **`known=False` is the honest gap, and V-3 is what keeps it honest.** A point with no reading
    is carried in the series — it is what makes `coverage_ratio_bp` computable at all — and it
    must carry no value. Interpolating one is not a smaller error than a missing point: it is a
    FABRICATED OBSERVATION that is indistinguishable in the column from a measured one, it
    improves the coverage ratio that exists to reveal it, and it makes a trend line look better
    supported the more data is missing.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    #: WHOSE reading this is — the graph node the metric was measured on. REQUIRED, with no
    #: default, and the field this type was missing when X0 shipped it.
    #:
    #: `metric_history`'s primary key is `(org_id, subject_node_id, metric, observed_at)`, so a
    #: point that does not name its subject cannot be written, cannot be read back, and cannot be
    #: re-queried to answer "where did this percentile come from" (the GAP FLAG in the module
    #: docstring). Optional-with-a-default was the alternative and it is worse than absent: a
    #: series silently defaulting to one subject is two accounts' readings in one column, and
    #: every trend, baseline and anomaly computed over it typechecks.
    #:
    #: `org_id` is deliberately NOT here — no type in D-02..D-06 carries it, the tenant is
    #: ambient at every call site that constructs one, and a second copy of it on the point is a
    #: second place for a tenant boundary to be got wrong.
    subject_node_id: str
    #: The metric's stable name — an identifier, because it reaches SQL, cache keys and a
    #: renderer's lookup table.
    metric: str
    #: The reading, in `unit`. `None` iff `known` is False (V-3, both directions).
    value_bp: int | None
    #: What the reading counts. Required — see `MetricUnit`.
    unit: MetricUnit
    #: ISO 4217, or `UNKNOWN_CURRENCY`. REQUIRED when `unit` is `MINOR_UNITS`, refused otherwise.
    currency: str | None = None
    #: The PERIOD this reading belongs to, tz-aware UTC.
    observed_at: datetime
    #: Did we actually read a value for this period? Not a truthiness coercion — see the
    #: validator: an empty string granting `known` is how a gap becomes a measurement.
    known: bool
    #: Could a connected source have carried this metric for this period at all? `None` means
    #: unhinted and is NOT a synonym for False — same tri-state discipline as
    #: `QualifiedEnterpriseSignal.coverage_ready`, and for the same reason: it is the licence to
    #: make a negative inference, and truthiness must never grant it.
    coverage_ready: bool | None = None

    @field_validator("subject_node_id", "metric", mode="before")
    @classmethod
    def _names(cls, value: Any, info: ValidationInfo) -> str:
        return require_identifier(value, info.field_name or "name")

    @field_validator("value_bp", mode="before")
    @classmethod
    def _measurement(cls, value: Any) -> int | None:
        return None if value is None else require_measure(value, "value_bp")

    @field_validator("unit", mode="before")
    @classmethod
    def _unit(cls, value: Any) -> MetricUnit:
        return require_enum(value, MetricUnit, "unit")

    @field_validator("currency", mode="before")
    @classmethod
    def _currency(cls, value: Any) -> str | None:
        """ISO 4217 or the one recorded unknown, exactly as `contracts/units.Money` spells it —
        imported rather than re-matched so the two cannot drift into accepting different codes."""
        if value is None:
            return None
        code = require_text(value, "currency")
        if code != UNKNOWN_CURRENCY and not ISO_4217.fullmatch(code):
            raise ValueError(
                f"currency must be an uppercase ISO 4217 code or {UNKNOWN_CURRENCY!r}, "
                f"got {code!r}")
        return code

    @field_validator("observed_at")
    @classmethod
    def _period(cls, value: datetime) -> datetime:
        return require_aware(value, "observed_at")

    @field_validator("known", mode="before")
    @classmethod
    def _known(cls, value: Any) -> bool:
        return require_bool(value, "known")

    @field_validator("coverage_ready", mode="before")
    @classmethod
    def _coverage(cls, value: Any) -> bool | None:
        return None if value is None else require_bool(value, "coverage_ready")

    @model_validator(mode="after")
    def _never_interpolated(self) -> MetricPoint:
        """V-3, both directions, plus the money rule.

        Doc 08 states one direction — `known=False` with a value is a reject, because that is an
        interpolation wearing a measurement's clothes. The converse is enforced too and is a GAP
        FLAG against the doc: `known=True` with no value claims a reading and names none, which no
        consumer can act on and which `coverage_ratio_bp` would then count as covered. Both states
        are unreadable rather than merely wrong, so both are refused at the seam that produced
        them.

        The currency rule is the `$84K` / `$8.4K` fault applied one layer up: an amount in minor
        units with no currency is a number that renders as whatever the reader's locale guesses,
        and `contracts/units.Money` refuses the same object for the same reason.
        """
        if not self.known and self.value_bp is not None:
            raise ValueError(
                f"a metric point with known=False must carry no value (got {self.value_bp}) — "
                "an interpolated value is a fabricated observation, indistinguishable in the "
                "column from a measured one, and it inflates the coverage ratio that exists to "
                "reveal the gap")
        if self.known and self.value_bp is None:
            raise ValueError(
                "a metric point with known=True must carry a value — a claimed reading that "
                "names no number is counted as covered and cannot be acted on")
        if self.unit is MetricUnit.MINOR_UNITS and self.currency is None:
            raise ValueError(
                "a metric in minor units must name its currency — an amount whose currency is "
                "unknown renders as whatever the reader's locale guesses")
        if self.unit is not MetricUnit.MINOR_UNITS and self.currency is not None:
            raise ValueError(
                f"currency is meaningless on a {self.unit.value} metric — a count of tickets "
                "denominated in USD is a unit error that would survive every later check")
        return self


class Trend(Measurement):
    """D-03 · which way one metric has moved, over a series that is allowed to have holes.

    **The confidence cap (V-4) is the load-bearing rule.** Four points and a slope is an
    extrapolation, and `MAX_TREND_CONFIDENCE_BP` is what stops it being rendered at the same
    weight as a sentence read out of a contract. There is no input to this type that can produce
    certainty, so certainty is unconstructible.

    **V-5 is the other one.** Two readings and a line between them is not a decline; it is noise
    with an opinion. `point_count < MIN_TREND_POINTS` therefore cannot carry a direction, and the
    honest answer — `INSUFFICIENT_HISTORY` — is a first-class member of the enum rather than an
    error the caller has to remember to check for.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    #: The metric this is a trend IN. Every evidence point must agree with it — see below.
    metric: str
    #: One of five answers, two of which are refusals. See `TrendDirection`.
    direction: TrendDirection
    #: The fitted slope as a proportion of the base, SIGNED: negative is a decline. Signed
    #: because "down 8%" and "up 8%" are the same magnitude and opposite intelligence.
    relative_slope_bp: int
    #: How many consecutive periods moved the same way. Doc 04: a 3-month streak is a far stronger
    #: claim than a noisy slope, and it is the raw fact a reader can check for themselves.
    streak_periods: int
    #: How many KNOWN points the fit used. V-5 reads this.
    point_count: int
    #: known / total periods, 0..10000. The gaps are visible rather than filled.
    coverage_ratio_bp: int
    #: <= `MAX_TREND_CONFIDENCE_BP`, always (V-4).
    trend_confidence_bp: int
    #: The series the trend was computed from, holes included. Required and non-empty: a trend
    #: with no points is a claim with no receipt, which is the one thing every contract in this
    #: package refuses.
    evidence_points: tuple[MetricPoint, ...]

    @field_validator("metric", mode="before")
    @classmethod
    def _metric_name(cls, value: Any) -> str:
        return require_identifier(value, "metric")

    @field_validator("direction", mode="before")
    @classmethod
    def _direction(cls, value: Any) -> TrendDirection:
        return require_enum(value, TrendDirection, "direction")

    @field_validator("relative_slope_bp", mode="before")
    @classmethod
    def _slope(cls, value: Any) -> int:
        return require_signed_bp(value, "relative_slope_bp")

    @field_validator("streak_periods", "point_count", mode="before")
    @classmethod
    def _counts(cls, value: Any, info: ValidationInfo) -> int:
        return require_non_negative(value, info.field_name or "count")

    @field_validator("coverage_ratio_bp", "trend_confidence_bp", mode="before")
    @classmethod
    def _proportions(cls, value: Any, info: ValidationInfo) -> int:
        return require_bp(value, info.field_name or "proportion")

    @model_validator(mode="after")
    def _honest_trend(self) -> Trend:
        """V-4, V-5, and the three coherences a reader would catch on the card.

        V-4 (cap) and V-5 (no direction under four points) are doc 08's. The other three are
        enforced here on the grounds `signal.py` states for its own additions — each admits a
        state that is unexplainable to a user rather than merely wrong, and nothing downstream
        would catch it:

        * A refusal carries no strength. `INSUFFICIENT_*` with a confidence and a streak is a
          number a ranker will sort on, attached to an answer we declined to give.
        * `RISING` with a negative slope prints a sentence that contradicts its own number.
        * A trend whose evidence points are about a DIFFERENT metric is a mislabelled receipt,
          which is worse than a missing one: it looks checkable and is not.
        """
        if self.trend_confidence_bp > MAX_TREND_CONFIDENCE_BP:
            raise ValueError(
                f"trend_confidence_bp must be at most {MAX_TREND_CONFIDENCE_BP} "
                f"(got {self.trend_confidence_bp}) — a trend is never certain")
        if self.direction in DIRECTIONAL and self.point_count < MIN_TREND_POINTS:
            raise ValueError(
                f"a {self.direction.value} trend needs at least {MIN_TREND_POINTS} known points "
                f"(got {self.point_count}) — below that there is no series, only two readings "
                "and a line drawn between them")
        if self.direction in NON_ANSWERS and (self.trend_confidence_bp or self.streak_periods):
            raise ValueError(
                f"{self.direction.value} is a refusal to answer and must carry no confidence and "
                f"no streak (got {self.trend_confidence_bp} / {self.streak_periods})")
        if self.direction is TrendDirection.RISING and self.relative_slope_bp < 0:
            raise ValueError("a rising trend cannot carry a negative slope")
        if self.direction is TrendDirection.DECLINING and self.relative_slope_bp > 0:
            raise ValueError("a declining trend cannot carry a positive slope")
        if not self.evidence_points:
            raise ValueError(
                "a trend requires its evidence points — a trend with no series is a claim with "
                "no receipt")
        wrong = sorted({point.metric for point in self.evidence_points} - {self.metric})
        if wrong:
            raise ValueError(
                f"every evidence point must be about {self.metric!r}; found {wrong} — a receipt "
                "for a different metric looks checkable and is not")
        subjects = sorted({point.subject_node_id for point in self.evidence_points})
        if len(subjects) > 1:
            raise ValueError(
                f"a trend is one subject's series; found {subjects} — two accounts' readings "
                "interleaved in one column produce a slope neither of them has")
        return self

    @property
    def known_points(self) -> int:
        """How many of the carried points actually hold a reading. The number `point_count`
        claims; a caller comparing the two is checking the sampler, which is why both exist."""
        return sum(1 for point in self.evidence_points if point.known)


class CohortPosition(Measurement):
    """D-04 · where one subject sits in a NAMED population. Law 2 made unconstructible otherwise.

    "Bottom decile" is the single most quotable thing this system can say and the easiest to say
    dishonestly. Three fields stop that: `cohort_id` names the population so the reader can ask
    which one (V-1), `population_size` says how many are in it so they can dismiss a cohort of
    four (V-1, V-2), and `band` must actually contain `percentile_bp` so the phrase on the card
    matches the number under it.

    **V-8 · the band must be one the population can REACH.** The three rules above all check the
    label against the number; none of them checks the number against the ARITHMETIC that produced
    it. Nearest rank counts the subject itself, so the smallest percentile a cohort of `n` can
    ever produce is `10000 // n` — 2000 at the floor of five — and every decile below that is
    empty no matter what the members do. The bottom decile was therefore unsayable for every
    cohort of ten or fewer, which is every cohort the sweep prefers to publish, while the WORST
    member of a five-member cohort was published as `D3`. `expressible_divisions` carries the
    arithmetic; this class applies it, narrowing the scheme to the finest one the population can
    express rather than refusing the position — see `_expressible_band`.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    #: The metric the position is IN.
    metric: str
    #: MANDATORY (V-1) — the population's declared identity. A percentile whose cohort is
    #: unnamed cannot be checked, disagreed with, or reproduced.
    cohort_id: str
    #: MANDATORY (V-1), and at least `MIN_COHORT_POPULATION` (V-2).
    population_size: int
    #: 0..10000 within the cohort.
    percentile_bp: int
    #: The quartile or decile label. Must contain `percentile_bp` — see `CohortBand`.
    band: CohortBand
    #: The cohort's own distribution at this metric, in the metric's unit, so the card can show
    #: the reader what they are being compared against rather than only the verdict.
    p25_bp: int
    p50_bp: int
    p75_bp: int
    #: When the comparison was computed. tz-aware UTC. A cohort moves, so a position is a
    #: statement about a moment and must say which.
    computed_at: datetime

    @field_validator("metric", "cohort_id", mode="before")
    @classmethod
    def _names(cls, value: Any, info: ValidationInfo) -> str:
        """V-1's half that a type system can carry: `cohort_id` is non-optional with no default,
        so an unnamed population is not merely discouraged, it is unconstructible."""
        return require_identifier(value, info.field_name or "name")

    @field_validator("population_size", mode="before")
    @classmethod
    def _population(cls, value: Any) -> int:
        return require_non_negative(value, "population_size")

    @field_validator("percentile_bp", mode="before")
    @classmethod
    def _percentile(cls, value: Any) -> int:
        return require_bp(value, "percentile_bp")

    @field_validator("band", mode="before")
    @classmethod
    def _band(cls, value: Any) -> CohortBand:
        return require_enum(value, CohortBand, "band")

    @field_validator("p25_bp", "p50_bp", "p75_bp", mode="before")
    @classmethod
    def _quartiles(cls, value: Any, info: ValidationInfo) -> int:
        """Metric values in the metric's own unit, so unbounded and signed — but never a float:
        a rounded quartile boundary silently reclassifies everyone near it."""
        return require_measure(value, info.field_name or "quartile")

    @field_validator("computed_at")
    @classmethod
    def _computed_at(cls, value: datetime) -> datetime:
        return require_aware(value, "computed_at")

    @model_validator(mode="before")
    @classmethod
    def _expressible_band(cls, data: Any) -> Any:
        """V-8 · narrow the band scheme to one this population can actually produce.

        BEFORE rather than after, because `band` is a field a caller states and the repair is to
        state a coarser one — an after-validator on a frozen model could only refuse. Refusal was
        the other candidate and it is the wrong failure: a five-member cohort HAS a checkable
        quartile position, `MIN_COHORT_POPULATION` exists to license it, and raising here would
        delete the position instead of the overclaim (and would take the sweep's whole comparison
        pass down with it for every small cohort in the org).

        It repairs ONLY the scheme, and only when the label is already truthful in its own scheme.
        A band that does not contain its percentile is passed through untouched so `_law_two`'s
        "must agree" refusal fires with its own message — otherwise recomputing the band from the
        percentile would silently launder every mismatched pair the coherence check exists to
        catch. Anything else unparseable (a missing key, a bad enum, a population under the floor)
        is likewise passed through to the field validator or V-2 that owns the message.
        """
        if not isinstance(data, Mapping):
            return data
        try:
            band = require_enum(data["band"], CohortBand, "band")
            percentile = require_bp(data["percentile_bp"], "percentile_bp")
            scheme = expressible_divisions(data["population_size"], requested=band.divisions)
        except (KeyError, TypeError, ValueError):
            return data
        if scheme == band.divisions or not band.contains(percentile):
            return data
        return {**data, "band": CohortBand.for_percentile(percentile, divisions=scheme)}

    @model_validator(mode="after")
    def _law_two(self) -> CohortPosition:
        """V-2 and the two coherences that keep the card's words matching its numbers.

        V-2 first: a population under five is a ranking of individuals wearing the clothes of a
        distribution, and it is the input that makes "bottom decile" a sentence about one person.

        The band check is the definitional one — the fourth decile IS the 30th-to-40th percentile
        — so a disagreement is not a tuning difference, it is a card that says "bottom decile"
        beside a median. The quartile ordering is the same kind of statement: p25 > p50 is not a
        distribution at all, and every comparison drawn against it is meaningless in a way that
        typechecks.
        """
        if self.population_size < MIN_COHORT_POPULATION:
            raise ValueError(
                f"a cohort needs at least {MIN_COHORT_POPULATION} members "
                f"(got {self.population_size}) — below that a percentile ranks individuals and "
                "calls it a distribution")
        if not self.band.contains(self.percentile_bp):
            low, high = self.band.bounds_bp
            raise ValueError(
                f"band {self.band.value} covers {low}..{high} bp and percentile_bp is "
                f"{self.percentile_bp} — the label and the number must agree, or the card says "
                "one thing and shows another")
        if not self.p25_bp <= self.p50_bp <= self.p75_bp:
            raise ValueError(
                f"the cohort distribution must be ordered p25 <= p50 <= p75, got "
                f"{self.p25_bp} / {self.p50_bp} / {self.p75_bp}")
        return self


class MetricCorrelation(Measurement):
    """D-05 · two metrics move together in one named cohort. It is NEVER a cause.

    **`is_causal` exists in order to be False.** A boolean that is always False looks like dead
    weight until you ask what its absence would mean: without the field, "does L2 claim this is
    causal?" has no answer in the data, so every layer above is free to supply its own — and the
    first renderer that writes "because" over a correlation is indistinguishable from one that
    read a real causal claim. With the field, the absence of the claim is EXPLICIT in every stored
    row, and V-7 makes the other value unconstructible rather than merely discouraged.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    metric_a: str
    metric_b: str
    #: The population the correlation was measured in. Law 2 again: two metrics that correlate
    #: across all accounts and not within a segment is the finding, and an unnamed population
    #: cannot tell those apart.
    cohort_id: str
    #: Spearman's rho in basis points, SIGNED: -10000..10000.
    rho_bp: int
    #: The label a card prints. The rho -> label cutoffs are BLG-12's and are not duplicated here.
    strength: CorrelationStrength
    #: Pairs used. >= `MIN_CORRELATION_SAMPLES` (V-6).
    n: int
    #: ALWAYS False (V-7). See the class docstring.
    is_causal: bool = False

    @field_validator("metric_a", "metric_b", "cohort_id", mode="before")
    @classmethod
    def _names(cls, value: Any, info: ValidationInfo) -> str:
        return require_identifier(value, info.field_name or "name")

    @field_validator("rho_bp", mode="before")
    @classmethod
    def _rho(cls, value: Any) -> int:
        return require_signed_bp(value, "rho_bp")

    @field_validator("strength", mode="before")
    @classmethod
    def _strength(cls, value: Any) -> CorrelationStrength:
        return require_enum(value, CorrelationStrength, "strength")

    @field_validator("n", mode="before")
    @classmethod
    def _sample(cls, value: Any) -> int:
        return require_non_negative(value, "n")

    @field_validator("is_causal", mode="before")
    @classmethod
    def _causal_flag(cls, value: Any) -> bool:
        """A literal bool. Truthiness is exactly how a `1` from a jsonb column would become a
        causal claim nobody typed."""
        return require_bool(value, "is_causal")

    @model_validator(mode="after")
    def _never_causal(self) -> MetricCorrelation:
        """V-6, V-7, and the self-correlation refusal.

        V-6: twenty pairs is the floor. Five points correlate at 0.9 by chance routinely, and a
        spurious "these two always move together" is worse than silence because it is actionable.

        V-7: `is_causal=True` is refused, always and with no override. This is the rule that makes
        it structurally impossible for any downstream layer to RECEIVE a causal claim from L2, no
        matter what it asks for — an assertion in a docstring would be re-litigated by the first
        caller who wanted one.

        A metric correlates with itself at 10000 and says nothing; carrying it would put a
        guaranteed STRONG row in front of every real finding.
        """
        if self.n < MIN_CORRELATION_SAMPLES:
            raise ValueError(
                f"a correlation needs at least {MIN_CORRELATION_SAMPLES} pairs (got {self.n}) — "
                "five points correlate at 0.9 by chance, and a spurious pairing is worse than "
                "silence because somebody acts on it")
        if self.is_causal:
            raise ValueError(
                "is_causal must be False — L2 measures co-movement and never cause; the field "
                "exists so the absence of the claim is explicit in every stored row")
        if self.metric_a == self.metric_b:
            raise ValueError(
                f"a metric cannot be correlated with itself ({self.metric_a!r}) — it is 10000 by "
                "construction and would outrank every real finding")
        return self


class Anomaly(Measurement):
    """D-06 · this metric departed from ITS OWN baseline. The complement to a cohort comparison.

    An account can sit in the top quartile of its cohort and still be collapsing against its own
    history — that account is exactly the one a cohort comparison never surfaces, and it is the
    "at-risk flagged 30+ days early" case the product is sold on.

    **MAD, not standard deviation, and the type says so by carrying `mad_bp`.** Business metrics
    are spiky; one big month widens a standard deviation far enough that a genuine collapse looks
    normal. The dispersion measure is part of the record because "why was this flagged" is not
    answerable from the deviation alone.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    metric: str
    #: This period's reading and the baseline it is being judged against, in the metric's unit.
    current_bp: int
    baseline_bp: int
    #: Median absolute deviation — the width of normal. A magnitude, never negative.
    mad_bp: int
    #: How far off, and how far off in units of MAD. Both are ratios that routinely exceed
    #: 10000 — doc 04 flags above 30000 — hence `require_ratio_bp` rather than `require_bp`.
    deviation_bp: int
    z_like_bp: int
    #: Which side. The sign, as a word.
    direction: AnomalyDirection
    #: Known periods in the baseline. >= `MIN_ANOMALY_PERIODS`.
    periods_used: int

    @field_validator("metric", mode="before")
    @classmethod
    def _metric_name(cls, value: Any) -> str:
        return require_identifier(value, "metric")

    @field_validator("current_bp", "baseline_bp", mode="before")
    @classmethod
    def _readings(cls, value: Any, info: ValidationInfo) -> int:
        return require_measure(value, info.field_name or "reading")

    @field_validator("mad_bp", "deviation_bp", "z_like_bp", mode="before")
    @classmethod
    def _magnitudes(cls, value: Any, info: ValidationInfo) -> int:
        return require_ratio_bp(value, info.field_name or "magnitude")

    @field_validator("direction", mode="before")
    @classmethod
    def _direction(cls, value: Any) -> AnomalyDirection:
        return require_enum(value, AnomalyDirection, "direction")

    @field_validator("periods_used", mode="before")
    @classmethod
    def _periods(cls, value: Any) -> int:
        return require_non_negative(value, "periods_used")

    @model_validator(mode="after")
    def _has_a_baseline(self) -> Anomaly:
        """D-06's floor and the direction coherence.

        Six known periods is the smallest baseline a median absolute deviation means anything
        over; below it the "normal band" is whatever the last two months happened to be, and every
        anomaly computed against it is a statement about the sample size.

        The direction check is definitional: an `ABOVE` anomaly whose current reading is below its
        baseline prints the opposite of its own numbers.
        """
        if self.periods_used < MIN_ANOMALY_PERIODS:
            raise ValueError(
                f"an anomaly needs at least {MIN_ANOMALY_PERIODS} known periods of baseline "
                f"(got {self.periods_used}) — below that the normal band is whatever the last "
                "two periods happened to be")
        if self.direction is AnomalyDirection.ABOVE and self.current_bp < self.baseline_bp:
            raise ValueError(
                f"an ABOVE anomaly cannot have current {self.current_bp} below baseline "
                f"{self.baseline_bp}")
        if self.direction is AnomalyDirection.BELOW and self.current_bp > self.baseline_bp:
            raise ValueError(
                f"a BELOW anomaly cannot have current {self.current_bp} above baseline "
                f"{self.baseline_bp}")
        return self


__all__ = ["BAND_SCHEMES", "DIRECTIONAL", "MAX_TREND_CONFIDENCE_BP", "MIN_ANOMALY_PERIODS",
           "MIN_COHORT_POPULATION", "MIN_CORRELATION_SAMPLES", "MIN_TREND_POINTS",
           "NON_ANSWERS", "Anomaly", "AnomalyDirection", "CohortBand", "CohortPosition",
           "CorrelationStrength", "Measurement", "MetricCorrelation", "MetricPoint",
           "MetricUnit", "Trend", "TrendDirection", "expressible_divisions", "require_measure",
           "require_ratio_bp", "require_signed_bp"]
