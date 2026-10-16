"""The morning brief, composed — once per seat per local day, at 08:00 in the org's timezone (STEP-15).

`speedrun008/YC-II W27/` STEP-15 §8.4 items 5-6, tree `yc2_w27_s15` M44.C4.L-integration.V1.U02
(`06` D9), ARMED since M45.C3.L-integration.V0.U01 (`06` D9: the engine composes at 08:00 in your org's
timezone and serves the route). Nothing in the engine ran at a local hour (`03` s15-F12): the heavy
tick runs every six hours from process start, the re-rank's day is UTC.

  `compose`      the seat's day (`executive/morning_day.read_day`), ordered and WRITTEN
                 (`executive/morning_writer.write_brief` — the Haiku-class draft where
                 `morning_brief` is armed and holds its check, the template's own words otherwise,
                 at no cost), kept (`executive/morning_store.keep`) — or, when the seat's brief of
                 that local day is already kept, that one, read back: the row is the claim, so two
                 composers write one brief;
  `kept_brief`   the account owner's brief of a local day as kept, or None — what the Slack digest sends
                 (`deliver/outbox`, M45.C3.L-integration.V0.U03): read, never composed;
  `is_due`       the local time in the org's timezone is past the brief's hour, and none is kept for that day;
  `compose_due`  for each org's account owner whose brief is due, compose it — once; a seat that fails is
                 counted and logged, never raised past: one tenant's brief is never the sweep.

⛔ TWO TRANSACTIONS IN `compose`, NOT ONE, SINCE M45. `write_brief` may ask a real model — gated by
its own site's own daily cap, but not instant — and holding a connection (and `morning_briefs`'
unique key's lock window) open across that call for every seat on every tick is not a cost this
unit will pay. The read (is one already kept? what is the day?) happens in its own connection;
`write_brief` runs with NONE held; `keep` opens a second, short one. The race this trades for is
bounded and cheap, never unbounded: two composers beaten to the same seat's same few seconds could
each spend one real consult before the loser's `keep` finds the winner's row already there and
reads it back, discarding its own draft — never two kept briefs, and never a cost past what each
site's own cap already allows for one call.
"""
from __future__ import annotations

from collections.abc import Iterable
from datetime import date, datetime, time
from zoneinfo import ZoneInfo

from sqlalchemy import text

from genios_engine.contracts.morning_brief import Brief
from genios_engine.executive import morning_store
from genios_engine.executive.morning_day import read_day, zone_of
from genios_engine.executive.morning_writer import write_brief
from genios_engine.platform.logging import get_logger

_log = get_logger("genios.executive.morning")

#: `06` D9: the brief's hour, in the org's own timezone.
BRIEF_HOUR = 8

#: Each org's account owner: the active seat whose address is the org's own (`platform/seats.ensure_owner_seat`).
_OWNERS = text(
    "select o.id as org_id, s.seat_id from orgs o "
    "  join org_seats s on s.org_id = o.id and s.active and lower(s.email) = lower(o.email) "
    " where (cast(:orgs as text[]) is null or o.id = any(:orgs)) order by o.id, s.seat_id")

#: The founder's own name, read the same way `morning_day.read_day`'s `_SEAT` does (`orgs.name` —
#: this is a solo-founder tool, so the org's own name field holds the person's). A tiny second
#: query rather than a new field on `Day`: `Day` is M44's own contract and this unit's artifact is
#: `morning.py` alone.
_FOUNDER_NAME = text("select name from orgs where id = :o")


def is_due(now: datetime, tz: str, *, kept: bool) -> bool:
    """Whether a seat's brief is due: the brief's hour has passed in `tz`, and none is kept for that local day."""
    return not kept and now.astimezone(ZoneInfo(tz)).time() >= time(BRIEF_HOUR)


def compose(engine, org_id: str, seat_id: str, *, now: datetime) -> tuple[Brief, bool]:
    """The seat's brief of its local day: composed and kept, or the one already kept (False)."""
    with engine.connect() as conn:
        tz = zone_of(conn, org_id)
        local = now.astimezone(ZoneInfo(tz)).date()
        held = morning_store.read(conn, org_id, seat_id, local)
        if held is not None:
            return held, False
        day = read_day(conn, org_id, seat_id, now=now)
        founder = conn.execute(_FOUNDER_NAME, {"o": org_id}).scalar()

    brief = write_brief(engine, org_id=org_id, seat_id=seat_id, items=day.items, now=now, tz=day.tz,
                        founder=(founder,) if founder else ())

    with engine.begin() as conn:
        return morning_store.keep(conn, brief)


def kept_brief(engine, org_id: str, *, now: datetime, local_date: date | None = None) -> Brief | None:
    """The org's account owner's brief of a local day, as KEPT — or None: the org has no owner seat, or none is kept
    (yet). `local_date` is the day asked for; without it, the local day of `now` in the org's timezone. What the Slack
    digest sends (`deliver/outbox`, M45.C3.L-integration.V0.U03; `03` s15-F4): the morning has one surface, and it is
    this brief — read, never composed, here."""
    with engine.connect() as conn:
        owner = conn.execute(_OWNERS, {"orgs": [org_id]}).first()
        if owner is None:
            return None
        day = local_date or now.astimezone(ZoneInfo(zone_of(conn, org_id))).date()
        return morning_store.read(conn, org_id, owner.seat_id, day)


def compose_due(engine, *, now: datetime, orgs: Iterable[str] | None = None) -> dict[str, int]:
    """Compose every account owner's brief that is due — `orgs` limits the tenants asked. Never raises past a seat:
    what failed is counted (`failed`) and logged."""
    counts = {"due": 0, "composed": 0, "kept_already": 0, "not_yet": 0, "failed": 0}
    wanted = None if orgs is None else sorted(set(orgs))
    with engine.connect() as conn:
        owners = [(r.org_id, r.seat_id) for r in conn.execute(_OWNERS, {"orgs": wanted})]
    for org_id, seat_id in owners:
        try:
            with engine.connect() as conn:
                tz = zone_of(conn, org_id)
                local = now.astimezone(ZoneInfo(tz)).date()
                kept = morning_store.read(conn, org_id, seat_id, local) is not None
            if not is_due(now, tz, kept=kept):
                counts["kept_already" if kept else "not_yet"] += 1
                continue
            counts["due"] += 1
            _brief, wrote = compose(engine, org_id, seat_id, now=now)
            counts["composed" if wrote else "kept_already"] += 1
        except Exception:      # noqa: BLE001 — one seat's brief is never the sweep
            counts["failed"] += 1
            _log.exception("the morning brief could not be composed org=%s seat=%s", org_id, seat_id)
    return counts


__all__ = ["BRIEF_HOUR", "compose", "compose_due", "is_due", "kept_brief"]
