"""STEP-01 · the live evaluation estimates for free, and spends only when told twice.

    pytest tests/scripts/test_golden_eval.py -q

Model spend on the golden set is the founder's call (06-DECISIONS D12c, default: no spend). So the
dry run touches no database and no model and says what a live pass would cost; a live run needs
BOTH a key in GENIOS_GOLDEN_LIVE_KEY and --spend-ok.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "golden_eval.py"


def _module():
    spec = importlib.util.spec_from_file_location("golden_eval", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_dry_run_needs_no_database_and_names_the_cost(monkeypatch, capsys):
    monkeypatch.delenv("GENIOS_TEST_DATABASE_URL", raising=False)
    assert _module().main(["--dry-run"]) == 0
    out = capsys.readouterr().out
    assert "model calls" in out and "$" in out and "Nothing was run" in out
    assert "F01" in out and "F40" in out


def test_a_live_run_without_both_consents_spends_nothing(monkeypatch, capsys):
    module = _module()
    monkeypatch.delenv(module.LIVE_KEY_ENV, raising=False)
    assert module.main(["--live", "--spend-ok"]) == 2
    monkeypatch.setenv(module.LIVE_KEY_ENV, "sk-not-a-real-key")
    assert module.main(["--live"]) == 2
    assert "D12c" in capsys.readouterr().err


def test_the_live_model_keeps_the_transport_the_runner_refuses_to_everyone_else():
    """Captured at construction, before `production_switches` replaces `LLMClient.call`."""
    from genios_engine.context.llm.client import LLMClient

    live = _module().LiveModel("sk-not-a-real-key", "claude-haiku-4-5-20251001")
    assert live._call is LLMClient.call and live.model == "claude-haiku-4-5-20251001"
