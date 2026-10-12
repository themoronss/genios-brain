"""STEP-17 §3.1 · CI runs the whole suite on Postgres, on production's Python.

    .venv/bin/python -m pytest -q tests/test_ci_runs_the_database_suite.py

`yc2_w27_s17` M40.C4.L-integration.V1.U02. Read from the workflow file itself, so the guarantee is the
file's and not a comment's (the shape of `tests/test_ci_runs_the_golden_set_on_postgres.py`).

⛔ WHY. Measured at `c97155cd`: CI's hermetic job skipped 2,088 tests in 330 files for want of a
database; `golden-pg` ran six of those files; **324 ran nowhere**. And production runs Python 3.11
(`Dockerfile`), CI ran 3.12, the laptop 3.13 — one guard already answered differently on 3.13
(`03` F35). So: a `database` job — a Postgres 17 service, production's dependency set, the whole suite
but the golden set, and a scan that fails it on any skip for want of a database — and every job on
the Dockerfile's own Python, read from the Dockerfile so the two cannot drift.

A database job can be green over nothing in more ways than a missing service, and each is closed
here: a second `-m` after the first (pytest keeps the last, so `-m "not pg"` would deselect every
database test and the scan would find no skip), a `PYTEST_ADDOPTS` in an env block, a
`continue-on-error`, anything after the scan that turns its exit 1 into a 0, an `if:` that skips the
job, a golden test outside the paths `golden-pg` runs.
"""
from __future__ import annotations

import ast
import re
import shlex
import tomllib
from pathlib import Path

import yaml
from sqlalchemy.engine import make_url

ROOT = Path(__file__).resolve().parents[1]
CI = ROOT / ".github" / "workflows" / "ci.yml"

#: The database job's suite, exactly: no path, no `-k`, no second `-m` — the whole suite but the
#: golden set — with every skip reported (`s` in `-rfEs`) so the scan can read why each one skipped.
SUITE = 'pytest -q -m "not golden" -rfEs > pytest.log 2>&1 && status=0 || status=$?'
#: The scan, exactly: it reads the log the suite wrote, and nothing after it can turn its exit 1 into
#: a 0 (`|| true`, `; exit 0`).
SCAN = "python scripts/qa/database_skips.py pytest.log"


def _workflow() -> dict:
    return yaml.safe_load(CI.read_text(encoding="utf-8"))


def _steps(job: str) -> list[dict]:
    return list(_workflow()["jobs"][job].get("steps") or ())


def _run(step: dict) -> str:
    return str(step.get("run") or "")


def _suite_step(job: str) -> dict:
    steps = [s for s in _steps(job) if _run(s).lstrip().startswith("pytest")]
    assert len(steps) == 1, (job, [s.get("name") or s.get("uses") for s in _steps(job)])
    return steps[0]


def _production_python() -> str:
    """The runtime image's Python — the LAST `FROM`, the stage a multi-stage build ships."""
    froms = re.findall(r"^FROM\s+(?:--\S+\s+)*(\S+)", (ROOT / "Dockerfile").read_text(encoding="utf-8"),
                       re.M)
    assert froms, "the Dockerfile has no FROM — re-point this test"
    match = re.match(r"python:(\d+\.\d+)", froms[-1])
    assert match, f"production's image is no longer python:X.Y ({froms[-1]}) — re-point this test"
    return match.group(1)


def _golden_files() -> set[str]:
    """Every file under tests/ that applies the golden marker (`pytest.mark.golden`), read from the AST."""
    found = set()
    for path in sorted((ROOT / "tests").rglob("*.py")):
        source = path.read_text(encoding="utf-8")
        if "golden" not in source:
            continue
        if any(isinstance(node, ast.Attribute) and node.attr == "golden"
               and isinstance(node.value, ast.Attribute) and node.value.attr == "mark"
               for node in ast.walk(ast.parse(source, filename=str(path)))):
            found.add(path.relative_to(ROOT).as_posix())
    return found


def test_every_job_runs_on_productions_python():
    python = _production_python()
    jobs = _workflow()["jobs"]
    for name, job in jobs.items():
        versions = [str((step.get("with") or {}).get("python-version")) for step in job.get("steps") or ()
                    if "setup-python" in str(step.get("uses") or "")]
        assert versions == [python], (name, versions, f"production runs {python} (Dockerfile)")
    assert set(jobs) >= {"test", "golden-pg", "database"}, sorted(jobs)


