"""Bring back the Gmail mail the old gate DELETED — STEP-08. A dry run unless told otherwise.

    python scripts/resync_deleted_mail.py --org <org_id> --database-url postgresql://…    # dry run
    … --days 365                  # the dry run for one window: what it reaches, what it leaves out
    … --apply --days 365          # frees the keys; the rows stay `dropped`
    … --finish                    # after the backfill drain: superseded, and not listed with why

**Why.** Before STEP-03 every noise rule and the AI filter's confident junk DELETED a mail: 258 of the
design partner's 395 Gmail messages are a ledger row with outcome `dropped` and no body. Listed again,
each lands as `duplicate`, because dedup ignores the outcome. `--apply` frees their keys
(`capture/landing/resync`); the existing backfill drain lands each through today's gate with its body;
`--finish` supersedes the old rows and says why the rest did not come back.

**The runbook** (`speedrun008/YC-II W27/` STEP-08 §8.6), after STEP-03 … STEP-07 are deployed and the
company brief is accepted (D26):
  1. this, as a dry run — send it to Rohit, who names the window (D5 / D16);
  2. `PATCH /connections/{gmail}/backfill-window` with that many days;
  3. `--apply --days <N>`;
  4. `POST /connections/{gmail}/backfill` — the legacy door, every message fetched in full (never
     `/integrations/gmail/sync`, which keeps rule-junk as a list snippet); wait for `backfill drain
     done` in the log, and run it again while it says `TRUNCATED`;
  5. `--finish`;
  6. `scripts/pipeline_health.py`: *every Gmail message in the window has its content, or a stated
     reason* must pass.

**What it reads and writes.** The dry run reads the ledger through a read-only transaction: counts by
the rule that deleted the mail, by month and by sender domain, the oldest, the window that reaches it,
what a given window leaves out, and the attachments — never a subject or a body. `--apply` changes the
key of each row it frees and writes one trace row each; `--finish` sets `superseded` on the rows a new
capture replaced and writes one trace row each. Nothing is deleted. Run again, each step does nothing
it has done.

**The target** goes through `scripts/_db.py`: no fallback to the application's database, and
`GENIOS_ALLOW_PROD_WRITE=1` for a production host.
"""
from __future__ import annotations

import argparse
import math
import os
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts._db import add_database_argument, resolve_database_url   # noqa: E402
from scripts._gate import read_only_connection, sql                   # noqa: E402

#: How many sender domains the dry run names.
TOP_DOMAINS = 15

#: Every deleted message the re-sync can free, whatever its age — `resync.free_deleted`'s population
#: before its window (`tests/scripts/test_resync_deleted_mail.py` holds the two equal).
_DELETED = (
    "select se.event_id, se.occurred_at, "
    "       split_part(lower(coalesce(se.actor ->> 'email', '')), '@', 2) as sender_domain, "
    "       coalesce((select x.reason_code from event_trace x where x.org_id = se.org_id "
    "                  and x.event_id = se.event_id and x.action = 'drop' "
    "                  order by x.at desc, x.id desc limit 1), 'no trace') as rule "
    "  from source_events se "
    " where se.org_id = :o and se.source = 'gmail' and se.object_type = 'email_message' "
    "   and se.outcome = 'dropped' and position('#resync:' in se.dedup_key) = 0 "
    "   and not exists (select 1 from raw_payloads rp where rp.org_id = se.org_id "
    "                    and rp.event_id = se.event_id and rp.expires_at > :now) "
    "   and not exists (select 1 from event_trace s0 where s0.org_id = se.org_id "
    "                    and s0.event_id = se.event_id and s0.reason_code = 'out_of_scope') "
    " order by se.occurred_at, se.event_id")

#: What the re-sync has done so far: every row it freed, by where it stands.
_SO_FAR = (
    "select case when se.outcome = 'superseded' then 'came back' "
    "            when exists (select 1 from event_trace t where t.org_id = se.org_id "
    "                          and t.event_id = se.event_id and t.stage = 'resync' "
    "                          and t.reason_code = 'resync_not_listed') then 'not listed' "
    "            else 'freed, waiting for the drain' end as state, count(*) as n "
    "  from source_events se "
    " where se.org_id = :o and se.source = 'gmail' and position('#resync:' in se.dedup_key) > 0 "
    " group by 1 order by 1")

#: The attachments of every deleted message: how many were deleted with it, how many survived it.
_ATTACHMENTS = (
    "select m.event_id, "
    "       count(*) filter (where a.outcome = 'dropped') as deleted, "
    "       count(*) filter (where a.outcome in ('emitted', 'parked', 'archived')) as survived "
    "  from source_events m "
    "  join source_events a on a.org_id = m.org_id and a.source = m.source "
    "       and a.object_type = 'email_attachment' and a.parent_object_id = m.source_object_id "
    " where m.org_id = :o and m.source = 'gmail' and m.object_type = 'email_message' "
    "   and m.outcome = 'dropped' "
    "   and not exists (select 1 from raw_payloads rp where rp.org_id = m.org_id "
    "                    and rp.event_id = m.event_id and rp.expires_at > :now) "
    " group by m.event_id")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    add_database_argument(ap)
    ap.add_argument("--org", required=True, help="the one tenant whose deleted mail comes back")
    ap.add_argument("--days", type=int, default=None,
                    help="the window Rohit names (D5 / D16): how far back, in days")
    step = ap.add_mutually_exclusive_group()
    step.add_argument("--apply", action="store_true",
                      help="free the keys of the deleted messages inside --days")
    step.add_argument("--finish", action="store_true",
                      help="after the backfill drain: supersede what came back, report the rest")
    args = ap.parse_args(argv)
    if args.days is not None and args.days < 1:
        ap.error("--days must be a positive number of days")
    if args.apply and args.days is None:
        ap.error("--apply needs --days: the window is Rohit's to name (D5 / D16), never a default")
    return args


