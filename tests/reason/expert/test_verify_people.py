"""STEP-13 §3.3 · the right people — whom a draft goes to, and whose ask a move answers.

    .venv/bin/python -m pytest -q tests/reason/expert/test_verify_people.py

Tree `yc2_w27_s13` M35.C2.L-logic.V1.U04 (`reason/expert/verify`). A draft goes to someone the file's mail shows
(`to`): with no `to`, or to someone not on the file, the draft is withheld and the move stands; to us, the
move is held; to the connector that introduced the file's counterparty — when the file is not the
connector's own — the review's own alternative becomes the move if it checks (the draft withheld), else the
move is held. A move answering an ask answers one that waits on US. A card text that calls the founder
"the founder" or names us as a party is noted (F178) — never dropped.
"""
from __future__ import annotations

import pytest

from genios_engine.contracts import claim_check as C
from genios_engine.reason.expert import dossier as D
from genios_engine.reason.expert.verify import check_review, matches
from tests.reason.expert import check_world as W

pytestmark = pytest.mark.unit


def _check(world_kw=None, **over) -> C.CheckedReview:
    dossier, people = W.world(**(world_kw or {}))
    return check_review(W.review(**over), dossier.text, people)


def _verdict(checked: C.CheckedReview, line: str) -> C.LineVerdict:
    return next(v for v in checked.verdicts if v.line == line and v.verdict != C.NOTED)


def test_a_draft_to_someone_on_the_file_goes():
    checked = _check()
    assert _verdict(checked, "to").verdict == C.KEPT
    assert checked.words.to == "Marco" and checked.words.draft


@pytest.mark.parametrize("to, reason", [(None, C.NO_RECIPIENT), ("Priya Nair", C.RECIPIENT_NOT_ON_FILE),
                                        ("partners@altavia.test", C.RECIPIENT_NOT_ON_FILE)])
def test_a_draft_with_nobody_on_the_file_to_go_to_is_withheld_and_the_move_stands(to, reason):
    checked = _check(move={"to": to})
    assert _verdict(checked, "to").reason == reason
    assert checked.words.draft is None and checked.words.to is None
    assert checked.fate == C.SHOWN and checked.words.headline


@pytest.mark.parametrize("to", ["Arjun Rao", "arjun@nimbuslabs.test", "Nimbus Labs",
                                "ops@nimbuslabs.test"])
def test_a_draft_to_us_holds_the_move(to):
    checked = _check(move={"to": to})
    assert _verdict(checked, "to") == C.LineVerdict("to", C.DROPPED, C.RECIPIENT_IS_US, to)
    assert checked.fate == C.HELD and checked.words.draft is None and checked.words.headline is None
    assert "addressed to you" in checked.question


def test_a_draft_to_the_connector_becomes_the_reviews_own_alternative():
    """'Send Boardy the update' on the file of the person Boardy introduced (replay 02): the move goes to
    that person — the review's alternative, checked — and the draft, written for the connector, does not."""
    checked = _check(move={"to": "Introly", "what": "Send Introly the short deck to pass on to Marco"})
    assert _verdict(checked, "to") == C.LineVerdict("to", C.DROPPED, C.RECIPIENT_IS_CONNECTOR, "Introly")
    assert _verdict(checked, "move").verdict == C.CORRECTED and _verdict(checked, "move").reason \
        == C.BY_ALTERNATIVE
    assert checked.fate == C.SHOWN
    assert checked.words.headline == "Write to Marco directly with the deck"
    assert checked.words.draft is None and checked.words.to is None


def test_a_draft_to_the_connector_with_no_usable_alternative_holds_the_move():
    for alternative in ("", "Ask Introly to forward the deck"):
        checked = _check(move={"to": "Introly"}, alternative=alternative)
        assert checked.fate == C.HELD, alternative
        assert "Introly" in checked.question and "Marco Ruiz" in checked.question


def test_a_draft_to_the_counterparty_is_never_the_connectors_even_when_they_share_a_name():
    """Introduced by a colleague at the same fund (`partners@altavia.test`): a draft to "Marco Ruiz at
    Altavia" names the connector's label AND the counterparty — it goes to Marco, as written."""
    checked = _check({"introduced_by": "partners@altavia.test"}, move={"to": "Marco Ruiz at Altavia"})
    assert _verdict(checked, "to").verdict == C.KEPT and checked.words.draft


def test_on_the_connectors_own_file_the_connector_is_the_right_person():
    """Introly's own file (it asked us something): answering Introly is right (case F09)."""
    checked = _check({"kind": "connector"}, move={"to": "Introly"})
    assert _verdict(checked, "to").verdict == C.KEPT and checked.fate == C.SHOWN


