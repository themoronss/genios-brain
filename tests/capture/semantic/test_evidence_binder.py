"""L1.4.6-U1 · span attachment enforcement — the rule that makes the layer honest.

    pytest tests/capture/semantic/test_evidence_binder.py -q

Doc-04 states three outcomes and a lenient implementation loses the third:

    cites something                          -> kept, untouched
    cites nothing, its words ARE in the text -> span SYNTHESIZED, confidence * 7 // 10
    cites nothing, its words are nowhere     -> DROPPED, `no_evidence` incremented

Every test below is about one of those three, about the counter that makes a mass-drop
regression visible, or about a boundary the binder must NOT cross — it never verifies a receipt
the model brought (that is ALG-08's job, one unit downstream) and it never stamps one verified.

Hermetic: no clock, no database, no model. The "extractor output" here is a `ClaimDraft`,
because a claim with no receipt has no legal typed form — every citation-bearing contract in
C-09 refuses an empty evidence list at construction, which is exactly why U1 runs post-parse
and pre-typing.
"""

from __future__ import annotations

import pytest

from genios_engine.capture.semantic.evidence_binder import (
    MAX_NO_EVIDENCE_RATE_BP,
    SYNTHESIS_FACTOR,
    BinderCounters,
    BoundClaim,
    ClaimDraft,
    bind_evidence,
    no_evidence_rate_bp,
    rate_blocks_prompt_release,
)
from genios_engine.capture.semantic.evidence_binder import _RECOVERED
from genios_engine.capture.validate.spans import SpanVerdict
from genios_engine.contracts.evidence import MAX_QUOTE_CHARS, EvidenceSpan

pytestmark = pytest.mark.unit

SOURCE_REF = "prepared_content:evt_binder"


def draft(claim_text: str, *, field: str = "commitments", confidence_bp: int = 8_000,
          evidence: tuple[EvidenceSpan, ...] = ()) -> ClaimDraft:
    return ClaimDraft(field=field, claim_text=claim_text, confidence_bp=confidence_bp,
                      evidence=evidence)


def span_for(quote: str, text: str) -> EvidenceSpan:
    """A receipt built by FINDING the quote, so no test here hand-counts an offset."""
    start = text.find(quote)
    assert start >= 0 and text.find(quote, start + 1) < 0, f"bad fixture quote {quote!r}"
    return EvidenceSpan(source_ref=SOURCE_REF, quote=quote, start_offset=start,
                        end_offset=start + len(quote), verified=False)


# ---------------------------------------------------------------------------------------------
# The three outcomes
# ---------------------------------------------------------------------------------------------

TEXT = ("Finance will confirm the increase by Friday. We can move forward with the annual "
        "contract once legal signs off.")


def test_a_claim_that_cites_nothing_and_says_nothing_findable_is_dropped():
    """Outcome 3. The claim asserts something the message does not contain, so nobody can ever
    point at it — it is not an extraction, it is an assertion, and it does not leave S2."""
    outcome = bind_evidence([draft("Procurement approved the renewal at $1.2M")],
                            prepared_text=TEXT, source_ref=SOURCE_REF)

    assert outcome.claims == ()
    assert outcome.counters.no_evidence == 1
    assert outcome.counters.claims_in == 1
    assert outcome.counters.synthesized == 0


def test_a_claim_with_recoverable_text_gets_a_synthesized_span_and_reduced_confidence():
    """Outcome 2. The words are in the message; the model just failed to say where it read
    them. The receipt is synthesized at the offsets they were actually found at, and the claim
    is priced for having needed one."""
    outcome = bind_evidence([draft("Finance will confirm the increase", confidence_bp=8_000)],
                            prepared_text=TEXT, source_ref=SOURCE_REF)

    assert outcome.counters.synthesized == 1
    assert outcome.counters.no_evidence == 0
    (bound,) = outcome.claims
    assert bound.synthesized is True
    assert bound.confidence_bp == 5_600                      # 8000 * 7 // 10
    (span,) = bound.evidence
    assert TEXT[span.start_offset:span.end_offset] == span.quote
    assert span.quote == "Finance will confirm the increase"
    assert span.source_ref == SOURCE_REF


def test_a_claim_that_brought_its_own_receipt_is_kept_untouched():
    """Outcome 1. The binder does not re-price a receipt the model brought and does not grade
    it: grading is ALG-08's, and doing it here would charge the same span twice."""
    cited = span_for("once legal signs off", TEXT)
    outcome = bind_evidence([draft("legal sign-off is pending", evidence=(cited,),
                                   confidence_bp=8_000)],
                            prepared_text=TEXT, source_ref=SOURCE_REF)

    (bound,) = outcome.claims
    assert bound.synthesized is False
    assert bound.confidence_bp == 8_000
    assert bound.evidence == (cited,)
    assert outcome.counters == BinderCounters(claims_in=1, carried_own_evidence=1,
                                              synthesized=0, no_evidence=0)


