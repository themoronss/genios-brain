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


def test_the_live_model_builds_its_client_before_the_runner_refuses_one(monkeypatch):
    """The live pass never ran (`06` D50): `production_switches` replaces `anthropic.Anthropic` with a class that
    raises, and the live client was built lazily, on its first call — inside the run, so the first expert prompt
    raised `UnrecordedModelCall: a raw Anthropic client was built during a golden run`. It is built at
    construction now, and its calls use it."""
    import types

    import anthropic

    built: list[str] = []

    class _Recording:
        def __init__(self, *, api_key, **_kw):
            built.append(api_key)
            self.messages = types.SimpleNamespace(create=lambda **kw: types.SimpleNamespace(
                content=[types.SimpleNamespace(type="text", text='{"ok": true}')], stop_reason="end_turn",
                usage=types.SimpleNamespace(input_tokens=3, output_tokens=2)))

    class _Refused:
        def __init__(self, *_a, **_kw):
            raise AssertionError("a raw client was built after construction")
    monkeypatch.setattr(anthropic, "Anthropic", _Recording)
    live = _module().LiveModel("sk-not-a-real-key", "claude-haiku-4-5-20251001")
    assert built == ["sk-not-a-real-key"], "built at construction"
    monkeypatch.setattr(anthropic, "Anthropic", _Refused)        # what the runner does for the run
    result = live.call("a prompt")
    assert result.ok and result.parsed == {"ok": True} and built == ["sk-not-a-real-key"]


# ── STEP-12 M33.C3.L-integration.V0.U01 · one site's live pass, its dry run first (`06` D50) ──────

def test_the_experts_dry_run_counts_only_its_calls_at_its_own_models_price(monkeypatch, capsys):
    """The expert asks the golden set ≈ a hundred questions; priced on ITS model, the tier's
    `claude-sonnet-5`, from the product's one price table — never Haiku's, never a second table."""
    from genios_engine.platform.metrics import llm_price
    from tests.replays import cassettes
    from tests.replays.founder_case import load_cases
    monkeypatch.delenv("GENIOS_TEST_DATABASE_URL", raising=False)
    module = _module()
    assert module.main(["--dry-run", "--site", "expert"]) == 0
    out = capsys.readouterr().out
    calls = sum(sum(1 for a in cassettes.load(c).values() if a.get("site") == "expert")
                for c in load_cases())
    assert calls > 0 and f"{calls} expert model calls" in out, out[-400:]
    assert "on claude-sonnet-5 at list price" in out and "Nothing was run" in out
    price_in, price_out = (round(p * 1e6, 6) for p in llm_price("claude-sonnet-5"))
    assert module.price_per_mtok("claude-sonnet-5") == (price_in, price_out) != \
        module.price_per_mtok(module.DEFAULT_MODEL)


def test_a_named_model_wins_and_the_default_is_haiku(monkeypatch):
    module = _module()
    assert module.model_for("expert", None) == "claude-sonnet-5"
    assert module.model_for("expert", "claude-opus-5") == "claude-opus-5"
    assert module.model_for(None, None) == module.model_for("decider", None) == module.DEFAULT_MODEL


def test_an_unknown_site_is_refused(capsys):
    import pytest
    with pytest.raises(SystemExit) as stop:
        _module().main(["--dry-run", "--site", "oracle"])
    assert stop.value.code == 2 and "no such site" in capsys.readouterr().err


def test_a_sites_live_pass_is_kept_beside_the_authored_cassettes_never_instead(monkeypatch, capsys):
    import pytest
    module = _module()
    monkeypatch.setenv(module.LIVE_KEY_ENV, "sk-not-a-real-key")
    with pytest.raises(SystemExit) as stop:
        module.main(["--live", "--site", "expert", "--spend-ok", "--record"])
    assert stop.value.code == 2 and "BESIDE" in capsys.readouterr().err
    monkeypatch.delenv(module.LIVE_KEY_ENV)
    assert module.main(["--live", "--site", "expert"]) == 2, "it still needs both consents"


def test_the_site_model_sends_that_sites_prompts_alone_to_the_live_model():
    from tests.replays.harness import SITE_MARKERS

    class _Model:
        def __init__(self, name):
            self.model, self.prompts = name, []

        def call(self, prompt, **kw):
            self.prompts.append(prompt)
            return prompt
    live, rest = _Model("claude-sonnet-5"), _Model("ideal")
    router = _module().SiteModel("expert", live, rest)
    marker = {site: m for site, _module_, m in SITE_MARKERS}
    router.call("…" + marker["expert"] + "…")
    router.call("…" + marker["decider"] + "…")
    router.call("an unmarked prompt")
    assert len(live.prompts) == 1 and len(rest.prompts) == 2 and router.model == "claude-sonnet-5"


