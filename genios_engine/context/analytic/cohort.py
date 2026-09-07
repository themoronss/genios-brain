"""L2.4.4 · the COHORT BUILDER (BLG-09) — WHO a tenant is compared against, and how a cohort
gets authored in the first place.

A metric reading means nothing alone. "Your close rate is 22%" is not information until it is
"22% against a peer cohort median of 31%", and the difference between those two sentences is
this file: it decides which population the second number comes from.

**Law 3 of Layer 2: cohorts are DECLARED, never clustered.** A cohort produced by k-means is a
cohort nobody can explain, that changes on every re-fit, and that a founder cannot correct. A
cohort defined as *"accounts with ARR 10k-50k, onboarded in the last two quarters, on the Growth
plan"* is explainable, stable, correctable and citable on a card. Nothing here imports a
clustering library, and `test_cohort.py` greps the whole analytic tree to keep it that way.

WHAT CROSSES THE TENANT BOUNDARY, because a cohort is the one construct in this engine whose
whole purpose is to let one subject's number be read against other subjects':

    NOTHING CROSSES IT. Every cohort in v2 is WITHIN ONE TENANT. `cohort_definitions.org_id` and
    `cohort_membership.org_id` are the leading key of every read below; the metric values a
    position is computed from are read from `metric_history` under the same `org_id`; and
    `CohortPosition` — the only object that leaves this module for a card — carries a percentile,
    a band, a population COUNT and three distribution boundaries, and carries no node id, no
    display name and no counterparty of any kind. A percentile is fine; a name is not.

    Doc 04 L2.4.6-U2 states the cross-org version as a DECISION, not an omission: *"cross-tenant
    comparison is a product decision with a compliance surface"* and it requires a k-anonymity
    floor, an explicit opt-in and a legal review. Until those exist, a function here that took two
    org ids would be the whole leak, so none does — every entry point takes exactly one `org_id`
    and every statement filters on it. `test_cohort.py` proves that structurally (no SQL in this
    module touches a cohort table without `org_id`) and behaviourally (two orgs, one of them
    holding a node with the SAME node_id, and nothing of the second reachable from the first's
    position).

DETERMINISM. Integer basis points, no float in any measure path, no clock, no LLM anywhere on
the sweep path. `eval_time` is a parameter of every function that needs an instant, so the same
graph evaluated twice produces byte-identical predicates, byte-identical ids and a byte-identical
`CohortPosition`. The one model site in this component is M-9 (`propose_cohort`), which is on
demand only, drafts a predicate for a HUMAN to approve, and never computes a number — the
population count, the samples and every percentile are computed here.

HOW THE TWO TABLES ARE BOUNDED, because `expertise_packages` reached 181 MB over 345 rows and put
this database into read-only, and a membership table refreshed on every sweep is exactly that
shape:

  1. `cohort_definitions` NEVER GROWS ON A SWEEP. System cohorts have STABLE ids per slot
     (`_system_cohort_id`) and are UPSERTED — a quartile family whose boundaries moved rewrites
     four rows, it does not append four. Authored cohorts are content-addressed, so re-approving
     the same predicate is the same row. `MAX_COHORTS_PER_ORG` caps the total.
  2. `cohort_membership` IS KEYED ON THE PERIOD, not on the sweep. `joined_at` is the ISO WEEK
     start (`history.period_start`, the one shared boundary function), so a node joining a cohort
     produces AT MOST ONE ROW PER WEEK however many sweeps run in that week — the primary key
     turns every later sweep into an in-place update. Row count is set by the calendar and by
     membership churn, never by sweep cadence.
  3. A SWEEP THAT RUNS TWICE IN ONE PERIOD IS A NO-OP. Joins upsert onto the same key; misses
     advance the hysteresis streak only when `evaluated_at < eval_time`, so replaying a sweep at
     the same instant cannot walk a node out of its cohort. This is the idempotency the sampler
     gets from its primary key, applied to a table whose writes are stateful.
  4. HYSTERESIS COSTS ROWS TOO, and that is the point: a node must fail the predicate on TWO
     consecutive evaluations before `left_at` is set, so a flapping value cannot produce a
     join/leave pair per sweep.
  5. A PER-SWEEP WRITE BUDGET (`MEMBERSHIP_WRITE_BUDGET`) caps how many membership rows one org's
     sweep may touch, so a 50k-node org's first sweep cannot become a 500k-statement transaction.
     Work not done this sweep is done by the next one; the budget is reported, never silent.
  6. RETENTION on the drain path: closed stints (`left_at` set) older than
     `MEMBERSHIP_RETENTION_MONTHS` are pruned by the same sweep that refreshes membership,
     through the `cohort_membership_changes` index. Open membership is never pruned — a cohort a
     node has been in for three years is one row, and deleting it would delete the cohort.

  Steady state: rows <= nodes x active cohorts x stints-in-window. A 2,000-node org with 20
  cohorts and quarterly churn settles around 160,000 rows and STOPS.

Both tables are named in `api/account_routes._ORG_SCOPED_TABLES` (that loop has no try/except, so
a name missing from it leaks a deleted tenant's membership silently) and both cascade from `orgs`.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from enum import Enum
from typing import Any, Callable, Iterable, Mapping, Sequence

from sqlalchemy import text

from genios_engine.contracts.analytic import MIN_COHORT_POPULATION, CohortBand, CohortPosition
from genios_engine.contracts.validators import require_aware, require_identifier, require_text
from genios_engine.context.analytic.history import (HISTORY_TABLE, RETENTION_MONTHS, MetricGrain,
                                                    months_before, period_start)
from genios_engine.platform.canonical import canonical_dumps, semantic_hash

# =================================================================================================
# THE NUMBERS
# =================================================================================================

#: The two tables this module owns. Named constants because they appear in the erasure list, in
#: the migration and in five statements below, and a string typed six times is a table that gets
#: renamed five times.
COHORT_DEFINITION_TABLE = "cohort_definitions"
COHORT_MEMBERSHIP_TABLE = "cohort_membership"

#: Consecutive failed evaluations before `left_at` is set (doc 04's hysteresis mitigation for
#: "membership churns every sweep -> noisy joined/left events"). Two, not three: one sweep of
#: tolerance absorbs a fact that was briefly missing during a re-derive, and three would make a
#: genuine departure take a fortnight to show up.
MISSES_BEFORE_LEAVING = 2

#: A quartile family needs four slots each at or above the population floor, so it needs at least
#: this many members before it is worth generating at all. Below it the generator refuses the
#: whole family rather than shipping four cohorts nothing may be compared in.
MIN_QUARTILE_POPULATION = 4 * MIN_COHORT_POPULATION

#: Definition-count ceiling per tenant. Bounds `cohort_definitions` against an authoring loop and
#: bounds the SWEEP, which does one membership pass per active cohort.
MAX_COHORTS_PER_ORG = 64

#: Ceiling on the `deals_by_stage` family. A stage vocabulary is a small closed set on a healthy
#: graph; on an unhealthy one it is whatever free text a connector wrote, and without a cap that
#: is one cohort per typo.
MAX_STAGE_COHORTS = 12

#: Membership rows one org's sweep may write. The sampler's point budget, for a table whose write
#: amplification is per-node rather than per-period.
MEMBERSHIP_WRITE_BUDGET = 20_000

#: Closed stints older than this are pruned on the drain path. The same 24 months `metric_history`
#: keeps, and derived from it rather than restated: a position computed in March must be
#: explainable in September against the membership that produced it, and neither window may drift
#: from the other.
MEMBERSHIP_RETENTION_MONTHS = RETENTION_MONTHS

#: Share of a cohort's members whose metric value is unknown, above which no position is returned.
#: Doc 04 L2.4.5: "a series more than 40% gaps cannot support a trend claim" — the same reasoning
#: about a population rather than a series.
MAX_UNKNOWN_SHARE_BP = 4_000

#: Node types a cohort may be about (doc 04: `account | deal | person`), spelled in the graph's
#: own vocabulary — `graph_nodes.node_type` says `company`, not `account`.
COHORT_NODE_TYPES = ("company", "deal", "person")


# =================================================================================================
# THE FACT REGISTRY — what a predicate is allowed to name
# =================================================================================================

class FactKind(str, Enum):
    """What a registered fact HOLDS, which is what decides the operators it can answer.

    The kind is not decoration: `within_days` on a plan name and `gt` on a timestamp are both
    nonsense, and both are refused at definition time because the kind says so. Doing it by kind
    rather than by a per-fact operator list keeps the rule one table wide.
    """

    #: An integer measurement in its own unit — minor units, days, a count.
    NUMBER = "number"
    #: A proportion stored as a decimal in the graph (`derived.engagement` is 0.8333). Normalised
    #: to integer basis points on read, through `Decimal`, so nothing downstream sees a float.
    RATIO = "ratio"
    #: A short categorical string — a plan, a stage, an industry. Compared case-insensitively.
    TEXT = "text"
    #: An instant. Answers `within_days`, never `lt`/`gt`: "before March" is a comparison against
    #: a literal date that would silently age, and every horizon in this layer is relative to
    #: `eval_time` by design.
    MOMENT = "moment"
    #: A boolean.
    FLAG = "flag"


@dataclass(frozen=True, slots=True)
class FactDefinition:
    """One fact a predicate may reference, and the question it exists to answer.

    `question` is required for the same reason `TRENDED_METRICS` requires one: a registered name
    nobody can say a use for is a cohort dimension that will be authored against by accident.
    """

    name: str
    kind: FactKind
    node_types: frozenset[str]
    question: str
    #: May the quartile generator (U2) build a family on this fact? Only NUMBER facts, and only
    #: ones where a quartile is a sentence a human would say.
    quartilable: bool = False

    def __post_init__(self) -> None:
        require_identifier(self.name, "fact name")
        require_text(self.question, f"question for {self.name}")
        if not self.node_types:
            raise ValueError(f"{self.name} must say which node types it describes")
        unknown = sorted(set(self.node_types) - set(COHORT_NODE_TYPES))
        if unknown:
            raise ValueError(f"{self.name} names node types this engine has no cohorts for: "
                             f"{unknown}")
        if self.quartilable and self.kind is not FactKind.NUMBER:
            raise ValueError(f"{self.name} is not a NUMBER, so a quartile of it is not a number")


#: The registered set. Every name here is either a field `context/` actually writes to
#: `graph_facts` (the `derived.*`, `deal.*`, `thread.*`, `commitment.*` rows), a property of the
#: node row itself (`node.*`), or one of the four CRM facts doc 04's own example predicate names.
#:
#: The CRM four are registered even though no connector writes them yet, and that is deliberate
#: rather than aspirational: an unregistered name RAISES, so leaving them out would make doc 04's
#: worked example unwritable, while registering them costs nothing — a predicate over a fact
#: nothing writes matches nobody, and a quartile family over it is REFUSED for population rather
#: than shipped empty. Absence is answered honestly instead of by an exception a founder cannot act
#: on.
CORE_COHORT_FACTS: tuple[FactDefinition, ...] = (
    FactDefinition("node.type", FactKind.TEXT, frozenset(COHORT_NODE_TYPES),
                   "is this an account, a deal or a person?"),
    FactDefinition("node.name", FactKind.TEXT, frozenset(COHORT_NODE_TYPES),
                   "which named entity is this? (naming one is how a cohort excludes a house account)"),
    FactDefinition("node.tenure_days", FactKind.NUMBER, frozenset(COHORT_NODE_TYPES),
                   "how long has this entity been in the graph? — the tenure quartile family",
                   quartilable=True),
    FactDefinition("derived.engagement", FactKind.RATIO, frozenset({"company", "person"}),
                   "how engaged is this relationship, as a ratio of its own history?"),
    FactDefinition("derived.momentum", FactKind.RATIO, frozenset({"company", "person"}),
                   "is the relationship accelerating or slowing?"),
    FactDefinition("derived.sentiment", FactKind.RATIO, frozenset({"company", "person"}),
                   "how does this relationship read?"),
    FactDefinition("deal.stage", FactKind.TEXT, frozenset({"company", "deal"}),
                   "which pipeline stage is this deal in? — the `deals_by_stage` family"),
    FactDefinition("deal.status", FactKind.TEXT, frozenset({"company", "deal"}),
                   "is this deal open, won or lost?"),
    FactDefinition("deal.value", FactKind.NUMBER, frozenset({"company", "deal"}),
                   "how big is this deal, in minor units? — the deal-size quartile family",
                   quartilable=True),
    FactDefinition("deal.currency", FactKind.TEXT, frozenset({"company", "deal"}),
                   "what currency is this deal denominated in?"),
    FactDefinition("deal.last_inbound", FactKind.MOMENT, frozenset({"company", "deal"}),
                   "when did this deal last hear from the other side?"),
    FactDefinition("thread.ball_in_court", FactKind.TEXT, frozenset({"company", "person"}),
                   "who owes the next message?"),
    FactDefinition("thread.last_inbound", FactKind.MOMENT, frozenset({"company", "person"}),
                   "when did they last write to us?"),
    FactDefinition("thread.last_outbound", FactKind.MOMENT, frozenset({"company", "person"}),
                   "when did we last write to them?"),
    FactDefinition("commitment.due_at", FactKind.MOMENT, frozenset(COHORT_NODE_TYPES),
                   "when is the open commitment on this entity due?"),
    FactDefinition("commitment.action", FactKind.TEXT, frozenset(COHORT_NODE_TYPES),
                   "what did we say we would do?"),
    FactDefinition("account.arr_minor_units", FactKind.NUMBER, frozenset({"company"}),
                   "what does this account pay us? — the ARR quartile family", quartilable=True),
    FactDefinition("account.plan", FactKind.TEXT, frozenset({"company"}),
                   "which plan is this account on?"),
    FactDefinition("account.industry", FactKind.TEXT, frozenset({"company"}),
                   "what industry is this account in?"),
    FactDefinition("account.onboarded_at", FactKind.MOMENT, frozenset({"company"}),
                   "when did this account start?"),
    FactDefinition("account.churned_at", FactKind.MOMENT, frozenset({"company"}),
                   "when did this account leave? — the churn cohort doc 04 works through"),
)


class FactRegistry:
    """The closed set of names a predicate may reference.

    A class rather than a module dict for the reason `history.MetricRegistry` gives: a shared
    mutable constant is an import-time side effect waiting to happen, and a caller extending the
    registry for one org must not extend it for the process.
    """

    def __init__(self, definitions: Iterable[FactDefinition] = ()) -> None:
        self._by_name: dict[str, FactDefinition] = {}
        for definition in definitions:
            if definition.name in self._by_name:
                raise ValueError(f"{definition.name} is registered twice")
            self._by_name[definition.name] = definition

    def __contains__(self, name: object) -> bool:
        return isinstance(name, str) and name in self._by_name

    def __len__(self) -> int:
        return len(self._by_name)

    @property
    def names(self) -> tuple[str, ...]:
        return tuple(sorted(self._by_name))

    def get(self, name: str) -> FactDefinition | None:
        return self._by_name.get(name)

    def require(self, name: str) -> FactDefinition:
        """Doc 04's fourth failure mode, enforced at DEFINITION time.

        *"A predicate references a missing fact -> silent empty cohort"*. A cohort that matches
        nobody because the fact name was mistyped is indistinguishable from a cohort that matches
        nobody because the business has no such accounts, and the first is a bug while the second
        is an answer.
        """
        definition = self._by_name.get(name)
        if definition is None:
            raise PredicateError(
                f"{name!r} is not a registered cohort fact (known: {', '.join(self.names)}) — an "
                "unregistered name would evaluate to an empty cohort, which reads exactly like a "
                "true answer")
        return definition

    def quartilable(self) -> tuple[FactDefinition, ...]:
        return tuple(d for d in self._by_name.values() if d.quartilable)

    def with_definitions(self, *definitions: FactDefinition) -> FactRegistry:
        return FactRegistry((*self._by_name.values(), *definitions))


def default_fact_registry() -> FactRegistry:
    """The core facts. A function, not a constant — see `history.default_registry`."""
    return FactRegistry(CORE_COHORT_FACTS)


# =================================================================================================
# THE PREDICATE TREE — typed, interpreted in Python, never SQL
# =================================================================================================

class PredicateError(ValueError):
    """A predicate that cannot be evaluated honestly. ALWAYS raised at definition time.

    Never raised by `evaluate`: a parsed predicate is total over any facts it is handed, because a
    predicate that raised halfway through a sweep would leave a cohort's membership half-updated.
    """


class PredicateOp(str, Enum):
    """Doc 04's operator list, closed. Not a string that reaches SQL — see `evaluate`."""

    EQ = "eq"
    NE = "ne"
    IN = "in"
    LT = "lt"
    LTE = "lte"
    GT = "gt"
    GTE = "gte"
    BETWEEN = "between"
    WITHIN_DAYS = "within_days"
    EXISTS = "exists"
    MISSING = "missing"


