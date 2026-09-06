"""M-6 · situation framing — the two HARD-FAIL rows of doc 09's H6 gate, tested adversarially.

    M-6 fabricated facts   0  — hard fail
    M-6 visibility leaks   0  — hard fail

Both are proven by ATTACKING the site rather than by asserting on a well-behaved response. The
adversarial corpus below is doc 12's requirement for this site — *"25 fixtures, cases 10–14, >= 3
with a visibility boundary"* — expressed as 25 hostile model responses, every one of which tries
to get a fabricated noun or a filtered fact onto a card. The two assertions over that corpus are
the gate rows.

Doc 12 says case 14 is *"the one to build the test for first. It is the only edge case in this
document with a data-leak consequence rather than a trust consequence."* It is the first section
below.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from genios_engine.context.framing import headline as headline_module
from genios_engine.context.framing.headline import (FALLBACK_CONTRADICTS_CONDITIONS,
                                                    FALLBACK_MALFORMED, FALLBACK_MODEL_ERROR,
                                                    FALLBACK_NO_MODEL,
                                                    FALLBACK_TEMPLATE_NOT_PERMITTED,
                                                    FALLBACK_UNKNOWN_TEMPLATE,
                                                    FALLBACK_UNSUPPORTED_SLOT, TEMPLATES,
                                                    FramingError, FramingFact, FramingInput,
                                                    HeadlineTemplate, build_prompt, frame,
                                                    template_headline, templates_for,
                                                    unsupported_terms)
from genios_engine.contracts.visibility import PARTICIPANTS, PRIVATE, Visibility

EVAL_TIME = datetime(2026, 3, 1, 9, 0, tzinfo=timezone.utc)

#: The reader every test frames FOR. On the thread, so they see the participants-scoped facts.
READER = "rohit@antler.co"
#: The sentence the board saw and this reader must never see. A distinctive token, so a leak is
#: findable in any string the site produces.
SECRET = "Blackthorn-acquisition"


def _public_facts() -> list[FramingFact]:
    return [
        FramingFact("fact:sub", "subscription.name", "AWS renewal", "AWS renewal",
                    Visibility(scope=PARTICIPANTS, principals=[READER])),
        FramingFact("fact:days", "subscription.current_period_end", "days left", 12,
                    Visibility(scope=PARTICIPANTS, principals=[READER])),
    ]


def _private_fact() -> FramingFact:
    """A fact from a thread this reader was NOT on. `private` with a different principal, which is
    exactly the shape of a board thread the founder's assistant may not read."""
    return FramingFact("fact:secret", "deal.codename", SECRET, SECRET,
                       Visibility(scope=PRIVATE, principals=["board@antler.co"]))


@pytest.fixture
def renewal():
    """The situation every test frames: a renewal with no owner, 12 days left."""
    def _build(*, extra: list[FramingFact] | None = None, viewer: str | None = READER,
               conditions=("edge.owns", "subscription.current_period_end")) -> FramingInput:
        return FramingInput.for_viewer(
            "vendor_renewal_decision", _public_facts() + (extra or []),
            matched_conditions=conditions, viewer_email=viewer,
            subject_label="AWS renewal")
    return _build


# =================================================================================================
# HARD FAIL · 0 visibility leaks — doc 12 case 14, built first
# =================================================================================================

def test_a_fact_outside_the_readers_visibility_never_reaches_the_prompt(renewal):
    """Barrier one. The model never SEES what the recipient may not — so a leak would require it
    to invent the string rather than to repeat one it was shown."""
    inp = renewal(extra=[_private_fact()])
    assert [f.fact_id for f in inp.facts] == ["fact:days", "fact:sub"]
    prompt = build_prompt(inp)
    assert SECRET not in prompt
    assert "fact:secret" not in prompt


def test_a_model_that_names_the_filtered_fact_is_refused(renewal):
    """Barrier two, and the one that matters: even a model that GUESSED the id correctly cannot
    pull the fact back in, because the slot is resolved against the filtered set."""
    inp = renewal(extra=[_private_fact()])
    leaky = lambda _prompt: {"template_id": "unowned_decision",
                             "slots": {"subject": "fact:secret", "days": "fact:days"}}
    result = frame(inp, ask=leaky, eval_time=EVAL_TIME)
    assert result.fallback is True
    assert result.fallback_reason == FALLBACK_UNSUPPORTED_SLOT
    assert SECRET not in result.headline
    assert SECRET not in result.why_it_matters


def test_the_situations_audience_is_the_narrowest_of_what_survived(renewal):
    """A framing's audience can only ever be as narrow as the evidence it was derived from."""
    inp = renewal()
    assert inp.visibility.scope == PARTICIPANTS
    assert inp.visibility.principals == [READER]
    assert frame(inp).visibility.scope == PARTICIPANTS


