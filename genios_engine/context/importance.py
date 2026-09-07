"""L2.7.4-U1 · BLG-18 steps 2 through 6 — the situation importance COMPOSER.

**Step 1 already exists and is NOT re-done here.** `situation_bso.gather_l1_signals` reads Layer
1's own score off `qualified_signals` and takes the MAX over the situation's live scored signals;
`build_business_situation` records which of the four sources it came from in
`metadata['importance_source']`. That is the base. This module takes it as a parameter and never
recomputes it — two layers deriving one number is how two layers end up disagreeing about one
situation, and the max-not-mean argument is already made, and tested, one file over.

**What was missing, and what this is.** Steps 2..6 of BLG-18 did not exist anywhere:
corroboration, the six L2-only modifiers, the coverage penalty, the clamp, and the stored
component record. Without them a situation's importance is exactly its loudest signal's
importance — which makes Layer 2 a pass-through, and makes the whole analytic stratum (trend,
cohort position, anomaly, dependency) something the product computes and never uses. Step 3 IS
the justification for L2.4: those four facts are things *no individual signal could know*.

**Why a module of its own rather than more of `situations.py`.** Six modifiers, their bulk
readers, a cap, a penalty, a clamp and an auditable component record is a unit with its own
shape; `situations.py` is the confidence vector's home and is being edited in parallel for its
sixth axis. The dependency points ONE WAY — `situations.py` imports this, this imports nothing
from `situations.py` — so there is no import cycle to unpick later.

THE FOUR DOCTRINES, as they land here.

* **The model describes, never scores.** There is no model in this file, no prompt, and nothing
  that could grow one: every term is an integer read out of a row somebody else wrote.
* **Integer basis points.** No float, no `round()`, no `statistics`. The coverage penalty is
  `* 8 // 10` because that is what doc 07 says, and `//` on ints is the only division here.
* **No claim without a receipt.** Every modifier that fires records WHICH fact fired it — the
  `graph_facts.fact_version_id`, the metric, the subject node, the numbers it was judged on. A
  reader asking "why is this a 7400" gets the arithmetic and the row ids, from stored data, with
  no recomputation. A modifier that did NOT fire records why not, in the same list, so silence
  and absence are distinguishable (see `ModifierTerm.fired`).
* **No clocks in logic.** `eval_time` is a parameter of the composer AND of every reader. Nothing
  in this module calls a clock, in Python or in SQL.

**AND ONE MORE, WHICH IS THIS FILE'S OWN SCAR TISSUE: the record must be CONTENT-STABLE.** The
component record reaches `BusinessSituationObject.metadata`, which `to_semantic_dict` hashes into
the expertise package's content address. A record carrying the sweep instant — or anything
derived from it, such as "this evidence is 96 days old" — mints a brand-new ~238 kB package row
for every situation on every sweep whether or not anything changed. That mechanism put 995 MB on
one tenant's database and took the project read-only. So the staleness term stores the evidence
DATE and the threshold, never the age; and `eval_time` appears nowhere in `as_record()`.

**Rule 11 (bounded, nameable raises).** Corroboration is capped at +1500 and its evidence is the
named additional source systems. The step-3 modifiers are capped at +4000 combined — doc 07's
own mitigation for "modifiers dominate the base" — and every one of them names the fact it read.
The base alone can still reach 10000.

**WHAT THIS MODULE DELIBERATELY DOES NOT PUBLISH.** `CohortPosition` carries the cohort's raw
p25/p50/p75, and `comparator.publishable_distribution` is the gate every exit goes through
because publishing an order statistic over a small population discloses named peers' exact
readings. No component here carries a distribution — the cohort term keeps the SUBJECT's own
percentile, its band, its population size and its cohort id, and nothing about the other members.
The same line is why the dependency term reads `derived.dependency.blocked_count` (one integer
about its own subject, ORG-visible by that module's own reasoning) and never
`derived.dependency.chains`, which embeds third parties' verbatim sentences and is
`participants`-scoped. A situation card is not the place to republish a thread.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Iterable, Mapping, Sequence

from sqlalchemy import text

from genios_engine.contracts.analytic import MIN_COHORT_POPULATION, CohortBand
from genios_engine.contracts.validators import require_aware
from genios_engine.platform.logging import get_logger

_log = get_logger("genios.context.importance")

# =================================================================================================
# THE VERSIONED WEIGHT TABLE — doc 07 L2.7.4-U1, and nothing invented beside it
# =================================================================================================

#: Stamped on every composed number. Doc 07's failure-mode table names the reason: after a weight
#: below moves, a historical importance is not comparable to a new one, and without a version on
#: the row nobody can tell which formula produced which score. Bump it when ANY weight, floor or
#: ordering in this file changes.
IMPORTANCE_VERSION = "l2-situation-importance.v1"

#: 0..10000, the scale every score in this codebase is in. Spelled rather than imported from
#: `capture/esqe/importance.BP_MAX` so Layer 2 does not take a hard dependency on a Layer 1 module
#: for one integer; `test_importance.py` pins the two together.
BP_MIN = 0
BP_MAX = 10_000

#: Step 2. `(distinct_sources - 1) * 500`, capped at 1500 — so a second source is worth +500 and a
#: fourth buys nothing more. Bounded and nameable: the additional SOURCE SYSTEMS are the
#: independent evidence, and they are listed in the component record.
CORROBORATION_PER_EXTRA_SOURCE_BP = 500
CORROBORATION_CAP_BP = 1_500

#: Step 3's weights, exactly as doc 07 states them.
TREND_BP = 1_000
COHORT_BP = 1_000
ANOMALY_BP = 800
DEPENDENCY_PER_BLOCKED_BP = 200
DEPENDENCY_MAX_BLOCKED = 5
CONFLICT_BP = 700

#: `signal_conflicts.resolution` for a disagreement nobody settled — modifier 3e's whole test. The
#: other two members of that closed vocabulary HAVE an answer. Spelled rather than imported for the
#: dependency reason the module docstring gives; `test_importance.py` pins it against the check
#: constraint migration 0087 puts on the column.
UNRESOLVED_RESOLUTION = "unresolved_surface_both"

#: How many conflict ids one term names. A receipt, not the table.
MAX_NAMED_CONFLICTS = 5
STALENESS_BP = -1_500

#: Doc 07's mitigation for "modifiers dominate the base": the POSITIVE step-3 terms may add at
#: most +4000 between them. They sum to 4500 when all five fire, so the cap genuinely bites.
#:
#: THE CAP IS POSITIVE-ONLY, and the staleness discount is outside it. Capping a negative term
#: would mean a situation that fired four modifiers got LESS of a staleness discount than one that
#: fired none — the discount would be spent on the cap — and a discount for evidence nobody has
#: refreshed in three months is exactly the term that must not be negotiable.
MODIFIER_CAP_BP = 4_000

#: Modifier 3a's floor, from doc 07: a trend the computer itself is under half-confident about
#: must not add a tenth of the whole scale. `contracts/analytic.MAX_TREND_CONFIDENCE_BP` is 8000,
#: so this floor sits at 62.5% of the reachable range — meetable by a clean four-point series with
#: full coverage (~5839 bp), unreachable by a gappy or noisy one. `test_importance.py` proves that
#: against the REAL `compute_trend`, because a threshold nobody's data can meet is a dead modifier
#: and dead rules are how 15 of Layer 1's 21 deep sales rules never fired.
MIN_TREND_CONFIDENCE_BP = 5_000

#: Modifier 3f's window. 90 days of silence on a situation is doc 07's number.
STALENESS_DAYS = 90

#: Step 4. `importance_bp * 8 // 10` — an honest discount for what we cannot see, applied to the
#: subtotal, integer division, no rounding rule needed.
COVERAGE_PENALTY_NUMERATOR = 8
COVERAGE_PENALTY_DENOMINATOR = 10

#: The guard doc 07 makes a HARD RULE. If more than 90% of the org's incoming signals still carry
#: exactly the neutral 5000, Layer 1's scorer is not live for this tenant and a spread composed on
#: top of that base is a spread this system invented. A fake distribution is worse than a flat one
#: because it looks like it works.
FLAT_BASE_BP = 5_000
FLAT_SUPPLY_LIMIT_BP = 9_000        # > 90% of the supply at exactly 5000
L1_NOT_ACTIVE = "L1_IMPORTANCE_NOT_ACTIVE"


# =================================================================================================
# WHICH END OF A COHORT IS THE BAD END — the register doc 07 assumes and the codebase lacks
# =================================================================================================

class MetricPolarity(str, Enum):
    """Which direction of a metric is the direction that costs the customer something.

    Doc 07's modifier 3b is two lines — "bottom decile of its cohort +1000" and "top decile on a
    RISK metric +1000" — and there is no risk-metric register anywhere in this codebase. There are
    two honest ways to get one and only one of them is available: derive it from the metric's own
    definition, or declare it. `MetricSpec` (L2.4.2's `sampler.TRENDED_METRICS`) carries no
    polarity field, and that file belongs to another unit, so it is declared HERE — from each
    metric's own registered `question`, which states the direction of harm in words.
    """

    #: A high reading is the bad reading. These ARE the risk metrics of doc 07's second line:
    #: "how long since we spoke", "how long they take to reply", "how much we owe them", "how long
    #: this deal has sat", "how many tickets", "how old the backlog is".
    HIGHER_IS_WORSE = "higher_is_worse"
    #: A low reading is the bad reading — engagement, breadth, deal value. Doc 07's first line
    #: ("bottom decile") is this polarity's extreme.
    LOWER_IS_WORSE = "lower_is_worse"


#: THE REGISTER. Keyed by `sampler.TrendedMetric`'s VALUES, spelled as literals with their
#: provenance rather than imported, for the reason `situations.ANALYTIC_FULL_*` gives: a confidence
#: axis (or here, an importance modifier) should not pull `context/analytic/` — a much heavier
#: module — into its import graph for a lookup table. `test_importance.py` pins this mapping
#: against `TRENDED_METRICS` in both directions, so a thirteenth registered metric fails the suite
#: instead of silently landing here as "polarity unknown, modifier never fires".
#:
#: The quoted question beside each is the one `sampler.TRENDED_METRICS` registers for it; the
#: polarity is read straight off it and is not a second opinion.
METRIC_POLARITY: Mapping[str, MetricPolarity] = {
    # "is engagement with this account declining?" — less is worse.
    "engagement.touch_count_28d": MetricPolarity.LOWER_IS_WORSE,
    # "have THEY gone quiet?" — less is worse.
    "engagement.inbound_count_28d": MetricPolarity.LOWER_IS_WORSE,
    # "have WE gone quiet on an account we said we were working?" — less is worse.
    "engagement.outbound_count_28d": MetricPolarity.LOWER_IS_WORSE,
    # "is this relationship going cold?" — MORE days since contact is worse.
    "engagement.days_since_contact": MetricPolarity.HIGHER_IS_WORSE,
    # "are they taking longer to answer than they used to?" — more latency is worse.
    "relationship.response_latency_hours": MetricPolarity.HIGHER_IS_WORSE,
    # "is this account single-threaded on one champion?" — fewer contacts is worse.
    "account.contact_breadth": MetricPolarity.LOWER_IS_WORSE,
    # "how much have we promised and not delivered?" — more open promises is worse.
    "account.open_commitment_count": MetricPolarity.HIGHER_IS_WORSE,
    # "is our reliability with this account getting worse?" — more overdue is worse.
    "account.overdue_commitment_count": MetricPolarity.HIGHER_IS_WORSE,
    # "is this deal quietly stalling in its current stage?" — more days in stage is worse.
    "deal.stage_age_days": MetricPolarity.HIGHER_IS_WORSE,
    # "is the deal being negotiated down?" — a smaller deal is worse.
    "deal.value_minor_units": MetricPolarity.LOWER_IS_WORSE,
    # "is this customer asking for help more than they used to?" — more tickets is worse.
    "support.ticket_count_28d": MetricPolarity.HIGHER_IS_WORSE,
    # "is our unanswered-request pile getting older?" — an older backlog is worse.
    "support.backlog_age_p50_days": MetricPolarity.HIGHER_IS_WORSE,
}

#: Doc 07's "risk metric", derived rather than typed twice.
RISK_METRICS: frozenset[str] = frozenset(
    m for m, p in METRIC_POLARITY.items() if p is MetricPolarity.HIGHER_IS_WORSE)


def worst_band(polarity: MetricPolarity, *, divisions: int) -> CohortBand:
    """The band a subject is in when it is at the BAD extreme of its cohort, in `divisions` scheme.

    **THE DECIMAL-THAT-IS-NOT-A-DECILE DECISION.** Doc 07 says "bottom decile", and since D8 the
    band scheme NARROWS: nearest rank cannot express a decile unless `population_size > 10`, so
    `CohortPosition` publishes QUARTILES below n=11 and the worst member of a five-member cohort
    is `Q1`, not `D1`. A modifier written as `band is CohortBand.D1` would therefore be dead on
    every small cohort — and small cohorts are most cohorts, because `most_specific` deliberately
    publishes the SMALLEST population. That is the dead-rule failure mode with a new face.

    So "bottom decile" is read as **the worst band the population can actually express**: D1 where
    deciles are expressible (n >= 11), Q1 below that; D10 / Q4 at the top for a risk metric. The
    claim is weaker on a small cohort and the record says so — the term carries `band`,
    `population_size` and `divisions`, so a reader sees "worst quartile of 6", never a decile the
    arithmetic could not have produced. The alternative — award nothing below n=11 — deletes the
    position rather than the overclaim, which is exactly what `expressible_divisions` refused to do
    one layer down, and the floor that protects the claim from meaninglessness (`population >= 5`,
    doc 07's own mitigation) is already enforced by V-2.
    """
    if polarity is MetricPolarity.LOWER_IS_WORSE:
        return CohortBand(f"{'Q' if divisions == 4 else 'D'}1")
    return CohortBand(f"{'Q' if divisions == 4 else 'D'}{divisions}")


# =================================================================================================
# THE INPUTS — one typed bundle, filled by the readers below or by a caller in a test
# =================================================================================================

@dataclass(frozen=True, slots=True)
class ConstituentSignal:
    """One piece of evidence the situation is built from, as step 2 needs to see it.

    `source_system` is the whole point: corroboration counts DISTINCT SOURCE SYSTEMS, because two
    mails in one thread are one source agreeing with itself, while a signed PDF and a calendar
    invite saying the same thing are independent. `id` is carried so the record can name what was
    counted — a raise nobody can trace back to rows is exactly the unbounded, unnameable raise
    Rule 11 refuses.
    """

    id: str
    source_system: str | None = None
    #: Layer 1's score for this signal, when it has one. The composer does NOT use it (the base is
    #: given), but `assess_l1_supply` reads a population of them and the field is here so a caller
    #: assembling constituents has one shape to fill, not two.
    importance_bp: int | None = None


@dataclass(frozen=True, slots=True)
class TrendInput:
    """A `derived.trend.<metric>` fact, in the shape modifier 3a judges.

    The field NAMES are `Trend`'s own (`trend_confidence_bp`, `point_count`, `direction`) rather
    than renamed here, because `situations.analytic_score` — the sixth confidence axis — reads
    those names off "the comparisons an importance number LEANED ON". `ComposedImportance.
    leaned_on()` hands these straight over, so the axis and the modifier can never disagree about
    which comparison was used.
    """

    metric: str
    subject_node_id: str
    direction: str
    trend_confidence_bp: int
    point_count: int = 0
    #: `graph_facts.fact_version_id` — the receipt. "Which trend?" is answerable by primary key.
    fact_version_id: str | None = None


@dataclass(frozen=True, slots=True)
class CohortInput:
    """A `derived.cohort_position.<metric>` fact, minus the distribution.

    `p25_bp` / `p50_bp` / `p75_bp` are ON the stored fact and are deliberately NOT read into this
    type: they are three named peers' literal readings, and the only sanctioned exit for them is
    `comparator.publishable_distribution`. A component record that carried them would be a fourth
    exit, on a card, with no gate in front of it.
    """

    metric: str
    subject_node_id: str
    percentile_bp: int
    population_size: int
    cohort_id: str
    #: The band AS STORED. The composer recomputes the expressible band from `percentile_bp` and
    #: `population_size` anyway (see `_cohort_term`), so a row written by an older, un-narrowed
    #: writer cannot smuggle a decile claim into a cohort of six.
    band: str | None = None
    fact_version_id: str | None = None


@dataclass(frozen=True, slots=True)
class AnomalyInput:
    """A `derived.anomaly.<metric>` fact. `flagged` is the detector's own conjunction (z_like >
    30000 AND deviation > 2000) — this module re-decides nothing about it and only reads it."""

    metric: str
    subject_node_id: str
    flagged: bool
    periods_used: int = 0
    z_like_bp: int | None = None
    direction: str | None = None
    fact_version_id: str | None = None


@dataclass(frozen=True, slots=True)
class DependencyInput:
    """A `derived.dependency.blocked_count` fact: how many items wait on this subject.

    One integer about its own subject, which is precisely why `correlation_dependency` files this
    field as ORG-visible while the chains beside it are `participants`. The chains name third
    parties and quote their sentences; this does not.
    """

    subject_node_id: str
    blocked_count: int
    fact_version_id: str | None = None


@dataclass(frozen=True, slots=True)
class ConflictInput:
    """One `signal_conflicts` row that is attached to this situation's own signals.

    **MATERIAL, by what test.** Doc 07 says "an unresolved MATERIAL conflict" and defines neither
    word. Material here is a conjunction of two checks, both of which are rows rather than
    judgements:

    * **Unresolved** — `resolution = 'unresolved_surface_both'`, the store's own closed
      vocabulary. The other two verdicts (`resolved_by_authority`, `resolved_by_recency`) HAVE an
      answer; acting on one of those is not acting on a contradiction, and raising importance for
      a disagreement we already settled would charge the customer for our own resolution logic.
    * **Load-bearing for THIS situation** — the conflict's `signal_id` is one of the situation's
      constituent qualified signals. Without this prong every unresolved disagreement anywhere in
      the tenant would raise every situation in it, which is a raise with no nameable evidence.

    The rejected alternative was field-based materiality: intersect `signal_conflicts.field` with
    the situation type's `domain_spec.expected_fields`. Both are dotted paths, but they are
    different registers — L1 claims are things like `contract.value`, the domain spec expects
    `deal.amount` / `thread.ball_in_court` — so the join would match almost nothing and the
    modifier would be dead while looking rigorous. That is the 9%-coverage `ball_in_court` failure
    exactly, and it is not worth repeating for a word doc 07 left undefined.
    """

    conflict_id: str
    field: str
    signal_id: str
    resolution: str


@dataclass(frozen=True, slots=True)
class ModifierInputs:
    """Everything step 3 and step 4 read, for ONE situation. Filled by `load_modifier_inputs`.

    Every collection defaults to empty and every scalar to the tri-state `None`, so a caller that
    knows nothing produces a composition with no modifiers rather than one with false ones.
    """

    trends: tuple[TrendInput, ...] = ()
    cohort_positions: tuple[CohortInput, ...] = ()
    anomalies: tuple[AnomalyInput, ...] = ()
    dependencies: tuple[DependencyInput, ...] = ()
    conflicts: tuple[ConflictInput, ...] = ()
    #: Modifier 3f's input. **MEASURED ON THE SITUATION, NOT ON THE SUBJECT** — the newest evidence
    #: correlated onto THIS situation (`context_situations.last_seen_at`). The two differ and the
    #: difference decides the modifier: a company node is busy with forty other threads while the
    #: renewal this situation is about has been silent since June, and reading the SUBJECT's newest
    #: evidence would let that unrelated traffic keep a dead situation at full weight. That is the
    #: "it told me about a contract I cancelled last week" failure with a different mechanism.
    newest_evidence_at: datetime | None = None
    #: Step 4's input, TRI-STATE. `False` discounts; `None` means no coverage row for this domain
    #: and must NOT discount — absence of a coverage declaration is not evidence of missing
    #: coverage, and the same tri-state discipline guards `QualifiedEnterpriseSignal.
    #: coverage_ready` and `MetricPoint.coverage_ready` one layer down.
    coverage_ready: bool | None = None
    #: Which domain the coverage answer above was read for. Recorded, never re-derived.
    coverage_domain: str | None = None


@dataclass(frozen=True, slots=True)
class ImportanceBase:
    """Step 1's answer, as `situation_bso` already produced it. Never recomputed here."""

    importance_bp: int
    #: `situation_bso`'s own vocabulary: l1_qualified_signals | l1_unscored | l1_all_retired |
    #: default. Carried through so the record says whether the base was MEASURED or DEFAULTED —
    #: the state the old constant made indistinguishable for 193 of 223 signals.
    source: str
    #: The `qualified_signals` row the base came from, when there was one. A POINTER, not a copy:
    #: Layer 1's own components ("why is this an 8100") live on that row and re-copying them here
    #: would be a second thing to keep in step after ALG-17's weights move.
    signal_id: str | None = None
    #: ALG-17's version for that signal. Same argument.
    version: str | None = None


# =================================================================================================
# THE RECORD — step 6, and the row the gate measures at 100%
# =================================================================================================

class ModifierName(str, Enum):
    """The six, closed. A renderer branching on the word cannot meet a seventh."""

    TREND = "trend"
    COHORT_POSITION = "cohort_position"
    ANOMALY = "anomaly"
    DEPENDENCY = "dependency"
    CONFLICT = "conflict"
    STALENESS = "staleness"


class ModifierReason(str, Enum):
    """Why a modifier did not fire — or, on a fired term, what qualified it.

    **A modifier that did not fire and a modifier that fired at 0 are different facts.** Both would
    read as an absent key in a `{name: delta}` dict, which is the shape L1's components use and the
    shape this record deliberately does not: `ModifierTerm.fired` says which, and this enum says
    why. "No trend on this subject at all" and "a declining trend we were not confident enough in"
    are different answers to "why is this only a 6200", and only one of them is a threshold anyone
    can go and look at.
    """

    FIRED = "fired"
    NO_INPUT = "no_input"
    TREND_NOT_DECLINING = "not_declining"
    TREND_CONFIDENCE_BELOW_FLOOR = "trend_confidence_below_floor"
    COHORT_POPULATION_BELOW_FLOOR = "population_below_floor"
    COHORT_NOT_AT_WORST_EXTREME = "not_at_worst_extreme"
    COHORT_POLARITY_UNKNOWN = "metric_polarity_unregistered"
    ANOMALY_NOT_FLAGGED = "not_flagged"
    DEPENDENCY_NOTHING_BLOCKED = "nothing_blocked"
    CONFLICT_NONE_MATERIAL = "no_unresolved_material_conflict"
    STALENESS_WITHIN_WINDOW = "within_window"
    STALENESS_UNDATED = "no_dated_evidence"
    SUPPRESSED = L1_NOT_ACTIVE


@dataclass(frozen=True, slots=True)
class ModifierTerm:
    """One of the six, always present, fired or not.

    `evidence` is the receipt and it is a mapping of PLAIN JSON: the fact version id, the metric,
    the subject node, and the numbers the decision turned on. Never a distribution (see the module
    docstring), never a quoted sentence, never a third party's name.
    """

    name: ModifierName
    fired: bool
    delta_bp: int
    reason: ModifierReason
    evidence: Mapping[str, Any] = field(default_factory=dict)

    def as_record(self) -> dict[str, Any]:
        return {"name": self.name.value, "fired": self.fired, "delta_bp": self.delta_bp,
                "reason": self.reason.value, "evidence": dict(self.evidence)}

    @classmethod
    def from_record(cls, record: Mapping[str, Any]) -> ModifierTerm:
        return cls(name=ModifierName(record["name"]), fired=bool(record["fired"]),
                   delta_bp=int(record["delta_bp"]), reason=ModifierReason(record["reason"]),
                   evidence=dict(record.get("evidence") or {}))


@dataclass(frozen=True, slots=True)
class ComposedImportance:
    """The composed number AND the whole arithmetic that produced it.

    **"Why is this a 7400?" must be answerable from STORED data without recomputation**, which is
    a stronger requirement than "the inputs are somewhere". So every term of the sum is a field
    here, in the order the steps run, and `as_record()` writes all of them:

        base + corroboration + sum(modifier deltas) - cap_removed = subtotal
        subtotal * 8 // 10 (only when coverage_ready is False)      = penalised
        clamp(penalised, 0, 10000)                                  = importance_bp

    `test_importance.py` re-derives `importance_bp` from a JSON round trip of the record alone and
    fails if the two disagree — the property, not the promise.
    """

    importance_bp: int
    version: str
    base_bp: int
    base_source: str
    base_signal_id: str | None
    base_version: str | None
    corroboration_bp: int
    distinct_source_count: int
    source_systems: tuple[str, ...]
    modifiers: tuple[ModifierTerm, ...]
    modifier_total_bp: int
    #: How much the +4000 cap took off. 0 when it did not bite — a stored 0 is the fact "the cap
    #: was checked and did not apply", which an absent key would not be.
    modifier_cap_removed_bp: int
    subtotal_bp: int
    coverage_ready: bool | None
    coverage_domain: str | None
    #: <= 0. The amount step 4 removed, so the penalty is visible as a term rather than inferable
    #: by dividing two other numbers.
    coverage_penalty_bp: int
    #: The amount step 5's clamp moved the number, signed. 0 when it did not bite.
    clamp_delta_bp: int
    #: True when the whole composition was suppressed by the supply guard and the base passed
    #: through untouched (doc 07 hard rule 7).
    l1_importance_not_active: bool = False

    # ── the two consumers ────────────────────────────────────────────────────────────────────
    def as_record(self) -> dict[str, Any]:
        """The JSONB body. **This is what gets stored** — `situations.importance_components` and
        `BusinessSituationObject.metadata['importance_components']` take this dict verbatim.

        NOTHING DERIVED FROM THE CLOCK IS IN IT. Not `eval_time`, not an age in days, not a
        "computed_at". `situation_bso` strips `eval_time` out of Layer 1's components for exactly
        this reason and `comparator.position_fact_value` omits `computed_at` for it too: the BSO's
        metadata is hashed into the expertise package's content address, so a per-sweep value here
        re-mints a ~238 kB row per situation per sweep. The staleness term therefore stores the
        evidence DATE and the threshold; the age is a subtraction the reader can do.
        """
        return {
            "version": self.version,
            "importance_bp": self.importance_bp,
            "base_bp": self.base_bp,
            "base_source": self.base_source,
            "base_signal_id": self.base_signal_id,
            "base_version": self.base_version,
            "corroboration_bp": self.corroboration_bp,
            "distinct_source_count": self.distinct_source_count,
            "source_systems": list(self.source_systems),
            "modifiers": [m.as_record() for m in self.modifiers],
            "modifier_total_bp": self.modifier_total_bp,
            "modifier_cap_removed_bp": self.modifier_cap_removed_bp,
            "modifier_cap_bp": MODIFIER_CAP_BP,
            "subtotal_bp": self.subtotal_bp,
            "coverage_ready": self.coverage_ready,
            "coverage_domain": self.coverage_domain,
            "coverage_penalty_bp": self.coverage_penalty_bp,
            "clamp_delta_bp": self.clamp_delta_bp,
            "l1_importance_not_active": self.l1_importance_not_active,
        }

    @classmethod
    def from_record(cls, record: Mapping[str, Any]) -> ComposedImportance:
        """Read a stored record back. Round-trip safe: `from_record(json.loads(json.dumps(
        c.as_record()))) == c`, which is the test that keeps `as_record` honest as fields land."""
        return cls(
            importance_bp=int(record["importance_bp"]), version=str(record["version"]),
            base_bp=int(record["base_bp"]), base_source=str(record["base_source"]),
            base_signal_id=record.get("base_signal_id"),
            base_version=record.get("base_version"),
            corroboration_bp=int(record["corroboration_bp"]),
            distinct_source_count=int(record["distinct_source_count"]),
            source_systems=tuple(record.get("source_systems") or ()),
            modifiers=tuple(ModifierTerm.from_record(m) for m in record.get("modifiers") or ()),
            modifier_total_bp=int(record["modifier_total_bp"]),
            modifier_cap_removed_bp=int(record["modifier_cap_removed_bp"]),
            subtotal_bp=int(record["subtotal_bp"]),
            coverage_ready=record.get("coverage_ready"),
            coverage_domain=record.get("coverage_domain"),
            coverage_penalty_bp=int(record["coverage_penalty_bp"]),
            clamp_delta_bp=int(record["clamp_delta_bp"]),
            l1_importance_not_active=bool(record.get("l1_importance_not_active", False)))

    def term(self, name: ModifierName) -> ModifierTerm:
        """One modifier by name. Every one of the six is always present, so this cannot miss."""
        for modifier in self.modifiers:
            if modifier.name is name:
                return modifier
        raise KeyError(f"no {name.value} term — the record is incomplete")     # pragma: no cover

    def leaned_on(self, inputs: ModifierInputs) -> dict[str, tuple[Mapping[str, Any], ...]]:
        """The comparisons this importance ACTUALLY LEANED ON, in `situations.score_situation`'s
        shape — `score_situation(trends=..., cohort_positions=..., anomalies=...)`.

        L2.5.1's sixth confidence axis is documented as reading "the comparisons an importance
        number LEANED ON — the ones whose modifiers actually fired, not every trend the org holds",
        and until this method nothing produced that set. The mappings carry the field names the
        axis reads by name (`trend_confidence_bp`, `point_count`, `population_size`,
        `periods_used`), so the axis measures the thinness of the inputs that moved the number
        rather than of whatever happened to be lying around.
        """
        return {
            "trends": tuple({"metric": t.metric, "trend_confidence_bp": t.trend_confidence_bp,
                             "point_count": t.point_count, "direction": t.direction}
                            for t in _qualifying_trends(inputs.trends)
                            ) if self.term(ModifierName.TREND).fired else (),
            "cohort_positions": tuple({"metric": c.metric, "cohort_id": c.cohort_id,
                                       "population_size": c.population_size,
                                       "percentile_bp": c.percentile_bp}
                                      for c in _qualifying_cohorts(inputs.cohort_positions)
                                      ) if self.term(ModifierName.COHORT_POSITION).fired else (),
            "anomalies": tuple({"metric": a.metric, "periods_used": a.periods_used,
                                "z_like_bp": a.z_like_bp}
                               for a in inputs.anomalies if a.flagged
                               ) if self.term(ModifierName.ANOMALY).fired else (),
        }


# =================================================================================================
# THE SUPPLY GUARD — doc 07 hard rule 7
# =================================================================================================

@dataclass(frozen=True, slots=True)
class L1Supply:
    """Whether Layer 1's scorer is actually live for this tenant, measured on its own output."""

    scored_count: int
    flat_count: int
    #: `flat_count * 10000 // scored_count`, or 0 on an empty supply.
    flat_share_bp: int
    active: bool


def assess_l1_supply(importance_bps: Iterable[int | None]) -> L1Supply:
    """Doc 07 hard rule 7. Over 90% of the supply at exactly 5000 means ALG-17 is not live here.

    Called ONCE PER SWEEP over the org's incoming signal scores, not per situation: it is a
    property of the supply, and a single situation whose signals happen to sit at 5000 says
    nothing about the tenant. The verdict rides into the composer as `ImportanceBase` is assembled
    (`l1_active`), and when it is False the composer keeps the base and adds nothing — a real flat
    distribution, honestly reported, beats a synthetic spread that looks like it works.

    **An EMPTY supply is unknown, not flat.** A tenant with no scored signals at all has published
    no evidence that the scorer is broken, and suppressing the modifiers there would leave a
    pre-L1-v2 tenant with no ranking whatsoever while the L2 facts that could rank it — a declining
    trend, five blocked items — are sitting in the graph. So the guard fires only on measured
    flatness.
    """
    scores = [int(bp) for bp in importance_bps if bp is not None]
    if not scores:
        return L1Supply(scored_count=0, flat_count=0, flat_share_bp=0, active=True)
    flat = sum(1 for bp in scores if bp == FLAT_BASE_BP)
    share = flat * BP_MAX // len(scores)
    active = share <= FLAT_SUPPLY_LIMIT_BP
    if not active:
        _log.warning(
            "%s: %d of %d incoming signals (%d bp) carry exactly %d — Layer 1's scorer is not "
            "live for this tenant. Situation importance keeps the base; the L2 modifiers are "
            "SUPPRESSED, because a spread composed on a constant is a spread this system invented.",
            L1_NOT_ACTIVE, flat, len(scores), share, FLAT_BASE_BP)
    return L1Supply(scored_count=len(scores), flat_count=flat, flat_share_bp=share, active=active)


# =================================================================================================
# THE COMPOSER — pure, integer, clockless
# =================================================================================================

def _qualifying_trends(trends: Sequence[TrendInput]) -> tuple[TrendInput, ...]:
    """Declining, and confident enough to be worth a tenth of the scale.

    **"RELATED metric", decided.** Doc 07 says "a declining trend on a RELATED metric" and defines
    relatedness nowhere. It is the SUBJECT JOIN: a trend is related to a situation when the trend's
    `subject_node_id` is one of the situation's own subject nodes — its anchor plus the
    counterparties correlated onto it (`situation_bso.gather_members`). That set is already what
    the situation claims to be about, so the join needs no new concept and no similarity score, and
    `load_modifier_inputs` never fetches a trend for a node outside it. The rejected alternative —
    "any metric in the same domain" — would let one account's decline raise every situation in the
    tenant, which is a raise with no nameable evidence.
    """
    return tuple(sorted(
        (t for t in trends
         if t.direction == "declining" and t.trend_confidence_bp >= MIN_TREND_CONFIDENCE_BP),
        key=lambda t: (-t.trend_confidence_bp, t.metric, t.subject_node_id)))


def _qualifying_cohorts(positions: Sequence[CohortInput]) -> tuple[CohortInput, ...]:
    """The positions that sit at the bad extreme of a population big enough to have one."""
    out = []
    for position in positions:
        if position.population_size < MIN_COHORT_POPULATION:
            continue
        polarity = METRIC_POLARITY.get(position.metric)
        if polarity is None:
            continue
        band = _expressible_band(position)
        if band is worst_band(polarity, divisions=band.divisions):
            out.append(position)
    return tuple(sorted(out, key=lambda c: (c.percentile_bp, c.metric, c.subject_node_id)))


def _expressible_band(position: CohortInput) -> CohortBand:
    """The band this cohort can ACTUALLY express, recomputed from the percentile and the size.

    Recomputed rather than trusted: `CohortPosition` narrows the scheme at construction (V-8), but
    the input here is a jsonb body that may have been written before that landed, and a stored
    `D1` on a population of six is a claim its own arithmetic could never have produced. Going
    through `CohortBand.for_percentile(..., population_size=...)` means the narrowing rule lives in
    exactly one place — the contract — and this module inherits it rather than restating it.
    """
    return CohortBand.for_percentile(position.percentile_bp, divisions=10,
                                     population_size=position.population_size)


def _trend_term(inputs: ModifierInputs) -> ModifierTerm:
    """3a. +1000 once, however many metrics are declining — the strongest one is the receipt."""
    if not inputs.trends:
        return ModifierTerm(ModifierName.TREND, False, 0, ModifierReason.NO_INPUT)
    declining = [t for t in inputs.trends if t.direction == "declining"]
    if not declining:
        return ModifierTerm(ModifierName.TREND, False, 0, ModifierReason.TREND_NOT_DECLINING,
                            {"metrics_seen": sorted({t.metric for t in inputs.trends})})
    qualifying = _qualifying_trends(inputs.trends)
    if not qualifying:
        best = max(declining, key=lambda t: t.trend_confidence_bp)
        # The threshold that stopped it, and the number it stopped — a reader must be able to see
        # a 4900 and know it was one point short rather than absent.
        return ModifierTerm(
            ModifierName.TREND, False, 0, ModifierReason.TREND_CONFIDENCE_BELOW_FLOOR,
            {"metric": best.metric, "subject_node_id": best.subject_node_id,
             "trend_confidence_bp": best.trend_confidence_bp,
             "floor_bp": MIN_TREND_CONFIDENCE_BP, "fact_version_id": best.fact_version_id})
    top = qualifying[0]
    return ModifierTerm(ModifierName.TREND, True, TREND_BP, ModifierReason.FIRED, {
        "metric": top.metric, "subject_node_id": top.subject_node_id,
        "trend_confidence_bp": top.trend_confidence_bp, "point_count": top.point_count,
        "floor_bp": MIN_TREND_CONFIDENCE_BP, "fact_version_id": top.fact_version_id,
        "qualifying_count": len(qualifying),
        "qualifying_metrics": sorted({t.metric for t in qualifying})})


def _cohort_term(inputs: ModifierInputs) -> ModifierTerm:
    """3b. +1000 for sitting at the bad end of a real population — see `worst_band`."""
    if not inputs.cohort_positions:
        return ModifierTerm(ModifierName.COHORT_POSITION, False, 0, ModifierReason.NO_INPUT)
    sized = [c for c in inputs.cohort_positions if c.population_size >= MIN_COHORT_POPULATION]
    if not sized:
        biggest = max(inputs.cohort_positions, key=lambda c: c.population_size)
        return ModifierTerm(
            ModifierName.COHORT_POSITION, False, 0, ModifierReason.COHORT_POPULATION_BELOW_FLOOR,
            {"metric": biggest.metric, "population_size": biggest.population_size,
             "floor": MIN_COHORT_POPULATION, "fact_version_id": biggest.fact_version_id})
    known = [c for c in sized if c.metric in METRIC_POLARITY]
    if not known:
        # Not a silent skip: an unregistered metric means `METRIC_POLARITY` has drifted from
        # `sampler.TRENDED_METRICS`, and a modifier that quietly never fires is how a dead rule
        # survives a review.
        return ModifierTerm(
            ModifierName.COHORT_POSITION, False, 0, ModifierReason.COHORT_POLARITY_UNKNOWN,
            {"metrics_seen": sorted({c.metric for c in sized})})
    qualifying = _qualifying_cohorts(known)
    if not qualifying:
        return ModifierTerm(
            ModifierName.COHORT_POSITION, False, 0, ModifierReason.COHORT_NOT_AT_WORST_EXTREME,
            {"metrics_seen": sorted({c.metric for c in known}),
             "bands": sorted({_expressible_band(c).value for c in known})})
    polarity_of = METRIC_POLARITY
    # The most extreme one is the receipt. For a LOWER_IS_WORSE metric that is the lowest
    # percentile; for a risk metric the highest — "most extreme" is polarity-relative, and sorting
    # by raw percentile for both would name the wrong member of a risk-metric pair.
    top = min(qualifying, key=lambda c: (
        c.percentile_bp if polarity_of[c.metric] is MetricPolarity.LOWER_IS_WORSE
        else BP_MAX - c.percentile_bp, c.metric))
    band = _expressible_band(top)
    return ModifierTerm(ModifierName.COHORT_POSITION, True, COHORT_BP, ModifierReason.FIRED, {
        "metric": top.metric, "subject_node_id": top.subject_node_id, "cohort_id": top.cohort_id,
        "percentile_bp": top.percentile_bp, "band": band.value, "divisions": band.divisions,
        "population_size": top.population_size,
        "polarity": polarity_of[top.metric].value,
        "risk_metric": top.metric in RISK_METRICS,
        "fact_version_id": top.fact_version_id, "qualifying_count": len(qualifying)})


def _anomaly_term(inputs: ModifierInputs) -> ModifierTerm:
    """3c. +800 when the detector flagged the subject against its OWN baseline."""
    if not inputs.anomalies:
        return ModifierTerm(ModifierName.ANOMALY, False, 0, ModifierReason.NO_INPUT)
    flagged = sorted((a for a in inputs.anomalies if a.flagged),
                     key=lambda a: (-(a.z_like_bp or 0), a.metric, a.subject_node_id))
    if not flagged:
        return ModifierTerm(ModifierName.ANOMALY, False, 0, ModifierReason.ANOMALY_NOT_FLAGGED,
                            {"metrics_seen": sorted({a.metric for a in inputs.anomalies})})
    top = flagged[0]
    return ModifierTerm(ModifierName.ANOMALY, True, ANOMALY_BP, ModifierReason.FIRED, {
        "metric": top.metric, "subject_node_id": top.subject_node_id,
        "z_like_bp": top.z_like_bp, "direction": top.direction,
        "periods_used": top.periods_used, "fact_version_id": top.fact_version_id,
        "flagged_count": len(flagged)})


def _dependency_term(inputs: ModifierInputs) -> ModifierTerm:
    """3d. +200 per blocked item, five items' worth at most. The cost is the blocked work.

    **N is the MAX across the situation's subject nodes, never the sum.** `derived.py` writes
    `deal.*` facts onto the company node AND the deal node, so one blocked item routinely waits on
    two of a situation's own subjects; summing would let node duplication buy +400 for one piece of
    blocked work, and a situation anchored on a company with three related deal nodes could reach
    the modifier's ceiling with two real blockers. The max is the honest reading of "N items
    blocked on this situation" when the situation is about several nodes at once.
    """
    if not inputs.dependencies:
        return ModifierTerm(ModifierName.DEPENDENCY, False, 0, ModifierReason.NO_INPUT)
    top = max(inputs.dependencies, key=lambda d: (d.blocked_count, d.subject_node_id))
    if top.blocked_count <= 0:
        return ModifierTerm(ModifierName.DEPENDENCY, False, 0,
                            ModifierReason.DEPENDENCY_NOTHING_BLOCKED,
                            {"subject_node_ids": sorted(d.subject_node_id
                                                        for d in inputs.dependencies)})
    counted = min(top.blocked_count, DEPENDENCY_MAX_BLOCKED)
    return ModifierTerm(ModifierName.DEPENDENCY, True, DEPENDENCY_PER_BLOCKED_BP * counted,
                        ModifierReason.FIRED, {
                            "subject_node_id": top.subject_node_id,
                            "blocked_count": top.blocked_count, "counted": counted,
                            "cap": DEPENDENCY_MAX_BLOCKED,
                            "per_blocked_bp": DEPENDENCY_PER_BLOCKED_BP,
                            # A POINTER to the chains, never their contents: the chains fact names
                            # third parties and quotes their sentences and is participants-scoped.
                            "fact_version_id": top.fact_version_id})


def _conflict_term(inputs: ModifierInputs) -> ModifierTerm:
    """3e. +700 once — we may be about to say something false.

    "Material" is defined, with its rejected alternative, on `ConflictInput`.
    """
    if not inputs.conflicts:
        return ModifierTerm(ModifierName.CONFLICT, False, 0, ModifierReason.NO_INPUT)
    material = sorted((c for c in inputs.conflicts if c.resolution == UNRESOLVED_RESOLUTION),
                      key=lambda c: c.conflict_id)
    if not material:
        return ModifierTerm(ModifierName.CONFLICT, False, 0, ModifierReason.CONFLICT_NONE_MATERIAL,
                            {"resolutions_seen": sorted({c.resolution for c in inputs.conflicts})})
    return ModifierTerm(ModifierName.CONFLICT, True, CONFLICT_BP, ModifierReason.FIRED, {
        # Ids and field paths only. The claims themselves are two sources' verbatim values and
        # live on the `signal_conflicts` row, which is where a reader with the right audience goes.
        "conflict_ids": [c.conflict_id for c in material[:MAX_NAMED_CONFLICTS]],
        "fields": sorted({c.field for c in material}),
        "unresolved_count": len(material), "resolution": UNRESOLVED_RESOLUTION})


def _staleness_term(inputs: ModifierInputs, *, eval_time: datetime) -> ModifierTerm:
    """3f. -1500 when the situation's own newest evidence is older than 90 days.

    UNDATED IS NOT STALE. A situation with no dated evidence gets no discount and says so: absence
    of a date is not evidence of age, and discounting it would penalise a tenant for a capture gap.
    """
    newest = inputs.newest_evidence_at
    if newest is None:
        return ModifierTerm(ModifierName.STALENESS, False, 0, ModifierReason.STALENESS_UNDATED)
    require_aware(newest, "newest_evidence_at")
    cutoff = require_aware(eval_time, "eval_time") - timedelta(days=STALENESS_DAYS)
    # The DATE and the threshold are stored; the AGE is not — see `as_record`. An age recomputed
    # every sweep is a new content address every sweep for every stale situation.
    evidence = {"newest_evidence_at": newest.isoformat(), "threshold_days": STALENESS_DAYS,
                "measured_on": "situation"}
    if newest > cutoff:
        return ModifierTerm(ModifierName.STALENESS, False, 0,
                            ModifierReason.STALENESS_WITHIN_WINDOW, evidence)
    return ModifierTerm(ModifierName.STALENESS, True, STALENESS_BP, ModifierReason.FIRED, evidence)


def compose_situation_importance(*, base: ImportanceBase,
                                 signals: Sequence[ConstituentSignal],
                                 modifiers: ModifierInputs,
                                 eval_time: datetime,
                                 l1_active: bool = True) -> ComposedImportance:
    """BLG-18 steps 2..6. Pure: no database, no clock, no model, integer basis points throughout.

    Step 1's `base` comes in already decided (`situation_bso.gather_l1_signals`). Steps 2..6 run in
    the doc's order, and the order is load-bearing at one place: the coverage penalty multiplies
    the SUBTOTAL and the clamp runs after it, so a situation whose terms sum past 10000 is
    discounted before it is clamped rather than after. Doc 07 states it in that order and the
    difference is visible (12000 -> 9600, not 10000 -> 8000), so it is followed rather than
    tidied — with both intermediate numbers stored so a reader never has to guess which happened.
    """
    require_aware(eval_time, "eval_time")

    # Step 2 — corroboration. Distinct SOURCE SYSTEMS, not distinct events: forty mails in one
    # thread are one source agreeing with itself, and counting events would let a busy thread buy
    # the whole +1500.
    systems = tuple(sorted({s.source_system for s in signals if s.source_system}))
    distinct = len(systems)
    corroboration = min(CORROBORATION_CAP_BP,
                        max(0, distinct - 1) * CORROBORATION_PER_EXTRA_SOURCE_BP)

    # Doc 07 hard rule 7. Keep the base, add nothing, and say so on the record. Every one of the
    # six terms is still written — suppressed is a fact about the composition, and a record with
    # the modifier list missing would be indistinguishable from a situation with no inputs.
    if not l1_active:
        terms = tuple(ModifierTerm(name, False, 0, ModifierReason.SUPPRESSED)
                      for name in ModifierName)
        clamped = max(BP_MIN, min(BP_MAX, base.importance_bp))
        return ComposedImportance(
            importance_bp=clamped, version=IMPORTANCE_VERSION, base_bp=base.importance_bp,
            base_source=base.source, base_signal_id=base.signal_id, base_version=base.version,
            corroboration_bp=0, distinct_source_count=distinct, source_systems=systems,
            modifiers=terms, modifier_total_bp=0, modifier_cap_removed_bp=0,
            subtotal_bp=base.importance_bp, coverage_ready=modifiers.coverage_ready,
            coverage_domain=modifiers.coverage_domain, coverage_penalty_bp=0,
            clamp_delta_bp=clamped - base.importance_bp, l1_importance_not_active=True)

    # Step 3 — the six, in doc order, every one of them recorded whether or not it fired.
    terms = (
        _trend_term(modifiers),
        _cohort_term(modifiers),
        _anomaly_term(modifiers),
        _dependency_term(modifiers),
        _conflict_term(modifiers),
        _staleness_term(modifiers, eval_time=eval_time),
    )
    positive = sum(t.delta_bp for t in terms if t.delta_bp > 0)
    negative = sum(t.delta_bp for t in terms if t.delta_bp < 0)
    cap_removed = max(0, positive - MODIFIER_CAP_BP)
    modifier_total = positive - cap_removed + negative

    subtotal = base.importance_bp + corroboration + modifier_total

    # Step 4 — the coverage penalty. ONLY on an explicit False: `None` is "no coverage row for this
    # domain", which is not a licence to discount (the same tri-state rule the signal contract and
    # the metric point contract both keep).
    if modifiers.coverage_ready is False:
        penalised = subtotal * COVERAGE_PENALTY_NUMERATOR // COVERAGE_PENALTY_DENOMINATOR
    else:
        penalised = subtotal
    coverage_penalty = penalised - subtotal

    # Step 5 — the clamp, stored as a delta so "did it bite" is a stored fact rather than an
    # inference from a number sitting suspiciously at 10000.
    clamped = max(BP_MIN, min(BP_MAX, penalised))

    return ComposedImportance(
        importance_bp=clamped, version=IMPORTANCE_VERSION, base_bp=base.importance_bp,
        base_source=base.source, base_signal_id=base.signal_id, base_version=base.version,
        corroboration_bp=corroboration, distinct_source_count=distinct, source_systems=systems,
        modifiers=terms, modifier_total_bp=modifier_total, modifier_cap_removed_bp=cap_removed,
        subtotal_bp=subtotal, coverage_ready=modifiers.coverage_ready,
        coverage_domain=modifiers.coverage_domain, coverage_penalty_bp=coverage_penalty,
        clamp_delta_bp=clamped - penalised, l1_importance_not_active=False)


# =================================================================================================
# THE READERS — bulk, org-scoped, point-in-time. Six queries per sweep, not six per situation.
# =================================================================================================
#
# THE SCAR THIS SHAPE EXISTS TO AVOID. `docs/plans/PERFORMANCE_HARDENING.md` records L3 doing
# ~1000 per-node reads and 24k audit writes per org, which took a reasoning pass past thirty
# minutes and blocked emission entirely. A modifier bundle assembled with one query per situation
# would reproduce it precisely: 223 situations x 4 fact families x a conflict read is over a
# thousand round trips for a table scan that fits in one. So every reader below takes the WHOLE
# set of nodes (or signals) the sweep cares about and returns a mapping; `load_modifier_inputs`
# calls each exactly once and assembles per-situation bundles in Python.

#: `graph_facts.field` prefixes for the three analytic families and the one dependency field.
#: Spelled here with their provenance rather than imported (`trend.TREND_FACT_PREFIX`,
#: `comparator.POSITION_FACT_PREFIX`, `anomaly.ANOMALY_FACT_PREFIX`,
#: `correlation_dependency.FIELD_BLOCKED_COUNT`) for the reason `METRIC_POLARITY` gives: this
#: module must not drag `context/analytic/` into every importer's graph for four strings.
#: `test_importance.py` pins all four against the modules that own them.
TREND_FACT_PREFIX = "derived.trend."
COHORT_FACT_PREFIX = "derived.cohort_position."
ANOMALY_FACT_PREFIX = "derived.anomaly."
DEPENDENCY_BLOCKED_FIELD = "derived.dependency.blocked_count"

FACT_TABLE = "graph_facts"
COVERAGE_TABLE = "source_coverage"
CONFLICT_TABLE = "signal_conflicts"

#: THE POINT-IN-TIME WINDOW, byte-identical to `graph_store._WINDOW_AT`. A derived fact is a
#: versioned row with a `[valid_from, valid_to)` stint, and `publish_derived_fact` exists because
#: a reader that took the LATEST row would answer March's question with September's cohort. Pinned
#: against `graph_store` by a test so the two cannot drift — doc 02's acceptance row, "replaying a
#: March decision against as_of=March reproduces its inputs", is one predicate wide.
FACT_WINDOW_AT = "valid_from <= :t and (valid_to is null or valid_to > :t)"

#: A candidate fact is a PROPOSAL, not a reading — never a modifier input. Superseded rows are NOT
#: excluded, and that is the point of the window: at an `eval_time` inside its stint, a since-
#: superseded row is the correct answer, and filtering on `status='active'` would silently make
#: every replay of a past instant read today's graph.
_EXCLUDED_FACT_STATUS = "candidate"

#: How many ids go into one `= any(array[...])`. A ceiling on the parameter, not a sample: an org
#: with more subject nodes than this is read in several passes, never truncated.
READ_CHUNK = 1_000


@dataclass(frozen=True, slots=True)
class SituationRef:
    """What a caller must know about one situation before the modifiers can be read for it.

    Every field is already on a `context_situations` row or already computed by
    `situation_bso` — nothing here asks the caller to derive anything new:

    * `subject_node_ids` — the anchor plus the counterparties `gather_members` returns. THE JOIN
      for modifiers 3a-3d (see `_qualifying_trends` for why the subject node is the relatedness
      test).
    * `signal_ids` — the constituent `qualified_signals` ids from `gather_l1_signals`. The join for
      modifier 3e.
    * `newest_evidence_at` — `context_situations.last_seen_at`, which IS the situation's own newest
      correlated evidence. Modifier 3f is measured on the situation, not the subject.
    * `domain` — the key `source_coverage` is filed under, for step 4.
    """

    situation_id: str
    domain: str
    subject_node_ids: tuple[str, ...] = ()
    signal_ids: tuple[str, ...] = ()
    newest_evidence_at: datetime | None = None


def _chunks(values: Sequence[str], size: int = READ_CHUNK) -> Iterable[list[str]]:
    for start in range(0, len(values), size):
        yield list(values[start:start + size])


def _body(value: Any) -> Mapping[str, Any]:
    """One jsonb column on the way back, defensively.

    psycopg2 decodes jsonb to a dict already; a driver that hands back text is the other case, and
    an unparseable body is dropped rather than raised. A malformed derived fact must cost its own
    modifier, never the whole sweep — the same rule `situation_bso._json` keeps for receipts.
    """
    if isinstance(value, Mapping):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except ValueError:
            return {}
        return parsed if isinstance(parsed, Mapping) else {}
    return {}


def _int(value: Any) -> int | None:
    """An integer or nothing. `True` is refused: bool is an int in Python, and a `flagged` read as
    a 1 would become a one-period baseline nobody measured (the trap `situations._analytic_reading`
    names)."""
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value


def read_derived_modifier_facts(
    conn, org_id: str, node_ids: Sequence[str], *, eval_time: datetime,
) -> dict[str, ModifierInputs]:
    """Modifiers 3a-3d for every node named, in ONE query per chunk of `READ_CHUNK` nodes.

    Returns a bundle PER NODE carrying only the four fact families; `load_modifier_inputs` merges
    the nodes of one situation together. The four families are read in a single statement rather
    than four because they live in one table under one index (`graph_facts_current`), and four
    passes over the same rows is three more than the answer needs.
    """
    require_aware(eval_time, "eval_time")
    ordered = tuple(sorted(set(node_ids)))
    trends: dict[str, list[TrendInput]] = {}
    cohorts: dict[str, list[CohortInput]] = {}
    anomalies: dict[str, list[AnomalyInput]] = {}
    dependencies: dict[str, list[DependencyInput]] = {}
    for chunk in _chunks(ordered):
        rows = conn.execute(text(
            f"select fact_version_id, subject_node_id, field, value from {FACT_TABLE} "
            "where org_id = :o and subject_node_id = any(cast(:nodes as text[])) "
            f"and status <> :skip and {FACT_WINDOW_AT} "
            "and (field like :trend or field like :cohort or field like :anomaly "
            "     or field = :blocked) "
            "order by subject_node_id, field, fact_version_id"),
            {"o": org_id, "nodes": chunk, "t": eval_time, "skip": _EXCLUDED_FACT_STATUS,
             "trend": f"{TREND_FACT_PREFIX}%", "cohort": f"{COHORT_FACT_PREFIX}%",
             "anomaly": f"{ANOMALY_FACT_PREFIX}%", "blocked": DEPENDENCY_BLOCKED_FIELD}
        ).mappings().all()
        for row in rows:
            node, fid, name = str(row["subject_node_id"]), str(row["fact_version_id"]), \
                str(row["field"])
            body = _body(row["value"])
            if name == DEPENDENCY_BLOCKED_FIELD:
                count = _int(body.get("count"))
                if count is not None:
                    dependencies.setdefault(node, []).append(
                        DependencyInput(subject_node_id=node, blocked_count=count,
                                        fact_version_id=fid))
            elif name.startswith(TREND_FACT_PREFIX):
                confidence = _int(body.get("trend_confidence_bp"))
                direction = body.get("direction")
                if confidence is None or not isinstance(direction, str):
                    continue
                trends.setdefault(node, []).append(TrendInput(
                    metric=str(body.get("metric") or name[len(TREND_FACT_PREFIX):]),
                    subject_node_id=node, direction=direction,
                    trend_confidence_bp=confidence,
                    point_count=_int(body.get("point_count")) or 0, fact_version_id=fid))
            elif name.startswith(COHORT_FACT_PREFIX):
                # A REFUSAL is written as a fact too (`position_fact_value`), and it carries
                # `refused` with no percentile. Reading one as a position would invent a rank.
                percentile = _int(body.get("percentile_bp"))
                population = _int(body.get("population_size"))
                cohort_id = body.get("cohort_id")
                if body.get("refused") or percentile is None or population is None \
                        or not isinstance(cohort_id, str):
                    continue
                # p25/p50/p75 are ON this body and are deliberately not read — see `CohortInput`.
                cohorts.setdefault(node, []).append(CohortInput(
                    metric=str(body.get("metric") or name[len(COHORT_FACT_PREFIX):]),
                    subject_node_id=node, percentile_bp=percentile, population_size=population,
                    cohort_id=cohort_id,
                    band=str(body["band"]) if isinstance(body.get("band"), str) else None,
                    fact_version_id=fid))
            elif name.startswith(ANOMALY_FACT_PREFIX):
                flagged = body.get("flagged")
                if not isinstance(flagged, bool):
                    continue
                anomalies.setdefault(node, []).append(AnomalyInput(
                    metric=str(body.get("metric") or name[len(ANOMALY_FACT_PREFIX):]),
                    subject_node_id=node, flagged=flagged,
                    periods_used=_int(body.get("periods_used")) or 0,
                    z_like_bp=_int(body.get("z_like_bp")),
                    direction=body.get("direction") if isinstance(body.get("direction"), str)
                    else None,
                    fact_version_id=fid))
    return {node: ModifierInputs(
        trends=tuple(trends.get(node, ())), cohort_positions=tuple(cohorts.get(node, ())),
        anomalies=tuple(anomalies.get(node, ())), dependencies=tuple(dependencies.get(node, ())))
        for node in ordered}


def read_unresolved_conflicts(conn, org_id: str,
                              signal_ids: Sequence[str]) -> dict[str, tuple[ConflictInput, ...]]:
    """Modifier 3e's input: the UNRESOLVED disagreements attached to these signals, by signal id.

    Filtered in SQL rather than in Python because `signal_conflicts` holds every disagreement the
    tenant has ever had, resolved ones included, and the resolved ones are exactly the rows this
    modifier must not read (see `ConflictInput`). No clock: a conflict has no window — it is
    superseded by a re-detection under the same content-addressed id, not by time.
    """
    ordered = tuple(sorted(set(signal_ids)))
    out: dict[str, list[ConflictInput]] = {}
    for chunk in _chunks(ordered):
        rows = conn.execute(text(
            f"select conflict_id, signal_id, field, resolution from {CONFLICT_TABLE} "
            "where org_id = :o and signal_id = any(cast(:sigs as text[])) "
            "and resolution = :unresolved order by conflict_id"),
            {"o": org_id, "sigs": chunk, "unresolved": UNRESOLVED_RESOLUTION}).mappings().all()
        for row in rows:
            out.setdefault(str(row["signal_id"]), []).append(ConflictInput(
                conflict_id=str(row["conflict_id"]), field=str(row["field"]),
                signal_id=str(row["signal_id"]), resolution=str(row["resolution"])))
    return {k: tuple(v) for k, v in out.items()}


def read_domain_coverage(conn, org_id: str) -> dict[str, bool]:
    """Step 4's input: `source_coverage.coverage_ready` for every domain the org has a row for.

    One read for the whole tenant — there are as many rows as there are registered domains, and a
    per-situation lookup would be 223 queries against a table with three rows in it. A domain with
    NO row is absent from the mapping, and absence stays `None` (unknown) all the way through: the
    penalty is for coverage we know we lack, never for a coverage pass that has not run.
    """
    rows = conn.execute(text(
        f"select domain, coverage_ready from {COVERAGE_TABLE} where org_id = :o"),
        {"o": org_id}).mappings().all()
    return {str(r["domain"]): bool(r["coverage_ready"]) for r in rows
            if r["coverage_ready"] is not None}


def load_modifier_inputs(conn, org_id: str, refs: Sequence[SituationRef], *,
                         eval_time: datetime) -> dict[str, ModifierInputs]:
    """Every situation's modifier bundle, in THREE queries plus one chunk pass. Org-scoped.

    A situation is usually about several nodes (an anchor company, its deal node, the people on
    the thread), so the per-node facts are UNIONED onto the situation. That union is what makes
    "N items blocked on this situation" a max rather than a sum (see `_dependency_term`) and what
    makes a decline on the deal node count for a situation anchored on the company.
    """
    require_aware(eval_time, "eval_time")
    nodes = sorted({n for ref in refs for n in ref.subject_node_ids})
    signals = sorted({s for ref in refs for s in ref.signal_ids})
    by_node = read_derived_modifier_facts(conn, org_id, nodes, eval_time=eval_time)
    by_signal = read_unresolved_conflicts(conn, org_id, signals)
    coverage = read_domain_coverage(conn, org_id)

    bundles: dict[str, ModifierInputs] = {}
    for ref in refs:
        node_bundles = [by_node[n] for n in ref.subject_node_ids if n in by_node]
        conflicts: list[ConflictInput] = []
        for signal_id in ref.signal_ids:
            conflicts.extend(by_signal.get(signal_id, ()))
        bundles[ref.situation_id] = ModifierInputs(
            trends=tuple(t for b in node_bundles for t in b.trends),
            cohort_positions=tuple(c for b in node_bundles for c in b.cohort_positions),
            anomalies=tuple(a for b in node_bundles for a in b.anomalies),
            dependencies=tuple(d for b in node_bundles for d in b.dependencies),
            # Deduplicated: one conflict can be attached to two of the situation's signals, and
            # naming it twice would read as two independent disagreements.
            conflicts=tuple(sorted({c.conflict_id: c for c in conflicts}.values(),
                                   key=lambda c: c.conflict_id)),
            newest_evidence_at=ref.newest_evidence_at,
            coverage_ready=coverage.get(ref.domain),
            coverage_domain=ref.domain)
    return bundles


def read_constituent_signals(
    conn, org_id: str, correlation_ids: Sequence[str],
) -> dict[str, tuple[ConstituentSignal, ...]]:
    """Step 2's input: the distinct SOURCE SYSTEMS behind each correlation, in one grouped query.

    **Counted over the correlated EVENTS, not over the live qualified signals**, and that is a
    deliberate difference from the BASE. ALG-19 retires signals on every sync; a corroboration
    that shrank as signals aged would move a situation's importance — and therefore its expertise
    package's content address — on a sweep where nothing about the situation changed, which is the
    write-amplification mechanism that took a tenant's database read-only. What the situation was
    BUILT from does not decay: three sources agreed in March whether or not March's signals are
    still live in September.
    """
    ordered = tuple(sorted(set(correlation_ids)))
    out: dict[str, list[ConstituentSignal]] = {}
    for chunk in _chunks(ordered):
        rows = conn.execute(text(
            "select m.correlation_id as cid, se.source as source, min(se.event_id) as event_id, "
            "       count(*) as n "
            "from context_correlation_members m "
            "join source_events se on se.event_id = m.event_id and se.org_id = m.org_id "
            "where m.org_id = :o and m.correlation_id = any(cast(:cids as text[])) "
            "group by 1, 2 order by 1, 2"),
            {"o": org_id, "cids": chunk}).mappings().all()
        for row in rows:
            out.setdefault(str(row["cid"]), []).append(ConstituentSignal(
                id=str(row["event_id"]), source_system=str(row["source"])))
    return {k: tuple(v) for k, v in out.items()}


__all__ = [
    "ANOMALY_BP", "ANOMALY_FACT_PREFIX", "BP_MAX", "BP_MIN", "COHORT_BP", "COHORT_FACT_PREFIX",
    "CONFLICT_BP", "CONFLICT_TABLE", "CORROBORATION_CAP_BP", "CORROBORATION_PER_EXTRA_SOURCE_BP",
    "COVERAGE_PENALTY_DENOMINATOR", "COVERAGE_PENALTY_NUMERATOR", "COVERAGE_TABLE",
    "DEPENDENCY_BLOCKED_FIELD", "DEPENDENCY_MAX_BLOCKED", "DEPENDENCY_PER_BLOCKED_BP",
    "FACT_TABLE", "FACT_WINDOW_AT", "FLAT_BASE_BP", "FLAT_SUPPLY_LIMIT_BP", "IMPORTANCE_VERSION",
    "L1_NOT_ACTIVE", "MAX_NAMED_CONFLICTS", "METRIC_POLARITY", "MIN_TREND_CONFIDENCE_BP",
    "MODIFIER_CAP_BP", "READ_CHUNK", "RISK_METRICS", "STALENESS_BP", "STALENESS_DAYS",
    "TREND_BP", "TREND_FACT_PREFIX", "UNRESOLVED_RESOLUTION",
    "AnomalyInput", "CohortInput", "ComposedImportance", "ConflictInput", "ConstituentSignal",
    "DependencyInput", "ImportanceBase", "L1Supply", "MetricPolarity", "ModifierInputs",
    "ModifierName", "ModifierReason", "ModifierTerm", "SituationRef", "TrendInput",
    "assess_l1_supply", "compose_situation_importance", "load_modifier_inputs",
    "read_constituent_signals", "read_derived_modifier_facts", "read_domain_coverage",
    "read_unresolved_conflicts", "worst_band",
]
