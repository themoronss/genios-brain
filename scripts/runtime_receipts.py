"""Runtime receipts — the missing eighth rung between Tested and Outcome-proven.

The Secret War audit makes 118 `[CODE]` claims and **zero** `[RUNTIME]` ones; its own limitation
column says *"Checkout evidence does not prove deployed tenant state."* So every "framework-ready,
not live-ready" verdict in it is a ceiling derived from the SHAPE of the code. Where the deployed
system is worse than the code suggests — a hardcoded card level, 17 dark reasoners, zero
executions, four-of-five constant score components, 100% route misses — the audit reports what the
code could do, not what the customer got. Reading it alone under-scopes the work.

This script closes that gap: one read-only query per structural claim, run against a real tenant,
so each `[CODE]` verdict gains a paired `[RUNTIME]` row. Every query is a SELECT; nothing here
writes, and it is safe to run against production.

    python scripts/runtime_receipts.py                     # every org
    python scripts/runtime_receipts.py --org org_abc123    # one tenant
    python scripts/runtime_receipts.py --json              # machine-readable

Exit code is 1 when any receipt FAILS, so it can gate a release.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass
from typing import Callable

from sqlalchemy import text

from genios_engine.platform.db import get_engine


from genios_engine.platform.receipts import (  # noqa: E402,F401
    RECEIPT_STATUSES, evaluate, receipts)

#: Four characters each, so the columns line up whatever the status is.
_MARKS = {"PASS": "PASS", "FAIL": "FAIL", "ERROR": "ERR ", "NOT_EXERCISED": "N/EX"}


def run(org: str | None, as_json: bool) -> int:
    url = os.environ.get("GENIOS_DATABASE_URL") or os.environ.get("DATABASE_URL")
    if not url:
        print("GENIOS_DATABASE_URL is not set", file=sys.stderr)
        return 2

    engine = get_engine(url)
    rows = evaluate(engine, org)

    if as_json:
        print(json.dumps({"org": org, "receipts": rows}, indent=2, default=str))
    else:
        scope = org or "ALL ORGS"
        print(f"\nRUNTIME RECEIPTS — {scope}\n" + "=" * 78)
        layer = None
        for r in rows:
            if r["layer"] != layer:
                layer = r["layer"]
                print(f"\n{layer}")
            # ⛔ FOUR MARKS, AND THE SET COMES FROM `RECEIPT_STATUSES`. This was a literal
            # `{"PASS": …, "FAIL": …, "ERROR": …}[status]`, which RAISES `KeyError` on a status it
            # has not met — so `3.2`'s `NOT_EXERCISED` would have crashed the release gate rather
            # than disagreed with it.
            mark = _MARKS.get(r["status"], r["status"][:4].upper())
            print(f"  [{mark}] {r['claim']:<52} = {r['value']}")
            if r["status"] != "PASS" and r["detail"]:
                print(f"         {r['detail']}")
        failed = sum(1 for r in rows if r["status"] in ("FAIL", "ERROR"))
        unexercised = sum(1 for r in rows if r["status"] == "NOT_EXERCISED")
        print("\n" + "=" * 78)
        print(f"{len(rows) - failed - unexercised}/{len(rows)} receipts pass"
              + (f" — {failed} FAILING" if failed else "")
              + (f" — ⛔ {unexercised} NOT EXERCISED (a pass over an empty table is not a pass)"
                 if unexercised else ""))

    # ⛔ READY IS THE TABLE'S ANSWER, NOT THIS SCRIPT'S. The release gate and `/readiness` read the
    # same `RECEIPT_STATUSES`, which is what the endpoint's docstring promises.
    return 0 if all(RECEIPT_STATUSES.get(r["status"], (False, ""))[0] for r in rows) else 1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--org", default=None, help="restrict to one tenant")
    ap.add_argument("--json", action="store_true", dest="as_json")
    a = ap.parse_args()
    return run(a.org, a.as_json)


if __name__ == "__main__":
    raise SystemExit(main())
