#!/usr/bin/env python3
"""Fail when a test skipped for want of a database — in the job that HAS one.

    python scripts/qa/database_skips.py pytest.log

STEP-17 §3.1 (`yc2_w27_s17` M40.C4.L-contract.V0.U01). Measured at `c97155cd`: CI's hermetic job
skipped 2,088 tests in 330 files for want of a database. The `database` job gives them one; this
reads that job's pytest log — its `-rs` summary lines, `SKIPPED [n] path:line: reason` — and names
every test that STILL skipped for want of it. A pass over an empty table is not a pass, and a
database suite that skipped is one.

Exit 0: none. Exit 1: some, each named. Exit 2: the log cannot answer — it is missing, it is not a
finished pytest run, or it counts skips it did not report (run pytest with `-rs`). Reads a file and
nothing else: no database, no network.
"""
from __future__ import annotations

import re
import sys
from collections import Counter
from pathlib import Path

#: A skip whose reason names the database it lacked. Measured on the hermetic log: every one of the
#: 2,088 says `GENIOS_TEST_DATABASE_URL`, "database" or "Postgres"; none of the other four does.
FOR_WANT_OF_A_DATABASE = re.compile(r"GENIOS_TEST_DATABASE_URL|\bdatabase\b|postgres", re.I)

_SKIPPED = re.compile(r"^SKIPPED \[(\d+)\] (\S+?): (.*)$")
_SUMMARY = re.compile(r"\b\d+ (?:passed|failed|errors?|skipped|xfailed|deselected)\b.* in [\d.]+s")
_SKIP_COUNT = re.compile(r"\b(\d+) skipped\b")


def scan(text: str) -> tuple[int, str]:
    """``(exit code, report)`` for one pytest log."""
    lines = text.splitlines()
    summary = next((line for line in reversed(lines) if _SUMMARY.search(line)), None)
    if summary is None:
        return 2, "no pytest summary line — this log is not a finished pytest run"
    skipped = [m for m in (_SKIPPED.match(line) for line in lines) if m]
    counted = _SKIP_COUNT.search(summary)
    if counted and int(counted.group(1)) and not skipped:
        return 2, (f"the run skipped {counted.group(1)} test(s) and reported none of them — run "
                   "pytest with -rs so a skip says why")
    wanting = [m for m in skipped if FOR_WANT_OF_A_DATABASE.search(m.group(3))]
    tests = sum(int(m.group(1)) for m in wanting)
    files = Counter(m.group(2).rsplit(":", 1)[0] for m in wanting)
    head = f"{tests} tests skipped for want of a database"
    if not wanting:
        return 0, head
    return 1, "\n".join([f"{head}, in {len(files)} files:"]
                        + [f"  {m.group(2)} ×{m.group(1)}: {m.group(3)}" for m in wanting])


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(__doc__.strip().splitlines()[2].strip(), file=sys.stderr)
        return 2
    path = Path(argv[1])
    if not path.is_file():
        print(f"no log at {path}", file=sys.stderr)
        return 2
    code, report = scan(path.read_text(encoding="utf-8", errors="replace"))
    print(report)
    return code


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
