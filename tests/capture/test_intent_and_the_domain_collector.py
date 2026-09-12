"""L1 · what kind of exchange this is, and where a message goes when no pattern claims it.

    pytest tests/capture/test_intent_and_the_domain_collector.py -q

TWO MEASUREMENTS, BOTH TAKEN READ-ONLY ON THE PILOT ON 2026-09-11.

**815 of 889 captured events carried no domain at all.** Four keyword tables — `fundraising`,
`sales`, `support`, `admin` — recognised 8% of a real mailbox, so 92% reached Layer 2 with
nothing to select a corpus by, and the one corpus the tenant had activated never got to speak.
A keyword table can only recognise language somebody thought to write down; most mail is
ordinary sentences.

**And nothing anywhere answered "what kind of exchange is this."** The system classified EVENTS
(14 `SignalType` members — a deadline was stated, a commitment was made) and never the exchange.
That is the same hole that leaves `party.role` at one fact across the whole graph.

INTENT IS NOT A FIFTEENTH SIGNAL TYPE, and that is the load-bearing design decision. `SignalType`
is picked ONE-per-event by a fixed precedence; ranking "promotional" against "escalation" has no
right answer, because a promotional email can also state a deadline. A message is BOTH. So intent
travels BESIDE the taxonomy, never inside it.
"""

from __future__ import annotations

import pytest

from genios_engine.capture.domain.hints import FALLBACK_DOMAIN, domain_hints
from genios_engine.capture.esqe import relevance
from genios_engine.capture.pipeline import coverage_verdict
from genios_engine.contracts.gated_event import DomainHint
from genios_engine.contracts.intent import (
    UNREAD,
    Band,
    IntentCategory,
    MessageIntent,
    Tone,
)

pytestmark = pytest.mark.unit


# =============================================================================================
# The contract: unknown is a real answer, and it is never guessed.
# =============================================================================================
def test_a_message_nobody_read_says_so():
    assert UNREAD.observed_anything is False
    assert UNREAD.category is IntentCategory.UNKNOWN


def test_a_message_that_was_read_is_distinguishable_from_one_that_was_not():
    """"An automated receipt nobody is waiting on" is information. "I could not read this" is
    not, and a reader that cannot tell them apart will treat the second as the first."""
    read = MessageIntent(category=IntentCategory.AUTOMATED, asks_for_reply=False)

    assert read.observed_anything is True
    assert UNREAD.observed_anything is False


@pytest.mark.parametrize("placeholder", ["unknown", "  N/A ", "none", "unclear", "-", "   "])
def test_a_placeholder_motive_is_absent_rather_than_a_value(placeholder):
    """`contracts/extraction` refuses the same strings for business values, and for the same
    reason: a sentinel satisfies a completeness check while telling the reader nothing, and then
    every consumer downstream has to know it."""
    assert MessageIntent(motive=placeholder).motive is None


def test_a_real_motive_is_kept_and_normalised():
    assert MessageIntent(motive="  wants a   demo\nnext week ").motive == "wants a demo next week"


# =============================================================================================
# What the gate may act on. This is where a mistake deletes somebody's mail.
# =============================================================================================
def test_machinery_that_asks_nothing_is_noise():
    intent = MessageIntent(category=IntentCategory.AUTOMATED, asks_for_reply=False,
                           human_authored=False)

    assert intent.is_noise is True


def test_a_vendor_pitch_is_never_noise_on_this_evidence():
    """A PERSON is behind a promotional message and they will follow up. `capture/gate/rules`
    already records what over-matching costs — `support@` and `hello@` are a real small
    business — and deleting a vendor silently is how a supplier conversation disappears."""
    intent = MessageIntent(category=IntentCategory.PROMOTIONAL, asks_for_reply=True,
                           human_authored=True)

    assert intent.is_noise is False


def test_a_receipt_is_never_noise():
    """An invoice IS the evidence an obligation exists. It is the least conversational thing in
    a mailbox and the most load-bearing."""
    assert MessageIntent(category=IntentCategory.TRANSACTIONAL,
                         asks_for_reply=False).is_noise is False


def test_could_not_tell_never_reads_as_nobody_is_waiting():
    """`asks_for_reply is False` and not `not asks_for_reply`. `None` means the reader could not
    tell, and the two must not collapse — one is evidence, the other is its absence."""
    unsure = MessageIntent(category=IntentCategory.AUTOMATED, asks_for_reply=None)

    assert unsure.is_noise is False


def test_an_unread_message_is_never_noise():
    assert UNREAD.is_noise is False


# =============================================================================================
# The gate's parser. The model is untrusted input.
# =============================================================================================
def _response(*entries):
    return type("R", (), {"ok": True, "parsed": {"verdicts": list(entries)}})()


def test_the_two_questions_are_read_together():
    out = relevance._parse_verdicts(_response(
        {"item": 1, "business": True, "description": "a customer asking for a demo",
         "category": "working", "human_authored": True, "asks_for_reply": True}), 1)

    business, description, intent = out[1]
    assert business is True
    assert description == "a customer asking for a demo"
    assert intent.category is IntentCategory.WORKING
    assert (intent.human_authored, intent.asks_for_reply) == (True, True)