def test_a_receipt_the_source_does_not_contain_is_still_carried_not_dropped():
    """The binder's question is "does this claim cite ANYTHING", never "is the citation true".

    A fabricated quote must reach L1.5.1 to be graded UNVERIFIED and priced by the ALG-08
    policy. Dropping it here would delete the evidence that the extractor is fabricating, and
    the unverified-rate monitor one unit downstream would go quiet exactly when it should not.
    """
    invented = EvidenceSpan(source_ref=SOURCE_REF, quote="Procurement signed",
                            start_offset=0, end_offset=18, verified=False)
    outcome = bind_evidence([draft("procurement signed", evidence=(invented,))],
                            prepared_text=TEXT, source_ref=SOURCE_REF)

    (bound,) = outcome.claims
    assert bound.evidence == (invented,)
    assert outcome.counters.no_evidence == 0


# ---------------------------------------------------------------------------------------------
# What a synthesized receipt may and may not carry
# ---------------------------------------------------------------------------------------------


def test_a_synthesized_span_is_never_stamped_verified():
    """`verify_span` returns its corrected span stamped True — that stamp is L1.5.1's alone.

    The needle here sits at offset 0, the one position where the cascade returns VERIFIED, so
    the flag would ride out of the binder untouched if it were passed through. A span leaving
    the extractor seam wearing a checkmark is the extractor grading its own homework.
    """
    outcome = bind_evidence([draft("Finance will confirm")], prepared_text=TEXT,
                            source_ref=SOURCE_REF)

    (span,) = outcome.claims[0].evidence
    assert span.start_offset == 0                            # the VERIFIED branch really ran
    assert span.verified is False


def test_a_reflowed_claim_recovers_and_the_receipt_quotes_the_SOURCE_not_the_model():
    """The model copied the sentence out of an email and flattened its newline.

    The words are literally present modulo whitespace, so the claim is recovered — and the
    stored quote is the source's own bytes, because a receipt that reproduces the model's
    reflow is a receipt that does not slice out of the document it points at.
    """
    text = "Finance will confirm\nthe increase by Friday."
    outcome = bind_evidence([draft("Finance will confirm the increase")], prepared_text=text,
                            source_ref=SOURCE_REF)

    (span,) = outcome.claims[0].evidence
    assert span.quote == "Finance will confirm\nthe increase"
    assert text[span.start_offset:span.end_offset] == span.quote


def test_an_over_long_claim_is_recovered_as_a_capped_quote_rather_than_dropped():
    """A needle longer than MAX_QUOTE_CHARS is truncated, not refused.

    A prefix matches wherever the whole string does, so the search is no less exact, and the
    receipt then quotes the first two sentences instead of a wall of text nobody checks —
    which is what the cap is for. Dropping it would delete a claim whose words are demonstrably
    in the message.
    """
    long_text = "A" * (MAX_QUOTE_CHARS + 120)
    outcome = bind_evidence([draft(long_text)], prepared_text=f"Preamble. {long_text} End.",
                            source_ref=SOURCE_REF)

    (span,) = outcome.claims[0].evidence
    assert len(span.quote) == MAX_QUOTE_CHARS
    assert span.start_offset == len("Preamble. ")


@pytest.mark.parametrize("claim_text, why", [
    ("", "a claim that cannot say what it asserts cannot be pointed at"),
    ("   \n\t ", "a whitespace-only needle is not a receipt ALG-08 would ever rewrite onto"),
])
def test_a_claim_with_no_usable_needle_is_dropped(claim_text, why):
    outcome = bind_evidence([draft(claim_text)], prepared_text=TEXT, source_ref=SOURCE_REF)

    assert outcome.claims == (), why
    assert outcome.counters.no_evidence == 1


def test_a_needle_longer_than_the_whole_message_is_dropped():
    """INVALID_BOUNDS is a failure verdict, not a recovery: there is no region to point at."""
    outcome = bind_evidence([draft("Finance will confirm the increase by Friday.")],
                            prepared_text="Finance.", source_ref=SOURCE_REF)

    assert outcome.claims == ()
    assert outcome.counters.no_evidence == 1


# ---------------------------------------------------------------------------------------------
# Integer basis points — the arithmetic, not a float in disguise
# ---------------------------------------------------------------------------------------------


