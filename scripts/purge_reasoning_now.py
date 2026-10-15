#!/usr/bin/env python3
"""Free the space the reasoning audit trail is holding, right now, without waiting for a deploy.

WHY THIS IS NEEDED AT ALL. The purge already runs on the maintenance heartbeat
(`api/routes.py` → `reason.retention.purge_expired_reasoning`). But the heartbeat needs the
database, and on 15 Oct 2026 the database is exactly what is unreachable: at 1,324 MB against a
500 MB tier, Supabase's TRANSACTION pooler (`:6543`, which prod's `GENIOS_DATABASE_URL` points at)
answers every checkout with `ECHECKOUTTIMEOUT after 60000ms`, so device sign-in hangs and the
heartbeat cannot run either. The SESSION pooler (`:5432`) is unaffected. This script lets an
operator drain the backlog through that working port while prod is still pointed at the broken one
— which is the only order that works, because freeing space is what lets the rest recover.

WHAT IT DELETES, AND WHAT IT CANNOT. Exactly what the heartbeat would: aged reasoning runs that NO
signal references, with their candidates, checks, results and outputs following by cascade. A run
under a live card is protected twice — by the `not exists` in the statement and, underneath it, by
`ON DELETE NO ACTION` foreign keys from `signals` that make Postgres refuse the delete however this
is called. See `reason/retention.py` for the full argument; this script adds no new rule, it only
chooses the moment.

MEASURED on prod the day this was written, 5,740 runs in the family:

    KEEP_DAYS=7 (the old default)  →    311 purgeable  (~58 MB)
    KEEP_DAYS=3                   →  4,530 purgeable  (~849 MB)
    KEEP_DAYS=2 (the new default) →  5,175 purgeable  (~970 MB)

THIS BUYS TIME, IT IS NOT THE FIX. The lane writes ~800 runs a day on one org with no real users,
at 192 KB a run, so whatever this clears comes back in about a week. The fix is to stop storing a
per-evaluator check for every losing candidate.

Dry run first — it prints what it would free and changes nothing:

    GENIOS_TARGET_DATABASE_URL="<session pooler url, port 5432>" \\
      python scripts/purge_reasoning_now.py

Then, deliberately:

    GENIOS_TARGET_DATABASE_URL="<same>" GENIOS_ALLOW_PROD_WRITE=1 \\
      python scripts/purge_reasoning_now.py --apply
"""
from __future__ import annotations

import argparse
import os
import sys

from sqlalchemy import create_engine, text

sys.path.insert(0, __file__.rsplit("/", 2)[0])
from scripts._db import add_database_argument, resolve_database_url  # noqa: E402

#: Average bytes a single run costs across the whole `reasoning_*` family, measured on prod
#: (1,074 MB / 5,740 runs). Used only to turn a row count into a number an operator can act on.
KB_PER_RUN = 192


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    add_database_argument(ap)
    ap.add_argument("--apply", action="store_true",
                    help="actually delete; without it the script only reports")
    ap.add_argument("--keep-days", type=int, default=None,
                    help="override the window; defaults to reason.retention.KEEP_DAYS")
    a = ap.parse_args()

    from genios_engine.reason.retention import KEEP_DAYS, purge_expired_reasoning
    keep = KEEP_DAYS if a.keep_days is None else max(0, a.keep_days)

    # The prod guard is a WRITE guard, so it is asked only when there is a write. A dry run reads
    # three counts and must not need `GENIOS_ALLOW_PROD_WRITE` — making an operator arm the
    # dangerous flag just to LOOK is how the flag stops meaning anything.
    if a.apply:
        url = resolve_database_url(a, purpose="purge the reasoning audit trail")
    else:
        url = getattr(a, "database_url", None) or os.environ.get("GENIOS_TARGET_DATABASE_URL") or ""
        if not url:
            print("Pass --database-url or set GENIOS_TARGET_DATABASE_URL.", file=sys.stderr)
            return 2
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+psycopg://", 1)
    if ":6543/" in url:
        print("!! This is the TRANSACTION pooler, which is the port that is currently failing.\n"
              "   Use the session pooler (:5432) for this script.", file=sys.stderr)
    eng = create_engine(url, connect_args={"connect_timeout": 15, "prepare_threshold": None})

    with eng.connect() as c:
        size_before = c.execute(text(
            "select pg_size_pretty(pg_database_size(current_database()))")).scalar()
        total = c.execute(text("select count(*) from reasoning_runs")).scalar()
        purgeable = c.execute(text(
            "select count(*) from reasoning_runs rr "
            f"where rr.started_at < now() - interval '{int(keep)} days' "
            "and not exists (select 1 from signals s "
            "                where s.org_id = rr.org_id and s.reasoning_run_id = rr.run_id)"
        )).scalar()

    print(f"database now      : {size_before}")
    print(f"reasoning_runs    : {total:,}")
    print(f"purgeable at {keep}d   : {purgeable:,}  (~{purgeable * KB_PER_RUN / 1024:.0f} MB)")
    print(f"will remain       : {total - purgeable:,}")

    if not a.apply:
        print("\nDry run. Nothing was deleted. Add --apply (with GENIOS_ALLOW_PROD_WRITE=1) to do it.")
        return 0
    if purgeable == 0:
        print("\nNothing aged past the window. Not the backlog — the write RATE is the problem.")
        return 0

    # `max_batches` high enough to clear this backlog in one command; the function still works in
    # bounded batches internally so no single statement holds a long lock.
    print("\npurging…")
    out = purge_expired_reasoning(eng, keep_days=keep, max_batches=200)
    print(f"  {out}")

    with eng.connect() as c:
        after = c.execute(text(
            "select pg_size_pretty(pg_database_size(current_database()))")).scalar()
        left = c.execute(text("select count(*) from reasoning_runs")).scalar()
    print(f"\ndatabase now      : {after}   (was {size_before})")
    print(f"reasoning_runs    : {left:,}")
    print("\nNOTE: space is freed for reuse inside Postgres but the file does not shrink without a\n"
          "VACUUM FULL, which locks the table. Supabase bills on the reported size, so if the\n"
          "tier is still over, run `vacuum (full, analyze) reasoning_reasoner_results;` and the\n"
          "other reasoning_* tables one at a time, off-peak.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
