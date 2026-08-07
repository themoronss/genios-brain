"""Layer 5.2 · the Timing & Interruptibility Unit — *should I interrupt this person, now?*

Every other unit in this layer asks whether a message is correct.  This one asks whether the
moment is.  It is the difference between a system people keep installed and one they mute in
week three, and it is the only unit here that can make GeniOS look thoughtless while being
completely right: a churn alert that is accurate, owned, well-worded and delivered at 03:14 is
still a reason to turn notifications off, and once they are off none of the accuracy matters.

**The one rule underneath all the others: deferral is not suppression.**  Nothing in this module
ever decides that a person should not be told something.  That judgement was made upstairs, by a
layer with the context to make it.  This unit only ever moves the moment — and where it cannot
find a humane one it says so with a reason code rather than quietly dropping the message.

**What it keys on, and why it is not ``interrupt``.**  Layer 5's ``CommunicationPlan.interrupt``
means *this deserves attention*.  It does not mean *this will make a phone buzz*: a high-band
card is pushed to Slack with ``interrupt=False`` and still lights up a lock screen at midnight.
Gating on ``DeliveryCandidate.intrusive`` — a property of the channel's physics rather than of
the sender's intent — is what closes that gap.  A digest is never gated here, because nobody was
ever going to be woken by a digest.

**The break-glass, and why it borrows Layer 5's confidence rule for free.**  Some things really
should wake somebody.  The escape hatch is ``band ≥ override_band AND interrupt``, and the second
half is doing more work than it looks.  ``executive/communication.py`` only sets ``interrupt``
when the reasoner's confidence clears its floor — a critical-scoring conclusion it is 40% sure of
comes through with ``interrupt=False`` — so a low-confidence crisis cannot break glass, and this
unit gets that property without knowing what a confidence interval is.  One dial, upstairs.

**Constraints compose; they do not race.**  A meeting, quiet hours and a burst limit are three
independent facts, and a delivery has to satisfy all three.  Rather than an if/elif ladder whose
order silently decides the answer, each check produces its own decision and
``DeliveryDecision.combine`` folds them: the latest window binds.  Adding a fourth signal later
is adding a line to a list.

**Purity.**  No database handle, no clock of its own.  Live signals arrive as an
``AttentionState`` the caller resolved, which is what makes the whole unit provable in CI — this
suite has no service containers — and what will let a calendar-backed busy signal replace today's
empty one without touching a single branch below.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from genios_engine.contracts.delivery import BAND_ORDER, DeliveryCandidate, DeliveryDecision

TIMING_VERSION = "timing.v1"
UNIT = "timing"

#: How far ahead the open-window search will look before giving up.  Eight days rather than one,
#: so a Friday-evening message under weekend quiet still finds Monday morning instead of falling
#: off the end of the scan.  It is a guard against a pathological profile, not a real limit: a
#: valid profile always opens within 48 hours.
_SEARCH_HORIZON_HOURS = 24 * 8

#: The rolling window a burst limit is measured over.
_BURST_WINDOW = timedelta(hours=1)


@dataclass(frozen=True, slots=True)
class AttentionProfile:
    """When this recipient may be interrupted, in their own local time.

    Defaults are deliberately protective.  A tenant that has configured nothing gets quiet hours
    switched **on** (21:00–08:00 local, UTC until they tell us otherwise), because the failure
    modes are not symmetric: a notification held until morning costs a few hours on something
    that was already days old, while one delivered at 03:00 costs the channel itself.  Critical
    work still breaks through, so the protective default has a floor, not a ceiling.
    """

    timezone: str = "UTC"
    quiet_enabled: bool = True
    quiet_start_hour: int = 21            # local hour the quiet window opens, inclusive
    quiet_end_hour: int = 8               # local hour it closes, exclusive
    quiet_weekends: bool = False          # treat Sat/Sun as entirely quiet
    max_interrupts_per_hour: int = 3
    override_band: str = "critical"       # the band allowed to break every rule above

    def __post_init__(self) -> None:
        for label, hour in (("quiet_start_hour", self.quiet_start_hour),
                            ("quiet_end_hour", self.quiet_end_hour)):
            if isinstance(hour, bool) or not isinstance(hour, int) or not 0 <= hour <= 23:
                raise ValueError(f"{label} must be an integer hour 0..23")
        # An equal start and end is genuinely ambiguous — zero hours of quiet or twenty-four? —
        # and one of those two readings silently mutes the product forever.  Refusing the config
        # turns a support mystery into a validation error at the moment somebody typed it.
        if self.quiet_enabled and self.quiet_start_hour == self.quiet_end_hour:
            raise ValueError(
                "quiet_start_hour and quiet_end_hour are equal, which means either no quiet "
                "hours or a permanently silent channel; set quiet_enabled=False for the former")
        if (isinstance(self.max_interrupts_per_hour, bool)
                or not isinstance(self.max_interrupts_per_hour, int)
                or self.max_interrupts_per_hour < 1):
            raise ValueError("max_interrupts_per_hour must be a positive integer")
        if self.override_band not in BAND_ORDER:
            raise ValueError(f"override_band must be one of {BAND_ORDER}")
        try:
            ZoneInfo(str(self.timezone))
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ValueError(f"unknown timezone {self.timezone!r}") from exc

    @property
    def zone(self) -> ZoneInfo:
        return ZoneInfo(str(self.timezone))

    def is_quiet(self, local: datetime) -> bool:
        """Is this local wall-clock moment inside the recipient's quiet window?"""
        if not self.quiet_enabled:
            return False
        if self.quiet_weekends and local.weekday() >= 5:      # Saturday=5, Sunday=6
            return True
        start, end = self.quiet_start_hour, self.quiet_end_hour
        if start < end:                                        # 00:00–08:00, same day
            return start <= local.hour < end
        return local.hour >= start or local.hour < end         # 21:00–08:00, wraps midnight