class Combinator(str, Enum):
    ALL = "all"
    ANY = "any"
    NONE = "none"


#: Which operators each kind can answer. The single table that makes "greater than a plan name"
#: and "within 30 days of an ARR" unwritable rather than merely wrong.
_OPS_BY_KIND: Mapping[FactKind, frozenset[PredicateOp]] = {
    FactKind.NUMBER: frozenset({PredicateOp.EQ, PredicateOp.NE, PredicateOp.IN, PredicateOp.LT,
                                PredicateOp.LTE, PredicateOp.GT, PredicateOp.GTE,
                                PredicateOp.BETWEEN, PredicateOp.EXISTS, PredicateOp.MISSING}),
    FactKind.RATIO: frozenset({PredicateOp.EQ, PredicateOp.NE, PredicateOp.IN, PredicateOp.LT,
                               PredicateOp.LTE, PredicateOp.GT, PredicateOp.GTE,
                               PredicateOp.BETWEEN, PredicateOp.EXISTS, PredicateOp.MISSING}),
    FactKind.TEXT: frozenset({PredicateOp.EQ, PredicateOp.NE, PredicateOp.IN, PredicateOp.EXISTS,
                              PredicateOp.MISSING}),
    FactKind.MOMENT: frozenset({PredicateOp.WITHIN_DAYS, PredicateOp.EXISTS,
                                PredicateOp.MISSING}),
    FactKind.FLAG: frozenset({PredicateOp.EQ, PredicateOp.NE, PredicateOp.EXISTS,
                              PredicateOp.MISSING}),
}

#: Operators that take no value at all.
_NULLARY = frozenset({PredicateOp.EXISTS, PredicateOp.MISSING})


@dataclass(frozen=True, slots=True)
class Condition:
    """One leaf: a registered fact, an operator its kind can answer, and a normalised value.

    `kind` is bound HERE, at parse time, rather than passed to `evaluate` — which is what lets
    `evaluate` be a pure function of (predicate, facts, eval_time) with no registry argument, and
    therefore what lets a stored predicate be replayed years later without the registry it was
    written against.
    """

    fact: str
    op: PredicateOp
    kind: FactKind
    value: Any = None

    def as_json(self) -> dict[str, Any]:
        out: dict[str, Any] = {"fact": self.fact, "op": self.op.value}
        if self.op not in _NULLARY:
            out["value"] = list(self.value) if isinstance(self.value, tuple) else self.value
        return out

    def facts(self) -> frozenset[str]:
        return frozenset({self.fact})


@dataclass(frozen=True, slots=True)
class Group:
    """`all` / `any` / `none` over sub-predicates. Empty groups are refused at parse time."""

    combinator: Combinator
    terms: tuple["Predicate", ...]

    def as_json(self) -> dict[str, Any]:
        return {self.combinator.value: [t.as_json() for t in self.terms]}

    def facts(self) -> frozenset[str]:
        return frozenset().union(*(t.facts() for t in self.terms)) if self.terms else frozenset()


Predicate = Condition | Group

#: A tree deeper than this is not explainable on a card, which is the whole reason it is a tree
#: and not SQL. It is also the recursion bound on `parse_predicate`.
MAX_PREDICATE_DEPTH = 6
#: And a tree wider than this is a list of node ids wearing a predicate's clothes.
MAX_PREDICATE_TERMS = 24


def _require_int(value: Any, label: str) -> int:
    """No floats in a predicate, ever.

    A float threshold is not a rounding question: `arr > 1000.5` compared against values
    normalised through `Decimal` reclassifies whoever sits on the boundary depending on which
    build did the comparing, and membership that moves without the business moving is exactly
    what Law 3 exists to prevent.
    """
    if isinstance(value, bool) or not isinstance(value, int):
        raise PredicateError(f"{label} must be an integer — a float threshold silently "
                             f"reclassifies whoever sits on the boundary (got {value!r})")
    return value