def test_a_move_answering_an_ask_answers_one_that_waits_on_us():
    checked = _check(move={"answers": W.ASK_CALL})
    assert _verdict(checked, "answers") == C.LineVerdict("answers", C.DROPPED, C.NOT_OURS_TO_ANSWER,
                                                         W.ASK_CALL)
    assert checked.fate == C.SHOWN, "the move may still be right: only the link it claims is wrong"
    assert _verdict(_check(), "answers").verdict == C.KEPT


def test_a_move_answering_an_ask_its_dossier_never_printed_drops_the_link():
    """Whether it is answered cannot be read: the `answers` line drops as an unshown citation does, and
    the move stands on its facts — never KEPT on an ask nobody can see."""
    checked = _check(move={"answers": "loop:never_printed"})
    assert _verdict(checked, "answers") == C.LineVerdict("answers", C.DROPPED, C.UNKNOWN_EVIDENCE,
                                                         "loop:never_printed")
    assert checked.fate == C.SHOWN and checked.words.headline


@pytest.mark.parametrize("over, line", [
    ({"frames": {"primary": "The deck is owed by the founder", "rivals": ["a pass"]}}, "situation"),
    ({"done_when": "Marco has the deck from Arjun Rao"}, "done_when"),
    ({"move": {"what": "Have Nimbus Labs send Marco the short deck"}}, "move"),
])
def test_a_card_text_speaking_of_you_is_noted_and_kept(over, line):
    checked = _check(**over)
    assert any(v.line == line and v.verdict == C.NOTED and v.reason == C.SPEAKS_OF_YOU
               for v in checked.verdicts)
    assert checked.stands(line) and checked.fate == C.SHOWN
    assert not any(v.reason == C.SPEAKS_OF_YOU for v in _check().verdicts), "the faithful review speaks to you"


def test_the_draft_may_name_us():
    """A draft is written BY the founder: signing it, or naming the company, is no third person."""
    checked = _check(draft="Hi Marco — the Nimbus Labs deck is attached. Arjun Rao")
    assert not any(v.reason == C.SPEAKS_OF_YOU for v in checked.verdicts)
    assert checked.words.draft


@pytest.mark.parametrize("to, person, named", [
    ("Marco", D.Person("Marco Ruiz", "marco@altavia.test"), True),
    ("Marco Ruiz at Altavia", D.Person("Marco Ruiz", "marco@altavia.test"), True),
    ("marco@altavia.test", D.Person("Marco Ruiz", "marco@altavia.test"), True),
    ("Marcus", D.Person("Marco Ruiz", "marco@altavia.test"), False),
    ("Ruiz", D.Person("Marco Ruiz", "marco@altavia.test"), False),
    ("Introly", D.Person("introly", "hello@introly.test"), True),
    ("Introly's team", D.Person("introly", "hello@introly.test"), True),
    ("Introlytics", D.Person("introly", "hello@introly.test"), False),
    ("Marco", None, False),
    (None, D.Person("Marco Ruiz", None), False),
    # Known only by an address — no name, or the address printed as their name (F30, F48): its words.
    ("Gaurav", D.Person(None, "gaurav@stackfield.test"), True),
    ("Gaurav", D.Person("gaurav@stackfield.test", "gaurav@stackfield.test"), True),
    ("Gaurav Mehta", D.Person(None, "gaurav.mehta@stackfield.test"), True),
    ("Gaurav", D.Person(None, "gaurav.mehta@stackfield.test"), True),
    ("Mehta", D.Person(None, "gaurav.mehta@stackfield.test"), False),
    ("Gaurav", D.Person(None, "stackfield.test"), False),                # a domain has no one's name,
    ("Stackfield", D.Person(None, "stackfield.test"), False),            # and is no one a draft goes to
    ("Gaurav", D.Person("Kunal Shah", "gaurav@stackfield.test"), False),  # a name of their own is theirs
])
def test_whom_a_to_names(to, person, named):
    assert matches(to, person) is named


def test_a_draft_to_someone_the_file_knows_only_by_address_goes():
    """Marco's mail carried no display name: "Marco" is still the man at marco@altavia.test."""
    import dataclasses
    dossier, people = W.world()
    bare = tuple(D.Person(None, p.key) if p.key and p.key.startswith("marco@") else p for p in people.people)
    assert all(p.name is None for p in bare if p.key and p.key.startswith("marco@"))
    people = dataclasses.replace(people, people=bare)
    checked = check_review(W.review(), dossier.text, people)
    assert _verdict(checked, "to").verdict == C.KEPT and checked.words.draft
    other = check_review(W.review(move={"to": "Priya"}), dossier.text, people)
    assert _verdict(other, "to").reason == C.RECIPIENT_NOT_ON_FILE
