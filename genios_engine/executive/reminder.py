"""Layer 5 · Unit 5 — the Reminder Unit.

The architecture marks this the highest-value unit in the layer, and it is right, because it is
also the easiest one to get wrong in a way that destroys the product.  A reminder engine that
fires on a timer is a nag.  A reminder engine that fires when the *business situation* still
holds and has got worse is a colleague.  The difference is entirely in what triggers it.

So nothing here counts days for its own sake.  Every trigger is a statement about the
commitment's standing in the world:

* an escalation rung the plan itself promised has come due,
* the outcome window is running out with nothing observed,
* or nobody has so much as looked at it since it landed.

And every reminder must first survive the Execution Validation Unit, so a commitment the world
has already satisfied is never nudged — that single guarantee is what buys the right to nudge
at all.

**Elapsed fraction, not fixed hours.**  The deadline warning triggers at a proportion of the
window rather than at "48 hours before".  A two-day commitment and a fourteen-day commitment are
not both urgent two days out; treating them alike is how a system ends up shouting about routine
work and whispering about the fire.

**Fatigue is a hard stop, not a taper.**  After the configured number of reminders the unit
stops asking and lets escalation take over.  A fifth identical nudge does not produce action; it
produces a filter rule, and after that GeniOS is talking to nobody.

Pure: history and clock are inputs.  The SQL that loads them lives in ``execution_store``.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from genios_engine.contracts.execution import ExecutionObject, ExecutionState
from genios_engine.executive.escalation import due_rungs, next_rung

REMINDER_VERSION = "remind.v1"

DEFAULTS: Mapping[str, Any] = {
    # Never twice inside a working day. Twenty rather than twenty-four so a daily sweep that
    # runs a few minutes early is not silently skipped for a whole cycle.
    "min_interval_hours": 20,
    # After this many, escalation takes over. Four is two more than most people need and one
    # fewer than it takes to get muted.
    "max_reminders": 4,
    # Untouched means genuinely untouched — still PENDING, nobody opened it.
    "untouched_hours": 24,
    # Warn when this much of the outcome window has burned, in basis points. 7500 = three
    # quarters gone, which is late enough to be real and early enough to be actionable.
    "deadline_warning_bp": 7_500,
    # How long to wait before looking again when nothing is due. Bounds the sweep's work
    # without letting a commitment go unexamined for a whole day.
    "recheck_hours": 6,
}


#: Framing for Layer 6's copy step, escalating with how much of the window has burned. Plain
#: strings rather than an enum because this is a rendering hint packs may extend; these three
#: are the engine's own vocabulary and the renderer falls back safely on anything else.
GENTLE, FIRM, URGENT = "gentle", "firm", "urgent"


@dataclass(frozen=True, slots=True)
class ReminderState:
    """What has already been said to this person about this commitment."""

    reminder_count: int = 0
    last_reminded_at: datetime | None = None
    fired_escalation_days: frozenset[int] = frozenset()


@dataclass(frozen=True, slots=True)
class ReminderDecision:
    """Whether to speak, why, how firmly, and when to look again.

    ``next_check_at`` is returned even when the answer is no.  It is what turns the reminder
    sweep from "re-examine every open commitment every run" into a due-time query, and it means
    a commitment can never be examined *less* often than its own next meaningful moment.
    """

    should_remind: bool
    reason_code: str
    detail: str
    urgency: str
    next_check_at: datetime
    escalation_day: int | None = None

    @property
    def escalating(self) -> bool:
        return self.escalation_day is not None


def _config(cfg: Mapping[str, Any] | None) -> dict[str, Any]:
    return {**DEFAULTS, **dict(cfg or {})}


def elapsed_bp(execution: ExecutionObject, now: datetime) -> int:
    """How much of the outcome window has burned, in basis points, clamped to 0..10000.

    Integer arithmetic throughout — this number reaches the semantic layer as a fact, and a
    float would be refused by canonicalisation for exactly the right reason.
    """
    total = int((execution.deadline_at - execution.created_at).total_seconds())
    if total <= 0:
        return 10_000
    burned = int((now - execution.created_at).total_seconds())
    return max(0, min(10_000, (burned * 10_000) // total))


def urgency_for(execution: ExecutionObject, now: datetime) -> str:
    burned = elapsed_bp(execution, now)
    if burned >= 9_000:
        return URGENT
    if burned >= 6_000:
        return FIRM
    return GENTLE


def _recheck(now: datetime, cfg: Mapping[str, Any]) -> datetime:
    return now + timedelta(hours=int(cfg["recheck_hours"]))


def decide_reminder(execution: ExecutionObject, *, state: ExecutionState,
                    history: ReminderState, now: datetime,
                    cfg: Mapping[str, Any] | None = None) -> ReminderDecision:
    """One commitment, one moment: speak or stay quiet, with the reason recorded either way.

    Assumes the Execution Validation Unit has already returned ``PROCEED``.  That ordering is
    not an optimisation — it is the correctness argument for the whole unit, and callers that
    invert it will nudge people about work the world has already done.
    """
    settings = _config(cfg)
    urgency = urgency_for(execution, now)

    if not execution.remindable:
        # Unrouted work is tracked and reported, never nudged: there is nobody to nudge, and a
        # reminder to the admin queue about an unowned account is a message with no recipient.
        return ReminderDecision(False, "not_remindable", "commitment has no owner to remind",
                                urgency, execution.deadline_at)

    # The ladder is a commitment made at planning time, not another generic reminder. It must
    # survive the owner-reminder cooldown/fatigue cap, and it is the one communication still
    # allowed while work is explicitly BLOCKED. The previous ordering checked those stops first,
    # making the comment "escalation takes over" false exactly when the cap was reached.
    due = due_rungs(execution, now=now, fired_days=history.fired_escalation_days)
    if due:
        rung = due[-1]
        return ReminderDecision(True, f"escalation_{rung.action.value}",
                                f"day {rung.day_offset} of the escalation ladder",
                                URGENT if rung.interrupt else urgency,
                                _recheck(now, settings), escalation_day=rung.day_offset)

    if state is not ExecutionState.PENDING and state is not ExecutionState.RUNNING \
            and state is not ExecutionState.WAITING:
        return ReminderDecision(False, "state_not_remindable", f"commitment is {state.value}",
                                urgency, _recheck(now, settings))

    if history.last_reminded_at is not None:
        earliest = history.last_reminded_at + timedelta(hours=int(settings["min_interval_hours"]))
        if now < earliest:
            return ReminderDecision(False, "cooldown",
                                    f"last reminded {history.last_reminded_at.isoformat()}",
                                    urgency, min(earliest, execution.deadline_at))

    if history.reminder_count >= int(settings["max_reminders"]):
        # Not a failure — a handover. The ladder is now the only thing that speaks, and it
        # speaks to somebody else, which is the entire point of having a ladder.
        return ReminderDecision(False, "fatigue_cap",
                                f"{history.reminder_count} reminders already sent; "
                                "escalation owns this commitment now",
                                URGENT, _recheck(now, settings))

    # Trigger 2 — the window is burning down with nothing observed.
    if elapsed_bp(execution, now) >= int(settings["deadline_warning_bp"]):
        return ReminderDecision(True, "deadline_approaching",
                                f"{execution.deadline_at.isoformat()} with no outcome observed",
                                urgency, _recheck(now, settings))

    # Trigger 3 — it landed and nobody has touched it. Distinct from the ladder because a
    # commitment that was never opened is a delivery problem, not a diligence problem.
    if state is ExecutionState.PENDING:
        untouched_since = execution.created_at + timedelta(hours=int(settings["untouched_hours"]))
        if now >= untouched_since and history.reminder_count == 0:
            return ReminderDecision(True, "untouched",
                                    f"delivered {execution.created_at.isoformat()}, "
                                    "never opened", urgency, _recheck(now, settings))

    upcoming = next_rung(execution, now=now, fired_days=history.fired_escalation_days)
    horizon = [_recheck(now, settings)]
    if upcoming is not None:
        horizon.append(upcoming.fires_at)
    return ReminderDecision(False, "nothing_due", "no trigger has come due", urgency,
                            min(horizon))


def reminder_facts(execution: ExecutionObject, decision: ReminderDecision,
                   now: datetime) -> dict[str, Any]:
    """The grounded fact corpus a reminder may be worded from.

    Every value here is derived from the commitment itself — no lookups, no inference, no
    freshly computed business claims.  Layer 6's invention validator will refuse any rendered
    sentence containing a number, name or date that is not in this dict, so this function is
    quite literally the vocabulary of what a reminder is allowed to say.
    """
    return {
        "goal": execution.goal,
        "days_open": max(0, int((now - execution.created_at).total_seconds()) // 86_400),
        "days_remaining": max(0, int((execution.deadline_at - now).total_seconds()) // 86_400),
        "deadline": execution.deadline_at.isoformat(),
        "window_elapsed_pct": elapsed_bp(execution, now) // 100,
        "consequence": execution.do_nothing_consequence,
        "next_action": execution.first_action.label,
        "urgency": decision.urgency,
        "reason_code": decision.reason_code,
        "escalation_day": decision.escalation_day,
        "subject_ref": execution.subject_ref,
    }


__all__ = ["DEFAULTS", "FIRM", "GENTLE", "REMINDER_VERSION", "URGENT", "ReminderDecision",
           "ReminderState", "decide_reminder", "elapsed_bp", "reminder_facts", "urgency_for"]
