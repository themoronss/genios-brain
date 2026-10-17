"""A live golden pass counts every call it paid for, can run the R-7 comparison, and stops at a dollar cap.

    pytest tests/scripts/test_the_live_pass_counts_every_call.py -q

⛔ `yc2_w27_s18` M50.C4.L-interface.V1.U09 (the 13 Oct audit's T5-10, s5t-F12; `06` D72). The Sonnet pass
of 12 Oct printed "$0.3533" for ≈ $10.4 really spent: the scorecard summed the cassette — the answers the
recorder KEPT — and every cut answer was raised, retried and never counted. Now:

  * the scorecard sums the recorder's `ledger` (every call, a cut included) and reports the cut calls;
  * `--thinking`, `--ceiling` and `--per-call-usd` set the site's R-site for the run only — `06` D72's two
    arms (off at 6,000; adaptive at 12,000 with the per-call cap at $0.15) — and are put back after;
  * `--max-usd` is required, and a call whose worst case would cross it is refused BEFORE the model is
    asked; the pass stops after that case and says so.

No model is called here: every "live" model is a fake.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

from genios_engine.context.llm.client import THINKING_ADAPTIVE, LLMResult
from genios_engine.reason.bundle import budget as B
from genios_engine.reason.bundle import sites as S

pytestmark = pytest.mark.unit

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "golden_eval.py"


def _module():
    spec = importlib.util.spec_from_file_location("golden_eval", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# =================================================================================================
# 1 · it refuses to start without a cap
# =================================================================================================
def test_a_live_pass_without_a_dollar_cap_never_starts(monkeypatch, capsys):
    module = _module()
    monkeypatch.setenv(module.LIVE_KEY_ENV, "sk-not-a-real-key")
    monkeypatch.setattr(module, "live", lambda *a, **k: pytest.fail("the pass started"))
    assert module.main(["--live", "--site", "expert", "--spend-ok"]) == 2
    assert "--max-usd" in capsys.readouterr().err


@pytest.mark.parametrize("cap", ["0", "-1"])
def test_a_cap_must_be_a_positive_number(cap):
    with pytest.raises(SystemExit):
        _module().main(["--live", "--site", "expert", "--spend-ok", "--max-usd", cap])


@pytest.mark.parametrize("args", [["--site", "expert", "--per-call-usd", "0"],
                                  ["--site", "expert", "--per-call-usd", "a dollar"],
                                  ["--site", "expert", "--ceiling", "0"]])
def test_a_run_setting_must_be_a_positive_number(args):
    with pytest.raises(SystemExit):
        _module().main(["--live", "--spend-ok", "--max-usd", "1", *args])


@pytest.mark.parametrize("flag", [["--thinking", "off"], ["--ceiling", "12000"], ["--per-call-usd", "0.15"]])
def test_a_site_setting_needs_a_site_with_a_tier_of_its_own(flag):
    with pytest.raises(SystemExit):
        _module().main(["--dry-run", *flag])


def test_the_settings_reach_the_live_pass(monkeypatch):
    """…and hold WHILE it runs — the gate reads the site's table at each consult — and not after."""
    module = _module()
    monkeypatch.setenv(module.LIVE_KEY_ENV, "sk-not-a-real-key")
    seen = {}

    def _live(*a, **k):
        seen.update(args=a, kw=k, during=(
            S.thinking_mode(S.SITE_EXPERT), S.max_output_tokens(S.SITE_EXPERT),
            B.NarrativeBudget.for_site(S.SITE_EXPERT, org_id="o").per_call_cap_micro_usd))
        return 0
    monkeypatch.setattr(module, "live", _live)
    assert module.main(["--live", "--site", "expert", "--spend-ok", "--max-usd", "7",
                        "--thinking", "adaptive", "--ceiling", "12000", "--per-call-usd", "0.15"]) == 0
    # ⛔ RESTATED by STEP-13b M38.C3.L-interface.V13.U03: `live` is also handed the ladder's rungs (none here: one model).
    assert seen["kw"] == {"max_usd": 7.0, "thinking": "adaptive", "ceiling": 12000,
                          "per_call_usd": "0.15", "ladder": None}
    assert seen["during"] == (THINKING_ADAPTIVE, 12000, 150_000)
    assert (S.thinking_mode(S.SITE_EXPERT), S.max_output_tokens(S.SITE_EXPERT)) == ("off", 6000)


