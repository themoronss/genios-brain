"""GeniOS-011 S07.U1 · golden_eval asks R-9 on its production tier, takes the L2 path, and probes before it pays.

    pytest tests/scripts/test_golden_eval_asks_r9_on_its_tier.py -q

The audit's `process-golden-eval-r9-wrong-model`: `SITE_TIERS` held the expert alone, so `--site reason_l2`
priced and asked R-9 on `DEFAULT_MODEL` (Haiku 4.5) — never production's `claude-sonnet-5` — and the run's
site settings (`site_settings`) were applied only to a site in `SITE_TIERS`. Nothing set `GENIOS_GOLDEN_L2`
either, so the cases ran today's path, where R-9 is never asked at all (`engine_runner.switch_on_the_expert`
switches `l2_reasoning` on only down the L2 path): a live R-9 pass would have spent nothing and measured nothing.
Now:

  * `SITE_TIERS` names `reason_l2` → R-9, so its model is its tier's and its settings are the site table's own
    (thinking off, an 8,000-token ceiling) — and a D72-style arm (`--thinking`, `--ceiling`) can move them;
  * `--l2-path` sets `GENIOS_GOLDEN_L2=1` for the run and puts it back; without it the run takes today's path
    even from a shell that exported the switch, and R-9 without the path is refused before anything is spent;
  * `--probe` makes at most two live calls and prints each one's `stop_reason` and `output_tokens` — the
    1-2 calls read before any paid pass (Sonnet 5's 203 cut calls of 12 Oct were found only after the spend).

No model is called here: every "live" model is a fake. The three end-to-end tests run a case on the scratch
database and skip without one.
"""
from __future__ import annotations

import importlib.util
import os
import threading
import types
from pathlib import Path

import pytest

from genios_engine.context.llm.client import LLMResult
from genios_engine.reason.bundle import sites as S
from genios_engine.reason.llm_sites import tier_model

pytestmark = pytest.mark.unit

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "golden_eval.py"
L2_ENV = "GENIOS_GOLDEN_L2"


