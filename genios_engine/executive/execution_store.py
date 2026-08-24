"""Layer 5 — the persistence seam for commitments.

Every other module in this layer is pure: decisions in, artifacts out, no clock, no database.
That is what lets the whole layer be tested without Postgres, which matters because CI has no
service containers.  This module is where that purity is deliberately spent, and it is kept as
thin as it can be — it reads rows, writes rows, and makes no judgements of its own.

Two invariants are enforced *here* rather than trusted to callers, because they are the ones a
distributed sweep will otherwise violate:

**One live commitment per decision.**  ``executions_one_per_decision`` is a partial unique index
on open rows.  The upsert below leans on it: two workers racing over the same decision produce
one row, and the loser's write is absorbed rather than retried.

**Guarded state transitions.**  Every state change carries an ``allowed_from`` set in its
``where`` clause, exactly like ``deliver/store.py``.  A transition that finds no row did not
fail — it lost a race to somebody who moved the commitment first, and the correct response is to
re-read, not to force.  The same pattern makes the escalation and reminder writes idempotent:
firing a rung twice is impossible because the second update matches nothing.

Nothing here decides whether to send.  ``due_executions`` returns *candidates*; the guard
decides.  Keeping the scheduler ignorant of that judgement is what stops a query optimisation
from quietly becoming a policy change.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import datetime
from typing import Any

from sqlalchemy import text

from genios_engine.contracts.execution import ExecutionObject, ExecutionState
from genios_engine.executive.collect import ExecutionOutcome
from genios_engine.executive.execution_guard import ValidationInput
from genios_engine.executive.lifecycle import Transition
from genios_engine.executive.reminder import ReminderState
from genios_engine.platform.canonical import canonical_dumps
from genios_engine.platform.ids import new_id
from genios_engine.reason.authority import (
    AUTHORITATIVE_SIGNAL_JOINS,
    AUTHORITATIVE_SIGNAL_PREDICATE,
)

STORE_VERSION = "exec_store.v1"

_EXECUTION_COLUMNS = (
    "org_id, execution_id, decision_hash, reasoning_run_id, candidate_id, context_snapshot_id, "
    "config_snapshot_id, capability_id, capability_version, play_id, plan_hash, state, goal, "
    "subject_ref, subject_type, assignee, audience, channel_id, channel_class, interrupt, "
    "routing_rule, priority_bp, confidence_bp, band, created_at, deadline_at, expires_at, "
    "next_check_at, closed_at, close_reason, superseded_by, reminder_count, last_reminded_at, "
    "escalation_count, delivered_at, first_touch_at, card_id, signal_id, plan_revision, payload")


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def log_event(conn, *, org_id: str, execution_id: str, kind: str, reason_code: str,
              actor: str = "system", from_state: str | None = None, to_state: str | None = None,
              detail: Mapping[str, Any] | None = None, occurred_at: datetime | None = None) -> str:
    """Append one audit row.  Never conditional — an event that only sometimes lands is worse
    than no event at all, because it makes the log look complete when it is not."""
    event_id = new_id("exev")
    conn.execute(text(
        "insert into execution_events (event_id, org_id, execution_id, kind, reason_code, "
        "actor, from_state, to_state, detail, occurred_at) values "
        "(:e, :o, :x, :k, :r, :a, :f, :t, cast(:d as jsonb), coalesce(:at, now()))"),
        {"e": event_id, "o": org_id, "x": execution_id, "k": kind, "r": reason_code,
         "a": actor, "f": from_state, "t": to_state, "d": _json(dict(detail or {})),
         "at": occurred_at})
    return event_id


def persist(conn, execution: ExecutionObject, *, next_check_at: datetime | None = None,
            signal_id: str | None = None, card_id: str | None = None,
            state: ExecutionState = ExecutionState.CREATED) -> dict[str, Any]:
    """Write a commitment, its steps and its ladder as one unit.

    Returns ``{"created": bool, "execution_id": str}``.  ``created`` is False when the decision
    already had a live commitment — the normal outcome of a repeat sweep, not an error, and the
    caller should treat it as "nothing to do" rather than retrying.

    The conflict target is ``(org_id, decision_hash) where closed_at is null``, so a re-plan of
    the *same* decision updates the routing and the schedule in place while leaving the plan and
    its identity alone.  Changing the plan itself is a supersede, not an update: see
    ``supersede``.
    """
    metadata = dict(execution.metadata)
    comms = execution.communication
    params = {
        "o": execution.org_id, "x": execution.execution_id,
        "dh": execution.decision_hash, "rr": execution.reasoning_run_id,
        "cd": execution.candidate_id, "cs": execution.context_snapshot_id,
        "cfg": execution.config_snapshot_id, "cap": execution.capability_id,
        "capv": execution.capability_version, "play": metadata.get("play_id"),
        "ph": execution.plan_hash, "st": state.value, "goal": execution.goal,
        "sref": execution.subject_ref, "stype": metadata.get("subject_type"),
        "asg": comms.assignee, "aud": comms.audience.value, "ch": comms.channel_id,
        "chc": comms.channel_class.value, "int": comms.interrupt,
        "rule": metadata.get("routing_rule") or comms.reason_code,
        "pri": execution.priority_bp, "conf": execution.confidence_bp,
        "band": metadata.get("band") or "standard", "cat": execution.created_at,
        "dl": execution.deadline_at, "exp": execution.expires_at,
        "nca": next_check_at, "sig": signal_id, "card": card_id,
        "pl": canonical_dumps(execution.to_semantic_dict()),
    }
    row = conn.execute(text(
        "insert into executions (" + _EXECUTION_COLUMNS + ") values "
        "(:o, :x, :dh, :rr, :cd, :cs, :cfg, :cap, :capv, :play, :ph, :st, :goal, :sref, :stype, "
        ":asg, :aud, :ch, :chc, :int, :rule, :pri, :conf, :band, :cat, :dl, :exp, :nca, "
        "null, null, null, 0, null, 0, null, null, :card, :sig, 1, cast(:pl as jsonb)) "
        "on conflict (org_id, decision_hash) where closed_at is null do nothing "
        "returning execution_id"), params).first()
    if row is None:
        return {"created": False, "execution_id": execution.execution_id}

    for action in execution.actions:
        conn.execute(text(
            "insert into execution_actions (org_id, execution_id, action_id, ordinal, stage, "
            "kind, label, requires_approval, read_only, deadline_at) values "
            "(:o, :x, :a, :ord, :stg, :k, :l, :ra, :ro, :dl) "
            "on conflict (org_id, execution_id, action_id) do nothing"),
            {"o": execution.org_id, "x": execution.execution_id, "a": action.action_id,
             "ord": action.ordinal, "stg": action.stage, "k": action.kind.value,
             "l": action.label, "ra": action.requires_approval, "ro": action.read_only,
             "dl": action.deadline_at})

    for step in execution.escalation:
        conn.execute(text(
            "insert into execution_escalations (org_id, execution_id, day_offset, action, "
            "audience, interrupt, fires_at, reason_code) values "
            "(:o, :x, :d, :a, :au, :i, :f, :r) "
            "on conflict (org_id, execution_id, day_offset) do nothing"),
            {"o": execution.org_id, "x": execution.execution_id, "d": step.day_offset,
             "a": step.action.value, "au": step.audience.value, "i": step.interrupt,
             "f": step.fires_at, "r": step.reason_code})

    log_event(conn, org_id=execution.org_id, execution_id=execution.execution_id,
              kind="execution.created", reason_code="built", to_state=state.value,
              detail={"plan_hash": execution.plan_hash, "actions": len(execution.actions),
                      "channel": comms.channel_id, "assignee": comms.assignee,
                      "routing_rule": params["rule"]},
              occurred_at=execution.created_at)
    return {"created": True, "execution_id": execution.execution_id}


def load(conn, org_id: str, execution_id: str) -> tuple[ExecutionObject, Any] | None:
    """Rehydrate a commitment, re-validating the stored plan on the way in."""
    row = conn.execute(text(
        "select * from executions where org_id=:o and execution_id=:x"),
        {"o": org_id, "x": execution_id}).mappings().first()
    if row is None:
        return None
    payload = row["payload"]
    if isinstance(payload, str):
        payload = json.loads(payload)
    return ExecutionObject.from_semantic_dict(payload), row


def due_executions(conn, *, now: datetime, limit: int = 200,
                   org_id: str | None = None) -> list[Any]:
    """Open commitments whose next check has come due.

    ``next_check_at is null`` is included on purpose: a freshly created commitment has not been
    scheduled yet, and excluding it would leave the very first delivery waiting for a check time
    that nothing ever sets.
    """
    clause = "and org_id=:o " if org_id else ""
    params: dict[str, Any] = {"n": now, "l": int(limit)}
    if org_id:
        params["o"] = org_id
    return conn.execute(text(
        "select * from executions where closed_at is null "
        "and (next_check_at is null or next_check_at <= :n) " + clause +
        "order by next_check_at asc nulls first, priority_bp desc, execution_id asc "
        "limit :l"), params).mappings().all()


def reminder_state(conn, org_id: str, execution_id: str, row: Any | None = None) -> ReminderState:
    """What has already been said, and which rungs have already fired."""
    if row is None:
        row = conn.execute(text(
            "select reminder_count, last_reminded_at from executions "
            "where org_id=:o and execution_id=:x"),
            {"o": org_id, "x": execution_id}).mappings().first() or {}
    fired = conn.execute(text(
        "select day_offset from execution_escalations where org_id=:o and execution_id=:x "
        "and fired_at is not null"), {"o": org_id, "x": execution_id}).fetchall()
    return ReminderState(reminder_count=int(row.get("reminder_count") or 0),
                         last_reminded_at=row.get("last_reminded_at"),
                         fired_escalation_days=frozenset(item.day_offset for item in fired))


def authority_valid(conn, org_id: str, signal_id: str | None, *, now: datetime) -> bool:
    """Re-run Layer 4's authority predicate for this commitment's signal.

    Delegated to ``reason/authority.py`` rather than reimplemented.  This predicate is the single
    hardest thing in the codebase to get right, and a second copy that drifted would mean a
    commitment could keep escalating on the strength of a decision the delivery path had already
    stopped trusting.

    ``now`` is passed rather than taken from the clock because the predicate binds
    ``:authority_time``: the same instant must judge the guard, the transition and the outbox, or
    a commitment could be authoritative for one and expired for the next within a single sweep.

    A commitment with no signal link is treated as authoritative: it came from a path that does
    not project into ``signals`` at all, and inventing a failure for it would suppress correct
    work.  Its authority is still bounded by ``expires_at``, which the guard checks separately.
    """
    if not signal_id:
        return True
    row = conn.execute(text(
        "select 1 from signals s " + AUTHORITATIVE_SIGNAL_JOINS +
        " where s.org_id=:o and s.signal_id=:s and (" + AUTHORITATIVE_SIGNAL_PREDICATE + ") "
        "limit 1"),
        {"o": org_id, "s": signal_id, "authority_time": now}).first()
    return row is not None


def validation_input(conn, execution: ExecutionObject, row: Any, *, now: datetime,
                     signal_id: str | None = None) -> ValidationInput:
    """Gather exactly what the guard is allowed to look at, in one pass.

    Assembled here rather than inside the guard so the judgement stays pure and, more
    importantly, so the *inputs to a suppression* can be stored next to the verdict.  Without
    that, "why was this suppressed?" is only answerable by re-querying a world that has since
    moved on.
    """
    org_id = execution.org_id
    observed: dict[str, datetime] = {}
    wanted = list(execution.monitoring_events)
    if wanted and execution.subject_ref:
        rows = conn.execute(text(
            "select kind, max(occurred_at) as seen from graph_observations "
            "where org_id=:o and subject_node_id=:n and kind = any(:k) and occurred_at > :since "
            "group by kind"),
            {"o": org_id, "n": execution.subject_ref, "k": wanted,
             "since": execution.created_at}).fetchall()
        observed = {item.kind: item.seen for item in rows}

    subject_status = None
    subject_missing = False
    if execution.subject_ref:
        node = conn.execute(text(
            "select 1 from graph_nodes where org_id=:o and node_id=:n and valid_to is null"),
            {"o": org_id, "n": execution.subject_ref}).first()
        subject_missing = node is None
        status = conn.execute(text(
            "select value from graph_facts where org_id=:o and subject_node_id=:n "
            "and field in ('deal.status','relationship.status','account.status') "
            "and valid_to is null order by field limit 1"),
            {"o": org_id, "n": execution.subject_ref}).first()
        if status is not None:
            raw = status.value
            subject_status = str(raw.get("value") if isinstance(raw, Mapping) else raw or "")

    owner_active = True
    if execution.communication.assignee:
        seat = conn.execute(text(
            "select 1 from org_seats where org_id=:o and seat_id=:s and active"),
            {"o": org_id, "s": execution.communication.assignee}).first()
        owner_active = seat is not None

    superseded = conn.execute(text(
        "select execution_id from executions where org_id=:o and subject_ref=:n and play_id=:p "
        "and closed_at is null and execution_id <> :x and created_at > :cat "
        "order by created_at desc limit 1"),
        {"o": org_id, "n": execution.subject_ref, "p": dict(execution.metadata).get("play_id"),
         "x": execution.execution_id, "cat": execution.created_at}).first()

    dismissed = conn.execute(text(
        "select 1 from execution_events where org_id=:o and execution_id=:x "
        "and kind='execution.cancelled' and reason_code='human_dismissed' limit 1"),
        {"o": org_id, "x": execution.execution_id}).first()

    return ValidationInput(
        now=now, state=ExecutionState(row["state"]),
        authority_valid=authority_valid(conn, org_id, signal_id or row.get("signal_id"),
                                        now=now),
        observed_events=observed, subject_status=subject_status, owner_active=owner_active,
        superseded_by=(superseded.execution_id if superseded else None),
        dismissed=dismissed is not None, subject_missing=subject_missing)


def apply_transition(conn, *, org_id: str, execution_id: str, move: Transition,
                     close: bool = False, next_check_at: datetime | None = None) -> bool:
    """Move a commitment, guarded on its current state.

    Returns False when the row was not in the expected state.  That is a lost race, not a
    failure: another worker, a human action or the sweep itself already moved it, and their move
    is the one that counts.  Forcing the write would overwrite a real event with a stale one.
    """
    result = conn.execute(text(
        "update executions set state=:to, updated_at=now(), "
        "next_check_at=case when :close then null else cast(:nca as timestamptz) end, "
        "closed_at=case when :close then :at else closed_at end, "
        "close_reason=case when :close then :reason else close_reason end "
        "where org_id=:o and execution_id=:x and state=:frm and closed_at is null"),
        {"to": move.to_state.value, "frm": move.from_state.value, "o": org_id,
         "x": execution_id, "close": close, "at": move.at, "reason": move.reason_code,
         "nca": next_check_at})
    if result.rowcount != 1:
        return False
    log_event(conn, org_id=org_id, execution_id=execution_id, kind=move.event_kind,
              reason_code=move.reason_code, actor=move.actor,
              from_state=move.from_state.value, to_state=move.to_state.value,
              detail={"detail": move.detail}, occurred_at=move.at)
    return True


def record_reminder(conn, *, org_id: str, execution_id: str, at: datetime, reason_code: str,
                    next_check_at: datetime | None, urgency: str,
                    escalation_day: int | None = None,
                    facts: Mapping[str, Any] | None = None) -> str:
    """Count the reminder, schedule the next look, say why it fired — and carry the vocabulary.

    ``facts`` is the grounded corpus from ``reminder.reminder_facts``: every value a reminder is
    permitted to be worded from, all of it derived from the commitment itself.  Storing it on the
    event is what makes the Layer 6 bridge possible without inverting the layer order — Layer 5
    says *what may be said*, Layer 6 decides *how it looks on Slack*, and Layer 6 never has to
    reach back into Layer 5's logic to find out what is true.

    Returns the event id so the caller can address this exact reminder downstream.
    """
    conn.execute(text(
        "update executions set reminder_count=reminder_count+1, last_reminded_at=:at, "
        "next_check_at=:nca, updated_at=now() where org_id=:o and execution_id=:x"),
        {"at": at, "nca": next_check_at, "o": org_id, "x": execution_id})
    return log_event(conn, org_id=org_id, execution_id=execution_id,
                     kind="execution.reminded", reason_code=reason_code,
                     detail={"urgency": urgency, "escalation_day": escalation_day,
                             "facts": dict(facts or {})},
                     occurred_at=at)


def link_card(conn, *, org_id: str, execution_id: str, card_id: str) -> bool:
    """Point a commitment at the Layer 6 card that surfaces it.

    Guarded on ``card_id is null`` so the link is written once and a later re-render cannot
    silently repoint a commitment at a different card — the audit trail would then describe a
    surface that no longer shows this work.
    """
    result = conn.execute(text(
        "update executions set card_id=:c, updated_at=now() "
        "where org_id=:o and execution_id=:x and card_id is null"),
        {"c": card_id, "o": org_id, "x": execution_id})
    return result.rowcount == 1


def fire_escalation(conn, *, org_id: str, execution_id: str, day_offset: int, at: datetime,
                    target_seat: str | None, reason_code: str) -> bool:
    """Mark a rung fired.  Idempotent by construction: the guard on ``fired_at is null`` means
    a re-run of a sweep that already fired this rung updates nothing and returns False."""
    result = conn.execute(text(
        "update execution_escalations set fired_at=:at, target_seat=:t "
        "where org_id=:o and execution_id=:x and day_offset=:d and fired_at is null"),
        {"at": at, "t": target_seat, "o": org_id, "x": execution_id, "d": day_offset})
    if result.rowcount != 1:
        return False
    conn.execute(text(
        "update executions set escalation_count=escalation_count+1, updated_at=now() "
        "where org_id=:o and execution_id=:x"), {"o": org_id, "x": execution_id})
    log_event(conn, org_id=org_id, execution_id=execution_id, kind="execution.escalated",
              reason_code=reason_code,
              detail={"day_offset": day_offset, "target_seat": target_seat}, occurred_at=at)
    return True


def complete_action(conn, *, org_id: str, execution_id: str, action_id: str, at: datetime,
                    actor: str) -> bool:
    """Tick one step.  Guarded on ``completed_at is null`` so a double submit is a no-op."""
    result = conn.execute(text(
        "update execution_actions set completed_at=:at, completed_by=:by "
        "where org_id=:o and execution_id=:x and action_id=:a and completed_at is null"),
        {"at": at, "by": actor, "o": org_id, "x": execution_id, "a": action_id})
    if result.rowcount != 1:
        return False
    conn.execute(text(
        "update executions set first_touch_at=coalesce(first_touch_at, :at), updated_at=now() "
        "where org_id=:o and execution_id=:x"), {"at": at, "o": org_id, "x": execution_id})
    log_event(conn, org_id=org_id, execution_id=execution_id, kind="execution.action_completed",
              reason_code="action_completed", actor=actor, detail={"action_id": action_id},
              occurred_at=at)
    return True


def action_completions(conn, org_id: str, execution_id: str) -> dict[str, datetime]:
    rows = conn.execute(text(
        "select action_id, completed_at from execution_actions "
        "where org_id=:o and execution_id=:x and completed_at is not null"),
        {"o": org_id, "x": execution_id}).fetchall()
    return {item.action_id: item.completed_at for item in rows}


def reassign(conn, *, org_id: str, execution_id: str, assignee: str | None, audience: str,
             routing_rule: str, at: datetime, actor: str = "system") -> None:
    """Point a live commitment at somebody else.

    Routing is deliberately not part of ``execution_id``, which is exactly what makes this a
    plain update rather than a new commitment: handing work to a colleague must not restart the
    escalation ladder or duplicate the row the outcome will be recorded against.
    """
    conn.execute(text(
        "update executions set assignee=:a, audience=:au, routing_rule=:r, updated_at=now() "
        "where org_id=:o and execution_id=:x and closed_at is null"),
        {"a": assignee, "au": audience, "r": routing_rule, "o": org_id, "x": execution_id})
    log_event(conn, org_id=org_id, execution_id=execution_id, kind="execution.reassigned",
              reason_code=routing_rule, actor=actor,
              detail={"assignee": assignee, "audience": audience}, occurred_at=at)


def supersede(conn, *, org_id: str, execution_id: str, by_execution_id: str,
              at: datetime) -> bool:
    """Close a commitment because a newer plan replaces it.

    A changed plan is a changed commitment, so it gets its own row and its own identity rather
    than mutating the old one in place. Closing the predecessor frees the partial unique key,
    which is how the replacement lands without a race.
    """
    result = conn.execute(text(
        "update executions set state='cancelled', closed_at=:at, close_reason='replanned', "
        "superseded_by=:by, next_check_at=null, updated_at=now() "
        "where org_id=:o and execution_id=:x and closed_at is null"),
        {"at": at, "by": by_execution_id, "o": org_id, "x": execution_id})
    if result.rowcount != 1:
        return False
    log_event(conn, org_id=org_id, execution_id=execution_id, kind="execution.cancelled",
              reason_code="replanned", to_state="cancelled",
              detail={"superseded_by": by_execution_id}, occurred_at=at)
    return True


def record_outcome(conn, outcome: ExecutionOutcome) -> bool:
    """Write the L7 feed row.  Once per commitment — a second would double-count it in every
    precision calculation the calibrator runs."""
    result = conn.execute(text(
        "insert into execution_outcomes (outcome_id, org_id, execution_id, decision_hash, "
        "capability_id, capability_version, play_id, play_version, terminal_state, reason_code, "
        "label, created_at, closed_at, seconds_to_close, actions_total, actions_completed, "
        "progress_bp, reminders_sent, escalations_fired, priority_bp, confidence_bp, band, "
        "routing_rule, outcome_kind, outcome_observed_at, assignee, subject_ref, payload) "
        "values (:id, :o, :x, :dh, :cap, :capv, :p, :pv, :ts, :rc, :lb, :cat, :clo, :sec, :at_, "
        ":ac, :pb, :rs, :ef, :pri, :conf, :band, :rule, :ok, :oat, :asg, :sref, cast(:pl as jsonb)) "
        "on conflict (org_id, execution_id) do nothing"),
        {"id": new_id("exout"), "o": outcome.org_id, "x": outcome.execution_id,
         "dh": outcome.decision_hash, "cap": outcome.capability_id,
         "capv": outcome.capability_version, "p": outcome.play_id, "pv": outcome.play_version,
         "ts": outcome.terminal_state.value, "rc": outcome.reason_code, "lb": outcome.label,
         "cat": outcome.created_at, "clo": outcome.closed_at, "sec": outcome.seconds_to_close,
         "at_": outcome.actions_total, "ac": outcome.actions_completed,
         "pb": outcome.progress_bp, "rs": outcome.reminders_sent,
         "ef": outcome.escalations_fired, "pri": outcome.priority_bp,
         "conf": outcome.confidence_bp, "band": outcome.band, "rule": outcome.routing_rule,
         "ok": outcome.outcome_kind, "oat": outcome.outcome_observed_at,
         "asg": outcome.assignee, "sref": outcome.subject_ref,
         "pl": canonical_dumps(outcome.to_semantic_dict())})
    return result.rowcount == 1


def active_channels(conn, org_id: str) -> frozenset[str]:
    """Which transports this org has actually registered.

    The card surface is always in the set: it needs no registration and it is the floor every
    other channel choice falls back to. Without it a tenant with no integrations would have its
    commitments planned as undeliverable rather than simply quiet.
    """
    rows = conn.execute(text(
        "select channel from org_channels where org_id=:o and active"), {"o": org_id}).fetchall()
    return frozenset({"in_app", *(item.channel for item in rows)})


__all__ = ["STORE_VERSION", "action_completions", "active_channels", "apply_transition",
           "authority_valid", "complete_action", "due_executions", "fire_escalation",
           "link_card", "load", "log_event", "persist", "reassign", "record_outcome",
           "record_reminder", "reminder_state", "supersede", "validation_input"]
