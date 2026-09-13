"""Whether a moment is SHOWN — shadow flag, DND, quiet hours, per-seat rate limits (P3 §2.2).

Every moment is stored either way; a suppressed one carries the first reason that applied:

    shadow            capture_policies.moments_display is off (the default — plan §15)
    dnd               the device reports Do-Not-Disturb / Focus (critical moments still show)
    quiet_hours       inside the seat's CONFIGURED quiet window (reminders and critical show)
    rate_limited_hour ≥ max shown in the last hour (default 6; reminders are never capped)
    rate_limited_day  ≥ max shown in the last 24 h (default 30)
    duplicate         an identical moment is still inside its TTL (decided in store.py)

QUIET HOURS ARE OPT-IN HERE. `deliver/timing.AttentionProfile` defaults to a protective 21:00–08:00
window for pushes that interrupt someone who is away. A moment is about what the seat is looking
at right now, so the default would only mute a person working late (or, with no timezone known,
their whole Indian morning — the defect `deliver/gate.build_context` records). The window applies
when a `delivery_preferences` row configures it for the seat (or '*') on `desktop` (or '*'), in
that row's zone, else the org's. It is evaluated with the shared `platform/quiet_hours.QuietWindow`
(same rules as the delivery profile) — this Layer 4 module never imports Layer 6.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import text

from genios_engine.platform.quiet_hours import QuietWindow

#: The delivery profile's defaults, for a configured window that leaves an hour unset.
_DEFAULT_START, _DEFAULT_END = 21, 8

SHADOW = "shadow"
DND = "dnd"
QUIET = "quiet_hours"
RATE_HOUR = "rate_limited_hour"
RATE_DAY = "rate_limited_day"
DUPLICATE = "duplicate"

DEFAULT_MAX_PER_HOUR = 6
DEFAULT_MAX_PER_DAY = 30


@dataclass(frozen=True)
class GuardState:
    moments_display: bool = False
    max_per_hour: int = DEFAULT_MAX_PER_HOUR
    max_per_day: int = DEFAULT_MAX_PER_DAY
    shown_hour: int = 0
    shown_day: int = 0
    dnd: bool = False
    quiet: QuietWindow | None = None           # None = no quiet window configured


def quiet_profile(prefs: dict | None, org_tz: str | None) -> QuietWindow | None:
    """A configured quiet window → its QuietWindow; unconfigured or unusable → None."""
    if not prefs or not prefs.get("quiet_enabled"):
        return None
    start, end = prefs.get("quiet_start_hour"), prefs.get("quiet_end_hour")
    try:
        return QuietWindow(timezone=str(prefs.get("tz_name") or org_tz or "UTC"),
                           start_hour=int(start if start is not None else _DEFAULT_START),
                           end_hour=int(end if end is not None else _DEFAULT_END),
                           weekends=bool(prefs.get("quiet_weekends") or False))
    except (ValueError, TypeError):
        return None


def decide(state: GuardState, *, kind: str, priority: str, now: datetime) -> tuple[bool, str | None]:
    """(display, reason). Most general first, so shadow mode reports shadow."""
    if not state.moments_display:
        return False, SHADOW
    critical = priority == "critical"
    if state.dnd and not critical:
        return False, DND
    if (state.quiet is not None and not critical and kind != "reminder"
            and state.quiet.is_quiet_at(now)):
        return False, QUIET
    if kind != "reminder":
        if state.shown_hour >= state.max_per_hour:
            return False, RATE_HOUR
        if state.shown_day >= state.max_per_day:
            return False, RATE_DAY
    return True, None


_STATE = text(
    "select "
    "(select count(*) from moments m where m.org_id = :o and m.seat_id = :s and m.display "
    " and m.kind <> 'reminder' and m.created_at > :now - interval '1 hour') as shown_hour, "
    "(select count(*) from moments m where m.org_id = :o and m.seat_id = :s and m.display "
    " and m.kind <> 'reminder' and m.created_at > :now - interval '1 day') as shown_day, "
    "o.timezone as org_tz, p.moments_display, p.moments_max_per_hour, p.moments_max_per_day, "
    "(select bool_or(l.dnd) from presence_leases l where l.org_id = :o and l.seat_id = :s "
    " and l.expires_at > :now and (cast(:d as text) is null or l.device_id = cast(:d as text))"
    ") as dnd, "
    "dp.tz_name, dp.quiet_enabled, dp.quiet_start_hour, dp.quiet_end_hour, dp.quiet_weekends "
    "from orgs o "
    "left join capture_policies p on p.org_id = o.id "
    "left join lateral (select d.tz_name, d.quiet_enabled, d.quiet_start_hour, d.quiet_end_hour, "
    " d.quiet_weekends from delivery_preferences d where d.org_id = o.id "
    " and d.seat_id in (:s, '*') and d.channel in ('desktop', '*') "
    " and d.quiet_enabled is not null "
    " order by (d.seat_id = :s) desc, (d.channel = 'desktop') desc limit 1) dp on true "
    "where o.id = :o")


def load_state(conn, *, org_id: str, seat_id: str, device_id: str | None,
               now: datetime) -> GuardState:
    """Everything the decision needs in ONE statement (run inside the persist transaction, after
    the seat's advisory lock, so two concurrent moments cannot both take the last slot)."""
    r = conn.execute(_STATE, {"o": org_id, "s": seat_id, "d": device_id, "now": now}
                     ).mappings().first()
    if r is None:
        return GuardState()
    prefs = {k: r[k] for k in ("tz_name", "quiet_enabled", "quiet_start_hour", "quiet_end_hour",
                               "quiet_weekends")}
    return GuardState(
        moments_display=bool(r["moments_display"]),
        max_per_hour=int(r["moments_max_per_hour"] if r["moments_max_per_hour"] is not None
                         else DEFAULT_MAX_PER_HOUR),
        max_per_day=int(r["moments_max_per_day"] if r["moments_max_per_day"] is not None
                        else DEFAULT_MAX_PER_DAY),
        shown_hour=int(r["shown_hour"] or 0), shown_day=int(r["shown_day"] or 0),
        dnd=bool(r["dnd"]), quiet=quiet_profile(prefs, r["org_tz"]))


def lock_seat(conn, org_id: str, seat_id: str) -> None:
    """Serialise one seat's moment writes for the rest of the transaction."""
    conn.execute(text("select pg_advisory_xact_lock(hashtextextended(:k, 0))"),
                 {"k": f"moments:{org_id}:{seat_id}"})


__all__ = ["DND", "DUPLICATE", "GuardState", "QUIET", "RATE_DAY", "RATE_HOUR", "SHADOW",
           "decide", "load_state", "lock_seat", "quiet_profile"]
