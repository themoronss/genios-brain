"""Layer 5 · Unit — the Escalation Unit.  What happens on each day nobody acts.

An escalation ladder is a promise made at planning time and kept later, which is why it is
built once, frozen into the execution object, and never recomputed.  If the ladder were derived
fresh each time the sweep ran, retuning the pack on a Tuesday would silently rewrite the
history of every commitment made on Monday, and "why was I escalated on day 7?" would have no
answer that survived the next config change.

Two things make the ladder more than a cron schedule.

**Urgency compresses it.**  A critical commitment does not deserve the same fourteen-day patience
as a routine one.  The band multiplier scales every rung, in integer basis points, so the shape
of the ladder is preserved while its tempo changes — critical work escalates at half the delay,
standard work at the declared delay.  This is the difference between an escalation policy and a
timer.

**It stops at the decision's expiry.**  Layer 4 declared how long it stands behind this
conclusion.  A rung that would fire after that is dropped at build time rather than fired at run
time, because escalating on the authority of a decision that has lapsed is exactly the failure
the whole authority chain exists to prevent — and dropping it here means the execution object is
*provably* incapable of it, not merely unlikely to.

Pure: evaluation time in, ladder out.  No clock, no database, no model.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime, timedelta
from typing import Any

from genios_engine.contracts.execution import (
    AudienceClass,
    EscalationAction,
    EscalationStep,
    ExecutionObject,
)

ESCALATION_VERSION = "escalate.v1"


class EscalationConfigError(RuntimeError):
    """A tenant or pack published a ladder that cannot be interpreted.

    Raised rather than defaulted.  Silently substituting the engine ladder for a misconfigured
    tenant one would mean an org believes it changed its escalation policy and it did not — and
    they would only discover otherwise on the day the policy mattered.
    """


DEFAULTS: Mapping[str, Any] = {
    # The shipped ladder: a gentle first touch, a real nudge, then widen, then widen loudly.
    # Days are *offsets from creation*, not from the deadline, because the useful intervention
    # is early — an escalation that starts when the window is already gone is a post-mortem.
    "ladder": (
        {"day": 1, "action": "notify", "audience": "owner", "interrupt": False},
        {"day": 3, "action": "remind", "audience": "owner", "interrupt": True},
        {"day": 7, "action": "escalate", "audience": "manager", "interrupt": False},
        {"day": 14, "action": "critical", "audience": "executive", "interrupt": True},
    ),
    # Tempo by band, in basis points of the declared delay. Critical work runs the same ladder
    # at half the delay; standard work runs it as written.
    "band_multiplier_bp": {"critical": 5_000, "high": 7_500, "standard": 10_000},
    # A ladder longer than this is somebody automating harassment rather than escalation.
    "max_rungs": 6,
}

_AUDIENCE_BY_NAME: Mapping[str, AudienceClass] = {item.value: item for item in AudienceClass}
_ACTION_BY_NAME: Mapping[str, EscalationAction] = {item.value: item for item in EscalationAction}


def _config(cfg: Mapping[str, Any] | None) -> dict[str, Any]:
    merged = {**DEFAULTS, **dict(cfg or {})}
    merged["band_multiplier_bp"] = {**DEFAULTS["band_multiplier_bp"],
                                    **dict(merged.get("band_multiplier_bp") or {})}
    return merged


def _scale_day(day: int, multiplier_bp: int) -> int:
    """Half-up integer scaling, floored at one day.

    Floored rather than allowed to reach zero: a rung that fires the instant the commitment is
    created is not an escalation, it is a duplicate of the original delivery.
    """
    return max(1, (day * multiplier_bp + 5_000) // 10_000)


def _parse_rung(raw: Any, index: int) -> tuple[int, EscalationAction, AudienceClass, bool]:
    if not isinstance(raw, Mapping):
        raise EscalationConfigError(f"escalation rung {index} must be a mapping")
    day = raw.get("day")
    if isinstance(day, bool) or not isinstance(day, int) or day < 0:
        raise EscalationConfigError(f"escalation rung {index} needs a non-negative integer day")
    action_name = str(raw.get("action", "")).strip().lower()
    if action_name not in _ACTION_BY_NAME:
        raise EscalationConfigError(
            f"escalation rung {index} has unknown action {raw.get('action')!r}")
    audience_name = str(raw.get("audience", "")).strip().lower()
    if audience_name not in _AUDIENCE_BY_NAME:
        raise EscalationConfigError(
            f"escalation rung {index} has unknown audience {raw.get('audience')!r}")
    interrupt = raw.get("interrupt", False)
    if not isinstance(interrupt, bool):
        raise EscalationConfigError(f"escalation rung {index} interrupt must be boolean")
    return day, _ACTION_BY_NAME[action_name], _AUDIENCE_BY_NAME[audience_name], interrupt


def build_ladder(*, eval_time: datetime, expires_at: datetime, band: str,
                 remindable: bool = True,
                 cfg: Mapping[str, Any] | None = None) -> tuple[EscalationStep, ...]:
    """Scale the declared ladder by urgency, cap it at the decision's expiry, freeze it.

    Collisions after scaling are collapsed rather than rejected: compressing a 1/3/7/14 ladder
    for critical work maps days 1 and 3 onto days 1 and 2, but a tighter tenant ladder could map
    two rungs onto the same day, and firing two escalations at the same instant is noise. The
    *stronger* rung wins the day — escalating is never downgraded to notifying by a rounding
    accident.
    """
    settings = _config(cfg)
    rungs: Sequence[Any] = tuple(settings.get("ladder") or ())
    if len(rungs) > int(settings["max_rungs"]):
        raise EscalationConfigError(
            f"escalation ladder has {len(rungs)} rungs; the ceiling is {settings['max_rungs']}")
    if not remindable:
        return ()

    multiplier = int(settings["band_multiplier_bp"].get(band, 10_000))
    strength = {action: rank for rank, action in enumerate(
        (EscalationAction.NOTIFY, EscalationAction.REMIND,
         EscalationAction.ESCALATE, EscalationAction.CRITICAL))}

    by_day: dict[int, tuple[EscalationAction, AudienceClass, bool]] = {}
    for index, raw in enumerate(rungs):
        day, action, audience, interrupt = _parse_rung(raw, index)
        scaled = _scale_day(day, multiplier)
        existing = by_day.get(scaled)
        if existing is None or strength[action] > strength[existing[0]]:
            by_day[scaled] = (action, audience, interrupt)

    steps: list[EscalationStep] = []
    for day in sorted(by_day):
        action, audience, interrupt = by_day[day]
        fires_at = eval_time + timedelta(days=day)
        if fires_at > expires_at:
            # Everything after this fires later still, so stopping is correct and cheaper than
            # filtering — and it keeps the surviving ladder contiguous from day one.
            break
        steps.append(EscalationStep(day_offset=day, action=action, audience=audience,
                                    interrupt=interrupt, fires_at=fires_at,
                                    reason_code=f"ladder_day{day}_{action.value}"))
    return tuple(steps)


def due_rungs(execution: ExecutionObject, *, now: datetime,
              fired_days: frozenset[int] | set[int] | None = None) -> tuple[EscalationStep, ...]:
    """Which rungs have come due and have not yet fired.

    Driven by ``fired_days`` — what the database says actually happened — rather than by a
    cursor.  A sweep that missed a day for any reason (deploy, outage, a paused org) must catch
    up on the rungs it skipped rather than silently forgetting them; a cursor would forget.
    """
    already = set(fired_days or ())
    return tuple(step for step in execution.escalation
                 if step.day_offset not in already and step.fires_at <= now)


def next_rung(execution: ExecutionObject, *, now: datetime,
              fired_days: frozenset[int] | set[int] | None = None) -> EscalationStep | None:
    """The next rung still ahead — what the UI shows as "escalates to your manager in 4 days"."""
    already = set(fired_days or ())
    return next((step for step in execution.escalation
                 if step.day_offset not in already and step.fires_at > now), None)


__all__ = ["DEFAULTS", "ESCALATION_VERSION", "EscalationConfigError", "build_ladder",
           "due_rungs", "next_rung"]
