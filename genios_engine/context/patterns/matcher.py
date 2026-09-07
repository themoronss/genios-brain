"""L2.6.1-U2 · the pattern EVALUATOR — does this declared pattern hold, and what proves it.

`match(pattern, graph_slice, *, eval_time) -> MatchResult | None`, pure, in the six ordered steps
doc 06 specifies:

    1. ANCHOR    the anchor's node_type must match, or return None immediately (cheap rejection)
    2. RESOLVE   every @-reference against the slice at eval_time — never against a constant
    3. REQUIRED  every condition must hold; record WHICH one failed when one does
    4. EVIDENCE  each satisfied condition records the object that satisfied it; an unevidenced
                 satisfaction is a FAILED condition
    5. OPTIONAL  satisfied optional signals add weight_bp; they never gate the fire
    6. RETURN    the match, with everything sorted

THE RULE THAT INVERTS THE SYSTEM IF IT IS WRITTEN BACKWARDS. `GENUINELY_ABSENT` satisfies an
absence condition. `UNKNOWABLE` does NOT, and neither do `STALE` and `NOT_EXPECTED`. Backwards,
every unconnected source becomes a confident finding about a customer, which is the exact failure
L2.5.5 exists to prevent — and it is invisible, because a pattern firing on missing data looks
identical to a pattern firing on a real gap.

DETERMINISM IS A PROPERTY OF THIS FUNCTION, AND IT IS TESTED. The same slice and the same
`eval_time` must produce a byte-identical result: matched nodes sorted, evidence in DECLARED
condition order, no set or dict iteration reaching the output. L2.7.3's clustering and the
fire-rate report both diff these results across runs, and an unstable order there reads as the
world having changed.

THE THREE FLOORS LIVE HERE, WITH THE CONDITION KIND, AND NOT WITH THE PATTERN. A pattern that
could declare its own trend-confidence floor would be a pattern that could lower it until it
fired.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from genios_engine.contracts.analytic import (MIN_ANOMALY_PERIODS, MIN_COHORT_POPULATION,
                                              AnomalyDirection, CohortBand)
from genios_engine.contracts.evidence import EvidenceSpan
from genios_engine.context.patterns.contract import (AUTHORITY_THRESHOLD_REF, AbsenceCondition,
                                                     AnomalyCondition, CohortCondition, CohortOp,
                                                     ConditionKind, EdgeCondition, EdgeOp,
                                                     FactCondition, FactOp, ObservationCondition,
                                                     Pattern, TemporalCondition, TemporalOp,
                                                     TrendCondition, combined_strength_bp,
                                                     days_between)
from genios_engine.context.patterns.slice import GraphSlice

#: The condition kinds this evaluator can actually EVALUATE. The registry validates every
#: registered condition against this set, so a pattern naming a kind nobody implemented fails at
#: REGISTRATION rather than never firing — doc 06's fourth failure mode, and the one that is
#: indistinguishable from a working pattern that found nothing.
#:
#: Read off `_evaluate_one` by hand rather than introspected: introspection would keep this set
#: true and make it unreadable, and the point of the set is that a human reviewing a new kind can
#: see in one place whether it was wired in.
IMPLEMENTED_KINDS: frozenset[ConditionKind] = frozenset({
    ConditionKind.FACT, ConditionKind.EDGE, ConditionKind.TEMPORAL, ConditionKind.ABSENCE,
    ConditionKind.TREND, ConditionKind.COHORT, ConditionKind.ANOMALY,
    ConditionKind.OBSERVATION})

#: A trend below this confidence cannot satisfy a trend condition. `Trend` itself caps confidence
#: at `MAX_TREND_CONFIDENCE_BP` (8000), so 5000 is a genuine majority of the available scale
#: rather than a number that admits everything.
TREND_MIN_CONFIDENCE_BP = 5_000

#: Law 2's floor, imported rather than restated: a `CohortPosition` cannot even be CONSTRUCTED
#: below it, and re-declaring the number here would be a second copy free to drift low.
COHORT_MIN_POPULATION = MIN_COHORT_POPULATION

#: A full baseline. Below it there is no "its own normal" to have departed from.
ANOMALY_MIN_PERIODS = MIN_ANOMALY_PERIODS


#: The reasons, as constants rather than inline strings, because `scripts/pattern_fire_report.py`
#: groups on them and a typo would silently create a second bucket for the same failure.
FAIL_ANCHOR_TYPE = "anchor_type"
FAIL_FACT_MISSING = "fact_missing"
FAIL_FACT_COMPARISON = "fact_comparison"
FAIL_FACT_NON_INTEGER = "fact_non_integer"
FAIL_REFERENCE_UNRESOLVED = "reference_unresolved"
FAIL_EDGE_PRESENT = "edge_present"
FAIL_EDGE_ABSENT = "edge_absent"
FAIL_EDGE_ABSENCE_UNKNOWABLE = "edge_absence_unknowable"
FAIL_TEMPORAL_MISSING = "temporal_missing"
FAIL_TEMPORAL_UNPARSEABLE = "temporal_unparseable"
FAIL_TEMPORAL_WINDOW = "temporal_window"
FAIL_ABSENCE_NOT_LICENSED = "absence_not_licensed"
FAIL_TREND_MISSING = "trend_missing"
FAIL_TREND_DIRECTION = "trend_direction"
FAIL_TREND_CONFIDENCE = "trend_confidence"
FAIL_COHORT_MISSING = "cohort_missing"
FAIL_COHORT_POPULATION = "cohort_population"
FAIL_COHORT_POSITION = "cohort_position"
FAIL_ANOMALY_MISSING = "anomaly_missing"
FAIL_ANOMALY_DIRECTION = "anomaly_direction"
FAIL_ANOMALY_PERIODS = "anomaly_periods"
FAIL_ANOMALY_MAGNITUDE = "anomaly_magnitude"
FAIL_OBSERVATION_MISSING = "observation_missing"
FAIL_OBSERVATION_STALE = "observation_stale"
FAIL_NO_EVIDENCE = "no_evidence_object"


@dataclass(frozen=True, slots=True)
class ConditionEvidence:
    """WHY one condition held — the object that satisfied it, not a restatement of the condition.

    `ref` is REQUIRED and non-empty. Doc 06's contract with Layer 3 is *"this fired because of
    these five facts"*, and a satisfied condition with no recoverable object is an assertion in a
    fact's typography. `matcher` treats an unevidenced satisfaction as a FAILURE rather than
    letting it through — see `_evidenced`.
    """

    #: Which condition, by its position in the pattern's declared list. Position rather than a
    #: name because conditions have no ids and two conditions on one field are legal.
    index: int
    kind: ConditionKind
    field_path: str
    operator: str
    expected: bool | int | str | None
    observed: bool | int | str | None
    #: The satisfying object's own id — `fact_version_id`, `edge_version_id`, `observation_id`,
    #: or a derived receipt key for the objects that have no row of their own.
    ref: str
    #: The object, flattened to something a card and an audit row can both read.
    record: tuple[tuple[str, Any], ...] = ()
    #: Verbatim receipts where they exist. Frequently empty — a CRM field has no quote.
    spans: tuple[EvidenceSpan, ...] = ()

    def as_record(self) -> dict[str, Any]:
        return {"index": self.index, "kind": self.kind.value, "field_path": self.field_path,
                "operator": self.operator, "expected": self.expected, "observed": self.observed,
                "ref": self.ref, "record": dict(self.record),
                "spans": [s.model_dump(mode="json") for s in self.spans]}


@dataclass(frozen=True, slots=True)
class ConditionFailure:
    """WHICH condition stopped the pattern, and why. The fire report's other half.

    Doc 06's second failure mode is a pattern that NEVER fires, and a registry that only records
    successes cannot tell "never matched" from "always failed on condition 4 because that field
    is spelled differently in this tenant". This is that record.
    """

    index: int
    kind: ConditionKind
    field_path: str
    reason: str
    detail: str = ""

    def as_record(self) -> dict[str, Any]:
        return {"index": self.index, "kind": self.kind.value, "field_path": self.field_path,
                "reason": self.reason, "detail": self.detail}


@dataclass(frozen=True, slots=True)
class MatchResult:
    """A pattern that held, with the receipt for every condition."""

    pattern_id: str
    pattern_version: int
    situation_type: str
    org_id: str
    anchor_node_id: str
    anchor_node_type: str
    #: Sorted. Every node the match touched, anchor included.
    matched_nodes: tuple[str, ...]
    #: Sorted `edge_version_id`s.
    matched_edges: tuple[str, ...]
    #: One entry per REQUIRED condition, in the pattern's declared order.
    evidence: tuple[ConditionEvidence, ...]
    #: The satisfied optional signals, in declared order. Never gates.
    optional_evidence: tuple[ConditionEvidence, ...]
    match_strength_bp: int
    eval_time: datetime

    def as_record(self) -> dict[str, Any]:
        """A stable, ordered record — what the fire log stores and the API returns."""
        return {"pattern_id": self.pattern_id, "pattern_version": self.pattern_version,
                "situation_type": self.situation_type, "org_id": self.org_id,
                "anchor_node_id": self.anchor_node_id, "anchor_node_type": self.anchor_node_type,
                "matched_nodes": list(self.matched_nodes),
                "matched_edges": list(self.matched_edges),
                "evidence": [e.as_record() for e in self.evidence],
                "optional_evidence": [e.as_record() for e in self.optional_evidence],
                "match_strength_bp": self.match_strength_bp,
                "eval_time": self.eval_time.isoformat()}


@dataclass(frozen=True, slots=True)
class MatchOutcome:
    """Either a match or the reason there was not one. `match()` returns the first half.

    Two entry points over one evaluation, because both halves are needed and recomputing the
    second by re-running the first with a flag is how they come to disagree.
    """

    matched: MatchResult | None
    failure: ConditionFailure | None

    @property
    def fired(self) -> bool:
        return self.matched is not None


# =================================================================================================
# The evaluation
# =================================================================================================

def match(pattern: Pattern, graph_slice: GraphSlice, *,
          eval_time: datetime) -> MatchResult | None:
    """Does this pattern hold over this slice, as at `eval_time`? PURE.

    `eval_time` is a required keyword argument and no clock is read in this module — a pattern
    that fired differently on replay could not be reviewed, and reviewing a misfire is the whole
    remedy the registry offers.
    """
    return evaluate(pattern, graph_slice, eval_time=eval_time).matched


def evaluate(pattern: Pattern, graph_slice: GraphSlice, *,
             eval_time: datetime) -> MatchOutcome:
    """`match`, plus the failing condition when it does not hold."""
    if eval_time.tzinfo is None:
        raise ValueError("eval_time must be timezone-aware — a naive instant compares wrong "
                         "against every dated fact in the graph")

    # 1 · ANCHOR — the cheap rejection, first.
    if graph_slice.anchor.node_type != pattern.anchor_node_type:
        return MatchOutcome(None, ConditionFailure(
            -1, ConditionKind.FACT, "anchor.node_type", FAIL_ANCHOR_TYPE,
            f"slice anchor is {graph_slice.anchor.node_type!r}, "
            f"pattern wants {pattern.anchor_node_type!r}"))

    # 3 + 4 · REQUIRED and EVIDENCE, in declared order. Short-circuit on the first failure —
    # but record WHICH one, because "never fires" and "always fails on condition 4" need
    # different remedies and look identical in a fire count.
    evidence: list[ConditionEvidence] = []
    for index, condition in enumerate(pattern.conditions):
        found, failure = _evaluate_one(condition, index, graph_slice, eval_time=eval_time)
        if failure is not None:
            return MatchOutcome(None, failure)
        evidence.append(found)          # type: ignore[arg-type]

    # 5 · OPTIONAL — never gates. A pattern with five declared conditions must fire on five, and
    # an optional signal that could block would make it seven without saying so.
    optional: list[ConditionEvidence] = []
    weights: list[int] = []
    for index, signal in enumerate(pattern.optional_signals):
        found, failure = _evaluate_one(signal.condition, index, graph_slice, eval_time=eval_time)
        if failure is None and found is not None:
            optional.append(found)
            weights.append(signal.weight_bp)

    nodes = {graph_slice.anchor.node_id}
    edges: set[str] = set()
    for item in (*evidence, *optional):
        if item.kind is ConditionKind.EDGE and item.ref.startswith("edge:"):
            edges.add(item.ref.split(":", 1)[1])
    for edge in graph_slice.edges:
        if edge.edge_version_id in edges:
            nodes.add(edge.from_node_id)
            nodes.add(edge.to_node_id)

    return MatchOutcome(MatchResult(
        pattern_id=pattern.pattern_id, pattern_version=pattern.version,
        situation_type=pattern.situation_type, org_id=graph_slice.org_id,
        anchor_node_id=graph_slice.anchor.node_id,
        anchor_node_type=graph_slice.anchor.node_type,
        # Sorted, not insertion-ordered: clustering and the shadow diff compare these across
        # runs, and a set's iteration order is not a property of the world.
        matched_nodes=tuple(sorted(nodes)), matched_edges=tuple(sorted(edges)),
        evidence=tuple(evidence), optional_evidence=tuple(optional),
        match_strength_bp=combined_strength_bp(tuple(weights)), eval_time=eval_time), None)


def _evaluate_one(condition: Any, index: int, s: GraphSlice, *,
                  eval_time: datetime) -> tuple[ConditionEvidence | None, ConditionFailure | None]:
    """One condition → (evidence, None) or (None, failure). Never both, never neither."""
    if isinstance(condition, FactCondition):
        return _fact(condition, index, s)
    if isinstance(condition, EdgeCondition):
        return _edge(condition, index, s)
    if isinstance(condition, TemporalCondition):
        return _temporal(condition, index, s, eval_time=eval_time)
    if isinstance(condition, AbsenceCondition):
        return _absence(condition, index, s)
    if isinstance(condition, TrendCondition):
        return _trend(condition, index, s)
    if isinstance(condition, CohortCondition):
        return _cohort(condition, index, s)
    if isinstance(condition, AnomalyCondition):
        return _anomaly(condition, index, s)
    if isinstance(condition, ObservationCondition):
        return _observation(condition, index, s, eval_time=eval_time)
    # Unreachable through the registry, which validates the kind at registration. Kept as a loud
    # refusal rather than a `pass`, because a silent fall-through here is a condition that always
    # holds — the single worst way for this function to be wrong.
    raise TypeError(f"no evaluator for condition {condition!r}")


def _evidenced(item: ConditionEvidence, index: int, kind: ConditionKind,
               field_path: str) -> tuple[ConditionEvidence | None, ConditionFailure | None]:
    """Rule 4, enforced in one place: a satisfaction with no `ref` is a FAILURE, not a match."""
    if not item.ref:
        return None, ConditionFailure(index, kind, field_path, FAIL_NO_EVIDENCE,
                                      "the condition held but produced no recoverable object")
    return item, None


# -- fact ------------------------------------------------------------------------------------

def _scalar(value: Any) -> bool | int | str | None:
    """A value a card can print and a jsonb column can hold. Floats are refused upstream."""
    if value is None or isinstance(value, (bool, int, str)):
        return value
    return str(value)


def _fact(c: FactCondition, index: int, s: GraphSlice):
    fact = s.fact(c.field_path)
    if fact is None:
        # A missing ROW is not an absence. `kind: absence` is the only thing entitled to say so,
        # and it consumes the typed answer rather than the empty result.
        return None, ConditionFailure(index, c.kind, c.field_path, FAIL_FACT_MISSING,
                                      "no fact row; a typed absence condition is the only way "
                                      "to assert that a fact is genuinely not there")
    expected: Any = c.value
    used_authority = isinstance(expected, str) and expected == AUTHORITY_THRESHOLD_REF
    if used_authority:
        if s.authority_threshold_minor_units is None:
            return None, ConditionFailure(
                index, c.kind, c.field_path, FAIL_REFERENCE_UNRESOLVED,
                "no authority rule in force at eval_time — 'high value' has no meaning for this "
                "org yet, and defaulting it to zero would fire on every anchor")
        expected = s.authority_threshold_minor_units

    observed = fact.value
    if isinstance(observed, float) or isinstance(expected, float):
        return None, ConditionFailure(index, c.kind, c.field_path, FAIL_FACT_NON_INTEGER,
                                      f"float value {observed!r}: money is minor units and "
                                      "ratios are basis points")
    ok = _compare(c.op, observed, expected)
    if ok is None:
        return None, ConditionFailure(index, c.kind, c.field_path, FAIL_FACT_NON_INTEGER,
                                      f"{c.op.value} needs two comparable numbers, got "
                                      f"{observed!r} and {expected!r}")
    if not ok:
        return None, ConditionFailure(index, c.kind, c.field_path, FAIL_FACT_COMPARISON,
                                      f"{observed!r} {c.op.value} {expected!r} is false")
    record: list[tuple[str, Any]] = [("subject_node_id", fact.subject_node_id),
                                     ("value_type", fact.value_type)]
    if fact.occurred_at is not None:
        record.append(("occurred_at", fact.occurred_at.isoformat()))
    if used_authority and s.authority_rule_id:
        record.append(("authority_rule_id", s.authority_rule_id))
    return _evidenced(ConditionEvidence(
        index=index, kind=c.kind, field_path=c.field_path, operator=c.op.value,
        expected=_scalar(expected), observed=_scalar(observed),
        ref=f"fact:{fact.fact_version_id}", record=tuple(record), spans=fact.spans),
        index, c.kind, c.field_path)


def _compare(op: FactOp, observed: Any, expected: Any) -> bool | None:
    """The fact comparison. `None` means the two are not comparable — which is a FAILURE with its
    own reason, never a silent False that would read as "the world says no"."""
    if op is FactOp.EXISTS:
        return True                                  # the row is there; that is the whole claim
    if op is FactOp.EQ:
        return _same(observed, expected)
    if op is FactOp.NE:
        return not _same(observed, expected)
    if op is FactOp.IN:
        return any(_same(observed, item) for item in (expected or ()))
    if op is FactOp.CONTAINS:
        return isinstance(observed, str) and isinstance(expected, str) and expected in observed
    if isinstance(observed, bool) or isinstance(expected, bool):
        return None                                  # a bool is not a magnitude
    if not isinstance(observed, int) or not isinstance(expected, int):
        return None
    if op is FactOp.GT:
        return observed > expected
    if op is FactOp.GTE:
        return observed >= expected
    if op is FactOp.LT:
        return observed < expected
    return observed <= expected


def _same(observed: Any, expected: Any) -> bool:
    """Equality that does not let `True` equal `1`.

    `bool` is an `int` in Python, so a plain `==` makes `{op: eq, value: 1}` hold on a boolean
    fact and `{op: eq, value: true}` hold on an integer one. Both are wrong in the same
    dangerous direction: they make a pattern fire on a field it was not written about.
    """
    if isinstance(observed, bool) != isinstance(expected, bool):
        return False
    if isinstance(observed, str) and isinstance(expected, str):
        # Graph facts arrive JSON-encoded through several writers; `"true"` and `true` are the
        # same field written by two lanes. Case and surrounding quotes are normalised, nothing
        # else is.
        return observed.strip().strip('"').lower() == expected.strip().strip('"').lower()
    return observed == expected


# -- edge ------------------------------------------------------------------------------------

def _edge(c: EdgeCondition, index: int, s: GraphSlice):
    anchor = s.anchor.node_id
    from_node = anchor if c.from_node == "@anchor" else c.from_node
    to_node = anchor if c.to_node == "@anchor" else c.to_node
    found = s.edges_of_type(c.edge_type, from_node_id=from_node, to_node_id=to_node)
    if c.op is EdgeOp.PRESENT:
        if not found:
            return None, ConditionFailure(index, c.kind, c.field_path, FAIL_EDGE_ABSENT,
                                          f"no {c.edge_type} edge from {from_node}")
        edge = min(found, key=lambda e: e.edge_version_id)   # deterministic pick
        return _evidenced(ConditionEvidence(
            index=index, kind=c.kind, field_path=c.field_path, operator=c.op.value,
            expected=c.edge_type, observed=edge.to_node_id, ref=f"edge:{edge.edge_version_id}",
            record=(("from_node_id", edge.from_node_id), ("to_node_id", edge.to_node_id),
                    ("confidence_bp", edge.confidence_bp))), index, c.kind, c.field_path)

    # MISSING — a negative inference, and licensed only by declared coverage. Without the
    # licence the condition FAILS rather than holding: an org with no CRM connected has no
    # `owns` edges at all, and "nobody owns this contract" would then be true of everything.
    if c.edge_type not in s.edge_coverage:
        return None, ConditionFailure(
            index, c.kind, c.field_path, FAIL_EDGE_ABSENCE_UNKNOWABLE,
            f"no connected source could have carried a {c.edge_type} edge for this org, so its "
            "absence licenses nothing")
    if found:
        return None, ConditionFailure(index, c.kind, c.field_path, FAIL_EDGE_PRESENT,
                                      f"{len(found)} {c.edge_type} edge(s) exist")
    return _evidenced(ConditionEvidence(
        index=index, kind=c.kind, field_path=c.field_path, operator=c.op.value,
        expected="absent", observed="absent",
        # The receipt for a missing edge is the COVERAGE claim — what we looked at — because
        # there is no row to point at and "we checked" is the only thing that makes it evidence.
        ref=f"edge_absent:{s.anchor.node_id}:{c.edge_type}",
        record=(("edge_type", c.edge_type), ("from_node_id", from_node),
                ("coverage", "declared knowable for this org"))), index, c.kind, c.field_path)


# -- temporal --------------------------------------------------------------------------------

def _as_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.strip().strip('"').replace("Z", "+00:00"))
        except ValueError:
            return None
        return parsed
    return None


def _temporal(c: TemporalCondition, index: int, s: GraphSlice, *, eval_time: datetime):
    fact = s.fact(c.field_path)
    if fact is None:
        return None, ConditionFailure(index, c.kind, c.field_path, FAIL_TEMPORAL_MISSING,
                                      "no dated fact at this path")
    when = _as_datetime(fact.value)
    if when is None:
        return None, ConditionFailure(index, c.kind, c.field_path, FAIL_TEMPORAL_UNPARSEABLE,
                                      f"{fact.value!r} is not a date")
    if when.tzinfo is None:
        from datetime import timezone
        when = when.replace(tzinfo=timezone.utc)
    if c.op is TemporalOp.WITHIN_DAYS:
        ahead = days_between(when, eval_time)
        # A window that has already closed is a DIFFERENT situation, and letting it satisfy
        # "within 30 days" is how a card says "12 days left" about a date last month.
        ok = 0 <= ahead <= c.value if when >= eval_time else False
        observed: int | str = ahead
    else:
        behind = days_between(eval_time, when)
        ok = behind >= c.value
        observed = behind
    if not ok:
        return None, ConditionFailure(
            index, c.kind, c.field_path, FAIL_TEMPORAL_WINDOW,
            f"{when.isoformat()} is {observed} days from eval_time; needs {c.op.value} {c.value}")
    return _evidenced(ConditionEvidence(
        index=index, kind=c.kind, field_path=c.field_path, operator=c.op.value,
        expected=c.value, observed=observed, ref=f"fact:{fact.fact_version_id}",
        record=(("dated_value", when.isoformat()), ("eval_time", eval_time.isoformat())),
        spans=fact.spans), index, c.kind, c.field_path)


# -- absence ---------------------------------------------------------------------------------

def _absence(c: AbsenceCondition, index: int, s: GraphSlice):
    """GENUINELY_ABSENT satisfies. UNKNOWABLE, STALE, NOT_EXPECTED and PRESENT do not.

    The licence is read off the contract's computed field, never re-derived here — a second
    derivation is a second place to get the most dangerous rule in this layer backwards.
    """
    absence = s.absence_for(c.field_path)
    licensed = s.licensed_absence(c.field_path)
    if licensed is None:
        seen = absence.absence_type.value if absence is not None else "no typed answer recorded"
        return None, ConditionFailure(
            index, c.kind, c.field_path, FAIL_ABSENCE_NOT_LICENSED,
            f"absence is {seen}; only genuinely_absent licenses a negative inference")
    return _evidenced(ConditionEvidence(
        index=index, kind=c.kind, field_path=c.field_path, operator="genuinely_absent",
        expected="genuinely_absent", observed=licensed.absence_type.value,
        # The receipt is WHAT WE LOOKED AT. Without `coverage_basis` this evidence would be the
        # bare assertion "it is not there", which is the thing a founder cannot check.
        ref=f"absence:{licensed.subject_node_id}:{licensed.expected_fact}",
        record=(("coverage_ready", licensed.coverage_ready),
                ("coverage_basis", list(licensed.coverage_basis)))), index, c.kind, c.field_path)


# -- trend / cohort / anomaly ------------------------------------------------------------------

def _trend(c: TrendCondition, index: int, s: GraphSlice):
    trend = s.trend_for(c.metric)
    if trend is None:
        return None, ConditionFailure(index, c.kind, c.metric, FAIL_TREND_MISSING,
                                      "no trend computed for this metric")
    if trend.direction is not c.direction:
        return None, ConditionFailure(
            index, c.kind, c.metric, FAIL_TREND_DIRECTION,
            f"trend is {trend.direction.value}, pattern wants {c.direction.value}")
    if trend.trend_confidence_bp < TREND_MIN_CONFIDENCE_BP:
        return None, ConditionFailure(
            index, c.kind, c.metric, FAIL_TREND_CONFIDENCE,
            f"confidence {trend.trend_confidence_bp} < {TREND_MIN_CONFIDENCE_BP}")
    return _evidenced(ConditionEvidence(
        index=index, kind=c.kind, field_path=f"trend.{c.metric}", operator="direction_is",
        expected=c.direction.value, observed=trend.direction.value,
        ref=f"trend:{c.metric}:{trend.direction.value}",
        record=(("relative_slope_bp", trend.relative_slope_bp),
                ("point_count", trend.point_count),
                ("coverage_ratio_bp", trend.coverage_ratio_bp),
                ("trend_confidence_bp", trend.trend_confidence_bp),
                ("streak_periods", trend.streak_periods))), index, c.kind, c.metric)


def _cohort(c: CohortCondition, index: int, s: GraphSlice):
    position = s.position_for(c.metric)
    if position is None:
        return None, ConditionFailure(index, c.kind, c.metric, FAIL_COHORT_MISSING,
                                      "no cohort position for this metric")
    if position.population_size < COHORT_MIN_POPULATION:
        return None, ConditionFailure(
            index, c.kind, c.metric, FAIL_COHORT_POPULATION,
            f"population {position.population_size} < {COHORT_MIN_POPULATION}")
    if c.op is CohortOp.BAND_IS:
        ok = position.band is CohortBand(c.value)
        observed: Any = position.band.value
    elif c.op is CohortOp.PERCENTILE_LTE:
        ok = position.percentile_bp <= int(c.value)
        observed = position.percentile_bp
    else:
        ok = position.percentile_bp >= int(c.value)
        observed = position.percentile_bp
    if not ok:
        return None, ConditionFailure(index, c.kind, c.metric, FAIL_COHORT_POSITION,
                                      f"{observed} fails {c.op.value} {c.value}")
    return _evidenced(ConditionEvidence(
        index=index, kind=c.kind, field_path=f"cohort.{c.metric}", operator=c.op.value,
        expected=c.value, observed=observed,
        # `cohort_id` is in the ref because a percentile whose population is unnamed cannot be
        # checked, disagreed with or reproduced — V-1's whole argument.
        ref=f"cohort:{position.cohort_id}:{c.metric}",
        record=(("cohort_id", position.cohort_id),
                ("population_size", position.population_size),
                ("percentile_bp", position.percentile_bp), ("band", position.band.value))),
        index, c.kind, c.metric)


def _anomaly(c: AnomalyCondition, index: int, s: GraphSlice):
    anomaly = s.anomaly_for(c.metric)
    if anomaly is None:
        return None, ConditionFailure(index, c.kind, c.metric, FAIL_ANOMALY_MISSING,
                                      "no anomaly verdict for this metric")
    if anomaly.periods_used < ANOMALY_MIN_PERIODS:
        return None, ConditionFailure(index, c.kind, c.metric, FAIL_ANOMALY_PERIODS,
                                      f"{anomaly.periods_used} periods < {ANOMALY_MIN_PERIODS}")
    if anomaly.direction is not AnomalyDirection(c.direction):
        return None, ConditionFailure(index, c.kind, c.metric, FAIL_ANOMALY_DIRECTION,
                                      f"anomaly is {anomaly.direction.value}")
    if c.min_z_like_bp is not None and anomaly.z_like_bp < c.min_z_like_bp:
        return None, ConditionFailure(index, c.kind, c.metric, FAIL_ANOMALY_MAGNITUDE,
                                      f"z_like {anomaly.z_like_bp} < {c.min_z_like_bp}")
    return _evidenced(ConditionEvidence(
        index=index, kind=c.kind, field_path=f"anomaly.{c.metric}", operator="direction_is",
        expected=c.direction.value, observed=anomaly.direction.value,
        ref=f"anomaly:{c.metric}:{anomaly.direction.value}",
        record=(("current_bp", anomaly.current_bp), ("baseline_bp", anomaly.baseline_bp),
                ("mad_bp", anomaly.mad_bp), ("z_like_bp", anomaly.z_like_bp),
                ("periods_used", anomaly.periods_used))), index, c.kind, c.metric)


def _observation(c: ObservationCondition, index: int, s: GraphSlice, *, eval_time: datetime):
    found = s.observations_of(c.kind_name)
    if not found:
        return None, ConditionFailure(index, c.kind, c.field_path, FAIL_OBSERVATION_MISSING,
                                      f"no active {c.kind_name} observation")
    if c.within_days is not None:
        fresh = [o for o in found
                 if o.occurred_at is not None
                 and 0 <= days_between(eval_time, o.occurred_at) <= c.within_days]
        if not fresh:
            return None, ConditionFailure(
                index, c.kind, c.field_path, FAIL_OBSERVATION_STALE,
                f"no {c.kind_name} observation inside {c.within_days} days")
        found = tuple(fresh)
    # Deterministic pick: the newest, ties broken by id, so two runs cite the same receipt.
    chosen = sorted(found, key=lambda o: ((o.occurred_at.isoformat() if o.occurred_at else ""),
                                          o.observation_id))[-1]
    return _evidenced(ConditionEvidence(
        index=index, kind=c.kind, field_path=c.field_path, operator="observed",
        expected=c.kind_name, observed=chosen.kind, ref=f"observation:{chosen.observation_id}",
        record=(("subject_node_id", chosen.subject_node_id),
                ("occurred_at", chosen.occurred_at.isoformat() if chosen.occurred_at else None)),
        spans=chosen.spans), index, c.kind, c.field_path)


__all__ = ["ANOMALY_MIN_PERIODS", "COHORT_MIN_POPULATION", "IMPLEMENTED_KINDS",
           "TREND_MIN_CONFIDENCE_BP",
           "ConditionEvidence", "ConditionFailure", "MatchOutcome", "MatchResult", "evaluate",
           "match"]
