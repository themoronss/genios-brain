"""The morning brief, composed — once per seat per local day, at 08:00 in the org's timezone (STEP-15).

`speedrun008/YC-II W27/` STEP-15 §8.4 items 5-6, tree `yc2_w27_s15` M44.C4.L-integration.V1.U02 (`06` D9: the engine
composes at 08:00 in your org's timezone and serves the route). Nothing in the engine ran at a local hour (`03`
s15-F12): the heavy tick runs every six hours from process start, the re-rank's day is UTC.

  `compose`      the seat's day (`executive/morning_day.read_day`), ordered and in the template's words
                 (`executive/morning_template.template_brief`), kept (`executive/morning_store.keep`) — or, when
                 the seat's brief of that local day is already kept, that one, read back: the row is the claim, so
                 two composers write one brief;
  `is_due`       the local time in the org's timezone is past the brief's hour, and none is kept for that day;
  `compose_due`  for each org's account owner whose brief is due, compose it — once; a seat that fails is
                 counted and logged, never raised past: one tenant's brief is never the sweep.

No model is asked here: the words are the template's (M45 writes them when a tenant arms `morning_brief`).
"""
from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime, time
from zoneinfo import ZoneInfo

from sqlalchemy import text

from genios_engine.contracts.morning_brief import Brief
from genios_engine.executive import morning_store
from genios_engine.executive.morning_day import read_day, zone_of
from genios_engine.executive.morning_template import template_brief
from genios_engine.platform.logging import get_logger

_log = get_logger("genios.executive.morning")

#: `06` D9: the brief's hour, in the org's own timezone.
BRIEF_HOUR = 8

#: Each org's account owner: the active seat whose address is the org's own (`platform/seats.ensure_owner_seat`).
_OWNERS = text(
    "select o.id as org_id, s.seat_id from orgs o "
    "  join org_seats s on s.org_id = o.id and s.active and lower(s.email) = lower(o.email) "
    " where (cast(:orgs as text[]) is null or o.id = any(:orgs)) order by o.id, s.seat_id")


def is_due(now: datetime, tz: str, *, kept: bool) -> bool:
    """Whether a seat's brief is due: the brief's hour has passed in `tz`, and none is kept for that local day."""
    return not kept and now.astimezone(ZoneInfo(tz)).time() >= time(BRIEF_HOUR)


def compose(engine, org_id: str, seat_id: str, *, now: datetime) -> tuple[Brief, bool]:
    """The seat's brief of its local day: composed and kept, or the one already kept (False)."""
    with engine.begin() as conn:
        tz = zone_of(conn, org_id)
        local = now.astimezone(ZoneInfo(tz)).date()
        held = morning_store.read(conn, org_id, seat_id, local)
        if held is not None:
            return held, False
        day = read_day(conn, org_id, seat_id, now=now)
        brief = template_brief(org_id=org_id, seat_id=seat_id, items=day.items, now=now, tz=day.tz)
        return morning_store.keep(conn, brief)


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


__all__ = ["BRIEF_HOUR", "compose", "compose_due", "is_due"]