@pytest.mark.parametrize("confidence_bp, expected_bp", [
    (10_000, 7_000),
    (8_500, 5_950),
    (9_999, 6_999),      # truncation rounds AGAINST the claim, never up
    # The rows that separate `bp * 7 // 10` from `int(bp * 0.7)`. 700 * (7/10) is
    # 489.99999999999994 in binary float and 1290 * (7/10) is 902.9999999999999, so a float
    # implementation silently pays out one basis point less than the doc's factor — the exact
    # class of drift integer basis points exist to make impossible.
    (700, 490),
    (1_290, 903),
    (1, 0),              # a claim we were already unsure of survives at zero, it is not deleted
    (0, 0),
])
def test_the_synthesis_penalty_is_integer_basis_points(confidence_bp, expected_bp):
    outcome = bind_evidence([draft("Finance will confirm", confidence_bp=confidence_bp)],
                            prepared_text=TEXT, source_ref=SOURCE_REF)

    bound = outcome.claims[0]
    assert bound.confidence_bp == expected_bp
    assert isinstance(bound.confidence_bp, int) and not isinstance(bound.confidence_bp, bool)


def test_the_penalty_is_the_documented_seven_tenths():
    """Pinned so a future edit to the factor is a deliberate change to a stated constant."""
    assert SYNTHESIS_FACTOR == (7, 10)


# ---------------------------------------------------------------------------------------------
# The counters and the release gate
# ---------------------------------------------------------------------------------------------


def test_a_mixed_batch_tallies_each_route_and_keeps_the_survivors_in_order():
    cited = span_for("annual contract", TEXT)
    drafts = [
        draft("first", field="entity_mentions", evidence=(cited,)),
        draft("Procurement approved the renewal", field="decision_states"),
        draft("move forward with the annual contract", field="commitments"),
        draft("nothing in this message says this", field="dependencies"),
    ]

    outcome = bind_evidence(drafts, prepared_text=TEXT, source_ref=SOURCE_REF)

    assert [c.draft.field for c in outcome.claims] == ["entity_mentions", "commitments"]
    assert outcome.counters == BinderCounters(claims_in=4, carried_own_evidence=1,
                                              synthesized=1, no_evidence=2)
    assert outcome.counters.bound == 2


@pytest.mark.parametrize("counters, expected_bp, why", [
    (BinderCounters(), 0, "no claims reports 0 — read it beside claims_in"),
    (BinderCounters(claims_in=4, carried_own_evidence=3, no_evidence=1), 2_500, "1 of 4"),
    (BinderCounters(claims_in=3, carried_own_evidence=2, no_evidence=1), 3_333,
     "integer division truncates, so the rate is never overstated"),
    (BinderCounters(claims_in=2, no_evidence=2), 10_000, "every claim dropped is 100%"),
    (BinderCounters(claims_in=20, carried_own_evidence=19, no_evidence=1), 500,
     "exactly the threshold"),
])
def test_the_no_evidence_rate_is_the_share_of_claims_that_had_no_receipt(counters, expected_bp,
                                                                        why):
    assert no_evidence_rate_bp(counters) == expected_bp, why


@pytest.mark.parametrize("rate_bp, blocks", [
    (0, False),
    (499, False),
    (500, False),        # "above 5%" — a prompt landing exactly on the stated bar ships
    (501, True),
    (10_000, True),
])
def test_the_release_gate_blocks_only_above_the_stated_five_percent(rate_bp, blocks):
    assert rate_blocks_prompt_release(rate_bp) is blocks
    assert MAX_NO_EVIDENCE_RATE_BP == 500


def test_the_counter_is_computed_from_a_real_pass_not_from_a_hand_built_tally():
    """The metric and the enforcement must be the same number: four fabrications out of eight
    claims is 50%, and that blocks the next prompt version."""
    drafts = ([draft("Finance will confirm the increase") for _ in range(4)]
              + [draft(f"fabrication number {n}") for n in range(4)])

    outcome = bind_evidence(drafts, prepared_text=TEXT, source_ref=SOURCE_REF)

    assert no_evidence_rate_bp(outcome.counters) == 5_000
    assert rate_blocks_prompt_release(no_evidence_rate_bp(outcome.counters)) is True


# ---------------------------------------------------------------------------------------------
# Fail-closed construction
# ---------------------------------------------------------------------------------------------


