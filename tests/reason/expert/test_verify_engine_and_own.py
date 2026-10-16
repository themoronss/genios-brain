"""STEP-13b · the check reads three sources: the file's data, the engine's lines and the expert's own.

    .venv/bin/python -m pytest -q tests/reason/expert/test_verify_engine_and_own.py

Tree `yc2_w27_s13b` M37.C4.L-logic.V7.U01 (`reason/expert/verify`). An engine id is held as an evidence id is — printed.
A fact citing only engine or own lines drops `engine_is_no_fact`; beside data it stands on the data alone, the engine
line grounding no name or number of it. An own line with a digit drops `own_states_a_number`, one naming a person,
company or address of the file `own_names_the_file`. An own line grounds an inference or pattern only beside a standing
data line. An inference or pattern citing an engine line holds its names and numbers by the card validator's rule.
`rests_on: inference:N` rests on that inference's facts; `guided_by` is held like a ground. Every line is labelled by
code; the engine lines the standing lines cite are kept on the check with their words.
"""
from __future__ import annotations

import dataclasses

import pytest

from genios_engine.contracts import claim_check as C
from genios_engine.contracts import engine_read as E
from genios_engine.reason.expert import dossier as D
from genios_engine.reason.expert.verify import check_review
from tests.reason.expert import check_world as W

pytestmark = pytest.mark.unit

RULE = "rule:investor_follow_up"
PB = "pb:founder_office.pb.investor.run_the_round"
LINES = (
    E.EngineLine(ref=RULE, family=E.RULE, words="Follow up once, a week after a deck. Typical gap is 14 days.",
                 source="fundraising.rules", source_version="v", reviewed=True),
    E.EngineLine(ref=PB, family=E.PLAYBOOK, words="A partner meeting follows a deck.", source="Run the round",
                 source_version="v", reviewed=False))
OWN = {"kind": "practice", "claim": "a request answered the same day keeps a thread warm",
       "why": "a reply that waits loses attention"}


UNIT = E.EngineLine(ref="ru:core.risk", family=E.UNIT, words="Risk reads high: quiet for long.",
                    source="core.risk", source_version="v", reviewed=False)


def _check(company=None, **over):
    p = dataclasses.replace(W.parts(), engine=E.EngineRead(lines=LINES), units=E.EngineRead(lines=(UNIT,)),
                            company=company)
    dossier = D.build_dossier(p)
    people = D.people_of(p, us=W.US, our_names=W.OUR_NAMES)
    return check_review(W.review(**over), dossier.text, people)


def _v(checked, line):
    return next(v for v in checked.verdicts if v.line == line and v.verdict != C.NOTED)


# ── facts ─────────────────────────────────────────────────────────────────────────────────────

def test_a_fact_citing_only_the_engine_or_the_experts_own_is_no_fact():
    only_engine = _check(fact2={"evidence": [RULE]})
    assert (_v(only_engine, "fact:2").verdict, _v(only_engine, "fact:2").reason) == (C.DROPPED, C.ENGINE_IS_NO_FACT)
    only_own = _check(fact2={"evidence": ["own:1"]}, own=[OWN])
    assert _v(only_own, "fact:2").reason == C.ENGINE_IS_NO_FACT
    both = _check(fact2={"evidence": [RULE, PB]})
    assert _v(both, "fact:2").reason == C.ENGINE_IS_NO_FACT


def test_an_engine_id_must_be_printed_as_an_evidence_id_must():
    checked = _check(fact2={"evidence": [W.ASK_DECK, "rule:never_printed"]})
    assert (_v(checked, "fact:2").reason, _v(checked, "fact:2").detail) == (C.UNKNOWN_EVIDENCE, "rule:never_printed")


def test_beside_data_a_fact_stands_on_the_data_and_the_engine_grounds_nothing_of_it():
    stands = _check(fact2={"evidence": [W.ASK_DECK, RULE]})
    assert _v(stands, "fact:2").verdict == C.KEPT
    # "14 days" is the ENGINE's number: a fact about this file may not lean on it.
    wrong = _check(fact2={"claim": "His ask for the deck has waited 14 days", "evidence": [W.ASK_DECK, RULE]})
    assert (_v(wrong, "fact:2").verdict, _v(wrong, "fact:2").reason) == (C.DROPPED, C.WRONG_NUMBER)


