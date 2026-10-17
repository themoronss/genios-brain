"""STEP-13 · a name is on its own lines, as a whole word (crosscheck X09, X16, X35, X50).

    .venv/bin/python -m pytest -q tests/reason/expert/test_verify_names.py

Tree `yc2_w27_s13` M35.C2.L-logic.V1.U12 (`reason/expert/verify`). A fact's names were checked against its lines
PLUS the file's head and every person on the file — so "Priya asked for a short deck" stood on Marco's mail
when Priya was on the file, with a draft to Priya (X09), and a month the head's first-touch date wrote
grounded a month no cited line holds. Names were matched as substrings, so "Avi" stood inside "Altavia"
(X16, `platform/grounding`'s shared rule). An earned word stood as an ordinary word anywhere, so "Block" the
company passed mid-sentence (X50); and `speaks_of_you` never caught the founder's first name (X35).

Now a fact's names are on its OWN lines (the items it cites, its matched quote) and our names — never the
file head. Beside them: the file's counterparty (the file is about them, every item of it is theirs); a
person of the file the cited items name — their whole name, as the file knows it; and, for a fact citing no
mail at all (a reading: an ask, a calculator, a situation, a booking), the one person the file has besides
its counterparty — the only one it could be. Every name matches as a whole word, inside the check
(`platform/grounding` unchanged); an earned word is ordinary only where it opens a sentence; and a card
text naming the founder by first name is noted.
"""
from __future__ import annotations

import dataclasses

import pytest

from genios_engine.contracts import claim_check as C
from genios_engine.reason.expert import dossier as D
from genios_engine.reason.expert.verify import check_review
from tests.reason.expert import check_world as W

pytestmark = pytest.mark.unit

PRIYA = D.Person("Priya Nair", "priya.nair@altavia.test")


def _check(*, ask_words: str | None = None, with_priya: bool = False, head: str = "", **over) -> C.CheckedReview:
    dossier, people = W.world(**({"ask_words": ask_words} if ask_words else {}))
    if with_priya:
        people = dataclasses.replace(people, people=(*people.people, PRIYA))
    if head:
        people = dataclasses.replace(people, head=people.head + "\n" + head)
    return check_review(W.review(**over), dossier.text, people)


def _verdict(checked: C.CheckedReview, line: str) -> C.LineVerdict:
    return next(v for v in checked.verdicts if v.line == line and v.verdict != C.NOTED)


def test_x09_a_person_on_the_file_is_not_named_by_another_person_s_mail():
    """X09's run: Priya is on the file; the fact says SHE asked, citing Marco's mail with Marco's words."""
    checked = _check(with_priya=True,
                     fact1={"claim": "Priya asked for a short deck before setting up a call"},
                     move={"to": "Priya", "what": "Send Priya the short deck and offer two times for a call"})
    assert _verdict(checked, "fact:1") == C.LineVerdict("fact:1", C.DROPPED, C.UNSUPPORTED, "name:Priya")
    assert checked.fate == C.HELD and checked.words.draft is None
    assert _verdict(_check(with_priya=True), "fact:1").verdict == C.KEPT, "Marco's own mail names Marco"


def test_a_month_the_file_head_writes_grounds_no_fact():
    """X09's other run: a first touch in March (the head) made "in March" stand on the introduction of 4 Aug."""
    checked = _check(head="First touch 2026-03-02 10:00 UTC", fact4={"claim": "Introly introduced Marco in March"})
    assert _verdict(checked, "fact:4") == C.LineVerdict("fact:4", C.DROPPED, C.UNSUPPORTED, "name:March")
    assert _verdict(_check(fact4={"claim": "Introly introduced Marco in August"}), "fact:4").verdict == C.KEPT


def test_the_counterparty_is_named_on_any_item_of_their_file():
    checked = _check(fact2={"claim": "Marco Ruiz's ask for the deck waits on us"})
    assert _verdict(checked, "fact:2").verdict == C.KEPT


