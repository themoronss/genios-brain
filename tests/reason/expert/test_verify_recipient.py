"""STEP-13 · the recipient is checked with or without a draft; the draft stands on the move's ground (X20, X23).

    .venv/bin/python -m pytest -q tests/reason/expert/test_verify_recipient.py

Tree `yc2_w27_s13` M35.C2.L-logic.V1.U14 (`reason/expert/verify`). Whom a move goes to was checked only inside
`if review.draft:` — so "Send Introly the short deck to pass on to Marco" with no draft was shown as it was
(X20), though §3.3 says never to us and never to a connector standing in for the person it introduced. And
the draft was grounded on the WHOLE dossier: a brief line about another investor and the what-if section's
"12" let "Sequoia Capital is leading the round and 12 funds have committed" through (X23).

Now the move's recipient is its `to` — or, with none, the first person its headline names — and it is
checked whether or not there is a draft: to us, the move is held; to the connector on a file that is not
the connector's own, the review's alternative becomes the move, or the move is held. The draft stands on
what the move stands on — its facts' items and quotes, the file's head and people — and on what the brief
says of US (the company, its goals: the draft is the founder's own words about their company), never on the
rest of the dossier.
"""
from __future__ import annotations

import pytest

from genios_engine.contracts import claim_check as C
from genios_engine.reason.expert.verify import check_review
from tests.reason.expert import check_world as W

pytestmark = pytest.mark.unit

VIA_INTROLY = "Send Introly the short deck to pass on to Marco"


def _check(world_kw=None, **over) -> C.CheckedReview:
    dossier, people = W.world(**(world_kw or {}))
    return check_review(W.review(**over), dossier.text, people)


def _verdict(checked: C.CheckedReview, line: str) -> C.LineVerdict | None:
    return next((v for v in checked.verdicts if v.line == line and v.verdict != C.NOTED), None)


def test_x20_a_move_to_the_connector_with_no_draft_becomes_the_alternative():
    checked = _check(move={"what": VIA_INTROLY, "to": None}, draft=None)
    assert _verdict(checked, "to") == C.LineVerdict("to", C.DROPPED, C.RECIPIENT_IS_CONNECTOR, "Introly")
    assert checked.fate == C.SHOWN and checked.words.headline == W.ANSWER["alternative"]


def test_a_move_to_the_connector_with_no_draft_and_no_alternative_is_held():
    checked = _check(move={"what": VIA_INTROLY, "to": None}, draft=None, alternative="")
    assert checked.fate == C.HELD and "Introly" in checked.question


def test_a_named_to_is_checked_with_no_draft_too():
    checked = _check(move={"to": "Introly"}, draft=None)
    assert _verdict(checked, "to").reason == C.RECIPIENT_IS_CONNECTOR
    assert checked.words.headline == W.ANSWER["alternative"]


@pytest.mark.parametrize("move", [
    {"what": "Send Arjun Rao the short deck to review first", "to": None},
    {"what": "Send the short deck to arjun@nimbuslabs.test first", "to": None},
    {"to": "Nimbus Labs"},
])
def test_a_move_to_us_with_no_draft_is_held(move):
    checked = _check(move=move, draft=None)
    assert _verdict(checked, "to").reason == C.RECIPIENT_IS_US
    assert checked.fate == C.HELD and "addressed to you" in checked.question


def test_a_move_naming_the_counterparty_first_is_theirs():
    """The faithful move, no draft: Marco is the first person it names — nothing to refuse."""
    checked = _check(draft=None, move={"to": None, "what": "Send Marco the short deck, as Introly suggested"})
    assert _verdict(checked, "to") is None and checked.fate == C.SHOWN
    assert checked.words.headline == "Send Marco the short deck, as Introly suggested"


def test_on_the_connector_s_own_file_a_move_to_it_stands():
    checked = _check({"kind": "connector"}, move={"what": "Thank Introly for the introduction", "to": None},
                     draft=None)
    assert _verdict(checked, "to") is None and checked.fate == C.SHOWN


def test_x23_the_draft_stands_on_the_move_s_ground_not_the_whole_dossier():
    """X23's run: the brief's line about Altavia (another line of work in motion, not ours) and the
    what-if section's numbers are no ground of the move's — the draft is withheld."""
    for draft in ("Hi Marco, Altavia Partners is leading the round. Arjun",
                  "Hi Marco, the short deck is attached — 78 more days before the file is dormant. Arjun"):
        checked = _check(fact4={"claim": "Introly wrote to us on 4 Aug", "quote": None}, draft=draft,
                         move={"rests_on": ["fact:1", "fact:2"]})
        assert checked.words.draft is None, draft
        assert _verdict(checked, "draft").reason in (C.UNSUPPORTED, C.WRONG_NUMBER)
        assert checked.fate == C.SHOWN and checked.words.headline


def test_the_draft_may_say_what_the_brief_says_of_us():
    """"Nimbus Labs" and the founder sign the draft; what the company IS comes from the brief's own lines."""
    checked = _check(draft="Hi Marco, Nimbus Labs is raising; the short deck is attached. Arjun Rao")
    assert _verdict(checked, "draft").verdict == C.KEPT and checked.words.draft


def test_the_brief_s_own_lines_ground_the_draft():
    """What the company IS — a brief line of its own section — is the founder's to say in their draft; the
    same words are on no line the move stands on."""
    dossier, people = W.world()
    text = dossier.text.replace("Company: Nimbus Labs, founder Arjun Rao",
                                "Company: Nimbus Labs, founder Arjun Rao\n- An AI chief of staff for founders")
    draft = "Hi Marco, we are building an AI chief of staff; the short deck is attached. Arjun"
    checked = check_review(W.review(draft=draft), text, people)
    assert _verdict(checked, "draft").verdict == C.KEPT and checked.words.draft == draft
    assert _verdict(check_review(W.review(draft=draft), dossier.text, people), "draft") == C.LineVerdict(
        "draft", C.DROPPED, C.UNSUPPORTED, "name:AI"), "without that line, AI is on none of its lines"


def test_a_name_is_a_capitalised_word():
    """A connector whose name is an ordinary word ("intro") is not named by "after the intro"."""
    checked = _check({"introduced_by": "hello@intro.test"}, draft=None,
                     move={"to": None, "what": "After the intro, send Marco the short deck"})
    assert _verdict(checked, "to") is None and checked.fate == C.SHOWN
