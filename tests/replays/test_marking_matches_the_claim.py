"""STEP-01 follow-up c · a forbidden phrase is matched as a claim, never as a piece of another word.

    pytest tests/replays/test_marking_matches_the_claim.py -q

`yc2_w27_align` M34.C1.L-logic.V1.U05. `marking._forbidden` matched a forbidden PHRASE as a substring
(`phrase.lower() in text.lower()`) while a forbidden NAME was matched as whole words (`says`). So the
benchmark's invented-traction guard on case F52 — "ARR", "MRR" — would fire on a card that says a reply
"arrived", or "MRRs" in a bulletin, and a case could fail on a word nobody wrote. A phrase is now the
claim it names: whole words, either case, any run of spaces between them.
"""
from __future__ import annotations

import copy

import pytest

from tests.replays import founder_case as fc
from tests.replays.marking import FAIL, PASS, judge
from tests.replays.test_marking import BASE, _card, _run


def _case(*phrases: str) -> fc.FounderCase:
    raw = copy.deepcopy(BASE)
    raw["forbidden"] = {"names": [], "phrases": list(phrases)}
    return fc.parse_case(raw, source="t.json")


def _says(text: str, *phrases: str) -> list:
    card = _card("c1", "Reply to Kavya Menon: send the deck\n" + text)
    return list(judge(_case(*phrases), _run(cards=[card])).forbidden_hits)


@pytest.mark.parametrize("text", ["Kavya's reply arrived on Monday.", "The arrangement holds.",
                                  "Carry the deck to the call."])
def test_a_phrase_inside_another_word_is_not_said(text):
    assert _says(text, "ARR") == []


@pytest.mark.parametrize("text", ["Your ARR is $40k.", "arr of the company", "MRR and ARR, both up.",
                                  "(ARR)"])
def test_the_phrase_itself_is_said_in_any_case(text):
    assert _says(text, "ARR") == [("c1", "ARR")]


def test_a_phrase_of_several_words_is_said_across_any_spacing():
    assert _says("We should   follow up\nwith Mira today.", "follow up with Mira") == [
        ("c1", "follow up with Mira")]
    assert _says("We should follow up with Miranda.", "follow up with Mira") == []


def test_a_said_phrase_still_fails_the_case():
    """The rule moved, not the verdict: a card that makes the forbidden claim still fails."""
    card = _card("c1", "Reply to Kavya Menon: send the deck. Your ARR is $40k.")
    assert judge(_case("ARR"), _run(cards=[card])).verdict == FAIL
    clean = _card("c1", "Reply to Kavya Menon: send the deck. It arrived.")
    assert judge(_case("ARR"), _run(cards=[clean])).verdict == PASS
