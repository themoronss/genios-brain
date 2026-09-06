"""The one place a maintenance script is allowed to decide which database it opens.

WHY THIS EXISTS. `scripts/rebuild_graph.py:107` resolves its target with
`get_settings().database_url`. `platform/config.py` loads `.env`, so on every developer machine
that expression is the **production Supabase URL** — and the script it feeds backs up, WIPES and
replays eight projection tables. Nothing in the invocation names production; you get it by
running the script at all. `tests/conftest.py` already closed the identical hole for the test
suite (a `conn` fixture that "rolled back" was holding locks on a paying tenant), and the L1 v2
plan adds five more gate scripts — `l1_s1_report`, `extract_golden`, `importance_distribution`,
`l1_end_to_end`, `l1_shadow_diff` — every one of which would inherit the same default.

THE MECHANISM. This module refuses to answer the question implicitly. A caller gets a URL only
by naming one, either as `--database-url` or in `GENIOS_TARGET_DATABASE_URL`; there is
deliberately NO fallback to `Settings`, and this module imports nothing from `genios_engine` so
the fallback cannot be re-introduced by accident. A URL whose host belongs to Supabase is
refused a second time unless `GENIOS_ALLOW_PROD_WRITE=1` is exported for that command, so
touching production is always two deliberate acts. Whatever survives both checks is PRINTED,
credentials redacted, before the caller receives it — the operator sees the target before the
first statement runs, not in the post-mortem.

A separate env var from `GENIOS_DATABASE_URL` is the point: the app's own variable is the one
already sitting in `.env` pointing at production, and reusing it would rebuild the default this
module exists to remove.

Usage:

    from scripts._db import add_database_argument, resolve_database_url

    ap = argparse.ArgumentParser()
    add_database_argument(ap)
    args = ap.parse_args()
    url = resolve_database_url(args, purpose="rebuild org graph")
"""
from __future__ import annotations

import argparse
import os
import sys
from typing import TextIO
from urllib.parse import urlsplit, urlunsplit

#: The ONLY env var this resolver reads for a target. Deliberately not `GENIOS_DATABASE_URL`:
#: that one is the running application's setting, is present in every developer `.env`, and
#: points at production — reading it here would re-create the implicit default by another name.
TARGET_URL_ENV = "GENIOS_TARGET_DATABASE_URL"

#: Second lock, checked only after a production-looking host is detected. Its value must be
#: exactly "1"; a truthy-ish "true"/"yes" is not accepted, because the whole purpose of the
#: variable is that setting it is a deliberate, unambiguous act for one command.
ALLOW_PROD_ENV = "GENIOS_ALLOW_PROD_WRITE"

#: Host suffixes that mean "this is the hosted tenant database". `supabase.co` covers the direct
#: host (`db.<ref>.supabase.co`), `supabase.com` covers the session/transaction poolers
#: (`aws-0-<region>.pooler.supabase.com`) that `platform/db.py` sizes its pool against. Matched on
#: the host SUFFIX so a new region or pooler hostname is guarded the day it appears.
PRODUCTION_HOST_SUFFIXES = ("supabase.co", "supabase.com")


class UnsafeDatabaseTarget(RuntimeError):
    """Raised instead of returning a URL the operator did not deliberately choose.

    An exception rather than `sys.exit` so the refusal is testable and so a caller that wraps
    several targets can report which one it rejected."""


