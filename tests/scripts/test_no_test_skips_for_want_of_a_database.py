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

`M40.C4.L-contract.V0.U05` (S17X-F2): the scan is INVERTED. It recognised a skip for want of a
database by its wording (`GENIOS_TEST_DATABASE_URL`, "database", "Postgres"), and 51 database-gated
`pytest.skip` calls in 27 files use other words — "0043 not applied", "no org", "graph store not
configured", "no scratch org seeded". Now the database job allows exactly the skips measured on a
real database run for a reason that is not a database (`ALLOWED`: python-docx missing, an empty
parameter set, the declared rollback exception 0080), each by its file AND its reason; every other
skip fails the job, named.

`M40.C4.L-contract.V0.U07` (F-4, second crosscheck): a fourth entry, `tests/test_health_memory.py`'s
"internal auth not wired in this harness (403)", came off ALLOWED — that 403 was the test's own
bug (it patched `platform.config.get_settings`, not `platform.auth.get_settings`, which is where
`require_internal` actually reads it), fixed at the test. A real database run no longer skips it.

`M40.C4.L-contract.V0.U06` (F-2, second crosscheck): `PASSED_FLOOR` sat about 750 passes above the
hermetic count it exists to exceed, as a bare literal nobody's upkeep touched (the hermetic count
itself grew from 18,013 to 18,674 between STEP-17 and the STEP-17/18 merge, +661, and nothing read
that growth). The floor is now checked against its own named, re-measurable constants
(`RECORDED_HERMETIC_PASSED`, `RECORDED_DATABASE_SUITE_PASSED`), never a literal in the test; and
`narrowing_conftest_hooks` guards the scan's own blind spot — it reads only a pytest summary LINE,
so a `conftest.py` that narrowed collection upstream would never show up in it.
"""
from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "qa" / "database_skips.py"
REPO_ROOT = SCRIPT.parents[2]


def _module():
    spec = importlib.util.spec_from_file_location("database_skips", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


#: The script's own floor, read from it — a log below it is not the database suite.
FLOOR = _module().PASSED_FLOOR
#: A number a finished database run clears.
RUN = FLOOR + 1

#: The three skips of a real database run, as pytest printed them — s13f4's whole suite on
#: Postgres at `ae24ee22` (20,868 passed, 4 skipped the day this was measured — the fourth,
#: test_health_memory.py's 403, was its own bug (F-4): fixed, it no longer skips at all).
MEASURED = (
    "SKIPPED [1] tests/capture/transcripts/test_transcript_units.py:68: could not import 'docx': "
    "No module named 'docx'\n"
    "SKIPPED [1] tests/contracts/test_l1_contracts.py:630: got empty parameter set for (lane)\n"
    "SKIPPED [1] tests/platform/test_the_code_can_always_be_rolled_back.py:72: "
    "0080_l1_extraction_results.sql is a declared exception — see DECLARED_EXCEPTIONS\n")

GREEN = f"........ [100%]\n{RUN} passed in 3.21s\n"
DB_SKIPS = (".s.s [100%]\n"
            "SKIPPED [1] tests/test_moments_pg.py:41: GENIOS_TEST_DATABASE_URL not set\n"
            "SKIPPED [3] tests/context/test_x.py:12: no scratch database configured\n"
            "SKIPPED [2] tests/reason/test_y.py:9: needs real Postgres\n"
            "SKIPPED [1] tests/capture/transcripts/test_transcript_units.py:68: could not import "
            "'docx': No module named 'docx'\n"
            f"{RUN} passed, 7 skipped in 2.00s\n")
OTHER_SKIPS = (".s [100%]\n" + MEASURED + f"{RUN} passed, 3 skipped in 1.00s\n")
#: The crosscheck's own examples: database-gated skips in words the old scan did not know.
IN_OTHER_WORDS = (".s [100%]\n"
                  "SKIPPED [1] tests/test_delivery_facts.py:53: 0043 not applied\n"
                  "SKIPPED [1] tests/test_delivery_facts.py:56: no org\n"
                  "SKIPPED [3] tests/platform/test_warm_lane_pg.py:273: graph store not configured\n"
                  "SKIPPED [1] tests/context/test_point_in_time.py:180: no scratch org seeded — "
                  "nothing to clone a tenant from\n"
                  f"{RUN} passed, 6 skipped in 1.00s\n")


def _scan(tmp_path, text: str):
    log = tmp_path / "pytest.log"
    log.write_text(text, encoding="utf-8")
    return subprocess.run([sys.executable, str(SCRIPT), str(log)], capture_output=True, text=True)


def test_a_clean_run_passes(tmp_path):
    r = _scan(tmp_path, GREEN)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "0 tests skipped for a reason the database job does not allow" in r.stdout


def test_a_skip_for_want_of_a_database_fails_and_is_named(tmp_path):
    r = _scan(tmp_path, DB_SKIPS)
    assert r.returncode == 1, r.stdout + r.stderr
    assert "6 tests skipped for a reason the database job does not allow, in 3 files" in r.stdout
    for where in ("tests/test_moments_pg.py:41", "tests/context/test_x.py:12",
                  "tests/reason/test_y.py:9"):
        assert where in r.stdout
    assert "test_transcript_units.py:68 ×1" not in r.stdout, "an allowed skip is not named a failure"


def test_the_skips_a_real_database_run_has_are_allowed(tmp_path):
    r = _scan(tmp_path, OTHER_SKIPS)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "0 tests skipped for a reason the database job does not allow" in r.stdout
    assert "3 allowed" in r.stdout, r.stdout


def test_a_database_skip_in_other_words_fails_and_is_named(tmp_path):
    """S17X-F2: the old scan read these four reasons as "another reason" and passed the job."""
    r = _scan(tmp_path, IN_OTHER_WORDS)
    assert r.returncode == 1, r.stdout + r.stderr
    assert "6 tests skipped for a reason the database job does not allow, in 3 files" in r.stdout
    for where in ("tests/test_delivery_facts.py:53", "tests/test_delivery_facts.py:56",
                  "tests/platform/test_warm_lane_pg.py:273", "tests/context/test_point_in_time.py:180"):
        assert where in r.stdout, where


@pytest.mark.parametrize("line", [
    # an allowed reason, in a file the allow-list does not name
    "SKIPPED [1] tests/test_moments_pg.py:41: got empty parameter set for (lane)",
    "SKIPPED [1] tests/test_x.py:9: could not import 'docx': No module named 'docx'",
    # F-4: ALLOWED until the second crosscheck, and for a reason it never named (500, not 403) —
    # now not a file the list names at all; either way, still refused
    "SKIPPED [1] tests/test_health_memory.py:97: internal auth not wired in this harness (500)",
    "SKIPPED [1] tests/contracts/test_l1_contracts.py:40: GENIOS_TEST_DATABASE_URL not set",
    "SKIPPED [1] tests/contracts/test_l1_contracts.py:640: got empty parameter set for (field)",
    "SKIPPED [1] tests/platform/test_the_code_can_always_be_rolled_back.py:72: "
    "0211_a_followup_names_its_observation.sql is a declared exception — see DECLARED_EXCEPTIONS",
    "SKIPPED [1] tests/capture/transcripts/test_transcript_units.py:68: could not import 'pypdf': "
    "No module named 'pypdf'",
])
def test_a_skip_is_allowed_only_by_its_file_and_its_reason_together(tmp_path, line):
    r = _scan(tmp_path, f".s [100%]\n{line}\n{RUN} passed, 1 skipped in 1.00s\n")
    assert r.returncode == 1, r.stdout + r.stderr
    assert line.split("] ", 1)[1].split(": ", 1)[0] in r.stdout


def test_the_allow_list_is_the_three_measured_and_each_says_why():
    """Adding a fourth is a decision — measured on a real database run, its reason not a database
    — and made here on purpose. Each entry names a file that exists and says why it may skip.

    F-4 (second crosscheck): `tests/test_health_memory.py` is NOT here any more — its 403 was the
    test's own bug (it patched the wrong module's `get_settings`), fixed at the test, not declared
    away."""
    allowed = _module().ALLOWED
    root = SCRIPT.parents[2]
    assert [entry[0] for entry in allowed] == [
        "tests/capture/transcripts/test_transcript_units.py",
        "tests/contracts/test_l1_contracts.py",
        "tests/platform/test_the_code_can_always_be_rolled_back.py",
    ]
    for path, _reason, why in allowed:
        assert (root / path).is_file(), path
        assert len(why.split()) >= 5, (path, why)


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


def test_the_floor_exceeds_the_recorded_hermetic_count():
    """F-2 (`yc2_w27_s1718` M40.C4.L-contract.V0.U06, second crosscheck): no literal here — the
    floor is read against the module's OWN recorded counts, so a floor that falls behind a
    re-measured (grown) hermetic count fails this test rather than silently passing a run that
    collected almost nothing. A database run that ran none of its database tests cannot clear the
    floor; a real one does."""
    module = _module()
    assert module.PASSED_FLOOR > module.RECORDED_HERMETIC_PASSED > 0
    assert module.PASSED_FLOOR <= module.RECORDED_DATABASE_SUITE_PASSED


def test_no_conftest_in_this_repo_narrows_collection():
    """F-2: `scan` only ever reads a pytest SUMMARY LINE — a `conftest.py` that narrowed
    collection upstream (`collect_ignore`, `pytest_collection_modifyitems`, …) would turn the
    database job green over fewer tests than it thinks it ran, and this scan would never see it.
    Measured 14 Oct: none of the repo's 9 `conftest.py` files defines one."""
    found = _module().narrowing_conftest_hooks(REPO_ROOT)
    assert found == [], f"{len(found)} conftest hook(s) could narrow collection: {found}"


def test_the_guard_catches_a_conftest_that_narrows_collection(tmp_path):
    """The rule, proven on synthetic files: a narrowing hook or assignment — plain or annotated —
    is caught; an ordinary fixture-only conftest is not."""
    (tmp_path / "conftest.py").write_text(
        "import pytest\n"
        "collect_ignore = ['test_slow.py']\n"
        "def pytest_collection_modifyitems(config, items):\n    pass\n"
        "@pytest.fixture\ndef clean():\n    return None\n")
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "conftest.py").write_text(
        "import pytest\n@pytest.fixture(autouse=True)\ndef db():\n    yield\n")
    annotated = tmp_path / "annotated"
    annotated.mkdir()
    (annotated / "conftest.py").write_text("collect_ignore_glob: list[str] = ['test_*_slow.py']\n")
    found = _module().narrowing_conftest_hooks(tmp_path)
    assert sorted(n.split(": ", 1)[1] for n in found) == [
        "collect_ignore", "collect_ignore_glob", "pytest_collection_modifyitems"]
    assert _module().narrowing_conftest_hooks(sub) == []
    assert [n.split(": ", 1)[1] for n in _module().narrowing_conftest_hooks(annotated)] == [
        "collect_ignore_glob"]
