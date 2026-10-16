"""STEP-14 · M42's acceptance — on the golden set, one file, one living card.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… GENIOS_GOLDEN_REQUIRED=1 pytest tests/replays/test_one_file_one_living_card.py -q

Tree `yc2_w27_s14` M42.C4.L-integration.V4.U05 (STEP-14 §3.1, §3.2; `03` F176, F52, F53). Every founder case replayed
from its cassette through the real chain (`cassettes.replayed`), and on every one:

  * no file has two open cards after any sweep — a file's next decision or question VERSIONS its card (`migrations/
    0220`, `platform/card_lifecycle.version_card`);
  * no file's card is expired REPLACED — the shape F176 measured ten times over nine cases;
  * every version names what changed and keeps the words before (`contracts/card_version`);
  * a renewal or a rewording pushes nothing — only a card's creation or a material version is followed by a push
    (s14-D1);
  * a held file's question is a version of its card — F07's move, then the question after its call, one card; the
    question cards (F01, F52, F63) are their files' cards. Your answer's version is the unit tests' (no golden case
    presses Answer: `tests/deliver/test_answering_a_question.py`).

THE NEGATIVE CONTROLS: a quiet version pushed is caught (`test_a_quiet_version_pushed_is_caught`); and with
versioning switched off — the builders' drafts naming no file, so every decision is a new
card, as before STEP-14 — the ideal reader re-runs F176's eight cases (no spend) and each shows its second card
about its subject again.
"""
from __future__ import annotations

import os
from collections import Counter

import pytest

from tests.replays import cassettes
from tests.replays.founder_case import load_cases
from tests.replays.marking import FAIL, PASS, judge

CASES = load_cases()
BY_ID = {c.case_id: c for c in CASES}
#: F176's eight cases: the advice changed as the file moved (F02, F05, F06, F24), the same advice in other words
#: (F25), the same advice after its window (F12, F50) — and F19, three people's asks on one file.
F176 = ("F02", "F05", "F06", "F12", "F19", "F24", "F25", "F50")
#: The cases whose file asks you a question on the golden set — the question is the file's card.
QUESTION_CASES = ("F01", "F52", "F63")


def _scratch_db() -> None:
    if os.environ.get("GENIOS_TEST_DATABASE_URL"):
        return
    if os.environ.get("GENIOS_GOLDEN_REQUIRED") == "1":
        pytest.fail("GENIOS_GOLDEN_REQUIRED=1 and no GENIOS_TEST_DATABASE_URL")
    pytest.skip("needs GENIOS_TEST_DATABASE_URL pointing at a scratch database")


def _param(case):
    return pytest.param(case, id=case.case_id, marks=[pytest.mark.pg, pytest.mark.golden])


@pytest.mark.parametrize("case", [_param(c) for c in CASES])
def test_one_file_one_living_card(case):
    _scratch_db()
    run = cassettes.replayed(case)
    assert not run.misses, f"{case.case_id}: the replay missed its cassette"
    for sweep in range(len(run.chain_ok)):
        open_files = Counter(c.file_id for c in run.cards if c.file_id and sweep in c.sweeps)
        assert all(n == 1 for n in open_files.values()), f"{case.case_id} sweep {sweep}: {dict(open_files)}"
    for card in run.cards:
        if card.file_id:
            replaced = [e for e in card.events if e[0] == "card.expired" and e[1] == "replaced"]
            assert not replaced, f"{case.case_id}: {card.card_id}, a file's card, expired REPLACED"
        for kind, _cause, change, material, kept in card.events:
            if kind == "card.versioned":
                assert change and kept and material is not None, \
                    f"{case.case_id}: {card.card_id} — a version names what changed and keeps the words before"
        assert not _pushed_after_a_quiet_version(card), f"{case.case_id}: {card.card_id} pushed after a quiet version"


def _pushed_after_a_quiet_version(card) -> bool:
    """A push whose card's last version before it was quiet (a renewal, a rewording): what s14-D1 forbids."""
    last_material = None
    for kind, cause, _change, material, _kept in card.events:
        if kind == "card.created":
            last_material = True
        elif kind == "card.versioned":
            last_material = bool(material)
        elif kind == "card.surfaced" and cause == "push" and not last_material:
            return True
    return False


