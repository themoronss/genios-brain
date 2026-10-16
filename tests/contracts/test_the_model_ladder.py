"""STEP-13b · the ladder's rule — when an answer is final, when it is repaired, when it climbs.

    .venv/bin/python -m pytest -q tests/contracts/test_the_model_ladder.py

Tree `yc2_w27_s13b` M38.C1.L-contract.V2.U01 (`contracts/model_ladder`, pure). "Climb", never "escalate" (the
executive's escalation ladder owns that word). A rung's answer is FINAL when its check shows it, suppresses it,
or holds it for the file's own state (an answered ask, your answer, a correction); it FAILS for the writer's
faults only. A failed answer is REPAIRED once on its own rung, handed the check's verdicts (crosscheck X32,
s13b-D4), and CLIMBS only when the repaired answer still fails. When every rung failed, the best fate stands.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from genios_engine.contracts import claim_check as C
from genios_engine.contracts import model_ladder as M

pytestmark = pytest.mark.unit

MIGRATION = Path(__file__).resolve().parents[2] / "migrations" / "0250_expert_review_attempts.sql"
WORDS = C.CardWords(headline="Send Neel the pre-read", situation=None, done_when=None, draft=None, to=None)
NONE = C.CardWords(None, None, None, None, None)


def _checked(fate=C.SHOWN, *verdicts, because=None, question=None):
    cited = ("evt_a",) if fate != C.REFUSED else ()
    held = fate in (C.HELD, C.SUPPRESSED, C.REFUSED)
    return C.CheckedReview(verdicts=tuple(verdicts) or (C.LineVerdict("fact:1", C.KEPT),), fate=fate,
                           words=WORDS if fate == C.SHOWN else NONE, cited=cited,
                           question=question or ("Did Neel ask?" if fate == C.HELD else None),
                           because=because or ("because" if held else None))


def _drop(line, reason, detail=""):
    return C.LineVerdict(line, C.DROPPED, reason, detail)


# ── the vocabulary is the table's ────────────────────────────────────────────────────────────

def test_the_closed_reasons_are_the_ones_the_attempts_table_admits():
    lists = [set(re.findall(r"'([a-z_]+)'", body)) for body in re.findall(r"in\s*\(([^)]*)\)", MIGRATION.read_text())]
    assert set(M.CLIMB_REASONS) in lists and len(set(M.CLIMB_REASONS)) == len(M.CLIMB_REASONS) == 13
    assert M.LADDER_VERSION == "ladder.v1"


# ── final: shown, suppressed, held for the file's own state ──────────────────────────────────

@pytest.mark.parametrize("checked", [
    _checked(C.SHOWN),
    _checked(C.SUPPRESSED, _drop("answers", C.ANSWERED, "loop:l1 by evt_2"), because="answered"),
    _checked(C.HELD, _drop("answers", C.ANSWERED, "loop:l1"), because=C.HELD_BECAUSE[C.ANSWERED]),
    _checked(C.HELD, _drop("rests_on", C.ON_YOUR_ANSWER, "ans:1"), because=C.HELD_BECAUSE[C.ON_YOUR_ANSWER]),
    _checked(C.SUPPRESSED, _drop("rests_on", C.DECLINED_BY_YOU, "ans:1"), because="declined"),
    _checked(C.HELD, _drop("correction", C.CORRECTION_UNHEEDED, "corr:1"), because=C.HELD_BECAUSE[C.CORRECTION_UNHEEDED]),
    _checked(C.HELD, _drop("called_wrong", C.CALLED_WRONG, "card:1"), because=C.HELD_BECAUSE[C.CALLED_WRONG]),
])
def test_an_answer_the_check_shows_suppresses_or_holds_for_the_files_own_state_is_final(checked):
    assert M.writer_fault("valid", checked) is None


def test_a_find_out_review_asking_its_own_question_is_shown_and_final():
    shown = C.CheckedReview(verdicts=(C.LineVerdict("fact:1", C.KEPT),), fate=C.SHOWN, words=WORDS,
                            cited=("evt_a",), question="Did Neel ask?")
    assert M.writer_fault("valid", shown) is None


def test_a_hold_with_no_writer_fault_in_it_is_final_not_blamed_on_the_writer():
    assert M.writer_fault("valid", _checked(C.HELD, _drop("question", C.UNKNOWN_EVIDENCE, "x"))) is None


# ── failed: the writer's faults only ─────────────────────────────────────────────────────────

@pytest.mark.parametrize("reason", [C.UNCITED, C.UNKNOWN_EVIDENCE, C.UNQUOTED, C.MISQUOTED, C.UNSUPPORTED,
                                    C.WRONG_NUMBER, C.ENGINE_IS_NO_FACT])
def test_a_move_held_because_a_fact_it_rests_on_dropped_is_the_writers_fault(reason):
    checked = _checked(C.HELD, _drop("fact:2", reason, "x"), because=C.HELD_BECAUSE[reason])
    assert M.writer_fault("valid", checked) == reason


def test_a_misquoted_quote_is_a_misquote():
    checked = _checked(C.HELD, _drop("quote:1", C.MISQUOTED, "send the deck"), because="m")
    assert M.writer_fault("valid", checked) == "misquoted"


@pytest.mark.parametrize("reason, fault", [(C.RECIPIENT_IS_US, "recipient_is_us"),
                                           (C.RECIPIENT_IS_CONNECTOR, "recipient_is_connector")])
def test_a_move_addressed_to_us_or_to_the_connector_is_the_writers_fault(reason, fault):
    checked = _checked(C.HELD, _drop("to", reason, "Neel"), because=C.HELD_BECAUSE[reason])
    assert M.writer_fault("valid", checked) == fault


def test_a_headline_that_fails_is_the_writers_fault():
    checked = _checked(C.HELD, _drop("move", C.UNSUPPORTED, "name:Boardy"), because=C.HELD_BECAUSE[C.HELD_MOVE])
    assert M.writer_fault("valid", checked) == "headline_failed"


def test_a_review_where_nothing_stands_is_refused_and_the_writers_fault():
    checked = C.CheckedReview(verdicts=(_drop("fact:1", C.UNCITED),), fate=C.REFUSED, words=NONE, cited=(),
                              because=C.NOTHING_STANDS)
    assert M.writer_fault("valid", checked) == "nothing_stands"


@pytest.mark.parametrize("status, fault", [("truncated", "truncated"), ("refused", "malformed"),
                                           ("failed", "malformed")])
def test_an_answer_that_never_became_a_review_is_a_fault_by_its_status(status, fault):
    assert M.writer_fault(status, None) == fault


def test_a_day_spent_is_no_fault_of_the_writer():
    assert M.writer_fault("over_budget", None) is None


def test_the_first_fault_in_the_check_order_names_a_hold_with_several():
    checked = _checked(C.HELD, _drop("fact:3", C.WRONG_NUMBER), _drop("fact:2", C.MISQUOTED),
                       _drop("to", C.RECIPIENT_IS_US), because="x")
    assert M.writer_fault("valid", checked) == "recipient_is_us", "the recipient outranks a fact"
    checked = _checked(C.HELD, _drop("fact:3", C.WRONG_NUMBER), _drop("fact:2", C.MISQUOTED), because="x")
    assert M.writer_fault("valid", checked) == "misquoted", "then the lowest-numbered fact"


def test_a_valid_status_with_no_check_is_a_programming_error():
    with pytest.raises(ValueError):
        M.writer_fault("valid", None)
    with pytest.raises(ValueError):
        M.writer_fault("maybe", None)


# ── the step: repair once, climb when the repaired answer still fails ────────────────────────

def _c(status="valid", checked=None, repair=False):
    return M.Consult(status=status, checked=checked, repair=repair)


HELD_FAULT = _checked(C.HELD, _drop("fact:1", C.MISQUOTED), because="m")


def test_a_final_answer_ends_the_climb():
    assert M.next_step((_c(checked=_checked(C.SHOWN)),), rung=1, rungs=2) == M.Step(M.FINAL)


def test_a_failed_first_answer_is_repaired_once_on_its_own_rung_with_the_checks_verdicts():
    step = M.next_step((_c(checked=HELD_FAULT),), rung=1, rungs=2)
    assert step == M.Step(M.REPAIR, fault="misquoted")


def test_a_repaired_answer_that_still_fails_climbs_with_the_reason():
    step = M.next_step((_c(checked=HELD_FAULT), _c(checked=HELD_FAULT, repair=True)), rung=1, rungs=2)
    assert step == M.Step(M.CLIMB, fault="misquoted")


def test_a_repaired_answer_that_is_final_ends_the_climb():
    step = M.next_step((_c(checked=HELD_FAULT), _c(checked=_checked(C.SHOWN), repair=True)), rung=1, rungs=2)
    assert step.kind == M.FINAL


def test_the_top_rung_failing_twice_exhausts_the_ladder_it_does_not_climb_off_it():
    step = M.next_step((_c(checked=HELD_FAULT), _c(checked=HELD_FAULT, repair=True)), rung=2, rungs=2)
    assert step == M.Step(M.EXHAUSTED, fault="misquoted")


def test_a_cut_answer_is_never_repaired_at_the_same_ceiling_it_climbs():
    assert M.next_step((_c("truncated"),), rung=1, rungs=2) == M.Step(M.CLIMB, fault="truncated")
    assert M.next_step((_c("truncated"),), rung=2, rungs=2) == M.Step(M.EXHAUSTED, fault="truncated")


def test_a_malformed_answer_after_its_syntax_repair_is_repaired_once_more_with_the_verdicts_then_climbs():
    assert M.next_step((_c("failed"),), rung=1, rungs=2) == M.Step(M.REPAIR, fault="malformed")
    assert M.next_step((_c("failed"), _c("failed", repair=True)), rung=1, rungs=2).kind == M.CLIMB


def test_a_day_spent_mid_climb_stops_it_and_carries_the_file():
    assert M.next_step((_c("over_budget"),), rung=1, rungs=2) == M.Step(M.CARRIED)
    assert M.next_step((_c(checked=HELD_FAULT), _c("over_budget", repair=True)), rung=1, rungs=2) == M.Step(M.CARRIED)


def test_at_most_two_consults_a_rung():
    with pytest.raises(ValueError):
        M.next_step((_c(checked=HELD_FAULT),) * 3, rung=1, rungs=2)
    with pytest.raises(ValueError):
        M.next_step((), rung=1, rungs=2)


# ── the complaint: the check's verdicts, handed back ─────────────────────────────────────────

def test_the_complaint_hands_back_the_lines_dropped_and_why():
    checked = _checked(C.HELD, _drop("fact:2", C.MISQUOTED, "quote: send the deck"), _drop("fact:3", C.UNCITED),
                       C.LineVerdict("fact:1", C.KEPT), because="m")
    text = M.complaint("valid", checked)
    assert "fact:2" in text and "misquoted" in text and "send the deck" in text
    assert "fact:3" in text and "uncited" in text
    assert "fact:1" not in text, "a line that stood is not a complaint"


def test_a_complaint_without_a_check_says_what_the_answer_was():
    assert "not valid JSON" in M.complaint("failed", None)
    assert "cut off" in M.complaint("truncated", None) and "did not hold" in M.complaint("refused", None)


# ── the best fate stands ─────────────────────────────────────────────────────────────────────

def test_when_every_rung_failed_the_best_fate_stands_and_on_a_tie_the_higher_rung():
    shown, suppressed = _checked(C.SHOWN), _checked(C.SUPPRESSED, because="a")
    refused = C.CheckedReview(verdicts=(_drop("fact:1", C.UNCITED),), fate=C.REFUSED, words=NONE, cited=(),
                              because=C.NOTHING_STANDS)
    held = HELD_FAULT
    assert M.best_of([(1, held), (2, refused)]) == 0, "held > refused"
    assert M.best_of([(1, refused), (2, held)]) == 1
    assert M.best_of([(1, held), (2, suppressed)]) == 1, "suppressed > held"
    assert M.best_of([(1, suppressed), (2, shown)]) == 1, "shown > suppressed"
    assert M.best_of([(1, held), (2, held)]) == 1, "a tie: the higher rung"
    assert M.best_of([(2, held), (1, held)]) == 0, "a tie is the higher RUNG, not the later one"
    assert M.best_of([(1, None), (2, held)]) == 1, "an answer that never became a review stands for nothing"
    assert M.best_of([(1, None), (2, None)]) is None
    assert M.best_of([]) is None


def test_the_fate_order_is_shown_suppressed_held_refused():
    assert M.FATE_ORDER == (C.SHOWN, C.SUPPRESSED, C.HELD, C.REFUSED)


def test_a_suppressed_answer_is_final_whatever_else_the_check_dropped():
    assert M.writer_fault("valid", _checked(C.SUPPRESSED, _drop("fact:2", C.UNCITED), because="a")) is None


def test_a_hold_for_the_files_own_state_is_final_even_with_a_writers_fault_beside_it():
    checked = _checked(C.HELD, _drop("rests_on", C.ON_YOUR_ANSWER, "ans:1"), _drop("fact:2", C.UNCITED), because="a")
    assert M.writer_fault("valid", checked) is None


def test_on_a_tie_on_the_same_rung_the_repaired_answer_stands():
    assert M.best_of([(1, HELD_FAULT), (1, HELD_FAULT)]) == 1


def test_a_step_and_a_fault_are_closed():
    with pytest.raises(ValueError):
        M.Step("leap")
    with pytest.raises(ValueError):
        M.Step(M.CLIMB, "rude")
    assert M.Step(M.FINAL).fault is None
