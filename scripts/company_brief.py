"""Read and decide a tenant's company brief — for an operator acting on the founder's word (STEP-07).

    python scripts/company_brief.py --org <org_id> --database-url postgresql://… show
    … accept <line_id> [<line_id> …] [--text "the founder's own words"]
    … reject <line_id> [<line_id> …]
    … remove <line_id> [<line_id> …]
    … add <section> "<text>" [--address a@b.c] [--domain b.c]

**Why.** The founder confirms the brief on the dashboard's screen (`api/company_brief_routes`); until
that screen exists, this makes the same decisions through the same writer
(`platform/company_brief_store`) — so Harsh can send Rohit the proposals (`show`) and apply exactly what
Rohit says, the way D14 and D23 are run. Accepting or adding a connector, key person or watchlist line
promotes what the gate archived from that sender's domain, as the screen does
(`capture/landing/promote.promote_named_sender`).

**What `show` prints.** The brief as the models read it, its version, what its budget left out, the
accepted lines, and every proposal with the patterns it rests on — never a message.

Every database door goes through `scripts/_db.py`: no fallback to the application's database, and
`GENIOS_ALLOW_PROD_WRITE=1` for a production host.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts._db import add_database_argument, resolve_database_url   # noqa: E402

ACTIONS = ("show", "accept", "reject", "remove", "add")
#: The sections whose line names a sender, so accepting one promotes that sender's archive.
NAMES_A_SENDER = ("connectors", "people", "watchlist")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    add_database_argument(ap)
    ap.add_argument("--org", required=True, help="the one tenant whose brief is read or decided")
    ap.add_argument("--by", default="operator", help="who decided, kept on the row")
    ap.add_argument("--text", default=None, help="accept: the founder's own words for the line")
    ap.add_argument("--address", default=None, help="add: the connector's or person's address")
    ap.add_argument("--domain", default=None, help="add: the watchlist domain")
    ap.add_argument("action", choices=ACTIONS)
    ap.add_argument("args", nargs="*", help="line ids, or for add: SECTION TEXT")
    return ap.parse_args(argv)


def _rests_on(evidence: list) -> str:
    return "; ".join(json.dumps({k: v for k, v in e.items() if k != "pattern"}, sort_keys=True,
                                ensure_ascii=False) if isinstance(e, dict) else str(e)
                     for e in evidence)


def show(engine, org_id: str) -> str:
    from sqlalchemy import text

    from genios_engine.platform import company_brief_store as store
    from genios_engine.platform.company_brief import brief_for

    with engine.connect() as c:
        brief = brief_for(c, org_id)
        lines = c.execute(text(
            "select line_id, section, text, address, domain from company_brief_lines "
            " where org_id = :o and status = 'accepted' order by accepted_at, line_id"),
            {"o": org_id}).fetchall()
        pending = store.pending(c, org_id)
    out = [f"company brief for {org_id}: "
           + (f"version {brief.version}" if brief else "none yet — no line is accepted")]
    if brief.truncated:
        out.append(f"the budget left out {len(brief.truncated)} line(s): {', '.join(brief.truncated)}")
    if brief:
        out += ["", brief.prompt_block().rstrip()]
    out += ["", f"accepted lines ({len(lines)}):"]
    out += [f"  {r.line_id}  [{r.section}] {r.text}"
            + (f" <{r.address or r.domain}>" if (r.address or r.domain) else "") for r in lines]
    out += ["", f"proposals waiting for the founder ({len(pending)}):"]
    for p in pending:
        named = p["address"] or p["domain"]
        out.append(f"  {p['line_id']}  [{p['section']}] {p['text']}"
                   + (f" <{named}>" if named else "") + f"   — proposed by {p['proposed_by']}")
        if p["evidence"]:
            out.append(f"      rests on {_rests_on(p['evidence'])}")
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.action == "add" and len(args.args) != 2:
        raise SystemExit("add takes SECTION and TEXT")
    if args.action in ("accept", "reject", "remove") and not args.args:
        raise SystemExit(f"{args.action} takes one or more line ids")
    if args.text is not None and (args.action != "accept" or len(args.args) != 1):
        raise SystemExit("--text gives the founder's words for ONE line being accepted")
    url = resolve_database_url(args, purpose="read or decide a tenant's company brief")
    from genios_engine.capture.landing.promote import promote_named_sender
    from genios_engine.platform import company_brief_store as store
    from genios_engine.platform.db import get_engine

    engine = get_engine(url)
    now = datetime.now(timezone.utc)
    if args.action == "show":
        print(show(engine, args.org))
        return 0
    if args.action == "add":
        section, words = args.args
        try:
            with engine.begin() as c:
                line_id = store.add(c, org_id=args.org, section=section, words=words,
                                    address=args.address, domain=args.domain, decided_by=args.by,
                                    at=now)
        except ValueError as exc:
            print(f"refused: {exc}")
            return 1
        promoted = promote_named_sender(engine, args.org, address=args.address, domain=args.domain) \
            if section in NAMES_A_SENDER else 0
        print(f"added {line_id} [{section}] — in force now; promoted {promoted} archived mail(s)")
        return 0
    for line_id in args.args:
        promoted = 0
        try:
            with engine.begin() as c:
                if args.action == "accept":
                    line = store.accept(c, org_id=args.org, line_id=line_id, decided_by=args.by,
                                        at=now, words=args.text)
                elif args.action == "reject":
                    line = store.reject(c, org_id=args.org, line_id=line_id, decided_by=args.by,
                                        at=now)
                else:
                    line = store.remove(c, org_id=args.org, line_id=line_id, decided_by=args.by,
                                        at=now)
        except ValueError as exc:            # each id is its own transaction: what came before stands
            print(f"refused {line_id}: {exc}")
            return 1
        if line is not None and line.section in NAMES_A_SENDER:
            promoted = promote_named_sender(engine, args.org, address=line.address,
                                            domain=line.domain)
        print({"accept": "accepted", "reject": "rejected", "remove": "removed"}[args.action]
              + f" {line_id}" + (f"; promoted {promoted} archived mail(s)"
                                 if args.action == "accept" else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
