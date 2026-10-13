"""STEP-13 · on the golden set a held file asks once — and F01 and F52 are its question cards.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… GENIOS_GOLDEN_REQUIRED=1 .venv/bin/python -m pytest -q tests/replays/test_a_held_file_asks_once.py

Tree `yc2_w27_s13` M36.C2.L-integration.V6.U08 (`06` D60, `03` F184). Every founder case runs through the REAL
chain with the expert on and the ideal reader answering from the case's cassette (no spend), and:

  * F01 and F52 — must-detect cases lost because their file was held in Investigation and no card asked its
    question — now pass, and a card the case expects is the file's question card;
  * a file asks ONE question at a time: after every sweep, the open question cards name distinct files,
    each card's words are the question its file asked (`founder_questions`), in the Investigation lane;
  * every case whose authored review must find out first (F01, F07, F21, F22, F52, F54) asks: a question
    card is built for it — and stays within the cards its case allows (its own verdict is
    `test_founder_cases`');
  * every must-abstain case holds;
  * no question card asks an instruction behind "Can you tell us:" (M36.C2.L-logic.V2.U17, the second crosscheck
    G8: F22 and F52 did) nor names you — the company, the founder by full or first name, an address or domain of
    ours (M36.C2.L-logic.V2.U19, F3: F54 asked "…whether Arjun went to the event…").
"""
from __future__ import annotations

import os

import pytest

from tests.replays.founder_case import load_cases
from tests.replays.marking import PASS, cards_about, judge

CASES = load_cases()
#: The cases whose question card is what the founder must see (STEP-13 §8.1).
ASKED_FOR = ("F01", "F52")
#: Every case with an authored review that must find out first (`model.expert[*].answer.mode`).
FIND_OUT = ("F01", "F07", "F21", "F22", "F52", "F54")


def _scratch_db() -> None:
    if os.environ.get("GENIOS_TEST_DATABASE_URL"):
        return
    if os.environ.get("GENIOS_GOLDEN_REQUIRED") == "1":
        pytest.fail("GENIOS_GOLDEN_REQUIRED=1 and no GENIOS_TEST_DATABASE_URL")
    pytest.skip("needs GENIOS_TEST_DATABASE_URL pointing at a scratch database")


def test_the_find_out_cases_are_the_authored_ones():
    """The list above is read off the authored answers, never typed from memory."""
    authored = sorted(c.case_id for c in CASES
                      if any(((e.get("answer") or {}).get("mode") == "find_out")
                             for e in (((c.model or {}).get("expert")) or ())))
    assert authored == sorted(FIND_OUT)


@pytest.mark.pg
@pytest.mark.golden
@pytest.mark.parametrize("case", CASES, ids=lambda c: c.case_id)
def test_a_held_file_asks_once(case):
    _scratch_db()
    from sqlalchemy import text

    from genios_engine.api import routes
    from genios_engine.deliver.store import QUESTION_CARD_BUILDER
    from tests.replays import cassettes
    from tests.replays.engine_runner import remove_tenant, run_case
    from tests.replays.harness import RecordedLLM

    run = run_case(case, RecordedLLM(cassettes.load(case)), keep=True)
    engine = routes._graph.engine
    try:
        with engine.connect() as c:
            asked = {r.card_id: r for r in c.execute(text(
                "select k.card_id, k.headline, k.output_lane, s.subject_node_id from cards k "
                "  join signals s on s.org_id = k.org_id and s.signal_id = k.signal_id "
                " where k.org_id = :o and k.builder_version = :b"),
                {"o": run.org_id, "b": QUESTION_CARD_BUILDER})}
            questions = {(r.file_id, r.question) for r in c.execute(text(
                "select file_id, question from founder_questions where org_id = :o"), {"o": run.org_id})}
            from genios_engine.platform.self_identity import identity_for, speaks_of_us
            us = identity_for(c, run.org_id)
            org = c.execute(text("select company, name, first_name, last_name from orgs where id = :o"),
                            {"o": run.org_id}).first()
            ours = tuple(n for n in (org.company, org.name,
                                     " ".join(p for p in (org.first_name, org.last_name) if p)) if n)
        for card in asked.values():
            assert card.output_lane == "investigation", card
            assert (card.subject_node_id, card.headline) in questions, f"{case.case_id}: {card} asks no question"
            assert "Can you tell us:" not in card.headline, f"{case.case_id}: an instruction asked: {card.headline}"
            assert speaks_of_us(card.headline, us, ours) is None, f"{case.case_id}: it names you: {card.headline}"
        for sweep in range(len(case.sweeps)):
            open_now = [asked[v.card_id].subject_node_id for v in run.cards
                        if v.card_id in asked and sweep in v.sweeps]
            assert len(open_now) == len(set(open_now)), \
                f"{case.case_id}: sweep {sweep} holds two questions for one file: {open_now}"
        if case.case_id in FIND_OUT:
            assert asked, f"{case.case_id}: a review that must find out first asked nothing"
        mark = judge(case, run)
        if case.case_id in ASKED_FOR:
            assert mark.verdict == PASS, f"{case.case_id}: {mark}"
            expected = [e for e in case.cards if e.min >= 1]
            assert any(v.card_id in asked for e in expected for v in cards_about(run, e.about)), \
                f"{case.case_id}: what the founder must see is not the file's question card"
        if case.kind == "must_abstain":
            assert mark.verdict == PASS, f"{case.case_id}: the must-abstain case broke: {mark}"
    finally:
        remove_tenant(engine, run.org_id)
