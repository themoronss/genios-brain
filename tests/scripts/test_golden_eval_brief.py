"""STEP-15 (s15-D1) · `scripts/golden_eval.py --site brief` — the writer's live look, before it reaches an account.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… pytest -q tests/scripts/test_golden_eval_brief.py

Tree `yc2_w27_s15` M45.C5.L-integration.V0.U01. `--site brief` runs OUTSIDE the normal chain
`identify_site` dispatches (R-8/R-8E only ever run after a case's last sweep, through
`executive/morning_writer.write_brief` directly) and there is no cassette to dry-run from — both
documented departures from every other `--site`, pinned here rather than only in the module's own
docstring.
"""
from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "golden_eval.py"


def _module():
    spec = importlib.util.spec_from_file_location("golden_eval_brief", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _needs_db():
    if not os.environ.get("GENIOS_TEST_DATABASE_URL"):
        pytest.skip("needs GENIOS_TEST_DATABASE_URL pointing at a scratch database")


# ── validation: brief is a site, but not an ordinary one ───────────────────────────────────────

def test_brief_is_a_valid_site_name():
    module = _module()
    assert module.BRIEF_SITE == "brief"
    assert module.BRIEF_SITE not in module.sites(), (
        "brief has no SITE_MARKERS entry — it runs after the chain, not inside it")


def test_record_is_refused_with_site_brief(monkeypatch, capsys):
    module = _module()
    monkeypatch.setenv(module.LIVE_KEY_ENV, "sk-not-a-real-key")
    with pytest.raises(SystemExit) as stop:
        module.main(["--live", "--site", "brief", "--spend-ok", "--record"])
    assert stop.value.code == 2
    assert "no cassette shape" in capsys.readouterr().err


def test_model_does_not_apply_to_site_brief(capsys):
    module = _module()
    with pytest.raises(SystemExit) as stop:
        module.main(["--dry-run", "--site", "brief", "--model", "claude-opus-5"])
    assert stop.value.code == 2
    assert "does not apply" in capsys.readouterr().err


def test_a_live_run_of_brief_without_both_consents_spends_nothing(monkeypatch, capsys):
    module = _module()
    monkeypatch.delenv(module.LIVE_KEY_ENV, raising=False)
    assert module.main(["--live", "--site", "brief", "--spend-ok"]) == 2
    assert "D12c" in capsys.readouterr().err


def test_thinking_and_ceiling_flags_do_not_apply_to_brief():
    module = _module()
    with pytest.raises(SystemExit):
        module.main(["--dry-run", "--site", "brief", "--thinking", "off"])


# ── the dry run: no cassette, priced from the real day instead ─────────────────────────────────

def test_the_dry_run_prices_both_tiers_from_the_real_day(monkeypatch, capsys):
    _needs_db()
    module = _module()
    assert module.main(["--dry-run", "--site", "brief", "F45"]) == 0
    out = capsys.readouterr().out
    assert "$ R-8" in out and "$ R-8E" in out and "F45" in out
    assert "no model was asked" in out
    assert "no cassette exists for these two sites yet" in out


def test_the_dry_run_prices_r8e_higher_than_r8_at_the_same_ceiling_ratio(monkeypatch, capsys):
    """R-8E is the Sonnet-class tier: its list price is higher than R-8's Haiku-class one, so for
    the same case its column must be the larger of the two."""
    _needs_db()
    module = _module()
    assert module.main(["--dry-run", "--site", "brief", "F45"]) == 0
    out = capsys.readouterr().out
    import re
    row = next(line for line in out.splitlines() if line.startswith("F45"))
    t1, t2 = (float(x) for x in re.findall(r"\$\s*([0-9.]+)", row)[:2])
    assert t2 > t1 > 0


# ── the live pass: both tiers, each its own spend cap, a scorecard either way ──────────────────

class _FakeResult:
    def __init__(self, parsed, model, input_tokens=120, output_tokens=24):
        self.parsed, self.raw = parsed, json.dumps(parsed)
        self.input_tokens, self.output_tokens = input_tokens, output_tokens
        self.model, self.ok, self.error, self.truncated = model, True, None, False


class _AlwaysMalformed:
    """Every call returns valid JSON in the wrong shape — R-8 and R-8E both fail past their one
    syntax repair, so the result is deterministic (the template) regardless of the case's own
    content, which `tests/executive/test_the_brief_writer.py` already covers faithfully."""

    def __init__(self, _key: str, model: str) -> None:
        self.model = model
        self.calls = 0

    def content_hash(self, material: str) -> str:
        import hashlib
        return hashlib.sha256(material.encode()).hexdigest()

    def call(self, prompt: str, *, max_tokens: int = 4096, **_kw):
        self.calls += 1
        return _FakeResult({"not_lines": []}, self.model)


def test_live_brief_falls_to_the_template_when_both_tiers_are_malformed(monkeypatch, tmp_path):
    _needs_db()
    from tests.replays.founder_case import load_cases
    module = _module()
    monkeypatch.setattr(module, "LiveModel", _AlwaysMalformed)
    monkeypatch.setattr(module, "SCORES", tmp_path)
    monkeypatch.setenv(module.LIVE_KEY_ENV, "sk-not-a-real-key")
    case = next(c for c in load_cases() if c.case_id == "F45")
    assert module.main(["--live", "--site", "brief", "--spend-ok", "--max-usd", "1",
                        case.case_id]) == 0
    [card_file] = list(tmp_path.glob("*-brief.json"))
    card = json.loads(card_file.read_text())
    assert card["template"] == 1 and card["written"] == 0 and card["escalated"] == 0
    assert card["spent_usd"] > 0, "two malformed attempts (R-8, R-8E) each spend real tokens"
    [row] = card["cases"]
    assert row["case"] == "F45" and row["written_by"] == "template"
    assert "Haiku" in row["why"] and "Sonnet" in row["why"]


def test_each_tiers_spend_cap_is_priced_on_its_own_model(monkeypatch, tmp_path):
    """Both caps top out at the same `--max-usd`, so a swap is invisible in the spend TOTAL
    (addition does not care which cap paid for which call) — it only shows in which model each
    cap was built to price. Caught here directly, at construction."""
    _needs_db()
    from tests.replays.founder_case import load_cases
    from genios_engine.reason.bundle.sites import TIER_T1, TIER_T2
    from genios_engine.reason.llm_sites import tier_model
    module = _module()
    monkeypatch.setattr(module, "LiveModel", _AlwaysMalformed)
    monkeypatch.setattr(module, "SCORES", tmp_path)
    monkeypatch.setenv(module.LIVE_KEY_ENV, "sk-not-a-real-key")
    built: list[str] = []
    real_cap = module.SpendCap

    class _Recording(real_cap):
        def __init__(self, max_usd, model):
            built.append(model)
            super().__init__(max_usd, model)
    monkeypatch.setattr(module, "SpendCap", _Recording)
    case = next(c for c in load_cases() if c.case_id == "F45")
    assert module.main(["--live", "--site", "brief", "--spend-ok", "--max-usd", "1",
                        case.case_id]) == 0
    assert built == [tier_model(TIER_T1), tier_model(TIER_T2)], (
        "the first cap built must be R-8's own (Haiku-class), the second R-8E's (Sonnet-class)")


def test_live_brief_counts_each_written_by_in_its_own_column(monkeypatch, tmp_path):
    """`card["written"]`/`["escalated"]`/`["template"]` must each count their OWN `written_by`
    value — not a neighbour's. Faked at `write_brief` itself (not `LiveModel`): the aggregation
    this test pins is `live_brief`'s own, not the writer's, which
    `tests/executive/test_the_brief_writer.py` already covers."""
    _needs_db()
    import dataclasses
    from tests.replays.founder_case import load_cases
    from genios_engine.contracts import morning_brief as B
    module = _module()
    monkeypatch.setattr(module, "SCORES", tmp_path)
    monkeypatch.setenv(module.LIVE_KEY_ENV, "sk-not-a-real-key")
    cases = [c for c in load_cases() if c.case_id in ("F45", "F13", "F01")]
    assert len(cases) == 3
    # Asymmetric on purpose: if "written" secretly counted ESCALATED (or any other neighbour),
    # 2 would read as 1 and this would catch it — equal counts could not tell the swap apart.
    verdicts = iter([B.WRITTEN, B.WRITTEN, B.ESCALATED])

    def _fake_write_brief(engine, **kw):
        from genios_engine.executive.morning_template import template_brief
        base = template_brief(org_id=kw["org_id"], seat_id=kw["seat_id"], items=kw["items"],
                              now=kw["now"], tz=kw["tz"])
        return dataclasses.replace(base, written_by=next(verdicts), model="fake", tier="T1",
                                   cost_micro_usd=1)
    monkeypatch.setattr("genios_engine.executive.morning_writer.write_brief", _fake_write_brief)
    assert module.main(["--live", "--site", "brief", "--spend-ok", "--max-usd", "1",
                        *[c.case_id for c in cases]]) == 0
    [card_file] = list(tmp_path.glob("*-brief.json"))
    card = json.loads(card_file.read_text())
    assert card["written"] == 2 and card["escalated"] == 1 and card["template"] == 0


def test_live_brief_writes_nothing_to_the_morning_briefs_table(monkeypatch, tmp_path):
    """`write_brief` is called directly here, never through `morning.compose` — a golden live pass
    must not collide with (or be hidden by) a real `morning_briefs` row for the same tenant."""
    _needs_db()
    from sqlalchemy import text
    from tests.replays.founder_case import load_cases
    module = _module()
    monkeypatch.setattr(module, "LiveModel", _AlwaysMalformed)
    monkeypatch.setattr(module, "SCORES", tmp_path)
    monkeypatch.setenv(module.LIVE_KEY_ENV, "sk-not-a-real-key")
    case = next(c for c in load_cases() if c.case_id == "F45")
    assert module.main(["--live", "--site", "brief", "--spend-ok", "--max-usd", "1",
                        case.case_id]) == 0
    from genios_engine.platform.db import get_engine
    engine = get_engine(os.environ["GENIOS_TEST_DATABASE_URL"])
    with engine.connect() as c:
        n = c.execute(text("select count(*) from morning_briefs where org_id like 'org_golden_%'")
                      ).scalar()
    assert n == 0, "the golden tenant was removed, and nothing else should have written this table"
