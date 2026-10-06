"""STEP-01 · how a founder case is marked — once, for the founder test and the board alike.

    pytest tests/replays/test_marking.py -q

The verdict is about what the founder SEES: the cards a case expects, the cards it forbids, and
the forbidden names and phrases. Where a must-detect case was lost — at the gate, before memory,
or in reasoning — is reported beside it, because that is what the next step needs to know; the
stage checks do not decide the verdict.

A must-abstain case passes only with its witness: silence from a chain that never reached the
stage is NOT EXERCISED, not a pass. What the engine cannot express is counted apart.
"""
from __future__ import annotations

import copy

import pytest

from tests.replays import founder_case as fc
from tests.replays.marking import (FAIL, NOT_EXERCISED, NOT_EXPRESSIBLE, PASS, judge)

BASE = {
    "case_id": "F93", "title": "An investor asks for the deck", "kind": "must_detect",
    "label_row": 10, "labelled_by": "claude", "replays": [],
    "founder": {"name": "Arjun Rao", "email": "arjun@nimbuslabs.test", "company": "Nimbus Labs",
                "timezone": "Asia/Kolkata"},
    "sweeps": ["2026-09-18T12:00:00Z", "2026-09-19T12:00:00Z"],
    "objects": [{"id": "ask", "source": "gmail", "sweep": 0,
                 "occurred_at": "2026-09-18T09:30:00Z",
                 "from": "Kavya Menon <kavya@lotusvc.test>", "to": ["arjun@nimbuslabs.test"],
                 "subject": "Deck?", "body": "Could you send the deck?", "labels": ["INBOX"]}],
    "expected": {"gate": {"ask": "emitted"}, "memory": {"ask": True},
                 "cards": [{"about": ["Kavya", "Lotus"], "min": 1, "max": 1,
                            "mentions": ["deck"]}],
                 "workstream": "investor"},
    "forbidden": {"names": ["Arjun Rao"], "phrases": ["last chance"]},
    "witness": None,
    "not_expressible": {"workstream": "STEP-09 — no workstream yet"},
}


def _case(**over) -> fc.FounderCase:
    raw = copy.deepcopy(BASE)
    raw.update(over)
    return fc.parse_case(raw, source="t.json")


def _abstain() -> fc.FounderCase:
    raw = copy.deepcopy(BASE)
    raw.update(kind="must_abstain", witness={"stage": "memory", "objects": ["ask"]},
               not_expressible={})
    raw["expected"] = {"cards": [{"about": ["Kavya"], "min": 0, "max": 0}]}
    return fc.parse_case(raw, source="t.json")


def _card(card_id: str, text: str, sweeps=(0, 1), subject: str | None = None) -> fc.CardView:
    return fc.CardView(card_id=card_id, state="queued", level="prescriptive", text=text,
                       output_lane=None, sweeps=tuple(sweeps), subject=subject)


def _run(*, cards=(), outcome="emitted", reason=None, facts=3, situations=(), chain_ok=(True, True),
         misses=()) -> fc.CaseRun:
    return fc.CaseRun(
        case_id="F93", org_id="org_golden_f93",
        landed=(fc.Landed(object_id="ask", source_object_id="f93-ask", event_id="evt_1",
                          outcome=outcome, reason=reason, sweep=0),),
        memory={"ask": facts}, situations=tuple(situations), cards=tuple(cards),
        funnel=({}, {}), chain_ok=tuple(chain_ok), model_calls=(), misses=tuple(misses))


# =================================================================================================
# must-detect
# =================================================================================================
def test_the_right_card_passes():
    mark = judge(_case(), _run(cards=[_card("c1", "Reply to Kavya Menon: send the deck")]))
    assert mark.verdict == PASS, mark
    assert mark.lost_at is None


def test_no_card_fails_and_says_it_was_lost_in_reasoning():
    mark = judge(_case(), _run())
    assert mark.verdict == FAIL and mark.lost_at == "reasoning"
    assert "0 card" in mark.reason


def test_a_mail_dropped_at_the_gate_is_lost_at_the_gate():
    mark = judge(_case(), _run(outcome="dropped", reason="N-06", facts=0))
    assert mark.verdict == FAIL and mark.lost_at == "gate"
    gate = next(c for c in mark.checks if c.name == "gate:ask")
    assert gate.verdict == FAIL and "dropped" in gate.reason and "N-06" in gate.reason


def test_a_mail_archived_at_the_gate_is_lost_at_the_gate_and_says_it_was_kept():
    """STEP-03 (`yc2_w27_s03/M21.C5.L-logic.V4.U02`): the gate archives what it used to drop. For the
    founder nothing changes — the mail was not read, so the case is lost at the gate exactly as
    before — but the check must name the rule and say the mail is KEPT: an archived must-detect
    mail is the one STEP-05 can still promote, a dropped one is gone."""
    mark = judge(_case(), _run(outcome="archived", reason="N-02", facts=0))
    assert mark.verdict == FAIL and mark.lost_at == "gate"
    gate = next(c for c in mark.checks if c.name == "gate:ask")
    assert gate.verdict == FAIL and "archived:N-02" in gate.reason
    assert "kept, read by no model" in gate.reason


def test_a_dropped_mail_is_not_said_to_be_kept():
    gate = next(c for c in judge(_case(), _run(outcome="dropped", reason="N-06", facts=0)).checks
                if c.name == "gate:ask")
    assert "kept" not in gate.reason


def test_a_mail_kept_but_never_in_memory_is_lost_before_memory():
    mark = judge(_case(), _run(facts=0))
    assert mark.verdict == FAIL and mark.lost_at == "memory"


