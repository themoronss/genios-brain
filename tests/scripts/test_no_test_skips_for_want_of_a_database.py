"""STEP-17 §3.1 · in the database job, a test that skips for want of a database is a failure.

    .venv/bin/python -m pytest -q tests/scripts/test_no_test_skips_for_want_of_a_database.py

`yc2_w27_s17` M40.C4.L-contract.V0.U01. Measured at `c97155cd`: CI's hermetic job skipped **2,088**
tests in **330** files for want of a database, and 324 of those files ran in no job at all. The
database job runs them — and this scan is what makes "they ran" checkable: it reads the job's pytest
log (`-rs` summary lines) and exits 1 naming every test that still skipped for want of a database.
A log that is not a finished pytest run, or one whose skips were not reported, is an error (exit
2), never a pass: *a skip is not a pass, and an unread log is not a clean one.*
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "qa" / "database_skips.py"

GREEN = "........ [100%]\n12 passed in 3.21s\n"
DB_SKIPS = (".s.s [100%]\n"
            "SKIPPED [1] tests/test_moments_pg.py:41: GENIOS_TEST_DATABASE_URL not set\n"
            "SKIPPED [3] tests/context/test_x.py:12: no scratch database configured\n"
            "SKIPPED [2] tests/reason/test_y.py:9: needs real Postgres\n"
            "SKIPPED [1] tests/test_docs.py:68: could not import 'docx': No module named 'docx'\n"
            "10 passed, 7 skipped in 2.00s\n")
OTHER_SKIPS = (".s [100%]\n"
               "SKIPPED [1] tests/test_docs.py:68: could not import 'docx': No module named 'docx'\n"
               "SKIPPED [1] tests/platform/test_rollback.py:72: 0080_l1.sql is a declared exception\n"
               "5 passed, 2 skipped in 1.00s\n")


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
    r = _scan(tmp_path, ".s.s [100%]\n10 passed, 7 skipped in 2.00s\n")
    assert r.returncode == 2 and "-rs" in (r.stdout + r.stderr)


def test_a_missing_log_is_an_error(tmp_path):
    r = subprocess.run([sys.executable, str(SCRIPT), str(tmp_path / "nope.log")],
                       capture_output=True, text=True)
    assert r.returncode == 2