@pytest.mark.parametrize("kwargs, exc", [
    ({"field": ""}, ValueError),
    ({"field": "   "}, ValueError),
    ({"confidence_bp": 0.7}, TypeError),                     # a ratio, the thing bp exists to ban
    ({"confidence_bp": True}, TypeError),
    ({"confidence_bp": 10_001}, ValueError),
    ({"confidence_bp": -1}, ValueError),
    ({"claim_text": None}, TypeError),
    ({"evidence": "not a sequence of spans"}, TypeError),
    ({"evidence": ["not a span"]}, TypeError),
])
def test_a_malformed_draft_is_refused_at_construction(kwargs, exc):
    base = {"field": "commitments", "claim_text": "Finance will confirm", "confidence_bp": 8_000}
    with pytest.raises(exc):
        ClaimDraft(**{**base, **kwargs})


def test_a_draft_freezes_its_evidence_so_a_caller_cannot_edit_a_receipt_after_the_fact():
    cited = span_for("annual contract", TEXT)
    mutable = [cited]
    drafted = ClaimDraft(field="commitments", claim_text="x", confidence_bp=1, evidence=mutable)
    mutable.clear()

    assert drafted.evidence == (cited,)


def test_a_bound_claim_with_no_evidence_cannot_be_constructed():
    """The output guarantee is enforced by the type, not only by the code path that builds it."""
    with pytest.raises(ValueError):
        BoundClaim(draft=draft("x"), evidence=(), confidence_bp=1, synthesized=True)


def test_recovery_accepts_every_literal_verdict_and_no_other():
    """The recovery policy is stated positively, so a new ALG-08 grade breaks this test instead
    of silently defaulting to "recovered" in the unit that decides whether an unsubstantiated
    claim survives."""
    assert _RECOVERED | {SpanVerdict.UNVERIFIED, SpanVerdict.INVALID_BOUNDS} == set(SpanVerdict)
    assert SpanVerdict.UNVERIFIED not in _RECOVERED
    assert SpanVerdict.INVALID_BOUNDS not in _RECOVERED


def test_binding_refuses_a_source_ref_that_names_nothing():
    """A synthesized receipt whose reference is blank points at character 412 *of what*."""
    with pytest.raises(ValueError):
        bind_evidence([draft("Finance")], prepared_text=TEXT, source_ref="")


# ---------------------------------------------------------------------------------------------
# The frame a carried receipt is measured in
#
# `bind_evidence` is handed a `(prepared_text, source_ref)` PAIR: one body of text, and the name
# of the frame its offsets are measured in. It stamps that name onto every receipt it
# synthesizes, and `align_span` in this same module raises on a `source_ref` naming a frame its
# offsets are not in — "a span whose offsets are in one frame while its reference names another
# points at the wrong sentence invisibly". The carried path is the one that never checked, and
# it is the common path: every receipt the model brings goes through it.
# ---------------------------------------------------------------------------------------------


def test_a_carried_receipt_from_another_frame_is_refused():
    """A prepared-frame receipt handed to a chunk-frame pass points at nothing and said so late.

    Kept verbatim, it was counted as `carried_own_evidence` — a claim WITH a receipt — and the
    offsets resolved to `''` in the text the pass was actually about. The failure surfaced one
    unit downstream as ALG-08's INVALID_BOUNDS, which reads as "the model invented an offset"
    when what happened is that the extractor stamped the wrong frame.
    """
    prepared = "Preamble sentence here. " + TEXT
    chunk_text = prepared[24:]
    foreign = span_for("legal signs off", prepared)     # measured against the PREPARED text
    assert chunk_text[foreign.start_offset:foreign.end_offset] == ""

    with pytest.raises(ValueError, match="frame"):
        bind_evidence([draft("x", evidence=(foreign,))], prepared_text=chunk_text,
                      source_ref="chunk:doc1:1")


def test_a_carried_receipt_in_the_passs_own_frame_is_kept_untouched():
    """The other half of the same rule: agreeing on the frame changes nothing about the claim."""
    own = span_for("legal signs off", TEXT)
    outcome = bind_evidence([draft("x", confidence_bp=9_000, evidence=(own,))],
                            prepared_text=TEXT, source_ref=SOURCE_REF)
    assert outcome.claims[0].evidence == (own,)
    assert outcome.claims[0].confidence_bp == 9_000
    assert outcome.counters == BinderCounters(claims_in=1, carried_own_evidence=1)


def test_the_frame_check_names_the_claim_and_both_references():
    """The message has to be actionable: which lane regressed, and which two frames disagreed."""
    foreign = EvidenceSpan(source_ref="chunk:doc9:4", quote="Finance", start_offset=0,
                           end_offset=7, verified=False)
    with pytest.raises(ValueError) as raised:
        bind_evidence([draft("x", field="commitments", evidence=(foreign,))],
                      prepared_text=TEXT, source_ref=SOURCE_REF)
    message = str(raised.value)
    assert "commitments" in message
    assert "chunk:doc9:4" in message and SOURCE_REF in message
