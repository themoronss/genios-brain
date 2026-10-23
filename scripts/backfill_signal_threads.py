#!/usr/bin/env python3
"""Give every stored signal the thread its mail was captured in (G012 H-02, the rows written before it).

    python scripts/backfill_signal_threads.py --database-url <url> --org <ORG>            # dry run: counts
    python scripts/backfill_signal_threads.py --database-url <url> --org <ORG> --apply    # writes

Until H-02, `capture/esqe/publisher._row_for` stored no `thread_key`, `direction`, `turn_index`, `thread_depth` or
`ball_in_court` (design partner, 23 Oct: NULL on 1,383 of 1,383 signals). Layer 2 keys a seed by its thread, so every
such signal's thread split by claim kind. This fills the five columns for the signals already stored, computed by the
SAME function capture runs (`capture/pipeline._thread_context`) over the SAME inputs: the event rebuilt from its stored
payload (`capture/landing/unread.to_raw_object` → `normalize.to_source_event`) and the org's mailbox owner (its
signup address — `api/routes._mailbox_owner_for`). A row whose payload cannot be read is left as it is and counted.

Only rows never filled (`thread_key` and `direction` both NULL) are touched; a second run finds none. Read-only until `--apply`. The target goes
through `scripts/_db.py` (production needs `GENIOS_ALLOW_PROD_WRITE=1`).
"""
from __future__ import annotations

import argparse
import os
import sys
from collections import Counter
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts._db import add_database_argument, resolve_database_url   # noqa: E402

_TODO = (
    "select q.signal_id, se.event_id, se.source, se.object_type, se.source_object_id, se.parent_object_id, "
    "se.internal_kind, se.recipients, se.actor, se.occurred_at, se.connection_id, rp.enc_content "
    "from qualified_signals q "
    "join source_events se on se.org_id = q.org_id and se.event_id = q.event_id "
    "left join raw_payloads rp on rp.org_id = se.org_id and rp.event_id = se.event_id "
    "where q.org_id = :o and q.thread_key is null and q.direction is null")
_SET = (
    "update qualified_signals set thread_key = :tk, direction = :dir, turn_index = :turn, thread_depth = :depth, "
    "ball_in_court = :ball where org_id = :o and signal_id = :s and thread_key is null and direction is null")


def parse_args(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    add_database_argument(ap)
    ap.add_argument("--org", required=True)
    ap.add_argument("--apply", action="store_true", help="write (default: a dry run that counts)")
    ap.add_argument("--crypto-key", default=os.environ.get("GENIOS_CRYPTO_KEY", ""),
                    help="the key the payloads are stored under (default: GENIOS_CRYPTO_KEY)")
    return ap.parse_args(argv)


def context_for(row, crypto_key: str, org_id: str, owner: str | None):
    """The capture-time ThreadContext for one stored signal's event, or None when its payload is unreadable."""
    from genios_engine.capture.landing.normalize import to_source_event
    from genios_engine.capture.landing.unread import to_raw_object
    from genios_engine.capture.pipeline import _thread_context
    raw = to_raw_object(SimpleNamespace(**dict(row._mapping), reason_code=None), crypto_key)
    if raw is None:
        return None
    event = to_source_event(raw, org_id=org_id, connection_id=row.connection_id, mailbox_owner=owner)
    return _thread_context(event, raw.raw, owner)


def main(argv=None) -> int:
    args = parse_args(argv)
    from sqlalchemy import create_engine, text
    url = resolve_database_url(args, purpose="backfill the thread of stored signals")
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+psycopg://", 1)
    engine = create_engine(url, connect_args={"prepare_threshold": None})
    with engine.connect() as c:
        owner = c.execute(text("select email from orgs where id = :o"), {"o": args.org}).scalar()
        rows = c.execute(text(_TODO), {"o": args.org}).fetchall()
    counts, updates = Counter(), []
    for row in rows:
        ctx = context_for(row, args.crypto_key, args.org, owner)
        if ctx is None:
            counts["payload_unreadable"] += 1
            continue
        counts["threaded" if ctx.thread_key else "no_thread"] += 1
        counts[f"direction={ctx.direction}"] += 1
        updates.append({"o": args.org, "s": row.signal_id, "tk": ctx.thread_key, "dir": ctx.direction,
                        "turn": ctx.turn_index, "depth": ctx.thread_depth,
                        "ball": getattr(ctx.ball_in_court, "value", ctx.ball_in_court)})
    print(f"signals with no thread: {len(rows)} | {dict(counts)}")
    if not args.apply:
        print("dry run — nothing written (add --apply)")
        return 0
    written = 0
    with engine.begin() as c:
        for u in updates:
            written += c.execute(text(_SET), u).rowcount or 0
    print(f"written: {written}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
