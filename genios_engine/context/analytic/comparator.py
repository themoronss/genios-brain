"""L2.4.5 · THE POPULATION COMPARATOR (BLG-10) — a reading becomes a POSITIONED reading.

`22%` is a number. *"22%, which is the 31st percentile of the 47 accounts on your Growth plan"*
is a sentence somebody can act on. Every comparative statement the product promises — "bottom
decile", "top quartile", "unlike your best customers" — reduces to the two units here, and
without them the whole analytic stratum emits numbers with nothing to hold them against.

WHAT THIS MODULE OWNS, AND WHAT IT DELIBERATELY DOES NOT
--------------------------------------------------------
The percentile arithmetic already exists and is NOT re-implemented here.
`context/analytic/cohort.percentile_bp` is doc 04 L2.4.5 step 3 (`rank = count(v <= value)`,
`percentile_bp = rank * 10000 // n`) and `cohort.position_from_values` is steps 2-5, including
Law 2 and the `CohortPosition` construction. A second percentile that disagrees with the first by
one rank is a defect nobody can see, so this module imports both and adds only what was missing:

  U1  the READING -> POSITION path: loading a cohort's population as it stood at an instant,
      choosing WHICH cohort a node is best compared against when it is in several, rendering the
      sentence, and writing the answer back to `graph_facts` on the drain so L3/L4 read it like
      any other fact. Without the last one the comparator is a function nothing calls.

  U2  the LOOKALIKE comparison: a reference cohort's trait PROFILE (modal value for a categorical
      trait, interquartile range for a numeric one), and how many of a candidate's traits fall
      inside it — returned WITH THE TRAIT NAMES. *"Matches on industry, plan and deal size;
      differs on stage"* is checkable. `0.87 similar` is not, and is exactly what `identity.py`
      refuses for the same reason.

THE TIE RULE, STATED ONCE
-------------------------
Two members holding the SAME value get the SAME percentile: `rank` counts `v <= value`, so both
of them count each other and every equal peer, and both land on the identical basis point. That
is the rule this layer wants — a percentile is a statement about a VALUE, so two accounts on 22%
cannot be told "31st" and "38th" — and it has a consequence worth stating rather than
discovering: the lowest value in a population of ten is the 1000th basis point, not the 0th, and
the highest is always exactly 10000. `support_situations.percentile_bp` computes a DIFFERENT
statistic (ties count as half); see the note on `percentile_bp` in `cohort.py` — the two are
named apart on purpose and doc 04's own acceptance number ("the lowest value in a cohort of 10 ->
percentile_bp near 1000") is this one's, not that one's.

GAP FLAG — doc 09's H3 row reads *"nearest-rank matches the existing
`support_situations.percentile_bp` exactly"*, and doc 04 line 554 states the premise it rests on:
*"`support_situations.py:405 percentile_bp()` already implements nearest-rank"*. It does not. It
is a MID-RANK statistic (ties counted as half), so the row as written is unsatisfiable in both
directions at once — a function cannot be nearest-rank AND agree with a mid-rank one, and the two
disagree by roughly `5000 // n` on every population. Doc 04's own acceptance figure settles which
of them L2.4.5 owes: the lowest value in a cohort of ten is 1000 bp under nearest-rank and 500
under mid-rank, so the comparator's is the number the doc is asking for.

What the row is actually protecting — that there is not a second copy of ONE statistic quietly
disagreeing with the first — is enforced by construction rather than by comment: this module
imports `cohort.percentile_bp` and defines no percentile of its own.
`tests/context/analytic/test_h34_gate_probes.py` pins BOTH functions on one population, asserts
doc 04's acceptance figure against the nearest-rank one, and asserts that no third percentile
exists in the stratum, so a drift onto the other's answer fails a gate rather than a card.

Reconciling the support module ONTO nearest-rank was tried and refused, and the reason is a
regression rather than a preference: a uniformly aged backlog would put every open loop at exactly
10000, `read_backlog_items`' `pctl < AGING_PERCENTILE_BP` guard would stop holding for all of them,
and a desk whose five loops were all raised this morning would report five aging findings. The
float arithmetic in that module — the part of it that IS a defect under this layer's rules — was
removed; the statistic was left where it is.

REFUSAL IS THE ANSWER, NOT A DEGRADED ONE
-----------------------------------------
A population below `MIN_COHORT_POPULATION` is not a weak comparison; it is no comparison, and it
comes back as a `CohortRefusal` a card can render. With four members every percentile is 2500,
5000, 7500 or 10000 — the phrase would be describing the arithmetic rather than the business.
The same is true of a lookalike with too few evaluable traits: "matches on 1 of 1 trait" is a
coin flip wearing a percentage.

POINT-IN-TIME
-------------
`eval_time` is a parameter everywhere and there is no clock in this module. A comparison "as at"
a past instant reads the membership that was open then (`joined_at <= at < left_at`) and the
readings observed by then AND NOT BEFORE THE STALENESS HORIZON (`since <= observed_at <= at`), so
re-asking March's question in September gets March's answer — including March's answer about who
was dark. Every measure is an integer basis point; no float appears, not even transiently.

AND THE WRITE PRESERVES IT. The published fact goes through `analytic/publish.publish_derived_fact`,
which never moves an existing row's `valid_from`: a position published in March still reads at
`read_graph(as_of=March)` after a September sweep changed it, because September opened a new
period-keyed row and closed March's rather than rewriting March's window. This module's own copy
of that upsert ended `valid_from = excluded.valid_from` and destroyed exactly the property X7
shipped in the same wave.

BOUNDING
--------
The bound is now stated in terms of CHANGES rather than of sweeps, which is both tighter and
true: the version id is period-keyed at ISO-week grain, so a position whose value never moves is
ONE row for the life of the tenant (a sweep that agrees with the stored value writes nothing at
all), and one that moves is at most one row per ISO week in which it actually moved. That is what
`ComparisonSweep.written` counts. `expertise_packages` reached 181 MB over 345 rows and put this
database into read-only because a writer on a recurring path appended; this one cannot. Both
passes are additionally capped per sweep — in STALENESS order, so a capped tail is deferred rather
than deleted — and no new table is introduced: the rows are `graph_facts`, which is already in
`api/account_routes._ORG_SCOPED_TABLES`.

WHAT A COMPARISON CARD MAY CARRY
--------------------------------
The subject's own reading, its rank, the size and name of the population, and the band. The
cohort's p25/p50/p75 only when the population can support a ladder that is not the sorted
population — see `publishable_distribution`, which applies `peer_baseline`'s floor and smoothing
window at the seam that publishes rather than leaving two halves of one wave disagreeing about
whether three members' exact readings may be printed on a fourth member's card.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Iterable, Mapping, Sequence

from sqlalchemy import text

from genios_engine.context.analytic.cohort import (COHORT_MEMBERSHIP_TABLE, COHORT_NODE_TYPES,
                                                   SYSTEM_AUTHOR, CohortDefinition, CohortRefusal,
                                                   CohortRefusalReason, FactKind, FactRegistry,
                                                   default_fact_registry, load_definitions,
                                                   load_node_facts, normalise_fact,
                                                   position_from_values)
from genios_engine.context.analytic.history import (HISTORY_TABLE, MetricGrain,
                                                    MetricRegistry)
# ONE staleness policy for the analytic stratum, imported rather than restated — see the
# `STALE_AFTER_PERIODS` note below for the four-times-looser horizon the duplicate produced.
from genios_engine.context.analytic.peer_baseline import (BASELINE_SMOOTHING_WINDOW,
                                                          MIN_BASELINE_POPULATION,
                                                          STALE_AFTER_PERIODS, metric_grain,
                                                          require_publishable_window,
                                                          smoothed_rung, staleness_floor)
from genios_engine.context.analytic.publish import PublishAction, publish_derived_fact
from genios_engine.contracts.analytic import (MIN_COHORT_POPULATION, CohortBand, CohortPosition,
                                              MetricUnit)
from genios_engine.contracts.validators import (require_aware, require_bp, require_identifier,
                                                require_non_negative)
from genios_engine.contracts.visibility import ORG

# =================================================================================================
# THE NUMBERS
# =================================================================================================

#: `graph_facts.field` prefix for U1's answer. One field per metric, like the trend computer:
#: L3 selects on `field`, and a per-node blob would make "where do we sit on close rate" a read
#: of every comparison the node has.
POSITION_FACT_PREFIX = "derived.cohort_position."

#: U2's answer. Keyed by REFERENCE COHORT rather than by metric, because a lookalike is a
#: statement about one named population ("your top-ARR quartile") and a node can be scored
#: against more than one without the two rows meaning the same thing.
LOOKALIKE_FACT_PREFIX = "derived.lookalike."

#: Both facts are JSON documents. A position split into six scalar facts is six rows a reader has
#: to reassemble and any one of which can go stale alone.
COMPARISON_VALUE_TYPE = "json"

#: Deciles, not quartiles, as the REQUESTED band scheme: "bottom decile" is the phrase the product
#: promises and a quartile cannot express it. `CohortBand` accepts 4 or 10 and nothing else.
#:
#: REQUESTED, and not necessarily published. `contracts.analytic.expressible_divisions` proves
#: that every band of a d-scheme is reachable only when `population_size > d` — nearest rank
#: counts the subject, so the smallest percentile a cohort of n can produce is `10000 // n` and
#: never 0 — and `CohortPosition` narrows the scheme to the finest one the population can express.
#: So this constant is the CEILING on what a card may say and the population decides what it
#: actually says: eleven members or more can be told "bottom decile", ten or fewer are told a
#: quartile. Asking for deciles here therefore can no longer produce a D-label on a cohort whose
#: arithmetic can never reach D1 — which it did, on exactly the cohorts `most_specific`
#: deliberately prefers, because it publishes the SMALLEST population.
DEFAULT_DIVISIONS = 10

#: Per-sweep caps. A tenant with 5,000 nodes and twelve metrics must not turn one drain into a
#: 60,000-statement transaction; work not done this sweep is done by the next one — which is TRUE
#: only because the order is by STALENESS rather than by id (see `_COMPARED_PAIRS_SQL` and
#: `_publication_order`). Under the old `order by m.cohort_id, h.metric` the order was stable
#: across sweeps, so an org above budget cut the same tail on every drain for ever and those nodes
#: could never receive a position at all — "the next sweep does it" was false for precisely the
#: nodes the budget existed to defer.
MAX_POSITION_FACTS_PER_SWEEP = 5_000
MAX_LOOKALIKE_FACTS_PER_SWEEP = 2_000

#: How many (cohort, metric) pairs one sweep will position at all.
MAX_COMPARED_PAIRS_PER_SWEEP = 240

#: THE STALENESS HORIZON. `STALE_AFTER_PERIODS`, `metric_grain` and `staleness_floor` are IMPORTED
#: from `peer_baseline` (see the imports above) and are not restated here. The defect they close —
#: a cross-member read bounded only from above, so a member dark for ten months still counted as
#: KNOWN, `unknown` stayed 0, and `INSUFFICIENT_COVERAGE` was a refusal the plumbing could not
#: produce — is derived once, at `peer_baseline.STALE_AFTER_PERIODS`.
#:
#: THIS MODULE USED TO CARRY ITS OWN COPY OF ALL THREE, AND THE COPY DISAGREED. It resolved the
#: grain against `history.default_registry()`, which holds the CORE metrics only, so all twelve
#: names the sampler actually writes fell through to a MONTH default — a three-MONTH horizon on
#: eleven metrics whose real grain is a WEEK. Measured at eval_time 2026-03-01: this module's
#: floor was 2026-01-01 where the ladder's was 2026-02-09, so a member last read in mid-January
#: was dark to `peer_baseline` and known here, in the same drain, on the same org, for the same
#: metric. Two answers about who is instrumented is not a tuning difference — it is the coverage
#: floor refusing a ladder and publishing a peer position off the same rows.
#:
#: One policy, one constant, one place. The import is the enforcement: there is no second number
#: to keep in step.

#: The grain the PAIR SCAN assumes, and the one place a coarse default is still correct.
#: `_compared_pairs` spans every metric at once and only decides which (cohort, metric) pairs are
#: LOOKED AT; `cohort_readings` then applies the exact per-metric horizon to each. Too coarse here
#: admits a cohort whose members are all dark, and `cohort_readings` refuses it — which WRITES the
#: refusal and retracts last week's position. Too tight would silently drop the pair and leave the
#: stale position standing, unretracted. The asymmetry decides the direction.
DEFAULT_METRIC_GRAIN = MetricGrain.MONTH

#: What `graph_facts.visibility_scope` this module CLAIMS. Stated here rather than as a literal in
#: the SQL because a cohort position carries peers' readings onto the subject's node and a
#: lookalike carries peers' matched trait names, so `contracts/visibility`'s law — the audience of
#: a derived insight is never wider than the audience of the evidence it came from — is a claim
#: this module is making, not a default it inherited. `publish_derived_fact` takes it as a
#: required keyword precisely so every such claim is greppable from one place.
POSITION_FACT_SCOPE = ORG

#: The `fact_version_id` prefix. A true PREFIX of the period-keyed id `publish_derived_fact`
#: builds, and the same string the pre-period rows were written under, so those legacy rows are
#: absorbed as this module's own open stint rather than orphaned beside a new one.
VERSION_PREFIX = "fv_cmp_"

#: A lookalike over fewer than three evaluable traits is a coin flip wearing a percentage.
MIN_LOOKALIKE_TRAITS = 3

#: The kinds a trait profile can be built from. MOMENT is excluded deliberately: the modal
#: instant of a cohort is meaningless and an interquartile range of timestamps ages out of being
#: true the day after it is computed — every horizon in this layer is relative to `eval_time`,
#: which a stored profile is not.
PROFILABLE_KINDS = frozenset({FactKind.NUMBER, FactKind.RATIO, FactKind.TEXT, FactKind.FLAG})

#: Never a trait. `node.name` IS the identity, so "matches on name" is either a tautology or one
#: tenant's node list leaking into another node's card; `node.type` is constant within a cohort
#: and would inflate every match_bp by a free point.
NON_TRAIT_FACTS = frozenset({"node.name", "node.type"})

#: How the sweep recognises the shipped reference populations. `cohort.quartile_cohorts` names
#: its top slot "<fact> · top quartile" and the id is an opaque hash, so the NAME is the only
#: public handle on the slot — the assumption is written down in
#: `docs/plans/L2_MISSING_UNIT_SPECS.md` §3 A-10. This line used to defer to a build report that
#: was never written, which is worse than deferring to nothing: the reader stops looking.
TOP_SLOT_SUFFIX = "top quartile"


# =================================================================================================
# U1 · PERCENTILE WITHIN COHORT — the reading, positioned
# =================================================================================================

def position_fact_field(metric: str) -> str:
    """`derived.cohort_position.<metric>` — where U1's answer lands in `graph_facts`."""
    return f"{POSITION_FACT_PREFIX}{require_identifier(metric, 'metric')}"


