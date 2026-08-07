"""Layer 5 · Unit 6 — the Monitoring Unit.  Did any of this actually happen?

The guard answers a binary question at a single moment: may this fire *now*.  Monitoring answers
a continuous one: how far has this commitment actually got, and has it stopped moving.  Both are
needed, and conflating them produces a system that only ever knows "done" or "not done" — which
is exactly the resolution at which a stalled commitment is indistinguishable from a fresh one.

Progress comes from two independent sources and they are deliberately not merged into a single
number without saying which is which:

* **Action completions** — a person or agent marked a step done.  Self-reported, immediate,
  and the only signal available for internal work with no external trace.
* **Observed events** — the world produced the evidence the play declared as success.  Slower,
  but not self-reported, which makes it the one that counts for Layer 7's learning.

When the world confirms the outcome, the commitment is complete regardless of how many steps
anyone ticked off.  When the steps are all ticked and the world is silent, the commitment is
*done but unproven* — a real and important state, because it is where a play that feels
productive and achieves nothing hides.

Pure: observations in, report out.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from genios_engine.contracts.execution import ExecutionObject, PlannedAction

MONITOR_VERSION = "monitor.v1"

DEFAULTS: Mapping[str, Any] = {
    # A commitment is stalled when it has not moved for this share of its own window, in basis
    # points. Proportional rather than absolute so a two-day commitment is called stalled after
    # a day and a fortnight-long one is not called stalled after a quiet weekend.
    "stall_bp": 3_000,
    # Never call something stalled before this much wall-clock has passed, whatever the window
    # says. Protects short-window commitments from being reported stalled the same afternoon.
    "stall_floor_hours": 12,
}


@dataclass(frozen=True, slots=True)
class ProgressReport:
    """Where a commitment stands, with the evidence separated by how much it can be trusted."""

    completed_action_ids: tuple[str, ...]
    current_stage: int
    progress_bp: int
    stalled: bool
    last_progress_at: datetime | None
    outcome_kind: str | None
    outcome_observed_at: datetime | None
    detail: str

    @property
    def outcome_observed(self) -> bool:
        """The world produced the declared evidence.  The only proof that counts for learning."""
        return self.outcome_kind is not None

    @property
    def steps_complete(self) -> bool:
        return self.progress_bp >= 10_000

    @property
    def done_but_unproven(self) -> bool:
        """Every step ticked, nothing observed.

        Worth naming.  A play that reliably reaches this state is a play whose steps people are
        happy to do and whose outcome never arrives, and no amount of completion rate will
        surface that — only the gap between the two will.
        """
        return self.steps_complete and not self.outcome_observed


def _next_action(execution: ExecutionObject,
                 completed: set[str]) -> PlannedAction | None:
    return next((action for action in execution.actions if action.action_id not in completed),
                None)


def observe(execution: ExecutionObject, *, now: datetime,
            action_completions: Mapping[str, datetime] | None = None,
            observed_events: Mapping[str, datetime] | None = None,
            cfg: Mapping[str, Any] | None = None) -> ProgressReport:
    """Build the progress report for one commitment.

    Both event sources are filtered to what happened *after* the commitment was created. The
    event that triggered a recommendation is frequently the same kind as the event that would
    prove it resolved — an inbound reply both signals a stalled deal and proves the follow-up
    worked — so counting history would mark every commitment complete on the day it was made.
    """
    settings = {**DEFAULTS, **dict(cfg or {})}
    completions = {action_id: seen for action_id, seen in (action_completions or {}).items()
                   if seen >= execution.created_at}
    known = {action.action_id for action in execution.actions}
    completed = {action_id for action_id in completions if action_id in known}

    wanted = set(execution.monitoring_events)
    hits = sorted(((seen, kind) for kind, seen in (observed_events or {}).items()
                   if kind in wanted and seen > execution.created_at))
    outcome_at, outcome_kind = hits[0] if hits else (None, None)

    if outcome_kind is not None:
        # The world confirmed it. Everything the plan asked for is, by definition, no longer
        # outstanding — reporting 40% progress on a commitment that demonstrably worked would
        # be technically defensible and completely useless.
        return ProgressReport(
            completed_action_ids=tuple(action.action_id for action in execution.actions),
            current_stage=execution.stage_count, progress_bp=10_000, stalled=False,
            last_progress_at=outcome_at, outcome_kind=outcome_kind,
            outcome_observed_at=outcome_at,
            detail=f"{outcome_kind} observed at {outcome_at.isoformat()}")

    total = len(execution.actions)
    progress_bp = (len(completed) * 10_000) // total if total else 0
    pending = _next_action(execution, completed)
    current_stage = pending.stage if pending is not None else execution.stage_count
    last_progress = max(completions.values()) if completions else None

    since = last_progress or execution.created_at
    window = int((execution.deadline_at - execution.created_at).total_seconds())
    threshold = max(int(settings["stall_floor_hours"]) * 3_600,
                    (window * int(settings["stall_bp"])) // 10_000)
    stalled = (pending is not None) and (now - since) >= timedelta(seconds=threshold)

    if pending is None:
        detail = "all steps complete; awaiting outcome evidence"
    elif stalled:
        detail = f"no progress since {since.isoformat()}; next step is {pending.action_id}"
    else:
        detail = f"{len(completed)}/{total} steps complete; next is {pending.action_id}"

    return ProgressReport(
        completed_action_ids=tuple(sorted(completed)), current_stage=current_stage,
        progress_bp=progress_bp, stalled=stalled, last_progress_at=last_progress,
        outcome_kind=None, outcome_observed_at=None, detail=detail)


def blocking_action(execution: ExecutionObject,
                    report: ProgressReport) -> PlannedAction | None:
    """The single step everything else is waiting on.

    What a stalled-commitment escalation should actually name.  "Your Acme follow-up is stuck on
    getting it approved" is a message somebody can act on; "your Acme follow-up is stalled" is a
    message somebody can only feel bad about.
    """
    return _next_action(execution, set(report.completed_action_ids))


__all__ = ["DEFAULTS", "MONITOR_VERSION", "ProgressReport", "blocking_action", "observe"]
