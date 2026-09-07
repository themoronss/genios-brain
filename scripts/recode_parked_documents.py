"""Re-code the attachment parks that were filed as permanently unreadable and are not.

    python scripts/recode_parked_documents.py --database-url postgresql://…            # dry run
    python scripts/recode_parked_documents.py --database-url postgresql://… --apply    # writes

**What went wrong, and why a stored row has to be corrected rather than left alone.** The Gmail
connector's pre-download skip filed EVERY attachment it did not fetch as
`document.status = "unsupported"`, which the gate parks under `DOC-02`. That code means *nothing
can ever read this file* — a .zip, a firmware blob — and it is terminal: `parked/drain.py` counts
it, `refetch.py` will retry it, but no amount of retrying changes an unreadable format, so the
row sits at `pending` for ever and reads to every surface as a file we correctly gave up on.

A screenshot invoice and a scanned PO are the opposite fact. They are readable in principle and
unread only because no OCR engine is wired on this host — `DOC-06 ocr_unavailable`, which is one
config line plus a redeploy away from being resolved. `documents/router.py` has always drawn that
distinction ("`unsupported` shrank"); the pre-download skip never learned it, and production
therefore holds hundreds of rows saying *unreadable* about files nobody has tried to read.

The connector is fixed. This script fixes the rows the old code already wrote, because a park is
a permanent record and correcting it is the only way the OCR backlog becomes visible — and, once
OCR is enabled, drainable.

**How a row is judged.** By the SAME function the connector now uses: `documents/router.has_pages`
over the mime and filename retained in `raw_payloads`. No heuristic of its own, so the script and
the door cannot disagree about what "has pages" means. A park whose payload has expired (TTL) or
cannot be decrypted is COUNTED and left alone: an unreadable payload is not evidence that the file
had no pages, and guessing would be inventing the very fact this script exists to correct.

**Read-only until `--apply`.** The dry run declares its transaction `read only` at the server, so
a statement that tried to write would be refused by PostgreSQL rather than by review. The target
is resolved through `scripts/_db.py`, which has no fallback to the application's own database.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts._db import add_database_argument, resolve_database_url   # noqa: E402

#: The code these rows were filed under, and the code the readable ones should carry.
FROM_CODE = "DOC-02"
TO_CODE = "DOC-06"

#: Only rows nobody has acted on. A park a human already promoted, recovered or dead-lettered is
#: a decision somebody made, and re-coding it would overwrite that decision with a guess about
#: what they would have done under a code they never saw.
STATUS = "pending"

#: `cast(:org as text)` because psycopg cannot infer the type of a bare NULL parameter compared
#: against itself, and "every tenant" is the ordinary invocation.
_SELECT = """
select p.event_id, p.org_id, r.enc_content
  from parked_events p
  left join raw_payloads r on r.event_id = p.event_id and r.org_id = p.org_id
 where p.reason_code = :code and p.status = :status
   and (cast(:org as text) is null or p.org_id = cast(:org as text))
"""

_UPDATE = """
update parked_events set reason_code = :to_code
 where event_id = :event and org_id = :org and reason_code = :from_code and status = :status
"""


def _payload(enc_content, key: str) -> dict | None:
    """The retained raw object, decrypted, or None when it is gone or unreadable."""
    if enc_content is None or not key:
        return None
    try:
        from genios_engine.platform.crypto import decrypt
        body = json.loads(decrypt(bytes(enc_content), key))
    except Exception:      # noqa: BLE001 — an unreadable payload is a row we leave alone
        return None
    return body if isinstance(body, dict) else None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    add_database_argument(ap)
    ap.add_argument("--org", default=None, help="one tenant, or every tenant when omitted")
    ap.add_argument("--apply", action="store_true",
                    help="write the corrected reason codes (default is a dry run)")
    ap.add_argument("--crypto-key", default=os.environ.get("GENIOS_CRYPTO_KEY", ""),
                    help="the key the payloads were encrypted with (default: GENIOS_CRYPTO_KEY)")
    args = ap.parse_args()
    url = resolve_database_url(args, purpose="re-code mislabelled document parks")

    from sqlalchemy import text

    from genios_engine.capture.documents.router import has_pages
    from genios_engine.platform.db import get_engine

    engine = get_engine(url)
    tally: Counter[str] = Counter()
    to_fix: list[tuple[str, str]] = []

    with engine.connect() as conn:
        conn.execute(text("set transaction read only"))
        rows = conn.execute(text(_SELECT),
                            {"code": FROM_CODE, "status": STATUS, "org": args.org}).fetchall()

    for row in rows:
        body = _payload(row.enc_content, args.crypto_key)
        if body is None:
            tally["payload_unavailable"] += 1
            continue
        mime = str(body.get("mime") or "")
        filename = str(body.get("subject") or "")
        if has_pages(mime, filename):
            tally["has_pages"] += 1
            to_fix.append((row.event_id, row.org_id))
        else:
            tally["genuinely_unsupported"] += 1

    print(f"parked {FROM_CODE}/{STATUS} rows examined: {len(rows)}")
    for name in ("has_pages", "genuinely_unsupported", "payload_unavailable"):
        print(f"  {name:24} {tally[name]}")

    if not args.apply:
        print(f"\nDRY RUN — nothing written. {len(to_fix)} row(s) would become {TO_CODE} "
              f"(drainable once an OCR engine is wired). Re-run with --apply to write.")
        return 0

    written = 0
    with engine.begin() as conn:
        for event_id, org_id in to_fix:
            written += conn.execute(text(_UPDATE), {
                "to_code": TO_CODE, "event": event_id, "org": org_id,
                "from_code": FROM_CODE, "status": STATUS}).rowcount
    print(f"\nre-coded {written} row(s) {FROM_CODE} -> {TO_CODE}")
    return 0


if __name__ == "__main__":       # pragma: no cover - operator entry point
    raise SystemExit(main())
