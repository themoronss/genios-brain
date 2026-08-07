"""Layer 5 · Unit 8 — the Execution Tracking Unit.  The state machine and its vocabulary.

A commitment's state is the only thing in this layer that legitimately changes.  Everything else
— the decision, the plan, the ladder — is immutable and content-addressed; the row that points
at them moves through ``created → pending → running → …`` and that movement *is* the history.

Two rules make that history worth trusting.

**Every move is proved legal against one table.**  ``ALLOWED_TRANSITIONS`` lives in the contract,
not here, so this module, the SQL guard and the tests all read the same definition.  A
transition that is legal in Python and illegal in Postgres is how audit trails start
disagreeing with themselves, and the only defence is to have exactly one copy.

**Every move carries a cause.**  Not a timestamp and a new value — a cause code, an actor and a
detail.  "cancelled" answers nothing; "cancelled · authority_revoked · the pack was rolled back"
answers everything, and it is the difference between an incident that takes an afternoon and one
that takes ten minutes.

Terminal states are terminal.  ``COMPLETED``, ``CANCELLED`` and ``EXPIRED`` go only to
``ARCHIVED``; there is
no reopening.  If the world changes again, that is a *new* decision producing a *new*
commitment, which is both honest and necessary — reopening would silently rewrite the outcome
Layer 7 already learned from.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from genios_engine.contracts.execution import (
    ALLOWED_TRANSITIONS,
    OPEN_STATES,
    TERMINAL_STATES,
    ExecutionState,
    can_transition,
)
from genios_engine.executive.execution_guard import GuardAction, GuardVerdict
from genios_engine.executive.monitor import ProgressReport

LIFECYCLE_VERSION = "lifecycle.v1"


class LifecycleError(RuntimeError):
    """An illegal state move was attempted.

    Raised rather than logged.  A caller that tries to complete an already-cancelled commitment
    has a bug in its ordering, and letting the write land would produce a row whose history no
    longer explains its own state.
    """


#: The audit vocabulary.  Fixed, because these strings are what dashboards group by and what
#: support reads at 2am; a free-text kind column becomes unqueryable within a month.
EVENT_CREATED = "execution.created"
EVENT_QUEUED = "execution.queued"
EVENT_DELIVERY_CONFIRMED = "execution.delivery_confirmed"
EVENT_STARTED = "execution.started"
EVENT_WAITING = "execution.waiting"
EVENT_BLOCKED = "execution.blocked"
EVENT_UNBLOCKED = "execution.unblocked"
EVENT_REMINDED = "execution.reminded"
EVENT_ESCALATED = "execution.escalated"
EVENT_REASSIGNED = "execution.reassigned"
EVENT_ACTION_COMPLETED = "execution.action_completed"
EVENT_SUPPRESSED = "execution.suppressed"
EVENT_REPLANNED = "execution.replanned"
EVENT_COMPLETED = "execution.completed"
EVENT_CANCELLED = "execution.cancelled"
EVENT_EXPIRED = "execution.expired"
EVENT_ARCHIVED = "execution.archived"

#: The event each state entry emits, so a transition never has to be paired with a hand-picked
#: event kind at the call site (which is where the two drift apart).
EVENT_FOR_STATE: dict[ExecutionState, str] = {
    ExecutionState.CREATED: EVENT_CREATED,
    ExecutionState.PENDING: EVENT_QUEUED,
    ExecutionState.RUNNING: EVENT_STARTED,
    ExecutionState.WAITING: EVENT_WAITING,
    ExecutionState.BLOCKED: EVENT_BLOCKED,
    ExecutionState.COMPLETED: EVENT_COMPLETED,
    ExecutionState.CANCELLED: EVENT_CANCELLED,
    ExecutionState.EXPIRED: EVENT_EXPIRED,
    ExecutionState.ARCHIVED: EVENT_ARCHIVED,
}


@dataclass(frozen=True, slots=True)
class Transition:
    """One legal move, with everything needed to explain it later."""

    from_state: ExecutionState
    to_state: ExecutionState
    event_kind: str
    reason_code: str
    actor: str
    at: datetime
    detail: str = ""

    @property
    def terminal(self) -> bool:
        return self.to_state in TERMINAL_STATES


def transition(current: ExecutionState, target: ExecutionState, *, reason_code: str,
               actor: str, at: datetime, detail: str = "") -> Transition:
    """Prove the move is legal, then describe it.

    A no-op move (``pending → pending``) is refused rather than silently allowed.  Sweeps run
    repeatedly over the same rows, and a tolerated no-op would fill the event log with
    indistinguishable rows that make the real transitions impossible to find.
    """
    if not can_transition(current, target):
        allowed = ", ".join(state.value for state in ALLOWED_TRANSITIONS.get(current, ()))
        raise LifecycleError(
            f"cannot move a commitment from {current.value} to {target.value}; "
            f"legal moves are: {allowed or 'none — this state is terminal'}")
    return Transition(from_state=current, to_state=target,
                      event_kind=EVENT_FOR_STATE[target], reason_code=reason_code,
                      actor=actor, at=at, detail=detail)


def next_state(current: ExecutionState, verdict: GuardVerdict,
               report: ProgressReport | None = None) -> ExecutionState | None:
    """Where the sweep should move this commitment, or None to leave it alone.

    The guard's verdict leads, because it is the unit with the authority to end things.  Only
    when the verdict is ``PROCEED`` does progress get a say, and then only to promote a
    commitment somebody has demonstrably started — a sweep may recognise work in flight, it may
    never decide on someone's behalf that they have finished.
    """
    terminal = verdict.terminal_state
    if terminal is not None:
        return terminal if can_transition(current, terminal) else None

    if verdict.action is not GuardAction.PROCEED or report is None:
        return None

    if current is ExecutionState.PENDING and report.progress_bp > 0:
        return ExecutionState.RUNNING
    if current is ExecutionState.RUNNING and report.done_but_unproven:
        # Every step ticked, no evidence yet. WAITING says exactly that, and it is what stops
        # the reminder unit nagging someone who has already done their part.
        return ExecutionState.WAITING
    return None


def is_open(state: ExecutionState) -> bool:
    return state in OPEN_STATES


def is_terminal(state: ExecutionState) -> bool:
    return state in TERMINAL_STATES


__all__ = ["EVENT_ACTION_COMPLETED", "EVENT_ARCHIVED", "EVENT_BLOCKED", "EVENT_CANCELLED",
           "EVENT_COMPLETED", "EVENT_CREATED", "EVENT_DELIVERY_CONFIRMED", "EVENT_ESCALATED",
           "EVENT_EXPIRED", "EVENT_FOR_STATE", "EVENT_REASSIGNED", "EVENT_REMINDED",
           "EVENT_QUEUED", "EVENT_REPLANNED", "EVENT_STARTED", "EVENT_SUPPRESSED", "EVENT_UNBLOCKED",
           "EVENT_WAITING", "LIFECYCLE_VERSION", "LifecycleError", "Transition", "is_open",
           "is_terminal", "next_state", "transition"]