def test_a_sites_live_pass_keeps_its_answers_and_board_beside_the_authored(monkeypatch, tmp_path):
    """The live pass end to end on one case, its "live" model the ideal reader (no spend): the expert's
    answers land BESIDE the authored cassettes, each case carries its authored verdict, and the
    scorecard names the site and what moved."""
    import json
    import os
    import pytest
    if not os.environ.get("GENIOS_TEST_DATABASE_URL"):
        pytest.skip("needs GENIOS_TEST_DATABASE_URL pointing at a scratch database")
    from tests.replays import cassettes
    from tests.replays.founder_case import load_cases
    from tests.replays.ideal_reader import IdealReader
    module = _module()
    case = next(c for c in load_cases() if c.case_id == "F13")

    class _Faithful:
        def __init__(self, _key, model):
            self._reader, self.model = IdealReader(case), model

        def content_hash(self, material):
            return self._reader.content_hash(material)

        def call(self, prompt, **kw):
            return self._reader.call(prompt, **kw)
    monkeypatch.setattr(module, "LiveModel", _Faithful)
    monkeypatch.setattr(module, "SCORES", tmp_path)
    monkeypatch.setenv(module.LIVE_KEY_ENV, "sk-not-a-real-key")
    before = cassettes.load(case)
    assert module.main(["--live", "--site", "expert", "--spend-ok", "F13"]) == 0
    [card_file] = list(tmp_path.glob("*-claude-sonnet-5-expert.json"))
    card = json.loads(card_file.read_text())
    assert card["site"] == "expert" and card["moved"] == []
    [row] = card["cases"]
    assert row["verdict"] == row["authored_verdict"] == "pass"
    # STEP-13 M35.C4.L-integration.V2.U04: what the check made of the model's reviews, per case and in all — the
    # faithful answers are valid, shown whole, nothing dropped.
    assert set(row["reviews"]) == {"valid"} and row["reviews"]["valid"] >= 1
    assert row["fates"] == {"shown": row["reviews"]["valid"]} and row["dropped"] == {}
    assert card["reviews"] == row["reviews"] and card["fates"] == row["fates"] and card["dropped"] == {}
    assert card["noted"] == row["noted"], "the wording notes summed as the rest are (G10)"
    [beside] = list(tmp_path.glob("*-claude-sonnet-5-expert/F13.json"))
    assert json.loads(beside.read_text()) and cassettes.load(case) == before, \
        "the authored cassette is never replaced"


def test_the_live_pass_counts_a_held_review_its_drop_and_its_note(monkeypatch, tmp_path):
    """STEP-13 M35.C4.L-integration.V2.U05 (the second crosscheck F4 + G10): the only assertions on the live pass's
    fates and drops were for the faithful case — every review shown, nothing dropped — so a counter that called
    every fate "shown", or counted no drop, passed (both mutants survived, notes/b/x32_mutants_out.txt), and the
    NOTED verdicts were counted nowhere. Here the "live" model is the ideal reader with ONE misquote and ONE
    "the founder": F13's review is held, its fact dropped `misquoted`, its situation noted `speaks_of_you`."""
    import copy
    import dataclasses
    import json
    import os

    import pytest
    if not os.environ.get("GENIOS_TEST_DATABASE_URL"):
        pytest.skip("GENIOS_TEST_DATABASE_URL not set — the live pass runs only on a scratch database")
    from tests.replays.founder_case import load_cases
    from tests.replays.ideal_reader import IdealReader
    from tests.replays.harness import identify_site
    module = _module()
    case = next(c for c in load_cases() if c.case_id == "F13")

    class _OneMisquote:
        def __init__(self, _key, model):
            self._reader, self.model, self.served = IdealReader(case), model, 0

        def content_hash(self, material):
            return self._reader.content_hash(material)

        def call(self, prompt, **kw):
            result = self._reader.call(prompt, **kw)
            if identify_site(prompt) != "expert" or self.served:
                return result
            self.served += 1
            answer = copy.deepcopy(result.parsed)
            answer["facts"][0]["quote"] = "words no mail of the file holds at all"
            answer["frames"]["primary"] = "the founder owes Mohit the traction summary before Monday"
            return dataclasses.replace(result, parsed=answer, raw=json.dumps(answer))
    monkeypatch.setattr(module, "LiveModel", _OneMisquote)
    monkeypatch.setattr(module, "SCORES", tmp_path)
    monkeypatch.setenv(module.LIVE_KEY_ENV, "sk-not-a-real-key")
    assert module.main(["--live", "--site", "expert", "--spend-ok", "F13"]) == 0
    [card_file] = list(tmp_path.glob("*-claude-sonnet-5-expert.json"))
    card = json.loads(card_file.read_text())
    [row] = card["cases"]
    assert row["reviews"] == {"valid": 1}, row
    assert row["fates"] == {"held": 1} and card["fates"] == {"held": 1}
    assert row["dropped"] == {"misquoted": 1} and card["dropped"] == {"misquoted": 1}
    assert row["noted"] == {"speaks_of_you": 1} and card["noted"] == {"speaks_of_you": 1}
