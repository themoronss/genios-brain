"""Layer 5 — the two passes that make the layer a running system rather than a library.

**Pass 1, ``plan_commitments``** turns authoritative Layer 4 decisions into commitments.  It
reads open signals that still prove out against ``reason/authority.py``'s predicate, builds an
execution object for each, and writes it once.  Idempotent by construction: the partial unique
index on ``(org_id, decision_hash)`` absorbs the second attempt, so running this every five
minutes is safe and running it twice concurrently is safe.

**Pass 2, ``run_lifecycle``** is the part the layer exists for.  For every commitment whose next
check has come due it re-validates against live state, moves the state machine, decides whether
to speak, fires the escalation rung the plan promised, and — when the commitment ends — writes
the outcome record Layer 7 will learn from.

The order inside pass 2 is the whole design and is worth stating plainly:

    validate → transition → observe → decide → speak

Validation comes first, always.  Never "remind, then check".  The single most damaging thing a
system like this can do is nudge somebody about work the world already finished, and the only
structural defence is to make the guard unskippable — every path to a message goes through it.

Nothing here is clever about batching or concurrency.  Both passes take a limit, both are
ordered deterministically, and both use guarded writes, so two workers running the same sweep
produce the same result as one — just faster.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import text

from genios_engine.contracts.execution import ExecutionObject, ExecutionState
from genios_engine.executive import execution_store as store
from genios_engine.executive.assignment import (
    PgSeatDirectory,
    resolve_escalation_target,
    resolve_owner,
)
from genios_engine.executive.collect import collect_outcome
from genios_engine.executive.communication import reassign as reassign_plan
from genios_engine.executive.execution import build_execution, execution_config
from genios_engine.executive.execution_guard import GuardAction, validate, validate_for_delivery
from genios_engine.executive.interpret import build_context
from genios_engine.executive.lifecycle import (
    EVENT_SUPPRESSED,
    LifecycleError,
    next_state,
    transition,
)
from genios_engine.executive.monitor import observe
from genios_engine.executive.reminder import decide_reminder
from genios_engine.platform.logging import get_logger
from genios_engine.reason.authority import (
    AUTHORITATIVE_SIGNAL_JOINS,
    AUTHORITATIVE_SIGNAL_PREDICATE,
    authority_time,
)

SWEEP_VERSION = "exec_sweep.v1"

_log = get_logger("genios.executive.sweep")

#: Signals eligible to become commitments: open, unexpired, and still authoritative. The heavy
#: lifting is the shared predicate — this query adds only "and no live commitment exists yet",
#: which is what makes the pass idempotent without a separate bookkeeping table.
_PLANNABLE_SIGNALS = (
    "select s.signal_id, s.subject_node_id, s.node_type, rr.run_id, rr.capability_id, "
    "rr.capability_version, rr.config_snapshot_id, rr.context_snapshot_id, "
    "ro.decision_hash, ro.decision_core, ro.confidence_bp as decision_confidence_bp, "
    "ro.missing_data, selected_rc.candidate_id, selected_rc.play_id, selected_rc.play_version, "
    "selected_rc.parameters, selected_rc.score_components, selected_rc.final_utility_bp, "
    "selected_rc.evidence_refs "
    "from signals s " + AUTHORITATIVE_SIGNAL_JOINS +
    " where s.org_id=:o and (" + AUTHORITATIVE_SIGNAL_PREDICATE + ") "
    "and not exists (select 1 from executions x where x.org_id=s.org_id "
    "and x.decision_hash=ro.decision_hash and x.closed_at is null) "
    "order by selected_rc.final_utility_bp desc, s.signal_id asc limit :l"
)


@dataclass(frozen=True, slots=True)
class SweepReport:
    """What a pass did, in numbers an operator can alarm on.

    Refusals are counted by reason rather than lumped together.  A sweep that plans nothing
    because every decision was ``no_action`` is healthy; one that plans nothing because every
    build hit ``window_closed`` is a misconfigured pack, and a single "skipped" counter cannot
    tell those apart.
    """

    examined: int = 0
    created: int = 0
    reminded: int = 0
    escalated: int = 0
    transitioned: int = 0
    reassigned: int = 0
    closed: int = 0
    reasons: Mapping[str, int] = field(default_factory=dict)


def _bump(counts: dict[str, int], code: str) -> None:
    counts[code] = counts.get(code, 0) + 1


def _json_field(value: Any) -> Any:
    return json.loads(value) if isinstance(value, str) else value


def _decision_core(row: Mapping[str, Any]) -> dict[str, Any]:
    core = _json_field(row["decision_core"]) or {}
    return core if isinstance(core, Mapping) else {}


def _expires_at(core: Mapping[str, Any]) -> datetime | None:
    """Read the decision's expiry out of the stored core.

    The value is canonically tagged (``{"$datetime": …}``), and a commitment must never be built
    on a guess about when its authority ends — so an unreadable expiry is a refusal, not a
    default.
    """
    raw = core.get("expires_at")
    if isinstance(raw, Mapping):
        raw = raw.get("$datetime")
    if not isinstance(raw, str):
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _node_facts(conn, org_id: str, node_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
    """Current typed facts and node attributes for the commitment's subject.

    Only what ownership resolution needs.  Loading the whole node would be simpler and would
    also quietly make routing depend on fields nobody declared it depended on.
    """
    rows = conn.execute(text(
        "select field, value from graph_facts where org_id=:o and subject_node_id=:n "
        "and valid_to is null"), {"o": org_id, "n": node_id}).fetchall()
    facts = {item.field: item.value for item in rows}
    node = conn.execute(text(
        "select attrs from graph_nodes where org_id=:o and node_id=:n and valid_to is null"),
        {"o": org_id, "n": node_id}).mappings().first()
    attrs = _json_field((node or {}).get("attrs")) or {}
    return facts, (attrs if isinstance(attrs, Mapping) else {})


def plan_commitments(engine, org_id: str, *, eval_time: datetime | None = None,
                     effective: Mapping[str, Any] | None = None,
                     limit: int = 100) -> SweepReport:
    """Turn every authoritative, uncommitted decision for this org into a commitment."""
    now = eval_time or authority_time()
    cfg = execution_config(effective)
    counts: dict[str, int] = {}
    examined = created = 0

    with engine.begin() as conn:
        channels = store.active_channels(conn, org_id)
        directory = PgSeatDirectory(conn=conn, org_id=org_id)
        rows = conn.execute(text(_PLANNABLE_SIGNALS),
                            {"o": org_id, "l": int(limit),
                             "authority_time": now}).mappings().all()

        for row in rows:
            examined += 1
            core = _decision_core(row)
            expires_at = _expires_at(core)
            if expires_at is None:
                _bump(counts, "unreadable_expiry")
                continue

            interpretation = build_context(
                org_id=org_id,
                parameters=_json_field(row["parameters"]) or {},
                capability_id=row["capability_id"],
                capability_version=row["capability_version"],
                play_id=row["play_id"], play_version=row["play_version"],
                decision_hash=row["decision_hash"], candidate_id=row["candidate_id"],
                context_snapshot_id=row["context_snapshot_id"],
                reasoning_run_id=row["run_id"],
                config_snapshot_id=row["config_snapshot_id"],
                expires_at=expires_at,
                do_nothing_consequence=str(core.get("do_nothing_consequence") or
                                           "No further action is taken on this."),
                priority_bp=int(row["final_utility_bp"] or 0),
                confidence_bp=int(row["decision_confidence_bp"] or 0),
                urgency_bp=int((_json_field(row["score_components"]) or {}).get(
                    "urgency", row["final_utility_bp"] or 0)),
                outcome_window_days=core.get("outcome_window_days"),
                uncertainty=tuple(_json_field(row["missing_data"]) or ()),
                evidence_ids=tuple(sorted(
                    str(item.get("evidence_id")) for item in
                    (_json_field(row["evidence_refs"]) or []) if item.get("evidence_id"))),
                subject_ref=row["subject_node_id"], subject_type=row["node_type"])
            if not interpretation.actionable:
                _bump(counts, interpretation.reason_code)
                continue

            context = interpretation.require()
            facts, attrs = _node_facts(conn, org_id, row["subject_node_id"])
            assignment = resolve_owner(facts=facts, attrs=attrs, directory=directory)
            result = build_execution(context, assignment=assignment, eval_time=now,
                                     available_channels=channels, cfg=cfg)
            _bump(counts, result.reason_code)
            if not result.built:
                continue

            written = store.persist(conn, result.require(),
                                    next_check_at=now, signal_id=row["signal_id"])
            if written["created"]:
                created += 1

    return SweepReport(examined=examined, created=created, reasons=counts)


def _close(conn, execution: ExecutionObject, row: Mapping[str, Any], *, target: ExecutionState,
           reason_code: str, detail: str, now: datetime, report) -> bool:
    """Terminate a commitment and record what it taught us, in one transaction.

    The outcome record is written *with* the closing transition rather than after it. A
    commitment that closed without producing an outcome row is invisible to Layer 7 forever,
    and there is no reconciliation job that can invent the progress it had at the moment it
    ended.
    """
    move = transition(ExecutionState(row["state"]), target, reason_code=reason_code,
                      actor="system", at=now, detail=detail)
    if not store.apply_transition(conn, org_id=execution.org_id,
                                  execution_id=execution.execution_id, move=move, close=True):
        return False
    outcome = collect_outcome(execution, terminal_state=target, reason_code=reason_code,
                              closed_at=now, report=report,
                              reminders_sent=int(row.get("reminder_count") or 0),
                              escalations_fired=int(row.get("escalation_count") or 0))
    store.record_outcome(conn, outcome)
    return True


def run_lifecycle(engine, *, eval_time: datetime | None = None,
                  effective: Mapping[str, Any] | None = None, limit: int = 200,
                  org_id: str | None = None) -> SweepReport:
    """One lifecycle pass over every commitment that has come due.

    Each commitment is handled in its own transaction.  A malformed payload or a lost race on
    one must not roll back the twenty that were processed correctly before it — this sweep is
    the only thing keeping commitments moving, and an all-or-nothing pass would let a single bad
    row stop the layer.
    """
    now = eval_time or authority_time()
    cfg = execution_config(effective)
    counts: dict[str, int] = {}
    examined = reminded = escalated = moved = reassigned = closed = 0

    with engine.connect() as conn:
        due = store.due_executions(conn, now=now, limit=limit, org_id=org_id)

    for row in due:
        examined += 1
        try:
            with engine.begin() as conn:
                outcome_code = _process_one(conn, row, now=now, cfg=cfg)
        except (LifecycleError, ValueError, KeyError) as exc:
            # Deliberately narrow. A commitment whose stored plan no longer validates is a real
            # defect that must be visible and must not stall the sweep, so it is logged, counted
            # and skipped — never silently repaired into something deliverable.
            _log.exception("execution %s could not be processed: %s", row["execution_id"], exc)
            _bump(counts, "processing_error")
            continue

        _bump(counts, outcome_code.code)
        reminded += outcome_code.reminded
        escalated += outcome_code.escalated
        moved += outcome_code.transitioned
        reassigned += outcome_code.reassigned
        closed += outcome_code.closed

    return SweepReport(examined=examined, reminded=reminded, escalated=escalated,
                       transitioned=moved, reassigned=reassigned, closed=closed, reasons=counts)


@dataclass(frozen=True, slots=True)
class _Step:
    code: str
    reminded: int = 0
    escalated: int = 0
    transitioned: int = 0
    reassigned: int = 0
    closed: int = 0


def _process_one(conn, row: Mapping[str, Any], *, now: datetime,
                 cfg: Mapping[str, Any]) -> _Step:
    """Validate → transition → observe → decide → speak, for one commitment."""
    org_id = row["org_id"]
    loaded = store.load(conn, org_id, row["execution_id"])
    if loaded is None:
        return _Step("vanished")
    execution, current = loaded
    state = ExecutionState(current["state"])

    validation = store.validation_input(conn, execution, current, now=now,
                                        signal_id=current.get("signal_id"))
    verdict = (validate_for_delivery(execution, validation)
               if state is ExecutionState.CREATED else validate(execution, validation))

    # --- the commitment ends here -------------------------------------------------------
    terminal = verdict.terminal_state
    if terminal is not None:
        report = observe(execution, now=now,
                         action_completions=store.action_completions(
                             conn, org_id, execution.execution_id),
                         observed_events=validation.observed_events)
        if _close(conn, execution, current, target=terminal, reason_code=verdict.reason_code,
                  detail=verdict.detail, now=now, report=report):
            return _Step(verdict.reason_code, closed=1)
        return _Step("close_lost_race")

    # --- the work is fine, the person is not --------------------------------------------
    if verdict.action is GuardAction.REROUTE:
        directory = PgSeatDirectory(conn=conn, org_id=org_id)
        facts, attrs = ({}, {})
        if execution.subject_ref:
            facts, attrs = _node_facts(conn, org_id, execution.subject_ref)
        assignment = resolve_owner(facts=facts, attrs=attrs, directory=directory)
        plan = reassign_plan(execution.communication, assignment, reason_code="owner_inactive")
        store.reassign(conn, org_id=org_id, execution_id=execution.execution_id,
                       assignee=plan.assignee, audience=plan.audience.value,
                       routing_rule=plan.reason_code, at=now)
        return _Step("rerouted", reassigned=1)

    if verdict.action is GuardAction.SUPPRESS:
        store.log_event(conn, org_id=org_id, execution_id=execution.execution_id,
                        kind=EVENT_SUPPRESSED, reason_code=verdict.reason_code,
                        detail={"detail": verdict.detail}, occurred_at=now)
        # Still schedule the next look. A suppressed moment is not a closed commitment, and a
        # blocked one in particular must keep escalating — that is how a block gets unblocked.
        decision = decide_reminder(execution, state=state,
                                   history=store.reminder_state(conn, org_id,
                                                                execution.execution_id, current),
                                   now=now, cfg=cfg.get("reminder"))
        conn.execute(text("update executions set next_check_at=:n, updated_at=now() "
                          "where org_id=:o and execution_id=:x"),
                     {"n": decision.next_check_at, "o": org_id, "x": execution.execution_id})
        return _Step(f"suppressed_{verdict.reason_code}")

    # --- first delivery ------------------------------------------------------------------
    transitions = 0
    if state is ExecutionState.CREATED:
        move = transition(state, ExecutionState.PENDING, reason_code="validated",
                          actor="system", at=now, detail=verdict.detail)
        if store.apply_transition(conn, org_id=org_id, execution_id=execution.execution_id,
                                  move=move, next_check_at=now):
            conn.execute(text("update executions set delivered_at=coalesce(delivered_at,:n) "
                              "where org_id=:o and execution_id=:x"),
                         {"n": now, "o": org_id, "x": execution.execution_id})
            state, transitions = ExecutionState.PENDING, 1

    # --- how far has it actually got ------------------------------------------------------
    report = observe(execution, now=now,
                     action_completions=store.action_completions(conn, org_id,
                                                                 execution.execution_id),
                     observed_events=validation.observed_events, cfg=cfg.get("monitor"))
    target = next_state(state, verdict, report)
    if target is not None:
        move = transition(state, target, reason_code=report.detail[:64] or "progress",
                          actor="system", at=now, detail=report.detail)
        if store.apply_transition(conn, org_id=org_id, execution_id=execution.execution_id,
                                  move=move, next_check_at=now):
            state, transitions = target, transitions + 1

    # --- speak, or say why not ------------------------------------------------------------
    history = store.reminder_state(conn, org_id, execution.execution_id, current)
    decision = decide_reminder(execution, state=state, history=history, now=now,
                               cfg=cfg.get("reminder"))
    if not decision.should_remind:
        conn.execute(text("update executions set next_check_at=:n, updated_at=now() "
                          "where org_id=:o and execution_id=:x"),
                     {"n": decision.next_check_at, "o": org_id, "x": execution.execution_id})
        return _Step(f"quiet_{decision.reason_code}", transitioned=transitions)

    fired = 0
    if decision.escalating:
        directory = PgSeatDirectory(conn=conn, org_id=org_id)
        rung = next(step for step in execution.escalation
                    if step.day_offset == decision.escalation_day)
        target_seat = resolve_escalation_target(
            audience=rung.audience, owner_seat=current.get("assignee"), directory=directory)
        if store.fire_escalation(conn, org_id=org_id, execution_id=execution.execution_id,
                                 day_offset=rung.day_offset, at=now,
                                 target_seat=target_seat.seat_id, reason_code=rung.reason_code):
            fired = 1

    store.record_reminder(conn, org_id=org_id, execution_id=execution.execution_id, at=now,
                          reason_code=decision.reason_code,
                          next_check_at=decision.next_check_at, urgency=decision.urgency,
                          escalation_day=decision.escalation_day)
    return _Step(f"reminded_{decision.reason_code}", reminded=1, escalated=fired,
                 transitioned=transitions)


def run_executive(engine, org_id: str, *, eval_time: datetime | None = None,
                  effective: Mapping[str, Any] | None = None) -> dict[str, SweepReport]:
    """Both passes for one org — the entry point a scheduler calls.

    Planning runs first so a commitment created this minute gets its first validation in the
    same pass rather than waiting for the next one.
    """
    now = eval_time or authority_time()
    planned = plan_commitments(engine, org_id, eval_time=now, effective=effective)
    lifecycle = run_lifecycle(engine, eval_time=now, effective=effective, org_id=org_id)
    return {"planned": planned, "lifecycle": lifecycle}


__all__ = ["SWEEP_VERSION", "SweepReport", "plan_commitments", "run_executive", "run_lifecycle"]
