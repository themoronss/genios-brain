"""How every active situation of one tenant ended — read-only, one line per type (or per situation).

    python scripts/situation_ends.py --org <org_id> --database-url postgresql://…
    python scripts/situation_ends.py --org <org_id> --database-url postgresql://… --verbose
    python scripts/situation_ends.py --org <org_id> --database-url postgresql://… --json

STEP-06 (`yc2_w27_s06 · M24.C2.L-interface.V3.U01`). *"Why did the 8 `awaiting_response` situations
never become cards?"* used to be an afternoon of tracing (`speedrun008/YC-II W27/` STEP-06 §4). This
prints, per situation type, how many ended which way — `no_corpus`, `not_live`, `held`, `rejected`,
`carded`, `decided`, `stopped`, `unrecorded` — from `reason/situation_end`, the one reader. With
`--verbose`, one line per situation with its reason. `unrecorded` must be 0.

Read-only at the server (`scripts/_gate.read_only_connection`). The target goes through
`scripts/_db.py`: no fallback to the application's database, and a production host needs
`GENIOS_ALLOW_PROD_WRITE=1` set for the command — a read here writes nothing either way.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[1]))

from scripts._db import add_database_argument, resolve_database_url   # noqa: E402
from scripts._gate import read_only_connection                        # noqa: E402


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    add_database_argument(ap)
    ap.add_argument("--org", required=True, help="the tenant whose situations to read")
    ap.add_argument("--verbose", action="store_true", help="one line per situation")
    ap.add_argument("--json", action="store_true", help="the same, as one JSON object")
    return ap.parse_args(argv)


def histogram(ends) -> dict[str, dict[str, int]]:
    """`domain:type` → end → count, both sorted, so two runs over the same rows print the same."""
    out: dict[str, Counter] = {}
    for e in ends:
        out.setdefault(f"{e.domain}:{e.situation_type}", Counter())[e.end] += 1
    return {kind: dict(sorted(counts.items())) for kind, counts in sorted(out.items())}


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    url = resolve_database_url(args, purpose="read how every situation ended (read-only)")
    from genios_engine.platform.db import get_engine
    from genios_engine.reason.situation_end import UNRECORDED, situation_ends

    conn = read_only_connection(get_engine(url))
    try:
        ends = situation_ends(conn, args.org)
    finally:
        conn.close()
    hist = histogram(ends)
    unrecorded = sum(1 for e in ends if e.end == UNRECORDED)
    if args.json:
        print(json.dumps({"org": args.org, "situations": len(ends), "unrecorded": unrecorded,
                          "by_type": hist,
                          "situations_by_end": [{"situation_id": e.situation_id,
                                                 "type": f"{e.domain}:{e.situation_type}",
                                                 "end": e.end, "detail": list(e.detail)}
                                                for e in ends] if args.verbose else None},
                         sort_keys=True))
    else:
        for kind, counts in hist.items():
            print(f"{kind:48s} " + "  ".join(f"{end} {n}" for end, n in counts.items()))
        if args.verbose:
            print()
            for e in ends:
                print(f"{e.situation_id}  {e.domain}:{e.situation_type}  {e.end}  "
                      + ", ".join(e.detail))
        print(f"\n{len(ends)} active situations · unrecorded {unrecorded}")
    return 1 if unrecorded else 0


if __name__ == "__main__":
    sys.exit(main())