def lookalike_fact_field(cohort_id: str) -> str:
    """`derived.lookalike.<cohort_id>` — one row per (candidate, reference cohort)."""
    return f"{LOOKALIKE_FACT_PREFIX}{require_identifier(cohort_id, 'cohort_id')}"


#: The ordinal suffixes, integer-indexed. English, and a table rather than a chain of `if`s
#: because 11/12/13 are the exceptions that a chain gets wrong.
_SUFFIX = ("th", "st", "nd", "rd", "th", "th", "th", "th", "th", "th")


def ordinal(number: int) -> str:
    """`31 -> '31st'`. Integer arithmetic; 11th, 12th and 13th are not 11st, 12nd, 13rd."""
    number = require_non_negative(number, "ordinal")
    if 11 <= number % 100 <= 13:
        return f"{number}th"
    return f"{number}{_SUFFIX[number % 10]}"


def _rendered_value(value_bp: int, unit: MetricUnit | None) -> str:
    """The reading in words. Integer division only — `2200` bp is `22%`, never `22.0%`.

    A `BP` reading is shown as a whole percent because that is the sentence a human says; the
    exact basis point travels in the fact body beside it, so nothing is lost and no float is
    introduced to produce a decimal nobody asked for.
    """
    if unit is MetricUnit.BP:
        return f"{value_bp // 100}%"
    if unit is MetricUnit.DAYS:
        return f"{value_bp} day" if value_bp == 1 else f"{value_bp} days"
    if unit is MetricUnit.MINOR_UNITS:
        return f"{value_bp} minor units"
    return str(value_bp)


