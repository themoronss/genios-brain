"""/v1/executive/* — the Layer 5 surface.

Two halves, and the split is the layer's own.

DECISION INTELLIGENCE (read-only, deterministic, no LLM on any path): briefs, the summary
ladder, memory, preventive warnings, why-not receipts. These say WHAT / WHY / HOW URGENT / ON
WHAT EVIDENCE / WHAT IF NOTHING.

COMMITMENTS (the executive engine): what happens after a recommendation is made — who owns it,
by when, through which channel, what has been done, what escalates on which day, and how it
ended. Layer 5 owns who and where; Layer 6 executes the transport. See docs/LAYER_MAP.md.

Every mutation here is a *human* act being recorded (a step ticked, a recommendation dismissed,
an owner changed). None of them decide anything — the sweep does that, and it re-validates
against live state before every message it sends."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Body, Depends, HTTPException
from sqlalchemy import text

from genios_engine.platform.auth import AuthCtx, get_current_org, require_owner
from genios_engine.platform.wiring import make_graph_store, make_pack_registry

router = APIRouter(prefix="/v1/executive", tags=["executive"])
_graph = make_graph_store()
_registry = make_pack_registry()


def _require_db():
    if _graph is None:
        raise HTTPException(400, "graph store not configured (needs DATABASE_URL)")


def _now() -> datetime:
    return datetime.now(timezone.utc)


@router.get("/briefs")
def briefs(limit: int = 20, org_id: str = Depends(get_current_org)) -> dict:
    """Open signals as ranked Decision Briefs — the executive queue."""
    _require_db()
    from genios_engine.executive.brief import load_briefs
    return {"briefs": load_briefs(_graph, org_id, registry=_registry, limit=limit)}


@router.get("/summary")
def summary(horizon: str = "one_line", org_id: str = Depends(get_current_org)) -> dict:
    """The summary ladder: one_line | one_minute | five_minute. Counted, never estimated."""
    _require_db()
    if horizon not in ("one_line", "one_minute", "five_minute"):
        raise HTTPException(422, "horizon must be one_line | one_minute | five_minute")
    from genios_engine.executive.summary import build_summary
    return build_summary(_graph, org_id, horizon)


@router.get("/memory")
def memory(limit: int = 10, org_id: str = Depends(get_current_org)) -> dict:
    """Executive working context: recent decisions, open decisions, overdue items,
    where attention sits. So the next decision isn't amnesiac."""
    _require_db()
    from genios_engine.executive.memory import load_memory
    return load_memory(_graph, org_id, limit=limit)


@router.get("/preventive")
def preventive(limit: int = 25, org_id: str = Depends(get_current_org)) -> dict:
    """The fourth mode: rules about to trip, with exact time remaining — act BEFORE
    the miss. Pure arithmetic over the same rules/facts the reasoner uses."""
    _require_db()
    from genios_engine.executive.modes import load_preventive
    return {"preventive": load_preventive(_graph, org_id, registry=_registry, limit=limit)}


@router.get("/why-not")
def why_not_route(entity_id: str | None = None, rule_id: str | None = None,
                  days: int = 7, org_id: str = Depends(get_current_org)) -> dict:
    """'Why didn't you tell me about X?' — the stored suppression receipts, answered
    from signal_suppression_log (written since day one, read for the first time)."""
    _require_db()
    from genios_engine.executive.explain import why_not
    return why_not(_graph, org_id, entity_id=entity_id, rule_id=rule_id, days=days)


# ---------------------------------------------------------------------------------------
# Commitments — the executive engine's surface.

_COMMITMENT_FIELDS = (
    "execution_id, state, goal, subject_ref, subject_type, play_id, assignee, audience, "
    "channel_id, interrupt, routing_rule, band, priority_bp, confidence_bp, created_at, "
    "deadline_at, expires_at, next_check_at, delivered_at, first_touch_at, closed_at, "
    "close_reason, reminder_count, escalation_count, card_id")


