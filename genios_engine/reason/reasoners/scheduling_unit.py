"""Category 3 · Optimization — the Scheduling Unit.

Answers one question: *does the clock allow this to happen now, and if not, when does it?*

"When" is half of a good recommendation and the half GeniOS used to get wrong. "Follow up today"
is not advice, it is damage, if the same buyer has a call with us tomorrow morning: the follow-up
pre-empts the meeting, burns the reason to meet, and makes the sender look like they do not know
their own calendar. The same sentence is equally wrong sent four hours after the last email (it
reads as pestering) or during a stated quiet window (it reads as not listening).

So this unit collects the timing constraints that are actually evidenced in the snapshot — a
scheduled interaction, a deadline, a declared cadence gap, a quiet period — and reports two things:

* `timing_fit_bp` — how well *acting now* sits with those constraints, 10,000 meaning nothing in
  the situation argues against now.
* `wait_hours` — the shortest wait that clears every constraint at once, bounded by any deadline
  that will not wait for it.

It does not choose an action, does not rank plays, and emits no candidate adjustments or checks.
It reports the shape of the window; the Decision Maker decides what to put inside it. A constraint
this unit cannot evidence is a constraint it stays silent about — an invented "wait 24 hours" is
worse than no timing advice at all, because it is indistinguishable from a measured one.

Fact names are configurable because different capabilities carry the same constraint under
different names, but every default points at a field Layer 2 already publishes for deals.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from genios_engine.contracts.reasoning import Finding, ReasoningRequest

from ..unit import Observation, ReasoningUnit, UnitCategory, UnitView, Verdict
from .common import clamp_bp, divide_half_up, elapsed_hours, evidence_ids, fact_value, parse_time


def _config_bp(view: UnitView, key: str, default: int) -> int:
    """Per-capability tuning, validated as integer basis points.

    A float or an out-of-range threshold authored in Layer 3 must fail loudly here rather than be
    coerced: silent coercion would change decision hashes without changing the manifest.
    """
    value = view.config.get(key, default)
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 10_000:
        raise ValueError(f"{key} must be integer basis points")
    return value


def _config_hours(view: UnitView, key: str, default: int) -> int:
    """Per-capability tuning expressed in whole hours (one hour to one year).

    Hours are not basis points and must not be validated as if they were — a 336-hour deadline
    window is legitimate, a 336bp one would be a typo nobody catches.
    """
    value = view.config.get(key, default)
    if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= 8_760:
        raise ValueError(f"{key} must be a whole number of hours between 1 and 8760")
    return value


def _config_field(view: UnitView, key: str, default: str) -> str:
    value = view.config.get(key, default)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{key} must be a fact name")
    return value.strip()


def _hours_ahead(request: ReasoningRequest, field: str) -> int | None:
    """Whole hours from the frozen evaluation time until a future fact, or None.

    `elapsed_hours` deliberately refuses future timestamps, but every constraint in this unit is
    ahead of us, so the unit needs the mirror image. None means "this is not a future constraint" —
    absent, unparseable, or already past — and the caller must then say nothing rather than
    substitute a zero, which would read downstream as "it is happening right now".
    """
    value = fact_value(request, field)
    if value is None:
        return None
    try:
        moment = parse_time(value, field)
    except ValueError:
        return None
    seconds = int((moment - request.evaluation_time).total_seconds())
    return None if seconds <= 0 else seconds // 3600


def _wait_window(observations: Sequence[Observation]) -> tuple[int, int | None]:
    """The longest wait any constraint demands, and the hardest ceiling any constraint imposes.

    Waits take the maximum because a window only opens once *every* constraint has cleared;
    ceilings take the minimum because the earliest deadline is the one that binds.
    """
    demanded = max((int(item.metrics["wait_hours"]) for item in observations
                    if "wait_hours" in item.metrics), default=0)
    ceilings = [int(item.metrics["max_wait_hours"]) for item in observations
                if "max_wait_hours" in item.metrics]
    return demanded, (min(ceilings) if ceilings else None)


class UpcomingInteractionPlugin:
    """A scheduled interaction is already booked, and acting now would spend its reason.

    This is the constraint that most often makes an otherwise correct recommendation embarrassing.
    If there is a call with this counterparty in the calendar, the outreach we are considering is
    the agenda of that call; sending it early does not accelerate anything, it removes the reason
    to hold the meeting and signals we were not tracking it.

    Pre-emption is strongest at the moment of the meeting and fades linearly to nothing at the
    configured horizon: a call in two hours makes acting now nearly indefensible, a call in three
    days barely constrains today at all. Beyond the horizon the plugin is silent — a meeting next
    month is a fact about next month, not a reason to sit on today's work.
    """

    plugin_id = "upcoming_interaction"

    def contribute(self, view: UnitView) -> tuple[Observation, ...]:
        field = _config_field(view, "next_interaction_field", "calendar.next_meeting_at")
        horizon = _config_hours(view, "interaction_horizon_hours", 72)
        ahead = _hours_ahead(view.request, field)
        if ahead is None or ahead > horizon:
            return ()
        preempt_bp = clamp_bp(10_000 - divide_half_up(ahead * 10_000, horizon))
        return (Observation(
            plugin_id=self.plugin_id,
            kind="scheduling.upcoming_interaction",
            # `wait_hours` is the meeting itself: it is the next moment at which this situation is
            # genuinely different, so it is the honest point to re-evaluate from.
            metrics={"against_now_bp": preempt_bp, "hours_ahead": ahead, "wait_hours": ahead},
            evidence_ids=evidence_ids(view.request, field),
            reason_codes=("defer_until_after_meeting",),
        ),)


class DeadlinePressurePlugin:
    """A dated commitment is closing, which compresses every window around it.

    A deadline is the one timing constraint that never argues against acting now — it only argues
    against waiting. So this plugin contributes no opposition at all; it contributes pressure and,
    critically, a ceiling: no other constraint may push the recommended wait past the deadline it
    would blow. That ceiling is what stops "wait for Thursday's meeting" from being emitted when
    the contract expires on Wednesday.

    Pressure rises linearly as the deadline enters the configured window and the plugin is silent
    outside it, because a close date eleven weeks out is a planning fact, not a timing constraint.
    """

    plugin_id = "deadline_pressure"

    def contribute(self, view: UnitView) -> tuple[Observation, ...]:
        field = _config_field(view, "deadline_field", "deal.close_date")
        window = _config_hours(view, "deadline_window_hours", 336)   # two weeks
        urgent_bp = _config_bp(view, "deadline_urgent_bp", 7_500)
        left = _hours_ahead(view.request, field)
        # A deadline already in the past is not a scheduling constraint — nothing this unit
        # reports can be waited for any more. That is a risk observation and belongs to core.risk.
        if left is None or left >= window:
            return ()
        pressure_bp = clamp_bp(10_000 - divide_half_up(left * 10_000, window))
        codes = ("deadline_within_window",)
        if pressure_bp >= urgent_bp:
            codes += ("act_before_deadline",)
        return (Observation(
            plugin_id=self.plugin_id,
            kind="scheduling.deadline_pressure",
            metrics={"pressure_bp": pressure_bp, "hours_left": left, "max_wait_hours": left},
            evidence_ids=evidence_ids(view.request, field),
            reason_codes=codes,
        ),)


class CadenceSpacingPlugin:
    """We contacted them recently, and contacting them again this soon reads as pressure.

    Cadence is the difference between persistence and harassment, and it is not a property of our
    urgency — it is a property of how long ago *they* last heard from us. The gap is declared per
    capability in Layer 3 rather than inferred, because the right spacing for an enterprise renewal
    and for a support escalation are hours apart and no formula recovers that from the snapshot.

    Silence when the gap has already been respected is deliberate: a constraint that has cleared is
    not an observation, and emitting a zero-strength one would inflate the constraint count.
    """

    plugin_id = "cadence_spacing"

    def contribute(self, view: UnitView) -> tuple[Observation, ...]:
        field = _config_field(view, "last_contact_field", "deal.last_outbound")
        min_gap = _config_hours(view, "min_gap_hours", 48)
        if fact_value(view.request, field) is None:
            return ()
        try:
            elapsed = elapsed_hours(view.request, field)
        except ValueError:
            # Unparseable, or stamped in the future: we cannot measure the gap, so we do not claim
            # one. Guessing here would suppress a legitimate follow-up on bad source data.
            return ()
        if elapsed >= min_gap:
            return ()
        crowding_bp = clamp_bp(10_000 - divide_half_up(elapsed * 10_000, min_gap))
        return (Observation(
            plugin_id=self.plugin_id,
            kind="scheduling.cadence_spacing",
            metrics={"against_now_bp": crowding_bp, "elapsed_hours": elapsed,
                     "wait_hours": min_gap - elapsed},
            evidence_ids=evidence_ids(view.request, field),
            reason_codes=("too_soon_after_last_contact",),
        ),)


class QuietWindowPlugin:
    """Somebody said "not until". That is not a preference to be weighed, it is a boundary.

    An out-of-office, a stated review period, a legal freeze — whatever produced the fact, the
    counterparty has told us when we may next speak. This unit marks the observation absolute so
    that no amount of deadline pressure can dress "acting now" up as acceptable: a closing deadline
    is our problem, not a licence to ignore what they asked for.

    The fact is optional and often absent; absence means no quiet window is known, never that one
    has been checked and cleared.
    """

    plugin_id = "quiet_window"

    def contribute(self, view: UnitView) -> tuple[Observation, ...]:
        field = _config_field(view, "quiet_until_field", "schedule.quiet_until")
        remaining = _hours_ahead(view.request, field)
        if remaining is None:
            return ()
        return (Observation(
            plugin_id=self.plugin_id,
            kind="scheduling.quiet_window",
            # `absolute_bp` is the marker the calculator looks for: its presence, not its size,
            # is what withdraws deadline relief.
            metrics={"against_now_bp": 10_000, "absolute_bp": 10_000,
                     "hours_remaining": remaining, "wait_hours": remaining},
            evidence_ids=evidence_ids(view.request, field),
            reason_codes=("inside_quiet_period",),
        ),)


class SchedulingUnit(ReasoningUnit):
    """Optimization · when the situation allows this to happen.

    Publishes timing only. `confidence_bp`, `urgency_bp` and `priority_override_bp` are owned by
    core.confidence and core.priority; a scheduling unit that touched them would silently re-score
    every capability in the roster every time somebody put a meeting in a calendar.
    """

    unit_id = "core.scheduling"
    version = "1.0.0"
    category = UnitCategory.OPTIMIZATION
    publishes = ("constraint_count", "deadline_pressure_bp", "timing_fit_bp", "wait_hours")
    plugins = (UpcomingInteractionPlugin(), DeadlinePressurePlugin(),
               CadenceSpacingPlugin(), QuietWindowPlugin())

    def calculate(self, view: UnitView,
                  observations: Sequence[Observation]) -> Mapping[str, int]:
        """Strongest objection sets the fit; a closing deadline buys back at most half of it.

        Deliberately not additive. Two soft constraints do not compound into a prohibition — the
        binding objection is the one that most argues against acting now, and summing them would
        make any busy account permanently unactionable.

        The deadline term is relief rather than opposition: as a dated commitment closes, the cost
        of waiting rises, so the same pre-emption risk becomes more tolerable. It is capped at half
        the pressure so that pressure can soften a judgement but never manufacture a good moment,
        and it is withdrawn entirely when any constraint is marked absolute.
        """
        opposition = max((int(item.metrics.get("against_now_bp", 0)) for item in observations),
                         default=0)
        pressure = max((int(item.metrics.get("pressure_bp", 0)) for item in observations),
                       default=0)
        absolute = any("absolute_bp" in item.metrics for item in observations)
        relief = 0 if absolute else divide_half_up(pressure, 2)
        demanded, ceiling = _wait_window(observations)
        wait = demanded if ceiling is None else min(demanded, ceiling)
        return {"timing_fit_bp": clamp_bp(10_000 - opposition + relief),
                "wait_hours": max(0, wait),
                "constraint_count": len(observations),
                "deadline_pressure_bp": clamp_bp(pressure)}

    def evaluate_meaning(self, view: UnitView, metrics: Mapping[str, int],
                         observations: Sequence[Observation]) -> Verdict:
        """`matched` means the clock materially constrains acting now — not that we should wait.

        Every observed constraint becomes a finding regardless of the verdict, because "we checked
        the calendar and the meeting was three days out" is exactly the trace someone needs when
        they later ask why the system sent something the day before a call.
        """
        threshold = _config_bp(view, "timing_fit_threshold_bp", 6_000)
        constrained = bool(observations) and metrics["timing_fit_bp"] < threshold
        findings = tuple(Finding(
            finding_id=f"scheduling.{item.plugin_id}",
            kind="scheduling",
            matched=True,
            metrics=item.metrics,
            evidence_ids=item.evidence_ids,
            reason_codes=item.reason_codes,
        ) for item in observations)
        codes = {code for item in observations for code in item.reason_codes}
        demanded, ceiling = _wait_window(observations)
        if ceiling is not None and demanded > ceiling:
            # The wait that clears the calendar runs past the deadline it would blow. Both facts
            # are true and irreconcilable; naming the conflict is the unit's job, resolving it is
            # the Decision Maker's.
            codes.add("timing_conflict_deadline_before_clearance")
        if not observations:
            codes.add("timing_unconstrained")
        return Verdict(
            matched=constrained,
            metrics=dict(metrics),
            findings=findings,
            reason_codes=tuple(sorted(codes)),
        )


__all__ = ["CadenceSpacingPlugin", "DeadlinePressurePlugin", "QuietWindowPlugin",
           "SchedulingUnit", "UpcomingInteractionPlugin"]
