"""STEP-17 §3.4 · the health gate's output is kept, and a run can demand that every check judged.

    .venv/bin/python -m pytest -q tests/scripts/test_pipeline_health_keeps_its_output.py

`yc2_w27_s17` M40.C3.L-interface.V0.U03. The plan: *"run after each deploy; its output is kept"*.
Printed lines are read once and scroll away, and the gate's stdout is not pure — `scripts/_db` prints
its `[db]` target lines there first (`03` F36). So `--json PATH` writes every verdict to a file: what
was measured, what was expected, what to do, the detail — pure JSON, written whether the run passed
or failed. And `--require-data` is for the run a day after a deploy, when every lane should have run:
a NO DATA then exits 2 (a FAIL still exits 1).
"""
from __future__ import annotations

import json
import sys
from types import SimpleNamespace

import pytest

from scripts import pipeline_health as ph

pytestmark = pytest.mark.unit


def _check(ok, no_data=False, name="n"):
    return ph.Check(name=name, ok=ok, measured=f"measured {name}", expected=f"expected {name}",
                    fix=f"fix {name}", detail=[f"detail {name}"], no_data=no_data)


def _main(monkeypatch, capsys, results, *argv):
    import genios_engine.platform.db as db
    monkeypatch.setattr(ph, "resolve_database_url", lambda *a, **k: "postgresql://scratch/x")
    monkeypatch.setattr(db, "get_engine", lambda url: SimpleNamespace())
    monkeypatch.setattr(ph, "read_only_connection", lambda engine: SimpleNamespace(close=lambda: None))
    monkeypatch.setattr(ph, "run", lambda *a, **k: list(results))
    monkeypatch.setattr(sys, "argv", ["pipeline_health.py", "--org", "org_x", *argv])
    code = ph.main()
    return code, capsys.readouterr().out


def test_the_verdicts_are_written_as_json(monkeypatch, capsys, tmp_path):
    out = tmp_path / "health.json"
    code, printed = _main(monkeypatch, capsys,
                          [_check(True, name="a"), _check(True, no_data=True, name="b"),
                           _check(False, name="c")], "--json", str(out))
    assert code == 1
    kept = json.loads(out.read_text(encoding="utf-8"))
    assert kept["org"] == "org_x" and kept["at"]
    assert kept["summary"] == {"checks": 3, "passed": 1, "no_data": 1, "failed": 1}
    assert [(c["name"], c["verdict"]) for c in kept["checks"]] == [
        ("a", "PASS"), ("b", "NO DATA"), ("c", "FAIL")]
    assert kept["checks"][2] == {"name": "c", "verdict": "FAIL", "measured": "measured c",
                                 "expected": "expected c", "fix": "fix c", "detail": ["detail c"]}
    assert "FAIL     c" in printed, "the human lines are still printed"


def test_a_passing_run_is_kept_too(monkeypatch, capsys, tmp_path):
    out = tmp_path / "health.json"
    code, _ = _main(monkeypatch, capsys, [_check(True, name="a")], "--json", str(out))
    assert code == 0 and json.loads(out.read_text())["summary"]["passed"] == 1


def test_require_data_turns_no_data_into_exit_two(monkeypatch, capsys):
    results = [_check(True, name="a"), _check(True, no_data=True, name="b")]
    assert _main(monkeypatch, capsys, results)[0] == 0
    assert _main(monkeypatch, capsys, results, "--require-data")[0] == 2


def test_a_failure_is_still_one_with_require_data(monkeypatch, capsys):
    results = [_check(False, name="a"), _check(True, no_data=True, name="b")]
    assert _main(monkeypatch, capsys, results, "--require-data")[0] == 1


def test_require_data_with_everything_judged_is_zero(monkeypatch, capsys):
    assert _main(monkeypatch, capsys, [_check(True, name="a")], "--require-data")[0] == 0
