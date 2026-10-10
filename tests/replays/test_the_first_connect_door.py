"""STEP-01 follow-up a · the golden set through the first-connect door, the path a founder's Sync takes.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… GENIOS_GOLDEN_REQUIRED=1 pytest tests/replays/test_the_first_connect_door.py -q

`yc2_w27_align` M34.C2.L-integration.V1.U11. The golden set drove the 6-hourly sweep's door only
(`api/routes._run_l2_chain`). A founder's own Sync — the first connect, and every Sync after it —
takes another chain, `_process_and_reason_unlocked`: it drains in chunks of 500 and calls the drain
once more after a short chunk, so the drain's org-wide passes see its own writes within the same
sync; it runs no post-passes and counts no funnel. No case ran it, so nothing said whether a founder
who presses Sync is told what the sweep would tell them.

Each case is replayed here through that door — the runner's sweep door swapped for it, every sweep
at the case's own instant (the door now takes `eval_time` as the sweep door does) — and judged by
the same marker against the same case through the sweep door. Measured 10 Oct: all 58 cases reach
the same verdict and the same cards through both doors. Two (F45, F53) ask the resolution site
questions the sweep door leaves to the next sweep — the door's second drain call reads loops its
first one opened — four and one prompts, each answered by the case's own rules (`NOT_RESOLVED`) and
kept in its cassette beside the sweep door's answers.
"""
from __future__ import annotations

import os

import pytest

from tests.replays import cassettes
from tests.replays.founder_case import load_cases

CASES = {c.case_id: c for c in load_cases()}


def _scratch_db() -> None:
    if os.environ.get("GENIOS_TEST_DATABASE_URL"):
        return
    if os.environ.get("GENIOS_GOLDEN_REQUIRED") == "1":
        pytest.fail("GENIOS_GOLDEN_REQUIRED=1 and no GENIOS_TEST_DATABASE_URL")
    pytest.skip("needs GENIOS_TEST_DATABASE_URL pointing at a scratch database")


def _seen(run, mark) -> dict:
    return {"verdict": mark.verdict, "lost_at": mark.lost_at,
            "cards": sorted((card.subject or "", card.state) for card in run.cards)}


@pytest.mark.pg
@pytest.mark.golden
@pytest.mark.parametrize("case_id", sorted(CASES))
def test_a_case_through_the_first_connect_door_is_told_what_the_sweep_tells_it(case_id, monkeypatch):
    _scratch_db()
    from genios_engine.api import routes
    from tests.replays.engine_runner import run_case
    from tests.replays.harness import RecordedLLM
    from tests.replays.marking import judge

    case = CASES[case_id]
    swept = cassettes.replayed(case)                     # the sweep door, as the golden set runs it
    expected = _seen(swept, judge(case, swept))

    def first_connect(org_id, *, eval_time=None):
        return routes._process_and_reason_unlocked(org_id, lambda *a, **k: None,
                                                   eval_time=eval_time)

    monkeypatch.setattr(routes, "_run_l2_chain", first_connect)
    llm = RecordedLLM(cassettes.load(case))
    run = run_case(case, llm)
    assert not llm.misses, llm.misses[:3]
    assert all(run.chain_ok), f"{case_id}: the first-connect door failed a sweep: {run.chain_ok}"
    assert _seen(run, judge(case, run)) == expected
