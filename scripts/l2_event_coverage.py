"""How many of each reading's findings can reach an EVENT — and therefore reach Layer 1.

    python scripts/l2_event_coverage.py --org <org> --database-url postgresql://…

WHY THIS NUMBER AND NOT ANOTHER. `gather_l1_signals` reaches Layer 1's qualified signals through
`context_correlation_members`, and a reading's membership is written by
`context/correlation_membership.declare_finding_events`, which writes NOTHING when the finding
resolves to no event. That is the correct behaviour — inventing membership would let a situation
claim evidence it does not have — and it is completely silent. A finding with no events becomes a
situation that cannot reach Layer 1, which Layer 3 then holds at `qes_required` before its content
is ever examined, and every layer in between reads as healthy.

`scripts/l2_lane_audit.py` asks whether a lane produces at all. This asks the next question down:
of what it produced, how much can be evidenced. A lane can be fully PRODUCING and half unreachable,
which is exactly what the pilot showed.

MEASURED ON THE PILOT 2026-09-16, which is why this exists:

    outreach            14/14      condition      13/13      analytic_movement  12/12
    commitment          14/35      unanswered      5/6        campaign            2/2

The commitment lane is not miswired. Four hypotheses were tested against the database and all four
were wrong: it is not a feedback loop (no reading anchor is read back — the exclusion holds), not a
missing `created_by_event_id` fallback (null on every one of those facts), not the domain-blind
`_reconcile` (no situation_type on this tenant is claimed by two domains), and not an unused edge
receipt (the only edge is Layer 2's own `concerns`, written with the synthetic `state:{org}` event,
which was never evaluated for qualification and never could be). Those 21 promises have no real
event to join, so the hold is right. What was missing is this line.

READ-ONLY, AND IT RUNS THE LAYER'S OWN CODE. `_gather` fills the same rows the sweep fills and
every reading is dispatched exactly as the sweep dispatches it; `finding_events` is the same
function the writer calls. Nothing is re-derived here, so a number this prints is a number the
sweep would produce. `set transaction read only` is the transaction's first statement
(`scripts/_gate.py`) and the target resolves through `scripts/_db.py`.
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone

sys.path.insert(0, ".")

from _db import add_database_argument, resolve_database_url          # noqa: E402
from _gate import read_only_connection                               # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--org", required=True)
    ap.add_argument("--min-coverage", type=int, default=100,
                    help="report a lane below this percent as a gap (default 100)")
    add_database_argument(ap)
    args = ap.parse_args()
    url = resolve_database_url(args, purpose="audit Layer 2 event coverage")

    # `platform.db.get_engine`, not a bare `create_engine`: this codebase runs psycopg3, and
    # SQLAlchemy's default postgresql:// dialect reaches for psycopg2, which is not installed.
    from genios_engine.platform.db import get_engine
    from genios_engine.context.graph_store import GraphStore
    from genios_engine.context import outreach_situations as O
    from genios_engine.context.correlation_membership import finding_events

    engine = get_engine(url)
    store = GraphStore(engine=engine)
    now = datetime.now(timezone.utc)
    held, _counts, employers = O._gather(store, args.org, now=now)

    header = f"{'reading':<22} {'findings':>9} {'with an event':>14} {'coverage':>9}"
    print(f"org {args.org}\n")
    print(header)
    print("-" * len(header))

    gaps: list[tuple[str, int, int]] = []
    for anchor, reader in O.READINGS:
        findings = reader(held, now, employers)
        if not findings:
            # Silence is `context/lane_health.DORMANT_LANES`' question, not this one. Printing a
            # 0/0 lane here as a coverage gap would put two different failures under one name.
            print(f"{anchor:<22} {0:>9} {'-':>14} {'(dormant)':>9}")
            continue
        with read_only_connection(engine) as conn:
            reached = sum(1 for f in findings
                          if finding_events(conn, org_id=args.org, finding=f))
        pct = round(100 * reached / len(findings))
        print(f"{anchor:<22} {len(findings):>9} {reached:>14} {pct:>8}%")
        if pct < args.min_coverage:
            gaps.append((anchor, reached, len(findings)))

    print()
    if not gaps:
        print("every producing lane can evidence every finding it made.")
        return 0

    print("LANES WHOSE FINDINGS CANNOT ALL REACH LAYER 1:")
    for anchor, reached, total in gaps:
        print(f"   {anchor}: {total - reached} of {total} findings resolve to no event")
    print("   Those situations are held at `qes_required` and the hold is correct — membership")
    print("   must never be invented. Close the gap in Layer 1 (an event that was never")
    print("   evaluated for qualification) or declare it; do not write membership without one.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
