"""Every defect class in one org's live card queue, found without being told.

Written because the loop had become: ship a card, the owner spots one flaw, fix that flaw, ship
again, owner spots the next. Each pass was correct and the sequence was useless — the person who
should be judging whether the advice is any good was instead doing QA on rendering. This asks the
whole queue every question at once so the list arrives complete.
"""
from __future__ import annotations

import os
import re
import sys

from sqlalchemy import text

from genios_engine.platform.db import get_engine

CHECKS: list[tuple[str, str]] = [
    ("headline truncated mid-token",
     r"(headline ~ '\.\s*$' or headline ~ '\s[a-z]{1,3}\.$' or length(headline) < 12)"),
    ("says it has nothing to say",
     r"(headline ilike '%no facts%' or headline ilike '%unable to%' or "
     r"headline ilike '%cannot %' or situation::text ilike '%no information provided%' or "
     r"situation::text ilike '%unable to determine%')"),
    ("raw serialisation leaked into copy",
     r"(headline ilike '%object Object%' or situation::text ilike '%object%Object%' or "
     r"why::text ilike '%$decimal%' or why::text ilike '%$datetime%')"),
    ("sentinel word reached the user",
     r"(situation::text ilike '%several days%' or situation::text ilike '%severald%' or "
     r"headline ilike '%{%}%' or situation::text ilike '%{%}%')"),
    ("template copy, not authored", "render_mode = 'raw_slot'"),
    ("abstains instead of advising", "level <> 'prescriptive'"),
    ("no action offered", "(actions is null or actions::text in ('[]','null'))"),
]


def main() -> int:
    org = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("GENIOS_AUDIT_ORG", "")
    if not org:
        print(__doc__)
        return 2
    engine = get_engine(os.environ["GENIOS_DATABASE_URL"])
    with engine.connect() as c:
        total = c.execute(text(
            "select count(*) from cards where org_id=:o and state='queued'"), {"o": org}).scalar()
        print(f"{total} queued cards\n")
        for label, predicate in CHECKS:
            n = c.execute(text(
                f"select count(*) from cards where org_id=:o and state='queued' and {predicate}"),
                {"o": org}).scalar()
            if not n:
                print(f"  ok    {label}")
                continue
            print(f"  {n:>3}   {label}")
            for row in c.execute(text(
                    f"select headline from cards where org_id=:o and state='queued' "
                    f"and {predicate} limit 3"), {"o": org}):
                print(f"          · {str(row[0])[:66]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
