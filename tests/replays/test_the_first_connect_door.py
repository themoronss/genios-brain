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
first one opened — four and one prompts, each answered by the case's own rules (`NOT_RESOLVED`).

THE DOOR'S OWN ANSWERS HAVE THEIR OWN CASSETTES (STEP-12, M32.C5.L-integration.V2.U04). They were
merged into the case's cassette, and the next re-record of the sweep door (`golden_eval --record`,
which writes what the sweep door asks and nothing else) dropped them. With the expert switched on,
the door asks more the sweep door never asks: the expert reviews a file the door's second drain call
has already moved, so its dossier differs — eight cases on 11 Oct, each answered by the case's own
authored review — and a kind the expert proposed changes the brief a later resolution prompt carries
(F57). So the door's answers sit in `cassettes/door/<case>.json`, beside the case's own and never
re-answering one of them, as the re-sync scenarios' do. Re-record them, when a prompt moves, with

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… python -m tests.replays.test_the_first_connect_door --record [F01 …]
"""
from __future__ import annotations

import os
from typing import Any

import pytest

from tests.replays import cassettes
from tests.replays.founder_case import CASSETTE_DIR, load_cases

CASES = {c.case_id: c for c in load_cases()}
#: The answers the first-connect door needs beyond its case's own cassette.
DOOR_CASSETTES = CASSETTE_DIR / "door"


def _cassette(case) -> dict:
    """The case's own cassette, and what its door adds — never a different answer."""
    own = cassettes.load(case)
    if not cassettes.path_for(case, DOOR_CASSETTES).is_file():
        return own
    extra = cassettes.load(case, DOOR_CASSETTES)
    assert not own.keys() & extra.keys(), "the door's cassette re-answers a recorded prompt"
    return {**own, **extra}


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

    monkeypatch.setattr(routes, "_run_l2_chain", _first_connect)
    llm = RecordedLLM(_cassette(case))
    run = run_case(case, llm)
    assert not llm.misses, llm.misses[:3]
    assert all(run.chain_ok), f"{case_id}: the first-connect door failed a sweep: {run.chain_ok}"
    assert _seen(run, judge(case, run)) == expected


def _first_connect(org_id, *, eval_time=None):
    """The founder's Sync, at the case's own instant — the door every case is driven through here."""
    from genios_engine.api import routes
    return routes._process_and_reason_unlocked(org_id, lambda *a, **k: None, eval_time=eval_time)


class _ServedThenRead:
    """The case's own cassette first; a prompt it does not hold is answered by the ideal reader, and
    that answer — only that — is written down."""

    def __init__(self, case) -> None:
        from tests.replays.harness import CassetteRecorder, RecordedLLM
        from tests.replays.ideal_reader import IdealReader
        self._recorded = RecordedLLM(cassettes.load(case))
        self.recorder = CassetteRecorder(IdealReader(case))
        self.model = self._recorded.model

    def content_hash(self, material: str) -> str:
        return self._recorded.content_hash(material)

    def call(self, prompt: str, **kw: Any):
        from tests.replays.harness import CassetteMiss
        try:
            return self._recorded.call(prompt, **kw)
        except CassetteMiss:
            return self.recorder.call(prompt, **kw)


def record(ids: list[str] | None = None) -> None:
    """Run each case through the door, its own cassette serving, and keep what the door alone asked."""
    from tests.replays.engine_runner import pin_scratch_database, run_case
    pin_scratch_database()                        # before `api.routes` binds its stores
    from genios_engine.api import routes
    original = routes._run_l2_chain
    routes._run_l2_chain = _first_connect
    try:
        for case_id in ids or sorted(CASES):
            case = CASES[case_id]
            model = _ServedThenRead(case)
            run_case(case, model)
            answers = model.recorder.cassette
            path = cassettes.path_for(case, DOOR_CASSETTES)
            if answers:
                cassettes.save(case, answers, source=cassettes.IDEAL_READER, folder=DOOR_CASSETTES)
            elif path.is_file():
                path.unlink()                       # the door now asks nothing the sweep door does not
            print(f"{case_id}: {len(answers)} door answer(s) — "
                  + ", ".join(sorted({a['site'] for a in answers.values()})))
    finally:
        routes._run_l2_chain = original


if __name__ == "__main__":       # pragma: no cover - the recording entry point
    import sys
    if sys.argv[1:2] != ["--record"]:
        raise SystemExit("usage: python -m tests.replays.test_the_first_connect_door --record [F01 …]")
    record(sys.argv[2:] or None)