def test_an_unreadable_category_does_not_discard_a_good_business_verdict():
    """Every field is independently optional. A model that answers the first question well and
    the second badly must still have its first answer honoured."""
    out = relevance._parse_verdicts(_response(
        {"item": 1, "business": False, "description": "spam", "category": "NONSENSE"}), 1)

    business, _desc, intent = out[1]
    assert business is False
    assert intent.category is IntentCategory.UNKNOWN


def test_a_string_where_a_boolean_belongs_is_refused_not_coerced():
    """`"yes"` is a model that did not follow the shape. Coercing it is how `asks_for_reply`
    silently becomes true for every message in the batch."""
    out = relevance._parse_verdicts(_response(
        {"item": 1, "business": True, "category": "working",
         "human_authored": "yes", "asks_for_reply": "true"}), 1)

    _b, _d, intent = out[1]
    assert intent.human_authored is None
    assert intent.asks_for_reply is None


def test_a_number_the_model_volunteered_still_has_no_path_in():
    """The rule this module has always enforced for the business verdict — *"Do not return any
    score, rating, probability or number"* — now has a second field to protect."""
    out = relevance._parse_verdicts(_response(
        {"item": 1, "business": True, "category": "working",
         "confidence": 0.93, "priority": 7, "engagement": "high"}), 1)

    _b, _d, intent = out[1]
    assert intent.engagement is Band.UNKNOWN, "the gate does not read a judgement it never asked for"
    assert not hasattr(intent, "confidence")


def test_a_rule_that_matched_a_header_records_that_it_read_nothing():
    """The five deterministic rules read an ENVELOPE, not a message. Recording an intent on them
    would let a header match masquerade as a reading of the exchange."""
    decision = relevance._decide("e1", True, relevance.RULE_KNOWN_COUNTERPARTY, "rules")

    assert decision.intent == UNREAD
    assert decision.intent.observed_anything is False


# =============================================================================================
# The collector: where a business message goes when no pattern claims it.
# =============================================================================================
@pytest.mark.parametrize("text", [
    "can you send that across by Thursday",
    "are we still on for the thing next week",
    "thanks, that works",
])
def test_an_ordinary_sentence_now_reaches_a_corpus(text):
    """The 92%. None of these contains a word any keyword table was ever going to hold."""
    hints = domain_hints("gmail", text, fallback=FALLBACK_DOMAIN)

    assert [(h.domain, h.source) for h in hints] == [("admin", "fallback")]


@pytest.mark.parametrize(("text", "expected"), [
    ("Sharing our pitch deck ahead of the term sheet discussion", "fundraising"),
    ("Can you share pricing and a proposal for the deal?", "sales"),
    ("The API is down and throwing errors", "support"),
])
def test_widening_admin_does_not_let_it_steal_a_specific_domain(text, expected):
    """`_SHIPPED_RANK` tests fundraising, sales and support BEFORE admin, and the widened admin
    pattern must not change that ordering. An investor thread says "deck" and also says
    "budget"; letting the collector claim it is the failure `hints.py` already records."""
    hints = domain_hints("gmail", text, fallback=FALLBACK_DOMAIN)

    assert hints[0].domain == expected
    assert hints[0].source == "keyword"


@pytest.mark.parametrize("text", [
    "Shortlisting candidates, can we schedule an interview?",
    "Invite: quarterly review, please RSVP",
    "Invoice 4471 is overdue, please process the payment",
    "Please sign the NDA before Friday",
    "Your leave request has been approved",
])
def test_business_operations_land_in_admin_on_evidence_not_on_the_collector(text):
    """Admin absorbs money, people, scheduling, procurement and governance while it is the
    activated corpus. These match a PATTERN — the collector is not doing the work."""
    hints = domain_hints("gmail", text, fallback=FALLBACK_DOMAIN)

    assert ("admin", "keyword") in [(h.domain, h.source) for h in hints]


def test_a_caller_that_did_not_ask_for_a_collector_gets_no_guess():
    """The default is `None`. Marketing and machinery are refused upstream, and a domain on
    something we are discarding would be a filing decision about a deletion."""
    assert domain_hints("gmail", "can you send that across") == []


# =============================================================================================
# A fallback is not a classification.
# =============================================================================================
def test_the_collector_never_becomes_a_verdict_about_the_tenants_sources():
    """`coverage_ready` is three-valued and `None` means *we never classified this event*.
    Consulting coverage on a collector hint would turn "we could not tell" into a claim about
    whether the tenant has connected enough systems — collapsing the exact distinction the
    third state exists to keep."""
    asked: list[str] = []

    def spy(domain: str):
        asked.append(domain)
        return {"coverage_ready": True}

    verdict = coverage_verdict([DomainHint(domain="admin", source="fallback")], spy)

    assert verdict is None
    assert asked == []