@dataclass(frozen=True, slots=True)
class AttentionState:
    """What is true about this recipient's attention *right now*.

    Resolved by the caller and passed in whole, so this module stays a pure function of its
    inputs.  The empty default is the honest v1 answer for ``busy_until``: GeniOS ingests
    calendars, but nothing yet projects "in a meeting until" per seat, and a fabricated busy
    signal would be worse than none.  The seam is here so that projection can be plugged in
    without reopening any decision below.
    """

    busy_until: datetime | None = None        # in a meeting or a focus block until this instant
    interrupts_last_hour: int = 0
    oldest_interrupt_at: datetime | None = None   # start of the rolling burst window


def _hours_from(moment: datetime) -> datetime:
    return moment.replace(minute=0, second=0, microsecond=0)


def next_open_window(now: datetime, profile: AttentionProfile) -> datetime | None:
    """The first instant at or after ``now`` that is outside the recipient's quiet window.

    Searched on the naive local wall clock and converted back per candidate, which is what makes
    it correct across a daylight-saving change: quiet hours are a statement about wall-clock time
    ("not before 8am"), and adding absolute hours to an aware datetime would drift that boundary
    by one on the two days a year it matters.  The loop requires each candidate to be strictly
    later than ``now`` in *absolute* terms, so a repeated wall-clock hour during a DST fall-back
    can never hand back a moment already in the past.

    ``None`` means no window opens inside the search horizon — only reachable with a profile
    ``AttentionProfile`` would have rejected, and handled by the caller as "send rather than
    hold forever".
    """
    zone = profile.zone
    wall = _hours_from(now.astimezone(zone)).replace(tzinfo=None)
    for step in range(_SEARCH_HORIZON_HOURS):
        candidate_wall = wall + timedelta(hours=step)
        if profile.is_quiet(candidate_wall):
            continue
        candidate = candidate_wall.replace(tzinfo=zone).astimezone(timezone.utc)
        if candidate > now:
            return candidate
    return None


