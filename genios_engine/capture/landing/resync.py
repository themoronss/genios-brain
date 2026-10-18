"""The mail the old gate DELETED comes back — its key freed, its row kept, its end named (STEP-08).

MEASURED ON THE GOLDEN SET 2026-10-07 (`speedrun008/YC-II W27/` STEP-08 §8.1). Before STEP-03 every
noise rule and the AI filter's confident junk was a DROP, and a drop kept no body: production holds
258 such Gmail messages — a ledger row, outcome `dropped`, no payload. Listed again, each lands as
`duplicate`, because dedup asks only whether the key exists (`capture/pipeline.land_raw_object`), never
what became of it: 15 of 15. The one key-freeing code there was, `unread.set_aside`, matches `emitted`
rows only — and its shape is unsafe here: a deleted row marked `superseded` before its message lands
again is what `unread.recover_orphans`, at the start of every pass, turns back into `emitted` with no
content (six of six).

SO THE TWO HALVES, AND NOTHING BETWEEN THEM. `free_deleted` marks the key of every deleted message
inside the window — `<key>#resync:<event_id>` — and leaves the row `dropped`; the existing backfill
drain (`POST /connections/{id}/backfill`) then lands each message through today's gate with its body,
as one more message of the window it re-reads. `finish` takes the old row out once a new capture holds
its key — `superseded`, its trace naming the new event — and writes, once, why every other freed row
did not come back: Gmail no longer lists it, or it is older than the connection's window. Measured: 13
of 13 land again, 13 superseded, a second listing lands nothing.

NEVER FREED. A scope exclusion (`out_of_scope`): the gate's one drop left, the tenant's instruction and
not a judgment about the mail. A row with a body: the parked drain and the re-read ladder own it. An
attachment: Gmail hands out a fresh `attachmentId` on every read, so an attachment's old key is never
taken again — it comes back with its message, once (`reread.drop_reread_attachments`). Calendar and
every other source: structured, short-circuited before any noise rule; nothing there was deleted.

Every step writes one `event_trace` row (stage `resync`), so `capture/journey` walks an old row to the
event that replaced it, and the new event back to the row it replaced.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import text

from genios_engine.capture.connectors.backfill import BACKFILL_DAYS_KEY, DEFAULT_BACKFILL_DAYS

#: What a freed key carries after the message's own key, and the stage every resync trace row names.
FREED_MARK = "#resync:"
STAGE = "resync"
#: The three things a resync can say about a deleted row — the trace's reason codes.
FREED = "resync_freed"
REPLACED = "resync_replaced"
NOT_LISTED = "resync_not_listed"
#: `unread.set_aside`'s mark: a replacement the re-read ladder holds set aside mid-read is still the
#: message come back. Spelled here (capture's ladder keeps it private) and pinned equal by the tests.
SET_ASIDE_MARK = "#superseded:"

_FREE = text(
    "update source_events se set dedup_key = se.dedup_key || :mark || se.event_id "
    " where se.org_id = :o and se.source = 'gmail' and se.object_type = 'email_message' "
    "   and se.outcome = 'dropped' and se.occurred_at >= :since "
    "   and position(:mark in se.dedup_key) = 0 "
    "   and not exists (select 1 from raw_payloads rp where rp.org_id = se.org_id "
    "                    and rp.event_id = se.event_id and rp.expires_at > :now) "
    "   and not exists (select 1 from event_trace s0 where s0.org_id = se.org_id "
    "                    and s0.event_id = se.event_id and s0.reason_code = 'out_of_scope') "
    "returning se.event_id, split_part(se.dedup_key, :mark, 1) as original_key, "
    "   (select x.reason_code from event_trace x where x.org_id = se.org_id "
    "     and x.event_id = se.event_id and x.action = 'drop' "
    "     order by x.at desc, x.id desc limit 1) as dropped_by")

_FREED_ROWS = text(
    "select old.event_id, old.occurred_at, split_part(old.dedup_key, :mark, 1) as original_key, "
    "       (select n.event_id from source_events n "
    "         where n.org_id = old.org_id and n.event_id <> old.event_id "
    "           and (n.dedup_key = split_part(old.dedup_key, :mark, 1) "
    "                or left(n.dedup_key, length(split_part(old.dedup_key, :mark, 1)) "
    "                                     + length(:aside)) "
    "                   = split_part(old.dedup_key, :mark, 1) || :aside) "
    "         order by (n.dedup_key = split_part(old.dedup_key, :mark, 1)) desc, "
    "                  n.captured_at desc, n.event_id "
    "         limit 1) as replaced_by, "
    "       exists (select 1 from event_trace t where t.org_id = old.org_id "
    "                and t.event_id = old.event_id and t.stage = :stage "
    "                and t.reason_code = :not_listed) as reported "
    "  from source_events old "
    " where old.org_id = :o and old.outcome = 'dropped' and position(:mark in old.dedup_key) > 0 "
    " order by old.occurred_at, old.event_id")

_SUPERSEDE = text(
    "update source_events set outcome = 'superseded' "
    " where org_id = :o and event_id = :e and outcome = 'dropped' "
    "   and position(:mark in dedup_key) > 0")

_TRACE = text(
    "insert into event_trace (org_id, event_id, dedup_key, source, stage, action, reason_code, "
    " detail) values (:o, :e, :k, 'gmail', :stage, :action, :code, cast(:detail as jsonb))")

#: How far back the drain re-reads — the widest window of the tenant's connected Gmail connections.
_WINDOW = text(
    "select max(case when capture_scope ->> :key ~ '^[0-9]+$' "
    "                then (capture_scope ->> :key)::int end) as days, count(*) as n "
    "  from connections where org_id = :o and source_type = 'gmail' and status = 'connected'")


@dataclass(frozen=True)
class Finish:
    """What one `finish` found. `replaced` is `(old event, new event)` for every row superseded by
    THIS call; `not_listed` counts every freed row still waiting, `newly_reported` the ones whose
    reason this call wrote; `window_days` is the window those reasons were read against."""
    superseded: int
    not_listed: int
    newly_reported: int
    outside_window: int
    replaced: tuple[tuple[str, str], ...]
    window_days: int


def free_deleted(engine, org_id: str, *, days: int, now: datetime | None = None) -> int:
    """Free the key of every Gmail message the gate deleted inside the last `days`, keeping its row
    `dropped`; one trace row each. Returns how many. Idempotent: a freed key is never freed again."""
    if isinstance(days, bool) or not isinstance(days, int) or days < 1:
        raise ValueError(f"days must be a positive whole number of days, got {days!r}")
    now = now or datetime.now(timezone.utc)
    with engine.begin() as c:
        rows = c.execute(_FREE, {"o": org_id, "mark": FREED_MARK, "now": now,
                                 "since": now - timedelta(days=days)}).fetchall()
        for r in rows:
            c.execute(_TRACE, {"o": org_id, "e": r.event_id, "k": r.original_key, "stage": STAGE,
                               "action": "pass", "code": FREED,
                               "detail": json.dumps({"window_days": days,
                                                     "dropped_by": r.dropped_by})})
    return len(rows)


def window_days(conn, org_id: str) -> int:
    """The window the backfill drain re-reads for this tenant: the widest of its connected Gmail
    connections, or `DEFAULT_BACKFILL_DAYS` when none says."""
    row = conn.execute(_WINDOW, {"o": org_id, "key": BACKFILL_DAYS_KEY}).one()
    return int(row.days) if row.days else DEFAULT_BACKFILL_DAYS


def finish(engine, org_id: str, *, now: datetime | None = None) -> Finish:
    """Supersede every freed row whose message a new capture now holds, naming the new event; say,
    once, why every other freed row has not come back. Idempotent."""
    now = now or datetime.now(timezone.utc)
    replaced: list[tuple[str, str]] = []
    waiting = newly = outside = 0
    with engine.begin() as c:
        days = window_days(c, org_id)
        since = now - timedelta(days=days)
        rows = c.execute(_FREED_ROWS, {"o": org_id, "mark": FREED_MARK, "aside": SET_ASIDE_MARK,
                                       "stage": STAGE, "not_listed": NOT_LISTED}).fetchall()
        for r in rows:
            if r.replaced_by:
                if c.execute(_SUPERSEDE, {"o": org_id, "e": r.event_id,
                                          "mark": FREED_MARK}).rowcount:
                    c.execute(_TRACE, {"o": org_id, "e": r.event_id, "k": r.original_key,
                                       "stage": STAGE, "action": "pass", "code": REPLACED,
                                       "detail": json.dumps({"replaced_by": r.replaced_by})})
                    replaced.append((r.event_id, r.replaced_by))
                continue
            waiting += 1
            occurred = r.occurred_at
            if occurred is not None and occurred.tzinfo is None:
                occurred = occurred.replace(tzinfo=timezone.utc)
            inside = occurred is not None and occurred >= since
            outside += not inside
            if not r.reported:
                c.execute(_TRACE, {"o": org_id, "e": r.event_id, "k": r.original_key,
                                   "stage": STAGE, "action": "drop", "code": NOT_LISTED,
                                   "detail": json.dumps({"inside_window": inside,
                                                         "window_days": days})})
                newly += 1
    return Finish(superseded=len(replaced), not_listed=waiting, newly_reported=newly,
                  outside_window=outside, replaced=tuple(replaced), window_days=days)


__all__ = ["FREED", "FREED_MARK", "Finish", "NOT_LISTED", "REPLACED", "SET_ASIDE_MARK", "STAGE",
           "finish", "free_deleted", "window_days"]
