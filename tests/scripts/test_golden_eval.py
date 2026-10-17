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
    # `--max-usd` is required since `yc2_w27_s18` M50.C4.L-interface.V1.U09; the ideal reader spends nothing.
    assert module.main(["--live", "--site", "expert", "--spend-ok", "--max-usd", "1", "F13"]) == 0
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
            # ⛔ RESTATED (STEP-13b M38.C3): the expert's review is asked through the ladder now - repaired once with the
            # check's verdicts, then the stronger rung - so a model that errs ONCE is put right and the review is shown. A
            # HELD review is one whose model keeps the error through the repair and the climb: every expert ask is wrong.
            if identify_site(prompt) != "expert":
                return result
            self.served += 1
            answer = copy.deepcopy(result.parsed)
            answer["facts"][0]["quote"] = "words no mail of the file holds at all"
            answer["frames"]["primary"] = "the founder owes Mohit the traction summary before Monday"
            return dataclasses.replace(result, parsed=answer, raw=json.dumps(answer))
    monkeypatch.setattr(module, "LiveModel", _OneMisquote)
    monkeypatch.setattr(module, "SCORES", tmp_path)
    monkeypatch.setenv(module.LIVE_KEY_ENV, "sk-not-a-real-key")
    # MERGED 13 Oct: `--max-usd` is required since `yc2_w27_s18` M50.C4.L-interface.V1.U09 (as above).
    assert module.main(["--live", "--site", "expert", "--spend-ok", "--max-usd", "1", "F13"]) == 0
    [card_file] = list(tmp_path.glob("*-claude-sonnet-5-expert.json"))
    card = json.loads(card_file.read_text())
    [row] = card["cases"]
    assert row["reviews"] == {"valid": 1}, row
    assert row["fates"] == {"held": 1} and card["fates"] == {"held": 1}
    assert row["dropped"] == {"misquoted": 1} and card["dropped"] == {"misquoted": 1}
    assert row["noted"] == {"speaks_of_you": 1} and card["noted"] == {"speaks_of_you": 1}


# ── STEP-13b M38.C3.L-interface.V2.U01 · the live scorecard per model ───────────────────────────

def _row(status="valid", rung=None, fate="shown", verdicts=(), facts=(), tin=9000, tout=900, cost=45000):
    return {"status": status, "rung": rung, "input_tokens": tin, "output_tokens": tout, "cost_micro_usd": cost,
            "review": {"facts": [dict(f) for f in facts]},
            "checked": None if fate is None else {"fate": fate, "verdicts": [dict(v) for v in verdicts]}}


def _v(line, verdict="kept", reason=None, source=None):
    return {"line": line, "verdict": verdict, "reason": reason, "detail": "", **({"source": source} if source else {})}


def test_the_tally_counts_what_the_check_made_of_each_review():
    t = _module().tally([
        _row(fate="shown", verdicts=[_v("fact:1")]),
        _row(fate="held", verdicts=[_v("fact:1", "dropped", "misquoted"), _v("prose", "noted", "unheld_number")]),
        _row(status="refused", fate=None)], [])
    assert t["reviews"] == {"refused": 1, "valid": 2} and t["fates"] == {"held": 1, "shown": 1}
    assert t["dropped"] == {"misquoted": 1} and t["noted"] == {"unheld_number": 1}
    assert t["held_share"] == 0.5, "held over the valid reviews"


def test_the_misquote_rate_is_decisive_facts_misquoted_over_those_quoting_a_mail():
    facts = [{"claim": "a", "evidence": ["e1"], "quote": "words one"}, {"claim": "b", "evidence": ["e2"], "quote": "two"},
             {"claim": "c", "evidence": ["e3"]}]
    t = _module().tally([_row(facts=facts, verdicts=[_v("fact:1"), _v("fact:2", "dropped", "misquoted"), _v("fact:3")])], [])
    assert (t["facts"], t["facts_quoting"], t["misquoted"]) == (3, 2, 1) and t["misquote_rate"] == 0.5
    stray = _module().tally([_row(facts=facts, verdicts=[_v("quote:2", "dropped", "misquoted")])], [])
    assert stray["misquoted"] == 1, "a quote that dropped on its own line (the fact needing none) is a misquote too"
    none = _module().tally([_row(facts=[facts[2]], verdicts=[_v("fact:1")])], [])
    assert none["facts_quoting"] == 0 and none["misquote_rate"] is None


def test_the_unknown_evidence_rate_is_over_every_fact():
    facts = [{"claim": "a", "evidence": ["e"]}] * 4
    t = _module().tally([_row(facts=facts, verdicts=[_v("fact:1", "dropped", "unknown_evidence")] + [_v(f"fact:{n}") for n in (2, 3, 4)])], [])
    assert t["unknown_evidence"] == 1 and t["unknown_evidence_rate"] == 0.25