def describe_position(position: CohortPosition, value_bp: int, *,
                      unit: MetricUnit | None = None, cohort_name: str | None = None) -> str:
    """The sentence. Deterministic and template-built — THE MODEL MAY DESCRIBE, NEVER SCORE, and
    here it does not even describe: every word is derived from the numbers beside it.

    "22%, the 31st percentile of 47 accounts on your Growth plan (D4)". The band is carried in
    the words as well as the number because `CohortPosition` guarantees they agree, and a reader
    who sees them disagree has found a bug rather than a rounding difference.
    """
    where = cohort_name or position.cohort_id
    return (f"{_rendered_value(value_bp, unit)}, the "
            f"{ordinal(require_bp(position.percentile_bp, 'percentile_bp') // 100)} percentile of "
            f"{position.population_size} in {where} ({position.band.value})")


@dataclass(frozen=True, slots=True)
class PositionedReading:
    """A raw reading and where it sits — the object this whole component exists to produce.

    Carries the VALUE as well as the position on purpose: a card that shows only the percentile
    has thrown away the thing being compared, and "you are in the 31st percentile" with no number
    beside it is unfalsifiable.
    """

    metric: str
    subject_node_id: str
    value_bp: int
    position: CohortPosition
    phrase: str
    unit: MetricUnit | None = None
    #: The cohort's own p25/p50/p75 AS A CARD MAY CARRY THEM, or `None` when it may not — see
    #: `publishable_distribution`. Deliberately NOT `position.p25_bp` and friends: those are the
    #: literal readings of three named members, which is a disclosure this component is not
    #: allowed to make and `peer_baseline` refuses to make on the same populations.
    distribution: tuple[int, int, int] | None = None

    @property
    def is_position(self) -> bool:
        return True

    @property
    def cohort_id(self) -> str:
        return self.position.cohort_id

    @property
    def population_size(self) -> int:
        return self.position.population_size

    @property
    def percentile_bp(self) -> int:
        return self.position.percentile_bp

    @property
    def band(self) -> CohortBand:
        return self.position.band


def publishable_distribution(values: Mapping[str, int]) -> tuple[int, int, int] | None:
    """The cohort's p25/p50/p75 as a comparison CARD may carry them, or `None`.

    THE CONTRADICTION THIS RESOLVES, because two components of one wave applied opposite rules to
    the same order statistics of the same populations. `cohort.position_from_values` fills
    `CohortPosition.p25_bp/p50_bp/p75_bp` with `_quantile` — the literal reading of the member
    standing at that rank — from a population of five upward. `peer_baseline` sets
    `MIN_BASELINE_POPULATION = 10` and `BASELINE_SMOOTHING_WINDOW = 3` and makes narrowing them
    impossible (`require_publishable_window`) for exactly the reason it states: "a five-rung
    ladder over a population of six IS the sorted population". Measured on a five-member cohort
    `{1200, 3450, 5100, 7800, 9900}`, the card for the top member carried p25=3450, p50=5100,
    p75=7800 — three of the other four members' exact numbers — beside an exact rank, which bounds
    the fourth. Within one tenant that is not a breach; it is one wave publishing what its own
    other half refuses to publish, and the two cannot both be the rule.

    THE RULE THIS MODULE ADOPTS: the ladder is the baseline's, so the baseline's disclosure terms
    apply to it wherever it is published. A comparison card may always carry the SUBJECT's own
    reading, its rank, the population count and the band — those are facts about the subject and
    about the shape of the population, not about any other member. It may carry the distribution
    only when the population can support a ladder that is not the sorted population: at least
    `MIN_BASELINE_POPULATION` members, and every rung the mean of `BASELINE_SMOOTHING_WINDOW`
    adjacent readings, computed by `peer_baseline.smoothed_rung` itself rather than by a second
    copy here.

    Below the ladder's floor the answer is `None` — WITHHELD, not degraded. A narrower window is
    the disclosure, and a card that showed a lower-resolution version of three members' readings
    would be showing three members' readings. The position itself survives: `CohortPosition` is
    the internal computation and is unchanged, and the subject still learns its own rank in a
    named population of a stated size, which is the whole of what BLG-10 promises.

    `position_from_values` is where the raw quantiles are still produced (X2 owns `cohort.py` and
    it is frozen for this wave). That is why the gate is here, at the two seams that PUBLISH —
    `position_fact_value` and the `PositionedReading` a route renders — rather than on the
    contract object every internal caller passes around.
    """
    if len(values) < MIN_BASELINE_POPULATION:
        return None
    window = require_publishable_window(BASELINE_SMOOTHING_WINDOW)
    known = sorted(values.values())
    return (smoothed_rung(known, 2_500, window), smoothed_rung(known, 5_000, window),
            smoothed_rung(known, 7_500, window))


def compare_reading(*, metric: str, cohort_id: str, values: Mapping[str, int],
                    subject_node_id: str, eval_time: datetime, unknown: int = 0,
                    divisions: int = DEFAULT_DIVISIONS, unit: MetricUnit | None = None,
                    cohort_name: str | None = None) -> PositionedReading | CohortRefusal:
    """U1, PURE — no database. A reading in, a positioned reading or a REFUSAL out.

    The arithmetic is `cohort.position_from_values` and is not repeated here: Law 2, the coverage
    floor, the nearest-rank percentile and the p25/p50/p75 the card shows all live there, and a
    second copy is a second thing to keep in step. What this adds is the value and the sentence.
    """
    outcome = position_from_values(metric=metric, cohort_id=cohort_id, values=values,
                                   subject_node_id=subject_node_id, eval_time=eval_time,
                                   divisions=divisions, unknown=unknown)
    if isinstance(outcome, CohortRefusal):
        return outcome
    value_bp = values[subject_node_id]
    return PositionedReading(
        metric=outcome.metric, subject_node_id=subject_node_id, value_bp=value_bp,
        position=outcome, unit=unit, distribution=publishable_distribution(values),
        phrase=describe_position(outcome, value_bp, unit=unit, cohort_name=cohort_name))


