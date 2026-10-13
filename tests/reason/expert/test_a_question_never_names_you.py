"""STEP-13 · a question to you never names you, held or find-out (second crosscheck F3).

    .venv/bin/python -m pytest -q tests/reason/expert/test_a_question_never_names_you.py

Tree `yc2_w27_s13` M36.C2.L-logic.V2.U19 — `platform/self_identity.speaks_of_us` and `to_you`, `reason/expert/verify`,
`reason/expert/asks`. "A question that names us is never asked" held only for find-out candidates with multi-word
names: `names_us` is a SUBJECT matcher — a one-word company name must be the whole subject, a first name claims
nothing — so "…whether GeniOS is incubated…" and "…whether Rohit went…" got through, golden F54 asked "Can you
tell us whether Arjun went to the event and spoke with Rhea?", and a HELD question skipped the filter altogether.

Now questions are read as PROSE: the company's name whole-word at any length, a first or full name, our addresses
and domains. A question that names us is asked in the second person ("whether you went…") where it can be, else
our closed question — and the hit is noted `speaks_of_you`, for the live pass to count.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from genios_engine.contracts import claim_check as C
from genios_engine.platform.self_identity import SelfIdentity, speaks_of_us, to_you
from genios_engine.reason.expert import asks
from genios_engine.reason.expert.verify import check_review
from tests.reason.expert import check_world as W

pytestmark = pytest.mark.unit

GENIOS = SelfIdentity.of(addresses=("rohit@thegenios.com",), domains=("thegenios.com",))
OURS = ("GeniOS", "Rohit Swerashi")


@pytest.mark.parametrize("text, hit", [
    ("Can you tell us whether GeniOS is incubated on the campus?", "GeniOS"),
    ("Can you tell us whether Rohit went to the event?", "Rohit"),
    ("Did Rohit Swerashi reply to Maria?", "Rohit Swerashi"),
    ("Did you reply from rohit@thegenios.com?", "rohit@thegenios.com"),
    ("Is thegenios.com on the list?", "thegenios.com"),
    ("Does Altavia lead seed rounds?", None),
    ("Is the genios of the idea new?", None),                          # a word, not the name: no capital
])
def test_f3_a_question_is_read_as_prose(text, hit):
    assert speaks_of_us(text, GENIOS, OURS) == hit


def test_an_article_or_a_title_is_no_first_name():
    assert speaks_of_us("The board met on Friday, did it not?", GENIOS, ("The Genios Company", "Dr Rohit Swerashi")) \
        is None
    assert speaks_of_us("Did Rohit meet them?", GENIOS, ("Dr Rohit Swerashi",)) == "Rohit"


@pytest.mark.parametrize("text, said", [
    ("Can you tell us whether Arjun went to the event and spoke with Rhea?",
     "Can you tell us whether you went to the event and spoke with Rhea?"),
    ("Can you tell us whether Nimbus Labs is incubated on the campus?",
     "Can you tell us whether you are incubated on the campus?"),
    ("Did Marco get Arjun's deck?", "Did Marco get your deck?"),
    ("Arjun was at the event, was he not?", "You were at the event, was he not?"),
    ("Does Arjun want a call?", "Do you want a call?"),
    ("Has Nimbus Labs filed the form?", "Have you filed the form?"),
])
def test_to_you_says_it_in_the_second_person(text, said):
    assert to_you(text, W.US, W.OUR_NAMES) == said


@pytest.mark.parametrize("text", ["Can you tell us whether Arjun wants a call?",
                                  "Is nimbuslabs.test on the investor's list?"])
def test_what_cannot_be_said_to_you_is_not_rephrased(text):
    """A verb left in the third person ("you wants"), a domain of ours: None — the closed question instead."""
    assert to_you(text, W.US, W.OUR_NAMES) is None


def test_an_address_of_ours_is_you():
    assert to_you("Whom should “Send the short deck to arjun@nimbuslabs.test first” go to?", W.US, W.OUR_NAMES) \
        == "Whom should “Send the short deck to you first” go to?"


# ── find-out: the golden F54 shape ─────────────────────────────────────────────────────────────────────────

def _find_out(unknown: str, what: str = "Ask Marco whether Altavia leads seed rounds"):
    dossier, people = W.world()
    review = W.review(mode="find_out", draft=None, move={"what": what, "to": None, "answers": None},
                      unknowns=[{"question": unknown, "relevance": "decides the ask"}],
                      fact4={"claim": "Introly introduced Marco to Arjun on 4 Aug"})   # a kept fact naming Arjun
    checked = check_review(review, dossier.text, people, evidence_ids=dossier.catalogue.evidence_ids)
    return SimpleNamespace(review=review, checked=checked, fingerprint="ffp-x")


def _ours_and_you():
    return (lambda t: speaks_of_us(t, W.US, W.OUR_NAMES)), (lambda t: to_you(t, W.US, W.OUR_NAMES))


def test_f3_a_find_out_question_naming_the_founder_is_asked_to_you():
    row = _find_out("Did Arjun reply to Marco after the intro?")
    ours, you = _ours_and_you()
    assert asks.question_words(row, ours=ours, you=you)[0] == "Did you reply to Marco after the intro?"
    assert C.LineVerdict("question", C.NOTED, C.SPEAKS_OF_YOU, "Arjun") in row.checked.verdicts


def test_f3_one_that_cannot_be_said_to_you_is_passed_over():
    row = _find_out("Whether Arjun wants a call with Marco.")
    ours, you = _ours_and_you()
    question = asks.question_words(row, ours=ours, you=you)[0]
    assert "wants a call" not in question and speaks_of_us(question, W.US, W.OUR_NAMES) is None


# ── held: the filter now holds there too ─────────────────────────────────────────────────────────────────────

def test_f3_a_held_question_naming_us_is_said_to_you_and_noted():
    """Held "addressed to you", its question quoted the move: "Whom should “Send Arjun Rao the short deck…” go to?"."""
    dossier, people = W.world()
    checked = check_review(W.review(move={"what": "Send Arjun Rao the short deck to review first", "to": None},
                                    draft=None), dossier.text, people)
    assert checked.fate == C.HELD
    assert checked.question == "Whom should “Send you the short deck to review first” go to? It is addressed to you."
    assert C.LineVerdict("question", C.NOTED, C.SPEAKS_OF_YOU, "Arjun Rao") in checked.verdicts


def test_your_own_quoted_words_are_never_rephrased():
    """B2's confirmation quotes your answer; naming yourself there is yours to do — only our words are read."""
    from genios_engine.reason.expert import verify as V
    question = "You said: “Yes, Arjun sent it”. Should we go ahead with “Send Marco the deck”?"
    _, people = W.world()
    assert V._to_you_beside_yours(question, people) == question
    assert speaks_of_us(V._YOUR_QUOTED.sub(" ", question), W.US, W.OUR_NAMES) is None


def test_a_card_text_naming_a_one_word_company_is_noted():
    """The note, too, reads prose: a one-word company name — "Nimbus", when that is all the company is called —
    was no subject `names_us` would claim, and no first name either."""
    from genios_engine.reason.expert import dossier as D
    p = W.parts()
    dossier, people = D.build_dossier(p), D.people_of(p, us=W.US, our_names=("Nimbus", "Arjun Rao"))
    checked = check_review(W.review(done_when="Nimbus has sent Marco the deck and a call is booked"),
                           dossier.text, people)
    assert C.LineVerdict("done_when", C.NOTED, C.SPEAKS_OF_YOU, "Nimbus") in checked.verdicts
