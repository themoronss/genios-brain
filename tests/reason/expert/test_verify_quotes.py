"""STEP-13 · a quote grounds nothing until it is matched (crosscheck X01, X17, X18).

    .venv/bin/python -m pytest -q tests/reason/expert/test_verify_quotes.py

Tree `yc2_w27_s13` M35.C2.L-logic.V1.U09 (`reason/expert/verify`). A fact's quote was read as the mail's words
before anyone matched it: only a DECISIVE fact on a mail whose words are shown had its quote matched, and
every other quote went straight into the fact's own lines, the headline and situation corpus and the card's
quotes — so a quote on an ask, a calculator, a situation or an older touch (whose words nobody is shown)
grounded whatever it said, shown to the founder as the mail's words (X01). Now every given quote is
matched against the worded lines of the items its fact cites; one that is not there — or on an item whose
words are not shown — is dropped `misquoted` (on its own `quote:<n>` line when the fact needs no quote)
and kept out of everything. Matching folds hyphens and thousands commas (X18); a quote of fewer than two
words that carry anything is no quote (X17: "a call" cannot prove "he does not want a call"); and a
decisive fact's numbers come from its quote, its mail's head or the calculators it cites — never from
another sentence of the mail its quote does not hold.
"""
from __future__ import annotations

import pytest

from genios_engine.contracts import claim_check as C
from genios_engine.reason.expert.verify import check_review, quoted_in
from tests.reason.expert import check_world as W

pytestmark = pytest.mark.unit

SEQUOIA = "I commit 2,500,000 from Sequoia Capital"
CONFIRM = {"what": "Confirm the 2,500,000 from Sequoia Capital with Marco", "rests_on": ["fact:1", "fact:2"]}


def _check(world_kw=None, **over) -> C.CheckedReview:
    dossier, people = W.world(**(world_kw or {}))
    return check_review(W.review(**over), dossier.text, people)


def _verdict(checked: C.CheckedReview, line: str) -> C.LineVerdict | None:
    return next((v for v in checked.verdicts if v.line == line and v.verdict != C.NOTED), None)


def test_a_quote_on_an_ask_grounds_nothing():
    """X01's first run: fact 2 cites `loop:ask_deck` (an ask prints no mail's words) and 'quotes' the
    5 crore term sheet; the move then names it. The quote is dropped, and the move holds."""
    checked = _check(fact2={"quote": "the 5 crore term sheet"},
                     move={"what": "Send Marco the 5 crore term sheet"})
    assert _verdict(checked, "quote:2") == C.LineVerdict("quote:2", C.DROPPED, C.MISQUOTED,
                                                         "the 5 crore term sheet")
    assert checked.stands("fact:2"), "the fact stands on its own line, without the quote"
    assert checked.fate == C.HELD and checked.words.headline is None
    assert "the 5 crore term sheet" not in checked.words.quotes


@pytest.mark.parametrize("cites", [W.ASK_DECK, "num:days_quiet", "sit:sit_marco", "evt_old_0"])
def test_a_quote_on_an_item_whose_words_are_not_shown_grounds_nothing(cites):
    """X01's second run: a decisive fact on a calculator, an ask, a situation or an older touch (past
    `TOUCHES_WHOLE`, listed without its words) 'quotes' a commitment nobody was shown."""
    checked = _check({"older": 6}, fact2={"claim": "Marco committed 2,500,000 from Sequoia Capital",
                                          "evidence": [cites], "quote": SEQUOIA}, move=CONFIRM)
    assert _verdict(checked, "quote:2") == C.LineVerdict("quote:2", C.DROPPED, C.MISQUOTED, SEQUOIA)
    assert not checked.stands("fact:2"), "without the quote, Sequoia is on none of its lines"
    assert checked.fate == C.HELD and checked.words.headline is None
    assert SEQUOIA not in checked.words.quotes


def test_the_same_quote_on_the_mail_that_says_it_stands():
    checked = _check({"ask_words": f"Thanks Arjun — {SEQUOIA}, if the round closes this month."},
                     fact2={"claim": "Marco committed 2,500,000 from Sequoia Capital", "evidence": [W.ASK],
                            "quote": SEQUOIA},
                     fact1={"claim": "Marco wrote to us on 11 Aug", "quote": "if the round closes this month"},
                     move=CONFIRM, draft=None)
    assert checked.fate == C.SHOWN, checked.verdicts
    assert checked.words.headline == CONFIRM["what"] and SEQUOIA in checked.words.quotes


def test_a_non_decisive_fact_s_unmatched_quote_grounds_no_situation():
    """X01, sharper: fact 4 needs no quote (the move does not rest on it), but the one it gives is not in
    the introduction's words — it is dropped, and the situation it alone grounded is withheld."""
    tiger = "Marco co-leads seed rounds with Tiger Global"
    checked = _check(fact4={"quote": tiger}, frames={"primary": tiger, "rivals": ["a pass"]})
    assert _verdict(checked, "quote:4") == C.LineVerdict("quote:4", C.DROPPED, C.MISQUOTED, tiger)
    assert checked.stands("fact:4"), "it stands on the introduction's own words"
    assert checked.words.situation is None and _verdict(checked, "situation").reason == C.UNSUPPORTED
    assert checked.fate == C.SHOWN and checked.words.headline


def test_two_generic_words_prove_nothing():
    """X17: "a call" is in Marco's mail — which asks FOR a call. It cannot prove he does not want one."""
    checked = _check(fact1={"claim": "Marco said he does not want a call", "quote": "a call"})
    assert _verdict(checked, "fact:1") == C.LineVerdict("fact:1", C.DROPPED, C.MISQUOTED, "a call")
    assert checked.fate == C.HELD


