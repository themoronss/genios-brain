"""Declare what a tenant's own addresses and domains are — `org_self_identities` (STEP-04).

    python scripts/declare_self_identity.py --org <org_id> --address ceo@thegenios.com \\
        --domain thegenios.com --by "06 D6" --database-url postgresql://…            # dry run
    … --apply                                                                         # writes

**Why.** "Who is us" was decided in eighteen places from `orgs.email`, the active seats and a
connections column nothing writes (`speedrun008/YC-II W27/` STEP-04 §8.2). An address of ours that is
neither — the design partner's `ceo@thegenios.com`, which only ever receives the founder's own mail —
and the company's own domain had nowhere to be said, so the engine typed the address a service, put it
on "waiting longest" lines, and minted the company as an outside company. A declaration here is read by
`platform/self_identity.identity_for`, which every module that asks "is this us?" asks.

**What it touches.** One tenant (`--org`), one table, inserts only — `on conflict do nothing`, so a
second run writes nothing. A public mail domain (gmail.com …) is refused before anything is written:
declared, it would make every Gmail sender one of us.

**Read-only until `--apply`.** The target goes through `scripts/_db.py`: no fallback to the
application's database, and `GENIOS_ALLOW_PROD_WRITE=1` for a production host.
"""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts._db import add_database_argument, resolve_database_url   # noqa: E402

INSERT = (
    "insert into org_self_identities (org_id, kind, value, declared_by) "
    "values (:org, :kind, :value, :by) on conflict do nothing")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    add_database_argument(ap)
    ap.add_argument("--org", required=True, help="the one tenant whose identity is declared")
    ap.add_argument("--address", action="append", default=[], help="an exact address of ours")
    ap.add_argument("--domain", action="append", default=[],
                    help="a domain every address of which is ours — never a public mail domain")
    ap.add_argument("--by", default="operator", help="who declared it, kept on the row")
    ap.add_argument("--apply", action="store_true", help="write (default: a dry run that lists)")
    return ap.parse_args(argv)


def declarations(*, addresses: list[str], domains: list[str]) -> list[tuple[str, str]]:
    """The rows to write, normalised exactly as `identity_for` reads them. Raises on a public mail
    domain or a value that does not normalise — nothing half-declared."""
    from genios_engine.platform.identity import norm_email
    from genios_engine.platform.self_identity import PUBLIC_MAIL_DOMAINS, norm_domain

    rows: list[tuple[str, str]] = []
    for raw in addresses:
        value = norm_email(raw)
        if not value:
            raise ValueError(f"{raw!r} is not an address")
        rows.append(("address", value))
    for raw in domains:
        value = norm_domain(raw)
        if not value:
            raise ValueError(f"{raw!r} is not a domain")
        if value in PUBLIC_MAIL_DOMAINS:
            raise ValueError(f"{value} is a public mail domain — declared, every address at it would "
                             "be one of us; declare the exact address instead")
        rows.append(("domain", value))
    return rows


def declare(engine, org_id: str, rows: list[tuple[str, str]], *, by: str, apply: bool) -> int:
    """How many rows would be written (dry run), or were (apply) — 0 for what is already declared."""
    from sqlalchemy import text

    if not apply:
        return len(rows)
    written = 0
    with engine.begin() as conn:
        for kind, value in rows:
            written += conn.execute(text(INSERT), {"org": org_id, "kind": kind, "value": value,
                                                   "by": by}).rowcount
    return written


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if not (args.address or args.domain):
        raise SystemExit("nothing to declare — give at least one --address or --domain")
    rows = declarations(addresses=args.address, domains=args.domain)
    url = resolve_database_url(args, purpose="declare a tenant's own addresses and domains")
    from genios_engine.platform.db import get_engine
    n = declare(get_engine(url), args.org, rows, by=args.by, apply=args.apply)
    listed = ", ".join(f"{kind} {value}" for kind, value in rows)
    if args.apply:
        print(f"declared {n} new value(s) for {args.org} ({listed}); already-declared ones unchanged")
    else:
        print(f"DRY RUN — nothing written. Would declare for {args.org}: {listed}. Re-run with --apply.")
    return 0


if __name__ == "__main__":       # pragma: no cover - operator entry point
    raise SystemExit(main())
