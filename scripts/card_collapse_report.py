#!/usr/bin/env python3
"""L2-7-U0 · how many cards the founder sees, and how many situations they are about — read-only.

    python scripts/card_collapse_report.py --org <org_id> --database-url <url>

⛔ **THE RATIO IS THE HEADLINE NUMBER OF THE WHOLE LAYER 2 PLAN.** The step file: *"38 cards
becoming N is the claim, and it must be measured rather than asserted."*

The fan-out is at the RULE, not the signal: `domain_shadow._emit_capability_signal` writes one
open signal per `(pack, rule, node)`, so one situation that fires three rules becomes three cards —
*"Nitesh's inbound messages dropping"*, *"Nitesh Pant's touch frequency declining"*, *"Check in
with Nitesh Pant"*.

⛔ **`situation_id` IS NULL UNTIL MIGRATION 0182 IS APPLIED**, and every signal written before it
reads NULL. This report says so plainly rather than reporting a collapse of 1.00 and letting
somebody conclude there is nothing to collapse.

READ-ONLY, AND STRUCTURALLY SO — through `scripts/_db.py`, which has no fallback to `Settings`,
and every statement here is a `select`.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts._db import add_database_argument, resolve_database_url  # noqa: E402

_HAS_COLUMN = """
select count(*) as n from information_schema.columns
 where table_name = 'signals' and column_name = 'situation_id'
"""

_COLLAPSE = """
select coalesce(s.situation_id, '(uninterpreted)') as situation,
       count(*) as signals,
       count(distinct s.rule_id) as rules,
       min(s.subject_node_id) as node
  from signals s
  left join cards k on k.org_id = s.org_id and k.signal_id = s.signal_id
       and k.state not in ('expired','dismissed')
 where s.org_id = :org and s.status = 'open' and k.card_id is null
 group by coalesce(s.situation_id, '(uninterpreted)')
 order by count(*) desc
"""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--org", required=True)
    add_database_argument(parser)
    args = parser.parse_args()

    url = resolve_database_url(args, purpose="L2-7 card collapse report (read-only)")

    from sqlalchemy import create_engine, text

    engine = create_engine(url)
    with engine.connect() as conn:
        has_column = int(conn.execute(text(_HAS_COLUMN)).scalar_one() or 0)
        if not has_column:
            print("⛔ `signals.situation_id` does not exist — migration 0182 is not applied.")
            print("   Every open signal would report as uninterpreted, and a collapse of 1.00")
            print("   would read as 'there is nothing to merge'. That is not a measurement.")
            return 2
        rows = [dict(r._mapping) for r in conn.execute(text(_COLLAPSE), {"org": args.org})]

    signals = sum(int(r["signals"]) for r in rows)
    interpreted = [r for r in rows if r["situation"] != "(uninterpreted)"]
    dark = sum(int(r["signals"]) for r in rows if r["situation"] == "(uninterpreted)")
    cards_after = len(interpreted) + dark        # ⛔ one card per situation, PLUS one per
                                                 # uninterpreted signal — never fewer, because
                                                 # "fewer cards must come from merging, never
                                                 # from dropping".

    print("LAYER 2 · WHAT THE FOUNDER SEES, AND WHAT IT IS ABOUT")
    print("=" * 66)
    print(f"  open signals without a card          {signals:>6}     ← cards today")
    print(f"  situations they belong to            {len(interpreted):>6}")
    print(f"  signals with no situation            {dark:>6}     ← surfaced, labelled")
    print("-" * 66)
    print(f"  cards after the collapse             {cards_after:>6}")
    if signals:
        print(f"  collapse                              {signals / max(cards_after, 1):>6.2f}×")
    print()
    print("  THE WIDEST FAN-OUTS  (one situation, many rules → many cards today)")
    print("-" * 66)
    for row in interpreted[:12]:
        print(f"  {str(row['situation'])[:34]:<34}{int(row['signals']):>4} signals"
              f"  {int(row['rules']):>3} rules")
    if dark:
        print()
        print(f"  ⛔ {dark} open signal(s) carry no situation. They are NOT dropped: "
              f"`card_source`")
        print("     labels them UNINTERPRETED — a measurement, not a conclusion — so a "
              "correlator")
        print("     gap shows up as a labelled card rather than as a card that never appeared.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
