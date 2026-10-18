"""Put the attachments the `file_name` refusal dead-lettered back on the refetch ladder — only those.

    python scripts/requeue_refused_attachments.py --org <org_id> --database-url postgresql://…          # dry run
    python scripts/requeue_refused_attachments.py --org <org_id> --database-url postgresql://… --apply  # writes

**What went wrong (STEP-18 B19).** Composio's `GMAIL_GET_ATTACHMENT` requires `file_name`
(toolkit 20260915_00) and the connector did not send it, so every attachment fetch was refused —
at capture, where the refusal became an empty stub parked under DOC-02 / DOC-05, and on every
refetch, where the ladder retried it five times and dead-lettered it. On the design partner's org,
2026-10-05: 88 of 88 stored errors were that refusal, 50 dead-lettered, 0 recovered. The
connector now sends the field (yc2_w27/M17.C3.U02). A dead letter is terminal and will not retry
on its own; this script is the way back for exactly the rows the refusal killed.

**What it touches.** One tenant (`--org` is required). Gmail attachment parks (`DOC-*`) whose
status is `dead_letter` and whose stored error names the refusal. Each goes back to `pending` with
its attempts reset and its next attempt now; the old error is kept, prefixed, so the row still
says why it was dead once. Nothing else is read or written.

**Read-only until `--apply`,** and run AFTER the connector fix is deployed — re-queued before it,
each row would be refused five more times and dead-lettered again. The target is resolved through
`scripts/_db.py`, which has no fallback to the application's own database and requires
`GENIOS_ALLOW_PROD_WRITE=1` for a production host.
"""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts._db import add_database_argument, resolve_database_url   # noqa: E402

#: The refusal, as it stands in every stored error the old connector produced.
REFUSAL_MARK = "Missing required fields: file_name"

SELECT = (
    "select event_id from parked_events "
    " where org_id = :org and source = 'gmail' and reason_code like 'DOC-%' "
    "   and status = 'dead_letter' and refetch_last_error like :refusal "
    " order by created_at")

UPDATE = (
    "update parked_events set status = 'pending', refetch_attempts = 0, "
    "       refetch_next_attempt_at = now(), refetch_failure_kind = null, "
    "       refetch_last_error = 'requeued after the file_name fix (B19); was: ' "
    "                            || coalesce(refetch_last_error, '') "
    " where org_id = :org and event_id = :event and status = 'dead_letter' "
    "   and refetch_last_error like :refusal")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description=__doc__)
    add_database_argument(ap)
    ap.add_argument("--org", required=True, help="the one tenant whose dead letters go back")
    ap.add_argument("--apply", action="store_true",
                    help="write (default is a read-only dry run that only counts)")
    return ap.parse_args(argv)


def requeue(engine, org_id: str, *, apply: bool) -> int:
    """How many rows the refusal dead-lettered for this tenant — re-queued when `apply`."""
    from sqlalchemy import text

    refusal = f"%{REFUSAL_MARK}%"
    with engine.connect() as conn:
        conn.execute(text("set transaction read only"))
        events = [r.event_id for r in conn.execute(
            text(SELECT), {"org": org_id, "refusal": refusal}).fetchall()]
    if not apply or not events:
        return len(events)
    written = 0
    with engine.begin() as conn:
        for event_id in events:
            written += conn.execute(text(UPDATE), {"org": org_id, "event": event_id,
                                                   "refusal": refusal}).rowcount
    return written


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    url = resolve_database_url(args, purpose="re-queue attachment parks the file_name refusal "
                                             "dead-lettered")
    from genios_engine.platform.db import get_engine
    n = requeue(get_engine(url), args.org, apply=args.apply)
    if args.apply:
        print(f"re-queued {n} dead-lettered attachment park(s) for {args.org}")
    else:
        print(f"DRY RUN — nothing written. {n} dead-lettered attachment park(s) for {args.org} "
              "name the file_name refusal. Re-run with --apply, after the connector fix is "
              "deployed.")
    return 0


if __name__ == "__main__":       # pragma: no cover - operator entry point
    raise SystemExit(main())