def test_a_reader_who_may_see_nothing_gets_no_facts_and_still_gets_a_card(renewal):
    """Fail-closed: an outsider sees an empty input, and the site still returns something rather
    than raising — a raise here would take the whole card queue down for one unauthorised reader."""
    inp = renewal(viewer="stranger@elsewhere.com")
    assert inp.facts == ()
    result = frame(inp, ask=lambda _p: {"template_id": "unowned_decision",
                                        "slots": {"subject": "fact:sub", "days": "fact:days"}})
    assert result.fallback is True
    # Not even the subject's NAME: the anchor's name is itself a fact about the world, and a card
    # naming it for somebody who could see none of the evidence is a smaller leak, not a
    # permitted one.
    assert "AWS" not in result.headline
    assert result.subject_label == "vendor renewal decision"


# =================================================================================================
# HARD FAIL · 0 fabricated facts — doc 12 case 10
# =================================================================================================

def test_prose_the_model_writes_is_discarded_entirely(renewal):
    """The model's own words never reach the card. It returns a template id and fact ids; anything
    else in the response is dropped, so an invented company name has nowhere to go."""
    chatty = lambda _p: {"template_id": "unowned_decision",
                         "slots": {"subject": "fact:sub", "days": "fact:days"},
                         "headline": "Northwind Capital is about to sue us for $4,000,000",
                         "note": "I am confident about this"}
    result = frame(renewal(), ask=chatty, eval_time=EVAL_TIME)
    assert result.fallback is False
    assert "Northwind" not in result.headline
    assert "sue" not in result.headline
    assert result.headline == "AWS renewal renews with no owner recorded and 12 days left to cancel"


def test_an_invented_fact_id_falls_back_to_the_deterministic_headline(renewal):
    invented = lambda _p: {"template_id": "unowned_decision",
                           "slots": {"subject": "fact:acquisition_rumour", "days": "fact:days"}}
    result = frame(renewal(), ask=invented, eval_time=EVAL_TIME)
    assert result.fallback_reason == FALLBACK_UNSUPPORTED_SLOT
    assert result.template_id == "deterministic_template"


def test_an_unknown_template_falls_back(renewal):
    result = frame(renewal(), ask=lambda _p: {"template_id": "urgent_crisis", "slots": {}},
                   eval_time=EVAL_TIME)
    assert result.fallback_reason == FALLBACK_UNKNOWN_TEMPLATE


def test_a_template_from_another_situation_type_falls_back(renewal):
    """A sentence written for an overdue promise, chosen for a renewal, would be a true-sounding
    claim about the wrong thing."""
    result = frame(renewal(), ask=lambda _p: {"template_id": "overdue_promise",
                                              "slots": {"subject": "fact:sub",
                                                        "days": "fact:days"}},
                   eval_time=EVAL_TIME)
    assert result.fallback_reason == FALLBACK_TEMPLATE_NOT_PERMITTED


# =================================================================================================
# Case 11 · the pattern's conditions are authoritative
# =================================================================================================

def test_a_framing_that_contradicts_the_matched_conditions_is_rejected(renewal):
    """The situation matched WITHOUT the owner condition, so it may not be framed as unowned —
    however well the sentence reads. Framing describes the conditions; it cannot overrule them."""
    inp = renewal(conditions=("subscription.current_period_end",))
    result = frame(inp, ask=lambda _p: {"template_id": "unowned_decision",
                                        "slots": {"subject": "fact:sub", "days": "fact:days"}},
                   eval_time=EVAL_TIME)
    assert result.fallback_reason == FALLBACK_CONTRADICTS_CONDITIONS
    assert "no owner" not in result.headline


# =================================================================================================
# Case 12 · numbers are templated in, never generated
# =================================================================================================

def test_a_template_containing_a_digit_cannot_be_registered():
    """The mechanism behind "$84K became $84,000,000". A literal number in a template is a number
    no fact backs, and registration is where that is cheap to catch."""
    with pytest.raises(FramingError):
        HeadlineTemplate(template_id="bad", situation_types=("x",), slots=("subject",),
                         sentence="{subject} has 12 days left", why_it_matters="")


def test_no_shipped_template_contains_a_digit():
    for template in TEMPLATES:
        assert not any(c.isdigit() for c in template.sentence), template.template_id
        assert not any(c.isdigit() for c in template.why_it_matters), template.template_id


def test_every_digit_in_the_output_came_from_a_supplied_value(renewal):
    result = frame(renewal(), ask=lambda _p: {"template_id": "unowned_decision",
                                              "slots": {"subject": "fact:sub",
                                                        "days": "fact:days"}},
                   eval_time=EVAL_TIME)
    digits = "".join(c for c in result.headline if c.isdigit())
    assert digits == "12", "the only number on the card is the one the fact carried"


