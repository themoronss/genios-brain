"""The judgment's lane reaches the card: a move L2 says is not one to make yet is held as one question.

    pytest tests/reason/l2/test_the_lane_reaches_the_card.py -q

L3 audit, 21 Oct 2026. Under `l2_cards` the L2 judgment's review is the file's review, and the card decides from
the review's mode and its claim check (`reason/expert/decide.mode_of`). L2 computes a lane beside the review
(`contracts/reasoning_result.lane_for`) and names what a person must look at first (`review_required`) — and
nothing read either: an `act` over an open conflict, an `act` on low evidence confidence, a decision nobody was
named to make, a move dated before the run — each was still a decision card with a draft. Now
`judgment_hold` hands the check one reason and the check holds the move: the card asks ONE question in our closed
words, and its headline and draft are withheld. A replay holds it the same way. An expert review has no judgment
and is checked exactly as before.
"""
from __future__ import annotations

import pytest

from genios_engine.contracts import claim_check as C
from genios_engine.contracts.reasoning_result import (CONFIDENCE_DIMENSIONS, ENDED_RESULT, LANE_CONFLICT,
                                                      LANE_DECISION, LANE_MONITOR, judgment_hold)
from genios_engine.reason.expert.verify import check_review
from genios_engine.reason.l2 import prompt as P
from genios_engine.reason.l2 import store as ST
from genios_engine.reason.l2.replay import replay_row
from tests.reason.l2.test_one_judgment import DOSSIER, PEOPLE, _answer, _Client, _judge
from tests.reason.l2.world import answer
from tests.reason.expert.test_the_dossier import NOW

pytestmark = pytest.mark.unit


def _confidence(**levels):
    return {d: {"level": levels.get(d, "high"), "reason": "the mail says so", "evidence": ["evt_005"]}
            for d in CONFIDENCE_DIMENSIONS}


#: Each way the judgment says "not a move yet", and the reason the check holds it for.
HELD_BY = {
    "open_conflict": (dict(open_conflict={"about": "the call date", "between": ["evt_005", "sig:s1"]}), C.OPEN_CONFLICT),
    "low_evidence": (dict(confidence=_confidence(evidence="low")), C.WEAK_GROUND),
    "unknown_framing": (dict(confidence=_confidence(framing="unknown")), C.WEAK_GROUND),
    "no_decider": (dict(decision_need={"needed": True, "who": None, "what": "whether to book"}), C.NO_DECIDER),
}


def _result(**over):
    judged = _judge(_Client(_answer(answer(**over))))
    assert judged.ended == ENDED_RESULT, judged.reason
    return judged.result


def test_a_judgment_with_nothing_against_the_move_shows_it():
    """The half that must not move: a good act is still a decision card with its words."""
    r = _result()
    assert r.lane == LANE_DECISION and r.check_fate == C.SHOWN
    assert r.checked.words.headline and not any(v.line == "judgment" for v in r.checked.verdicts)


@pytest.mark.parametrize("case", sorted(HELD_BY))
def test_a_move_the_judgment_says_is_not_one_to_make_is_held_as_one_question(case):
    over, why = HELD_BY[case]
    r = _result(**over)
    assert r.check_fate == C.HELD and r.checked.because == C.HELD_BECAUSE[why], (
        f"{case}: the card was still a decision ({r.check_fate}) though the judgment's lane is {r.lane}")
    assert r.checked.question and C.HELD_BECAUSE[why] in r.checked.question
    assert r.checked.words.headline is None and r.checked.words.draft is None, "a held move shows no draft"
    assert [v.reason for v in r.checked.verdicts if v.line == "judgment"] == [why]


def test_a_move_dated_before_the_run_is_held():
    raw = answer()
    raw["next_move"] = {**raw["next_move"], "by_when": (NOW.date().replace(day=1)).isoformat()}
    judged = _judge(_Client(_answer(raw)))
    r = judged.result
    assert r.check_fate == C.HELD and r.checked.because == C.HELD_BECAUSE[C.MOVE_DATE_PASSED]


def test_the_lanes_are_what_lane_for_says():
    assert _result(**HELD_BY["open_conflict"][0]).lane == LANE_CONFLICT
    assert _result(**HELD_BY["low_evidence"][0]).lane == LANE_MONITOR


def test_a_finding_out_review_keeps_its_own_question():
    """Only an act's move is held: a find-out already asks, and its question is its own."""
    r = _result(mode="find_out", intervention_mode="gather_evidence",
                open_conflict={"about": "the call date", "between": ["evt_005", "sig:s1"]})
    assert not any(v.line == "judgment" for v in r.checked.verdicts)


@pytest.mark.parametrize("case", sorted(HELD_BY))
def test_a_replay_holds_it_the_same_way(case):
    r = _result(**HELD_BY[case][0])
    row = ST.StoredResult(subject_ref=r.subject_ref, fingerprint="l2fp:t", status=ST.RESULT, reason=None,
                          depth=r.depth, lane=r.lane, result=r.as_mapping(), receipt={"output_hash": r.output_hash()},
                          dossier={"text": DOSSIER.text, "evidence_ids": sorted(DOSSIER.catalogue.evidence_ids),
                                   "numbers": sorted(DOSSIER.catalogue.numbers),
                                   "stages": list(DOSSIER.catalogue.stages)},
                          prompt_version=P.PROMPT_VERSION, reasoned_at=NOW)
    assert replay_row(row, PEOPLE).check_fate == r.check_fate == C.HELD


def test_an_expert_review_is_checked_as_before():
    """No judgment, no hold: the expert path calls the check without one."""
    r = _result(**HELD_BY["open_conflict"][0])
    plain = check_review(r.review, DOSSIER.text, PEOPLE, evidence_ids=DOSSIER.catalogue.evidence_ids)
    assert plain.fate == C.SHOWN


def test_the_hold_reasons_are_closed_and_said_in_founder_words():
    assert set(C.JUDGMENT_HOLDS) <= set(C.REASONS) and "judgment" in C.CARD_LINES
    for why in C.JUDGMENT_HOLDS:
        assert C.HELD_BECAUSE[why]
    assert judgment_hold(LANE_DECISION, ()) is None
    assert judgment_hold(LANE_CONFLICT, (("decision_without_owner", "x"),)) == C.OPEN_CONFLICT, "a conflict first"
