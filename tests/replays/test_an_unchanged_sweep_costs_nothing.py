"""STEP-02 · the acceptance: a sweep that brings nothing new costs nothing, and changes nothing.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… GENIOS_GOLDEN_REQUIRED=1 pytest tests/replays/test_an_unchanged_sweep_costs_nothing.py -q

Tree `yc2_w27_s02/M20.C6.L-integration.V5.U03`. Every founder case of the golden set is run through
the REAL chain (`engine_runner.run_case`, the ideal reader answering — no spend) with one more sweep
15 minutes after its last, bringing nothing new. That sweep:

  * asks the decider nothing and R-1 nothing — measured before STEP-02: F13 2 calls, F12/F25/F28 4,
    F07 5, F29 12, every one for the same answer (`speedrun008/YC-II W27/` STEP-02 §8.1);
  * leaves the founder the cards the case's own last sweep left;
  * and the case is marked exactly as its recorded run is — the gate moves no verdict on the board.

It also caught the gate's own first rule: a 24-hour renewal margin re-decided F27's card on every
sweep of its last day, and renewed nothing (`reason/change_gate.RENEW_MARGIN`, now zero).
"""
from __future__ import annotations

import collections
import dataclasses
import datetime as dt
import os

import pytest

from tests.replays import cassettes
from tests.replays.founder_case import load_cases
from tests.replays.harness import identify_site
from tests.replays.marking import judge

CASES = load_cases()
PAID = ("decider", "r1")


def _scratch_db() -> None:
    if os.environ.get("GENIOS_TEST_DATABASE_URL"):
        return
    if os.environ.get("GENIOS_GOLDEN_REQUIRED") == "1":
        pytest.fail("GENIOS_GOLDEN_REQUIRED=1 and no GENIOS_TEST_DATABASE_URL")
    pytest.skip("needs GENIOS_TEST_DATABASE_URL pointing at a scratch database")


class _Tagged:
    """The model the case is run with, every call tagged with the sweep it was made in."""

    def __init__(self, inner, sweep: dict) -> None:
        self.inner, self.sweep = inner, sweep
        self.model = getattr(inner, "model", "")
        self.calls: list[tuple[int, str]] = []

    def content_hash(self, material: str) -> str:
        return self.inner.content_hash(material)

    def call(self, prompt: str, **kw):
        self.calls.append((self.sweep["n"], identify_site(prompt)))
        return self.inner.call(prompt, **kw)


def _open_after(run, sweep: int):
    return sorted((c.text, c.level, c.output_lane or "") for c in run.cards if sweep in c.sweeps)


@pytest.mark.pg
@pytest.mark.golden
@pytest.mark.parametrize("case", CASES, ids=lambda c: c.case_id)
def test_an_unchanged_sweep_costs_nothing_and_changes_nothing(case, monkeypatch):
    _scratch_db()
    from genios_engine.api import routes
    from tests.replays.engine_runner import run_case
    from tests.replays.harness import CassetteRecorder
    from tests.replays.ideal_reader import IdealReader

    extended = dataclasses.replace(
        case, sweeps=case.sweeps + (case.sweeps[-1] + dt.timedelta(minutes=15),))
    last = len(extended.sweeps) - 1
    sweep = {"n": -1}
    original = routes._run_l2_chain

    def chain(org_id, *, eval_time=None):
        sweep["n"] += 1
        return original(org_id, eval_time=eval_time)

    monkeypatch.setattr(routes, "_run_l2_chain", chain)
    model = _Tagged(CassetteRecorder(IdealReader(extended)), sweep)
    run = run_case(extended, model)

    on_last = collections.Counter(site for s, site in model.calls if s == last)
    paid = {site: n for site, n in on_last.items() if site in PAID}
    assert not paid, f"{case.case_id}: the unchanged sweep paid {paid} (all its calls: {dict(on_last)})"
    assert _open_after(run, last) == _open_after(run, last - 1), (
        f"{case.case_id}: the unchanged sweep changed what the founder sees")
    recorded = judge(case, cassettes.replayed(case))
    assert judge(case, run).verdict == recorded.verdict, (
        f"{case.case_id}: the gate moved the verdict from {recorded.verdict}")


@pytest.mark.pg
@pytest.mark.golden
def test_without_the_gate_the_same_sweep_pays_again(monkeypatch):
    """⛔ THE NEGATIVE CONTROL: the zeros above are the gate's. With every verdict forced to
    "decide", F13's unchanged sweep asks the decider and R-1 again — what it did before STEP-02."""
    _scratch_db()
    from genios_engine.api import routes
    from genios_engine.reason import change_gate
    from tests.replays.engine_runner import run_case
    from tests.replays.harness import CassetteRecorder
    from tests.replays.ideal_reader import IdealReader

    monkeypatch.setattr(change_gate, "should_skip",
                        lambda *a, **kw: change_gate.GateVerdict(False, change_gate.CHANGED))
    case = next(c for c in CASES if c.case_id == "F13")
    extended = dataclasses.replace(
        case, sweeps=case.sweeps + (case.sweeps[-1] + dt.timedelta(minutes=15),))
    sweep = {"n": -1}
    original = routes._run_l2_chain

    def chain(org_id, *, eval_time=None):
        sweep["n"] += 1
        return original(org_id, eval_time=eval_time)

    monkeypatch.setattr(routes, "_run_l2_chain", chain)
    model = _Tagged(CassetteRecorder(IdealReader(extended)), sweep)
    run_case(extended, model)
    last = len(extended.sweeps) - 1
    assert {site for s, site in model.calls if s == last} >= {"decider", "r1"}
