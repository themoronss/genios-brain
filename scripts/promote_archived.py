"""Promote one tenant's archived mail back to kept, by the rule that archived it — STEP-05.

    python scripts/promote_archived.py --org <org_id> --rule N-02 --sender-domain boardy.ai \\
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

**`--apply` re-fetches the body first (GeniOS-011 S06.U2, B27).** On the Gmail fast path a confident
junk drop was archived with its LIST snippet, not its body, and the re-read reads the stored payload —
so a promotion that only flipped the row would have the next pass read Boardy's introductions from
their ~snippet. So each mail is fetched again WHOLE through its connection's connector
(`connectors/composio.whole_message_reader`: deadline, refusal handling, one retry), its stored payload
replaced with the whole message, and only then promoted. A mail whose body cannot be fetched is NOT
promoted: it stays archived, counted ("NOT FETCHED"), and a later run tries it again. `--crypto-key`
(default `GENIOS_CRYPTO_KEY`) is the key the payloads are stored under. The dry run fetches nothing.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from datetime import timezone
from types import SimpleNamespace

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
                    help="only mail sent from this domain (e.g. boardy.ai — Boardy writes from boardy@boardy.ai)")
    ap.add_argument("--apply", action="store_true", help="promote (default: a dry run that counts)")
    ap.add_argument("--crypto-key", default=os.environ.get("GENIOS_CRYPTO_KEY", ""),
                    help="the key the payloads are stored under (default: GENIOS_CRYPTO_KEY); "
                         "--apply re-stores each re-fetched body under it")
    return ap.parse_args(argv)


#: How the re-fetched body replaces the archived payload. The same row the re-read ladder reads
#: (`unread._FIND_PARKED` joins `raw_payloads` on the event); its `expires_at` — the archive's keep
#: window — is left as it was.
_RESTORE_BODY = (
    "update raw_payloads set enc_content = :enc "
    " where org_id = :o and event_id = :e")
#: Where each candidate's message is: its source, type and provider id, and the connection that
#: captured it.
_WHERE_FROM = (
    "select event_id, connection_id, source, object_type, source_object_id from source_events "
    " where org_id = :o and event_id = any(:ids)")


def _reader_for_connections(url: str, org_id: str):
    """`(connection_id, source) -> whole-message reader | None` over the target's connections.

    The connection that captured the mail, else a live one for the same org and source — a
    reconnect writes a new connection row (`api/routes._attachment_connector_for`, same reasoning);
    a connection that belongs to another org answers None. A connector that cannot read a message
    whole (the offline fixture) answers None, and nothing is promoted on a snippet."""
    from genios_engine.capture.connections.store import PostgresConnectionStore
    from genios_engine.capture.connectors.composio import whole_message_reader
    from genios_engine.platform.wiring import make_connector_for

    store = PostgresConnectionStore(url)
    built: dict[tuple, object] = {}

    def reader_for(connection_id, source):
        if (connection_id, source) not in built:
            conn = store.get(connection_id) if connection_id else None
            if conn is not None and conn.org_id != org_id:
                built[(connection_id, source)] = None
                return None
            if conn is None:
                conn = next((c for c in store.list_active(source) if c.org_id == org_id), None)
            connector = make_connector_for(conn) if conn is not None else None
            built[(connection_id, source)] = (whole_message_reader(connector)
                                              if hasattr(connector, "whole_message") else None)
        return built[(connection_id, source)]

    return reader_for


def refetch_bodies(engine, org_id: str, event_ids, *, reader_for, crypto_key: str):
    """GeniOS-011 S06.U2 (B27) · each candidate's whole message, fetched again and stored in place
    of its archived payload. Returns `(fetched_ids, not_fetched)` — a mail is fetched only when its
    connector read it whole; a refusal, a timeout, no connector, or a message that is not a Gmail
    email is NOT fetched, and is never promoted on what was stored."""
    from sqlalchemy import text

    from genios_engine.platform.crypto import encrypt

    if not event_ids:
        return [], 0
    with engine.connect() as c:
        rows = c.execute(text(_WHERE_FROM), {"o": org_id, "ids": list(event_ids)}).fetchall()
    fetched: list[str] = []
    bodies: list[dict] = []
    for row in rows:
        reader = reader_for(row.connection_id, row.source)
        whole = None
        if reader is not None:
            try:
                whole = reader(SimpleNamespace(event_id=row.event_id, source=row.source,
                                               object_type=row.object_type,
                                               source_object_id=row.source_object_id))
            except Exception as e:      # noqa: BLE001 — said, and the mail stays archived
                print(f"  not fetched {row.event_id}: {type(e).__name__}", file=sys.stderr)
                whole = None
        if whole is None or whole.source_object_id != row.source_object_id:
            continue
        fetched.append(row.event_id)
        bodies.append({"o": org_id, "e": row.event_id,
                       "enc": encrypt(json.dumps(whole.raw, default=str), crypto_key)})
    if bodies:
        with engine.begin() as c:
            c.execute(text(_RESTORE_BODY), bodies)
    return fetched, len(event_ids) - len(fetched)


def promote_refetched(engine, org_id: str, *, rule: str, sender_domain: str | None,
                      reader_for, crypto_key: str):
    """`--apply`: the mail `promote_archived` would promote, each re-fetched whole first; only the
    fetched ones go back to the ledger as kept. Returns `(dry_report, promoted, not_fetched)`.

    The selection and the promotion are `capture/landing/promote`'s own statements, not copies, so
    what this promotes is exactly what its dry run listed — narrowed to the bodies that arrived."""
    from sqlalchemy import text

    from genios_engine.capture.landing import promote

    report = promote.promote_archived(engine, org_id, rule=rule, sender_domain=sender_domain,
                                      apply=False)
    with engine.connect() as c:
        rows = c.execute(promote._ARCHIVED_BY, {"o": org_id, "rule": report.rule,
                                                 "domain": report.sender_domain,
                                                 "now": datetime.now(timezone.utc)}).fetchall()
    readable = [r.event_id for r in rows if r.readable]
    fetched, not_fetched = refetch_bodies(engine, org_id, readable, reader_for=reader_for,
                                          crypto_key=crypto_key)
    promoted = 0
    if fetched:
        with engine.begin() as c:
            promoted = c.execute(promote._PROMOTE, {"o": org_id, "rule": report.rule,
                                                    "ids": fetched}).rowcount
    return report, promoted, not_fetched


def main(argv: list[str] | None = None, *, reader_for=None) -> int:
    """`reader_for(connection_id, source)` answers a whole-message reader or None; by default it
    is built over the target's own connections (`_reader_for_connections`)."""
    args = parse_args(argv)
    from genios_engine.capture.landing.promote import ARCHIVE_CODES, promote_archived
    if args.rule not in ARCHIVE_CODES:
        raise SystemExit(f"{args.rule!r} is not a code the gate archives with — one of "
                         f"{sorted(ARCHIVE_CODES)}")
    if args.apply and not args.crypto_key:
        raise SystemExit("--apply re-stores each re-fetched body encrypted: pass --crypto-key or "
                         "set GENIOS_CRYPTO_KEY")
    url = resolve_database_url(args, purpose="promote a tenant's archived mail back to kept")
    from genios_engine.platform.db import get_engine
    engine = get_engine(url)
    if args.apply:
        report, promoted, not_fetched = promote_refetched(
            engine, args.org, rule=args.rule, sender_domain=args.sender_domain,
            reader_for=reader_for or _reader_for_connections(url, args.org),
            crypto_key=args.crypto_key)
    else:
        report = promote_archived(engine, args.org, rule=args.rule,
                                  sender_domain=args.sender_domain, apply=False)
    scope = f"archived by {report.rule}" + (f" from {report.sender_domain}"
                                            if report.sender_domain else "")
    print(f"{args.org}: {report.archived} mail {scope} can be read again; "
          f"{report.unreadable} past the archive's window (left archived)")
    for event_id, occurred_at, domain in report.sample:
        print(f"  {event_id}  {occurred_at}  {domain}")
    if args.apply:
        print(f"PROMOTED {promoted} — each read whole again; the next chain pass reads them")
        print(f"NOT FETCHED {not_fetched} — the provider did not hand back the whole message; "
              "left archived, never promoted on its snippet")
    else:
        print("DRY RUN — nothing written, nothing fetched. --apply fetches each mail whole "
              "first; a mail whose body cannot be fetched stays archived.")
    return 0


if __name__ == "__main__":       # pragma: no cover - operator entry point
    raise SystemExit(main())
