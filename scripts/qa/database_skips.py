#!/usr/bin/env python3
"""Fail when a test skipped in the job that HAS a database — for any reason but the allowed ones.

    python scripts/qa/database_skips.py pytest.log

STEP-17 §3.1 (`yc2_w27_s17` M40.C4.L-contract.V0.U01). Measured at `c97155cd`: CI's hermetic job
skipped 2,088 tests in 330 files for want of a database. The `database` job gives them one; this
reads that job's pytest log — its `-rs` summary lines, `SKIPPED [n] path:line: reason` — and names
every test that STILL skipped. A pass over an empty table is not a pass, and a database suite that
skipped is one.

INVERTED (`M40.C4.L-contract.V0.U05`, S17X-F2): the scan first recognised a skip for want of a
database by its wording — `GENIOS_TEST_DATABASE_URL`, "database", "Postgres" — and 51 database-gated
`pytest.skip` calls in 27 files say something else ("0043 not applied", "no org", "graph store not
configured", "no scratch org seeded"): each would have skipped in the database job and passed it.
Now the job allows exactly the skips a real database run has for a reason that is not a database
(`ALLOWED`, each by its file AND its reason), and every other skip fails it, named.

Exit 0: none but the allowed. Exit 1: some, each named. Exit 2: the log cannot answer — it is missing, it is not a
finished pytest run, or it counts skips it did not report (run pytest with `-rs`). Reads a file and
nothing else: no database, no network.

A finished run is one that PASSED more than `PASSED_FLOOR` tests (`M40.C4.L-contract.V0.U03`,
S17X-F1). pytest's collect-only line — `20689/20800 tests collected (111 deselected) in 31.20s` — read
as a finished run with no skips, so a `--co` from `$GITHUB_ENV` or from `addopts` made the database
job green after running nothing. A collection, a run where no test ran, one where every test was
deselected, and one narrowed below the floor (a path, `-k`, `--deselect`) are each exit 2.
"""
from __future__ import annotations

import re
import sys
from collections import Counter
from pathlib import Path

#: The skips the database job allows: `(test file, its reason as a full regex, why)`. Measured on a
#: real database run — s13f4's whole suite on Postgres at `ae24ee22`, 20,868 passed and four
#: skipped. A skip is allowed only by its file and its reason together; adding a fourth is a
#: decision, measured the same way, its reason not a database, and
#: `tests/scripts/test_no_test_skips_for_want_of_a_database.py` names the three on purpose.
#:
#: ⛔ F-4 (`yc2_w27_s1718` M40.C4.L-contract.V0.U07, second crosscheck): a fourth skip was ALLOWED
#: here — `tests/test_health_memory.py`, "internal auth not wired in this harness (403)" — and its
#: reason was false. The test set the internal token on the CACHED `Settings` instance and then
#: called `cache_clear()`; `platform/auth` binds `get_settings` at its own import
#: (`from platform.config import get_settings`), so patching `platform.config.get_settings`
#: afterwards never reached `require_internal`, which read a FRESH, token-less `Settings`. Fixed
#: at the test (it now patches where auth reads it) — the skip never fires on a real database run,
#: and the entry comes off: a false reason is not a database reason either.
ALLOWED: tuple[tuple[str, str, str], ...] = (
    ("tests/capture/transcripts/test_transcript_units.py",
     r"could not import 'docx': No module named 'docx'",
     "python-docx is missing from a local venv; CI installs requirements.txt, which pins it, so "
     "there the test runs"),
    ("tests/contracts/test_l1_contracts.py",
     r"got empty parameter set for \(lane\)",
     "UNTYPED_LANES is derived from ExtractionResult and is empty once every lane is typed — the "
     "parametrize shrinks by itself, by design"),
    ("tests/platform/test_the_code_can_always_be_rolled_back.py",
     r"0080_l1_extraction_results\.sql is a declared exception — see DECLARED_EXCEPTIONS",
     "0080 is the declared rollback exception (DECLARED_EXCEPTIONS) — its check does not apply, "
     "by decision"),
)

#: A database run that passed this many tests or fewer is not the database suite — it was narrowed,
#: collected only, or ran none of its database tests. Measured: the hermetic suite, which runs no
#: database test, passed 18,013 at `7766a06a`; the database suite passed 20,569 at `c97155cd`
#: (STEP-17 §2) and the whole suite 20,868 at `ae24ee22`. The floor sits between the two. Raise it as
#: the suite grows; lower it only with the measurement that says why, never to make a run pass.
PASSED_FLOOR = 19_000

_SKIPPED = re.compile(r"^SKIPPED \[(\d+)\] (\S+?): (.*)$")
_SUMMARY = re.compile(r"\b\d+ (?:passed|failed|errors?|skipped|xfailed|deselected)\b.* in [\d.]+s"
                      r"|\b(?:no tests ran|collected)\b.* in [\d.]+s")
_COLLECTED = re.compile(r"\bcollected\b")
_PASSED = re.compile(r"\b(\d+) passed\b")
_SKIP_COUNT = re.compile(r"\b(\d+) skipped\b")


def scan(text: str) -> tuple[int, str]:
    """``(exit code, report)`` for one pytest log."""
    lines = text.splitlines()
    summary = next((line for line in reversed(lines) if _SUMMARY.search(line)), None)
    if summary is None:
        return 2, "no pytest summary line — this log is not a finished pytest run"
    if _COLLECTED.search(summary):
        return 2, (f"this log is a collection, not a run ({summary.strip()}) — `--co` came from "
                   "the command, `addopts` or PYTEST_ADDOPTS, and nothing ran")
    passed = _PASSED.search(summary)
    passed = int(passed.group(1)) if passed else 0
    if passed <= PASSED_FLOOR:
        return 2, (f"the run passed {passed:,} test(s), not more than the floor of {PASSED_FLOOR:,} "
                   f"({summary.strip()}) — no tests ran, or a path, -k, --deselect or second -m "
                   "narrowed it: this log is not the database suite")
    skipped = [m for m in (_SKIPPED.match(line) for line in lines) if m]
    counted = _SKIP_COUNT.search(summary)
    if counted and int(counted.group(1)) and not skipped:
        return 2, (f"the run skipped {counted.group(1)} test(s) and reported none of them — run "
                   "pytest with -rs so a skip says why")
    refused = [m for m in skipped if not _allowed(m.group(2).rsplit(":", 1)[0], m.group(3))]
    tests = sum(int(m.group(1)) for m in refused)
    allowed = sum(int(m.group(1)) for m in skipped) - tests
    files = Counter(m.group(2).rsplit(":", 1)[0] for m in refused)
    head = f"{tests} tests skipped for a reason the database job does not allow"
    tail = f"{allowed} allowed — a measured reason that is not a database (ALLOWED)"
    if not refused:
        return 0, f"{head}; {tail}"
    return 1, "\n".join([f"{head}, in {len(files)} files; {tail}:"]
                        + [f"  {m.group(2)} ×{m.group(1)}: {m.group(3)}" for m in refused])


def _allowed(path: str, reason: str) -> bool:
    """Whether ALLOWED holds this skip — its file and its whole reason, together."""
    return any(path == file and re.fullmatch(pattern, reason.strip())
               for file, pattern, _why in ALLOWED)


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
