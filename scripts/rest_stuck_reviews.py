"""One-off, after the STEP-18 deploy: a review object stuck at `governed` waits for review again.

    python scripts/rest_stuck_reviews.py --database-url "$URL"            # dry run: counts and ids
    python scripts/rest_stuck_reviews.py --database-url "$URL" --apply    # moves them, one transaction

`yc2_w27_s18` M48.C1.L-data.V1.U14 (S18-X09; L6 Learning, `feedback/`). STEP-18 B4
(`feedback/publisher._rest_for_review`, M48.C1.L-data.V0.U02) rests a NEW review object at
`human_review`. One the weekly sweep sent for review BEFORE that fix stays where it was — at
`governed` — and nothing moves it: `publisher.persist` answers `unchanged` for any row past
`candidate`, so the sweep never publishes it again, and its id is stable week to week. The review
route answers 409 to anything not at `human_review` and the queues read only `human_review`, so such
an object is never listed and can never be reviewed.

Which rows: `state = 'governed'` and the object's LATEST `learning_transitions` row goes to
`human_review` — the ledger says it waits for review, the row says it does not. Latest by
`occurred_at`, and between two edges written at the same instant (the sweep persists and publishes
with one `now`: `→ governed`, then `governed → human_review`) the one with a `from_state` is the
later. Nothing is written to `learning_transitions`: the ledger already holds the edge, and the row
catches up with it.

Dry run by default; `--apply` moves them in one transaction, each row still `governed` when it is
moved. `--org` narrows it to one tenant. The target is named (`scripts/_db`), never the configured
database.
"""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text  # noqa: E402

from scripts._db import add_database_argument, resolve_database_url   # noqa: E402

#: Every object the ledger sends to review and the row still holds at `governed`.
STUCK = (
    "select lo.org_id, lo.learning_id from learning_objects lo "
    "where lo.state = 'governed' "
    "and (cast(:org as text) is null or lo.org_id = cast(:org as text)) "
    "and (select lt.to_state from learning_transitions lt "
    "     where lt.org_id = lo.org_id and lt.learning_id = lo.learning_id "
    "     order by lt.occurred_at desc, (lt.from_state is null) asc, lt.id desc "
    "     limit 1) = 'human_review' "
    "order by lo.org_id, lo.learning_id")
#: The move — only a row that is still `governed`.
REST = ("update learning_objects set state = 'human_review' "
        "where org_id = :o and learning_id = :l and state = 'governed'")


def stuck(conn, org: str | None = None) -> list[tuple[str, str]]:
    """`(org_id, learning_id)` of every review object stuck at `governed`, in order."""
    return [(r.org_id, r.learning_id) for r in conn.execute(text(STUCK), {"org": org})]


def rest(engine, org: str | None = None) -> list[tuple[str, str]]:
    """Move every stuck object to `human_review`, in ONE transaction; the ones moved."""
    with engine.begin() as c:
        found = stuck(c, org)
        moved = [(o, lid) for o, lid in found
                 if c.execute(text(REST), {"o": o, "l": lid}).rowcount == 1]
    return moved


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    add_database_argument(ap)
    ap.add_argument("--org", default=None, help="one tenant (default: every tenant)")
    ap.add_argument("--apply", action="store_true", help="move them (default is a dry run)")
    args = ap.parse_args(argv)
    url = resolve_database_url(args, purpose="rest review objects stuck at governed")

    from genios_engine.platform.db import get_engine

    engine = get_engine(url)
    if not args.apply:
        with engine.connect() as c:
            found = stuck(c, args.org)
        _print("would move", found)
        print("DRY RUN — nothing written. Re-run with --apply to move them.")
        return 0
    _print("moved", rest(engine, args.org))
    return 0


def _print(verb: str, rows: list[tuple[str, str]]) -> None:
    orgs: dict[str, int] = {}
    for org, _lid in rows:
        orgs[org] = orgs.get(org, 0) + 1
    print(f"{verb} {len(rows)} review object(s) from governed to human_review, in {len(orgs)} org(s)")
    for org, lid in rows:
        print(f"  {org}  {lid}")


if __name__ == "__main__":
    raise SystemExit(main())