@router.get("/commitments")
def commitments(state: str | None = None, assignee: str | None = None, limit: int = 50,
                include_closed: bool = False, org_id: str = Depends(get_current_org)) -> dict:
    """The commitment queue: what this org is actually on the hook for.

    Ordered by deadline rather than by score. A ranked queue answers "what is most important";
    this one answers "what is about to be missed", which is the question the executive engine
    exists to keep asking.
    """
    _require_db()
    clauses = ["org_id=:o"]
    params: dict = {"o": org_id, "l": max(1, min(int(limit), 200))}
    if not include_closed:
        clauses.append("closed_at is null")
    if state:
        clauses.append("state=:s")
        params["s"] = state
    if assignee:
        clauses.append("assignee=:a")
        params["a"] = assignee
    with _graph.engine.connect() as c:
        rows = c.execute(text(
            f"select {_COMMITMENT_FIELDS} from executions where " + " and ".join(clauses) +
            " order by closed_at is not null, deadline_at asc, priority_bp desc limit :l"),
            params).mappings().all()
    return {"commitments": [dict(row) for row in rows], "count": len(rows)}


@router.get("/commitments/{execution_id}")
def commitment(execution_id: str, org_id: str = Depends(get_current_org)) -> dict:
    """One commitment in full: the plan, the ladder, the audit trail.

    The event list is returned alongside rather than behind another call, because the questions
    people bring to this endpoint — "why did this escalate?", "who moved it?" — are answered by
    the events, and an endpoint that makes you fetch twice gets read once.
    """
    _require_db()
    with _graph.engine.connect() as c:
        row = c.execute(text(
            f"select {_COMMITMENT_FIELDS}, plan_hash, decision_hash, capability_id, payload "
            "from executions where org_id=:o and execution_id=:x"),
            {"o": org_id, "x": execution_id}).mappings().first()
        if row is None:
            raise HTTPException(404, "commitment not found")
        actions = c.execute(text(
            "select action_id, ordinal, stage, kind, label, requires_approval, read_only, "
            "deadline_at, completed_at, completed_by from execution_actions "
            "where org_id=:o and execution_id=:x order by ordinal"),
            {"o": org_id, "x": execution_id}).mappings().all()
        ladder = c.execute(text(
            "select day_offset, action, audience, interrupt, fires_at, fired_at, target_seat, "
            "reason_code from execution_escalations where org_id=:o and execution_id=:x "
            "order by day_offset"), {"o": org_id, "x": execution_id}).mappings().all()
        events = c.execute(text(
            "select kind, reason_code, actor, from_state, to_state, detail, occurred_at "
            "from execution_events where org_id=:o and execution_id=:x "
            "order by occurred_at desc limit 100"),
            {"o": org_id, "x": execution_id}).mappings().all()
    return {"commitment": dict(row), "actions": [dict(a) for a in actions],
            "escalation": [dict(e) for e in ladder], "events": [dict(e) for e in events]}


@router.post("/commitments/{execution_id}/actions/{action_id}/complete")
def complete_action(execution_id: str, action_id: str,
                    ctx: AuthCtx = Depends(require_owner)) -> dict:
    """Record that a step was done.

    Idempotent: a double submit updates nothing and returns ``recorded: false``. The state
    machine is deliberately not advanced here — the sweep does that, after re-validating, so a
    step ticked on a commitment the world has already killed does not resurrect it.
    """
    _require_db()
    from genios_engine.executive import execution_store as store
    from genios_engine.executive.coordination import dependencies_met
    with _graph.engine.begin() as c:
        loaded = store.load(c, org_id=ctx.org_id, execution_id=execution_id)
        if loaded is None:
            raise HTTPException(404, "no open commitment with that id")
        execution, _ = loaded
        # Unit 2.5 — dependency-gated completion. A step whose prerequisites have not happened
        # cannot be ticked: doing so records a history that never occurred (the plan said
        # "draft, then send"; ticking "send" first claims an approval that was skipped). Only
        # gate a KNOWN action with UNMET deps — an already-completed or unknown id falls through
        # to the store, which is idempotent and returns recorded=false rather than a 409.
        known = {a.action_id for a in execution.actions}
        if action_id in known and not dependencies_met(
                action_id, execution.actions, store.action_completions(c, ctx.org_id, execution_id)):
            raise HTTPException(409, "action blocked: complete its prerequisite step(s) first")
        done = store.complete_action(c, org_id=ctx.org_id, execution_id=execution_id,
                                     action_id=action_id, at=_now(),
                                     actor=ctx.actor_id or "human")
    return {"recorded": done, "execution_id": execution_id, "action_id": action_id}


