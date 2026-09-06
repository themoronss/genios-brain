"""L2.6.1-U1 · the pattern SCHEMA — a detectable situation as data, not as code.

Anchor-based detection (`situations.situation_type(anchor_type, domain)`) answers *"what is this
about?"*. A pattern answers *"do these five things hold together right now?"*, and those are
different capabilities: no anchor type can express Globe's own worked example — renewal **and**
auto-renew **and** high value **and** a short cancellation window **and** a migration discussion
**and** no scheduled decision. Six conditions, one card, and the current code cannot say it.

WHY A SCHEMA AND NOT SIX PYTHON FUNCTIONS. The same argument cohorts (L2.4.4) and expectation maps
(L2.5.5) already won: a declared thing can be diffed, reviewed and corrected by the person who
noticed it was wrong, and a detector written in Python can only be corrected by the person who
wrote it. Adding a detectable situation must be a registry entry.

THE THREE RULES THIS FILE ENFORCES AT PARSE TIME, each because the alternative fails silently:

1. **`extra="forbid"` everywhere.** A misspelled key in a YAML condition is a condition that
   quietly does not exist, and a pattern with four of its five conditions is not a tighter
   pattern — it is a looser one that still looks correct in review. L1 shipped fifteen of
   twenty-one deep sales rules gated on a field 9% of records carried, and every test was green.

2. **A `fact` condition may not say `missing`.** "There is no row" and "no connected source could
   have carried one" are the same empty result and opposite claims. Absence is expressible only
   through `kind: absence`, which consumes L2.5.5's TYPED absence and therefore knows which of the
   two it is looking at. This is the single most important refusal in the file.

3. **No floats, anywhere, ever** — see `no_float`. A pattern is data that reaches a comparison
   against integer basis points; a `0.30` in a YAML file is a threshold nobody can reproduce.

WHAT IS DELIBERATELY NOT HERE. No thresholds, no weights beyond the ones a pattern declares about
itself, and no scoring. A pattern says what must hold; how much a match is worth is
`scorer.py`'s, and how much a SITUATION matters is BLG-18's and composes from Layer 1 signals.
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Annotated, Any, Literal, Union

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from genios_engine.contracts.analytic import (DIRECTIONAL, AnomalyDirection, CohortBand,
                                              TrendDirection)
from genios_engine.contracts.quality import AbsenceType

#: The strength every match starts from once all required conditions hold. Required conditions
#: are BINARY — they all held or there is no match at all — so they cannot contribute a partial
#: score, and the base is what says so arithmetically. Only `optional_signals` move the number.
#:
#: 6000 rather than 10000 so a bare match and a corroborated one are distinguishable at all: a
#: base of 10000 would clamp every optional signal away and make `weight_bp` decorative.
BASE_MATCH_STRENGTH_BP = 6_000

#: The ceiling. Basis points, so 10000 is "as strong as this scale can say".
MAX_MATCH_STRENGTH_BP = 10_000

#: The two `@`-references a pattern may use. A closed set, validated at registration: an
#: unresolvable reference is a condition that silently never holds, which is indistinguishable
#: from a pattern that found nothing.
ANCHOR_REF = "@anchor"
AUTHORITY_THRESHOLD_REF = "@authority_threshold"
REFERENCES: frozenset[str] = frozenset({ANCHOR_REF, AUTHORITY_THRESHOLD_REF})


class PatternError(ValueError):
    """A pattern that cannot be registered. Loud at REGISTRATION, never at evaluation.

    Doc 06's failure table: *"a condition references a missing capability -> silent non-fire"*.
    A pattern that fails to load is visible; a pattern that loads and can never hold is
    indistinguishable from a working one that found nothing, and nobody goes looking for it.
    """


def no_float(value: Any, label: str) -> Any:
    """Refuse a float anywhere in a pattern, at any depth. Doctrine 2, enforced at parse time.

    YAML turns `1.5` into a Python float without asking, and a float threshold in a pattern is a
    comparison whose boundary moves with the platform's rounding. Bools are excluded from the
    numeric check deliberately: `True` is an `int` in Python and a perfectly good fact value.
    """
    if isinstance(value, float):
        raise PatternError(
            f"{label} is a float ({value!r}); patterns are integer-only — express a ratio in "
            "basis points and a money value in minor units")
    if isinstance(value, (list, tuple)):
        for item in value:
            no_float(item, label)
    if isinstance(value, dict):
        for key, item in value.items():
            no_float(item, f"{label}.{key}")
    return value


class ConditionKind(str, Enum):
    """The eight kinds doc 06 names, each mapping to a group that is actually built.

    The last four are only expressible because L2.4 and L2.5.5 exist, and that is the concrete
    payoff of the analytic stratum: *"engagement declining AND bottom-decile in its cohort AND no
    owner"* becomes declarable, and that one pattern is a churn detector nobody wrote code for.
    """

    FACT = "fact"                 # graph_facts                      (L2.1)
    EDGE = "edge"                 # graph_edges, present or missing  (L2.1)
    TEMPORAL = "temporal"         # date proximity to eval_time      (L2.1.3)
    ABSENCE = "absence"           # TYPED absence                    (L2.5.5)
    TREND = "trend"               # direction + confidence           (L2.4.3)
    COHORT = "cohort"             # percentile position              (L2.4.5)
    ANOMALY = "anomaly"           # deviation vs own baseline        (L2.4.8)
    OBSERVATION = "observation"   # graph_observations               (L2.1)


class FactOp(str, Enum):
    """What a `fact` condition may assert. `missing` is CONSPICUOUSLY ABSENT — see rule 2 in the
    module docstring; `exists` is the positive half and is safe because a row that is there is
    there regardless of what the connectors can see."""

    EQ = "eq"
    NE = "ne"
    GT = "gt"
    GTE = "gte"
    LT = "lt"
    LTE = "lte"
    IN = "in"
    CONTAINS = "contains"
    EXISTS = "exists"


#: The fact operators that compare two numbers. Named as data so the evaluator and the validator
#: read the same list rather than two `in (...)` tuples that drift.
NUMERIC_FACT_OPS: frozenset[FactOp] = frozenset({FactOp.GT, FactOp.GTE, FactOp.LT, FactOp.LTE})


class EdgeOp(str, Enum):
    PRESENT = "present"
    MISSING = "missing"


class TemporalOp(str, Enum):
    """Two operators, both relative to `eval_time`, and neither of them reads a clock.

    `before`/`after` against a literal date were considered and refused: a hardcoded date in a
    pattern is a rule that silently expires, and the two below express every situation the seed
    set needs — a window closing (`within_days`) and a silence (`older_than_days`).
    """

    #: The dated field lies in the FUTURE, at most N days after `eval_time`. A deadline
    #: approaching. A date already in the past does NOT satisfy it — that is a different
    #: situation (missed) and must be a different pattern, or a card says "12 days left" about a
    #: window that closed last month.
    WITHIN_DAYS = "within_days"
    #: The dated field lies in the PAST, at least N days before `eval_time`. A silence.
    OLDER_THAN_DAYS = "older_than_days"


class CohortOp(str, Enum):
    BAND_IS = "band_is"
    PERCENTILE_LTE = "percentile_lte"
    PERCENTILE_GTE = "percentile_gte"


class _Base(BaseModel):
    """Frozen, forbidding, and alias-friendly — the three properties every condition shares."""

    model_config = ConfigDict(frozen=True, extra="forbid", populate_by_name=True)


class FactCondition(_Base):
    """`{kind: fact, field: contract.auto_renews, op: eq, value: true}`"""

    kind: Literal[ConditionKind.FACT] = ConditionKind.FACT
    #: A dotted field PATH into `graph_facts.field`, never a human label. `situation_bso` learned
    #: this the hard way: human labels have spaces, match nothing in the graph, and a predicate
    #: over them answers FALSE where it should answer UNKNOWN.
    field_path: str = Field(alias="field")
    op: FactOp
    #: The comparand, or an `@`-reference resolved against the graph at `eval_time`. Absent for
    #: `exists`, which compares nothing.
    value: bool | int | str | tuple[Any, ...] | None = None

    @field_validator("value", mode="before")
    @classmethod
    def _value(cls, value: Any) -> Any:
        if isinstance(value, list):
            return tuple(no_float(value, "value"))
        return no_float(value, "value")

    @model_validator(mode="after")
    def _shape(self) -> FactCondition:
        if self.op is FactOp.EXISTS:
            if self.value is not None:
                raise PatternError("an `exists` fact condition compares nothing; drop `value`")
            return self
        if self.value is None:
            raise PatternError(f"fact condition on {self.field_path!r} needs a `value`")
        if self.op is FactOp.IN and not isinstance(self.value, tuple):
            raise PatternError("`in` needs a list of values")
        if self.op in NUMERIC_FACT_OPS and not _numeric_or_ref(self.value):
            raise PatternError(
                f"`{self.op.value}` on {self.field_path!r} compares numbers; got {self.value!r}. "
                "Money is minor units, ratios are basis points, and a reference is one of "
                f"{sorted(REFERENCES)}")
        return self


def _numeric_or_ref(value: Any) -> bool:
    if isinstance(value, bool):
        return False
    return isinstance(value, int) or (isinstance(value, str) and value in REFERENCES)


class EdgeCondition(_Base):
    """`{kind: edge, type: owns, from: "@anchor", op: missing}`

    A MISSING edge is a negative inference and is governed as one: the evaluator satisfies it only
    where the slice declares that this edge type's absence was KNOWABLE for the org (see
    `slice.GraphSlice.edge_coverage`). Without that declaration a disconnected CRM would read as
    "nobody owns this contract", which is the same failure `AbsenceType.UNKNOWABLE` exists to
    prevent one table over.
    """

    kind: Literal[ConditionKind.EDGE] = ConditionKind.EDGE
    edge_type: str = Field(alias="type")
    from_node: str = Field(default=ANCHOR_REF, alias="from")
    to_node: str | None = Field(default=None, alias="to")
    op: EdgeOp = EdgeOp.PRESENT

    @property
    def field_path(self) -> str:
        return f"edge.{self.edge_type}"


class TemporalCondition(_Base):
    """`{kind: temporal, field: contract.cancellable_until, op: within_days, value: 30}`"""

    kind: Literal[ConditionKind.TEMPORAL] = ConditionKind.TEMPORAL
    field_path: str = Field(alias="field")
    op: TemporalOp
    #: Whole days. Positive: "within 0 days" is a pattern that can only fire on the exact instant
    #: and is a mistake somebody should hear about at registration.
    value: int

    @field_validator("value", mode="before")
    @classmethod
    def _days(cls, value: Any) -> int:
        no_float(value, "value")
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            raise PatternError(f"a temporal window is a positive whole number of days: {value!r}")
        return value


class AbsenceCondition(_Base):
    """`{kind: absence, field: decision.scheduled, type: GENUINELY_ABSENT}`

    ONLY `GENUINELY_ABSENT` is registrable. `UNKNOWABLE`, `STALE` and `NOT_EXPECTED` are refused
    HERE rather than at evaluation, because a pattern that declares `type: UNKNOWABLE` is asking
    to fire on our own missing plumbing and no amount of care at the call site makes that a
    finding about a customer.
    """

    kind: Literal[ConditionKind.ABSENCE] = ConditionKind.ABSENCE
    field_path: str = Field(alias="field")
    absence_type: AbsenceType = Field(default=AbsenceType.GENUINELY_ABSENT, alias="type")

    @field_validator("absence_type", mode="before")
    @classmethod
    def _only_genuine(cls, value: Any) -> AbsenceType:
        if isinstance(value, str):
            try:
                value = AbsenceType(value.lower())
            except ValueError as exc:
                raise PatternError(f"unknown absence type {value!r}") from exc
        if value is not AbsenceType.GENUINELY_ABSENT:
            raise PatternError(
                f"an absence condition may only require GENUINELY_ABSENT, not {value}. "
                "UNKNOWABLE means a source that could have carried the fact was never connected; "
                "firing on it turns our own coverage gap into a claim about the customer")
        return value


class TrendCondition(_Base):
    """`{kind: trend, metric: engagement.touch_count_28d, direction: DECLINING}`

    The confidence floor is NOT declarable per pattern — it lives with the kind (see
    `matcher.TREND_MIN_CONFIDENCE_BP`), so no pattern can lower it to make itself fire.
    """

    kind: Literal[ConditionKind.TREND] = ConditionKind.TREND
    metric: str
    direction: TrendDirection

    @field_validator("direction", mode="before")
    @classmethod
    def _real_direction(cls, value: Any) -> TrendDirection:
        if isinstance(value, str):
            try:
                value = TrendDirection(value.lower())
            except ValueError as exc:
                raise PatternError(f"unknown trend direction {value!r}") from exc
        if value not in DIRECTIONAL and value is not TrendDirection.FLAT:
            raise PatternError(
                f"{value} is a REFUSAL, not a direction — a pattern cannot fire on "
                "'we cannot see enough of this to say'")
        return value


class CohortCondition(_Base):
    """`{kind: cohort, metric: m, op: percentile_lte, value: 2500}`

    The population floor lives with the kind (`MIN_COHORT_POPULATION`), not with the pattern.
    """

    kind: Literal[ConditionKind.COHORT] = ConditionKind.COHORT
    metric: str
    op: CohortOp
    value: int | str

    @model_validator(mode="after")
    def _shape(self) -> CohortCondition:
        if self.op is CohortOp.BAND_IS:
            if not isinstance(self.value, str):
                raise PatternError("`band_is` takes a band label, e.g. D1")
            try:
                CohortBand(self.value)
            except ValueError as exc:
                raise PatternError(f"unknown cohort band {self.value!r}") from exc
        elif isinstance(self.value, bool) or not isinstance(self.value, int):
            raise PatternError(f"`{self.op.value}` takes a percentile in basis points")
        elif not 0 <= self.value <= 10_000:
            raise PatternError(f"a percentile is 0..10000 basis points, got {self.value}")
        return self


class AnomalyCondition(_Base):
    """`{kind: anomaly, metric: m, direction: below}` — deviation against its OWN baseline."""

    kind: Literal[ConditionKind.ANOMALY] = ConditionKind.ANOMALY
    metric: str
    direction: AnomalyDirection
    #: An optional additional floor on how far off it must be, in basis points of MAD. The
    #: PERIODS floor is not declarable — that one lives with the kind.
    min_z_like_bp: int | None = None

    @field_validator("min_z_like_bp", mode="before")
    @classmethod
    def _floor(cls, value: Any) -> int | None:
        if value is None:
            return None
        no_float(value, "min_z_like_bp")
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise PatternError("min_z_like_bp is a non-negative integer in basis points")
        return value


class ObservationCondition(_Base):
    """`{kind: observation, kind_name: migration_discussed, within_days: 60}`"""

    kind: Literal[ConditionKind.OBSERVATION] = ConditionKind.OBSERVATION
    kind_name: str
    #: How recent the observation must be, relative to `eval_time`. `None` means any active
    #: observation, however old — which is legitimate for a durable statement ("they told us they
    #: are migrating") and wrong for a perishable one, so it is stated per pattern.
    within_days: int | None = None

    @field_validator("within_days", mode="before")
    @classmethod
    def _window(cls, value: Any) -> int | None:
        if value is None:
            return None
        no_float(value, "within_days")
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            raise PatternError("within_days is a positive whole number of days")
        return value

    @property
    def field_path(self) -> str:
        return f"observation.{self.kind_name}"


Condition = Annotated[
    Union[FactCondition, EdgeCondition, TemporalCondition, AbsenceCondition,
          TrendCondition, CohortCondition, AnomalyCondition, ObservationCondition],
    Field(discriminator="kind")]


class OptionalSignal(_Base):
    """A condition that RAISES match strength and never gates the fire.

    Kept as a wrapper around a real `Condition` rather than as a parallel type with a `weight_bp`
    field, so an optional signal and a required condition are evaluated by exactly the same code.
    Two evaluators for one grammar is how a pattern comes to mean one thing in the required list
    and another in the optional one.
    """

    condition: Condition
    #: What a satisfied signal adds to `match_strength_bp`. Positive: a "signal" that lowers
    #: strength is a required condition written backwards.
    weight_bp: int

    @field_validator("weight_bp", mode="before")
    @classmethod
    def _weight(cls, value: Any) -> int:
        no_float(value, "weight_bp")
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            raise PatternError("weight_bp is a positive integer in basis points")
        if value > MAX_MATCH_STRENGTH_BP:
            raise PatternError(f"weight_bp {value} exceeds the {MAX_MATCH_STRENGTH_BP} scale")
        return value


class FireRate(_Base):
    """What the pattern's author expects it to do, declared BEFORE it is allowed to activate.

    Doc 06's first failure mode is *"pattern too loose — fires constantly, becomes noise"* and its
    mitigation is this number: exceeding it 10x blocks activation. A pattern with no declared rate
    has nothing to be compared against, so the schema requires one and registration fails without
    it. This is the guard against the failure Layer 1 saw from the other side — fifteen dead rules
    and a green suite — pointed at the opposite direction.
    """

    #: Fires per 100 ANCHORS per 30 days. Per anchor and not per org, because "12 fires" means
    #: nothing without knowing whether the org has 20 contracts or 20,000.
    per_100_anchors_per_30d: int

    @field_validator("per_100_anchors_per_30d", mode="before")
    @classmethod
    def _rate(cls, value: Any) -> int:
        no_float(value, "per_100_anchors_per_30d")
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            raise PatternError(
                "expected_fire_rate.per_100_anchors_per_30d must be a positive integer — a "
                "pattern that expects to never fire cannot be measured against anything")
        if value > 100:
            raise PatternError(
                "a pattern cannot expect to fire on more than 100 of every 100 anchors")
        return value


class Evidence(_Base):
    """The two fixtures every pattern ships with: one that fires and one that does not.

    Named rather than merely tested, because doc 06 asks for `first_evidence` on every pattern and
    the negative fixture is the half people skip. A pattern with only a positive fixture has been
    shown to fire; it has not been shown to DISCRIMINATE, and a pattern that matches everything
    passes a positive fixture perfectly.
    """

    positive: str
    negative: str


class Pattern(_Base):
    """One declared, detectable situation. Data — the only Python that reads it is the evaluator."""

    pattern_id: str
    version: int = 1
    #: Which business domains may see this pattern. Sorted so two loads of one file produce
    #: byte-identical objects.
    domain: tuple[str, ...] = ()
    #: What kind of node this pattern is ABOUT. The cheap rejection, and it runs first.
    anchor_node_type: str
    conditions: tuple[Condition, ...]
    optional_signals: tuple[OptionalSignal, ...] = ()
    #: What a match becomes. Provisional: L2.7.3 clustering may merge it into another situation.
    situation_type: str
    expected_fire_rate: FireRate
    #: Who reviews this pattern when it misfires. A person, not a team alias that nobody reads.
    owner: str
    first_evidence: Evidence

    @field_validator("domain", mode="before")
    @classmethod
    def _domains(cls, value: Any) -> tuple[str, ...]:
        if value is None:
            return ()
        if isinstance(value, str):
            value = [value]
        return tuple(sorted({str(v) for v in value}))

    @field_validator("pattern_id", "situation_type", "anchor_node_type", "owner", mode="before")
    @classmethod
    def _text(cls, value: Any) -> str:
        text = str(value or "").strip()
        if not text:
            raise PatternError("pattern_id, anchor_node_type, situation_type and owner are all "
                               "required and none of them may be blank")
        return text

    @field_validator("version", mode="before")
    @classmethod
    def _version(cls, value: Any) -> int:
        no_float(value, "version")
        if isinstance(value, bool) or not isinstance(value, int) or value < 1:
            raise PatternError("version is a whole number starting at 1")
        return value

    @model_validator(mode="after")
    def _at_least_one_condition(self) -> Pattern:
        if not self.conditions:
            raise PatternError(
                f"pattern {self.pattern_id!r} declares no conditions — a pattern with no "
                "conditions matches every anchor of its type, which is the 'fires on everything' "
                "failure with no way to measure it")
        return self

    @property
    def key(self) -> tuple[str, int]:
        return (self.pattern_id, self.version)

    def as_record(self) -> dict[str, Any]:
        """The pattern as a plain, ordered record — what the report script and the API print."""
        return {"pattern_id": self.pattern_id, "version": self.version,
                "domain": list(self.domain), "anchor_node_type": self.anchor_node_type,
                "situation_type": self.situation_type, "owner": self.owner,
                "conditions": [c.model_dump(mode="json", by_alias=True) for c in self.conditions],
                "optional_signals": [s.model_dump(mode="json", by_alias=True)
                                     for s in self.optional_signals],
                "expected_fire_rate_per_100_anchors_per_30d":
                    self.expected_fire_rate.per_100_anchors_per_30d}


def combined_strength_bp(weights: tuple[int, ...]) -> int:
    """`BASE_MATCH_STRENGTH_BP` plus the satisfied optional weights, CLAMPED. Integer only.

    ONE construction, several callers: the evaluator computes it while it is looking at the
    signals, and `scorer.score_candidate` reports it. Two copies of this sum is how a candidate
    comes to disagree with the match that produced it about how strong the match was.
    """
    total = BASE_MATCH_STRENGTH_BP
    for weight in weights:
        total += int(weight)
    return min(MAX_MATCH_STRENGTH_BP, total)


def days_between(later: datetime, earlier: datetime) -> int:
    """Whole days, truncated toward zero, from two aware instants. No float, no clock.

    Used for every temporal comparison and every interval a card prints, so the number on the card
    and the number the condition tested are the same arithmetic.
    """
    return int((later - earlier).total_seconds()) // 86_400


__all__ = ["ANCHOR_REF", "AUTHORITY_THRESHOLD_REF", "BASE_MATCH_STRENGTH_BP",
           "MAX_MATCH_STRENGTH_BP", "NUMERIC_FACT_OPS", "REFERENCES", "AbsenceCondition",
           "AnomalyCondition", "CohortCondition", "CohortOp", "Condition", "ConditionKind",
           "EdgeCondition", "EdgeOp", "Evidence", "FactCondition", "FactOp", "FireRate",
           "ObservationCondition", "OptionalSignal", "Pattern", "PatternError",
           "TemporalCondition", "TemporalOp", "TrendCondition", "combined_strength_bp",
           "days_between", "no_float"]