def test_a_person_the_cited_mail_names_is_named_whole():
    """Marco's mail names "Priya": the file knows her as Priya Nair, so "Priya Nair" stands — "Asha Nair" not."""
    words = "Thanks Arjun — could you send a short deck before we set up a call? I'll loop in Priya, our associate."
    kept = _check(ask_words=words, with_priya=True,
                  fact4={"claim": "Marco will loop in Priya Nair, his associate", "evidence": [W.ASK]})
    assert _verdict(kept, "fact:4").verdict == C.KEPT
    other = _check(ask_words=words, with_priya=True,
                   fact4={"claim": "Marco will loop in Asha Nair, his associate", "evidence": [W.ASK]})
    assert _verdict(other, "fact:4") == C.LineVerdict("fact:4", C.DROPPED, C.UNSUPPORTED, "name:Asha")


def test_a_reading_names_the_one_person_it_could_be():
    """An ask's line names nobody. On a file whose only other person is Introly it can only be Introly's
    introduction; with Priya on the file too, the line cannot say which — the name is refused."""
    claim = {"claim": "The ask Introly's introduction led to waits on us"}
    assert _verdict(_check(fact2=claim), "fact:2").verdict == C.KEPT
    assert _verdict(_check(with_priya=True, fact2=claim), "fact:2") == C.LineVerdict(
        "fact:2", C.DROPPED, C.UNSUPPORTED, "name:Introly")


def test_a_mail_names_only_the_people_it_names_even_the_one_it_could_be():
    """Introly is the file's one other person — but the fact cites MARCO's mail, which does not name
    Introly: it says who wrote and what, and Introly is in neither (the introduction is another mail)."""
    checked = _check(fact1={"claim": "Marco, whom Introly introduced, asked for a short deck before setting up "
                                     "a call"})
    assert _verdict(checked, "fact:1") == C.LineVerdict("fact:1", C.DROPPED, C.UNSUPPORTED, "name:Introly")


def test_a_booking_is_a_reading_and_names_the_one_person_it_could_be():
    from datetime import datetime, timezone
    dossier, people = W.world(meeting_at=datetime(2026, 8, 25, 15, 0, tzinfo=timezone.utc))
    review = W.review(fact4={"claim": "The call Introly made possible is booked for 25 Aug",
                             "evidence": [W.MEETING]})
    assert _verdict(check_review(review, dossier.text, people), "fact:4").verdict == C.KEPT


def test_we_are_never_the_other_person_a_reading_could_name():
    """Our own address among the file's people does not make Introly one of two."""
    dossier, people = W.world()
    people = dataclasses.replace(people, people=(*people.people, D.Person("Arjun Rao", "arjun@nimbuslabs.test")))
    review = W.review(fact2={"claim": "The ask Introly's introduction led to waits on us"})
    assert _verdict(check_review(review, dossier.text, people), "fact:2").verdict == C.KEPT


def test_a_name_inside_another_word_is_no_name():
    """X16's run: "Avi" stood inside "Altavia" — in the headline, while the same check refused Avi as a
    recipient."""
    checked = _check(move={"what": "Send Avi the short deck and offer two times for a call", "to": None},
                     draft=None)
    assert _verdict(checked, "move") == C.LineVerdict("move", C.DROPPED, C.UNSUPPORTED, "name:Avi")
    assert checked.fate == C.HELD
    fact = _check(fact1={"claim": "Avi asked for a short deck before setting up a call"})
    assert _verdict(fact, "fact:1") == C.LineVerdict("fact:1", C.DROPPED, C.UNSUPPORTED, "name:Avi")


@pytest.mark.parametrize("key, text, kept", [
    ("ira@larkspurvc.test", "Send Marco the short deck and copy Larkspur on it", True),
    ("ira@larkspurvc.test", "Send Marco the short deck and copy Lark on it", False),
    ("nandini@vertexangels.test", "Send Marco the short deck and copy Vertex Angels on it", True),
    ("nandini@vertexangels.test", "Send Marco the short deck and copy Angels on it", False),
    ("events@bluebayhub.test", "Send Marco the short deck before the Bluebay event", True),
])
def test_a_file_known_by_its_domain_is_named_by_how_the_domain_begins(key, text, kept):
    """The golden set's files are often known only by an address: "Larkspur" for `larkspurvc.test`,
    "Vertex Angels" for `vertexangels.test`. A name that begins the domain's label — the kind of firm
    after it, at most `LABEL_TAIL` letters — is its name; a piece of the middle is not."""
    dossier, people = W.world()
    people = dataclasses.replace(people, people=(*people.people, D.Person(key, key)))
    checked = check_review(W.review(move={"what": text}), dossier.text, people)
    assert (_verdict(checked, "move").verdict != C.DROPPED) is kept, _verdict(checked, "move")