def test_the_standing_data_alone_is_what_a_confidence_may_count():
    checked = _check(fact2={"evidence": [W.ASK_DECK, RULE]})
    assert RULE not in checked.cited and W.ASK_DECK in checked.cited
    assert RULE not in checked.words.evidence


# ── the expert's own ──────────────────────────────────────────────────────────────────────────

def test_an_own_line_is_kept_and_labelled_own():
    checked = _check(own=[OWN])
    assert _v(checked, "own:1") == C.LineVerdict("own:1", C.KEPT) and _v(checked, "own:1").source == C.OWN


@pytest.mark.parametrize("own, reason", [
    ({**OWN, "claim": "a deck is read within 7 days"}, C.OWN_STATES_A_NUMBER),
    ({**OWN, "why": "a second round of mail loses 2 weeks"}, C.OWN_STATES_A_NUMBER),
    ({**OWN, "claim": "Marco answers a request the same day"}, C.OWN_NAMES_THE_FILE),
    ({**OWN, "why": "Altavia keeps a thread warm"}, C.OWN_NAMES_THE_FILE),
    ({**OWN, "claim": "write to marco@altavia.test the same day"}, C.OWN_NAMES_THE_FILE),
    ({**OWN, "claim": "a request to altavia.test is answered the same day"}, C.OWN_NAMES_THE_FILE)])
def test_an_own_line_with_a_digit_or_a_name_of_the_file_drops(own, reason):
    checked = _check(own=[own])
    assert (_v(checked, "own:1").verdict, _v(checked, "own:1").reason) == (C.DROPPED, reason)


def test_an_ordinary_word_in_an_own_line_is_no_name_of_the_file():
    assert _v(_check(own=[{**OWN, "claim": "A marco polo of mail is no practice"}]), "own:1").verdict == C.DROPPED
    assert _v(_check(own=[{**OWN, "claim": "an introduced investor screens before a call"}]),
              "own:1").verdict == C.KEPT


def test_an_own_line_grounds_an_inference_or_pattern_only_beside_a_standing_data_line():
    alone = _check(own=[OWN], inferences=[{"claim": "the thread is warm", "based_on": ["own:1"]}])
    assert (_v(alone, "inference:1").verdict, _v(alone, "inference:1").reason) == (C.DROPPED, C.UNGROUNDED)
    beside = _check(own=[OWN], inferences=[{"claim": "the thread is warm", "based_on": ["own:1", "fact:1"]}])
    assert _v(beside, "inference:1").verdict == C.KEPT and _v(beside, "inference:1").source == C.MIXED
    fell = _check(own=[OWN], fact1={"evidence": []},
                  inferences=[{"claim": "the thread is warm", "based_on": ["own:1", "fact:1"]}])
    assert _v(fell, "inference:1").reason == C.UNGROUNDED, "its data line fell"
    dropped_own = _check(own=[{**OWN, "claim": "after 3 days"}],
                         inferences=[{"claim": "the thread is warm", "based_on": ["own:1", "fact:1"]}],
                         patterns=[{"kind": "pattern", "claim": "it holds", "based_on": ["own:1"]}])
    assert _v(dropped_own, "inference:1").verdict == C.KEPT, "fact:1 still grounds it"
    assert _v(dropped_own, "pattern:1").reason == C.UNGROUNDED


def test_an_own_ref_past_the_experts_own_lines_grounds_nothing():
    checked = _check(own=[OWN], inferences=[{"claim": "x is so", "based_on": ["own:3", "fact:1"]}])
    assert _v(checked, "inference:1").verdict == C.KEPT, "fact:1 holds it; own:3 is no line"


# ── the engine in an inference or a pattern ───────────────────────────────────────────────────

def test_an_engine_line_alone_may_ground_a_pattern_and_is_labelled_engine():
    checked = _check(patterns=[{"kind": "pattern", "claim": "a partner meeting follows a deck", "based_on": [PB]}])
    assert _v(checked, "pattern:1").verdict == C.KEPT and _v(checked, "pattern:1").source == C.ENGINE


