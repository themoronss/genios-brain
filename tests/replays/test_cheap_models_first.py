"""STEP-13b · M38's acceptance on the golden set — the cheapest model asks first, a stronger one only when the check says the writer erred.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… GENIOS_GOLDEN_REQUIRED=1 pytest tests/replays/test_cheap_models_first.py -q

Tree `yc2_w27_s13b` M38.C4.L-integration.V14.U01. No spend: every rung is a scripted reader (`engine_runner.production_switches(rungs=)`).
Rung one is the recorded model with ONE mutation of one served answer (`test_every_claim_is_checked.MUTATIONS`) - a model that
keeps making the one error, the repair and all; rung two is the recorded model as authored, the stronger model that gets it
right. On the REAL chain, on the cases the mutations name:

  * an answer failing by a writer's fault on rung one (F11, a decisive quote removed) is asked once more on its rung with the
    check's verdicts, climbs, and rung two's review decides its file - the stored row says rung two, and the card is rung two's;
  * a review held on an answered ask (F45), a find-out review asking its own question (F52) and a shown review (F11 as
    authored) do not climb: rung two is never asked;
  * a day spent mid-climb carries the file, and the stronger model is not asked;
  * every attempt is kept (`expert_review_attempts`) and counted, with the closed reason it climbed;
  * NEGATIVE CONTROL: with one rung, the failing answer's file is HELD, and the card the stronger model would have made does not appear.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest

from tests.replays.harness import RecordedLLM
from tests.replays.test_every_claim_is_checked import (CASES, MUTATIONS, Mutation, _Mutating, _scratch_db,
                                                       _words, CARD_TEXTS)

pytestmark = [pytest.mark.pg, pytest.mark.golden]

BY_ID = {m.id: m for m in MUTATIONS}
QUOTE_REMOVED = BY_ID["a_decisive_quote_removed"]                  # F11 <northfieldvc.test>: held, the writer's fault
ANSWERED_ASK = BY_ID["answers_an_ask_our_reply_answered"]           # F45 <bluepeak.test>: held for the file's own state
HEADLINE = "Reply to Tom that you are raising your seed round now"   # what F11's recorded (good) answer makes the card say


@dataclass
class Run:
    asked: dict[str, int]                         # expert prompts each rung was handed
    reviews: list[dict[str, Any]]                 # the file's stored rows
    attempts: list[dict[str, Any]]                # every consult kept, in the order asked
    cards: list[str]                              # every text of every card


def _run(case_id: str, mutation: Mutation | None, *, rungs: tuple[str, ...] = ("T1", "T2"),
         daily_usd: str | None = None) -> Run:
    from sqlalchemy import text

    from genios_engine.api import routes
    from genios_engine.reason.bundle import budget as B
    from genios_engine.reason.bundle import sites as S
    from tests.replays import cassettes
    from tests.replays.engine_runner import remove_tenant, run_case

    case = CASES[case_id]
    cassette = cassettes.load(case)
    cheap = _Mutating(cassette, mutation)             # rung one: the one error, again and again
    strong = _Mutating(cassette, None)                # rung two: the recorded answer as authored
    main = _Mutating(cassette, mutation) if mutation is not None else _Mutating(cassette, None)
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(S, "EXPERT_LADDER", rungs)
        if daily_usd is not None:
            mp.setitem(B.OWN_BUDGETS, S.SITE_EXPERT, (daily_usd, B.OWN_BUDGETS[S.SITE_EXPERT][1]))
        run = run_case(case, main, keep=True, rungs={"T1": cheap, "T2": strong})
    engine = routes._graph.engine
    try:
        with engine.connect() as c:
            reviews = [dict(r._mapping) for r in c.execute(text(
                "select n.canonical_key as key, r.status, r.rung, r.review, r.checked from expert_reviews r "
                "  left join graph_nodes n on n.org_id = r.org_id and n.node_id = r.file_id and n.valid_to is null "
                " where r.org_id = :o order by r.reviewed_at, r.fingerprint"), {"o": run.org_id})]
            attempts = [dict(r._mapping) for r in c.execute(text(
                "select a.rung, a.consult, a.status, a.fate, a.climbed_because, n.canonical_key as key "
                "  from expert_review_attempts a left join graph_nodes n on n.org_id = a.org_id "
                "       and n.node_id = a.file_id and n.valid_to is null "
                " where a.org_id = :o order by a.attempted_at, a.attempt_no"), {"o": run.org_id})]
            cards = ["\n".join(_words(getattr(r, col)) for col in CARD_TEXTS) for r in c.execute(text(
                f"select {', '.join(CARD_TEXTS)} from cards where org_id = :o"), {"o": run.org_id})]
    finally:
        remove_tenant(engine, run.org_id)
    return Run(asked={"T1": cheap.expert_calls, "T2": strong.expert_calls}, reviews=reviews, attempts=attempts,
               cards=cards)


def _file(run: Run, key: str):
    return ([a for a in run.attempts if a["key"] == key], [r for r in run.reviews if r["key"] == key])


# ── a writer's fault climbs, and the stronger rung decides the file ────────────────────────────────────────────

def test_a_failed_answer_is_repaired_once_climbs_and_rung_twos_review_decides_its_file():
    _scratch_db()
    run = _run("F11", QUOTE_REMOVED)
    attempts, rows = _file(run, QUOTE_REMOVED.key)
    assert [(a["rung"], a["consult"], a["status"], a["fate"], a["climbed_because"]) for a in attempts] == [
        (1, "first", "valid", "held", None), (1, "repair", "valid", "held", "unquoted"),
        (2, "first", "valid", "shown", None)], attempts
    [row] = rows
    assert (row["status"], row["rung"], row["checked"]["fate"]) == ("valid", 2, "shown"), "rung two's review decides"
    assert run.asked["T2"] == 1
    assert any(HEADLINE in text for text in run.cards), "the card is the stronger model's"


def test_negative_control_with_one_rung_the_failing_answers_file_is_held():
    _scratch_db()
    run = _run("F11", QUOTE_REMOVED, rungs=("T1",))
    attempts, rows = _file(run, QUOTE_REMOVED.key)
    assert [(a["rung"], a["consult"], a["fate"]) for a in attempts] == [(1, "first", "held"), (1, "repair", "held")]
    [row] = rows
    assert (row["rung"], row["checked"]["fate"]) == (1, "held") and run.asked["T2"] == 0
    assert not any(HEADLINE in text for text in run.cards), "the card the stronger model would have made does not appear"


# ── what is no writer's fault does not climb ───────────────────────────────────────────────────────────────────

def test_a_review_held_on_an_answered_ask_does_not_climb():
    _scratch_db()
    run = _run("F45", ANSWERED_ASK)
    attempts, rows = _file(run, ANSWERED_ASK.key)
    mutated = [a for a in attempts if a["fate"] == "suppressed"]
    assert mutated and all(a["consult"] == "first" and a["climbed_because"] is None for a in mutated), attempts
    assert {a["rung"] for a in attempts} == {1} and run.asked["T2"] == 0, "the stronger model is never asked"


def test_a_shown_review_does_not_climb_and_every_file_costs_one_consult():
    _scratch_db()
    run = _run("F11", None)
    assert run.asked["T2"] == 0 and len(run.attempts) == len(run.reviews) >= 1
    assert {(a["rung"], a["consult"], a["fate"], a["climbed_because"]) for a in run.attempts} == {(1, "first", "shown", None)}


def test_a_find_out_review_asking_its_own_question_does_not_climb():
    _scratch_db()
    run = _run("F52", None)
    modes = {r["review"]["mode"] for r in run.reviews}
    assert "find_out" in modes, "F52 is the case where the expert asks"
    assert run.asked["T2"] == 0 and {a["consult"] for a in run.attempts} == {"first"}
    assert {a["fate"] for a in run.attempts} <= {"shown", "suppressed"}


# ── a day spent mid-climb ──────────────────────────────────────────────────────────────────────────────────────

def test_a_day_spent_mid_climb_carries_the_file_and_the_stronger_model_is_not_asked():
    _scratch_db()
    run = _run("F11", QUOTE_REMOVED, daily_usd="0.045")
    attempts, rows = _file(run, QUOTE_REMOVED.key)
    assert attempts and attempts[-1]["status"] == "over_budget", attempts
    assert rows and {r["status"] for r in rows} == {"over_budget"} and run.asked["T2"] == 0, rows
    assert not any(a["rung"] == 2 for a in attempts)
    assert {a["status"] for a in attempts} <= {"valid", "over_budget"}


# ── every attempt kept and counted ─────────────────────────────────────────────────────────────────────────────

def test_every_attempt_is_kept_with_the_closed_reason_it_climbed():
    _scratch_db()
    from genios_engine.contracts.model_ladder import CLIMB_REASONS
    run = _run("F11", QUOTE_REMOVED)
    attempts, _ = _file(run, QUOTE_REMOVED.key)
    assert len(attempts) == 3
    assert [a["climbed_because"] for a in attempts if a["climbed_because"]] == ["unquoted"]
    assert all(a["climbed_because"] in CLIMB_REASONS for a in attempts if a["climbed_because"])