def _module():
    spec = importlib.util.spec_from_file_location("golden_eval", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _live_args(*more: str) -> list[str]:
    return ["--live", "--spend-ok", "--max-usd", "1", *more]


# =================================================================================================
# 1 · R-9's model and settings are its production tier's
# =================================================================================================
def test_reason_l2_is_a_site_with_a_tier_of_its_own():
    from tests.replays.harness import SITE_MARKERS
    module = _module()
    assert module.SITE_TIERS.get("reason_l2") == S.SITE_REASON == "R-9"
    assert "reason_l2" in {site for site, _m, _marker in SITE_MARKERS}, "a harness site, so --site takes it"


def test_r9_is_asked_on_its_tiers_model_never_the_default():
    module = _module()
    assert module.model_for("reason_l2", None) == tier_model(S.tier_for(S.SITE_REASON)) == "claude-sonnet-5"
    assert module.model_for("reason_l2", None) != module.DEFAULT_MODEL
    assert module.model_for("reason_l2", "claude-opus-5") == "claude-opus-5", "a named model still wins"


def test_r9s_settings_are_the_site_tables_own():
    """Thinking off and an 8,000-token ceiling (`reason/bundle/sites`), with R-9's own 160 s timeout."""
    module = _module()
    assert module.site_profile("reason_l2") == {
        "r_site": "R-9", "model": "claude-sonnet-5", "thinking": "off", "ceiling": 8000, "timeout_s": 160.0}
    assert module.site_profile("reason_l2")["ceiling"] == S.max_output_tokens(S.SITE_REASON)
    assert module.site_profile("reason_l2")["thinking"] == S.thinking_mode(S.SITE_REASON)
    assert module.site_profile("decider") is None and module.site_profile(None) is None


def test_the_dry_run_names_r9s_model_and_settings_with_no_key(monkeypatch, capsys):
    """The DONE WHEN's dry run: no key, no database, no model — and it says R-9 is asked on Sonnet 5 with
    thinking off at 8,000, and that no R-9 call is recorded to price (the L2 path is never recorded)."""
    module = _module()
    monkeypatch.delenv(module.LIVE_KEY_ENV, raising=False)
    monkeypatch.delenv("GENIOS_TEST_DATABASE_URL", raising=False)
    monkeypatch.setattr(module, "LiveModel", lambda *a, **k: pytest.fail("a dry run built a live model"))
    assert module.main(["--dry-run", "--site", "reason_l2"]) == 0
    out = capsys.readouterr().out
    assert "R-9 on claude-sonnet-5" in out and "thinking off" in out and "ceiling 8000" in out, out[-900:]
    assert "on claude-sonnet-5 at list price" in out and "Nothing was run" in out
    assert "never recorded" in out and "--probe" in out, "a $0.00 estimate is not presented as the cost"


def test_a_run_setting_reaches_r9_for_the_run_alone(monkeypatch):
    """R-9 in `SITE_TIERS` is what lets `site_settings` hold its row: by default its own (off, 8,000), and an
    arm's `--ceiling` while the pass runs — put back after."""
    module = _module()
    monkeypatch.setenv(module.LIVE_KEY_ENV, "sk-not-a-real-key")
    seen = []
    monkeypatch.setattr(module, "live", lambda *a, **k: seen.append(
        (S.thinking_mode(S.SITE_REASON), S.max_output_tokens(S.SITE_REASON))) or 0)
    assert module.main(_live_args("--site", "reason_l2", "--l2-path")) == 0
    assert module.main(_live_args("--site", "reason_l2", "--l2-path", "--ceiling", "12000")) == 0
    assert seen == [("off", 8000), ("off", 12000)]
    assert S.max_output_tokens(S.SITE_REASON) == 8000, "put back after the run"


# =================================================================================================
# 2 · --l2-path is the path the run takes
# =================================================================================================
def test_the_l2_path_flag_sets_the_switch_for_the_run_and_puts_it_back(monkeypatch):
    from tests.replays.engine_runner import L2_PATH_ENV
    from tests.replays.engine_runner import l2_path
    module = _module()
    assert L2_PATH_ENV == L2_ENV
    monkeypatch.delenv(L2_ENV, raising=False)
    monkeypatch.setenv(module.LIVE_KEY_ENV, "sk-not-a-real-key")
    seen = []
    monkeypatch.setattr(module, "live", lambda *a, **k: seen.append((os.environ.get(L2_ENV), l2_path())) or 0)
    assert module.main(_live_args("--site", "reason_l2", "--l2-path")) == 0
    assert seen == [("1", True)] and L2_ENV not in os.environ


def test_without_the_flag_an_inherited_switch_does_not_choose_the_path(monkeypatch):
    """The path a pass takes is its flag's, never a shell's: an exported `GENIOS_GOLDEN_L2=1` would otherwise
    turn an expert pass into an L2 one with nothing on the command line saying so."""
    from tests.replays.engine_runner import l2_path
    module = _module()
    monkeypatch.setenv(L2_ENV, "1")
    monkeypatch.setenv(module.LIVE_KEY_ENV, "sk-not-a-real-key")
    seen = []
    monkeypatch.setattr(module, "live", lambda *a, **k: seen.append((os.environ.get(L2_ENV), l2_path())) or 0)
    assert module.main(_live_args("--site", "expert")) == 0
    assert seen == [(None, False)] and os.environ.get(L2_ENV) == "1", "and the shell's is put back"


@pytest.mark.parametrize("mode", [["--live"], ["--probe"]])
def test_r9_without_the_l2_path_is_refused_before_anything_is_spent(monkeypatch, capsys, mode):
    """Today's path never asks R-9: the pass would spend nothing and measure nothing, and say it measured."""
    module = _module()
    monkeypatch.setenv(module.LIVE_KEY_ENV, "sk-not-a-real-key")
    monkeypatch.setattr(module, "live", lambda *a, **k: pytest.fail("the pass started"))
    monkeypatch.setattr(module, "probe", lambda *a, **k: pytest.fail("the probe started"))
    with pytest.raises(SystemExit) as stop:
        module.main([*mode, "--site", "reason_l2", "--spend-ok", "--max-usd", "1"])
    assert stop.value.code == 2 and "--l2-path" in capsys.readouterr().err


@pytest.mark.parametrize("args", [["--record", "--l2-path"],
                                  ["--live", "--record", "--l2-path", "--spend-ok", "--max-usd", "1"]])
def test_the_l2_path_never_records_over_todays_cassettes(monkeypatch, capsys, args):
    """The cassettes are today's path, and CI replays them so (`l2_score` records nothing either)."""
    module = _module()
    monkeypatch.setenv(module.LIVE_KEY_ENV, "sk-not-a-real-key")
    monkeypatch.setattr(module, "record", lambda *a, **k: pytest.fail("cassettes re-recorded"))
    monkeypatch.setattr(module, "live", lambda *a, **k: pytest.fail("the pass started"))
    with pytest.raises(SystemExit) as stop:
        module.main(args)
    assert stop.value.code == 2 and "today's cassettes" in capsys.readouterr().err


def test_the_scorecard_names_the_l2_path():
    module = _module()
    assert module.scorecard_name("2026-10-23", "claude-sonnet-5", "reason_l2", None, l2=True) == \
        "2026-10-23-claude-sonnet-5-reason_l2-l2"
    assert module.scorecard_name("2026-10-23", "claude-sonnet-5", "expert", None) == \
        "2026-10-23-claude-sonnet-5-expert", "today's path names its card as before"


# =================================================================================================
# 3 · --probe: at most two live calls, each one's stop_reason and output_tokens printed
# =================================================================================================
class _Inner:
    """A live model that says why it stopped, the way `LiveModel.stop_reason` does."""

    model = "claude-sonnet-5"
    supports_thinking = True

    def __init__(self, stops=("max_tokens", "end_turn", "end_turn")) -> None:
        self.calls, self._stops, self._local = 0, list(stops), threading.local()
        self._lock = threading.Lock()

    def content_hash(self, material):
        return "h"

    def stop_reason(self):
        return getattr(self._local, "last", None)

    def call(self, prompt, *, max_tokens=4096, **kw):
        with self._lock:
            self.calls += 1
            self._local.last = self._stops[(self.calls - 1) % len(self._stops)]
        return LLMResult(parsed={"ok": True}, raw="{}", model=self.model, input_tokens=1200,
                         output_tokens=max_tokens if self._local.last == "max_tokens" else 3100)


def _r9_prompt() -> str:
    from tests.replays.harness import SITE_MARKERS
    return "…" + {site: m for site, _module_, m in SITE_MARKERS}["reason_l2"] + "…"


def test_the_probe_makes_at_most_two_calls_and_prints_each_ones_stop_reason(capsys):
    module = _module()
    inner = _Inner()
    probe = module.ProbeModel(inner)
    probe.call(_r9_prompt(), max_tokens=8000, thinking="off", timeout_s=160.0)
    probe.call(_r9_prompt(), max_tokens=8000, thinking="off", timeout_s=160.0)
    with pytest.raises(module.ProbeComplete):
        probe.call(_r9_prompt(), max_tokens=8000, thinking="off")
    assert inner.calls == 2 == len(probe.made) == module.PROBE_CALLS
    assert not issubclass(module.ProbeComplete, Exception), \
        "a site's `except Exception` must not swallow the stop and let the case ask a third time"
    lines = [line for line in capsys.readouterr().out.splitlines() if line.startswith("probe ")]
    assert len(lines) == 2, lines
    assert "stop_reason=max_tokens" in lines[0] and "output_tokens=8000" in lines[0]
    assert "stop_reason=end_turn" in lines[1] and "output_tokens=3100" in lines[1]
    assert all("reason_l2" in line and "max_tokens=8000" in line and "thinking=off" in line for line in lines)
    assert [row["stop_reason"] for row in probe.made] == ["max_tokens", "end_turn"]


def test_the_probe_holds_at_two_when_the_drain_asks_from_many_threads():
    """`run_sync` and the L2 drain run thread pools over one client: the count is taken under a lock."""
    module = _module()
    inner = _Inner()
    probe = module.ProbeModel(inner)
    stopped = []

    def _ask():
        try:
            probe.call(_r9_prompt(), max_tokens=8000)
        except module.ProbeComplete:
            stopped.append(1)
    threads = [threading.Thread(target=_ask) for _ in range(16)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert inner.calls == 2 and len(stopped) == 14


def test_the_live_model_keeps_each_responses_stop_reason(monkeypatch):
    """`LLMClient.call` reads `stop_reason` only to say `truncated`; the probe needs the API's own word, also on
    a call with R-9's own timeout (`with_options`, a second client)."""
    import anthropic

    class _Fake:
        def __init__(self, *, api_key=None, stop="end_turn", **_kw):
            self.stop = stop
            self.messages = types.SimpleNamespace(create=lambda **kw: types.SimpleNamespace(
                content=[types.SimpleNamespace(type="text", text='{"ok": true}')], stop_reason=self.stop,
                usage=types.SimpleNamespace(input_tokens=3, output_tokens=2)))

        def with_options(self, **_opts):
            return _Fake(stop="max_tokens")
    monkeypatch.setattr(anthropic, "Anthropic", _Fake)
    live = _module().LiveModel("sk-not-a-real-key", "claude-sonnet-5")
    assert live.stop_reason() is None
    live.call("a prompt", max_tokens=8000)
    assert live.stop_reason() == "end_turn"
    result = live.call("a prompt", max_tokens=8000, timeout_s=160.0)
    assert live.stop_reason() == "max_tokens" and result.truncated


@pytest.mark.parametrize("drop", ["key", "--spend-ok", "--max-usd"])
def test_a_probe_needs_every_consent_a_pass_needs(monkeypatch, drop):
    module = _module()
    monkeypatch.setattr(module, "probe", lambda *a, **k: pytest.fail("the probe started"))
    if drop == "key":
        monkeypatch.delenv(module.LIVE_KEY_ENV, raising=False)
    else:
        monkeypatch.setenv(module.LIVE_KEY_ENV, "sk-not-a-real-key")
    args = ["--probe", "--site", "reason_l2", "--l2-path", "--spend-ok", "--max-usd", "1"]
    if drop == "--spend-ok":
        args.remove("--spend-ok")
    if drop == "--max-usd":
        args = args[:-2]
    assert module.main(args) == 2


def test_the_probe_runs_instead_of_the_pass_on_r9s_tier_and_path(monkeypatch):
    module = _module()
    monkeypatch.delenv(L2_ENV, raising=False)
    monkeypatch.setenv(module.LIVE_KEY_ENV, "sk-not-a-real-key")
    monkeypatch.setattr(module, "live", lambda *a, **k: pytest.fail("the paid pass started"))
    seen = {}

    def _probe(*a, **k):
        seen.update(args=a, kw=k, path=os.environ.get(L2_ENV),
                    settings=(S.thinking_mode(S.SITE_REASON), S.max_output_tokens(S.SITE_REASON)))
        return 0
    monkeypatch.setattr(module, "probe", _probe)
    assert module.main(["--probe", "--site", "reason_l2", "--l2-path", "--spend-ok", "--max-usd", "0.5",
                        "F13"]) == 0
    assert seen["args"] == (["F13"], "claude-sonnet-5", "reason_l2") and seen["kw"] == {"max_usd": 0.5}
    assert seen["path"] == "1" and seen["settings"] == ("off", 8000)


@pytest.mark.parametrize("args", [["--probe", "--dry-run"], ["--probe", "--record"],
                                  ["--probe", "--site", "brief"]])
def test_a_probe_is_a_live_pass_only(monkeypatch, capsys, args):
    module = _module()
    monkeypatch.setenv(module.LIVE_KEY_ENV, "sk-not-a-real-key")
    monkeypatch.setattr(module, "probe", lambda *a, **k: pytest.fail("the probe started"))
    with pytest.raises(SystemExit) as stop:
        module.main([*args, "--spend-ok", "--max-usd", "1"])
    assert stop.value.code == 2 and "--probe" in capsys.readouterr().err


# =================================================================================================
# 4 · end to end on the scratch database: R-9 asked live, down the L2 path, with its own settings
# =================================================================================================
class _Faithful:
    """The ideal reader standing in for the live model, keeping what each R-9 call was asked with."""

    supports_thinking = True
    asked: list = []

    def __init__(self, case):
        from tests.replays.ideal_reader import IdealReader
        self._reader, self._local = IdealReader(case), threading.local()

    def content_hash(self, material):
        return self._reader.content_hash(material)

    def stop_reason(self):
        return getattr(self._local, "last", None)

    def call(self, prompt, *, max_tokens=4096, **kw):
        from tests.replays.harness import identify_site
        type(self).asked.append((identify_site(prompt), max_tokens, kw.get("thinking")))
        self._local.last = "end_turn"
        return self._reader.call(prompt, max_tokens=max_tokens, **kw)


def _f13():
    from tests.replays.founder_case import load_cases
    return next(c for c in load_cases() if c.case_id == "F13")


def _tenant_left(org: str) -> bool:
    from sqlalchemy import text

    from genios_engine.api import routes
    with routes._graph.engine.connect() as conn:
        return bool(conn.execute(text("select count(*) from orgs where id = :o"), {"o": org}).scalar())


@pytest.fixture
def own_tenant(monkeypatch):
    """The scratch database is shared with other runs: this test's case runs on a tenant of its own, never F13's
    usual `org_golden_f13`, which another run of the same case would wipe from under it."""
    import uuid

    from tests.replays import engine_runner
    org = f"{engine_runner.ORG_PREFIX}s07u1_{uuid.uuid4().hex[:10]}"
    real = engine_runner.run_case
    monkeypatch.setattr(engine_runner, "run_case", lambda case, llm, **kw: real(case, llm, **{**kw, "org_id": org}))
    return org


def test_the_r9_live_pass_takes_the_l2_path_end_to_end(monkeypatch, tmp_path, own_tenant):
    import json
    if not os.environ.get("GENIOS_TEST_DATABASE_URL"):
        pytest.skip("GENIOS_TEST_DATABASE_URL not set — the live pass runs a case on a scratch database")
    module = _module()
    case = _f13()

    class _Live(_Faithful):
        asked: list = []

        def __init__(self, _key, model):
            super().__init__(case)
            self.model = model
    monkeypatch.delenv(L2_ENV, raising=False)
    monkeypatch.setattr(module, "LiveModel", _Live)
    monkeypatch.setattr(module, "SCORES", tmp_path)
    monkeypatch.setenv(module.LIVE_KEY_ENV, "sk-not-a-real-key")
    assert module.main(["--live", "--site", "reason_l2", "--l2-path", "--spend-ok", "--max-usd", "1", "F13"]) == 0
    [card_file] = list(tmp_path.glob("*-claude-sonnet-5-reason_l2-l2.json"))
    card = json.loads(card_file.read_text())
    assert card["site"] == "reason_l2" and card["model"] == "claude-sonnet-5" and card["l2_path"] is True
    assert card["calls"] >= 1, "R-9 was asked: the case ran down the L2 path"
    # Set beside the authored answers ON THE SAME PATH — the ideal reader's own, since no cassette holds the L2
    # path (today's cassette, replayed down it, missed at R-9's first prompt after the live case was paid for).
    [row] = card["cases"]
    assert row["verdict"] == row["authored_verdict"] and card["moved"] == [], row
    assert _Live.asked and {site for site, _m, _t in _Live.asked} == {"reason_l2"}, "only R-9 went live"
    assert {(m, t) for _s, m, t in _Live.asked} == {(8000, "off")}, "with R-9's own settings"
    assert L2_ENV not in os.environ and not _tenant_left(own_tenant)


def test_the_probe_end_to_end_prints_and_writes_nothing(monkeypatch, tmp_path, capsys, own_tenant):
    if not os.environ.get("GENIOS_TEST_DATABASE_URL"):
        pytest.skip("GENIOS_TEST_DATABASE_URL not set — the probe runs a case on a scratch database")
    module = _module()
    case = _f13()

    class _Live(_Faithful):
        asked: list = []

        def __init__(self, _key, model):
            super().__init__(case)
            self.model = model
    monkeypatch.delenv(L2_ENV, raising=False)
    monkeypatch.setattr(module, "LiveModel", _Live)
    monkeypatch.setattr(module, "SCORES", tmp_path)
    monkeypatch.setenv(module.LIVE_KEY_ENV, "sk-not-a-real-key")
    assert module.main(["--probe", "--site", "reason_l2", "--l2-path", "--spend-ok", "--max-usd", "1",
                        "F13"]) == 0
    lines = [line for line in capsys.readouterr().out.splitlines() if line.startswith("probe ")]
    assert 1 <= len(lines) <= 2 and len(_Live.asked) == len(lines), lines
    assert all("stop_reason=end_turn" in line and "output_tokens=" in line for line in lines)
    assert list(tmp_path.iterdir()) == [], "a probe writes no scorecard"
    assert not _tenant_left(own_tenant)


def test_the_probes_stop_ends_the_case_mid_chain_and_removes_its_tenant(monkeypatch, tmp_path, capsys, own_tenant):
    """With no site every prompt goes to the "live" model, so F13 asks far more than two: the third raises
    `ProbeComplete` from inside the real chain (its `except Exception` sites and thread pools), the case stops
    there, and `run_case` removes the tenant on that exit too."""
    if not os.environ.get("GENIOS_TEST_DATABASE_URL"):
        pytest.skip("GENIOS_TEST_DATABASE_URL not set — the probe runs a case on a scratch database")
    module = _module()
    case = _f13()

    class _Live(_Faithful):
        asked: list = []

        def __init__(self, _key, model):
            super().__init__(case)
            self.model = model
    monkeypatch.delenv(L2_ENV, raising=False)
    monkeypatch.setattr(module, "LiveModel", _Live)
    monkeypatch.setattr(module, "SCORES", tmp_path)
    monkeypatch.setenv(module.LIVE_KEY_ENV, "sk-not-a-real-key")
    assert module.main(["--probe", "--spend-ok", "--max-usd", "1", "F13"]) == 0
    lines = [line for line in capsys.readouterr().out.splitlines() if line.startswith("probe ")]
    assert len(lines) == 2 == len(_Live.asked), lines
    assert lines[0].startswith("probe 1/2 · ") and lines[1].startswith("probe 2/2 · ")
    assert list(tmp_path.iterdir()) == [] and not _tenant_left(own_tenant), "the probe's stop removes its tenant"
