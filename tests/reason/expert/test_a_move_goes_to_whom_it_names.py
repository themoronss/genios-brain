"""STEP-13 · a move goes to the person it names, never to us beside them (second crosscheck F1).

    .venv/bin/python -m pytest -q tests/reason/expert/test_a_move_goes_to_whom_it_names.py

Tree `yc2_w27_s13` M35.C2.L-logic.V1.U14 (fix) — `reason/expert/verify._target`. X20's fix read whom a move with no
`to` goes to as the FIRST person its headline names — and counted our own names among them: "Send the Nimbus Labs
short deck to Marco", "Introduce Nimbus Labs to Marco with the short deck", "Have Arjun Rao send Marco the short
deck" and "Arjun Rao should send Marco the short deck" were held "It is addressed to you." (be27bffe showed all
four). We are the recipient only of a move that names nobody of the file.
"""
from __future__ import annotations

import pytest

from genios_engine.contracts import claim_check as C
from genios_engine.reason.expert.verify import check_review
from tests.reason.expert import check_world as W

pytestmark = pytest.mark.unit

NAMES_US_FIRST = ["Send the Nimbus Labs short deck to Marco",
                  "Introduce Nimbus Labs to Marco with the short deck",
                  "Have Arjun Rao send Marco the short deck",
                  "Arjun Rao should send Marco the short deck",
                  "Have arjun@nimbuslabs.test send Marco the short deck"]


def _check(**over) -> C.CheckedReview:
    dossier, people = W.world()
    return check_review(W.review(**over), dossier.text, people)


def _to(checked: C.CheckedReview) -> C.LineVerdict | None:
    return next((v for v in checked.verdicts if v.line == "to"), None)


@pytest.mark.parametrize("what", NAMES_US_FIRST)
def test_f1_a_move_naming_us_before_the_counterparty_goes_to_the_counterparty(what):
    checked = _check(move={"what": what, "to": None}, draft=None)
    assert checked.fate == C.SHOWN, (checked.fate, checked.question, checked.verdicts)
    assert checked.words.headline == what and _to(checked) is None


@pytest.mark.parametrize("what", NAMES_US_FIRST)
def test_with_a_draft_and_no_to_only_the_draft_is_withheld(what):
    checked = _check(move={"what": what, "to": None})
    assert checked.fate == C.SHOWN and checked.words.headline == what
    assert _to(checked) == C.LineVerdict("to", C.DROPPED, C.NO_RECIPIENT) and checked.words.draft is None


@pytest.mark.parametrize("what", ["Send Arjun Rao the short deck to review first",
                                  "Send the short deck to arjun@nimbuslabs.test first",
                                  "Nimbus Labs should file the deck"])
def test_a_move_that_names_only_us_is_still_addressed_to_us(what):
    checked = _check(move={"what": what, "to": None}, draft=None)
    assert _to(checked).reason == C.RECIPIENT_IS_US and checked.fate == C.HELD


def test_a_move_naming_us_and_the_connector_still_goes_to_the_connector():
    checked = _check(move={"what": "Have Arjun Rao send Introly the short deck to pass on to Marco", "to": None},
                     draft=None)
    assert _to(checked).reason == C.RECIPIENT_IS_CONNECTOR