def test_a_template_using_an_undeclared_slot_cannot_be_registered():
    with pytest.raises(FramingError):
        HeadlineTemplate(template_id="bad", situation_types=("x",), slots=("subject",),
                         sentence="{subject} and {mystery}", why_it_matters="")


# =================================================================================================
# The fallback is a real path, and it is logged
# =================================================================================================

def test_no_model_publishes_the_deterministic_headline(renewal):
    result = frame(renewal(), ask=None)
    assert result.fallback is True
    assert result.fallback_reason == FALLBACK_NO_MODEL
    assert result.headline == "AWS renewal: vendor renewal decision"
    assert result.evidence_fact_ids == ("fact:days", "fact:sub")


def test_a_model_that_raises_does_not_take_the_card_down(renewal):
    def explodes(_prompt):
        raise RuntimeError("budget exhausted")
    result = frame(renewal(), ask=explodes, eval_time=EVAL_TIME)
    assert result.fallback_reason == FALLBACK_MODEL_ERROR
    assert result.headline


def test_a_malformed_response_falls_back(renewal):
    for junk in ("not json", None, {"template_id": "unowned_decision", "slots": "subject"}):
        result = frame(renewal(), ask=lambda _p, j=junk: j, eval_time=EVAL_TIME)
        assert result.fallback is True
        assert result.fallback_reason in (FALLBACK_MALFORMED, FALLBACK_UNKNOWN_TEMPLATE)


def test_the_fallback_is_logged(renewal, caplog):
    """A silent fallback is a card that quietly got worse and nobody can tell how often."""
    import logging
    with caplog.at_level(logging.INFO, logger="genios.context.framing"):
        frame(renewal(), ask=None)
    assert FALLBACK_NO_MODEL in caplog.text


def test_the_same_situation_framed_twice_is_identical(renewal):
    """A cached response must render the same card. Prompt and output are both deterministic."""
    ask = lambda _p: {"template_id": "unowned_decision",
                      "slots": {"subject": "fact:sub", "days": "fact:days"}}
    a = frame(renewal(), ask=ask, eval_time=EVAL_TIME)
    b = frame(renewal(), ask=ask, eval_time=EVAL_TIME)
    assert a.as_record() == b.as_record()
    assert build_prompt(renewal()) == build_prompt(renewal())


# =================================================================================================
# THE ADVERSARIAL CORPUS — doc 12's golden-set requirement for M-6, as 25 hostile responses
# =================================================================================================

def _hostile_responses() -> list[dict]:
    """Twenty-five ways a model tries to put something on a card that nothing supports.

    Cases 10 (fabrication), 11 (contradiction), 12 (number drift) and 14 (leak) are all here, and
    five of them carry a visibility boundary — doc 12 asks for at least three.
    """
    invented = [
        {"template_id": "unowned_decision", "slots": {"subject": "fact:rumour",
                                                      "days": "fact:days"}},
        {"template_id": "unowned_decision", "slots": {"subject": "AWS renewal",
                                                      "days": "12"}},
        {"template_id": "unowned_decision", "slots": {"subject": "fact:sub", "days": "9999"}},
        {"template_id": "unowned_decision", "slots": {"subject": "fact:sub"}},
        {"template_id": "unowned_decision", "slots": {}},
        {"template_id": "unowned_decision"},
        {"template_id": "", "slots": {"subject": "fact:sub", "days": "fact:days"}},
        {"template_id": "sole_approver", "slots": {"subject": "fact:sub", "count": "fact:days"}},
        {"template_id": "overdue_promise", "slots": {"subject": "fact:sub", "days": "fact:days"}},
        {"template_id": "relationship_cooling", "slots": {"subject": "fact:sub",
                                                          "metric": "fact:days"}},
        {"template_id": "unowned_decision", "slots": {"subject": "fact:sub", "days": "fact:days"},
         "headline": "URGENT: Acme is terminating the master agreement"},
        {"template_id": "unowned_decision", "slots": {"subject": "fact:sub", "days": "fact:days"},
         "why_it_matters": "the CFO said we would lose $84,000,000"},
        {"template_id": "unowned_decision", "slots": {"subject": "fact:sub", "days": "fact:days"},
         "extra_claim": "and the CEO is resigning"},
        {"template_id": "unowned_decision", "slots": {"subject": None, "days": None}},
        {"template_id": None, "slots": None},
        {"template_id": ["unowned_decision"], "slots": {"subject": "fact:sub"}},
        {"template_id": "unowned_decision", "slots": {"subject": ["fact:sub"],
                                                      "days": "fact:days"}},
        {"template_id": "unowned_decision", "slots": {"subject": "fact:sub",
                                                      "days": "fact:sub"}},
        {"template_id": "condition_met", "slots": {"subject": "fact:sub"}},
        {"template_id": "unprepared_meeting", "slots": {"subject": "fact:sub",
                                                        "days": "fact:days"}},
    ]
    leaks = [
        {"template_id": "unowned_decision", "slots": {"subject": "fact:secret",
                                                      "days": "fact:days"}},
        {"template_id": "unowned_decision", "slots": {"subject": "fact:sub",
                                                      "days": "fact:secret"}},
        {"template_id": "unowned_decision", "slots": {"subject": SECRET, "days": "fact:days"}},
        {"template_id": "unowned_decision", "slots": {"subject": "fact:sub", "days": "fact:days"},
         "headline": f"The {SECRET} thread says the renewal is dead"},
        {"template_id": "unowned_decision", "slots": {"subject": "fact:sub", "days": "fact:days"},
         "subject_label": SECRET},
    ]
    return invented + leaks