def test_the_engines_lines_and_the_experts_own_are_counted_from_the_labels_the_check_wrote():
    t = _module().tally([_row(verdicts=[
        _v("fact:1", source="data"), _v("inference:1", source="mixed"), _v("pattern:1", source="engine"),
        _v("own:1", source="own"), _v("own:2", "dropped", "own_states_a_number", source="own")])], [])
    assert (t["engine_lines"], t["own_lines"], t["own_dropped"]) == (2, 2, 1)


def test_tokens_and_cost_are_summed_and_a_review_with_no_cost_adds_none():
    t = _module().tally([_row(tin=100, tout=10, cost=5), _row(tin=200, tout=20, cost=7)], [])
    assert (t["tokens_in"], t["tokens_out"], t["cost_micro_usd"]) == (300, 30, 12)


def test_the_ladder_says_which_rung_answered_what_it_asked_why_it_climbed_and_what_each_rung_cost():
    attempts = [{"rung": 1, "consult": "first", "climbed_because": None, "cost_micro_usd": 10, "status": "valid"},
                {"rung": 1, "consult": "repair", "climbed_because": "unquoted", "cost_micro_usd": 12, "status": "valid"},
                {"rung": 2, "consult": "first", "climbed_because": None, "cost_micro_usd": 40, "status": "valid"}]
    t = _module().tally([_row(rung=2)], attempts)
    assert t["ladder"] == {"stood": {"2": 1}, "attempts": {"1:first": 1, "1:repair": 1, "2:first": 1},
                           "climbs": {"unquoted": 1}, "cost_micro_usd": {"1": 22, "2": 40}}
    assert _module().tally([_row(rung=None)], [])["ladder"]["stood"] == {"1": 1}, "a row before 0250 reads as rung one"


def test_an_empty_run_tallies_to_zeros_not_to_a_division():
    t = _module().tally([], [])
    assert t["reviews"] == {} and t["held_share"] is None and t["misquote_rate"] is None
    assert t["unknown_evidence_rate"] is None and t["cost_micro_usd"] == 0


def test_a_total_is_summed_from_the_cases_and_its_rates_are_worked_out_again():
    m = _module()
    facts = [{"claim": "a", "evidence": ["e"], "quote": "q"}] * 2
    one = m.tally([_row(fate="held", facts=facts, verdicts=[_v("fact:1", "dropped", "misquoted"), _v("fact:2")])],
                  [{"rung": 1, "consult": "first", "climbed_because": None, "cost_micro_usd": 3, "status": "valid"}])
    two = m.tally([_row(fate="shown", facts=facts, verdicts=[_v("fact:1"), _v("fact:2")], rung=2)],
                  [{"rung": 2, "consult": "first", "climbed_because": None, "cost_micro_usd": 4, "status": "valid"}])
    total = m.combine([one, two])
    assert total["reviews"] == {"valid": 2} and total["fates"] == {"held": 1, "shown": 1}
    assert (total["facts"], total["facts_quoting"], total["misquoted"]) == (4, 4, 1)
    assert total["held_share"] == 0.5 and total["misquote_rate"] == 0.25 and total["cost_micro_usd"] == 90_000
    assert total["ladder"]["stood"] == {"1": 1, "2": 1} and total["ladder"]["cost_micro_usd"] == {"1": 3, "2": 4}
    assert m.combine([])["held_share"] is None and m.combine([])["reviews"] == {}


# ── STEP-13b M38.C3.L-interface.V13.U03 · the ladder's live pass, and the kept scorecards' targets ──

def _card(**over):
    base = {"recall": 0.8, "forbidden_outputs": 0, "abstain_failures": 0, "reviews": {"valid": 50},
            "fates": {"shown": 40, "held": 10}, "cost_usd": 1.0,
            "cases": [{"kind": "must_abstain", "verdict": "pass"}] * 13 + [{"kind": "must_detect", "verdict": "pass"}]}
    base.update(over)
    return base


def _index(tmp_path, **cards):
    import json
    names = {}
    for name, card in cards.items():
        if card is not None:
            (tmp_path / f"{name}.json").write_text(json.dumps(card))
            names[name] = f"{name}.json"
    index = tmp_path / "s13b.json"
    index.write_text(json.dumps({"scorecards": names}))
    return index


