"""The boundary — where the pattern registry meets a database, and the only impure module here.

Everything above this file is a pure function over injected data. This one does the three things
that cannot be pure: it READS the graph into slices, it WRITES the fire log, and it holds the
per-tenant activation switch. The clock is read by the CALLER and passed in as `eval_time`; there
is no `datetime.now()` below this line either.

THE MIGRATION PATH, STATED. This wave lands the registry BESIDE anchor-based detection, exactly as
doc 06 requires: *"keep anchor-based detection running alongside. Compare fire sets on a pilot for
7 days before switching. Do not delete the anchor path in this wave."* So:

  * nothing here writes `context_situations`, `context_correlations` or any table
    `context/situations.py` owns — the only tables this module writes are the three
    `pattern_*` ones migration 0100 creates, and they are new;
  * `refresh_situations` is untouched and its behaviour is unchanged;
  * a fire is recorded with `activated=false` until somebody activates the pattern for that
    tenant through the guard, so evaluation is SHADOW by default;
  * switching over means, in a later wave, having `situation_bso` build its object from a
    `SituationCandidate` instead of from a correlation — a change to that module, made against
    seven days of fire evidence from this one.

`absences` and `edge_coverage` license the two NEGATIVE condition kinds.  Production evaluation
reads the current typed-absence store and explicit edge-coverage declarations; tests may still
inject either provider.  No row means no licence, so the fire report says
`absence_not_licensed` rather than drawing a finding from an unconnected source.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Mapping, Sequence

from sqlalchemy import text

from genios_engine.context.authority_view import AuthorityView, PostgresAuthorityRules, bottleneck
from genios_engine.context.patterns.candidate import SituationCandidate, build_candidate
from genios_engine.context.patterns.contract import Pattern
from genios_engine.context.patterns.matcher import ConditionFailure, evaluate
from genios_engine.context.patterns.registry import (ActivationDecision, FireObservation,
                                                     PatternRegistry, activation_decision,
                                                     seed_registry)
from genios_engine.context.patterns.slice import (GraphSlice, MissingFact, SliceEdge, SliceFact,
                                                  SliceNode, SliceObservation)
from genios_engine.context.quality.missing import read_absences
from genios_engine.platform.ids import new_id
from genios_engine.platform.logging import get_logger

_log = get_logger("genios.context.patterns")

#: How many anchors one evaluation may consider, per pattern. A tenant with 50,000 people is not a
#: reason to build 50,000 slices in one request; what is not evaluated this run is evaluated next.
ANCHOR_BUDGET = 2_000

#: How many fire ROWS one run may write per pattern. The true count still goes to
#: `pattern_runs.fires`, so a pattern that matches everything is measured at its real rate and
#: stores a bounded sample of the evidence. Without this, the loose pattern the guard exists to
#: catch would fill the table on its way to being caught.
FIRE_WRITE_BUDGET = 200

#: How long the fire log is kept. Long enough for the 30-day report the gate asks for, plus two
#: more windows to compare against.
FIRE_RETENTION_DAYS = 90

#: The signature of a typed-absence provider: given a connection, an org and the node ids in play,
#: return the `MissingFact` rows for them. L2.5.5 owns the implementation; this package owns only
#: the seam.
AbsenceProvider = Callable[[Any, str, tuple[str, ...]], Sequence[MissingFact]]
#: Which edge types' ABSENCE is knowable for this org — i.e. a connected source could have carried
#: them. Without this, a missing edge licenses nothing.
EdgeCoverageProvider = Callable[[Any, str], frozenset[str]]


def _no_absences(conn: Any, org_id: str, node_ids: tuple[str, ...]) -> tuple[MissingFact, ...]:
    """The default: no typed absence is available, so no absence condition can hold.

    NOT an error and NOT an empty finding — the two are different, which is the entire subject of
    L2.5.5. A pattern with an absence condition reports `absence_not_licensed` and does not fire.
    """
    return ()


def _no_edge_coverage(conn: Any, org_id: str) -> frozenset[str]:
    return frozenset()


def stored_absence_provider(conn: Any, org_id: str,
                            node_ids: tuple[str, ...]) -> tuple[MissingFact, ...]:
    """Current-epoch typed absences for the anchors being evaluated.

    A stale ``GENUINELY_ABSENT`` row is deliberately omitted: its embedded contract still says it
    licenses inference, while the storage wrapper knows the coverage epoch has moved.  Omitting it
    makes the matcher answer ``absence_not_licensed`` until the next absence refresh rechecks it.
    UNKNOWABLE/STALE rows remain visible and fail safely through their own contract property.
    """
    wanted = frozenset(str(node_id) for node_id in node_ids)
    out: list[MissingFact] = []
    for stored in read_absences(conn, org_id):
        if stored.fact.subject_node_id not in wanted:
            continue
        if stored.fact.is_finding and not stored.licenses_negative_inference:
            continue
        out.append(stored.fact)
    return tuple(sorted(out, key=lambda fact: (fact.subject_node_id, fact.expected_fact)))


def declared_edge_coverage(conn: Any, org_id: str) -> frozenset[str]:
    """Edge types whose absence an explicit, current declaration licenses.

    Presence in the graph is not coverage: seeing one ``owns`` edge proves that edge and says
    nothing about an anchor where it is absent.  The declaration therefore requires a non-empty
    capability basis and a ready flag.  No row means no licence.
    """
    rows = _rows(conn,
        "select edge_type from edge_coverage_declarations "
        "where org_id = :o and coverage_ready and jsonb_array_length(coverage_basis) > 0 "
        "order by edge_type", {"o": org_id})
    return frozenset(str(row.edge_type) for row in rows)


def declare_edge_coverage(conn: Any, *, org_id: str, edge_type: str,
                          coverage_ready: bool, coverage_basis: Sequence[str],
                          coverage_epoch: int, declared_by: str,
                          declared_at: datetime) -> None:
    """Record the audited licence used by missing-edge pattern conditions."""
    edge_type = str(edge_type).strip()
    declared_by = str(declared_by).strip()
    basis = sorted({str(value).strip() for value in coverage_basis if str(value).strip()})
    if not edge_type or not declared_by:
        raise ValueError("edge_type and declared_by are required")
    if coverage_ready and not basis:
        raise ValueError("ready edge coverage requires a non-empty capability basis")
    if isinstance(coverage_epoch, bool) or not isinstance(coverage_epoch, int) or coverage_epoch < 1:
        raise ValueError("coverage_epoch must be a positive integer")
    conn.execute(text(
        "insert into edge_coverage_declarations "
        "(org_id, edge_type, coverage_ready, coverage_basis, coverage_epoch, declared_by, "
        " declared_at) values (:o,:edge,:ready,cast(:basis as jsonb),:epoch,:by,:at) "
        "on conflict (org_id, edge_type) do update set "
        "coverage_ready=excluded.coverage_ready, coverage_basis=excluded.coverage_basis, "
        "coverage_epoch=excluded.coverage_epoch, declared_by=excluded.declared_by, "
        "declared_at=excluded.declared_at"), {
            "o": org_id, "edge": edge_type, "ready": bool(coverage_ready),
            "basis": json.dumps(basis), "epoch": coverage_epoch,
            "by": declared_by, "at": declared_at})


@dataclass(frozen=True, slots=True)
class PatternRun:
    """What one pattern did over one tenant at one instant."""

    pattern_id: str
    pattern_version: int
    anchors_considered: int
    fires: int
    candidates: tuple[SituationCandidate, ...]
    top_failure: ConditionFailure | None
    activated: bool

    def as_record(self) -> dict[str, Any]:
        return {"pattern_id": self.pattern_id, "pattern_version": self.pattern_version,
                "anchors_considered": self.anchors_considered, "fires": self.fires,
                "activated": self.activated,
                "top_failure": self.top_failure.as_record() if self.top_failure else None,
                "candidates": [c.as_record() for c in self.candidates]}


@dataclass(frozen=True, slots=True)
class EvaluationReport:
    org_id: str
    eval_time: datetime
    runs: tuple[PatternRun, ...]

    @property
    def candidates(self) -> tuple[SituationCandidate, ...]:
        return tuple(c for run in self.runs for c in run.candidates)

    def as_record(self) -> dict[str, Any]:
        return {"org_id": self.org_id, "eval_time": self.eval_time.isoformat(),
                "patterns_evaluated": len(self.runs),
                "fires": sum(r.fires for r in self.runs),
                "runs": [r.as_record() for r in self.runs]}


# =================================================================================================
# Reading the graph into slices
# =================================================================================================

def _rows(conn, sql: str, params: Mapping[str, Any]):
    return conn.execute(text(sql), dict(params)).fetchall()


def _coerce(value: Any) -> Any:
    """A `graph_facts.value` as the evaluator should see it.

    Values arrive JSON-encoded through several writers, so `"true"`, `true`, `"42"` and `42` are
    all real spellings of two facts. Decoded here, once, rather than in eight comparison branches
    — and a float that survives decoding is left alone so the evaluator can REFUSE it loudly
    instead of this function quietly rounding it.
    """
    if not isinstance(value, str):
        return value
    text_value = value.strip()
    if text_value and (text_value[0] in '[{"' or text_value in ("true", "false", "null")
                       or _looks_numeric(text_value)):
        try:
            return json.loads(text_value)
        except (ValueError, TypeError):
            return value
    return value


def _looks_numeric(value: str) -> bool:
    body = value[1:] if value[:1] in "+-" else value
    return body.isdigit()


def _authority_facts(view: AuthorityView | None, org_id: str, *,
                     eval_time: datetime) -> dict[str, list[SliceFact]]:
    """The Founder Bottleneck reading, as slice facts on the approvers themselves.

    DERIVED AT `eval_time`, NEVER STORED. Authority is historical — a rule in force last quarter is
    not a rule in force now — so a count written into `graph_facts` would be a number that quietly
    stops being true and no reader could tell. The receipt is the rule ids, carried on the fact's
    `fact_version_id`, so a card saying "you are the only approver for three classes" can name the
    three rules.
    """
    if view is None:
        return {}
    report = bottleneck(view.rules(org_id, as_of=eval_time), evaluated_at=eval_time)
    out: dict[str, list[SliceFact]] = {}
    for load in report.loads:
        out[load.approver_node_id] = [
            SliceFact(load.approver_node_id, "authority.sole_approver_subject_count",
                      len(load.sole_subject_types),
                      f"authority:{load.approver_node_id}:sole", value_type="int"),
            SliceFact(load.approver_node_id, "authority.undelegated_subject_count",
                      len(load.undelegated_subject_types),
                      f"authority:{load.approver_node_id}:undelegated", value_type="int"),
        ]
    return out


def slices_for(conn, org_id: str, *, node_type: str, eval_time: datetime,
               limit: int = ANCHOR_BUDGET,
               absence_provider: AbsenceProvider = _no_absences,
               edge_coverage_provider: EdgeCoverageProvider = _no_edge_coverage,
               authority: AuthorityView | None = None,
               authority_subject_type: str | None = None) -> tuple[GraphSlice, ...]:
    """Every anchor of one node type, with its neighbourhood, as at `eval_time`.

    ONE QUERY PER CONCEPT, grouped in memory — the shape `refresh_situations` already keeps, and
    for the same reason: one query per anchor is fine on a fixture and quadratic on a founder's
    inbox. The reads are `valid_to is null` current-state reads; a point-in-time evaluation is
    `graph_store.read_graph(as_of=...)`'s job and is not what a live drain wants.
    """
    anchors = _rows(conn,
        "select node_id, node_type, display_name from graph_nodes "
        "where org_id = :o and node_type = :t and valid_to is null "
        "order by node_id limit :lim",
        {"o": org_id, "t": node_type, "lim": int(limit)})
    if not anchors:
        return ()
    node_ids = tuple(r.node_id for r in anchors)

    facts: dict[str, list[SliceFact]] = {}
    for row in _rows(conn,
            "select fact_version_id, subject_node_id, field, value, value_type, occurred_at "
            "from graph_facts where org_id = :o and subject_node_id = any(:ids) "
            "and valid_to is null and status = 'active' order by subject_node_id, field",
            {"o": org_id, "ids": list(node_ids)}):
        facts.setdefault(row.subject_node_id, []).append(SliceFact(
            subject_node_id=row.subject_node_id, field_path=row.field,
            value=_coerce(row.value), fact_version_id=row.fact_version_id,
            occurred_at=row.occurred_at, value_type=row.value_type or "text"))

    edges: dict[str, list[SliceEdge]] = {}
    for row in _rows(conn,
            "select edge_version_id, edge_type, from_node_id, to_node_id, confidence "
            "from graph_edges where org_id = :o and valid_to is null "
            "and (from_node_id = any(:ids) or to_node_id = any(:ids)) "
            "order by edge_version_id",
            {"o": org_id, "ids": list(node_ids)}):
        edge = SliceEdge(edge_version_id=row.edge_version_id, edge_type=row.edge_type,
                         from_node_id=row.from_node_id, to_node_id=row.to_node_id,
                         confidence_bp=int((row.confidence or 0) * 10_000))
        for side in (row.from_node_id, row.to_node_id):
            if side in node_ids:
                edges.setdefault(side, []).append(edge)

    observations: dict[str, list[SliceObservation]] = {}
    for row in _rows(conn,
            "select observation_id, subject_node_id, kind, occurred_at from graph_observations "
            "where org_id = :o and subject_node_id = any(:ids) and status = 'active' "
            "order by observation_id",
            {"o": org_id, "ids": list(node_ids)}):
        observations.setdefault(row.subject_node_id, []).append(SliceObservation(
            observation_id=row.observation_id, subject_node_id=row.subject_node_id,
            kind=row.kind, occurred_at=row.occurred_at))

    absences: dict[str, list[MissingFact]] = {}
    for absence in absence_provider(conn, org_id, node_ids) or ():
        absences.setdefault(absence.subject_node_id, []).append(absence)

    coverage = edge_coverage_provider(conn, org_id) or frozenset()
    authority_by_node = _authority_facts(authority, org_id, eval_time=eval_time)

    # Resolved ONCE per node type, not once per anchor: the answer is a property of the org and
    # the instant, and asking it per anchor is 2,000 identical queries on a real tenant.
    threshold, rule_id = _threshold_for(authority, org_id, eval_time=eval_time,
                                        subject_type=authority_subject_type or node_type)

    out: list[GraphSlice] = []
    for row in anchors:
        own_facts = tuple(facts.get(row.node_id, ())) + tuple(authority_by_node.get(row.node_id, ()))
        out.append(GraphSlice(
            org_id=org_id,
            anchor=SliceNode(row.node_id, row.node_type, row.display_name),
            facts=own_facts,
            edges=tuple(edges.get(row.node_id, ())),
            observations=tuple(observations.get(row.node_id, ())),
            absences=tuple(absences.get(row.node_id, ())),
            edge_coverage=coverage,
            authority_threshold_minor_units=threshold, authority_rule_id=rule_id,
            read_at=eval_time))
    return tuple(out)


def _threshold_for(view: AuthorityView | None, org_id: str, *, eval_time: datetime,
                   subject_type: str) -> tuple[int | None, str | None]:
    """`@authority_threshold` for this org, at this instant. `None` when no rule is in force.

    `None` and not zero, and the difference is the whole reference: a zero threshold makes "high
    value" mean "any value", and the pattern that was written about the company's largest
    contracts fires on every one of them.
    """
    if view is None:
        return None, None
    answer = view.resolve(org_id, subject_type=subject_type, evaluated_at=eval_time)
    if answer.rule is None or answer.rule.threshold_minor_units is None:
        return None, None
    return answer.rule.threshold_minor_units, answer.rule.rule_id


# =================================================================================================
# Evaluating and recording
# =================================================================================================

def evaluate_org(store, org_id: str, *, eval_time: datetime,
                 registry: PatternRegistry | None = None,
                 limit: int = ANCHOR_BUDGET,
                 absence_provider: AbsenceProvider | None = None,
                 edge_coverage_provider: EdgeCoverageProvider | None = None,
                 record: bool = True) -> EvaluationReport:
    """Run every registered pattern over one tenant and record what happened.

    Returns the candidates AND the run statistics, because the statistics are the product here:
    a pattern that fired zero times and a pattern that fired on every anchor are both defects, and
    a function that returned only the candidates would report the first as success and the second
    as a very good day.
    """
    registry = registry or seed_registry()
    absence_provider = absence_provider or stored_absence_provider
    edge_coverage_provider = edge_coverage_provider or declared_edge_coverage
    view = _authority_view(store)
    runs: list[PatternRun] = []
    with store.engine.connect() as conn:
        activation = activation_state(conn, org_id)
        for node_type in registry.anchor_types():
            slices = slices_for(conn, org_id, node_type=node_type, eval_time=eval_time,
                                limit=limit, absence_provider=absence_provider,
                                edge_coverage_provider=edge_coverage_provider, authority=view)
            for pattern in registry.for_anchor(node_type):
                runs.append(_run_one(pattern, slices, eval_time=eval_time,
                                     activated=bool(activation.get(pattern.pattern_id))))
    report = EvaluationReport(org_id=org_id, eval_time=eval_time, runs=tuple(runs))
    if record:
        record_evaluation(store, report)
    return report


def _run_one(pattern: Pattern, slices: Sequence[GraphSlice], *, eval_time: datetime,
             activated: bool) -> PatternRun:
    """One pattern over one anchor population. Pure — the slices are already read."""
    candidates: list[SituationCandidate] = []
    failures: dict[tuple[int, str], int] = {}
    first_failure: dict[tuple[int, str], ConditionFailure] = {}
    for graph_slice in slices:
        outcome = evaluate(pattern, graph_slice, eval_time=eval_time)
        if outcome.matched is not None:
            candidates.append(build_candidate(outcome.matched, graph_slice, eval_time=eval_time))
        elif outcome.failure is not None:
            key = (outcome.failure.index, outcome.failure.reason)
            failures[key] = failures.get(key, 0) + 1
            first_failure.setdefault(key, outcome.failure)
    top = None
    if failures:
        # Most common failure, ties broken by condition index — deterministic, so two runs over an
        # unchanged tenant report the same remedy.
        key = sorted(failures.items(), key=lambda kv: (-kv[1], kv[0][0], kv[0][1]))[0][0]
        top = first_failure[key]
    return PatternRun(pattern_id=pattern.pattern_id, pattern_version=pattern.version,
                      anchors_considered=len(slices), fires=len(candidates),
                      candidates=tuple(candidates), top_failure=top, activated=activated)


def record_evaluation(store, report: EvaluationReport) -> int:
    """Write the run rows and a bounded sample of the fires. Returns rows written.

    The run row is written for EVERY pattern, including the ones that fired zero times — that row
    is the only evidence a silent pattern was ever evaluated at all, and without it "no fires"
    and "never ran" are the same empty result.
    """
    written = 0
    with store.engine.begin() as conn:
        for run in report.runs:
            conn.execute(text(
                "insert into pattern_runs (run_id, org_id, pattern_id, pattern_version, "
                "  anchors_considered, fires, top_failure_index, top_failure_reason, "
                "  top_failure_field, evaluated_at) "
                "values (:id, :o, :p, :v, :a, :f, :fi, :fr, :ff, :t) "
                "on conflict (org_id, pattern_id, pattern_version, evaluated_at) do update set "
                "  anchors_considered = excluded.anchors_considered, fires = excluded.fires, "
                "  top_failure_index = excluded.top_failure_index, "
                "  top_failure_reason = excluded.top_failure_reason, "
                "  top_failure_field = excluded.top_failure_field"),
                {"id": new_id("prun"), "o": report.org_id, "p": run.pattern_id,
                 "v": run.pattern_version, "a": run.anchors_considered, "f": run.fires,
                 "fi": run.top_failure.index if run.top_failure else None,
                 "fr": run.top_failure.reason if run.top_failure else None,
                 "ff": run.top_failure.field_path if run.top_failure else None,
                 "t": report.eval_time})
            written += 1
            for candidate in run.candidates[:FIRE_WRITE_BUDGET]:
                conn.execute(text(
                    "insert into pattern_fires (fire_id, org_id, pattern_id, pattern_version, "
                    "  anchor_node_id, anchor_node_type, situation_type, match_strength_bp, "
                    "  activated, evidence, evaluated_at) "
                    "values (:id, :o, :p, :v, :n, :nt, :st, :s, :act, cast(:ev as jsonb), :t) "
                    "on conflict (org_id, pattern_id, pattern_version, anchor_node_id, "
                    "             evaluated_at) do update set "
                    "  match_strength_bp = excluded.match_strength_bp, "
                    "  activated = excluded.activated, evidence = excluded.evidence"),
                    {"id": new_id("pfir"), "o": report.org_id, "p": candidate.pattern_id,
                     "v": candidate.pattern_version, "n": candidate.anchor_node_id,
                     "nt": candidate.anchor_node_type, "st": candidate.provisional_type,
                     "s": candidate.match_strength_bp, "act": run.activated,
                     "ev": json.dumps([e.as_record()
                                       for e in candidate.per_condition_evidence], default=str),
                     "t": report.eval_time})
                written += 1
    prune_fire_log(store, report.org_id, before=report.eval_time
                   - timedelta(days=FIRE_RETENTION_DAYS))
    return written


def prune_fire_log(store, org_id: str, *, before: datetime) -> int:
    """Retention, on the same request that writes. No periodic task — the Celery broker is a
    quota-limited Upstash instance and this layer adds nothing to it."""
    with store.engine.begin() as conn:
        fires = conn.execute(text(
            "delete from pattern_fires where org_id = :o and evaluated_at < :t"),
            {"o": org_id, "t": before}).rowcount or 0
        runs = conn.execute(text(
            "delete from pattern_runs where org_id = :o and evaluated_at < :t"),
            {"o": org_id, "t": before}).rowcount or 0
    return fires + runs


# =================================================================================================
# The guard — observations, and the activation switch that reads them
# =================================================================================================

def fire_observations(conn, org_id: str, *, since: datetime,
                      until: datetime) -> tuple[FireObservation, ...]:
    """What every pattern DID over a window, from the run rows. Sorted by pattern id.

    `anchors` is the LARGEST anchor population any run in the window considered, not the sum: the
    same 400 subscriptions evaluated on twelve days are 400 anchors, and summing them would report
    4,800 and divide a genuine breach down to nothing. `fires` is likewise the largest single
    run's count rather than the sum — the question the guard asks is "how much of the population
    does this pattern match", and that is a per-evaluation ratio.
    """
    window_days = max(1, int((until - since).total_seconds()) // 86_400)
    rows = conn.execute(text(
        "select pattern_id, max(anchors_considered) as anchors, max(fires) as fires "
        "from pattern_runs where org_id = :o and evaluated_at >= :since "
        "and evaluated_at <= :until group by pattern_id order by pattern_id"),
        {"o": org_id, "since": since, "until": until}).mappings().all()
    return tuple(FireObservation(pattern_id=r["pattern_id"], fires=int(r["fires"] or 0),
                                 anchors=int(r["anchors"] or 0), window_days=window_days)
                 for r in rows)


def activation_state(conn, org_id: str) -> dict[str, bool]:
    """Which patterns are ACTIVE for this tenant. Everything else is shadow."""
    rows = conn.execute(text(
        "select pattern_id, activated_at from pattern_activation where org_id = :o"),
        {"o": org_id}).mappings().all()
    return {r["pattern_id"]: r["activated_at"] is not None for r in rows}


def activate(store, org_id: str, pattern_id: str, *, activated_by: str, eval_time: datetime,
             registry: PatternRegistry | None = None,
             window_days: int = 30) -> ActivationDecision:
    """Turn a pattern on for one tenant — IF its measured fire rate allows it.

    This is doc 06's guard at the only place it can be enforced: a pattern that has already been
    observed firing on more than ten times its declared rate does not activate, and the refusal is
    STORED, so the next person to ask why sees the rate rather than a shrug.
    """
    registry = registry or seed_registry()
    pattern = registry.get(pattern_id)
    if pattern is None:
        raise KeyError(f"no registered pattern {pattern_id!r}")
    since = eval_time - timedelta(days=window_days)
    with store.engine.connect() as conn:
        observed = {o.pattern_id: o for o in fire_observations(conn, org_id, since=since,
                                                               until=eval_time)}
    observation = observed.get(pattern_id, FireObservation(pattern_id, 0, 0, window_days))
    decision = activation_decision(pattern, observation)
    with store.engine.begin() as conn:
        conn.execute(text(
            "insert into pattern_activation (org_id, pattern_id, activated_at, activated_by, "
            "  blocked_reason, blocked_at, updated_at) "
            "values (:o, :p, :at, :by, :reason, :bat, :now) "
            "on conflict (org_id, pattern_id) do update set "
            "  activated_at = excluded.activated_at, activated_by = excluded.activated_by, "
            "  blocked_reason = excluded.blocked_reason, blocked_at = excluded.blocked_at, "
            "  updated_at = excluded.updated_at"),
            {"o": org_id, "p": pattern_id,
             "at": eval_time if decision.allowed else None,
             "by": activated_by if decision.allowed else None,
             "reason": None if decision.allowed else decision.reason,
             "bat": None if decision.allowed else eval_time, "now": eval_time})
    if not decision.allowed:
        _log.warning("pattern activation refused org=%s pattern=%s %s",
                     org_id, pattern_id, decision.reason)
    return decision


def deactivate(store, org_id: str, pattern_id: str, *, eval_time: datetime) -> bool:
    """Back to shadow. Reversible by design — a pattern that could not be turned off would be a
    pattern nobody dares turn on."""
    with store.engine.begin() as conn:
        return (conn.execute(text(
            "update pattern_activation set activated_at = null, activated_by = null, "
            "  updated_at = :now where org_id = :o and pattern_id = :p"),
            {"o": org_id, "p": pattern_id, "now": eval_time}).rowcount or 0) > 0


def _authority_view(store) -> AuthorityView | None:
    """The Authority view over the same engine, or None when it cannot be built.

    `None` rather than a raise: an org with no authority rules must still be able to evaluate the
    five patterns that do not reference a threshold, and the one that does fails its condition
    with `reference_unresolved` — which is exactly what the report should say.
    """
    try:
        return AuthorityView(PostgresAuthorityRules(store.engine))
    except Exception as exc:                       # pragma: no cover — defensive
        _log.warning("authority view unavailable: %s", exc)
        return None


def utc_now() -> datetime:
    """The clock, read at the process boundary and nowhere else in this package.

    Named and exported so a route can call it and every function below it can take `eval_time` as
    a parameter. `datetime.now()` appears in this package exactly once — here.
    """
    return datetime.now(timezone.utc)


__all__ = ["ANCHOR_BUDGET", "FIRE_RETENTION_DAYS", "FIRE_WRITE_BUDGET", "AbsenceProvider",
           "EdgeCoverageProvider", "EvaluationReport", "PatternRun", "activate",
           "activation_state", "deactivate", "declare_edge_coverage",
           "declared_edge_coverage", "evaluate_org", "fire_observations",
           "prune_fire_log", "record_evaluation", "slices_for",
           "stored_absence_provider", "utc_now"]