def evaluate_timing(candidate: DeliveryCandidate, profile: AttentionProfile,
                    state: AttentionState, *, now: datetime) -> DeliveryDecision:
    """Decide whether this delivery may interrupt its recipient at ``now``.

    Returns SEND or DEFER — never SUPPRESS.  Whether a person should hear about something at all
    is not a question about the clock, and answering it here would put a second, much dumber
    policy engine underneath the one that already made the call.
    """
    if not candidate.intrusive:
        return DeliveryDecision.send(UNIT, "channel_not_intrusive",
                                     channel_class=candidate.channel_class.value)

    # The break-glass, checked before anything that could hold the message.  Deliberately not a
    # per-check exception: one place decides that this is the class of thing worth waking someone
    # for, so raising the bar is a single config change rather than an audit of every branch.
    if candidate.interrupt and candidate.at_least(profile.override_band):
        return DeliveryDecision.send(UNIT, f"override_band_{candidate.band}",
                                     override_band=profile.override_band)

    checks: list[DeliveryDecision] = []

    # 1. In a meeting or a focus block. Guarded on the instant still being ahead of us: a stale
    #    busy_until must resolve to "go", not to a deferral whose window has already closed.
    if state.busy_until is not None and state.busy_until > now:
        checks.append(DeliveryDecision.defer(UNIT, "recipient_busy", state.busy_until))

    # 2. Asleep, or otherwise off the clock.
    local = now.astimezone(profile.zone)
    if profile.is_quiet(local):
        opens_at = next_open_window(now, profile)
        if opens_at is None:
            # Unreachable through AttentionProfile, which refuses an all-day quiet window. Kept
            # because the alternative on a config that slipped through some future loader is a
            # message that waits forever, and a message delivered slightly rudely beats one that
            # is never delivered at all.
            checks.append(DeliveryDecision.send(UNIT, "quiet_window_unsatisfiable",
                                                timezone=profile.timezone))
        else:
            checks.append(DeliveryDecision.defer(
                UNIT, "quiet_hours", opens_at, timezone=profile.timezone,
                local_hour=local.hour))

    # 3. Too much, too fast. This caps the *burst*, and only the burst: the per-person daily
    #    volume is already capped upstream by the pack's `budget_per_user_day`
    #    (deliver/router.py), and a second daily dial here would be a second answer to the same
    #    question — the failure mode being two limits that disagree and neither of which anybody
    #    can find. An hour window is the dimension that budget does not cover: seven cards are a
    #    reasonable day and an unreasonable minute.
    if state.interrupts_last_hour >= profile.max_interrupts_per_hour:
        window_started = state.oldest_interrupt_at or now
        clears_at = max(window_started + _BURST_WINDOW, now + timedelta(minutes=1))
        checks.append(DeliveryDecision.defer(
            UNIT, "burst_limit", clears_at,
            delivered_last_hour=int(state.interrupts_last_hour),
            limit=int(profile.max_interrupts_per_hour)))

    if not checks:
        return DeliveryDecision.send(UNIT, "within_attention_window")
    return DeliveryDecision.combine(*checks)


def describe_profile(profile: AttentionProfile) -> dict[str, Any]:
    """Flat, loggable summary — used in delivery audit rows so a held message explains itself."""
    return {"timezone": profile.timezone, "quiet_enabled": profile.quiet_enabled,
            "quiet_start_hour": profile.quiet_start_hour,
            "quiet_end_hour": profile.quiet_end_hour,
            "quiet_weekends": profile.quiet_weekends,
            "max_interrupts_per_hour": profile.max_interrupts_per_hour,
            "override_band": profile.override_band}


__all__ = ["TIMING_VERSION", "UNIT", "AttentionProfile", "AttentionState", "describe_profile",
           "evaluate_timing", "next_open_window"]
