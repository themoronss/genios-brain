"""One-off: a screen follow-up from before migration 0211 can hold MORE THAN ONE active observation.

    python scripts/retire_duplicate_screen_observations.py --database-url "$URL"            # dry run
    python scripts/retire_duplicate_screen_observations.py --database-url "$URL" --apply    # writes

`yc2_w27_s1718` M48.C2.L-data.V2.U21 (G-2, the STEP-17/18 second crosscheck). STEP-18 B13
(`reason/moments/screen_memory._retire`, M48.C2.L-data.V0.U06) retires a follow-up's PREVIOUS
observation when it is rewritten — but only when the row already names one (`observation_id`,
0211). A row written before 0211 names none: `write_items` minted one active observation per
version with nothing to retire it, so a follow-up rewritten more than once before the migration
landed can still hold several `active` graph_observations for the one `followup_id` — and the
first write AFTER 0211 only retires the ONE it itself replaces, leaving the older duplicates
active forever. A reader that counts a person's evidence by `status = 'active'` counts one ask as
many.

Which rows: every `followup_id` (`graph_source_refs.evidence->>'followup_id'`, where
`graph_source_refs.source = 'screen_insight'`) with more than one `graph_observations` row at
`status = 'active'`. For each, the LATEST survives (`occurred_at` desc, then `created_at` desc,
then `observation_id` desc to break an exact tie) and every other one is marked `superseded` —
NEVER deleted, same as `screen_memory._retire` does for an ordinary rewrite. The survivor's id is
then written into `screen_followups.observation_id`, so a later rewrite of that same follow-up
retires it the ordinary way and this script never has work to do on it twice.

Dry run by default; `--apply` moves them, one `followup_id` per statement pair, inside ONE
transaction for the whole run. `--org` narrows it to one tenant. The target is named
(`scripts/_db`), never the configured database.
"""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text  # noqa: E402

from scripts._db import add_database_argument, resolve_database_url   # noqa: E402

#: Every `(org_id, followup_id)` with more than one active screen-insight observation.
DUPLICATES = (
    "select o.org_id, r.evidence->>'followup_id' as followup_id, count(*) as active "
    "from graph_observations o "
    "join graph_source_refs r on r.observation_id = o.observation_id and r.org_id = o.org_id "
    "where r.source = 'screen_insight' and o.status = 'active' "
    "and r.evidence->>'followup_id' is not null "
    "and (cast(:org as text) is null or o.org_id = cast(:org as text)) "
    "group by 1, 2 having count(*) > 1 order by 1, 2")
#: One `(org_id, followup_id)`'s active observations, latest first — the survivor.
ACTIVE_FOR_FOLLOWUP = (
    "select o.observation_id from graph_observations o "
    "join graph_source_refs r on r.observation_id = o.observation_id and r.org_id = o.org_id "
    "where o.org_id = :org and r.source = 'screen_insight' and o.status = 'active' "
    "and r.evidence->>'followup_id' = :followup_id "
    "order by o.occurred_at desc nulls last, o.created_at desc, o.observation_id desc")
#: Supersede — never delete, as an ordinary rewrite does.
SUPERSEDE = ("update graph_observations set status = 'superseded' "
            "where org_id = :org and observation_id = :obs and status = 'active'")
#: So the next ordinary rewrite of this follow-up retires the survivor the usual way.
NAME_SURVIVOR = ("update screen_followups set observation_id = :obs "
                 "where org_id = :org and id = :followup_id")


def duplicates(conn, org: str | None = None) -> list[tuple[str, str, int]]:
    """`(org_id, followup_id, how many active)` for every follow-up with more than one, in order."""
    return [(r.org_id, r.followup_id, int(r.active))
            for r in conn.execute(text(DUPLICATES), {"org": org})]


def retire(engine, org: str | None = None) -> list[tuple[str, str, str, int]]:
    """Supersede every duplicate but the latest, in ONE transaction. Returns
    `(org_id, followup_id, surviving observation_id, how many superseded)` per follow-up."""
    moved: list[tuple[str, str, str, int]] = []
    with engine.begin() as c:
        found = duplicates(c, org)
        for org_id, followup_id, _n in found:
            rows = c.execute(text(ACTIVE_FOR_FOLLOWUP),
                             {"org": org_id, "followup_id": followup_id}).fetchall()
            if len(rows) < 2:
                continue   # retired by a concurrent write since `found` was read
            survivor, rest = rows[0].observation_id, rows[1:]
            for row in rest:
                c.execute(text(SUPERSEDE), {"org": org_id, "obs": row.observation_id})
            c.execute(text(NAME_SURVIVOR),
                     {"org": org_id, "obs": survivor, "followup_id": followup_id})
            moved.append((org_id, followup_id, survivor, len(rest)))
    return moved


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    add_database_argument(ap)
    ap.add_argument("--org", default=None, help="one tenant (default: every tenant)")
    ap.add_argument("--apply", action="store_true", help="supersede them (default is a dry run)")
    args = ap.parse_args(argv)
    url = resolve_database_url(args, purpose="retire duplicate screen observations")

    from genios_engine.platform.db import get_engine

    engine = get_engine(url)
    if not args.apply:
        with engine.connect() as c:
            found = duplicates(c, args.org)
        _print_found(found)
        print("DRY RUN — nothing written. Re-run with --apply to supersede them.")
        return 0
    _print_moved(retire(engine, args.org))
    return 0


def _print_found(rows: list[tuple[str, str, int]]) -> None:
    orgs = {org for org, _fid, _n in rows}
    print(f"would retire the extra observation(s) of {len(rows)} follow-up(s) in {len(orgs)} org(s)")
    for org, fid, n in rows:
        print(f"  {org}  {fid}  {n} active, keeping the latest")


def _print_moved(rows: list[tuple[str, str, str, int]]) -> None:
    orgs = {org for org, _fid, _obs, _n in rows}
    superseded = sum(n for _o, _f, _obs, n in rows)
    print(f"superseded {superseded} observation(s) across {len(rows)} follow-up(s) in {len(orgs)} org(s)")
    for org, fid, obs, n in rows:
        print(f"  {org}  {fid}  kept {obs}, superseded {n}")


if __name__ == "__main__":
    raise SystemExit(main())