@pytest.mark.pg
@pytest.mark.golden
def test_a_quiet_version_pushed_is_caught():
    """⛔ THE NEGATIVE CONTROL (STEP-14 fix, the crosscheck's finding 8, M42.C4.L-integration.V4.U06): the store reports
    every version MATERIAL to the pipeline while the event it writes says what the rule said — so quiet renewals are
    pushed. Replayed from their cassettes (no spend), F12 and F50 renew on the golden set: the check above must see a
    push after a quiet version on each. Before the fix it saw none — history ordered by `occurred_at` put every
    version before its card's creation."""
    _scratch_db()
    from genios_engine.deliver.store import CardStore
    from tests.replays.engine_runner import run_case
    from tests.replays.harness import RecordedLLM
    real = CardStore.version_card

    def everything_material(self, *a, **k):
        done = real(self, *a, **k)
        return None if done is None else (done[0], done[1], True, done[3])
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(CardStore, "version_card", everything_material)
        for cid in ("F12", "F50"):
            run = run_case(BY_ID[cid], RecordedLLM(cassettes.load(BY_ID[cid])))
            assert not run.misses, cid
            assert any(_pushed_after_a_quiet_version(c) for c in run.cards), \
                f"{cid}: the mutant pushed a quiet renewal and the acceptance did not see it"


@pytest.mark.pg
@pytest.mark.golden
def test_the_board_holds_a_quiet_version_somewhere():
    """Not vacuous: the golden set carries versions, a renewal or a rewording among them, and a push."""
    _scratch_db()
    changes = Counter(e[2] for c in CASES for card in cassettes.replayed(c).cards for e in card.events
                      if e[0] == "card.versioned")
    assert sum(changes.values()) >= 8, changes
    assert changes["renewed"] + changes["reworded"] >= 1, changes


@pytest.mark.pg
@pytest.mark.golden
def test_a_held_files_question_is_a_version_of_its_card():
    _scratch_db()
    f07 = [c for c in cassettes.replayed(BY_ID["F07"]).cards if c.file_id]
    assert len(f07) == 1, "the move, then the question after the call: one card"
    assert "asked" in [e[2] for e in f07[0].events if e[0] == "card.versioned"], f07[0].events
    for cid in QUESTION_CASES:
        run = cassettes.replayed(BY_ID[cid])
        assert run.cards and all(c.file_id for c in run.cards if c.level == "review"), \
            f"{cid}: the question card is its file's card"


@pytest.mark.pg
@pytest.mark.golden
@pytest.mark.parametrize("case_id", F176)
def test_with_versioning_off_f176_shows_its_second_card_again(case_id, monkeypatch):
    """⛔ THE NEGATIVE CONTROL: the builders' drafts name no file — every decision is a new card, as before STEP-14 —
    and the ideal reader re-runs the case (no spend, no cassette written)."""
    _scratch_db()
    from genios_engine.deliver import card_builder, pipeline
    from tests.replays.engine_runner import run_case
    from tests.replays.harness import CassetteRecorder
    from tests.replays.ideal_reader import IdealReader
    case = BY_ID[case_id]
    assert judge(case, cassettes.replayed(case)).verdict == PASS, "with the living card, it passes"
    build = card_builder.build_draft

    def no_file(*a, **k):
        draft = build(*a, **k)
        return {**draft, "file_id": None}
    monkeypatch.setattr(pipeline, "build_draft", no_file)
    real_question = pipeline.question_card
    monkeypatch.setattr(pipeline, "question_card",
                        lambda *a, **k: (lambda card, copy: ({**card, "file_id": None}, copy))(*real_question(*a, **k)))
    off = run_case(case, CassetteRecorder(IdealReader(case)))
    marked = judge(case, off)
    assert marked.verdict == FAIL and "expected exactly 1" in marked.reason, (case_id, marked.reason)