@dataclass(frozen=True, slots=True)
class PopulationReadings:
    """One cohort's population at one instant: who was in it, and what is known of them.

    `unknown` is carried rather than recomputed because it is the input to the COVERAGE refusal,
    and a caller that inferred it from `len(members) - len(values)` after the fact would be
    inferring it from a different read.
    """

    cohort_id: str
    metric: str
    values: Mapping[str, int]
    unknown: int
    member_count: int
    #: The unit the readings are IN, read off the rows rather than assumed. A stored `5000` is
    #: fifty percent, fifty dollars or five thousand days, and a card that guesses is the
    #: `$84K`/`$8.4K` fault; `None` only when the population has no reading at all.
    unit: MetricUnit | None = None


_MEMBERS_AT_SQL = text(
    f"select node_id from {COHORT_MEMBERSHIP_TABLE} "
    "where org_id = :o and cohort_id = :c and joined_at <= :at "
    "  and (left_at is null or left_at > :at) order by node_id")

def staleness_horizon(eval_time: datetime, grain: MetricGrain,
                      periods: int = STALE_AFTER_PERIODS) -> datetime:
    """This module's name for `peer_baseline.staleness_floor`, which is the ONE implementation.

    Kept as a name rather than as a body: the horizon this module applies and the horizon the
    ladder applies have to be the same instant or the same population reads as two different
    populations, and the way to guarantee that is to have one function. `periods` stays positional
    here because `cohort_readings` and `_compared_pairs` pass it through as their own parameter.
    """
    return staleness_floor(require_aware(eval_time, "eval_time"), grain, periods=periods)


#: The LATEST reading of one metric per member, as at an instant. `observed_at <= :at` is what
#: makes a past comparison a past comparison; `sampled_at desc` breaks the tie the way
#: `history.read_series` does, so a backfill written after a live reading of the same period does
#: not silently win.
#:
#: `observed_at >= :since` is the STALENESS HORIZON and it is the half that was missing. Without a
#: lower bound a member read once, eighteen months ago, is indistinguishable from a member read
#: this week: it lands in `values`, so `unknown` stays 0, so `MAX_UNKNOWN_SHARE_BP` never trips
#: and `INSUFFICIENT_COVERAGE` is a refusal the plumbing cannot produce. A member past the horizon
#: now falls out of `values` and is counted as UNKNOWN — which is what the floor is for. It is
#: dropped rather than refused one member at a time on purpose: one dark member in twenty is a
#: gap the coverage share absorbs, and half a cohort dark is the refusal.
_LATEST_VALUES_SQL = text(
    f"select distinct on (subject_node_id) subject_node_id as node_id, value_bp, unit "
    f"from {HISTORY_TABLE} "
    "where org_id = :o and metric = :m and subject_node_id = any(:ids) "
    "  and observed_at <= :at and observed_at >= :since and sampled_at <= :at "
    "order by subject_node_id, observed_at desc, sampled_at desc")

#: Which (cohort, metric) pairs are worth positioning at all — read off what EXISTS rather than
#: from the cross product of cohorts and the metric registry, so a metric no member has a reading
#: of costs nothing. Same staleness lower bound, at the COARSEST grain (`DEFAULT_METRIC_GRAIN`),
#: because one statement spans every metric and only the per-metric read below knows each one's
#: own grain: a candidate filter must never be tighter than the authoritative read, or a pair the
#: comparator would have refused for coverage disappears instead, which is a silent drop rather
#: than a stated refusal.
#:
#: THE ORDER IS THE FIX FOR THE DARK TAIL. `order by m.cohort_id, h.metric` is stable across
#: sweeps, so an org with more pairs than `MAX_COMPARED_PAIRS_PER_SWEEP` cut the SAME tail on
#: every drain, for ever — those nodes could never receive a position at all, while both this
#: module and `runner.py` asserted "work not done this sweep is done by the next one". The three
#: keys below are read off the data, so no cursor table is needed and a restart cannot lose one:
#:
#:   1. `bool_or(p.fact_version_id is null)` — SOME member of this pair has no open position at
#:      all. Never-positioned pairs outrank every positioned one, monotonically, which is what
#:      makes "every node eventually receives a position" true rather than aspirational.
#:   2. `bool_or(p.valid_from < h.sampled_at)` — some member's position predates a reading it
#:      should reflect. `metric_history`'s upsert only moves `sampled_at` when the VALUE moves
#:      (`_UPSERT`'s `where ... is distinct from` clause), so this is real new evidence and not
#:      merely another sweep of an unchanged series.
#:   3. the oldest open position, then (cohort, metric) so the answer is deterministic.
#:
#: A pair in neither class 1 nor class 2 has nothing new to say, so where it sits among its own
#: class cannot cost a reader anything: recomputing it writes nothing (`PublishAction.UNCHANGED`).
_COMPARED_PAIRS_SQL = text(
    f"select m.cohort_id as cohort_id, h.metric as metric, count(distinct m.node_id) as members "
    f"from {COHORT_MEMBERSHIP_TABLE} m "
    f"join {HISTORY_TABLE} h on h.org_id = m.org_id and h.subject_node_id = m.node_id "
    "left join graph_facts p on p.org_id = m.org_id and p.subject_node_id = m.node_id "
    "  and p.field = :position_prefix || h.metric and p.valid_to is null "
    "where m.org_id = :o and m.joined_at <= :at and (m.left_at is null or m.left_at > :at) "
    "  and h.observed_at <= :at and h.observed_at >= :since and h.sampled_at <= :at "
    "group by m.cohort_id, h.metric having count(distinct m.node_id) >= :floor "
    "order by bool_or(p.fact_version_id is null) desc, "
    "         bool_or(p.valid_from < h.sampled_at) desc, "
    "         min(p.valid_from) asc nulls first, m.cohort_id, h.metric limit :n")


def cohort_readings(store, *, org_id: str, cohort_id: str, metric: str, eval_time: datetime,
                    registry: MetricRegistry | None = None,
                    stale_after_periods: int = STALE_AFTER_PERIODS) -> PopulationReadings:
    """The population AS IT WAS at `eval_time`, and its readings as they were known then.

    Two statements, both org-scoped, both parameterised. Nothing that identifies a member leaves
    this function to a card — `PopulationReadings` is consumed into a `CohortPosition`, which
    carries a count and three boundaries and no node ids at all.

    KNOWN MEANS RECENTLY READ. `unknown` counts the members with no reading inside the metric's
    own staleness window as well as those with no reading at all, because to the coverage floor
    they are the same member: nobody can say what that account's close rate is now. That is the
    input `MAX_UNKNOWN_SHARE_BP` was written for, and until the horizon existed it could only ever
    be zero on this path.
    """
    at = require_aware(eval_time, "eval_time")
    since = staleness_horizon(at, metric_grain(metric, registry), stale_after_periods)
    engine = getattr(store, "engine", store)
    with engine.connect() as conn:
        members = [str(row.node_id) for row in
                   conn.execute(_MEMBERS_AT_SQL, {"o": org_id, "c": cohort_id, "at": at}).all()]
        rows = (conn.execute(_LATEST_VALUES_SQL,
                             {"o": org_id, "m": metric, "ids": members, "at": at,
                              "since": since}).all()
                if members else [])
    values = {str(row.node_id): int(row.value_bp) for row in rows if row.value_bp is not None}
    units = {MetricUnit(row.unit) for row in rows if row.value_bp is not None}
    return PopulationReadings(cohort_id=cohort_id, metric=metric, values=values,
                              unknown=len(members) - len(values), member_count=len(members),
                              unit=units.pop() if len(units) == 1 else None)


