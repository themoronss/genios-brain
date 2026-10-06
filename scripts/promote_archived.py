"""Promote one tenant's archived mail back to kept, by the rule that archived it — STEP-05.

    python scripts/promote_archived.py --org <org_id> --rule N-02 --sender-domain boardy.com \\
        --database-url postgresql://…                                               # dry run
    … --apply                                                                         # promotes

**Why.** The gate archives what a noise rule or the AI filter calls noise — kept, encrypted for 180
days, read by no model (STEP-03). Boardy's introductions are archived on their unsubscribe header (N-02)
and are the one place the people Boardy introduced are named with what they do. Since STEP-05 an archive
enters memory as names and dates only; promoting it puts it back in the ledger as KEPT, and the next
chain pass's re-read (`api/routes._reread_unread`) reads it — through the gate as a re-read, so the rule
that archived it does not archive it again (`capture/landing/promote`).

**What it touches.** One tenant (`--org`), the mail archived by one rule (`--rule`, e.g. N-02 or
llm_junk) and, if given, sent from one domain. The dry run counts and lists event ids, dates and sender
domains — never a subject or a body. `--apply` flips those rows to `emitted` with attention
`promoted:<rule>`; nothing else is written. A mail past the archive's keep window is counted and left.

**Read-only until `--apply`.** The target goes through `scripts/_db.py`: no fallback to the
application's database, and `GENIOS_ALLOW_PROD_WRITE=1` for a production host.
"""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts._db import add_database_argument, resolve_database_url   # noqa: E402


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    add_database_argument(ap)
    ap.add_argument("--org", required=True, help="the one tenant whose archive is promoted")
    ap.add_argument("--rule", required=True,
                    help="the code that archived the mail — an N-code or llm_junk")
    ap.add_argument("--sender-domain", default=None,
                    help="only mail sent from this domain (e.g. boardy.com)")
    ap.add_argument("--apply", action="store_true", help="promote (default: a dry run that counts)")
    return ap.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    from genios_engine.capture.landing.promote import ARCHIVE_CODES, promote_archived
    if args.rule not in ARCHIVE_CODES:
        raise SystemExit(f"{args.rule!r} is not a code the gate archives with — one of "
                         f"{sorted(ARCHIVE_CODES)}")
    url = resolve_database_url(args, purpose="promote a tenant's archived mail back to kept")
    from genios_engine.platform.db import get_engine
    report = promote_archived(get_engine(url), args.org, rule=args.rule,
                              sender_domain=args.sender_domain, apply=args.apply)
    scope = f"archived by {report.rule}" + (f" from {report.sender_domain}"
                                            if report.sender_domain else "")
    print(f"{args.org}: {report.archived} mail {scope} can be read again; "
          f"{report.unreadable} past the archive's window (left archived)")
    for event_id, occurred_at, domain in report.sample:
        print(f"  {event_id}  {occurred_at}  {domain}")
    if args.apply:
        print(f"PROMOTED {report.promoted} — the next chain pass reads them")
    else:
        print("DRY RUN — nothing written. Re-run with --apply.")
    return 0


if __name__ == "__main__":       # pragma: no cover - operator entry point
    raise SystemExit(main())
