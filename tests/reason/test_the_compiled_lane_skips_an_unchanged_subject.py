"""STEP-02 · the compiled lane skips a situation whose decision inputs did not move — and only that.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… pytest tests/reason/test_the_compiled_lane_skips_an_unchanged_subject.py -q

Tree `yc2_w27_s02/M20.C3.L-integration.V2.U02`, on the REAL chain: a founder case of the golden set
run through `tests/replays/engine_runner.run_case`, with the ideal reader answering every prompt (no
spend), and one more sweep 15 minutes after its last.

Measured before this unit (`speedrun008/YC-II W27/` STEP-02 §8.1): on that extra sweep the compiled
lane asked the decider again for every situation — F13 once, F29 seven times, three of them shadow
rows whose answer is thrown away — and no card changed.

  * the unchanged sweep asks the decider nothing for a compiled (`expertise.*`) subject, live or
    shadow, and every card is what it was;
  * a real change — the pack's `authority_revision` moving, one of the two inputs outside the request
    — decides them again;
  * a gate that cannot fingerprint decides them too: it fails open, never shut.
"""
from __future__ import annotations

import collections
import dataclasses
import datetime as dt
import os

import pytest
from sqlalchemy import text

pytestmark = pytest.mark.pg

if not os.environ.get("GENIOS_TEST_DATABASE_URL"):
    pytest.skip("needs GENIOS_TEST_DATABASE_URL pointing at a scratch database",
                allow_module_level=True)

from tests.replays.engine_runner import run_case                    # noqa: E402
from tests.replays.founder_case import load_cases                   # noqa: E402
from tests.replays.harness import CassetteRecorder                  # noqa: E402
from tests.replays.ideal_reader import IdealReader                  # noqa: E402

CASES = {c.case_id: c for c in load_cases()}


def _run(case_id: str, monkeypatch, *, before_last=None):
    """The case, plus one sweep 15 minutes after its last; the decider's calls by sweep."""
    from genios_engine.api import routes
    from genios_engine.reason import llm_decision_maker as dm

    base = CASES[case_id]
    case = dataclasses.replace(
        base, sweeps=base.sweeps + (base.sweeps[-1] + dt.timedelta(minutes=15),))
    last = len(case.sweeps) - 1
    sweep = {"n": -1}
    calls: dict[int, list[str]] = collections.defaultdict(list)
    _decide, _chain = dm.decide_with_llm, routes._run_l2_chain

    def decide(request, *a, **kw):
        calls[sweep["n"]].append(str(request.capability.capability_id))
        return _decide(request, *a, **kw)

    def chain(org_id, *, eval_time=None):
        sweep["n"] += 1
        if sweep["n"] == last and before_last is not None:
            before_last(org_id)
        return _chain(org_id, eval_time=eval_time)

    monkeypatch.setattr(dm, "decide_with_llm", decide)
    monkeypatch.setattr(routes, "_run_l2_chain", chain)
    run = run_case(case, CassetteRecorder(IdealReader(case)))
    compiled = lambda ids: [c for c in ids if c.startswith("expertise.")]      # noqa: E731
    return run, compiled(calls[last - 1]), compiled(calls[last])


def _open_after(run, sweep: int):
    """What the founder sees after one sweep — each card's text, level and lane; not its id."""
    return sorted((c.text, c.level, c.output_lane or "") for c in run.cards if sweep in c.sweeps)


@pytest.mark.parametrize("case_id", ["F13", "F29"])
def test_an_unchanged_sweep_asks_the_compiled_lane_nothing(case_id, monkeypatch):
    run, before, after = _run(case_id, monkeypatch)
    assert before, f"{case_id}: the compiled lane decided nothing on the case's own last sweep"
    assert after == [], f"{case_id}: re-decided on an unchanged sweep: {after}"
    last = len(CASES[case_id].sweeps)                  # the extra sweep's index
    assert _open_after(run, last) == _open_after(run, last - 1), "the skip changed a card"
    assert _open_after(run, last), f"{case_id}: no card to keep — the comparison proves nothing"


def test_a_moved_input_decides_again(monkeypatch):
    from genios_engine.api import routes

    def bump(org_id):
        with routes._graph.engine.begin() as conn:
            conn.execute(text("update tenant_packs set authority_revision = authority_revision + 1, "
                              "updated_at = now() where org_id = :o"), {"o": org_id})

    _, before, after = _run("F13", monkeypatch, before_last=bump)
    assert after, "the pack's revision moved and the compiled lane did not decide again"


def test_a_gate_that_cannot_fingerprint_decides_everything(monkeypatch):
    from genios_engine.reason import fingerprint

    def broken(*a, **kw):
        raise RuntimeError("the fingerprint is unavailable")

    monkeypatch.setattr(fingerprint, "material_fingerprint", broken)
    _, before, after = _run("F13", monkeypatch)
    assert after == before and after, "a gate that could not judge skipped a decision"


def test_without_the_gate_the_unchanged_sweep_is_decided_again(monkeypatch):
    """⛔ THE NEGATIVE CONTROL: the first test's zero is the gate's, not the case's. With every
    verdict forced to "decide", the same unchanged sweep asks the decider again — what it did before
    this unit."""
    from genios_engine.reason import change_gate

    monkeypatch.setattr(change_gate, "should_skip",
                        lambda *a, **kw: change_gate.GateVerdict(False, change_gate.CHANGED))
    _, before, after = _run("F13", monkeypatch)
    assert after and after == before, after
