"""STEP-01 · CI runs the golden set on Postgres on every push — and the hermetic job leaves it out.

    pytest tests/test_ci_runs_the_golden_set_on_postgres.py -q

Read from the workflow file itself, so the guarantee is the file's and not a comment's. It first
runs when the batch is pushed (06-DECISIONS D10).
"""
from __future__ import annotations

from pathlib import Path

import yaml

CI = Path(__file__).resolve().parents[1] / ".github" / "workflows" / "ci.yml"


def _workflow() -> dict:
    return yaml.safe_load(CI.read_text(encoding="utf-8"))


def _runs(job: dict) -> list[str]:
    return [str(step.get("run") or "") for step in job.get("steps") or ()]


def test_the_hermetic_job_deselects_the_golden_set():
    runs = _runs(_workflow()["jobs"]["test"])
    pytest_runs = [r for r in runs if r.strip().startswith("pytest")]
    assert pytest_runs and all('-m "not golden"' in r for r in pytest_runs), pytest_runs


def test_the_hermetic_job_installs_production_dependencies():
    """A test that needs a package production ships must run in CI, not die at its import.

    The job installed `.[dev]` alone. On Python 3.12 with that install — the job's own — seven tests
    fail at an import of a package `requirements.txt` ships: the six of
    `tests/test_office_extraction.py` (openpyxl, python-pptx; the file came in on 2026-09-10) and
    the runner's door test in `tests/replays/test_engine_runner.py` (anthropic).
    """
    runs = _runs(_workflow()["jobs"]["test"])
    assert any("requirements.txt" in r for r in runs), runs


def test_a_golden_job_runs_on_a_postgres_17_service():
    job = _workflow()["jobs"]["golden-pg"]
    service = job["services"]["postgres"]
    assert str(service["image"]).startswith("postgres:17")
    url = job["env"]["GENIOS_TEST_DATABASE_URL"]
    assert url.startswith("postgresql+psycopg://") and "localhost:5432" in url, url
    assert service["env"]["POSTGRES_DB"] in url and service["env"]["POSTGRES_PASSWORD"] in url


def test_the_golden_job_never_skips():
    assert str(_workflow()["jobs"]["golden-pg"]["env"]["GENIOS_GOLDEN_REQUIRED"]) == "1"


def test_the_golden_job_runs_the_set_and_the_board_it_is_held_to():
    runs = _runs(_workflow()["jobs"]["golden-pg"])
    assert any(r.startswith("pytest") and "tests/replays" in r for r in runs), runs
    assert any("scripts/golden_score.py" in r and "--assert-recorded" in r for r in runs), runs
    assert any("requirements.txt" in r for r in runs), "the golden set runs on production's deps"


def test_the_golden_marker_is_registered():
    pyproject = (CI.parents[2] / "pyproject.toml").read_text(encoding="utf-8")
    assert '"golden:' in pyproject, "--strict-markers would reject an unregistered marker"


def test_a_red_pytest_step_names_its_failures_where_anyone_can_read_them():
    """`YC-II W27/03` F138 · run `37924361307` (9 Oct): the hermetic job went red after 46 minutes and
    nobody without a signed-in GitHub account could read which tests failed — the job log needs a
    login (the API answers 403). Annotations do not: each pytest step turns its FAILED/ERROR lines
    into `::error` annotations, which `GET /repos/{repo}/check-runs/{job_id}/annotations` returns to
    anyone — and the step still exits with pytest's own code."""
    for job in ("test", "golden-pg"):
        steps = [s for s in _workflow()["jobs"][job]["steps"]
                 if str(s.get("run") or "").strip().startswith("pytest")]
        assert steps, job
        for step in steps:
            run = str(step["run"])
            assert "-rfE" in run, (job, "the summary lines the annotations are cut from")
            assert "::error" in run and "^(FAILED|ERROR) " in run, (job, run)
            assert "exit $status" in run and "status=$?" in run, (job, "a red pytest stays red")
            assert step.get("shell") == "bash", (job, "the exit-code capture is bash")
