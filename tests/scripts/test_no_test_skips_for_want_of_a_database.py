"""STEP-17 §3.1 · in the database job, a test that skips for want of a database is a failure.

    .venv/bin/python -m pytest -q tests/scripts/test_no_test_skips_for_want_of_a_database.py

`yc2_w27_s17` M40.C4.L-contract.V0.U01. Measured at `c97155cd`: CI's hermetic job skipped **2,088**
tests in **330** files for want of a database, and 324 of those files ran in no job at all. The
database job runs them — and this scan is what makes "they ran" checkable: it reads the job's pytest
log (`-rs` summary lines) and exits 1 naming every test that still skipped for want of a database.
A log that is not a finished pytest run, or one whose skips were not reported, is an error (exit
2), never a pass: *a skip is not a pass, and an unread log is not a clean one.*

`M40.C4.L-contract.V0.U03` (S17X-F1): a log is a finished run only if it PASSED more than the floor
(`PASSED_FLOOR`). The collect-only line — `20689/20800 tests collected (111 deselected) in 31.20s` —
read as a finished run with no skips, exit 0: a `PYTEST_ADDOPTS=--co` written to `$GITHUB_ENV`, or a
`--co` in `addopts`, turned the database job green after running nothing. A collection, a run where
no test ran, one where every test was deselected, and one narrowed below the floor are each exit 2.
"""
from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "qa" / "database_skips.py"


def _module():
    spec = importlib.util.spec_from_file_location("database_skips", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


#: The script's own floor, read from it — a log below it is not the database suite.
FLOOR = _module().PASSED_FLOOR
#: A number a finished database run clears.
RUN = FLOOR + 1

GREEN = f"........ [100%]\n{RUN} passed in 3.21s\n"
DB_SKIPS = (".s.s [100%]\n"
            "SKIPPED [1] tests/test_moments_pg.py:41: GENIOS_TEST_DATABASE_URL not set\n"
            "SKIPPED [3] tests/context/test_x.py:12: no scratch database configured\n"
            "SKIPPED [2] tests/reason/test_y.py:9: needs real Postgres\n"
            "SKIPPED [1] tests/test_docs.py:68: could not import 'docx': No module named 'docx'\n"
            f"{RUN} passed, 7 skipped in 2.00s\n")
OTHER_SKIPS = (".s [100%]\n"
               "SKIPPED [1] tests/test_docs.py:68: could not import 'docx': No module named 'docx'\n"
               "SKIPPED [1] tests/platform/test_rollback.py:72: 0080_l1.sql is a declared exception\n"
               f"{RUN} passed, 2 skipped in 1.00s\n")


def _scan(tmp_path, text: str):
    log = tmp_path / "pytest.log"
    log.write_text(text, encoding="utf-8")
    return subprocess.run([sys.executable, str(SCRIPT), str(log)], capture_output=True, text=True)


def test_a_clean_run_passes(tmp_path):
    r = _scan(tmp_path, GREEN)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "0 tests skipped for want of a database" in r.stdout


def test_a_skip_for_want_of_a_database_fails_and_is_named(tmp_path):
    r = _scan(tmp_path, DB_SKIPS)
    assert r.returncode == 1, r.stdout + r.stderr
    assert "6 tests skipped for want of a database, in 3 files" in r.stdout
    for where in ("tests/test_moments_pg.py:41", "tests/context/test_x.py:12",
                  "tests/reason/test_y.py:9"):
        assert where in r.stdout
    assert "test_docs.py" not in r.stdout, "a skip for another reason is not this scan's"


def test_a_skip_for_another_reason_is_not_counted(tmp_path):
    r = _scan(tmp_path, OTHER_SKIPS)
    assert r.returncode == 0, r.stdout + r.stderr


def test_a_log_that_is_not_a_finished_run_is_an_error(tmp_path):
    r = _scan(tmp_path, "........\nKeyboardInterrupt\n")
    assert r.returncode == 2 and "no pytest summary" in (r.stdout + r.stderr)


def test_skips_that_were_not_reported_are_an_error(tmp_path):
    """`7 skipped` with no SKIPPED lines: the run left out `-rs`, and its skips cannot be read."""
    r = _scan(tmp_path, f".s.s [100%]\n{RUN} passed, 7 skipped in 2.00s\n")
    assert r.returncode == 2 and "-rs" in (r.stdout + r.stderr)


def test_a_missing_log_is_an_error(tmp_path):
    r = subprocess.run([sys.executable, str(SCRIPT), str(tmp_path / "nope.log")],
                       capture_output=True, text=True)
    assert r.returncode == 2


# ── M40.C4.L-contract.V0.U03 (S17X-F1): a finished run passed more than the floor ────────────────


@pytest.mark.parametrize("summary", [
    "20689/20800 tests collected (111 deselected) in 31.20s",   # the crosscheck's own line
    "20800 tests collected in 31.20s",
    "1 test collected in 0.10s",
    "no tests collected in 0.10s",
])
def test_a_collection_is_not_a_run(tmp_path, summary):
    """`--co` from `$GITHUB_ENV` or `addopts`: pytest exits 0 having run nothing."""
    r = _scan(tmp_path, f"tests/test_a.py::test_one\n\n{summary}\n")
    assert r.returncode == 2, r.stdout + r.stderr
    assert "is a collection, not a run" in r.stdout + r.stderr


@pytest.mark.parametrize("summary", ["no tests ran in 0.01s", "20800 deselected in 3.10s"])
def test_a_run_where_no_test_ran_is_an_error(tmp_path, summary):
    r = _scan(tmp_path, f"\n{summary}\n")
    assert r.returncode == 2, r.stdout + r.stderr
    assert f"{FLOOR:,}" in r.stdout + r.stderr or "no tests ran" in r.stdout + r.stderr


def test_a_run_narrowed_to_the_floor_is_not_the_database_suite(tmp_path):
    """A path, a `-k`, a `--deselect`: green, no skip — and far fewer tests than the suite has."""
    r = _scan(tmp_path, f"........ [100%]\n{FLOOR} passed, 3 deselected in 9.00s\n")
    assert r.returncode == 2, r.stdout + r.stderr
    assert f"passed {FLOOR:,}" in r.stdout + r.stderr and f"{FLOOR:,}" in r.stdout + r.stderr
    assert _scan(tmp_path, f"........ [100%]\n{RUN} passed, 3 deselected in 9.00s\n").returncode == 0


def test_a_red_run_over_the_floor_still_reads_its_skips(tmp_path):
    """The scan runs when the suite failed too (`if: success() || failure()`): failures do not hide
    its skips, and a red run that passed enough is still read."""
    r = _scan(tmp_path, ("F.s [100%]\nSKIPPED [1] tests/test_moments_pg.py:41: GENIOS_TEST_DATABASE_URL not set\n"
                         f"2 failed, {RUN} passed, 1 skipped in 9.00s\n"))
    assert r.returncode == 1 and "tests/test_moments_pg.py:41" in r.stdout, r.stdout + r.stderr


def test_the_floor_sits_between_the_hermetic_suite_and_the_database_suite():
    """Measured: the hermetic suite — no database test runs — passed 18,013 at `7766a06a`; the
    database suite 20,569 at `c97155cd` (STEP-17 §2) and the whole suite 20,868 at `ae24ee22`. A
    database run that ran none of its database tests cannot clear the floor; a real one does."""
    assert 18_013 < FLOOR < 20_569, FLOOR