def compare_in_cohort(store, *, org_id: str, cohort_id: str, metric: str, subject_node_id: str,
                      eval_time: datetime, divisions: int = DEFAULT_DIVISIONS,
                      unit: MetricUnit | None = None, cohort_name: str | None = None,
                      metric_registry: MetricRegistry | None = None,
                      ) -> PositionedReading | CohortRefusal:
    """Position ONE node against ONE cohort, on demand — the read behind a card's comparison.

    `metric_registry` only decides the staleness horizon's GRAIN; left out, the coarser default
    applies, so an on-demand read is never stricter about darkness than the sweep is.
    """
    at = require_aware(eval_time, "eval_time")
    readings = cohort_readings(store, org_id=org_id, cohort_id=cohort_id, metric=metric,
                               eval_time=at, registry=metric_registry)
    if readings.member_count == 0:
        return CohortRefusal(CohortRefusalReason.NO_SUCH_COHORT, cohort_id, metric, 0, at,
                             "no membership was open for this cohort at that instant")
    if subject_node_id not in readings.values:
        # Distinguish "not one of them" from "one of them, but unread": the first is a question
        # asked of the wrong population and the second is a coverage problem on the right one, and
        # a card that confuses them tells a customer their account is missing data when in fact it
        # was compared against the wrong peer group.
        if subject_node_id not in _open_members(store, org_id, cohort_id, at):
            return CohortRefusal(CohortRefusalReason.SUBJECT_NOT_A_MEMBER, cohort_id, metric,
                                 len(readings.values), at,
                                 "the subject is not in the cohort it was compared against")
    return compare_reading(metric=metric, cohort_id=cohort_id, values=readings.values,
                           subject_node_id=subject_node_id, eval_time=at,
                           unknown=readings.unknown, divisions=divisions,
                           unit=unit if unit is not None else readings.unit,
                           cohort_name=cohort_name)


def most_specific(outcomes: Sequence[PositionedReading | CohortRefusal],
                  ) -> PositionedReading | CohortRefusal | None:
    """Which comparison to publish when a node sits in several cohorts. THE RULE, STATED:

    a position always beats a refusal; among positions the SMALLEST population wins, because the
    most specific peer group is the most informative thing to be told ("22%, the 31st percentile
    of the 12 enterprise accounts" says more than "of all 4,000 nodes"); among refusals the
    LARGEST population wins, because the near miss is the honest one to show. Ties in both
    directions break on `cohort_id` lexicographically, so the answer does not depend on the order
    the database happened to return the cohorts in.
    """
    #: THE BAND THIS PICKS IS ALWAYS ONE ITS POPULATION CAN REACH. Choosing the SMALLEST
    #: population is choosing the cohort where an unreachable decile did the most damage — the
    #: worst member of a five-member cohort was published as `D3`, which reads as "below average,
    #: not alarming". Nothing is checked here because nothing CAN be wrong here: every candidate
    #: is a `CohortPosition`, and that type narrows its own scheme to `expressible_divisions` at
    #: construction, so a `PositionedReading` carrying an unreachable band does not exist to pick.
    positions = [o for o in outcomes if isinstance(o, PositionedReading)]
    if positions:
        return min(positions, key=lambda o: (o.population_size, o.cohort_id))
    refusals = [o for o in outcomes if isinstance(o, CohortRefusal)]
    if refusals:
        # `min` on a NEGATED population rather than `max`, so both branches break their tie the
        # same way — on the smallest `cohort_id`. A `max` here would need the id inverted too, and
        # inverting a string's ordering is where "coh_a" and "coh_ab" stop agreeing with the
        # branch above.
        return min(refusals, key=lambda o: (-o.population_size, o.cohort_id))
    return None


def position_fact_value(outcome: PositionedReading | CohortRefusal) -> dict[str, Any]:
    """The JSON body of the fact — the answer AND its population, or the refusal and its reason.

    REFUSALS ARE WRITTEN TOO, for the reason the trend computer writes them: the cheap-looking
    alternative leaves last week's "top decile" sitting on a node whose cohort has since shrunk
    below the floor, and nothing would ever retract it. Overwriting the same version-keyed row
    with "we cannot say" makes the fact self-correcting at no extra row.
    """
    if isinstance(outcome, CohortRefusal):
        return {"metric": outcome.metric, "cohort_id": outcome.cohort_id,
                "refused": outcome.reason.value, "population_size": outcome.population_size,
                "detail": outcome.detail}
    position = outcome.position
    # The DISCLOSURE gate, and the WITHHELD case is stated in the body rather than left as three
    # absent keys: a reader that found no `p25_bp` could not tell "this cohort is too small to
    # describe" from "an older writer wrote this row", and only the first of those is an answer.
    ladder = outcome.distribution
    body = {"metric": position.metric, "cohort_id": position.cohort_id,
            "value_bp": outcome.value_bp,
            "unit": outcome.unit.value if outcome.unit is not None else None,
            "percentile_bp": position.percentile_bp, "band": position.band.value,
            "population_size": position.population_size,
            "p25_bp": ladder[0] if ladder else None, "p50_bp": ladder[1] if ladder else None,
            "p75_bp": ladder[2] if ladder else None,
            "distribution_window": BASELINE_SMOOTHING_WINDOW if ladder else None,
            "distribution_withheld": None if ladder else
            f"a distribution needs {MIN_BASELINE_POPULATION} members to publish; this cohort has "
            f"{position.population_size} and the ladder would be the sorted population",
            "phrase": outcome.phrase}
    # `computed_at` is DELIBERATELY absent. It is the sweep instant, so including it made the
    # jsonb body different on every drain of an unchanged position — which defeats
    # `publish_derived_fact`'s UNCHANGED branch and turns "one row per (node, field) for the life
    # of the tenant" into one superseded row per ISO week whether or not anything moved. The
    # question it answered — since when has this been true — is what the row's own `valid_from`
    # and `occurred_at` columns are, read through `graph_store.read_graph(as_of=...)`.
    return body


# =================================================================================================
# U2 · LOOKALIKE COMPARISON — traits by name, never a similarity score
# =================================================================================================

class LookalikeRefusalReason(str, Enum):
    """Why no lookalike. Each one is a sentence a founder can act on."""

    #: The reference cohort is below `MIN_COHORT_POPULATION` — a profile of four is four accounts.
    INSUFFICIENT_POPULATION = "insufficient_population"
    #: No trait was held by enough of the reference cohort to profile at all.
    NO_REFERENCE_PROFILE = "no_reference_profile"
    #: The candidate holds fewer than `MIN_LOOKALIKE_TRAITS` of the profiled traits.
    TOO_FEW_TRAITS = "too_few_traits"


@dataclass(frozen=True, slots=True)
class LookalikeRefusal:
    reason: LookalikeRefusalReason
    cohort_id: str
    subject_node_id: str
    evaluated_traits: int
    computed_at: datetime
    detail: str = ""

    @property
    def is_match(self) -> bool:
        return False


@dataclass(frozen=True, slots=True)
class TraitBand:
    """What one trait looks like across the reference cohort.

    Exactly one of `modal` (categorical) and `low`/`high` (numeric interquartile range) is set —
    the kind decides which, and mixing them would be a trait that matches on two different
    questions. `support` is how many members the band was built from, so a profile whose "modal
    industry" is one account out of forty is visible rather than authoritative-looking.
    """

    fact: str
    kind: FactKind
    support: int
    modal: Any = None
    low: int | None = None
    high: int | None = None

    def contains(self, value: Any) -> bool:
        """Integer comparison for a numeric band, exact match for a categorical one.

        `low <= value <= high` — INCLUSIVE at both ends, because the quartile boundary is itself a
        member's value and excluding it would put the account that defines the edge of your best
        customers outside the profile of your best customers.
        """
        if self.kind in (FactKind.NUMBER, FactKind.RATIO):
            if not isinstance(value, int) or isinstance(value, bool):
                return False
            return self.low is not None and self.high is not None and self.low <= value <= self.high
        return value is not None and value == self.modal


