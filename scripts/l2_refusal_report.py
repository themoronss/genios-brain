#!/usr/bin/env python3
"""L2-0 · every way Layer 2 declined, on one screen — read-only.

    python scripts/l2_refusal_report.py --org <org_id> --database-url <url>
    python scripts/l2_refusal_report.py --corpus-only        # no database, runnable today

⛔ **WHY THIS SCRIPT IS THE FIRST THING LAYER 2 BUILDS.** `situation_bso.l1_refusal`:

    THE REFUSAL IS CORRECT... THE SILENCE IS NOT. Such a card today simply exists, ranks, and
    quietly never becomes anything, while no surface says "its best evidence scored 1360 against a
    floor of 2500". That is the fifth time this codebase has carried a refusal that was right and
    invisible, and the other four were each found by accident.

Eight things in this engine are built and never switched on, and every one of them looks identical
to a tenant with nothing happening. **This is the surface that tells them apart.** Until it exists,
every number a later step claims has no denominator.

READ-ONLY, AND STRUCTURALLY SO. The target is resolved through `scripts/_db.py`, which has no
fallback to `Settings` — *"nothing in the invocation names production; you get it by running the
script at all"* — and every statement here is a `select`. `l1_refusal` carries the same rule for
the same reason: *"this function reads, and a test fails the build if it ever learns to write."*

THE SHAPE IS COMPUTED SOMEWHERE ELSE. `context/quality/refusals.py` is pure and tested without a
database; this file only fetches rows and prints what that module returns.

⛔ **`--corpus-only` EXISTS BECAUSE ONE OF THE FOUR REFUSALS NEEDS NO DATABASE, AND WAITING FOR ONE
IS HOW ITS NUMBER STAYED WRONG.** The plan recorded *"534 capabilities, 200 admissible"* and
budgeted step 8 against 334 going dark. The corpus is on disk, it was always countable, and nobody
counted it: **155 capabilities, 155 admissible, 0 hollow — and 24 of 69 authored situations still
`draft`**, which downgrades every card built from one to an observation. The other three sections
still need the pilot.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts._db import add_database_argument, resolve_database_url  # noqa: E402

_DECISIONS = """
select situation_id, outcome, reasons
  from situation_admission_decisions
 where org_id = :org
 order by decided_at desc
 limit :limit
"""

#: Situations with no live signal — the population `l1_refusal` explains one at a time.
_DARK_DOMAIN_COUNTS = """
select domain, count(*) as situations
  from context_situations
 where org_id = :org and status = 'active' and domain = any(:domains)
 group by domain
"""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--org")
    parser.add_argument("--limit", type=int, default=2000)
    parser.add_argument("--corpus-root", default="Domain Expertise",
                        help="the authored three-domain corpus; needs no database")
    parser.add_argument("--corpus-only", action="store_true",
                        help="count the corpus and skip every database section")
    add_database_argument(parser)
    args = parser.parse_args()

    from genios_engine.context.quality.refusals import refusal_report, render

    # THE CORPUS HALF, ALWAYS. It reads files, never a row, so it is the one section that can be
    # produced on any machine — and `corpus_health` is the compiler's OWN admission rule rather
    # than a count this script keeps for itself.
    from genios_engine.packs.compiler.authoring import ExpertBrainCatalog
    from genios_engine.packs.compiler.capability_resolver import corpus_health

    corpus = [{"domain": h.domain, "total": h.total, "admitted": h.admitted,
               "inadmissible": h.inadmissible, "hollow": h.hollow,
               "situations": h.situations, "situations_unreviewed": h.situations_unreviewed}
              for h in corpus_health(ExpertBrainCatalog(args.corpus_root)).values()]

    if args.corpus_only:
        for line in render(refusal_report(decisions=(), refusals=(), dark=(), corpus=corpus)):
            print(line)
        return 0

    if not args.org:
        parser.error("--org is required unless --corpus-only is given")

    url = resolve_database_url(args, purpose="L2-0 refusal report (read-only)")

    from sqlalchemy import create_engine, text

    from genios_engine.context.domain_silence import DARK_DOMAINS
    from genios_engine.context.situation_bso import l1_refusal

    engine = create_engine(url)
    with engine.connect() as conn:
        decisions = [dict(r._mapping) for r in
                     conn.execute(text(_DECISIONS), {"org": args.org, "limit": args.limit})]
        dark = [dict(r._mapping) for r in
                conn.execute(text(_DARK_DOMAIN_COUNTS),
                             {"org": args.org, "domains": list(DARK_DOMAINS)})]

        # THE SCORE, FOR EVERY HELD SITUATION — the sentence the code says nothing speaks.
        # One call per held situation rather than a join: `l1_refusal` carries the rule about
        # which refusals are real ("one signal that cleared the bar ends the question"), and
        # re-implementing that rule in SQL here would be a second answer to one question.
        refusals = []
        for row in decisions:
            if str(row.get("outcome") or "").lower() != "hold":
                continue
            found = l1_refusal(conn, args.org, row.get("situation_id"))
            if found:
                refusals.append({"situation_id": row["situation_id"], **found})

    for line in render(refusal_report(decisions=decisions, refusals=refusals, dark=dark,
                                      corpus=corpus)):
        print(line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
