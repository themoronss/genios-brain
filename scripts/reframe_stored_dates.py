"""Re-frame the dates a late read stored — `03` F148's half already in the database. A dry run unless told.

    python scripts/reframe_stored_dates.py --org <org_id> --database-url postgresql://…          # dry run
    … --apply                     # rewrite only the late-framed dates; print each event id

**Why.** Until `yc2_w27_align` M34.C2 U13/U14, Layer 1 resolved a mail's "by Friday", "this week",
"next week" against the clock of the sync that READ it, not the day it was written (`03` F148). Live
mail is read within minutes; a first connect, a sync after downtime and STEP-08's history re-sync read
it weeks or months late, so every relative date in that mail is off by the gap — and a stored answer is
reused as it is (the extraction cache key carries no clock). The fix makes new reads right; this
re-frames what late reads already stored: each `dates_mentioned` entry and each commitment's `due` in
`l1_extraction_results.output` whose frame (`resolved_against`) is more than `--gap-hours` after its
mail's own time is resolved again by ALG-09 (`capture/validate/dates.resolve_date`), against that time,
from the words the model quoted (`as_written`) and in the org's zone. Nothing else in the row moves.

**Then** the graph has to read them: STEP-09's re-filing (`08` §3.8 — `scripts.rebuild_graph`, then the
correlation rebuild) carries the corrected dates into `commitment.due_at` and every fact made from them.

**What it reads and writes.** The dry run reads through a read-only transaction and prints counts by the
month of the mail — rows, dates and promises it would re-frame — never a mail's words, not even the date
phrase. `--apply` rewrites only those rows' `output`, in one transaction, and names each event; run
again, it finds nothing. The target goes through `scripts/_db.py`: no fallback to the application's
database, and `GENIOS_ALLOW_PROD_WRITE=1` for a production host.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts._db import add_database_argument, resolve_database_url   # noqa: E402
from scripts._gate import read_only_connection, sql                   # noqa: E402

#: How far after its mail a frame must be to count as a late read: a mail read within the day was
#: read as it arrived, and its dates are its writer's.
GAP_HOURS = 24

#: L1's own extractions (`profile_id` set — L2's legacy cache rows carry none), with their mail's time.
_ROWS = ("select x.processing_key, x.event_id, x.output, se.occurred_at "
         "  from l1_extraction_results x "
         "  join source_events se on se.org_id = x.org_id and se.event_id = x.event_id "
         " where x.org_id = :o and x.profile_id is not null "
         " order by se.occurred_at, x.processing_key")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    add_database_argument(ap)
    ap.add_argument("--org", required=True, help="org_id whose stored dates to re-frame")
    ap.add_argument("--apply", action="store_true", help="rewrite the late-framed dates")
    ap.add_argument("--gap-hours", type=int, default=GAP_HOURS,
                    help=f"how late a read must be to re-frame (default {GAP_HOURS})")
    return ap.parse_args(argv)


def _aware(at: datetime) -> datetime:
    return at if at.tzinfo is not None else at.replace(tzinfo=timezone.utc)


def _instant(value) -> datetime | None:
    if not value:
        return None
    return _aware(datetime.fromisoformat(str(value).replace("Z", "+00:00")))


def reframed(date: dict, written: datetime, tz: str) -> dict | None:
    """One stored date, re-resolved against when its mail was written — or None when it was not
    framed late, or ALG-09 cannot read it again (then it is left exactly as stored)."""
    from genios_engine.capture.validate.dates import resolve_date
    from genios_engine.contracts.evidence import EvidenceSpan

    frame = _instant(date.get("resolved_against"))
    if frame is None or not date.get("as_written"):
        return None
    evidence = [EvidenceSpan(**span) for span in date.get("evidence") or ()]
    try:
        again = resolve_date(str(date["as_written"]), eval_time=written, tz=tz, evidence=evidence)
    except (TypeError, ValueError):
        return None
    return again.model_dump(mode="json")


def plan(rows, *, tz: str, gap: timedelta) -> list[tuple[str, str, datetime, dict, int, int]]:
    """Each stored output with a late-framed date: (processing key, event, mail time, new output,
    dates re-framed, promises re-framed)."""
    out = []
    for r in rows:
        written = _aware(r.occurred_at)
        output = r.output if isinstance(r.output, dict) else json.loads(r.output)
        dates = promises = 0
        new = json.loads(json.dumps(output))
        for i, date in enumerate(new.get("dates_mentioned") or ()):
            frame = _instant(date.get("resolved_against"))
            if frame is not None and frame - written > gap:
                again = reframed(date, written, tz)
                if again is not None:
                    new["dates_mentioned"][i] = again
                    dates += 1
        for commitment in new.get("commitments") or ():
            due = commitment.get("due")
            frame = _instant(due.get("resolved_against")) if isinstance(due, dict) else None
            if frame is not None and frame - written > gap:
                again = reframed(due, written, tz)
                if again is not None:
                    commitment["due"] = again
                    promises += 1
        if dates or promises:
            out.append((r.processing_key, r.event_id, written, new, dates, promises))
    return out


def _zone(conn, org: str) -> str:
    return str(conn.execute(sql("select timezone from orgs where id = :o"), {"o": org}).scalar()
               or "UTC")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    purpose = ("re-frame a tenant's late-read dates" if args.apply
               else "count a tenant's late-read dates (read-only)")
    url = resolve_database_url(args, purpose=purpose)
    from genios_engine.platform.db import get_engine
    engine = get_engine(url)
    gap = timedelta(hours=args.gap_hours)
    if args.apply:
        with engine.begin() as c:
            todo = plan(c.execute(sql(_ROWS), {"o": args.org}).fetchall(), tz=_zone(c, args.org),
                        gap=gap)
            for key, event_id, _written, new, _d, _p in todo:
                c.execute(sql("update l1_extraction_results set output = cast(:out as jsonb) "
                              " where org_id = :o and processing_key = :k"),
                          {"out": json.dumps(new, default=str), "o": args.org, "k": key})
        for _key, event_id, written, _new, dates, promises in todo:
            print(f"  {event_id} ({written.date().isoformat()}): {dates} date(s), {promises} promise(s)")
        print(f"REFRAMED {len(todo)} stored extraction(s) — next, re-file the history (08 §3.8) so the "
              "graph reads them")
        return 0
    conn = read_only_connection(engine)
    try:
        todo = plan(conn.execute(sql(_ROWS), {"o": args.org}).fetchall(), tz=_zone(conn, args.org),
                    gap=gap)
    finally:
        conn.close()
    months = Counter(written.strftime("%Y-%m") for _k, _e, written, _n, _d, _p in todo)
    print(f"{args.org}: {len(todo)} stored extraction(s) read more than {args.gap_hours} h after their "
          f"mail — {sum(t[4] for t in todo)} date(s), {sum(t[5] for t in todo)} promise(s) to re-frame")
    print("  by month of the mail: " + (" · ".join(f"{m} {n}" for m, n in sorted(months.items()))
                                        or "none"))
    print("DRY RUN — nothing written. Next: --apply, then re-file the history (08 §3.8)")
    return 0


if __name__ == "__main__":       # pragma: no cover - operator entry point
    raise SystemExit(main())