def test_the_adversarial_corpus_produces_zero_fabricated_facts_and_zero_leaks(renewal):
    """THE GATE. Twenty-five hostile responses, and not one of them puts a word on a card that the
    caller did not supply — nor a word from a fact this reader may not see.

    Every response either renders one of the shipped templates over supplied values, or falls back.
    There is no third outcome, which is the property that makes the two hard-fail rows structural
    rather than aspirational.
    """
    inp = renewal(extra=[_private_fact()])
    supplied = {f.rendered() for f in inp.facts} | {f.label for f in inp.facts}
    fabrications: list[str] = []
    leaks: list[str] = []

    for response in _hostile_responses():
        result = frame(inp, ask=lambda _p, r=response: r, eval_time=EVAL_TIME)
        text = f"{result.headline} {result.subject_label} {result.why_it_matters}"
        if SECRET.lower() in text.lower() or "fact:secret" in text:
            leaks.append(str(response))
        if not result.fallback:
            template = next(t for t in TEMPLATES if t.template_id == result.template_id)
            used = [inp.fact(fid) for fid in result.evidence_fact_ids]
            if unsupported_terms(result.headline, template, [f for f in used if f]):
                fabrications.append(str(response))
        else:
            # Even the fallback may only use supplied material.
            for word in ("Acme", "URGENT", "resigning", "84,000,000", "9999"):
                if word in text:
                    fabrications.append(str(response))

    assert leaks == [], f"visibility leak — HARD FAIL: {leaks}"
    assert fabrications == [], f"fabricated fact — HARD FAIL: {fabrications}"


def test_the_corpus_is_the_size_doc_12_asks_for():
    """25 fixtures for M-6, with at least three carrying a visibility boundary."""
    responses = _hostile_responses()
    assert len(responses) >= 25
    boundary = [r for r in responses if SECRET in str(r) or "fact:secret" in str(r)]
    assert len(boundary) >= 3


# =================================================================================================
# Cross-cutting rules from doc 12
# =================================================================================================

def test_the_model_output_reaches_no_bp_field():
    """Doc 12's first cross-cutting rule: *"No `_bp` output, ever. No LLM at L2 produces a number
    that feeds ranking."* Source-level, because the defect would be a field existing."""
    source = Path(headline_module.__file__).read_text()
    assert "_bp" not in source.replace("weight_bp", "").replace("importance_bp", "")
    from dataclasses import fields
    from genios_engine.context.framing.headline import Framing
    assert not [f.name for f in fields(Framing) if f.name.endswith("_bp")]


def test_the_site_makes_no_visibility_decision_of_its_own():
    """Doc 12's second rule: the model never widens an audience. The only visibility this module
    computes is `narrowest()` over what the reader could already see."""
    source = Path(headline_module.__file__).read_text()
    assert "can_view" in source and "narrowest" in source
    assert "scope=" not in source.split("def for_viewer")[1].split("def fact")[0], (
        "the filter may never CONSTRUCT a scope; it only narrows what it was given")


def test_every_situation_type_the_seed_patterns_emit_has_a_template():
    """A situation type with no template can still be framed — it falls back — but the fallback is
    the plain card, and shipping six patterns whose cards are all plain would make the site
    decorative."""
    from genios_engine.context.patterns.registry import seed_registry
    for pattern in seed_registry().all():
        assert templates_for(pattern.situation_type), pattern.situation_type


def test_the_deterministic_headline_uses_only_supplied_facts(renewal):
    plain = template_headline(renewal())
    assert plain.subject_label == "AWS renewal"
    assert plain.fallback is True
