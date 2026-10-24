#!/usr/bin/env python3
"""Make every OPEN evidence need name what Layer 1 can fetch, before the fetchers are armed (G012 H-20).

    python scripts/reframe_open_needs.py --database-url <url> --org <ORG>            # dry run: counts
    python scripts/reframe_open_needs.py --database-url <url> --org <ORG> --apply    # writes

A closed need never reopens (`context/evidence_need_store`), and the queue filed before H-20 would have closed almost
whole the first time `GENIOS_NEED_FETCHERS=on` worked it (design partner, local copy, 24 Oct: 336 open): a graph
thread node where Gmail wants its thread id, a meeting or a person where a fetch wants a thread or a party, and the
sources that would settle it in the model's prose where the executor compares a source name. RUN THIS FIRST, then the
one fetch by hand (`04-FOR-HARSH.md` E2), then arm.

Each open need gets the subject `context/need_subjects.resolve_subject` gives it — for an L2 need, judged as part of the
file its judgment was about (`reasoning_results.request_id` = the need's `trace_id`) — and, for an L2 need, the source
names among its sources (`reason/l2/evidence.source_names`). The question is never touched; only `open` rows change.
Read-only until `--apply`. The target goes through `scripts/_db.py` (production needs `GENIOS_ALLOW_PROD_WRITE=1`).
"""
from __future__ import annotations

import argparse
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts._db import add_database_argument, resolve_database_url   # noqa: E402

_OPEN = (
    "select e.need_id, e.org_id, e.trace_id, e.question, e.why_it_matters, e.subject_ref, e.acceptable_sources, "
    "       e.unacceptable_sources, e.window_from, e.window_to, e.max_cost_usd, e.expires_at, r.subject_ref as judged "
    "  from evidence_needs e "
    "  left join lateral (select subject_ref from reasoning_results r where r.org_id = e.org_id "
    "                      and r.request_id = e.trace_id limit 1) r on true "
    " where e.org_id = :o and e.state = 'open' order by e.created_at")


def parse_args(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    add_database_argument(ap)
    ap.add_argument("--org", required=True)
    ap.add_argument("--apply", action="store_true", help="write (default: a dry run that counts)")
    return ap.parse_args(argv)


def reframed(conn, row):
    """The need as it would be filed today, from its stored row."""
    from genios_engine.context.evidence_needs import DEFAULT_UNACCEPTABLE
    from genios_engine.context.need_subjects import fetchable
    from genios_engine.contracts.evidence import EvidenceNeed
    from genios_engine.reason.l2.evidence import NEED_PREFIX, source_names
    need = EvidenceNeed(need_id=row.need_id, org_id=row.org_id, trace_id=row.trace_id, question=row.question,
                        why_it_matters=row.why_it_matters, subject_ref=row.subject_ref,
                        acceptable_sources=tuple(row.acceptable_sources or ()),
                        unacceptable_sources=tuple(row.unacceptable_sources or ()),
                        window_from=row.window_from, window_to=row.window_to, max_cost_usd=row.max_cost_usd,
                        expires_at=row.expires_at)
    judged = str(row.judged or "")
    need = fetchable(conn, row.org_id, need, file_id=judged.split(":", 1)[1] if judged.startswith("file:") else None)
    if str(row.need_id).startswith(NEED_PREFIX):
        acceptable = source_names(need.acceptable_sources)
        unacceptable = tuple(s for s in dict.fromkeys((*DEFAULT_UNACCEPTABLE, *source_names(need.unacceptable_sources)))
                             if s not in acceptable)
        need = need.model_copy(update={"acceptable_sources": acceptable, "unacceptable_sources": unacceptable})
    return need


def main(argv=None) -> int:
    args = parse_args(argv)
    from sqlalchemy import create_engine, text
    from genios_engine.capture.acquire.evidence_need import plan_fetch
    from genios_engine.context.evidence_need_store import reframe_open
    url = resolve_database_url(args, purpose="reframe the open evidence needs")
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+psycopg://", 1)
    engine = create_engine(url, connect_args={"prepare_threshold": None})
    counts: Counter = Counter()
    changed = []
    with engine.connect() as c:
        rows = c.execute(text(_OPEN), {"o": args.org}).fetchall()
        for row in rows:
            need = reframed(c, row)
            before = plan_fetch(need.model_copy(update={"subject_ref": row.subject_ref})) or "no fetch"
            counts[f"{before} -> {plan_fetch(need) or 'no fetch'}"] += 1
            if (need.subject_ref, list(need.acceptable_sources), list(need.unacceptable_sources)) != \
                    (row.subject_ref, list(row.acceptable_sources or ()), list(row.unacceptable_sources or ())):
                changed.append(need)
    print(f"open needs: {len(rows)} | would change: {len(changed)}")
    for k, v in sorted(counts.items(), key=lambda kv: -kv[1]):
        print(f"  {v:4}  {k}")
    if not args.apply:
        print("dry run — nothing written (add --apply)")
        return 0
    with engine.begin() as c:
        written = sum(reframe_open(c, n) for n in changed)
    print(f"written: {written}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
