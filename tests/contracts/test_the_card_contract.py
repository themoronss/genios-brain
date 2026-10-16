"""STEP-14 · the card contract — nothing false reaches the dashboard, whatever wrote the card.

    .venv/bin/python -m pytest -q tests/contracts/test_the_card_contract.py

Tree `yc2_w27_s14` M43.C4.L-contract.V0.U01 (`contracts/card_contract`; STEP-14 §3.5, §8.4 item 6, s14-F10, s14-F11).
Production showed *"nsrcel — a dated payment obligation is open"* (any dated commitment became money), *"Which is
right? Maria Exconde: party.role"* (a field's name on a card), *"8 data points, 1 unreadable"*. The contract is
pure, for every card whatever wrote it — the pipeline's decision and question cards and P4's team and verify cards —
and refuses, with the rule and what it found, a card that:

  us            names us as its subject, or sends its draft to us;
  internal      shows an internal field name (`party.role`) or an unfilled slot (`{stage}`);
  money         claims money with no money in its evidence (*"a dated payment obligation"*);
  quote         quotes words that are not in its quotes;
  number        says a number or a date its own corpus does not hold.
"""
from __future__ import annotations

import pytest

from genios_engine.contracts import card_contract as K
from genios_engine.platform.self_identity import SelfIdentity

pytestmark = pytest.mark.unit

US = SelfIdentity.of(addresses=["arjun@nimbuslabs.test"], domains=["nimbuslabs.test"])
OUR_NAMES = ("Arjun Rao", "Nimbus Labs")
CARD = K.CardText(headline="Reply to Maria Exconde", situation="Maria replied on 11 Aug; your reply is owed",
                  subject="Maria Exconde", recipient="maria@alyst.test",
                  draft="Hi Maria — thanks for the note on the 11th.",
                  why_now="Maria Exconde wrote on 11 Aug", what_remains=("Maria asked a question — waiting on you",))
GROUND = dict(quotes=("Could you send the deck before Friday?",),
              corpus=("Maria replied 2026-08-11", "maria@alyst.test", "Maria Exconde", "Friday"),
              money_evidence=False)


def _check(card=CARD, **over):
    return K.check(card, us=US, our_names=OUR_NAMES, **{**GROUND, **over})


def _with(**over):
    return K.CardText(**{**CARD.as_mapping(), **over})


def test_a_true_card_passes():
    assert _check() == ()


@pytest.mark.parametrize("over, found", [
    ({"subject": "Arjun Rao"}, "subject: Arjun Rao"),
    ({"subject": "nimbuslabs.test"}, "subject: nimbuslabs.test"),
    ({"recipient": "arjun@nimbuslabs.test"}, "recipient: arjun@nimbuslabs.test"),
    ({"recipient": "team@nimbuslabs.test"}, "recipient: team@nimbuslabs.test"),
])
def test_a_card_about_us_or_to_us_is_refused(over, found):
    [refusal] = _check(_with(**over))
    assert (refusal.rule, refusal.found) == (K.US, found)


@pytest.mark.parametrize("field, text, found", [
    ("situation", "Which is right? Maria Exconde: party.role", "party.role"),
    ("headline", "Set a next date with Maria at {stage}", "{stage}"),
    ("why_now", "commitment.action is open", "commitment.action"),
    ("draft", "Hi Maria, per derived.momentum we should talk", "derived.momentum"),
    ("what_remains", ("deal.stage — waiting on you",), "deal.stage"),
])
def test_an_internal_field_name_or_an_unfilled_slot_is_refused(field, text, found):
    [refusal] = _check(_with(**{field: text}))
    assert (refusal.rule, refusal.found) == (K.INTERNAL, found)


def test_an_address_or_a_domain_is_no_field_name():
    assert _check(_with(situation="Maria (maria@alyst.test, alyst.test) replied on 11 Aug")) == ()
    assert _check(_with(situation="Maria (desk@deal.test, a.deal.test) replied on 11 Aug")) == (), \
        "a namespace word inside an address or a domain is no field"


@pytest.mark.parametrize("text", ["nsrcel — a dated payment obligation is open", "₹50,000 is owed on 11 Aug",
                                  "The invoice is due on 11 Aug", "$40k due on 11 Aug"])
def test_money_with_no_money_in_the_evidence_is_refused(text):
    refusals = _check(_with(situation=text), corpus=GROUND["corpus"] + ("50,000", "40k"))
    assert [r.rule for r in refusals] == [K.MONEY]
    assert _check(_with(situation=text), corpus=GROUND["corpus"] + ("50,000", "40k"), money_evidence=True) == ()


def test_a_quote_not_in_its_quotes_is_refused_and_one_in_them_passes():
    said = _with(situation="Maria asked “Could you send the deck before Friday?”")
    assert _check(said) == ()
    invented = _with(situation="Maria asked “Could you send the pricing sheet?”")
    [refusal] = _check(invented)
    assert (refusal.rule, refusal.found) == (K.QUOTE, "Could you send the pricing sheet?")
    titled = _with(why_now="Your meeting “Partner meeting — Meridian” is in 2 days")
    assert [r.rule for r in _check(titled, corpus=GROUND["corpus"] + ("Partner meeting — Meridian", "2"))] == [], \
        "a meeting's title, in its corpus, may be quoted"


@pytest.mark.parametrize("text, found", [("Maria replied on 12 Aug", "12"), ("8 data points, 1 unreadable", "8")])
def test_a_number_its_corpus_does_not_hold_is_refused(text, found):
    refusals = _check(_with(situation=text))
    assert [(r.rule, r.found) for r in refusals][:1] == [(K.NUMBER, found)]


def test_every_rule_is_named_once_and_every_refusal_reads_back():
    assert K.RULES == (K.US, K.INTERNAL, K.MONEY, K.QUOTE, K.NUMBER)
    refusals = _check(_with(subject="Arjun Rao", situation="party.role is owed $5 on 12 Aug"))
    assert [r.rule for r in refusals] == [K.US, K.INTERNAL, K.MONEY, K.NUMBER], "in the order of the rules"
    assert all(K.Refusal.from_mapping(r.as_mapping()) == r for r in refusals)
    with pytest.raises(ValueError):
        K.Refusal(rule="rude", found="x")


def test_a_card_text_reads_back_as_stored():
    assert K.CardText.from_mapping(CARD.as_mapping()) == CARD
