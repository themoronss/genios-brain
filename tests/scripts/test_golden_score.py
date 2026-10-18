"""STEP-01 · the golden board refuses rather than prints a number from nothing.

    pytest tests/scripts/test_golden_score.py -q

The board itself runs on the scratch database (`GENIOS_TEST_DATABASE_URL=… python
scripts/golden_score.py`); what is held here is everything that must hold without one: the
refusal, the two lines' shape, and `--assert-recorded`'s reading of the before-score.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "golden_score.py"
BOARD = {"must_detect": {"pass": 4, "of": 30, "not_expressible": 8, "fail": 18,
                         "lost_at": {"gate": 5}},
         "must_abstain": {"pass": 5, "of": 10, "not_exercised": 2, "fail": 3},
         "forbidden_outputs": 4,
         "atlas": {"passing": 0, "blocked": 7, "of": 80, "not_expressible": 73}}


def _module():
    spec = importlib.util.spec_from_file_location("golden_score", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_without_a_scratch_database_it_refuses_with_exit_2(monkeypatch, capsys):
    monkeypatch.delenv("GENIOS_TEST_DATABASE_URL", raising=False)
    assert _module().main([]) == 2
    assert "REFUSED" in capsys.readouterr().err


def test_a_production_host_is_refused(monkeypatch):
    monkeypatch.setenv("GENIOS_TEST_DATABASE_URL",
                       "postgresql://u:p@db.abcdefgh.supabase.co:5432/postgres")
    assert _module().main([]) == 2


def test_the_board_is_two_lines_with_every_count_named():
    founder, atlas = _module().lines(BOARD)
    assert founder == ("founder golden set   must-detect  4/30 (8 not expressible)   "
                       "must-abstain  5/10 (2 not exercised)   forbidden outputs  4")
    assert atlas == "atlas replays 01–07  passing  0/80   blocked  7/80   not expressible  73"


def test_the_recorded_board_is_read_back_exactly(tmp_path):
    module = _module()
    founder, atlas = module.lines(BOARD)
    page = tmp_path / "03-FINDINGS.md"
    page.write_text(f"## F\n\n```\n{founder}\n{atlas}\n```\n", encoding="utf-8")
    assert module.recorded(page) == (founder, atlas)


def test_a_page_with_no_board_or_two_boards_is_refused(tmp_path):
    module = _module()
    founder, atlas = module.lines(BOARD)
    empty = tmp_path / "none.md"
    empty.write_text("nothing recorded\n", encoding="utf-8")
    twice = tmp_path / "twice.md"
    twice.write_text(f"{founder}\n{atlas}\n{founder}\n{atlas}\n", encoding="utf-8")
    for page in (empty, twice):
        with pytest.raises(SystemExit):
            module.recorded(page)