# =================================================================================================
# 2 · the run's site settings, and nothing after it
# =================================================================================================
def test_the_site_settings_hold_for_the_run_and_are_put_back():
    module = _module()
    before = (S.SITE_THINKING[S.SITE_EXPERT], S.max_output_tokens(S.SITE_EXPERT),
              B.OWN_BUDGETS[S.SITE_EXPERT])
    with module.site_settings(S.SITE_EXPERT, thinking=THINKING_ADAPTIVE, ceiling=12000,
                              per_call_usd="0.15"):
        assert S.thinking_mode(S.SITE_EXPERT) == THINKING_ADAPTIVE
        assert S.max_output_tokens(S.SITE_EXPERT) == 12000
        assert B.NarrativeBudget.for_site(S.SITE_EXPERT, org_id="o").per_call_cap_micro_usd == 150_000
        assert B.OWN_BUDGETS[S.SITE_EXPERT][0] == before[2][0], "the day's cap is not the run's to move"
    assert (S.SITE_THINKING[S.SITE_EXPERT], S.max_output_tokens(S.SITE_EXPERT),
            B.OWN_BUDGETS[S.SITE_EXPERT]) == before


def test_no_setting_changes_nothing():
    module = _module()
    before = dict(S.SITE_THINKING), dict(S.SITE_MAX_OUTPUT_TOKENS), dict(B.OWN_BUDGETS)
    with module.site_settings(S.SITE_EXPERT):
        assert (dict(S.SITE_THINKING), dict(S.SITE_MAX_OUTPUT_TOKENS), dict(B.OWN_BUDGETS)) == before


def test_the_settings_are_put_back_when_the_run_fails():
    module = _module()
    with pytest.raises(RuntimeError):
        with module.site_settings(S.SITE_EXPERT, ceiling=12000):
            raise RuntimeError("the run died")
    assert S.max_output_tokens(S.SITE_EXPERT) == 6000


# =================================================================================================
# 3 · ⛔ the hard stop
# =================================================================================================
class _Model:
    model = "claude-sonnet-5"
    supports_thinking = True

    def __init__(self, result: LLMResult) -> None:
        self.result, self.calls = result, 0

    def call(self, prompt, *, max_tokens=4096, **kw):
        self.calls += 1
        return self.result


def _cut() -> LLMResult:
    return LLMResult(parsed={}, raw="{", ok=False, truncated=True, model="claude-sonnet-5",
                     input_tokens=5600, output_tokens=6000, error="truncated")


def test_a_call_whose_worst_case_crosses_the_cap_is_never_made():
    module = _module()
    cap = module.SpendCap(0.05, "claude-sonnet-5")
    inner = _Model(_cut())
    capped = module.CappedModel(inner, cap)
    with pytest.raises(module.SpendCapReached):
        capped.call("x" * 22_400, max_tokens=6000)        # worst ≈ $0.011 in + $0.06 out > $0.05
    assert inner.calls == 0 and cap.reached and cap.spent_usd == 0


def test_every_call_made_is_charged_a_cut_one_included():
    module = _module()
    cap = module.SpendCap(1.0, "claude-sonnet-5")
    capped = module.CappedModel(_Model(_cut()), cap)
    capped.call("x" * 100, max_tokens=6000)
    assert cap.spent_usd == pytest.approx(5600 / 1e6 * 2 + 6000 / 1e6 * 10)
    assert not cap.reached and capped.supports_thinking is True and capped.model == "claude-sonnet-5"


def test_the_cap_stops_before_the_call_that_would_cross_it():
    """Two cut calls at ~$0.071 each fit $0.20 with the third's worst case refused."""
    module = _module()
    cap = module.SpendCap(0.20, "claude-sonnet-5")
    inner = _Model(_cut())
    capped = module.CappedModel(inner, cap)
    capped.call("x" * 100, max_tokens=6000)
    capped.call("x" * 100, max_tokens=6000)
    with pytest.raises(module.SpendCapReached):
        capped.call("x" * 100, max_tokens=6000)
    assert inner.calls == 2 and cap.spent_usd <= 0.20