@router.post("/commitments/{execution_id}/dismiss")
def dismiss(execution_id: str, reason: str = Body("not_relevant", embed=True),
            ctx: AuthCtx = Depends(require_owner)) -> dict:
    """A human says this should not happen.

    Written as an event, not as a direct state change. The guard reads it on the next pass and
    cancels with ``human_dismissed``, which keeps every termination flowing through one place —
    and means the dismissal is captured for Layer 7 even if the cancel races with a completion.
    """
    _require_db()
    from genios_engine.executive import execution_store as store
    at = _now()
    with _graph.engine.begin() as c:
        exists = c.execute(text(
            "select 1 from executions where org_id=:o and execution_id=:x and closed_at is null"),
            {"o": ctx.org_id, "x": execution_id}).first()
        if exists is None:
            raise HTTPException(404, "no open commitment with that id")
        store.log_event(c, org_id=ctx.org_id, execution_id=execution_id,
                        kind="execution.cancelled", reason_code="human_dismissed",
                        actor=ctx.actor_id or "human", detail={"reason": str(reason)[:200]},
                        occurred_at=at)
        # Bound explicitly rather than written as SQL now(): every other time in this codebase
        # is passed in, so a replay or a test observes the same instant the event recorded.
        c.execute(text("update executions set next_check_at=:n, updated_at=now() "
                       "where org_id=:o and execution_id=:x"),
                  {"n": at, "o": ctx.org_id, "x": execution_id})
    return {"dismissed": True, "execution_id": execution_id}


@router.post("/commitments/{execution_id}/reassign")
def reassign(execution_id: str, seat_id: str = Body(..., embed=True),
             ctx: AuthCtx = Depends(require_owner)) -> dict:
    """Hand a commitment to somebody else.

    An update, never a new row. Routing is excluded from the commitment's content address for
    exactly this reason: reassignment must not restart the escalation ladder or split the
    outcome record in two.
    """
    _require_db()
    from genios_engine.executive import execution_store as store
    from genios_engine.executive.assignment import PgSeatDirectory
    with _graph.engine.begin() as c:
        seat = PgSeatDirectory(conn=c, org_id=ctx.org_id).active_seat(seat_id)
        if seat is None:
            raise HTTPException(422, f"{seat_id} is not an active seat in this org")
        open_row = c.execute(text(
            "select 1 from executions where org_id=:o and execution_id=:x and closed_at is null"),
            {"o": ctx.org_id, "x": execution_id}).first()
        if open_row is None:
            raise HTTPException(404, "no open commitment with that id")
        store.reassign(c, org_id=ctx.org_id, execution_id=execution_id, assignee=seat,
                       audience="owner", routing_rule="manual_reassign", at=_now(),
                       actor=ctx.actor_id or "human")
    return {"reassigned": True, "execution_id": execution_id, "assignee": seat}


@router.post("/sweep")
def sweep(ctx: AuthCtx = Depends(require_owner)) -> dict:
    """Run both executive passes for this org now.

    Exists because a scheduler is an operational detail and a demo is not. Safe to call
    repeatedly: planning is idempotent on ``(org, decision_hash)`` and every lifecycle write is
    guarded on the state it expects to find.
    """
    _require_db()
    import dataclasses

    from genios_engine.executive.sweep import run_executive
    effective, _ = (_registry.effective(ctx.org_id) if _registry else (None, None))
    result = run_executive(_graph.engine, ctx.org_id, effective=effective)
    # `asdict`, not `vars`: SweepReport is a frozen slotted dataclass and has no __dict__.
    return {name: dataclasses.asdict(report) for name, report in result.items()}