@dataclass(frozen=True, slots=True)
class ReferenceProfile:
    """"What our best customers look like" — as bands, one per trait, with the population."""

    cohort_id: str
    node_type: str
    population_size: int
    bands: tuple[TraitBand, ...]
    computed_at: datetime

    @property
    def facts(self) -> tuple[str, ...]:
        return tuple(band.fact for band in self.bands)


@dataclass(frozen=True, slots=True)
class Lookalike:
    """How much a candidate looks like a reference cohort — WITH THE TRAIT NAMES.

    `match_bp` exists to sort by. `matching` and `differing` are what makes the claim checkable,
    and step 5 of doc 04's algorithm is explicit that they are the point: *"matches on industry,
    company size and entry channel; differs on region"* is actionable, `0.87 similar` is not.
    """

    cohort_id: str
    subject_node_id: str
    match_bp: int
    matching: tuple[str, ...]
    differing: tuple[str, ...]
    population_size: int
    computed_at: datetime

    @property
    def is_match(self) -> bool:
        return True

    @property
    def evaluated_traits(self) -> int:
        return len(self.matching) + len(self.differing)

    @property
    def phrase(self) -> str:
        """Deterministic, template-built, and it names the traits before the number."""
        matched = ", ".join(self.matching) if self.matching else "nothing"
        differs = f"; differs on {', '.join(self.differing)}" if self.differing else ""
        return (f"matches on {matched}{differs} "
                f"({len(self.matching)} of {self.evaluated_traits} traits, "
                f"{self.match_bp // 100}% of the profile of {self.population_size} peers)")


def _numeric_band(fact: str, kind: FactKind, values: Mapping[str, int], *, cohort_id: str,
                  eval_time: datetime) -> TraitBand | None:
    """The interquartile range of one numeric trait, through the SAME quantile the position uses.

    `position_from_values` is asked for the position of an arbitrary member and its p25/p75 are
    read off the answer. That is deliberate rather than lazy: `CohortPosition` carries the
    cohort's own distribution precisely so a reader can see what it is being compared against,
    and taking the IQR from it means a lookalike band and a percentile card can never be cut on
    two different quantile rules. The anchor is the lexicographically smallest member so the call
    is reproducible; which member it is cannot change p25 or p75.
    """
    if len(values) < MIN_COHORT_POPULATION:
        return None
    anchor = min(values)
    outcome = position_from_values(metric=fact, cohort_id=cohort_id, values=values,
                                   subject_node_id=anchor, eval_time=eval_time)
    if isinstance(outcome, CohortRefusal):
        return None
    return TraitBand(fact=fact, kind=kind, support=len(values),
                     low=outcome.p25_bp, high=outcome.p75_bp)


def _modal_band(fact: str, kind: FactKind, held: Sequence[Any]) -> TraitBand | None:
    """The most common value of a categorical trait. TIE RULE: the smallest value by its string
    form wins, so a cohort split evenly between two industries profiles the same way on every
    machine and in every build rather than however the dict happened to iterate.
    """
    if len(held) < MIN_COHORT_POPULATION:
        return None
    counts: dict[Any, int] = {}
    for value in held:
        counts[value] = counts.get(value, 0) + 1
    modal = min(counts, key=lambda value: (-counts[value], str(value)))
    return TraitBand(fact=fact, kind=kind, support=counts[modal], modal=modal)


def reference_profile(*, cohort_id: str, node_type: str, member_facts: Mapping[str, Mapping[str, Any]],
                      eval_time: datetime, registry: FactRegistry | None = None,
                      ) -> ReferenceProfile | LookalikeRefusal:
    """U2 steps 1-2, PURE — the reference cohort's profile, or a refusal.

    Built only from REGISTERED facts (`FactRegistry`): an unregistered name would profile on a
    field nobody declared, which is the "silent empty cohort" fault in another coat. A trait held
    by fewer than `MIN_COHORT_POPULATION` members is left out entirely rather than profiled
    thinly, so a band that IS present is one the cohort actually shares.
    """
    at = require_aware(eval_time, "eval_time")
    registry = registry or default_fact_registry()
    population = len(member_facts)
    if population < MIN_COHORT_POPULATION:
        return LookalikeRefusal(
            LookalikeRefusalReason.INSUFFICIENT_POPULATION, cohort_id, cohort_id, 0, at,
            f"{population} members and a reference profile needs {MIN_COHORT_POPULATION}")

    bands: list[TraitBand] = []
    for name in registry.names:
        definition = registry.require(name)
        if name in NON_TRAIT_FACTS or definition.kind not in PROFILABLE_KINDS:
            continue
        if node_type not in definition.node_types:
            continue
        held = [normalise_fact(definition.kind, facts.get(name))
                for facts in member_facts.values()]
        known = [value for value in held if value is not None]
        if definition.kind in (FactKind.NUMBER, FactKind.RATIO):
            numeric = {node: normalise_fact(definition.kind, facts.get(name))
                       for node, facts in member_facts.items()}
            band = _numeric_band(name, definition.kind,
                                 {node: value for node, value in numeric.items()
                                  if isinstance(value, int) and not isinstance(value, bool)},
                                 cohort_id=cohort_id, eval_time=at)
        else:
            band = _modal_band(name, definition.kind, known)
        if band is not None:
            bands.append(band)

    if not bands:
        return LookalikeRefusal(
            LookalikeRefusalReason.NO_REFERENCE_PROFILE, cohort_id, cohort_id, 0, at,
            "no trait is held by enough of this cohort to describe it")
    return ReferenceProfile(cohort_id=cohort_id, node_type=node_type, population_size=population,
                            bands=tuple(bands), computed_at=at)


def lookalike(profile: ReferenceProfile, *, subject_node_id: str, facts: Mapping[str, Any],
              eval_time: datetime, registry: FactRegistry | None = None,
              ) -> Lookalike | LookalikeRefusal:
    """U2 steps 3-5, PURE. How many of the candidate's traits fall inside the profile.

    ONLY TRAITS THE CANDIDATE ACTUALLY HOLDS ARE EVALUATED. An absent trait is not a mismatch:
    counting it as one would make a sparsely-known node look unlike your best customers because
    of what nobody recorded, which is the fabricated-zero fault the sampler refuses for
    `deal.value`. It is also why the count of evaluated traits travels with the answer — `2 of 2`
    and `2 of 11` are the same `match_bp` and completely different claims.
    """
    at = require_aware(eval_time, "eval_time")
    registry = registry or default_fact_registry()
    matching: list[str] = []
    differing: list[str] = []
    for band in profile.bands:
        definition = registry.get(band.fact)
        value = normalise_fact(definition.kind if definition else band.kind, facts.get(band.fact))
        if value is None:
            continue
        (matching if band.contains(value) else differing).append(band.fact)

    evaluated = len(matching) + len(differing)
    if evaluated < MIN_LOOKALIKE_TRAITS:
        return LookalikeRefusal(
            LookalikeRefusalReason.TOO_FEW_TRAITS, profile.cohort_id, subject_node_id, evaluated,
            at, f"{evaluated} of the profile's {len(profile.bands)} traits are known for this "
                f"node and a comparison needs {MIN_LOOKALIKE_TRAITS}")
    return Lookalike(cohort_id=profile.cohort_id, subject_node_id=subject_node_id,
                     match_bp=len(matching) * 10_000 // evaluated,
                     matching=tuple(matching), differing=tuple(differing),
                     population_size=profile.population_size, computed_at=at)