def test_every_target_met_exits_zero_and_each_is_said(tmp_path, capsys):
    index = _index(tmp_path, haiku=_card(fates={"shown": 40, "held": 10}),
                   sonnet=_card(recall=0.8, cost_usd=2.0), ladder=_card(recall=0.85, cost_usd=1.2))
    assert _module().main(["--assert-scorecards", str(index)]) == 0
    out = capsys.readouterr().out
    assert out.count("met") >= 6 and "every target met" in out and "MISSED" not in out


def _good():
    return dict(haiku=_card(), sonnet=_card(cost_usd=2.0), ladder=_card(cost_usd=1.0))


def test_a_target_missed_is_said_not_loosened_and_exits_one(tmp_path, capsys):
    m = _module()
    cases = {
        "haiku: forbidden": dict(_good(), haiku=_card(forbidden_outputs=1)),
        "sonnet: forbidden": dict(_good(), sonnet=_card(cost_usd=2.0, abstain_failures=1)),
        "ladder: forbidden": dict(_good(), ladder=_card(cost_usd=1.0, forbidden_outputs=3)),
        "haiku: forbidden 0 and must-abstain 13 of 13": dict(_good(), haiku=_card(
            cases=[{"kind": "must_abstain", "verdict": "pass"}] * 12)),
        "must-detect": dict(_good(), sonnet=_card(recall=0.9, cost_usd=2.0), ladder=_card(recall=0.85, cost_usd=1.0)),
        "cost per review": dict(_good(), ladder=_card(cost_usd=2.0)),
        "held share": dict(_good(), haiku=_card(fates={"shown": 25, "held": 25}))}
    for name, cards in cases.items():
        folder = tmp_path / name.replace(" ", "_").replace(":", "")
        folder.mkdir()
        assert m.main(["--assert-scorecards", str(_index(folder, **cards))]) == 1, name
        out = capsys.readouterr().out
        missed = [line for line in out.splitlines() if line.startswith("MISSED")]
        assert len(missed) == 1 and name.split(":")[0] in missed[0].lower().replace("the ladder's ", "") or \
            (len(missed) == 1 and name in missed[0].lower()), (name, missed)
        assert "s13b-D2" in out, name


def test_the_ladders_targets_are_judged_against_sonnet_alone(tmp_path, capsys):
    cheaper = _index(tmp_path, haiku=_card(), sonnet=_card(cost_usd=2.0), ladder=_card(cost_usd=1.5))
    assert _module().main(["--assert-scorecards", str(cheaper)]) == 0
    equal = tmp_path / "eq"
    equal.mkdir()
    assert _module().main(["--assert-scorecards", str(_index(equal, haiku=_card(), sonnet=_card(cost_usd=2.0),
                                                            ladder=_card(cost_usd=2.0)))]) == 1, "below, not equal"
    capsys.readouterr()


def test_scorecards_not_yet_kept_are_not_run_and_never_passed(tmp_path, capsys):
    assert _module().main(["--assert-scorecards", str(_index(tmp_path, haiku=_card()))]) == 3
    out = capsys.readouterr().out
    assert "not run" in out and "the lead's live passes" in out and "every target met" not in out
    assert _module().main(["--assert-scorecards", str(_index(tmp_path / ".." / tmp_path.name))]) == 3
    gone = tmp_path / "gone"
    gone.mkdir()
    import json
    (gone / "i.json").write_text(json.dumps({"scorecards": {"haiku": "missing.json"}}))
    assert _module().main(["--assert-scorecards", str(gone / "i.json")]) == 3, "a named file that is not there"


def test_a_missed_target_outranks_a_scorecard_not_yet_kept(tmp_path):
    assert _module().main(["--assert-scorecards", str(_index(tmp_path, haiku=_card(forbidden_outputs=2)))]) == 1


def test_the_index_may_name_other_targets(tmp_path):
    import json
    index = _index(tmp_path, haiku=_card(fates={"shown": 30, "held": 20}), sonnet=_card(), ladder=_card(cost_usd=0.5))
    data = json.loads(index.read_text())
    assert _module().main(["--assert-scorecards", str(index)]) == 0, "40% held is under half"
    data["targets"] = {"held_share_below": 0.3}
    index.write_text(json.dumps(data))
    assert _module().main(["--assert-scorecards", str(index)]) == 1


def test_assert_scorecards_combines_with_nothing_and_needs_no_database_or_key(tmp_path, monkeypatch):
    import pytest
    monkeypatch.delenv("GENIOS_TEST_DATABASE_URL", raising=False)
    monkeypatch.delenv("GENIOS_GOLDEN_LIVE_KEY", raising=False)
    index = _index(tmp_path, haiku=_card())
    for extra in ("--live", "--dry-run", "--record"):
        with pytest.raises(SystemExit) as stop:
            _module().main(["--assert-scorecards", str(index), extra])
        assert stop.value.code == 2
    assert _module().main(["--assert-scorecards", str(index)]) == 3