def test_six_cards_where_one_was_expected_fails():
    cards = [_card(f"c{i}", f"Kavya Menon item {i}: the deck") for i in range(6)]
    mark = judge(_case(), _run(cards=cards))
    assert mark.verdict == FAIL and "6 cards" in mark.reason


def test_a_card_that_does_not_say_what_it_must_fails():
    mark = judge(_case(), _run(cards=[_card("c1", "Kavya Menon is waiting")]))
    assert mark.verdict == FAIL and "deck" in mark.reason


def test_a_forbidden_name_on_any_card_fails_and_is_counted():
    cards = [_card("c1", "Send Arjun Rao the deck — Kavya"), _card("c2", "last chance with Lotus")]
    mark = judge(_case(), _run(cards=cards))
    assert mark.verdict == FAIL
    assert sorted(mark.forbidden_hits) == [("c1", "Arjun Rao"), ("c2", "last chance")]


def test_matching_is_whole_word():
    mark = judge(_case(), _run(cards=[_card("c1", "Kavyas lotuses decked out")]))
    assert mark.verdict == FAIL and "0 card" in mark.reason


def test_a_chain_that_crashed_fails_whatever_it_left_behind():
    mark = judge(_case(), _run(cards=[_card("c1", "Kavya: send the deck")],
                               chain_ok=(True, False)))
    assert mark.verdict == FAIL and "sweep 1" in mark.reason


def test_a_swallowed_cassette_miss_fails_the_run():
    mark = judge(_case(), _run(cards=[_card("c1", "Kavya: send the deck")],
                               misses=[("narrator", "ab" * 32)]))
    assert mark.verdict == FAIL and "cassette" in mark.reason


def test_what_cannot_be_expressed_is_reported_apart_and_decides_nothing():
    mark = judge(_case(), _run(cards=[_card("c1", "Kavya: send the deck")]))
    declared = [c for c in mark.checks if c.verdict == NOT_EXPRESSIBLE]
    assert [c.name for c in declared] == ["workstream"] and "STEP-09" in declared[0].reason
    assert mark.verdict == PASS


def test_a_case_whose_only_card_expectation_is_declared_is_not_expressible():
    raw = copy.deepcopy(BASE)
    raw["not_expressible"] = {"workstream": "STEP-09", "cards": "the screen door is not driven"}
    mark = judge(fc.parse_case(raw, source="t.json"), _run())
    assert mark.verdict == NOT_EXPRESSIBLE


# =================================================================================================
# must-abstain
# =================================================================================================
def test_silence_with_its_witness_passes():
    assert judge(_abstain(), _run()).verdict == PASS


def test_silence_without_its_witness_is_not_exercised():
    """The mail never reached memory: "no card" says nothing about the decision not to make one."""
    mark = judge(_abstain(), _run(facts=0))
    assert mark.verdict == NOT_EXERCISED and "witness" in mark.reason


def test_the_card_that_must_not_exist_fails_whatever_the_witness():
    mark = judge(_abstain(), _run(facts=0, cards=[_card("c1", "Recap for Kavya")]))
    assert mark.verdict == FAIL


# =================================================================================================
# STEP-04 · we are never the subject of a card
# =================================================================================================
def _gmail_founder() -> fc.FounderCase:
    raw = copy.deepcopy(BASE)
    raw["founder"] = {"name": "Meera Iyer", "email": "meera.iyer@gmail.com", "company": "Kitebird",
                      "timezone": "Asia/Kolkata", "also": ["ceo@kitebird.test"],
                      "domains": ["kitebird.test"]}
    raw["objects"][0]["to"] = ["meera.iyer@gmail.com"]
    raw["forbidden"] = {"names": [], "phrases": []}
    raw["expected"]["cards"] = [{"about": ["Kavya"], "min": 1, "max": 1, "mentions": ["deck"]}]
    return fc.parse_case(raw, source="t.json")


@pytest.mark.parametrize("subject", ["Meera Iyer", "meera.iyer@gmail.com", "CEO@kitebird.test",
                                     "kitebird.test", "Ms Meera Iyer — waiting on you"])
def test_a_card_whose_subject_is_the_founder_fails_whatever_else_it_says(subject):
    """STEP-04 (`yc2_w27_s04/M22.C5.L-logic.V1.U03`): production showed *"Send Mr Rohit Swerashi your
    traction metrics"* — a card telling the founder to act on himself. Its subject was the founder; a
    card's subject is the counterparty, always."""
    case = _gmail_founder()
    run = _run(cards=[_card("c1", "Kavya Menon asked for the deck", subject="Kavya Menon"),
                      _card("c2", "Send the deck — Kavya asked", subject=subject)])
    mark = judge(case, run)
    assert mark.verdict == FAIL
    assert "subject is the founder" in mark.reason and "c2" in mark.reason


def test_a_card_about_the_counterparty_that_quotes_the_founder_passes():
    """Our words may be on the card (`7075014c` — a stated dependency is grounded on them); we may
    never be the one it is about."""
    case = _gmail_founder()
    run = _run(cards=[_card("c1", "Kavya Menon: 'Hi Meera, send the deck'", subject="Kavya Menon")])
    assert judge(case, run).verdict == PASS


def test_a_card_with_no_subject_is_not_judged_on_it():
    case = _gmail_founder()
    run = _run(cards=[_card("c1", "Kavya Menon asked for the deck", subject=None)])
    assert judge(case, run).verdict == PASS