def lookalike_fact_value(outcome: Lookalike | LookalikeRefusal) -> dict[str, Any]:
    """The JSON body. Refusals are written for the reason positions' are: self-correction.

    `computed_at` is absent for the reason `position_fact_value` states: it is the sweep instant,
    so carrying it made an unchanged lookalike a DIFFERENT jsonb value on every drain, and
    `publish_derived_fact` can only recognise "nothing has changed" if nothing has changed.
    """
    if isinstance(outcome, LookalikeRefusal):
        return {"cohort_id": outcome.cohort_id, "refused": outcome.reason.value,
                "evaluated_traits": outcome.evaluated_traits, "detail": outcome.detail}
    return {"cohort_id": outcome.cohort_id, "match_bp": outcome.match_bp,
            "matching": list(outcome.matching), "differing": list(outcome.differing),
            "evaluated_traits": outcome.evaluated_traits,
            "population_size": outcome.population_size, "phrase": outcome.phrase}


# =================================================================================================
# THE SWEEP — the real request path. `context/runner.process_pending` calls this.
# =================================================================================================

@dataclass(frozen=True, slots=True)
class ComparisonSweep:
    """What one drain's comparison pass did, including what it refused and where it stopped.

    `written` is separate from `positions` + `lookalikes` because `publish_derived_fact` writes
    NOTHING when the open row already holds the same value. A pass that reported "4,000 facts"
    where 3,990 of them were re-confirmations is the accounting that made the old writer's
    amplification invisible; the two numbers together say how much of a sweep was new.

    `budget_exhausted` is still carried, and it is still the runner's to surface — see the note in
    `refresh_comparison_facts` about what it now means, which is different from what it meant when
    the truncation was permanent.
    """

    positions: int = 0
    lookalikes: int = 0
    refusals: int = 0
    pairs: int = 0
    budget_exhausted: bool = False
    written: int = 0

    @property
    def facts(self) -> int:
        return self.positions + self.lookalikes


def _write_comparison_fact(conn, *, org_id: str, node_id: str, field_name: str,
                           value: Mapping[str, Any], now: datetime) -> PublishAction:
    """One published comparison, through `publish.publish_derived_fact` — THE shared L2.4 writer.

    WHAT WAS HERE AND WHY IT WAS WRONG. This module had its own copy of an upsert whose conflict
    clause ended `valid_from = excluded.valid_from`, one of four copies in the wave. That single
    assignment MOVES the window of a row that already exists, so a position published in March and
    swept again in September read back as `[September, inf)` and `read_graph(as_of=March)`
    returned nothing — about a fact GeniOS itself published in March. The as-of reader shipped in
    the same wave is what turns that from a harmless-looking recompute into a correctness bug, and
    doc 02's acceptance row ("replaying a March decision against as_of=March reproduces its
    inputs") failed for exactly the facts L2.4.5 exists to produce.

    The bounding property the old docstring defended is not weakened, it is made honest. The
    version id is period-keyed at ISO-week grain, so a value that never changes is ONE row for the
    life of the tenant (the sweep re-confirming it writes nothing at all), and a value that changes
    is at most one row per ISO week in which it actually changed — never one per sweep. That is a
    tighter bound than the old "one row per (node, field)" was, because the old one bought its
    size by being wrong about every instant except the last.

    No new table, so nothing is added to `api/account_routes._ORG_SCOPED_TABLES`: `graph_facts` is
    already on it and these rows are erased with the tenant by the entry already there.
    """
    return publish_derived_fact(
        conn, org_id=org_id, subject_node_id=node_id, field=field_name, value=dict(value),
        eval_time=now, value_type=COMPARISON_VALUE_TYPE, visibility_scope=POSITION_FACT_SCOPE,
        version_prefix=VERSION_PREFIX).action


def _compared_pairs(engine, org_id: str, at: datetime, limit: int, *,
                    stale_after_periods: int = STALE_AFTER_PERIODS) -> list[tuple[str, str]]:
    """Every (cohort, metric) pair with at least the floor's worth of RECENT readings, in
    staleness order, capped — see `_COMPARED_PAIRS_SQL` for what the three order keys are for."""
    since = staleness_horizon(at, DEFAULT_METRIC_GRAIN, stale_after_periods)
    with engine.connect() as conn:
        rows = conn.execute(_COMPARED_PAIRS_SQL,
                            {"o": org_id, "at": at, "since": since,
                             "floor": MIN_COHORT_POPULATION, "n": limit,
                             "position_prefix": POSITION_FACT_PREFIX}).all()
    return [(str(row.cohort_id), str(row.metric)) for row in rows]


#: Every open derived fact this module owns for one org, as (node, field) -> when it began being
#: true. One statement rather than a lookup per candidate: the publication loops below need the
#: whole map to SORT by it, and 5,000 nodes' worth of round trips is the O(nodes) shape
#: `PERFORMANCE_HARDENING.md` already names as the reason L3 took thirty minutes.
_OPEN_DERIVED_SQL = text(
    "select subject_node_id as node_id, field, valid_from from graph_facts "
    "where org_id = :o and valid_to is null and field like :p")


def _published_at(engine, org_id: str, field_prefix: str) -> dict[tuple[str, str], datetime]:
    with engine.connect() as conn:
        rows = conn.execute(_OPEN_DERIVED_SQL, {"o": org_id, "p": f"{field_prefix}%"}).all()
    return {(str(row.node_id), str(row.field)): row.valid_from for row in rows}


#: The instant a NEVER-PUBLISHED fact sorts at. `datetime.min` in UTC, so "no row" is strictly
#: older than every real `valid_from` and needs no second sort key to say so. A constant, not a
#: clock — `datetime.min` is a property of the type.
_NEVER = datetime.min.replace(tzinfo=timezone.utc)


def _publication_order(candidates: Iterable[tuple[str, str]],
                       published_at: Mapping[tuple[str, str], datetime],
                       ) -> list[tuple[str, str]]:
    """(node, field) pairs, STALEST FIRST — the other half of the dark-tail fix.

    `_COMPARED_PAIRS_SQL` decides which cohorts are compared; this decides which of the resulting
    nodes are actually published when there are more of them than `position_limit`. Sorting by
    node id was stable across sweeps, so on an org above budget the same nodes were dropped every
    drain and could never receive a position — the tail was permanent, not deferred.

    A node with no open row sorts at `_NEVER`, so it outranks every node that already has one, and
    the never-positioned set therefore drains monotonically. The (node, field) tie-break keeps the
    answer deterministic for two facts published in the same instant, which is the ordinary case
    on the first sweep of a tenant.
    """
    return sorted(candidates, key=lambda key: (published_at.get(key, _NEVER), key))


def reference_cohorts(definitions: Iterable[CohortDefinition]) -> tuple[CohortDefinition, ...]:
    """The shipped "best customers" populations — the top quartile slot of each system family.

    Selected by NAME because `cohort._system_cohort_id` hashes the slot into an opaque id and the
    name is the only public handle on it (recorded as a spec gap). System-owned only: an authored
    cohort that happens to be called "top quartile" is somebody's own definition, and turning it
    into a reference population without being asked would be this module choosing what "best"
    means for a tenant.
    """
    return tuple(d for d in definitions
                 if d.created_by == SYSTEM_AUTHOR and d.name.strip().lower().endswith(
                     TOP_SLOT_SUFFIX))