# =================================================================================================
# 4 · the scorecard sums every call
# =================================================================================================
def test_the_spend_is_every_call_of_the_site_a_cut_included():
    ledger = [
        {"site": "expert", "input_tokens": 5600, "output_tokens": 6000, "truncated": True},
        {"site": "expert", "input_tokens": 5600, "output_tokens": 2000, "truncated": False},
        {"site": "decider", "input_tokens": 900, "output_tokens": 90, "truncated": False},
    ]
    assert _module().spend(ledger, "expert") == {"calls": 2, "truncated_calls": 1,
                                                 "tokens_in": 11_200, "tokens_out": 8000}
    assert _module().spend(ledger, None)["calls"] == 3


def test_the_scorecard_names_its_arm():
    module = _module()
    assert module.scorecard_name("2026-10-13", "claude-sonnet-5", "expert", None) == \
        "2026-10-13-claude-sonnet-5-expert"
    assert module.scorecard_name("2026-10-13", "claude-sonnet-5", "expert", "adaptive") == \
        "2026-10-13-claude-sonnet-5-expert-adaptive"
    assert module.scorecard_name("2026-10-13", "claude-haiku-4-5", None, None) == \
        "2026-10-13-claude-haiku-4-5"


def test_the_live_model_and_the_router_take_the_thinking_mode():
    module = _module()
    assert module.LiveModel.supports_thinking is True

    class _Rest:
        model = "ideal"

        def __init__(self):
            self.kw = None

        def call(self, prompt, *, max_tokens=4096):
            self.kw = {"max_tokens": max_tokens}
            return "rest"
    live, rest = _Model(_cut()), _Rest()
    router = module.SiteModel("expert", live, rest)
    assert router.supports_thinking is True
    assert router.call("an unmarked prompt", max_tokens=600, thinking="off", timeout_s=9.0) == "rest"
    assert rest.kw == {"max_tokens": 600}, "the ideal reader is never handed the live model's settings"


# =================================================================================================
# 5 · end to end: a cut call is counted on the card (a scratch database)
# =================================================================================================
def test_a_cut_call_is_on_the_card_end_to_end(monkeypatch, tmp_path):
    """The live pass on one case, its "live" expert cut at the ceiling on every call: the card counts
    each cut call and its tokens — the cassette, which keeps none of them, would say $0."""
    import json
    import os
    if not os.environ.get("GENIOS_TEST_DATABASE_URL"):
        pytest.skip("GENIOS_TEST_DATABASE_URL not set — the live pass runs a case on a scratch database")
    from tests.replays.founder_case import load_cases
    from tests.replays.ideal_reader import IdealReader
    module = _module()
    case = next(c for c in load_cases() if c.case_id == "F13")

    class _CutsEveryAnswer:
        def __init__(self, _key, model):
            self._reader, self.model = IdealReader(case), model

        def content_hash(self, material):
            return self._reader.content_hash(material)

        def call(self, prompt, *, max_tokens=4096, **kw):
            return LLMResult(parsed={}, raw='{"mode": "act", "facts": [', ok=False, truncated=True,
                             model=self.model, input_tokens=len(prompt) // 4, output_tokens=max_tokens,
                             error=f"truncated (max_tokens={max_tokens})")
    monkeypatch.setattr(module, "LiveModel", _CutsEveryAnswer)
    monkeypatch.setattr(module, "SCORES", tmp_path)
    monkeypatch.setenv(module.LIVE_KEY_ENV, "sk-not-a-real-key")
    assert module.main(["--live", "--site", "expert", "--spend-ok", "--max-usd", "5", "F13"]) == 0
    [card_file] = list(tmp_path.glob("*-claude-sonnet-5-expert.json"))
    card = json.loads(card_file.read_text())
    assert card["calls"] >= 1 and card["truncated_calls"] == card["calls"]
    assert card["tokens_out"] == 6000 * card["calls"] and card["cost_usd"] > 0
    assert card["cases"][0]["truncated_calls"] == card["calls"] and card["stopped_at_cap"] is None