def add_database_argument(parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
    """Attach the standard `--database-url` flag. Every maintenance script takes it in the same
    spelling so an operator never has to remember which script uses which name."""
    parser.add_argument(
        "--database-url", default=None,
        help=(f"target Postgres URL. REQUIRED unless {TARGET_URL_ENV} is set — these scripts "
              "never inherit the application's configured database."))
    return parser


def is_production_url(database_url: str) -> bool:
    """True when the URL's host is a Supabase host, i.e. the tenant database that serves live
    traffic. Host-based rather than name-based: a URL can be spelled a dozen ways, but the host
    is what the connection actually reaches."""
    host = (urlsplit(database_url).hostname or "").lower()
    return any(host == suffix or host.endswith("." + suffix)
               for suffix in PRODUCTION_HOST_SUFFIXES)


def redact(database_url: str) -> str:
    """The URL with its password replaced by `***`, safe to print and to paste into a ticket.

    Everything else is kept — user, host, port and database name — because those four are exactly
    what the operator needs to recognise the wrong target before the script writes to it. A fully
    masked string would be safe and useless."""
    parts = urlsplit(database_url)
    if parts.password is None:
        return database_url
    user = parts.username or ""
    host = parts.hostname or ""
    netloc = f"{user}:***@{host}" if user else f":***@{host}"
    if parts.port:
        netloc = f"{netloc}:{parts.port}"
    return urlunsplit((parts.scheme, netloc, parts.path, parts.query, parts.fragment))


def describe(database_url: str) -> str:
    """One line naming the host, the database and whether it is production — the line printed
    before any statement runs."""
    parts = urlsplit(database_url)
    host = parts.hostname or "(no host)"
    port = f":{parts.port}" if parts.port else ""
    name = parts.path.lstrip("/") or "(no database name)"
    kind = "PRODUCTION" if is_production_url(database_url) else "non-production"
    return f"{kind}  host={host}{port}  database={name}  url={redact(database_url)}"


def resolve_database_url(args: argparse.Namespace | None = None, *,
                         purpose: str = "database access",
                         stream: TextIO | None = None) -> str:
    """Return the URL this script may open, or raise `UnsafeDatabaseTarget`.

    Resolution order, and there is no third source:
      1. `--database-url` on the command line (an explicit choice for this one run);
      2. `GENIOS_TARGET_DATABASE_URL` in the environment (an explicit choice for this shell).

    `get_settings().database_url` is NOT consulted. That is the whole contract: a script with no
    named target does nothing at all, which is the only behaviour that is safe by default on a
    machine whose `.env` points at a live tenant.

    A production host additionally requires `GENIOS_ALLOW_PROD_WRITE=1`, so reaching production is
    two deliberate acts and neither of them is "ran the script". The resolved target is printed —
    redacted — before this function returns, because a guard the operator cannot see is a guard
    they cannot correct.
    """
    out = sys.stdout if stream is None else stream
    flag = getattr(args, "database_url", None) if args is not None else None
    url = (flag or os.environ.get(TARGET_URL_ENV) or "").strip()
    origin = "--database-url" if flag else TARGET_URL_ENV

    if not url:
        raise UnsafeDatabaseTarget(
            f"refusing to run {purpose!r} without an explicit database target. Pass "
            f"--database-url <url> or export {TARGET_URL_ENV}. These scripts deliberately do not "
            "fall back to the configured database_url, because on a machine with a .env that is "
            "the production tenant database.")

    parts = urlsplit(url)
    if not parts.scheme.startswith("postgres") or not parts.hostname:
        # Not pedantry: `urlsplit("localhost:5432/genios")` yields scheme="localhost" and no host,
        # so a plausible-looking typo parses cleanly and would reach the driver as garbage — or,
        # worse, be silently ignored by a caller that only checks for a non-empty string. Every
        # script behind this resolver opens Postgres; anything else is a mistake, not a target.
        raise UnsafeDatabaseTarget(
            f"{origin} is not a Postgres URL: {redact(url)!r}. Expected "
            "postgresql://user:pass@host:5432/dbname (a scheme and a host are both required).")

    if is_production_url(url) and os.environ.get(ALLOW_PROD_ENV) != "1":
        raise UnsafeDatabaseTarget(
            f"refusing {purpose!r} against PRODUCTION ({parts.hostname}). This is the live tenant "
            f"database. If that is genuinely intended, run the command with {ALLOW_PROD_ENV}=1 "
            "set, and only after you have said out loud what it writes.")

    print(f"[db] {purpose}", file=out)
    print(f"[db] target ({origin}): {describe(url)}", file=out, flush=True)
    return url
