#!/usr/bin/env python3
r"""⛔ Every fact path a reasoning unit binds — and whether anything in the product writes it.

READ-ONLY. One `set transaction read only` connection, no writes, no model calls.

WHY THIS EXISTS. Measured 2026-10-01: `expertise._ROSTER` binds **22** fact paths and **14 have zero
rows** in `graph_facts`. One root, fourteen symptoms — there is no CRM connector, so the deal object
barely exists:

    present    thread.last_outbound 206 · thread.last_inbound 198 · derived.engagement 174
               derived.momentum 174 · meeting.start_at 49 · deal.last_inbound 34
               commitment.due_at 30 · deal.status 3
    absent     every deal.* beyond those two, all five approval gates, both consent fields,
               calendar.next_meeting_at, schedule.quiet_until

⛔ WHAT IT EXPLAINS. `core.policy` has skipped on all 165 of its rows with
`no_declared_input_available`, and **all four of its essential fields are in the absent list.** It is
not failing; it is correctly refusing to run on nothing, forever.

⛔ AND THIS IS WHAT `no_declared_input_available` CANNOT SAY. That reason conflates two facts with
different movers:

    "this situation did not carry the field"      -> data coverage. A sync, a backfill.
    "nothing has ever written the field anywhere" -> a connector that does not exist.

The second is not fixable by looking at the situation at all, and it is the true one here.

⛔ THE PATH LIST IS DERIVED FROM `_ROSTER`, never copied. A seventh role added to a unit appears in
this census without an edit — the rule `S5.U02` established for `AXIS_SOURCES`, one level up.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text                                              # noqa: E402

from genios_engine.platform.db import get_engine                         # noqa: E402
from genios_engine.reason.unit_health import (                           # noqa: E402
    DECLARED_UNWRITTEN, roster_fact_paths, undeclared_unwritten, written_after_all,
)


def main() -> int:
    url = os.environ.get("GENIOS_DATABASE_URL")
    if not url:
        print("GENIOS_DATABASE_URL is not set — nothing to measure.")
        return 2

    bound = roster_fact_paths()
    engine = get_engine(url)
    with engine.connect() as conn:
        # ⛔ READ ONLY, FIRST STATEMENT. A census may never change what it is counting.
        conn.execute(text("set transaction read only"))
        counts = {field: int(n) for field, n in conn.execute(text(
            "select field, count(*) from graph_facts group by field")).all()}

    print("=" * 96)
    print("FACT-WRITER CENSUS — every path the roster binds, and whether anything writes it")
    print("=" * 96)
    print(f"\n  {'fact path':<30}{'rows':>8}  {'state':<12} bound by")
    print("  " + "-" * 92)
    for path, binders in bound.items():
        rows = counts.get(path, 0)
        if rows:
            state = "written"
            mark = "   "
        elif path in DECLARED_UNWRITTEN:
            state = "declared"
            mark = "   "
        else:
            state = "⛔ UNDECLARED"
            mark = "⛔ "
        print(f"  {mark}{path:<27}{rows:>8}  {state:<12} {', '.join(binders)[:40]}")

    written = sum(1 for p in bound if counts.get(p, 0))
    print(f"\n  bound: {len(bound)}   written: {written}   empty: {len(bound) - written}   "
          f"declared: {len(DECLARED_UNWRITTEN)}")

    print("\n" + "=" * 96)
    new = undeclared_unwritten(counts)
    recovered = written_after_all(counts)
    if new:
        print("⛔ BOUND PATHS WITH NO WRITER AND NO DECLARATION:")
        for path in new:
            print(f"      {path:<30} bound by {', '.join(bound[path])}")
        print("\n   Each one is a unit role that can never bind. Declare it in")
        print("   reason/unit_health.DECLARED_UNWRITTEN with a reason, a MOVER and its binders —")
        print("   or find out what stopped writing it.")
    if recovered:
        print("✅ DECLARED-UNWRITTEN PATHS THAT NOW CARRY ROWS — update the declaration:")
        for path in recovered:
            print(f"      {path:<30} now {counts.get(path, 0)} rows "
                  f"(declared empty on {DECLARED_UNWRITTEN[path].measured_on})")
    if not new and not recovered:
        print("Every empty bound path is declared. The movers, grouped:\n")
        movers: dict[str, list[str]] = {}
        for path, fact in sorted(DECLARED_UNWRITTEN.items()):
            movers.setdefault(fact.mover, []).append(path)
        for mover, paths in sorted(movers.items()):
            print(f"   {mover}")
            print(f"      {len(paths)} path(s): {', '.join(paths)}")
    print("=" * 96)
    return 1 if new else 0


if __name__ == "__main__":
    raise SystemExit(main())