def test_the_ladder_is_rungs_cheapest_first_each_once_and_only_the_experts_live_pass(monkeypatch, capsys):
    import pytest
    m = _module()
    monkeypatch.setenv(m.LIVE_KEY_ENV, "sk-not-a-real-key")
    for bad in (["--ladder", "T2,T1"], ["--ladder", "T1,T1"], ["--ladder", "T4"], ["--ladder", ""]):
        with pytest.raises(SystemExit) as stop:
            m.main(["--live", "--spend-ok", "--max-usd", "1", *bad])
        assert stop.value.code == 2, bad
    for other in (["--dry-run"], ["--live", "--site", "decider"], ["--live", "--model", "m"], ["--live", "--record"]):
        with pytest.raises(SystemExit) as stop:
            m.main(["--ladder", "T1,T2", "--spend-ok", "--max-usd", "1", *other])
        assert stop.value.code == 2, other
    monkeypatch.delenv(m.LIVE_KEY_ENV)
    assert m.main(["--live", "--ladder", "T1,T2", "--spend-ok", "--max-usd", "1"]) == 2, "it still needs both consents"
    assert m.main(["--live", "--ladder", "T1,T2", "--spend-ok"]) == 2


def test_the_ladders_money_is_one_pool_priced_at_each_rungs_own_model():
    m = _module()
    pool = m.SharedCap(1.0)
    haiku, sonnet = pool.for_model("claude-haiku-4-5-20251001"), pool.for_model("claude-sonnet-5")
    assert haiku.price_in < sonnet.price_in and haiku.max_usd == sonnet.max_usd == 1.0

    class _R:
        input_tokens, output_tokens = 1_000_000, 100_000
    haiku.charge(_R)
    sonnet.charge(_R)
    assert round(pool.spent_usd, 4) == round(haiku.price_in + 0.1 * haiku.price_out + sonnet.price_in
                                             + 0.1 * sonnet.price_out, 4) == haiku.spent_usd == sonnet.spent_usd
    assert not pool.reached
    haiku.reached = True
    assert pool.reached and sonnet.reached


def test_the_capped_model_stops_a_rung_whose_worst_case_crosses_the_pool():
    import pytest
    m = _module()

    class _Inner:
        model = "claude-sonnet-5"

        def call(self, prompt, **kw):
            raise AssertionError("never asked")
    pool = m.SharedCap(0.0001)
    capped = m.CappedModel(_Inner(), pool.for_model("claude-sonnet-5"))
    with pytest.raises(m.SpendCapReached):
        capped.call("x" * 4000, max_tokens=4096)
    assert pool.reached


def test_the_ladder_run_sets_the_rungs_and_the_leave_for_opus_and_puts_them_back():
    from genios_engine.reason.bundle import sites as S
    from genios_engine.reason.expert import sweep
    m = _module()
    before = (S.EXPERT_LADDER, sweep._clients)
    with m.ladder_settings(("T1", "T3")):
        assert S.EXPERT_LADDER == ("T1", "T3")
        assert [t for t, _c in sweep._clients({"T1": object(), "T3": object()}, None, allow_opus=False)] == ["T1", "T3"]
    assert (S.EXPERT_LADDER, sweep._clients) == before
    assert sweep._clients({"T1": object()}, None, allow_opus=False)[0][0] == "T1"


def test_replay_live_spends_nothing_and_combines_with_no_other_mode(monkeypatch):
    import pytest
    m = _module()
    for other in (["--live"], ["--dry-run"], ["--record"], ["--ladder", "T1,T2"]):
        with pytest.raises(SystemExit) as stop:
            m.main(["--replay-live", "somewhere", *other])
        assert stop.value.code == 2, other
    with pytest.raises(SystemExit, match="no such folder"):
        monkeypatch.setenv("GENIOS_TEST_DATABASE_URL", "postgresql+psycopg://x:y@127.0.0.1:1/z")
        monkeypatch.setattr("tests.replays.engine_runner.pin_scratch_database", lambda: None)
        m.main(["--replay-live", "/nowhere/at/all"])


def test_the_kept_index_is_awaiting_the_leads_passes_and_a_missing_one_is_refused(capsys):
    root = SCRIPT.parents[1]
    index = root / "speedrun008" / "YC-II W27" / "scores" / "s13b.json"
    assert _module().main(["--assert-scorecards", str(index)]) == 3, "nothing is kept yet: not run, never passed"
    assert _module().main(["--assert-scorecards", str(index) + ".missing"]) == 2