def test_an_evidence_backed_hint_is_still_consulted():
    """The guard may not become "coverage is never checked"."""
    asked: list[str] = []

    def spy(domain: str):
        asked.append(domain)
        return {"coverage_ready": True}

    verdict = coverage_verdict([DomainHint(domain="sales", source="keyword")], spy)

    assert verdict is True
    assert asked == ["sales"]


def test_a_real_hint_behind_a_collector_one_still_wins():
    asked: list[str] = []

    def spy(domain: str):
        asked.append(domain)
        return {"coverage_ready": False}

    verdict = coverage_verdict([DomainHint(domain="admin", source="fallback"),
                                DomainHint(domain="sales", source="keyword")], spy)

    assert verdict is False
    assert asked == ["sales"]


# =============================================================================================
# The design decision, pinned so it cannot be undone by accident.
# =============================================================================================
def test_intent_is_not_a_member_of_the_event_taxonomy():
    """If a future author adds `PROMOTIONAL` to `SignalType`, `classify_signals` must rank it
    against `ESCALATION` — and there is no right answer, because a promotional message can also
    state a deadline. A message is BOTH; that is only expressible while the two are separate."""
    from genios_engine.contracts.signal import SignalType

    names = {member.value for member in SignalType}

    for category in IntentCategory:
        assert category.value not in names, category
    assert len(names) == 15            # 14 from doc 08 + availability_change (migration 0139)


def test_a_judgement_is_banded_not_scored():
    """A model asked for 0..10000 produces a false precision every downstream reader then treats
    as measured. Three bands can be argued with; 6,400 cannot."""
    assert {b.value for b in Band} == {"high", "medium", "low", "unknown"}
    assert MessageIntent().engagement is Band.UNKNOWN


# =============================================================================================
# Two readers, one answer.
# =============================================================================================
def test_the_richer_reading_wins_only_where_it_actually_answered():
    """The junk gate sees a subject line in a batch; the extractor has the whole message. Both
    already run. Carrying two intents would make every downstream reader choose."""
    gate = MessageIntent(category=IntentCategory.PROMOTIONAL, human_authored=True)
    richer = MessageIntent(category=IntentCategory.WORKING, tone=Tone.URGENT,
                           motive="wants pricing")

    folded = gate.merged_with(richer)

    assert folded.category is IntentCategory.WORKING, "the fuller read corrects the snippet"
    assert folded.tone is Tone.URGENT
    assert folded.motive == "wants pricing"
    assert folded.human_authored is True, "and keeps what only the gate answered"


def test_a_silent_extractor_never_erases_what_the_gate_read():
    """An empty reading is an ABSENCE, not a correction. Reading more of a message must never
    lose information."""
    gate = MessageIntent(category=IntentCategory.AUTOMATED, asks_for_reply=False)

    folded = gate.merged_with(MessageIntent())

    assert folded.category is IntentCategory.AUTOMATED
    assert folded.asks_for_reply is False
    assert folded.is_noise is True


def test_no_second_reading_at_all_leaves_the_first_untouched():
    gate = MessageIntent(category=IntentCategory.RELATIONAL)

    assert gate.merged_with(None).category is IntentCategory.RELATIONAL


def test_the_extraction_field_is_never_nullable():
    """Schema rule S-1 refuses a null field on an extraction — "an empty list or an empty
    mapping is how 'nothing was found' is said here" — and an empty `MessageIntent` says
    exactly that while merging as a no-op, so silence needs no sentinel of its own."""
    from genios_engine.contracts.extraction import ExtractionResult

    field = ExtractionResult.model_fields["exchange_intent"]

    assert field.annotation is MessageIntent
    assert field.default_factory is MessageIntent


def test_it_is_not_called_intent_because_that_name_is_taken():
    """`ExtractionResult.intent` is the SPEECH ACT of one message (inform | request | commit |
    decide | escalate) and `esqe/detector` reads it to fire ESCALATION. "I am escalating this"
    is a speech act; "this is a vendor pitch" is the kind of exchange it sits in. One message
    has both."""
    from genios_engine.contracts.extraction import ExtractionResult

    assert ExtractionResult.model_fields["intent"].annotation is str
    assert "exchange_intent" in ExtractionResult.model_fields


def test_the_validator_was_extended_rather_than_bypassed():
    """S-2 refuses a field its rule table has no rule for — "extend the validator with the field
    rather than letting the newest field be the unchecked one". A single nested record was a
    shape it did not know, so it learned one."""
    from genios_engine.capture.validate.schema import _Shape, _shape_of

    shape, element = _shape_of(MessageIntent)

    assert shape is _Shape.MODEL
    assert element is MessageIntent


def test_the_observed_half_and_the_judged_half_are_separate_fields():
    intent = MessageIntent(category=IntentCategory.WORKING, tone=Tone.URGENT,
                           engagement=Band.HIGH)

    assert intent.observed_anything is True
    assert intent.engagement is Band.HIGH