def test_an_inference_citing_an_engine_line_holds_its_names_and_numbers():
    ok = _check(inferences=[{"claim": "Marco is likely to follow the rule", "based_on": [RULE, "fact:1"]}])
    assert _v(ok, "inference:1").verdict == C.KEPT
    name = _check(inferences=[{"claim": "Neel is likely to follow the rule", "based_on": [RULE, "fact:1"]}])
    assert (_v(name, "inference:1").verdict, _v(name, "inference:1").reason) == (C.DROPPED, C.UNSUPPORTED)
    number = _check(inferences=[{"claim": "He will wait 30 days", "based_on": [RULE, "fact:1"]}])
    assert (_v(number, "inference:1").verdict, _v(number, "inference:1").reason) == (C.DROPPED, C.WRONG_NUMBER)
    own_number = _check(inferences=[{"claim": "The gap is 14 days", "based_on": [RULE, "fact:1"]}])
    assert _v(own_number, "inference:1").verdict == C.KEPT, "the engine line's own number is its to say"


def test_an_inference_citing_no_engine_line_is_read_as_before():
    assert _v(_check(inferences=[{"claim": "Neel will wait 30 days", "based_on": ["fact:1"]}]),
              "inference:1").verdict == C.KEPT


def test_an_inference_citing_an_own_line_against_the_engine_is_noted():
    checked = _check(own=[OWN], inferences=[{"claim": "this file differs", "based_on": ["own:1", RULE, "fact:1"]}])
    assert C.OWN_DISAGREES in checked.notes
    assert C.OWN_DISAGREES not in _check(own=[OWN], inferences=[
        {"claim": "this file differs", "based_on": ["own:1", "fact:1"]}]).notes


# ── the move ──────────────────────────────────────────────────────────────────────────────────

def test_a_move_resting_on_an_inference_rests_on_its_facts():
    on_fact = _check(fact1={"quote": None}, move={"rests_on": ["fact:1"]})
    on_inference = _check(fact1={"quote": None}, move={"rests_on": ["inference:1"]})
    assert _v(on_fact, "fact:1").reason == _v(on_inference, "fact:1").reason == C.UNQUOTED
    assert on_inference.fate == C.HELD
    assert all(v.line != "rests_on" for v in on_inference.verdicts), "inference:1 is an inference of the review"
    only_second = _check(fact1={"quote": None}, move={"rests_on": ["fact:2"]})
    assert only_second.fate == C.SHOWN, "fact 1 is not what the move rests on"
    inference_of_two = _check(
        fact1={"quote": None}, inferences=[{"claim": "both hold", "based_on": ["fact:2"]}],
        move={"rests_on": ["inference:1"]})
    assert inference_of_two.fate == C.SHOWN, "the inference rests on fact 2, not fact 1"


def test_a_rests_on_naming_no_fact_and_no_inference_of_the_review_is_a_stray():
    checked = _check(move={"rests_on": ["fact:1", "inference:4"]})
    assert (_v(checked, "rests_on").reason, _v(checked, "rests_on").detail) == (C.UNKNOWN_EVIDENCE, "inference:4")


def test_what_the_move_is_guided_by_is_held_like_a_ground():
    ok = _check(own=[OWN], move={"guided_by": [RULE, "own:1"]})
    assert _v(ok, "guided_by").verdict == C.KEPT
    bad = _check(own=[OWN], move={"guided_by": [RULE, "own:2", "rule:never_printed"]})
    assert (_v(bad, "guided_by").verdict, _v(bad, "guided_by").reason) == (C.DROPPED, C.UNKNOWN_EVIDENCE)
    assert _v(bad, "guided_by").detail == "own:2, rule:never_printed"
    assert bad.fate == C.SHOWN, "a slip of one optional field never holds the move"
    gone = _check(own=[{**OWN, "claim": "after 3 days"}], move={"guided_by": ["own:1"]})
    assert _v(gone, "guided_by").verdict == C.DROPPED, "an own line that fell guides nothing"
    assert all(v.line != "guided_by" for v in _check().verdicts)


# ── the labels and the engine lines kept on the check ──────────────────────────────────────────

def test_every_line_is_labelled_by_code_from_what_it_cites():
    checked = _check(own=[OWN], inferences=[{"claim": "one", "based_on": ["fact:1"]},
                                            {"claim": "two", "based_on": [RULE, "fact:1"]}],
                     patterns=[{"kind": "pattern", "claim": "three", "based_on": [PB]}])
    assert [_v(checked, f"fact:{n}").source for n in (1, 2, 3, 4)] == [C.DATA] * 4
    assert _v(checked, "inference:1").source == C.DATA and _v(checked, "inference:2").source == C.MIXED
    assert _v(checked, "pattern:1").source == C.ENGINE