def _normalise_predicate_value(definition: FactDefinition, op: PredicateOp, value: Any) -> Any:
    kind = definition.kind
    label = f"value for {definition.name} {op.value}"
    if op is PredicateOp.WITHIN_DAYS:
        days = _require_int(value, label)
        if days <= 0:
            raise PredicateError(f"{label} must be a positive number of days")
        return days
    if op is PredicateOp.BETWEEN:
        if not isinstance(value, (list, tuple)) or len(value) != 2:
            raise PredicateError(f"{label} must be a two-element [low, high]")
        low, high = (_require_int(v, label) for v in value)
        if low > high:
            raise PredicateError(f"{label} is inverted: [{low}, {high}] matches nothing")
        return (low, high)
    if op is PredicateOp.IN:
        if not isinstance(value, (list, tuple)) or not value:
            raise PredicateError(f"{label} must be a non-empty list")
        if len(value) > MAX_PREDICATE_TERMS:
            raise PredicateError(f"{label} lists {len(value)} members — a cohort is a rule, not "
                                 "an enumeration of the answer")
        return tuple(sorted({_normalise_scalar(kind, v, label) for v in value},
                            key=lambda v: (str(type(v)), v)))
    return _normalise_scalar(kind, value, label)


def _normalise_scalar(kind: FactKind, value: Any, label: str) -> Any:
    if kind in (FactKind.NUMBER, FactKind.RATIO):
        return _require_int(value, label)
    if kind is FactKind.FLAG:
        if not isinstance(value, bool):
            raise PredicateError(f"{label} must be true or false")
        return value
    if kind is FactKind.MOMENT:
        raise PredicateError(f"{label}: a moment is compared with within_days, never with a "
                             "literal date — a literal ages, and this layer's horizons are all "
                             "relative to eval_time")
    return require_text(value, label).lower()


def parse_predicate(raw: Any, *, registry: FactRegistry | None = None,
                    _depth: int = 0) -> Predicate:
    """The typed predicate tree, from the JSON a human or M-9 wrote. RAISES AT DEFINITION TIME.

    Doc 04's hard rule 1: *"NO FREE SQL FROM PREDICATES"*. The tree is interpreted in Python
    against loaded node facts (`evaluate`), and no function in this module ever interpolates a
    predicate — or any part of one — into a statement. `test_cohort.py` greps this file for
    f-string SQL to keep that structural rather than habitual.
    """
    registry = registry or default_fact_registry()
    if _depth > MAX_PREDICATE_DEPTH:
        raise PredicateError(f"predicate nests deeper than {MAX_PREDICATE_DEPTH} — a cohort "
                             "nobody can read is a cohort nobody can correct")
    if not isinstance(raw, Mapping):
        raise PredicateError(f"a predicate is an object, got {type(raw).__name__}")
    keys = set(raw)
    combinators = {c.value for c in Combinator} & keys
    if combinators:
        if len(keys) != 1:
            raise PredicateError(f"a combinator node carries exactly one key, got {sorted(keys)}")
        name = combinators.pop()
        terms_raw = raw[name]
        if not isinstance(terms_raw, (list, tuple)) or not terms_raw:
            raise PredicateError(f"{name!r} needs at least one term — an empty group matches "
                                 "either everything or nothing, and which is not visible")
        if len(terms_raw) > MAX_PREDICATE_TERMS:
            raise PredicateError(f"{name!r} carries {len(terms_raw)} terms (max "
                                 f"{MAX_PREDICATE_TERMS})")
        return Group(Combinator(name),
                     tuple(parse_predicate(t, registry=registry, _depth=_depth + 1)
                           for t in terms_raw))
    if "fact" not in raw or "op" not in raw:
        raise PredicateError(f"a condition needs 'fact' and 'op', got {sorted(keys)}")
    unknown = keys - {"fact", "op", "value"}
    if unknown:
        raise PredicateError(f"unsupported keys on a condition: {sorted(unknown)}")
    definition = registry.require(str(raw["fact"]))
    try:
        op = PredicateOp(str(raw["op"]))
    except ValueError:
        raise PredicateError(
            f"{raw['op']!r} is not one of the supported operators "
            f"({', '.join(o.value for o in PredicateOp)})") from None
    if op not in _OPS_BY_KIND[definition.kind]:
        raise PredicateError(
            f"{definition.name} is a {definition.kind.value} and cannot answer {op.value!r} "
            f"(it answers: {', '.join(sorted(o.value for o in _OPS_BY_KIND[definition.kind]))})")
    if op in _NULLARY:
        if "value" in raw and raw["value"] is not None:
            raise PredicateError(f"{op.value} takes no value")
        return Condition(definition.name, op, definition.kind)
    if "value" not in raw:
        raise PredicateError(f"{op.value} on {definition.name} needs a value")
    return Condition(definition.name, op, definition.kind,
                     _normalise_predicate_value(definition, op, raw["value"]))


def predicate_json(predicate: Predicate) -> dict[str, Any]:
    """The predicate as storable, diffable JSON. Round-trips through `parse_predicate`."""
    return predicate.as_json()


def predicate_fingerprint(predicate: Predicate) -> str:
    """Content address of a predicate — the same canonical hash the rest of the engine uses."""
    return semantic_hash(predicate.as_json())


# ── evaluation ───────────────────────────────────────────────────────────────────────────────

def _as_decimal(value: Any) -> Decimal | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return Decimal(value)
    if isinstance(value, Decimal):
        return value
    if isinstance(value, float):
        # `Decimal(repr(v))` and NOT `Decimal(v)`: the second carries the binary expansion
        # (0.1 -> 0.1000000000000000055511151231257827), and a boundary comparison against it is
        # decided by a bit nobody wrote. `derived.py` writes these facts as `repr(round(v, 4))`,
        # so the decimal string is the value the graph actually meant.
        return Decimal(repr(value))
    if isinstance(value, str):
        try:
            return Decimal(value.strip())
        except (InvalidOperation, ValueError):
            return None
    return None


def _as_int_measure(value: Any) -> int | None:
    number = _as_decimal(value)
    if number is None:
        return None
    return int(number.to_integral_value(rounding="ROUND_HALF_EVEN"))


def _as_ratio_bp(value: Any) -> int | None:
    """A decimal ratio as integer basis points. `0.8333` -> `8333`, exactly and once."""
    number = _as_decimal(value)
    if number is None:
        return None
    return int((number * 10_000).to_integral_value(rounding="ROUND_HALF_EVEN"))