def test_the_database_job_has_a_postgres_17_service_and_points_the_suite_at_it():
    job = _workflow()["jobs"]["database"]
    service = job["services"]["postgres"]
    env = service.get("env") or {}
    assert str(service["image"]).startswith("postgres:17"), service["image"]
    url = make_url(job["env"]["GENIOS_TEST_DATABASE_URL"])
    assert url.drivername == "postgresql+psycopg", url.drivername
    assert (url.host, url.username) == ("localhost", env.get("POSTGRES_USER", "postgres")), url
    assert (url.password, url.database) == (env["POSTGRES_PASSWORD"], env["POSTGRES_DB"]), url
    assert f"{url.port}:5432" in [str(p) for p in service.get("ports") or ()], (
        "the job runs on the runner, not in a container: it reaches the service on a mapped port")
    assert "--health-cmd" in str(service.get("options") or ""), (
        "without a health check the suite can start before Postgres accepts a connection")


def test_the_database_job_runs_the_whole_suite_but_the_golden_set_on_productions_dependencies():
    steps = _steps("database")
    suite = _suite_step("database")
    first = _run(suite).strip().splitlines()[0]
    assert first == SUITE, (first, "the whole suite but the golden set — no path, no -k, no second -m")
    config = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert config["tool"]["pytest"]["ini_options"]["testpaths"] == ["tests"], "no path means tests/"
    installs = [i for i, s in enumerate(steps) if "requirements.txt" in _run(s) and ".[dev]" in _run(s)]
    assert installs and installs[0] < steps.index(suite), (
        "production's dependency set and the test extras, installed before the suite runs")


def test_the_suite_sees_the_database_and_nothing_that_narrows_it():
    """Every env block the suite step inherits — the workflow's, the job's, its own — holds the
    database URL and nothing else: no `PYTEST_ADDOPTS`, no URL emptied for one step."""
    workflow = _workflow()
    job = workflow["jobs"]["database"]
    seen = {**(workflow.get("env") or {}), **(job.get("env") or {}),
            **(_suite_step("database").get("env") or {})}
    assert seen == {"GENIOS_TEST_DATABASE_URL": job["env"]["GENIOS_TEST_DATABASE_URL"]}, seen


def test_the_database_job_runs_on_every_push_and_cannot_go_soft():
    workflow = _workflow()
    job = workflow["jobs"]["database"]
    trigger = workflow.get("on", workflow.get(True))      # YAML 1.1 reads a bare `on:` as true
    assert trigger["push"]["branches"] == ["**"], trigger
    assert "if" not in job, "a job its condition skipped is not a failure"
    soft = [s.get("name") or s.get("uses") for s in [job, *job["steps"]] if s.get("continue-on-error")]
    assert not soft, ("continue-on-error turns a red step green", soft)


def test_a_skip_for_want_of_a_database_fails_the_job():
    steps = _steps("database")
    scans = [s for s in steps if "database_skips.py" in _run(s)]
    assert len(scans) == 1, [s.get("name") or s.get("uses") for s in steps]
    (scan,) = scans
    assert _run(scan).strip() == SCAN, _run(scan)
    assert (ROOT / "scripts" / "qa" / "database_skips.py").is_file()
    assert str(scan.get("if") or "") == "success() || failure()", (
        "the scan reports even when a test failed — a red job should still say what it skipped")
    assert steps.index(scan) > steps.index(_suite_step("database")), "it reads the log the suite wrote"


def test_a_red_database_suite_names_its_failures_where_anyone_can_read_them():
    """`03` F138's annotations, as the hermetic job carries them: the log printed, each FAILED/ERROR
    line an `::error` annotation (the API returns those to anyone; the job log needs a login), and
    the step's exit pytest's own."""
    step = _suite_step("database")
    run = _run(step)
    lines = run.strip().splitlines()
    assert lines[1:] == _run(_suite_step("test")).strip().splitlines()[1:], lines
    assert "cat pytest.log" in lines and "::error" in run and "^(FAILED|ERROR) " in run, run
    assert lines[-1] == "exit $status" and "status=$?" in lines[0], "a red pytest stays red"
    assert step.get("shell") == "bash", "the exit-code capture is bash"


def test_every_golden_test_it_leaves_out_runs_in_golden_pg():
    """`-m "not golden"` deselects the golden set here, so every file that carries the marker must be
    on a path `golden-pg` runs — or a golden test runs in no job, S17-F4's shape again."""
    first = _run(_suite_step("golden-pg")).strip().splitlines()[0]
    paths = [token.rstrip("/") for token in shlex.split(first.split(">", 1)[0])
             if token.startswith("tests")]
    golden = _golden_files()
    assert golden, "no file carries the golden marker — the deselection reads nothing; re-point this"
    stray = sorted(f for f in golden if not any(f == p or f.startswith(p + "/") for p in paths))
    assert not stray, (stray, paths)