def test_the_engine_lines_the_standing_lines_cite_are_kept_with_their_words():
    checked = _check(fact2={"evidence": [W.ASK_DECK, RULE]},
                     patterns=[{"kind": "pattern", "claim": "a meeting follows", "based_on": [PB]}])
    assert [c.ref for c in checked.engine] == sorted([PB, RULE])
    rule = next(c for c in checked.engine if c.ref == RULE)
    assert (rule.words, rule.source, rule.reviewed) == (
        "Follow up once, a week after a deck. Typical gap is 14 days.", "fundraising.rules", True)
    pb = next(c for c in checked.engine if c.ref == PB)
    assert (pb.source, pb.reviewed) == ("Run the round", False)
    assert C.CheckedReview.from_mapping(checked.as_mapping()).engine == checked.engine


def test_the_engine_grounds_no_word_of_the_card():
    """The headline stands on the file's lines: "14 days" is the engine's number, not the file's."""
    checked = _check(fact2={"evidence": [W.ASK_DECK, RULE]},
                     move={"what": "Send Marco the short deck within 14 days", "rests_on": ["fact:1", "fact:2"]})
    assert _v(checked, "move").verdict == C.DROPPED and checked.fate == C.HELD


def test_a_unit_reading_is_kept_as_a_line_no_one_reviewed():
    checked = _check(patterns=[{"kind": "pattern", "claim": "the quiet is long", "based_on": ["ru:core.risk"]}])
    [unit] = checked.engine
    assert (unit.ref, unit.words, unit.source, unit.reviewed) == (
        "ru:core.risk", "Risk reads high: quiet for long.", "core.risk", False)


def test_an_inference_that_fell_cites_nothing_to_keep():
    checked = _check(inferences=[{"claim": "Neel follows the rule", "based_on": [RULE, "fact:1"]}])
    assert _v(checked, "inference:1").verdict == C.DROPPED and checked.engine == ()


def test_the_names_of_a_file_are_its_people_not_us_and_not_a_function_word():
    from genios_engine.reason.expert import verify as V
    bird, founder = D.Person("Will Bird", "will@birdvc.test"), D.Person("Arjun Rao", "arjun@nimbuslabs.test")
    people = D.FilePeople(counterparty=bird, people=(founder, bird), us=W.US, our_names=W.OUR_NAMES)
    names = V._file_names(people)
    assert "bird" in names and "birdvc" in names and "will@birdvc.test" in names and "birdvc.test" in names
    assert "will" not in names, "a function word names no one"
    assert "arjun" not in names and not any("nimbuslabs" in n for n in names), "the founder is every file's"


SELF = __import__("genios_engine.context.company_record", fromlist=["x"])


def test_a_fact_resting_on_a_line_of_the_company_record_quotes_it_as_a_touch():
    from datetime import datetime, timezone
    line = SELF.SelfLine(event_id="evt_elsewhere", at=datetime(2026, 8, 1, 9, 0, tzinfo=timezone.utc),
                         said="We closed our pre-seed round last month.")
    record = SELF.CompanyRecord(org_id="org_x", as_of=W.NOW, lines=(line,))
    fact = {"claim": "You told another investor the pre-seed round closed", "evidence": ["self:evt_elsewhere"]}
    unquoted = _check(company=record, fact2=fact)
    assert _v(unquoted, "fact:2").reason == C.UNQUOTED
    quoted = _check(company=record, fact2={**fact, "quote": "We closed our pre-seed round last month"})
    assert _v(quoted, "fact:2").verdict == C.KEPT
    misquoted = _check(company=record, fact2={**fact, "quote": "We raised a seed round last month"})
    assert _v(misquoted, "fact:2").reason == C.MISQUOTED


def test_an_engine_line_cited_only_by_a_dropped_line_is_not_kept():
    checked = _check(fact2={"claim": "Neel waits", "evidence": [W.ASK_DECK, RULE]})
    assert _v(checked, "fact:2").verdict == C.DROPPED and RULE not in [c.ref for c in checked.engine]


def test_a_review_that_cites_no_engine_line_keeps_none():
    assert _check().engine == ()