def _as_moment(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        try:
            return require_aware(value, "moment")
        except ValueError:
            return None
    if isinstance(value, str):
        raw = value.strip().replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(raw)
        except ValueError:
            return None
        return parsed if parsed.tzinfo is not None else None
    return None


def normalise_fact(kind: FactKind, value: Any) -> Any:
    """A raw `graph_facts` value in the shape its kind compares in, or None for "not known".

    None is the ONLY absence. A fact whose stored value cannot be read as its kind — a plan name
    where a number belongs — is absent rather than zero, for the reason the sampler gives about
    `deal.value`: a fabricated zero puts a node in a cohort it does not belong to and is
    indistinguishable, downstream, from a real reading.
    """
    if value is None:
        return None
    if kind is FactKind.NUMBER:
        return _as_int_measure(value)
    if kind is FactKind.RATIO:
        return _as_ratio_bp(value)
    if kind is FactKind.MOMENT:
        return _as_moment(value)
    if kind is FactKind.FLAG:
        return value if isinstance(value, bool) else None
    if isinstance(value, (str, int)) and not isinstance(value, bool):
        return str(value).strip().lower() or None
    return None


def _whole_days(later: datetime, earlier: datetime) -> int:
    return int((later - earlier).total_seconds()) // 86_400


def _evaluate_condition(condition: Condition, facts: Mapping[str, Any],
                        eval_time: datetime) -> bool:
    held = normalise_fact(condition.kind, facts.get(condition.fact))
    if condition.op is PredicateOp.EXISTS:
        return held is not None
    if condition.op is PredicateOp.MISSING:
        return held is None
    if held is None:
        # Every other operator is a claim ABOUT a value. A node with no such fact fails the claim
        # rather than raising — `missing` is how a predicate asks about absence, and doc 04 lists
        # both operators precisely so absence never has to be inferred from a comparison.
        return False
    if condition.op is PredicateOp.WITHIN_DAYS:
        if not isinstance(held, datetime):
            return False
        elapsed = _whole_days(eval_time, held)
        # Backward-looking, and only backward: "onboarded in the last 180 days". A moment in the
        # future is not in the last N days, and treating it as one would put next quarter's
        # renewal in this quarter's churn cohort.
        return 0 <= elapsed <= condition.value
    if condition.op is PredicateOp.EQ:
        return held == condition.value
    if condition.op is PredicateOp.NE:
        return held != condition.value
    if condition.op is PredicateOp.IN:
        return held in condition.value
    if condition.op is PredicateOp.BETWEEN:
        low, high = condition.value
        return low <= held <= high
    if not isinstance(held, int) or isinstance(held, bool):
        return False
    if condition.op is PredicateOp.LT:
        return held < condition.value
    if condition.op is PredicateOp.LTE:
        return held <= condition.value
    if condition.op is PredicateOp.GT:
        return held > condition.value
    return held >= condition.value


def evaluate(predicate: Predicate, node_facts: Mapping[str, Any], *, eval_time: datetime) -> bool:
    """Is this node in the cohort? PURE — no database, no clock, no model.

    Total by construction: it never raises on a node, whatever its facts hold, because a predicate
    that threw on one member would abandon a membership refresh halfway through and leave the
    table describing a population that never existed.
    """
    eval_time = require_aware(eval_time, "eval_time")
    return _evaluate(predicate, node_facts, eval_time)


def _evaluate(predicate: Predicate, node_facts: Mapping[str, Any], eval_time: datetime) -> bool:
    if isinstance(predicate, Condition):
        return _evaluate_condition(predicate, node_facts, eval_time)
    results = (_evaluate(term, node_facts, eval_time) for term in predicate.terms)
    if predicate.combinator is Combinator.ALL:
        return all(results)
    if predicate.combinator is Combinator.ANY:
        return any(results)
    return not any(results)


# =================================================================================================
# COHORT DEFINITIONS (U1)
# =================================================================================================

#: `created_by` for anything this module generates. A human's id never looks like this, and
#: `approve_proposal` refuses to store a `created_by` that does — the model drafted, the person
#: owns it.
SYSTEM_AUTHOR = "system:default"


@dataclass(frozen=True, slots=True)
class CohortDefinition:
    """A cohort: a predicate a human (or a human-approved draft) wrote, and who wrote it."""

    cohort_id: str
    org_id: str
    name: str
    node_type: str
    predicate: Predicate
    created_by: str
    created_at: datetime
    active: bool = True

    @property
    def system_owned(self) -> bool:
        return self.created_by == SYSTEM_AUTHOR

    def as_row(self) -> dict[str, Any]:
        return {"cohort_id": self.cohort_id, "org_id": self.org_id, "name": self.name,
                "node_type": self.node_type, "predicate": canonical_dumps(self.predicate.as_json()),
                "created_by": self.created_by, "created_at": self.created_at,
                "active": self.active}


def _system_cohort_id(org_id: str, family: str, slot: str) -> str:
    """A STABLE id per (org, family, slot) — the mechanism that keeps `cohort_definitions` from
    growing on a sweep.

    A quartile family is regenerated every sweep and its boundaries move as the population moves.
    Content-addressing the id would mint a new cohort every time ARR shifted, orphan the old one's
    membership, and grow both tables without a single new customer. The slot is the identity;
    the boundaries are the current definition of it.
    """
    return f"coh_{semantic_hash([org_id, family, slot])[:20]}"


def _authored_cohort_id(org_id: str, node_type: str, name: str, predicate: Predicate) -> str:
    """Content-addressed: approving the same cohort twice is the same row, not two."""
    return f"coh_{semantic_hash([org_id, node_type, name.strip().lower(), predicate.as_json()])[:20]}"


def define_cohort(*, org_id: str, name: str, node_type: str, predicate: Any, created_by: str,
                  eval_time: datetime, registry: FactRegistry | None = None,
                  cohort_id: str | None = None, active: bool = True) -> CohortDefinition:
    """Author a cohort. Every refusal in here fires at DEFINITION time, on purpose.

    Doc 04's failure table puts three of its four mitigations at this moment rather than at
    evaluation: an unregistered fact name, an operator the fact's kind cannot answer, and a
    predicate that describes a node type its facts do not belong to. All three produce the same
    symptom later — an empty cohort — and an empty cohort is a valid answer, so the error has to
    arrive while somebody is still looking at what they wrote.
    """
    registry = registry or default_fact_registry()
    org_id = require_identifier(org_id, "org_id")
    name = require_text(name, "cohort name")
    node_type = require_text(node_type, "node_type").lower()
    eval_time = require_aware(eval_time, "eval_time")
    created_by = require_text(created_by, "created_by")
    if node_type not in COHORT_NODE_TYPES:
        raise PredicateError(f"a cohort is over {', '.join(COHORT_NODE_TYPES)}, not {node_type!r}")
    tree = predicate if isinstance(predicate, (Condition, Group)) else parse_predicate(
        predicate, registry=registry)
    for fact_name in sorted(tree.facts()):
        definition = registry.require(fact_name)
        if node_type not in definition.node_types:
            raise PredicateError(
                f"{fact_name} describes {', '.join(sorted(definition.node_types))} and this "
                f"cohort is over {node_type} — a predicate about a node type its facts never "
                "appear on is an empty cohort that looks like an answer")
    return CohortDefinition(
        cohort_id=cohort_id or _authored_cohort_id(org_id, node_type, name, tree),
        org_id=org_id, name=name, node_type=node_type, predicate=tree,
        created_by=created_by, created_at=eval_time, active=active)


# =================================================================================================
# QUARTILE COHORTS (U2) AND THE SHIPPED DEFAULTS
# =================================================================================================

class CohortRefusalReason(str, Enum):
    """Why no cohort — or no position — was produced. A refusal is a RETURN VALUE here, the way
    `INSUFFICIENT_HISTORY` is one in `TrendDirection`: "we cannot say" is an answer a card can
    render honestly, and an exception is not."""

    #: Doc 04's Law 2 floor. Two tenants do not make a peer group and neither do four accounts.
    INSUFFICIENT_POPULATION = "insufficient_population"
    #: Too many members have no reading for this metric to rank anyone against.
    INSUFFICIENT_COVERAGE = "insufficient_coverage"
    #: Every value is the same, so quartile boundaries collapse and three of four slots are empty.
    DEGENERATE_DISTRIBUTION = "degenerate_distribution"
    #: The subject is not in the cohort it was asked to be positioned in.
    SUBJECT_NOT_A_MEMBER = "subject_not_a_member"
    #: The subject has no known reading of this metric.
    SUBJECT_VALUE_UNKNOWN = "subject_value_unknown"
    #: The cohort id names no active definition for this tenant.
    NO_SUCH_COHORT = "no_such_cohort"


@dataclass(frozen=True, slots=True)
class CohortRefusal:
    """No position. Carries the population it refused on, so the reader can see how close it was."""

    reason: CohortRefusalReason
    cohort_id: str
    metric: str
    population_size: int
    computed_at: datetime
    detail: str = ""

    @property
    def is_position(self) -> bool:
        return False


@dataclass(frozen=True, slots=True)
class QuartileFamily:
    """Four cohorts over one numeric fact, with the boundaries they were cut at."""

    fact: str
    node_type: str
    boundaries_bp: tuple[int, int, int]
    definitions: tuple[CohortDefinition, ...]
    population: int


def _quantile(sorted_values: Sequence[int], q_bp: int) -> int:
    """Nearest-rank quantile, integer arithmetic only.

    `(q_bp * (n - 1)) // 10000` and not a float index: the same population must cut at the same
    boundary on every machine and in every build, and an index computed through a float is decided
    by a rounding rule nobody wrote down.
    """
    if not sorted_values:
        raise ValueError("a quantile of nothing")
    index = (q_bp * (len(sorted_values) - 1)) // 10_000
    return sorted_values[min(max(index, 0), len(sorted_values) - 1)]


def percentile_bp(values: Sequence[int], value: int) -> int:
    """Where `value` sits among `values`, in basis points. Nearest-rank, doc 04 L2.4.5 step 3.

    `rank = count(v <= value); percentile_bp = rank * 10000 // n`, integer throughout.
    `support_situations.percentile_bp` computes a DIFFERENT statistic (ties count as half) through
    float arithmetic, so it is deliberately not reused here: this layer's rule is that no float
    appears in a measure path, and a percentile that lands on 4999 or 5001 depending on a binary
    expansion is a card that says "below median" about a median performer. The two are named
    apart, and L2.4.5 owns reconciling the support module onto this one.
    """
    if not values:
        raise ValueError("a percentile within an empty population")
    rank = sum(1 for v in values if v <= value)
    return min(rank * 10_000 // len(values), 10_000)


def quartile_cohorts(*, org_id: str, fact: str, node_type: str, values: Mapping[str, int],
                     eval_time: datetime, registry: FactRegistry | None = None,
                     ) -> QuartileFamily | CohortRefusal:
    """U2 · four balanced cohorts over one registered numeric fact, or a refusal.

    Balanced BY CONSTRUCTION is the reason doc 04 ships quartiles rather than hand-cut bands: a
    cohort's usefulness is bounded by its population, and a boundary a human guessed produces one
    cohort of 90 and three of 3. Cutting on the population's own quartiles cannot.

    Refuses rather than degrades in two cases, and the second one matters more than it looks: a
    population where every value is identical has quartile boundaries that all collapse onto one
    number, and cutting it yields one cohort holding everybody and three holding nobody — four
    rows in the definitions table that can never produce a position.
    """
    registry = registry or default_fact_registry()
    definition = registry.require(fact)
    if not definition.quartilable:
        raise PredicateError(f"{fact} is not registered as quartilable — a quartile family is a "
                             "storage and membership commitment, so it is a deliberate act")
    eval_time = require_aware(eval_time, "eval_time")
    ordered = sorted(values.values())
    if len(ordered) < MIN_QUARTILE_POPULATION:
        return CohortRefusal(CohortRefusalReason.INSUFFICIENT_POPULATION,
                             _system_cohort_id(org_id, f"{fact}_quartile", "family"), fact,
                             len(ordered), eval_time,
                             f"{len(ordered)} known values, and four slots each need "
                             f"{MIN_COHORT_POPULATION}")
    b25, b50, b75 = (_quantile(ordered, 2_500), _quantile(ordered, 5_000),
                     _quantile(ordered, 7_500))
    if not b25 < b50 < b75:
        # The boundaries collapsed: this population is concentrated enough that a quartile cut
        # cannot separate anyone. Refused BEFORE the predicates are built, because a collapsed
        # slot would be `between [b25 + 1, b50]` with b25 == b50 — an inverted range, which
        # `parse_predicate` refuses as an authoring mistake. It is not one here, and a generator
        # that raised would take down the whole default family for a tenant whose accounts happen
        # to pay the same amount.
        return CohortRefusal(
            CohortRefusalReason.DEGENERATE_DISTRIBUTION,
            _system_cohort_id(org_id, f"{fact}_quartile", "family"), fact, len(ordered), eval_time,
            f"the quartile boundaries of {fact} collapse onto {b25}/{b50}/{b75} — the values are "
            "too concentrated for quartiles to separate anyone")
    slots = (
        ("q1", "bottom quartile", {"all": [{"fact": fact, "op": "lte", "value": b25}]}),
        ("q2", "lower-middle quartile",
         {"all": [{"fact": fact, "op": "between", "value": [b25 + 1, b50]}]}),
        ("q3", "upper-middle quartile",
         {"all": [{"fact": fact, "op": "between", "value": [b50 + 1, b75]}]}),
        ("q4", "top quartile", {"all": [{"fact": fact, "op": "gt", "value": b75}]}),
    )
    built: list[CohortDefinition] = []
    for slot, label, raw in slots:
        tree = parse_predicate(raw, registry=registry)
        members = sum(1 for value in ordered if _evaluate(tree, {fact: value}, eval_time))
        if members < MIN_COHORT_POPULATION:
            return CohortRefusal(
                CohortRefusalReason.DEGENERATE_DISTRIBUTION,
                _system_cohort_id(org_id, f"{fact}_quartile", slot), fact, len(ordered), eval_time,
                f"the {label} of {fact} holds {members} of {len(ordered)} — the values are too "
                "concentrated for quartiles to separate anyone")
        built.append(define_cohort(
            org_id=org_id, name=f"{fact} · {label}", node_type=node_type, predicate=tree,
            created_by=SYSTEM_AUTHOR, eval_time=eval_time, registry=registry,
            cohort_id=_system_cohort_id(org_id, f"{fact}_quartile", slot)))
    return QuartileFamily(fact=fact, node_type=node_type, boundaries_bp=(b25, b50, b75),
                          definitions=tuple(built), population=len(ordered))


@dataclass(frozen=True, slots=True)
class DefaultCohorts:
    """What the shipped families produced for one org, INCLUDING what they refused and why.

    The refusals are returned rather than logged because they are the honest answer to "why do I
    have no ARR cohorts?" — nobody writes that fact, so there is nothing to cut. An operator who
    cannot see that concludes the generator is broken.
    """

    definitions: tuple[CohortDefinition, ...] = ()
    refusals: tuple[CohortRefusal, ...] = ()


def default_cohorts(*, org_id: str, facts_by_type: Mapping[str, Mapping[str, Mapping[str, Any]]],
                    eval_time: datetime, registry: FactRegistry | None = None) -> DefaultCohorts:
    """The five families doc 04 ships so value exists before anybody authors anything:
    `all_active_accounts` · `accounts_by_arr_quartile` · `deals_by_stage` ·
    `accounts_by_tenure_quartile` · `deals_by_size_quartile`.
    """
    registry = registry or default_fact_registry()
    eval_time = require_aware(eval_time, "eval_time")
    definitions: list[CohortDefinition] = []
    refusals: list[CohortRefusal] = []

    accounts = facts_by_type.get("company", {})
    # `deal.*` facts live on the DEAL node where a connector made one and on the COMPANY node
    # otherwise — `derived.py` writes `deal.stage` onto the account when the pipeline is inferred
    # from correspondence. The family follows the facts rather than assuming a node type, because
    # a deal cohort declared over a node type this tenant has none of is an empty cohort that
    # looks exactly like a tenant with no deals.
    deals = facts_by_type.get("deal") or accounts
    deal_node_type = "deal" if facts_by_type.get("deal") else "company"

    definitions.append(define_cohort(
        org_id=org_id, name="All active accounts", node_type="company",
        predicate={"all": [{"fact": "node.type", "op": "eq", "value": "company"}]},
        created_by=SYSTEM_AUTHOR, eval_time=eval_time, registry=registry,
        cohort_id=_system_cohort_id(org_id, "all_active_accounts", "all")))

    for fact, node_type, source in (("account.arr_minor_units", "company", accounts),
                                    ("node.tenure_days", "company", accounts),
                                    ("deal.value", deal_node_type, deals)):
        outcome = quartile_cohorts(org_id=org_id, fact=fact, node_type=node_type,
                                   values=numeric_values(source, fact, registry=registry),
                                   eval_time=eval_time, registry=registry)
        if isinstance(outcome, CohortRefusal):
            refusals.append(outcome)
        else:
            definitions.extend(outcome.definitions)

    stages = sorted({str(normalise_fact(FactKind.TEXT, facts.get("deal.stage")))
                     for facts in deals.values()
                     if normalise_fact(FactKind.TEXT, facts.get("deal.stage")) is not None})
    for stage in stages[:MAX_STAGE_COHORTS]:
        definitions.append(define_cohort(
            org_id=org_id, name=f"Deals in stage · {stage}", node_type=deal_node_type,
            predicate={"all": [{"fact": "deal.stage", "op": "eq", "value": stage}]},
            created_by=SYSTEM_AUTHOR, eval_time=eval_time, registry=registry,
            cohort_id=_system_cohort_id(org_id, "deals_by_stage", stage)))

    return DefaultCohorts(tuple(definitions[:MAX_COHORTS_PER_ORG]), tuple(refusals))


def numeric_values(facts_by_node: Mapping[str, Mapping[str, Any]], fact: str, *,
                   registry: FactRegistry | None = None) -> dict[str, int]:
    """Every node's known integer value of one numeric fact. Unknown values are ABSENT, not zero."""
    registry = registry or default_fact_registry()
    definition = registry.require(fact)
    out: dict[str, int] = {}
    for node_id, facts in facts_by_node.items():
        value = normalise_fact(definition.kind, facts.get(fact))
        if isinstance(value, int) and not isinstance(value, bool):
            out[node_id] = value
    return out


# =================================================================================================
# READING THE GRAPH — one bulk read per sweep, org-scoped, no per-node round trip
# =================================================================================================

#: Current nodes only (`valid_to is null`), of the types cohorts are about, for ONE org.
_NODES_SQL = text(
    "select node_id, node_type, display_name, valid_from from graph_nodes "
    "where org_id = :o and valid_to is null and node_type = any(:types)")

#: Current active facts for ONE org, narrowed to the registered names. The field list travels as
#: a BOUND parameter (`= any(:fields)`), never as interpolated text — the same shape
#: `sampler._FACTS_SQL` uses. It is a closed registry constant rather than anything from a
#: predicate or a request, and pushing it into the query rather than filtering in Python is worth
#: it on a large tenant: a graph with half a million facts returns the twenty thousand a cohort
#: can be declared over.
_FACTS_SQL = text(
    "select subject_node_id as node_id, field, value from graph_facts "
    "where org_id = :o and valid_to is null and status = 'active' and field = any(:fields)")


def _decode(value: Any) -> Any:
    """`graph_facts.value` is jsonb and arrives as a str on some drivers, decoded on others."""
    if isinstance(value, str):
        import json
        try:
            return json.loads(value)
        except (ValueError, TypeError):
            return value
    return value


def load_node_facts(engine, org_id: str, *, node_types: Sequence[str], eval_time: datetime,
                    registry: FactRegistry | None = None,
                    ) -> dict[str, dict[str, dict[str, Any]]]:
    """`{node_type: {node_id: {fact: value}}}` for ONE org, in two queries.

    Two queries and not one per node: the reasoning pass that did O(nodes) round trips took thirty
    minutes on a 1,500-node org, and a membership refresh runs this for every cohort a tenant has.

    `node.tenure_days` is computed here rather than stored, from `valid_from` and the caller's
    `eval_time`, because it is the only fact in the registry that changes with nothing but the
    passage of time — persisting it would mean rewriting a row per node per day, which is the
    write amplification this whole layer is bounded against.
    """
    registry = registry or default_fact_registry()
    eval_time = require_aware(eval_time, "eval_time")
    wanted = sorted({t.lower() for t in node_types})
    with engine.connect() as conn:
        node_rows = conn.execute(_NODES_SQL, {"o": org_id, "types": wanted}).all()
        fact_rows = conn.execute(_FACTS_SQL,
                                 {"o": org_id, "fields": list(registry.names)}).all()

    by_type: dict[str, dict[str, dict[str, Any]]] = {t: {} for t in wanted}
    owner: dict[str, str] = {}
    for row in node_rows:
        node_type = str(row.node_type)
        node_id = str(row.node_id)
        first_seen = row.valid_from
        facts: dict[str, Any] = {"node.type": node_type, "node.name": row.display_name}
        if isinstance(first_seen, datetime) and first_seen.tzinfo is not None:
            facts["node.tenure_days"] = max(_whole_days(eval_time, first_seen), 0)
        by_type.setdefault(node_type, {})[node_id] = facts
        owner[node_id] = node_type
    for row in fact_rows:
        node_type = owner.get(str(row.node_id))
        if node_type is None:
            continue                                   # a fact about a superseded node version
        field = str(row.field)
        if field not in registry:
            continue                                   # unregistered: not a cohort dimension
        by_type[node_type][str(row.node_id)][field] = _decode(row.value)
    return by_type


def load_node_names(engine, org_id: str, node_ids: Sequence[str]) -> dict[str, str]:
    """Display names for M-9's five samples. ORG-SCOPED — a name is the one thing that must never
    be read across a tenant boundary, and this is the only function here that reads one at all."""
    if not node_ids:
        return {}
    with engine.connect() as conn:
        rows = conn.execute(text(
            "select node_id, display_name from graph_nodes "
            "where org_id = :o and valid_to is null and node_id = any(:ids)"),
            {"o": org_id, "ids": sorted(set(node_ids))}).all()
    return {str(r.node_id): str(r.display_name or r.node_id) for r in rows}


# =================================================================================================
# THE DEFINITION STORE
# =================================================================================================

_UPSERT_DEFINITION_SQL = text(
    f"insert into {COHORT_DEFINITION_TABLE} "
    "  (cohort_id, org_id, name, node_type, predicate, created_by, created_at, active) "
    "values (:cohort_id, :org_id, :name, :node_type, cast(:predicate as jsonb), :created_by, "
    "        :created_at, :active) "
    "on conflict (cohort_id) do update set name = excluded.name, "
    "  node_type = excluded.node_type, predicate = excluded.predicate, active = excluded.active "
    # The org guard on an UPSERT. `cohort_id` is content-addressed and carries the org, so a
    # collision across tenants is not reachable — and this clause is what makes that a guarantee
    # of the SQL rather than of the hash: another tenant's row cannot be rewritten by this
    # statement even if one were ever constructed.
    f"where {COHORT_DEFINITION_TABLE}.org_id = excluded.org_id")

_LOAD_DEFINITIONS_SQL = text(
    f"select cohort_id, org_id, name, node_type, predicate, created_by, created_at, active "
    f"from {COHORT_DEFINITION_TABLE} where org_id = :o and (:only_active = false or active) "
    "order by cohort_id")

_COUNT_DEFINITIONS_SQL = text(
    f"select count(*) from {COHORT_DEFINITION_TABLE} where org_id = :o and active")


def save_definitions(engine, definitions: Sequence[CohortDefinition]) -> int:
    """Upsert. A regenerated system family REWRITES its four rows; it never appends four."""
    if not definitions:
        return 0
    with engine.begin() as conn:
        conn.execute(_UPSERT_DEFINITION_SQL, [d.as_row() for d in definitions])
    return len(definitions)


def load_definitions(engine, org_id: str, *, only_active: bool = True,
                     registry: FactRegistry | None = None) -> tuple[CohortDefinition, ...]:
    """Every cohort of ONE tenant. A stored predicate that no longer parses — because a fact was
    de-registered under it — is skipped rather than raised on, so one dead definition cannot stop
    a sweep from refreshing the other twenty."""
    registry = registry or default_fact_registry()
    with engine.connect() as conn:
        rows = conn.execute(_LOAD_DEFINITIONS_SQL,
                            {"o": org_id, "only_active": not only_active}).all()
    out: list[CohortDefinition] = []
    for row in rows:
        try:
            predicate = parse_predicate(_decode(row.predicate), registry=registry)
        except PredicateError:
            continue
        out.append(CohortDefinition(
            cohort_id=str(row.cohort_id), org_id=str(row.org_id), name=str(row.name),
            node_type=str(row.node_type), predicate=predicate, created_by=str(row.created_by),
            created_at=require_aware(row.created_at, "created_at"), active=bool(row.active)))
    return tuple(out)


# =================================================================================================
# MEMBERSHIP (U1) AND ITS CHANGE EVENTS (U3)
# =================================================================================================

_OPEN_MEMBERS_SQL = text(
    f"select node_id, joined_at, miss_streak, evaluated_at from {COHORT_MEMBERSHIP_TABLE} "
    "where org_id = :o and cohort_id = :c and left_at is null")

_JOIN_SQL = text(
    f"insert into {COHORT_MEMBERSHIP_TABLE} "
    "  (org_id, cohort_id, node_id, joined_at, left_at, miss_streak, evaluated_at) "
    "values (:o, :c, :n, :joined_at, null, 0, :at) "
    "on conflict (org_id, cohort_id, node_id, joined_at) do update "
    "  set left_at = null, miss_streak = 0, evaluated_at = excluded.evaluated_at")

_HELD_SQL = text(
    f"update {COHORT_MEMBERSHIP_TABLE} set miss_streak = 0, evaluated_at = :at "
    "where org_id = :o and cohort_id = :c and node_id = :n and left_at is null "
    "  and (evaluated_at is null or evaluated_at < :at)")

_MISS_SQL = text(
    f"update {COHORT_MEMBERSHIP_TABLE} set miss_streak = miss_streak + 1, evaluated_at = :at "
    "where org_id = :o and cohort_id = :c and node_id = :n and left_at is null "
    # The idempotency guard. Without it, replaying a sweep at the same `eval_time` advances the
    # hysteresis streak a second time and walks a node out of a cohort it never left.
    "  and (evaluated_at is null or evaluated_at < :at)")

_LEAVE_SQL = text(
    f"update {COHORT_MEMBERSHIP_TABLE} set left_at = :at, evaluated_at = :at "
    "where org_id = :o and cohort_id = :c and node_id = :n and left_at is null")

_PRUNE_MEMBERSHIP_SQL = text(
    f"delete from {COHORT_MEMBERSHIP_TABLE} where org_id = :o and left_at is not null "
    "and left_at < :cutoff")

_MEMBERS_AT_SQL = text(
    f"select node_id from {COHORT_MEMBERSHIP_TABLE} where org_id = :o and cohort_id = :c "
    "and joined_at <= :at and (left_at is null or left_at > :at)")

_CHANGES_SQL = text(
    f"select node_id, joined_at, left_at, cohort_id from {COHORT_MEMBERSHIP_TABLE} "
    "where org_id = :o and ((joined_at >= :since and joined_at < :until) "
    "                    or (left_at   >= :since and left_at   < :until)) "
    "order by cohort_id, node_id, joined_at")


class CohortEventKind(str, Enum):
    JOINED = "joined_cohort"
    LEFT = "left_cohort"


@dataclass(frozen=True, slots=True)
class CohortEvent:
    """U3 · a membership TRANSITION. *"Three accounts dropped out of your healthy-engagement
    cohort this month"* is a pattern, and it is only visible if transitions are recorded.

    Deliberately NOT a `graph_observations` row. The transition is already recorded, exactly and
    idempotently, by the membership row's own `joined_at` / `left_at` — that is what doc 04 means
    by "membership is HISTORICAL". Writing a second row per transition into a table other passes
    read would (a) double this component's write amplification on the one table designed to append,
    and (b) be un-replayable: a re-run would emit the observation again, while `membership_changes`
    derives the same events from the state and returns the same answer every time.
    """

    kind: CohortEventKind
    cohort_id: str
    node_id: str
    at: datetime


@dataclass(frozen=True, slots=True)
class MembershipDelta:
    """What one cohort's refresh changed. Counts, plus the transitions as typed events."""

    cohort_id: str
    joined: tuple[str, ...] = ()
    left: tuple[str, ...] = ()
    held: int = 0
    evaluated: int = 0
    events: tuple[CohortEvent, ...] = ()
    budget_exhausted: bool = False

    @property
    def population_size(self) -> int:
        return self.held + len(self.joined)


class WriteBudget:
    """Membership writes one sweep may make. The sampler's point budget, for this table.

    A 50k-node org's first sweep touches 50k rows per cohort; without a ceiling that is a single
    transaction big enough to matter to every other tenant on the instance. Work not done is not
    lost — the next sweep starts where this one stopped, because membership is state, not a queue.
    """

    def __init__(self, limit: int = MEMBERSHIP_WRITE_BUDGET) -> None:
        self._left = max(int(limit), 0)
        self.spent = 0

    def take(self, n: int = 1) -> bool:
        if self._left < n:
            return False
        self._left -= n
        self.spent += n
        return True

    @property
    def exhausted(self) -> bool:
        return self._left <= 0


def refresh_membership(store, definition: CohortDefinition, *, eval_time: datetime,
                       node_facts: Mapping[str, Mapping[str, Any]] | None = None,
                       budget: WriteBudget | None = None) -> MembershipDelta:
    """Re-evaluate one cohort and write the transitions. Hysteresis, idempotence, and a budget.

    THE HYSTERESIS RULE (doc 04's fourth mitigation, and hard rule 4 of the reverse prompt): a
    node that fails the predicate ONCE stays in the cohort with its miss streak advanced; a node
    that fails TWICE consecutively leaves, with `left_at` set. Rows are never deleted — *"accounts
    that left this cohort last month"* is a churn signal and it is only askable if membership is
    historical.

    THE PERIOD RULE: `joined_at` is the ISO WEEK start, so a node joining produces one row per
    week however many sweeps run in it, and a sweep replayed at the same `eval_time` writes
    nothing new at all.
    """
    eval_time = require_aware(eval_time, "eval_time")
    stint = period_start(eval_time, MetricGrain.WEEK)
    budget = budget or WriteBudget()
    engine = getattr(store, "engine", store)
    facts = node_facts
    if facts is None:
        facts = load_node_facts(engine, definition.org_id, node_types=(definition.node_type,),
                                eval_time=eval_time).get(definition.node_type, {})
    matched = {node_id for node_id, node in facts.items()
               if _evaluate(definition.predicate, node, eval_time)}

    params = {"o": definition.org_id, "c": definition.cohort_id}
    joined: list[str] = []
    left: list[str] = []
    held = 0
    exhausted = False
    with engine.begin() as conn:
        open_rows = {str(r.node_id): r for r in conn.execute(_OPEN_MEMBERS_SQL, params).all()}
        joins: list[dict[str, Any]] = []
        holds: list[dict[str, Any]] = []
        misses: list[dict[str, Any]] = []
        leaves: list[dict[str, Any]] = []
        for node_id in sorted(matched):
            row = open_rows.get(node_id)
            if row is None:
                if not budget.take():
                    exhausted = True
                    break
                joins.append({**params, "n": node_id, "joined_at": stint, "at": eval_time})
                joined.append(node_id)
                continue
            held += 1
            if row.miss_streak:
                # A node that came back before the streak reached two: the streak resets, and no
                # transition is recorded because none happened. This is hysteresis paying off.
                if not budget.take():
                    exhausted = True
                    break
                holds.append({**params, "n": node_id, "at": eval_time})
        if not exhausted:
            for node_id, row in sorted(open_rows.items()):
                if node_id in matched:
                    continue
                evaluated_at = row.evaluated_at
                if evaluated_at is not None and evaluated_at.tzinfo is not None \
                        and evaluated_at >= eval_time:
                    held += 1                          # already judged at this instant: a replay
                    continue
                if not budget.take():
                    exhausted = True
                    break
                if int(row.miss_streak or 0) + 1 >= MISSES_BEFORE_LEAVING:
                    leaves.append({**params, "n": node_id, "at": eval_time})
                    left.append(node_id)
                else:
                    misses.append({**params, "n": node_id, "at": eval_time})
                    held += 1
        for statement, rows in ((_JOIN_SQL, joins), (_HELD_SQL, holds), (_MISS_SQL, misses),
                                (_LEAVE_SQL, leaves)):
            if rows:
                conn.execute(statement, rows)

    events = tuple(
        [CohortEvent(CohortEventKind.JOINED, definition.cohort_id, n, stint) for n in joined]
        + [CohortEvent(CohortEventKind.LEFT, definition.cohort_id, n, eval_time) for n in left])
    return MembershipDelta(cohort_id=definition.cohort_id, joined=tuple(joined),
                           left=tuple(left), held=held, evaluated=len(facts), events=events,
                           budget_exhausted=exhausted)


def membership_changes(store, org_id: str, *, since: datetime, until: datetime,
                       ) -> tuple[CohortEvent, ...]:
    """U3's reader: every join and leave in a window, for ONE tenant, derived from the state.

    Idempotent by construction — asking twice returns the same events, because the events ARE the
    membership rows rather than a second ledger that could disagree with them.
    """
    since = require_aware(since, "since")
    until = require_aware(until, "until")
    engine = getattr(store, "engine", store)
    with engine.connect() as conn:
        rows = conn.execute(_CHANGES_SQL, {"o": org_id, "since": since, "until": until}).all()
    events: list[CohortEvent] = []
    for row in rows:
        joined_at, left_at = row.joined_at, row.left_at
        if joined_at is not None and since <= joined_at < until:
            events.append(CohortEvent(CohortEventKind.JOINED, str(row.cohort_id),
                                      str(row.node_id), joined_at))
        if left_at is not None and since <= left_at < until:
            events.append(CohortEvent(CohortEventKind.LEFT, str(row.cohort_id),
                                      str(row.node_id), left_at))
    return tuple(sorted(events, key=lambda e: (e.at, e.cohort_id, e.node_id, e.kind.value)))


def prune_membership(store, org_id: str, *, eval_time: datetime) -> int:
    """Retention: CLOSED stints older than 24 months. Open membership is never pruned.

    The asymmetry is the whole design. A node that has been in a cohort for three years is ONE row
    and deleting it would delete the cohort; a stint that closed in 2024 is history nobody will
    ask about again, and it is the part that accumulates. Runs on the drain, like the history
    prune, because the Celery broker is a quota-limited Upstash instance and this layer's rule is
    to prefer in-process work on a sweep that already happens.
    """
    eval_time = require_aware(eval_time, "eval_time")
    cutoff = months_before(eval_time, MEMBERSHIP_RETENTION_MONTHS)
    engine = getattr(store, "engine", store)
    with engine.begin() as conn:
        return int(conn.execute(_PRUNE_MEMBERSHIP_SQL, {"o": org_id, "cutoff": cutoff}).rowcount
                   or 0)


# =================================================================================================
# THE SWEEP ENTRY POINT — what `context/runner.process_pending` calls
# =================================================================================================

@dataclass(frozen=True, slots=True)
class CohortSweep:
    """What one org's cohort pass did, in numbers an operator can act on."""

    cohorts: int = 0
    joined: int = 0
    left: int = 0
    members: int = 0
    pruned: int = 0
    refusals: tuple[CohortRefusal, ...] = ()
    budget_exhausted: bool = False

    @property
    def changes(self) -> int:
        return self.joined + self.left


def refresh_cohorts_for_drain(store, org_id: str, *, eval_time: datetime,
                              registry: FactRegistry | None = None,
                              budget: WriteBudget | None = None) -> CohortSweep:
    """The one function the drain calls. Deterministic, no model, no clock.

    ORDER MATTERS. The shipped families are generated from the facts this drain just derived, THEN
    membership is refreshed against the same in-memory snapshot — reloading between the two would
    mean the quartile boundaries and the membership they cut were read at two different instants,
    and a node could sit outside every quartile of the fact it was cut on.

    M-9 IS NOT HERE AND CANNOT BE. Predicate authoring is on demand only (doc 04 L2.4.4-U4: "T3,
    on demand only — never in a sweep"), it needs a human to approve what the model drafted, and a
    sweep has no human in it. This function takes no drafter, imports no model client, and
    `test_cohort.py` reads the source of both this function and `runner.py` to keep it that way.
    """
    eval_time = require_aware(eval_time, "eval_time")
    registry = registry or default_fact_registry()
    budget = budget or WriteBudget()
    engine = getattr(store, "engine", store)

    facts_by_type = load_node_facts(engine, org_id, node_types=COHORT_NODE_TYPES,
                                    eval_time=eval_time, registry=registry)
    if not any(facts_by_type.values()):
        return CohortSweep()                            # nothing in the graph: nothing to compare

    shipped = default_cohorts(org_id=org_id, facts_by_type=facts_by_type, eval_time=eval_time,
                              registry=registry)
    save_definitions(engine, shipped.definitions)

    definitions = load_definitions(engine, org_id, registry=registry)[:MAX_COHORTS_PER_ORG]
    joined = left = members = 0
    exhausted = False
    for definition in definitions:
        delta = refresh_membership(store, definition, eval_time=eval_time,
                                   node_facts=facts_by_type.get(definition.node_type, {}),
                                   budget=budget)
        joined += len(delta.joined)
        left += len(delta.left)
        members += delta.population_size
        exhausted = exhausted or delta.budget_exhausted
        if exhausted:
            break
    pruned = prune_membership(store, org_id, eval_time=eval_time)
    return CohortSweep(cohorts=len(definitions), joined=joined, left=left, members=members,
                       pruned=pruned, refusals=shipped.refusals, budget_exhausted=exhausted)


# =================================================================================================
# POSITION — the only object that leaves this module for a card
# =================================================================================================

_VALUES_SQL = text(
    f"select distinct on (subject_node_id) subject_node_id as node_id, value_bp "
    f"from {HISTORY_TABLE} "
    "where org_id = :o and metric = :m and subject_node_id = any(:ids) and observed_at <= :at "
    "order by subject_node_id, observed_at desc, sampled_at desc")


def position_from_values(*, metric: str, cohort_id: str, values: Mapping[str, int],
                         subject_node_id: str, eval_time: datetime, divisions: int = 10,
                         unknown: int = 0) -> CohortPosition | CohortRefusal:
    """Where one member sits among its cohort, or a REFUSAL. PURE — no database.

    Law 2 is enforced twice on purpose: here, where a population under five returns a refusal a
    card can render, and again in `CohortPosition` itself, where it is unconstructible. The
    contract's version is the guarantee; this one is the honest sentence.

    A cohort below the floor is NOT a weak position. Five is where "bottom decile" stops being a
    sentence about one person wearing the clothes of a distribution — with four members every
    percentile is 2500, 5000, 7500 or 10000, and the phrase on the card describes the arithmetic
    rather than the business.
    """
    eval_time = require_aware(eval_time, "eval_time")
    known = sorted(values.values())
    population = len(known)
    total = population + max(unknown, 0)
    if population < MIN_COHORT_POPULATION:
        return CohortRefusal(
            CohortRefusalReason.INSUFFICIENT_POPULATION, cohort_id, metric, population, eval_time,
            f"{population} members have a reading and a percentile needs "
            f"{MIN_COHORT_POPULATION} — below that a ranking of individuals is not a distribution")
    if total and unknown * 10_000 // total > MAX_UNKNOWN_SHARE_BP:
        return CohortRefusal(
            CohortRefusalReason.INSUFFICIENT_COVERAGE, cohort_id, metric, population, eval_time,
            f"{unknown} of {total} members have no reading of {metric}")
    if subject_node_id not in values:
        return CohortRefusal(CohortRefusalReason.SUBJECT_VALUE_UNKNOWN, cohort_id, metric,
                             population, eval_time,
                             f"{metric} has no known reading for the subject")
    subject = values[subject_node_id]
    rank_bp = percentile_bp(known, subject)
    return CohortPosition(
        metric=metric, cohort_id=cohort_id, population_size=population, percentile_bp=rank_bp,
        band=CohortBand.for_percentile(rank_bp, divisions=divisions),
        p25_bp=_quantile(known, 2_500), p50_bp=_quantile(known, 5_000),
        p75_bp=_quantile(known, 7_500), computed_at=eval_time)


def position_in_cohort(store, *, org_id: str, cohort_id: str, metric: str, subject_node_id: str,
                       eval_time: datetime, divisions: int = 10,
                       ) -> CohortPosition | CohortRefusal:
    """Position a node against its cohort, reading ONE tenant's membership and ONE tenant's
    history.

    Every statement this function reaches carries `org_id`, and the object it returns carries a
    percentile, a band, a count and three boundaries — no node id, no display name, nothing that
    identifies another member. That is the whole cross-tenant story of L2.4.4: a cohort is within
    one tenant (doc 04 L2.4.6-U2 defers the cross-org version explicitly), and even WITHIN a
    tenant the position reveals the distribution rather than the people in it.

    **NOT ON A REQUEST PATH, AND SAYING SO IS THE POINT.** This used to answer
    `GET /api/org/{org}/cohorts/{cohort_id}/position`, and two defects were measured against it
    there: `_VALUES_SQL` bounds the per-member read only from ABOVE, so a member dark for ten
    months still counted as a reading and the coverage floor could not be reached; and the
    `CohortPosition` it returns carries `p25_bp/p50_bp/p75_bp` as literal member readings from a
    floor of five, which `peer_baseline` refuses to publish on the same populations. That route now
    reads `comparator.compare_in_cohort`, which bounds the read by `staleness_floor` and gates the
    ladder through `publishable_distribution`.

    What still reaches this function is the tenant-isolation probes (`test_h12_gate_probes`), which
    use it as the smallest org-scoped read there is. It is kept for that and it is NOT the read
    behind a card. Anything that wants to show a customer a position calls `compare_in_cohort`.
    """
    eval_time = require_aware(eval_time, "eval_time")
    engine = getattr(store, "engine", store)
    with engine.connect() as conn:
        members = [str(r.node_id) for r in
                   conn.execute(_MEMBERS_AT_SQL,
                                {"o": org_id, "c": cohort_id, "at": eval_time}).all()]
        if not members:
            # Empty has two causes and they are different answers: a cohort_id that names nothing
            # of THIS tenant's (including one that belongs to another tenant, which is the same
            # answer from here — it does not exist), and a declared cohort nobody currently
            # matches. Distinguished with one indexed lookup, and only on the path where it is
            # already known there is nothing to rank.
            declared = conn.execute(text(
                f"select 1 from {COHORT_DEFINITION_TABLE} where org_id = :o and cohort_id = :c"),
                {"o": org_id, "c": cohort_id}).first()
            return CohortRefusal(
                CohortRefusalReason.INSUFFICIENT_POPULATION if declared
                else CohortRefusalReason.NO_SUCH_COHORT,
                cohort_id, metric, 0, eval_time,
                "this cohort currently has no members" if declared
                else "no cohort of that id belongs to this tenant")
        if subject_node_id not in members:
            return CohortRefusal(CohortRefusalReason.SUBJECT_NOT_A_MEMBER, cohort_id, metric,
                                 len(members), eval_time,
                                 "the subject is not in the cohort it was compared against")
        rows = conn.execute(_VALUES_SQL, {"o": org_id, "m": metric, "ids": sorted(members),
                                          "at": eval_time}).all()
    values = {str(r.node_id): int(r.value_bp) for r in rows if r.value_bp is not None}
    return position_from_values(metric=metric, cohort_id=cohort_id, values=values,
                                subject_node_id=subject_node_id, eval_time=eval_time,
                                divisions=divisions, unknown=len(members) - len(values))


# =================================================================================================
# M-9 · COHORT PREDICATE AUTHORING — the one model site in this component
# =================================================================================================

class ProposalRefusalReason(str, Enum):
    """Why a draft was not offered for approval. Every one is a NAMED reason a founder can act on."""

    #: The model returned something that is not a predicate.
    NOT_A_PREDICATE = "not_a_predicate"
    #: The predicate references a fact nobody registered — doc 04 failure 13.
    UNREGISTERED_FACT = "unregistered_fact"
    #: The founder named a reference account and the predicate excludes it — doc 04 failure 14.
    #: The draft misunderstood the ask, so it is surfaced and NOT stored.
    REFERENCE_NODE_EXCLUDED = "reference_node_excluded"
    #: The predicate matches nobody at all.
    EMPTY_POPULATION = "empty_population"
    #: The model could not be reached.
    MODEL_UNAVAILABLE = "model_unavailable"
    #: `created_by` would not be a human — the model drafted; a person owns it.
    NOT_A_HUMAN_AUTHOR = "not_a_human_author"


class ProposalRefused(ValueError):
    """A draft that must not be stored. Carries the reason as a value, not just a sentence."""

    def __init__(self, reason: ProposalRefusalReason, detail: str) -> None:
        super().__init__(f"{reason.value}: {detail}")
        self.reason = reason
        self.detail = detail


#: A predicate matching more than this share of the node universe is not a peer group, it is the
#: population. Doc 04 failure 12 ("predicate matches 2000 accounts") is mitigated by the PREVIEW
#: rather than by a refusal — a broad cohort can be exactly what was asked for — so this produces
#: a warning on the proposal and the human decides.
BROAD_COHORT_SHARE_BP = 6_000

#: Doc 04 failure 15: "founder approves without reading" — the preview shows the count AND five
#: named samples, so approving without reading still shows who is in it.
PROPOSAL_SAMPLES = 5


@dataclass(frozen=True, slots=True)
class CohortProposal:
    """M-9's output: a reviewable predicate, its population, and five members BY NAME.

    Nothing here is stored. A proposal becomes a cohort only through `approve_proposal`, and only
    with a human's id — `created_by` records the PERSON, never the model.
    """

    org_id: str
    ask: str
    name: str
    node_type: str
    predicate: Predicate
    population_size: int
    universe_size: int
    samples: tuple[tuple[str, str], ...]
    reference_node_id: str | None = None
    warnings: tuple[str, ...] = ()
    drafted_by: str = ""

    @property
    def predicate_json(self) -> dict[str, Any]:
        return self.predicate.as_json()

    @property
    def share_bp(self) -> int:
        return (self.population_size * 10_000 // self.universe_size) if self.universe_size else 0


#: What M-9's model site is handed and what it must return: an ask plus the vocabulary it may use,
#: back to a predicate tree. It returns JSON — it never returns a score, a population or a member.
Drafter = Callable[[str, "DraftBrief"], Mapping[str, Any]]


@dataclass(frozen=True, slots=True)
class DraftBrief:
    """The vocabulary a drafter may write against. Facts and operators — never the tenant's rows.

    The model is given the SCHEMA, not the data: it decides what the founder meant, and the
    deterministic engine decides who matches. Passing member rows would make the draft a
    clustering of this month's population wearing a predicate's clothes, which is Law 3 broken by
    the back door.
    """

    node_type: str
    facts: tuple[tuple[str, str, str], ...]
    operators: tuple[str, ...]
    combinators: tuple[str, ...]

    @classmethod
    def build(cls, node_type: str, registry: FactRegistry) -> "DraftBrief":
        facts = tuple((d.name, d.kind.value, d.question)
                      for d in (registry.get(n) for n in registry.names)
                      if d is not None and node_type in d.node_types)
        return cls(node_type=node_type, facts=facts,
                   operators=tuple(o.value for o in PredicateOp),
                   combinators=tuple(c.value for c in Combinator))


def draft_prompt(ask: str, brief: DraftBrief) -> str:
    """The M-9 prompt. The model DESCRIBES what the founder meant; it never scores anything."""
    lines = [f"  {name} ({kind}) — {question}" for name, kind, question in brief.facts]
    return (
        "A founder described a group of records they want to compare against. Write the "
        "PREDICATE that selects that group.\n\n"
        f"THEIR WORDS: {ask}\n\n"
        f"RECORD TYPE: {brief.node_type}\n"
        "FACTS YOU MAY REFERENCE (nothing else exists):\n" + "\n".join(lines) + "\n\n"
        f"OPERATORS: {', '.join(brief.operators)}\n"
        f"COMBINATORS: {', '.join(brief.combinators)}\n\n"
        "RULES\n"
        "- Return JSON only: {\"name\": \"<short human name>\", \"predicate\": <tree>}\n"
        "- A tree is {\"all\": [...]} / {\"any\": [...]} / {\"none\": [...]} or "
        "{\"fact\": ..., \"op\": ..., \"value\": ...}\n"
        "- Integers only for numeric values. Never a decimal.\n"
        "- Dates are expressed with within_days, never as a literal date.\n"
        "- Do NOT estimate how many records match, and do NOT name any record. You are writing "
        "the rule; the engine counts.\n")


def llm_predicate_drafter(llm, *, max_tokens: int = 1024) -> Drafter:
    """Adapt the engine's LLM client into a `Drafter`. THE one model call in L2.4.

    Injected rather than constructed inside `propose_cohort` for the reason the whole layer is
    built on: a test drives the same code path with a stub drafter and no network, and the sweep
    path cannot reach a model even by accident because it never receives one.
    """
    def _draft(ask: str, brief: DraftBrief) -> Mapping[str, Any]:
        result = llm.call(draft_prompt(ask, brief), max_tokens=max_tokens)
        if not getattr(result, "ok", False):
            raise ProposalRefused(ProposalRefusalReason.MODEL_UNAVAILABLE,
                                  str(getattr(result, "error", "no response"))[:200])
        return getattr(result, "parsed", {}) or {}
    return _draft


def propose_cohort(*, org_id: str, ask: str, drafter: Drafter, node_type: str,
                   node_facts: Mapping[str, Mapping[str, Any]],
                   node_names: Mapping[str, str] | None = None,
                   eval_time: datetime, reference_node_id: str | None = None,
                   registry: FactRegistry | None = None) -> CohortProposal:
    """M-9 · a founder's sentence becomes a reviewable predicate. ON DEMAND ONLY, never a sweep.

    *"customers like Acme who churned last year"* -> a predicate + a population preview + five
    named samples -> a human approves, edits or rejects. The model is a DRAFTING AID and the
    artifact it produces is exactly the reviewable tree a human would have written, which is why
    this does not break Law 3.

    THE THREE GUARDS, all of them here rather than downstream:
      1. POPULATION PREVIEW before approval — a predicate matching 2,000 accounts is visibly wrong
         before it is ever stored, and the count is computed HERE, deterministically, never by the
         model.
      2. REFERENCE-NODE CHECK — if the founder named Acme, Acme must be in the result. If it is
         not, the predicate misunderstood the ask: surfaced, and not stored.
      3. FACT-NAME VALIDATION at definition time — an unregistered name raises when the predicate
         is written, not silently at evaluation.
    """
    registry = registry or default_fact_registry()
    org_id = require_identifier(org_id, "org_id")
    ask = require_text(ask, "ask")
    node_type = require_text(node_type, "node_type").lower()
    eval_time = require_aware(eval_time, "eval_time")
    if node_type not in COHORT_NODE_TYPES:
        raise ProposalRefused(ProposalRefusalReason.NOT_A_PREDICATE,
                              f"a cohort is over {', '.join(COHORT_NODE_TYPES)}")

    drafted = drafter(ask, DraftBrief.build(node_type, registry))
    if not isinstance(drafted, Mapping) or "predicate" not in drafted:
        raise ProposalRefused(ProposalRefusalReason.NOT_A_PREDICATE,
                              "the draft carries no predicate")
    try:
        predicate = parse_predicate(drafted["predicate"], registry=registry)
    except PredicateError as exc:
        raise ProposalRefused(ProposalRefusalReason.UNREGISTERED_FACT, str(exc)) from None
    for fact_name in sorted(predicate.facts()):
        definition = registry.require(fact_name)
        if node_type not in definition.node_types:
            raise ProposalRefused(
                ProposalRefusalReason.UNREGISTERED_FACT,
                f"{fact_name} is not a fact of a {node_type}")

    members = sorted(node_id for node_id, facts in node_facts.items()
                     if _evaluate(predicate, facts, eval_time))
    # The reference check comes FIRST, before the emptiness check, and the order is the whole
    # message: a predicate that matches nobody AND excludes the account the founder named is not
    # an empty-population problem, it is a misunderstanding, and telling them "nothing matched"
    # sends them to look at their data instead of at the sentence.
    if reference_node_id and reference_node_id not in members:
        raise ProposalRefused(
            ProposalRefusalReason.REFERENCE_NODE_EXCLUDED,
            f"{reference_node_id} was named in the ask and the drafted predicate excludes it — "
            "the draft misunderstood what was asked, so it is not offered for approval")
    if not members:
        raise ProposalRefused(ProposalRefusalReason.EMPTY_POPULATION,
                              "the drafted predicate matches nobody, so there is nothing to "
                              "approve and nothing to compare against")

    names = dict(node_names or {})
    # The named reference LEADS the samples. The founder said "like Acme"; a preview of five
    # members that happens to sort Acme out of view answers a different question, and doc 04's
    # fifteenth failure mode is a human approving without reading.
    shown = ([reference_node_id] if reference_node_id else []) + [
        node_id for node_id in members if node_id != reference_node_id]
    samples = tuple((node_id, names.get(node_id) or str(node_facts[node_id].get("node.name")
                                                        or node_id))
                    for node_id in shown[:PROPOSAL_SAMPLES])
    warnings: list[str] = []
    universe = len(node_facts)
    if universe and len(members) * 10_000 // universe > BROAD_COHORT_SHARE_BP:
        warnings.append(f"this matches {len(members)} of {universe} {node_type} records — a "
                        "cohort that broad compares everyone against themselves")
    if len(members) < MIN_COHORT_POPULATION:
        warnings.append(f"only {len(members)} records match; a position needs "
                        f"{MIN_COHORT_POPULATION}, so this cohort will refuse to produce one "
                        "until it grows")
    return CohortProposal(
        org_id=org_id, ask=ask, name=require_text(drafted.get("name") or ask[:80], "name"),
        node_type=node_type, predicate=predicate, population_size=len(members),
        universe_size=universe, samples=samples, reference_node_id=reference_node_id,
        warnings=tuple(warnings), drafted_by=str(drafted.get("model") or "m9"))


def approve_proposal(proposal: CohortProposal, *, approved_by: str, eval_time: datetime,
                     registry: FactRegistry | None = None) -> CohortDefinition:
    """A human approves a draft. `created_by` is THE HUMAN — the model drafted; the person owns it.

    An id that looks like this engine's own author, or like a model, is refused: `created_by` is
    the field a founder reads when they ask "who decided this?", and an answer of "system" to that
    question about a cohort a model wrote is the one answer that must never be storable.
    """
    approved_by = require_text(approved_by, "approved_by")
    lowered = approved_by.lower()
    if lowered.startswith(("system:", "model:", "m9", "claude", "assistant", "anthropic")):
        raise ProposalRefused(ProposalRefusalReason.NOT_A_HUMAN_AUTHOR,
                              f"{approved_by!r} is not a person — a drafted cohort is owned by "
                              "the human who approved it")
    return define_cohort(org_id=proposal.org_id, name=proposal.name, node_type=proposal.node_type,
                         predicate=proposal.predicate, created_by=approved_by,
                         eval_time=eval_time, registry=registry)


__all__ = [
    "BROAD_COHORT_SHARE_BP", "COHORT_DEFINITION_TABLE", "COHORT_MEMBERSHIP_TABLE",
    "COHORT_NODE_TYPES", "CORE_COHORT_FACTS", "MAX_COHORTS_PER_ORG", "MAX_STAGE_COHORTS",
    "MEMBERSHIP_RETENTION_MONTHS", "MEMBERSHIP_WRITE_BUDGET", "MIN_QUARTILE_POPULATION",
    "MISSES_BEFORE_LEAVING", "PROPOSAL_SAMPLES", "SYSTEM_AUTHOR",
    "CohortBand", "CohortDefinition", "CohortEvent", "CohortEventKind", "CohortPosition",
    "CohortProposal", "CohortRefusal", "CohortRefusalReason", "CohortSweep", "Combinator",
    "Condition", "DefaultCohorts", "DraftBrief", "Drafter", "FactDefinition", "FactKind",
    "FactRegistry", "Group", "MembershipDelta", "Predicate", "PredicateError", "PredicateOp",
    "ProposalRefusalReason", "ProposalRefused", "QuartileFamily", "WriteBudget",
    "approve_proposal", "default_cohorts", "default_fact_registry", "define_cohort",
    "draft_prompt", "evaluate", "llm_predicate_drafter", "load_definitions", "load_node_facts",
    "load_node_names", "membership_changes", "normalise_fact", "numeric_values", "parse_predicate",
    "percentile_bp", "position_from_values", "position_in_cohort", "predicate_fingerprint",
    "predicate_json", "propose_cohort", "prune_membership", "quartile_cohorts",
    "refresh_cohorts_for_drain", "refresh_membership", "save_definitions",
]
