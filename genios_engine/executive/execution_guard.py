"""Layer 5 · Unit — the Execution Validation Unit.  Is this still worth doing *right now*?

This is the unit the architecture note asked for, and it is the difference between a system
people keep and a system people mute.

The classic failure of any reminder engine is that it reminds you about something that already
happened.  The plan was correct when it was made; the world moved; nobody told the scheduler.
You get nudged to chase a customer who replied yesterday, and from that moment on every future
nudge is presumed wrong until proven otherwise.  Trust is lost far faster than it is earned.

So nothing here trusts the plan.  **Every** outbound moment — first delivery, each reminder,
each escalation rung — is validated against live state immediately before it happens, and the
verdict is recorded.  Validation is cheap; a wrong nudge is not.

The unit is pure.  It takes a snapshot of the facts it needs (``ValidationInput``) and returns a
verdict.  Gathering those facts is SQL and lives in ``executive.execution_store``; keeping the
judgement separate is what makes every one of these branches testable without a database, and
what lets the same logic answer "why was this suppressed?" months later from stored inputs.

Checks are ordered by authority, not by cost.  A revoked decision outranks a satisfied outcome,
which outranks a closed subject, which outranks a stale owner — because when several things are
wrong at once, the operator needs to be told the *most fundamental* one.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from genios_engine.contracts.execution import (
    OPEN_STATES,
    TERMINAL_STATES,
    ExecutionObject,
    ExecutionState,
)

GUARD_VERSION = "guard.v1"

#: Subject states that make a commitment pointless regardless of anything else. Chasing a
#: closed-lost deal is not diligence, it is the system failing to read the room.
DEAD_SUBJECT_STATUSES: frozenset[str] = frozenset({
    "closed", "closed_won", "closed_lost", "won", "lost", "cancelled", "canceled",
    "archived", "deleted", "churned"})


class GuardAction(str, Enum):
    """What to do about this commitment right now.

    Deliberately more than a boolean.  "Do not send" covers four genuinely different situations —
    the work is done, the deal is dead, the clock ran out, the owner left — and collapsing them
    into one flag would make the difference invisible in exactly the reports where it matters.
    """

    PROCEED = "proceed"      # deliver, remind or escalate as planned
    SUPPRESS = "suppress"    # not now — the commitment stays open, this moment is skipped
    REROUTE = "reroute"      # valid work, wrong person; re-resolve the owner and continue
    COMPLETE = "complete"    # the world already did it
    CANCEL = "cancel"        # it should never happen now
    EXPIRE = "expire"        # the window closed with nothing observed


#: Which verdicts end the commitment.  Used by the lifecycle sweep so the mapping from verdict
#: to terminal state exists once rather than being re-derived at each call site.
_TERMINAL_ACTIONS: Mapping[GuardAction, ExecutionState] = {
    GuardAction.COMPLETE: ExecutionState.COMPLETED,
    GuardAction.CANCEL: ExecutionState.CANCELLED,
    GuardAction.EXPIRE: ExecutionState.EXPIRED,
}


@dataclass(frozen=True, slots=True)
class ValidationInput:
    """Everything the guard is allowed to look at, gathered once.

    An explicit input record rather than a live handle, for two reasons.  It makes every branch
    reachable in a test without Postgres, and it makes a suppression decision *reproducible* —
    store this record next to the verdict and the same judgement can be re-derived years later,
    even after the deal, the seat and the pack have all changed.
    """

    now: datetime
    state: ExecutionState
    #: Result of the Layer 4 authority predicate. False means the decision behind this
    #: commitment no longer proves out — a revoked pack, a superseded run, a broken chain.
    authority_valid: bool = True
    #: Success events observed since the commitment was created, as ``{kind: observed_at}``.
    observed_events: Mapping[str, datetime] = field(default_factory=dict)
    #: Current status of the subject entity, lower-cased, or None when unknown.
    subject_status: str | None = None
    #: Whether the recorded assignee is still an active seat.
    owner_active: bool = True
    #: A newer execution for the same subject and play, if one exists.
    superseded_by: str | None = None
    #: Explicit human dismissal — a "wrong" or "not now" action recorded against this work.
    dismissed: bool = False
    #: The subject entity vanished from the graph (merged, deleted, tenant offboarded).
    subject_missing: bool = False


@dataclass(frozen=True, slots=True)
class GuardVerdict:
    action: GuardAction
    reason_code: str
    detail: str

    @property
    def proceed(self) -> bool:
        return self.action is GuardAction.PROCEED

    @property
    def terminal_state(self) -> ExecutionState | None:
        """The state this verdict moves the commitment to, if it ends it."""
        return _TERMINAL_ACTIONS.get(self.action)


def validate(execution: ExecutionObject, state: ValidationInput) -> GuardVerdict:
    """The whole unit.  One commitment, one moment, one verdict.

    Read top to bottom: each branch is a reason the planned moment should not simply happen, in
    descending order of authority.  The default at the bottom is the only path that proceeds,
    which is the correct shape for a guard — everything must be *proven* fine, not assumed fine.
    """
    # 0. Already finished. Not an error: sweeps race with human action, and the human wins.
    if state.state in TERMINAL_STATES:
        return GuardVerdict(GuardAction.SUPPRESS, "already_terminal",
                            f"commitment is {state.state.value}")

    # 1. Authority. Layer 4's decision is the only thing that makes this commitment legitimate;
    #    if the chain no longer proves out, nothing downstream is allowed to fire — this is the
    #    same check the outbox runs before every send, applied to reminders and escalations too.
    if not state.authority_valid:
        return GuardVerdict(GuardAction.CANCEL, "authority_revoked",
                            "the reasoning decision behind this commitment is no longer "
                            "authoritative")

    # 2. Expiry. A decision past its own window cannot authorise a nudge.
    if state.now >= execution.expires_at:
        return GuardVerdict(GuardAction.EXPIRE, "decision_expired",
                            f"decision expired at {execution.expires_at.isoformat()}")

    # 3. The world already did it. Checked before the subject and the owner because a completed
    #    outcome is good news, and reporting it as "cancelled — deal closed" would lose the one
    #    data point Layer 7 needs to learn whether the play works.
    satisfied = _satisfied_by(execution, state)
    if satisfied is not None:
        kind, observed_at = satisfied
        return GuardVerdict(GuardAction.COMPLETE, "outcome_observed",
                            f"{kind} observed at {observed_at.isoformat()}")

    # 4. A human said no. Their judgement is not something a sweep gets to overrule.
    if state.dismissed:
        return GuardVerdict(GuardAction.CANCEL, "human_dismissed",
                            "a human dismissed this recommendation")

    # 5. The subject is gone or done.
    if state.subject_missing:
        return GuardVerdict(GuardAction.CANCEL, "subject_missing",
                            "the subject entity no longer exists in the graph")
    if state.subject_status and state.subject_status.strip().lower() in DEAD_SUBJECT_STATUSES:
        return GuardVerdict(GuardAction.CANCEL, "subject_closed",
                            f"subject is {state.subject_status}")

    # 6. Something newer says the same thing better. The old one steps aside rather than both
    #    of them nagging about the same account with slightly different words.
    if state.superseded_by:
        return GuardVerdict(GuardAction.CANCEL, "superseded",
                            f"superseded by {state.superseded_by}")

    # 7. The work is fine; the owner is not. Rerouting rather than cancelling is the whole point:
    #    when a rep leaves, their commitments are exactly what must not disappear with them.
    if execution.communication.routable and not state.owner_active:
        return GuardVerdict(GuardAction.REROUTE, "owner_inactive",
                            f"recipient {execution.communication.recipient} is no longer active")

    # 8. The deadline passed with nothing observed. Expired, not cancelled — the distinction is
    #    what lets Layer 7 tell "we chose not to" apart from "we ran out of time", and only the
    #    second one is evidence the window was too short.
    if state.now >= execution.deadline_at:
        return GuardVerdict(GuardAction.EXPIRE, "deadline_passed",
                            f"deadline was {execution.deadline_at.isoformat()}")

    # 9. Blocked commitments hold their position: they still escalate (that is how a block gets
    #    unblocked) but they are not nudged as though the owner were simply slow.
    if state.state is ExecutionState.BLOCKED:
        return GuardVerdict(GuardAction.SUPPRESS, "blocked",
                            "commitment is blocked; escalation applies, reminders do not")

    return GuardVerdict(GuardAction.PROCEED, "valid", "commitment is still live and unmet")


def _satisfied_by(execution: ExecutionObject,
                  state: ValidationInput) -> tuple[str, datetime] | None:
    """The earliest declared success event observed after the commitment was made.

    "After" is load-bearing.  The event that *caused* the recommendation is often the same kind
    as the event that would prove it resolved — an inbound reply both signals a stalled deal and
    proves the follow-up landed.  Counting a pre-existing observation would mark every
    commitment complete the instant it was created, which is the most convincing possible way to
    look like it is working while doing nothing.
    """
    wanted = set(execution.monitoring_events)
    if not wanted:
        return None
    hits = [(kind, seen) for kind, seen in (state.observed_events or {}).items()
            if kind in wanted and seen > execution.created_at]
    if not hits:
        return None
    return min(hits, key=lambda item: (item[1], item[0]))


def validate_for_delivery(execution: ExecutionObject, state: ValidationInput) -> GuardVerdict:
    """Validation at the first delivery, where one extra rule applies.

    A commitment that has not reached a person yet has no history to preserve, so a stale owner
    is a build-time mistake rather than an operational event: it is suppressed and re-planned,
    not rerouted-with-an-audit-trail. Everything else is the standard verdict.
    """
    verdict = validate(execution, state)
    if verdict.action is GuardAction.REROUTE and state.state is ExecutionState.CREATED:
        return GuardVerdict(GuardAction.SUPPRESS, "owner_inactive_at_build",
                            "resolved owner went inactive before first delivery; re-plan")
    return verdict


def is_live(state: ExecutionState) -> bool:
    return state in OPEN_STATES


__all__ = ["DEAD_SUBJECT_STATUSES", "GUARD_VERSION", "GuardAction", "GuardVerdict",
           "ValidationInput", "is_live", "validate", "validate_for_delivery"]