def refresh_comparison_facts(store, org_id: str, *, eval_time: datetime,
                             divisions: int = DEFAULT_DIVISIONS,
                             pair_limit: int = MAX_COMPARED_PAIRS_PER_SWEEP,
                             position_limit: int = MAX_POSITION_FACTS_PER_SWEEP,
                             lookalike_limit: int = MAX_LOOKALIKE_FACTS_PER_SWEEP,
                             registry: FactRegistry | None = None,
                             metric_registry: MetricRegistry | None = None) -> ComparisonSweep:
    """THE ONE FUNCTION THE DRAIN CALLS. Deterministic, no model, no clock.

    U1 first: every (cohort, metric) pair the tenant has readings for is positioned, and each node
    gets ONE published comparison per metric — `most_specific` decides which cohort, so a node in
    five cohorts produces one row rather than five that a reader has to choose between.

    U2 second, and only against the shipped top-quartile populations: profile once per reference
    cohort, then score the candidates of that node type that are NOT already in it. A member of
    the reference cohort is skipped because "your best customer looks like your best customers"
    is not a finding.

    NEVER FATAL upstream and bounded here: `runner.process_pending` wraps the call, and both
    passes stop at their budget with `budget_exhausted` set rather than silently truncating.

    AND THE TRUNCATION IS NOW A DEFERRAL RATHER THAN A DELETION. Every budget in this function
    used to cut a list ordered by id, which is stable across sweeps: an org above budget lost the
    SAME nodes on every drain, for ever, so "work not done this sweep is done by the next one" was
    false for exactly the nodes it was written about. Both passes are now ordered by staleness —
    the pairs in `_COMPARED_PAIRS_SQL`, the publications in `_publication_order` — and a node with
    no open fact sorts before every node that has one, so the unpositioned set drains
    monotonically and `budget_exhausted` means "there is more to do next drain" rather than "there
    is a tail nothing will ever reach". Surfacing that flag out of the drain is the runner's.
    """
    at = require_aware(eval_time, "eval_time")
    registry = registry or default_fact_registry()
    engine = getattr(store, "engine", store)

    pairs = _compared_pairs(engine, org_id, at, pair_limit)
    # node -> metric -> every cohort's answer, so `most_specific` sees all of them at once.
    by_node: dict[str, dict[str, list[PositionedReading | CohortRefusal]]] = {}
    for cohort_id, metric in pairs:
        readings = cohort_readings(store, org_id=org_id, cohort_id=cohort_id, metric=metric,
                                   eval_time=at, registry=metric_registry)
        for node_id in sorted(readings.values):
            outcome = compare_reading(metric=metric, cohort_id=cohort_id, values=readings.values,
                                      subject_node_id=node_id, eval_time=at,
                                      unknown=readings.unknown, divisions=divisions,
                                      unit=readings.unit)
            by_node.setdefault(node_id, {}).setdefault(metric, []).append(outcome)

    position_age = _published_at(engine, org_id, POSITION_FACT_PREFIX)
    chosen_by_key = {(node_id, position_fact_field(metric)): most_specific(outcomes)
                     for node_id, metrics in by_node.items()
                     for metric, outcomes in metrics.items()}
    published: list[tuple[str, str, dict[str, Any], bool]] = []
    exhausted = False
    for node_id, field_name in _publication_order(chosen_by_key, position_age):
        if len(published) >= position_limit:
            exhausted = True
            break
        chosen = chosen_by_key[(node_id, field_name)]
        if chosen is None:
            continue
        published.append((node_id, field_name, position_fact_value(chosen),
                          isinstance(chosen, CohortRefusal)))

    matches: list[tuple[str, str, dict[str, Any], bool]] = []
    lookalike_age = _published_at(engine, org_id, LOOKALIKE_FACT_PREFIX)
    facts_by_type = load_node_facts(engine, org_id, node_types=COHORT_NODE_TYPES, eval_time=at,
                                    registry=registry)
    if any(facts_by_type.values()):
        for definition in reference_cohorts(load_definitions(engine, org_id, registry=registry)):
            candidates = facts_by_type.get(definition.node_type, {})
            if not candidates:
                continue
            member_ids = _open_members(engine, org_id, definition.cohort_id, at)
            profile = reference_profile(
                cohort_id=definition.cohort_id, node_type=definition.node_type,
                member_facts={node: facts for node, facts in candidates.items()
                              if node in member_ids},
                eval_time=at, registry=registry)
            if isinstance(profile, LookalikeRefusal):
                continue
            # Same staleness order as the position pass, for the same reason: `sorted(candidates)`
            # is stable across sweeps, so on an org above `lookalike_limit` the tail of the
            # candidate list was permanently unscored rather than deferred.
            field_name = lookalike_fact_field(definition.cohort_id)
            outside = [(node_id, field_name) for node_id in candidates
                       if node_id not in member_ids]
            for node_id, _ in _publication_order(outside, lookalike_age):
                if len(matches) >= lookalike_limit:
                    exhausted = True
                    break
                outcome = lookalike(profile, subject_node_id=node_id, facts=candidates[node_id],
                                    eval_time=at, registry=registry)
                if isinstance(outcome, LookalikeRefusal):
                    continue          # nothing to publish and nothing stale to retract
                matches.append((node_id, field_name, lookalike_fact_value(outcome), False))
            if exhausted:
                break

    if not published and not matches:
        return ComparisonSweep(pairs=len(pairs), budget_exhausted=exhausted)
    refused = 0
    wrote = 0
    # ONE transaction for the whole pass, and it is the transaction `publish_derived_fact` needs:
    # it selects the open row `for update` before closing it, so the close and the insert that
    # replaces it commit together and a sweep cannot retire the old answer and then fail to write
    # the new one.
    with engine.begin() as conn:
        for node_id, field_name, value, is_refusal in (*published, *matches):
            action = _write_comparison_fact(conn, org_id=org_id, node_id=node_id,
                                            field_name=field_name, value=value, now=at)
            refused += 1 if is_refusal else 0
            wrote += 0 if action is PublishAction.UNCHANGED else 1
    return ComparisonSweep(positions=len(published), lookalikes=len(matches), refusals=refused,
                           pairs=len(pairs), budget_exhausted=exhausted, written=wrote)


def _open_members(store, org_id: str, cohort_id: str, at: datetime) -> frozenset[str]:
    """Who was in the cohort at that instant. One statement, org-scoped, parameterised."""
    with getattr(store, "engine", store).connect() as conn:
        rows = conn.execute(_MEMBERS_AT_SQL, {"o": org_id, "c": cohort_id, "at": at}).all()
    return frozenset(str(row.node_id) for row in rows)


__all__ = [
    "COMPARISON_VALUE_TYPE", "DEFAULT_DIVISIONS", "DEFAULT_METRIC_GRAIN",
    "LOOKALIKE_FACT_PREFIX", "MAX_COMPARED_PAIRS_PER_SWEEP", "MAX_LOOKALIKE_FACTS_PER_SWEEP",
    "MAX_POSITION_FACTS_PER_SWEEP", "MIN_LOOKALIKE_TRAITS", "NON_TRAIT_FACTS",
    "POSITION_FACT_PREFIX", "POSITION_FACT_SCOPE", "PROFILABLE_KINDS", "STALE_AFTER_PERIODS",
    "TOP_SLOT_SUFFIX", "VERSION_PREFIX",
    "ComparisonSweep", "Lookalike", "LookalikeRefusal", "LookalikeRefusalReason",
    "PopulationReadings", "PositionedReading", "ReferenceProfile", "TraitBand",
    "cohort_readings", "compare_in_cohort", "compare_reading", "describe_position",
    "lookalike", "lookalike_fact_field", "lookalike_fact_value", "metric_grain", "most_specific",
    "ordinal", "position_fact_field", "position_fact_value", "publishable_distribution",
    "reference_cohorts", "reference_profile", "refresh_comparison_facts", "staleness_horizon",
]