def _day(at: datetime) -> str:
    return at.date().isoformat()


def _counts(items) -> str:
    return " · ".join(f"{k or '(none)'} {n}" for k, n in items) or "none"


def _ranked(counter: Counter, top: int | None = None) -> list:
    """Most first, then by name — the same order on every run."""
    return sorted(counter.items(), key=lambda kv: (-kv[1], str(kv[0])))[:top]


def census(conn, org: str, *, now: datetime, days: int | None) -> list[str]:
    """The dry run's lines. Reads the ledger only; names domains and dates, never a mail's words."""
    from genios_engine.capture.landing.resync import window_days

    rows = conn.execute(sql(_DELETED), {"o": org, "now": now}).fetchall()
    so_far = {r.state: int(r.n) for r in conn.execute(sql(_SO_FAR), {"o": org})}
    attachments = conn.execute(sql(_ATTACHMENTS), {"o": org, "now": now}).fetchall()
    window = window_days(conn, org)
    lines = [f"{org}: {len(rows)} Gmail message(s) the old gate deleted, with no content, not freed"]
    if rows:
        oldest = _aware(min(r.occurred_at for r in rows))
        needed = max(1, math.ceil((now - oldest).total_seconds() / 86400))
        lines += [
            f"  oldest {_day(oldest)} — a window of {needed} days reaches every one",
            f"  by rule:   {_counts(_ranked(Counter(r.rule for r in rows)))}",
            f"  by month:  "
            f"{_counts(sorted(Counter(_aware(r.occurred_at).strftime('%Y-%m') for r in rows).items()))}",
            f"  by sender domain (top {TOP_DOMAINS}): "
            f"{_counts(_ranked(Counter(r.sender_domain for r in rows), TOP_DOMAINS))}",
        ]
        if days is not None:
            since = now - timedelta(days=days)
            left = [r for r in rows if _aware(r.occurred_at) < since]
            lines.append(f"  --days {days} reaches {len(rows) - len(left)} and leaves out {len(left)}"
                         + (f", the oldest {_day(_aware(left[0].occurred_at))}" if left else ""))
    lines.append(f"  the Gmail connection's window today: {window} days"
                 + (f" — PATCH /connections/{{gmail}}/backfill-window to {days} before the drain"
                    if days is not None and days > window else ""))
    deleted = sum(int(a.deleted) for a in attachments)
    survived = sum(int(a.survived) for a in attachments)
    split = sum(1 for a in attachments if int(a.deleted) and int(a.survived))
    lines.append(f"  attachments of deleted messages: {deleted} deleted with their message (they come "
                 f"back with it) · {survived} survived it (not landed twice) · {split} message(s) "
                 "with both (their deleted attachments do not come back)")
    lines.append("  re-sync so far: " + (" · ".join(f"{k} {v}" for k, v in sorted(so_far.items()))
                                         or "nothing freed yet"))
    return lines


def _aware(at: datetime) -> datetime:
    return at if at.tzinfo is not None else at.replace(tzinfo=timezone.utc)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    purpose = ("free the keys of a tenant's deleted Gmail mail" if args.apply
               else "finish a tenant's Gmail re-sync" if args.finish
               else "count a tenant's deleted Gmail mail (read-only)")
    url = resolve_database_url(args, purpose=purpose)
    from genios_engine.capture.landing import resync
    from genios_engine.platform.db import get_engine

    engine = get_engine(url)
    now = datetime.now(timezone.utc)
    if args.apply:
        freed = resync.free_deleted(engine, args.org, days=args.days, now=now)
        with engine.connect() as c:
            window = resync.window_days(c, args.org)
        print(f"FREED {freed} deleted Gmail message(s) from the last {args.days} days — each row "
              "stays `dropped` until its message lands again")
        if window < args.days:
            print(f"  ⚠ the Gmail connection's window is {window} days: PATCH "
                  f"/connections/{{gmail}}/backfill-window to {args.days} first, or the drain will "
                  f"not list the mail older than {window} days")
        print("Next: POST /connections/{gmail}/backfill — then --finish")
        return 0
    if args.finish:
        done = resync.finish(engine, args.org, now=now)
        print(f"FINISHED: {done.superseded} came back and were superseded; {done.not_listed} freed "
              f"message(s) not listed ({done.outside_window} older than the connection's "
              f"{done.window_days}-day window; the rest Gmail no longer lists, or the drain has "
              f"not reached yet); {done.newly_reported} reason(s) written now")
        print("Next: re-run the backfill while it says TRUNCATED and --finish again; then "
              "scripts/pipeline_health.py")
        return 0
    conn = read_only_connection(engine)
    try:
        for line in census(conn, args.org, now=now, days=args.days):
            print(line)
    finally:
        conn.close()
    print("DRY RUN — nothing written. Next, with Rohit's window: --apply --days N")
    return 0


if __name__ == "__main__":       # pragma: no cover - operator entry point
    raise SystemExit(main())
