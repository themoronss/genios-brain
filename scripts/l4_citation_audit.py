"""Which pack lanes deliver cards that carry no citation — and is each zero explained?

    python scripts/l4_citation_audit.py --org <org> --database-url postgresql://…

THE COUNTING HALF of `reason/uncited_lanes`. That module declares which lanes cannot cite and why;
this one asks the live `signals` table whether the declaration still matches what the tenant
actually publishes. Neither half is sufficient alone: the unit test proves the declaration is
well-formed and cannot rot in either direction, and it runs against no data, so it can never
notice a NEW lane that started delivering uncited cards. Only a read of the tenant can.

THREE VERDICTS, and only the third is a defect:
  CITING      — the lane bound a corpus and its signals quote it.
  DECLARED    — it cited on none AND `UNCITED_LANES` says why, with a measurement and a mover.
  UNEXPLAINED — it cited on none and nothing says why. This is the class that let 72% of one
                tenant's cards ship with no doctrine behind them while the funnel read healthy.

A FOURTH ROW IS REPORTED AND IS NOT A VERDICT: a declared lane that has STARTED citing. Its entry
is now false and must be deleted — the same both-directions rule `context/lane_health` keeps, and
the reason a permanent exception list does not become a record of things that used to be true.

CITATION IS NOT THE SAME QUESTION AS ATTRIBUTION, and this script reports both so they cannot be
confused. `capability_via_run` counts signals whose `reasoning_runs` row carries a capability id —
which is where `reason/authority.AUDITED_CARD_JUDGMENTS_CTES` reads it from, and therefore what
decides whether Layer 7 can calibrate the lane at all. A lane can be uncitable and still fully
attributable; `general` is exactly that, and a reader who saw only the citation column would
conclude the opposite.

READ-ONLY, AND NEVER IMPLICITLY PRODUCTION. `set transaction read only` is the transaction's first
statement (`scripts/_gate.py`) and the target resolves through `scripts/_db.py`, which has no
fallback to the application's configured `database_url`.
"""
from __future__ import annotations

import argparse
import sys

sys.path.insert(0, ".")

from _db import add_database_argument, resolve_database_url          # noqa: E402
from _gate import read_only_connection, sql                          # noqa: E402

from genios_engine.reason.uncited_lanes import (                     # noqa: E402
    UNCITED_LANES, now_citing, undeclared)

_LANES = sql("""
    select coalesce(s.pack_id, '') as lane,
           count(*) as signals,
           count(s.citations) as cited,
           count(rr.capability_id) as capability_via_run,
           count(distinct s.rule_id) as rules,
           count(distinct c.card_id) as cards
    from signals s
    left join reasoning_runs rr on rr.org_id = s.org_id and rr.run_id = s.reasoning_run_id
    left join cards c on c.org_id = s.org_id and c.signal_id = s.signal_id
    where s.org_id = :o
    group by 1 order by 2 desc
""")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--org", required=True)
    add_database_argument(ap)
    args = ap.parse_args()
    url = resolve_database_url(args, purpose="audit Layer 4 citation lanes")

    # `platform.db.get_engine`, not a bare `create_engine`: this codebase runs psycopg3, and
    # SQLAlchemy's default postgresql:// dialect reaches for psycopg2, which is not installed.
    from genios_engine.platform.db import get_engine
    engine = get_engine(url)
    with read_only_connection(engine) as conn:
        rows = conn.execute(_LANES, {"o": args.org}).fetchall()

    if not rows:
        print(f"no signals for {args.org} — nothing to audit")
        return 0

    counts = {row.lane: (int(row.signals), int(row.cited)) for row in rows}
    total_signals = sum(int(row.signals) for row in rows)
    total_cards = sum(int(row.cards) for row in rows)

    print(f"org {args.org} — {total_signals} signals, {total_cards} cards\n")
    header = f"{'lane':<14} {'verdict':<12} {'signals':>8} {'cited':>7} {'attributable':>13} {'cards':>6}"
    print(header)
    print("-" * len(header))
    for row in rows:
        lane = row.lane
        if int(row.cited):
            verdict = "CITING"
        elif lane in UNCITED_LANES:
            verdict = "DECLARED"
        else:
            verdict = "UNEXPLAINED"
        shown = lane or "<no pack>"
        print(f"{shown:<14} {verdict:<12} {row.signals:>8} {row.cited:>7} "
              f"{row.capability_via_run:>13} {row.cards:>6}")

    problems = undeclared(counts)
    stale = now_citing(counts)
    print()
    if problems:
        print("UNEXPLAINED — deliver cards, cite on none, and nothing says why:")
        for lane in problems:
            print(f"   {lane or '<no pack>'}  ({counts[lane][0]} signals)")
        print("   declare each in reason/uncited_lanes.UNCITED_LANES, with a measurement and a")
        print("   MOVES WHEN — or bind it to a corpus.")
    else:
        print("no unexplained lane: every lane either cites or declares why it cannot.")

    if stale:
        print()
        print("STALE DECLARATION — listed as uncitable, but citing now:")
        for lane in stale:
            print(f"   {lane or '<no pack>'}  ({counts[lane][1]} of {counts[lane][0]} cited)")
        print("   delete the entry; the list must not record things that used to be true.")

    return 1 if (problems or stale) else 0


if __name__ == "__main__":
    raise SystemExit(main())