@pytest.mark.parametrize("claim", ["Marco of Altavia asked for a short deck before setting up a call",
                                   "Marco, at Altavia's fund, asked for a short deck before setting up a call",
                                   "Marco Ruiz-style, he asked for a short deck before setting up a call"])
def test_a_whole_name_with_its_marks_still_stands(claim):
    checked = _check(fact1={"claim": claim, "evidence": [W.ASK, W.INTRO]})
    assert _verdict(checked, "fact:1").verdict == C.KEPT, checked.verdicts


@pytest.mark.parametrize("text, kept", [
    ("Block an hour to send Marco the short deck and offer two times for a call", True),   # opens the move
    ("Send Marco the short deck. Block an hour for the call", True),                       # opens a sentence
    ("Send Marco the short deck and copy Block on it", False),                             # X50: a company
])
def test_an_earned_word_is_ordinary_only_where_it_opens_a_sentence(text, kept):
    checked = _check(move={"what": text})
    assert (_verdict(checked, "move").verdict != C.DROPPED) is kept, _verdict(checked, "move")


def test_a_card_naming_the_founder_by_first_name_is_noted():
    """X35: 26 of the 61 third-person texts STEP-13 §8.1 counted say "Arjun"."""
    checked = _check(done_when="Marco has the deck from Arjun, and a call is booked")
    assert any(v.line == "done_when" and v.verdict == C.NOTED and v.reason == C.SPEAKS_OF_YOU and v.detail == "Arjun"
               for v in checked.verdicts)
    assert checked.stands("done_when")
    assert not any(v.reason == C.SPEAKS_OF_YOU for v in _check(draft="Hi Marco, the deck is attached. Arjun").verdicts), \
        "the draft is the founder's own: signing it is no third person"


# ── STEP-13b M37.C4.L-logic.V8.U02 · Haiku's pass read ordinary words as invented names ────────

@pytest.mark.parametrize("word, text", [
    ("two", "Two weeks is long, so send Marco the short deck"),
    ("done", "Done means Marco has the deck"),
    ("by", "By the end of the week send Marco the short deck"),
    ("silence", "Silence since August: send Marco the short deck"),
    ("log", "Log the call and send Marco the short deck"),
    # golden F13, F42 ("About half the companies reviewed at a partners' meeting go on to diligence") and F17
    # ("Interview rounds typically run two to four weeks"): authored patterns citing a playbook line, now held to its
    # words by the card validator's rule (V7.U01) — an opening ordinary word, read as a name.
    ("about", "About half the companies Marco sees go on, so send the short deck"),
    ("interview", "Interview rounds run long, so send Marco the short deck")])
def test_a_word_haikus_pass_dropped_is_ordinary_where_it_opens_a_sentence(word, text):
    from genios_engine.reason.expert.verify import EARNED
    assert word in EARNED
    assert _verdict(_check(move={"what": text}), "move").verdict != C.DROPPED


@pytest.mark.parametrize("word", ["Two", "Done", "Silence", "Log"])
def test_the_same_word_mid_sentence_is_still_a_name_of_the_file(word):
    """A company called Log, Two or Done is a name: only an opening word is read as a word."""
    checked = _check(move={"what": f"Send Marco the short deck and copy {word} on it"})
    assert _verdict(checked, "move").reason == C.UNSUPPORTED and _verdict(checked, "move").detail == f"name:{word}"


@pytest.mark.parametrize("text", ["Send Marco the API short deck", "Send Marco the short deck by noon UTC",
                                  "Send Marco the short deck; the API docs follow"])
def test_an_acronym_of_the_trade_is_a_word_anywhere(text):
    from genios_engine.reason.expert.verify import ACRONYMS
    assert {"api", "utc"} <= ACRONYMS
    assert _verdict(_check(move={"what": text}), "move").verdict != C.DROPPED


def test_a_name_that_looks_like_an_acronym_still_drops_when_the_file_does_not_hold_it():
    checked = _check(move={"what": "Send Marco the short deck and copy ACME on it"})
    assert _verdict(checked, "move").reason == C.UNSUPPORTED