@pytest.mark.parametrize("ask_words, quote", [
    ("Could you send the follow-up deck by e-mail? We have 1,400 users.", "send the follow up deck by email"),
    ("Could you send the follow up deck by email? We have 1400 users.", "send the follow-up deck by e-mail"),
    ("Could you send the follow-up deck by e-mail? We have 1,400 users.", "We have 1400 users"),
    ("Could you send the follow up deck by email? We have 1400 users.", "We have 1,400 users"),
])
def test_a_faithful_quote_with_a_hyphen_or_a_grouping_comma_is_matched(ask_words, quote):
    """X18: "follow-up" is "follow up", "e-mail" is "email", "1,400" is "1400" — a faithful quote stands."""
    checked = _check({"ask_words": ask_words}, fact1={"quote": quote,
                                                      "claim": "Marco asked for the follow-up deck"})
    assert _verdict(checked, "fact:1").verdict == C.KEPT, checked.verdicts
    assert checked.fate == C.SHOWN and quote in checked.words.quotes


def test_a_decisive_fact_s_number_comes_from_its_quote_not_another_sentence_of_the_mail():
    """The quote carries the claim's numbers: the mail says "5 deals" elsewhere, the quote does not."""
    words = "Thanks Arjun — could you send a short deck before we set up a call? We close 5 deals a month."
    claim = "Marco asked for a short deck before setting up a call, as he closes 5 deals a month"
    checked = _check({"ask_words": words}, fact1={"claim": claim})
    assert _verdict(checked, "fact:1") == C.LineVerdict("fact:1", C.DROPPED, C.WRONG_NUMBER, "number:5")
    carried = _check({"ask_words": words}, fact1={"claim": claim, "quote": "We close 5 deals a month"})
    assert _verdict(carried, "fact:1").verdict == C.KEPT
    dated = _check({"ask_words": words}, fact1={"claim": "Marco asked on 11 Aug for a short deck before "
                                                         "setting up a call"})
    assert _verdict(dated, "fact:1").verdict == C.KEPT, "the mail's own date is on its head"


def test_a_decisive_fact_s_calculator_still_corrects_its_number():
    checked = _check(fact1={"claim": "Marco asked for a short deck before setting up a call; he answered in "
                                     "12 days", "evidence": [W.ASK, W.REPLY_TIME]})
    assert _verdict(checked, "fact:1") == C.LineVerdict(
        "fact:1", C.CORRECTED, C.BY_CALCULATOR, f"number:12 -> 6 ({W.REPLY_TIME})")


def test_a_decisive_fact_s_number_on_the_calculator_it_cites_stands_as_written():
    checked = _check(fact1={"claim": "Marco asked for a short deck before setting up a call; he answered in "
                                     "6 days", "evidence": [W.ASK, W.REPLY_TIME]})
    assert _verdict(checked, "fact:1").verdict == C.KEPT


def test_an_unmatched_quote_never_reaches_the_card_beside_a_shown_move():
    """Fact 2 is decisive and cites the ask (no words): its claim stands on the ask's line, the move is
    shown — and the card's quotes are the matched ones only."""
    checked = _check(fact2={"quote": "the deck waits on us now"})
    assert checked.fate == C.SHOWN and _verdict(checked, "quote:2").reason == C.MISQUOTED
    assert checked.words.quotes == (W.ANSWER["facts"][0]["quote"],)


def test_the_faithful_review_keeps_its_matched_quote():
    checked = _check()
    assert checked.words.quotes == (W.ANSWER["facts"][0]["quote"],)
    assert not any(v.line.startswith("quote:") for v in checked.verdicts)


@pytest.mark.parametrize("quote, words, held", [
    ("please follow up soon", ["please follow-up soon"], True),
    ("please follow-up soon", ["please follow up soon"], True),
    ("send it by email", ["send it by e-mail please"], True),
    ("send it by e-mail", ["send it by email please"], True),
    ("we have 1400 users", ["We have 1,400 users"], True),
    ("raising 12,50,000 now", ["raising 1250000 now"], True),           # Indian grouping, one number
    ("follow the deck", ["follow-up the deck"], False),                 # "follow" is no "follow-up"…
    ("please follow", ["please follow-up soon"], True),                 # …but a hyphen is a boundary
    ("a call", ["could we set up a call"], False),                      # one word that carries anything
    ("the deck", ["send the deck"], False),
    ("send the deck", ["could you send the deck"], True),
    ("send a short", ["could you send a shorter deck"], False),         # whole words, still
    ("end a short deck", ["could you send a short deck"], False),
])
def test_how_a_quote_is_matched(quote, words, held):
    assert quoted_in(quote, words) is held


# ── M35.C2.L-logic.V1.U09 (fix) · the second crosscheck G5: the bound, declared and pinned ──────────────────────

@pytest.mark.parametrize("claim, quote", [
    ("Marco refuses to set up a call", "set up a call"),
    ("Marco said he does not want a short deck", "short deck"),
    ("Marco does not read anything within a week", "read everything within a week")])
def test_g5_the_declared_bound_a_matched_quote_is_not_read_for_its_meaning(claim, quote):
    """⛔ DECLARED, NOT FIXED (verify's docstring, 1; tree U09): a claim inverting its matched quote stands — a
    lexical polarity rule would drop 13 of the golden set's 130 authored quoted facts, every one faithful. The
    quote reaches the card beside the move (`CardWords.quotes`), so the founder reads what it rests on."""
    dossier, people = W.world()
    checked = check_review(W.review(fact1={"claim": claim, "quote": quote}), dossier.text, people)
    assert next(v for v in checked.verdicts if v.line == "fact:1").verdict == C.KEPT
    assert quote in checked.words.quotes, "what it rests on is on the card, for the founder to read"
