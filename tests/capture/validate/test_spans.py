"""G1 · the pure validators — Wave W1. The span half: ALG-08 (L1.5.1-U1 and U2).

The gate is one suite plus three greps, and the greps are the interesting half:

    pytest tests/capture/validate -q                          # 0 skips
    grep -rn "float("        genios_engine/capture/validate/  # nothing
    grep -rn "datetime.now"  genios_engine/capture/validate/  # nothing
    grep -rn "LLMClient"     genios_engine/capture/validate/  # nothing

A validator that reads a clock cannot be replayed, a validator that calls a model is not a
validator, and a validator that touches a float has already lost the cent it was checking. All
three are properties of the SOURCE, not of any single test, which is why the gate greps and why
nothing below asserts on the text of the module.

What IS asserted here is behaviour against real strings: that the cascade grades a span exact /
whitespace-normalised / relocated / fuzzy / UNVERIFIED in that order, that a verified span comes
back with the offsets we FOUND rather than the ones the model claimed, and that the per-claim
policy holds — a fabricated `Money` or `ResolvedDate` is gone from the result, a `Commitment`
survives at halved confidence with its receipts still flagged unverified. Every span in this file
is built by `span_of`, which finds the quote in the fixture text, so no assertion depends on a
hand-counted offset that the next edit to the fixture would silently invalidate.
"""

from __future__ import annotations

import unicodedata
from dataclasses import FrozenInstanceError
from datetime import datetime, timedelta, timezone
from typing import Any

import pytest
from pydantic import ValidationError

from genios_engine.capture.validate.spans import (BP_FULL, MAX_RATE_REGRESSION_BP, SpanCounters,
                                                  SpanVerdict, apply_verdicts,
                                                  rate_regression_blocks_release,
                                                  unverified_rate_bp, verify_span)
from genios_engine.contracts.evidence import MAX_QUOTE_CHARS, EvidenceSpan
from genios_engine.contracts.extraction import (Commitment, DecisionState, Dependency,
                                                EntityMention, ExtractionResult,
                                                UnclassifiedObservation)
from genios_engine.contracts.units import DateCertainty, Money, ResolvedDate

WAVE = "W1"
GATE = "G1"

SOURCE_REF = "prepared_content:evt_l1_worked_example"

#: The same sentence as the worked example, reflowed across two lines. This is the shape a real
#: prepared email has and the model does not: extractors copy a quote with the newline flattened
#: to a space, which is the whole reason VERIFIED_WHITESPACE exists as a grade rather than as a
#: hallucination report.
WRAPPED_SOURCE = ("we can probably move forward with the $84K annual\ncontract, but I still "
                  "need Finance to confirm.")

#: One sentence, one repeated phrase. `str.find` must make the answer a property of the text.
REPEATED_SOURCE = "Send the invoice today. I will send the invoice today as well."


def _span(quote: str, start: int, *, source_ref: str = SOURCE_REF) -> EvidenceSpan:
    """A span as an EXTRACTOR would emit it: unverified, offsets asserted rather than found.

    Used only where a test needs a WRONG offset on purpose — the `span_of` fixture refuses to
    build one of those, correctly, because everywhere else a wrong offset is a broken test.
    """
    return EvidenceSpan(source_ref=source_ref, quote=quote, start_offset=start,
                        end_offset=start + len(quote), verified=False)


# ---------------------------------------------------------------------------------------------
# L1.5.1-U1 · the cascade
# ---------------------------------------------------------------------------------------------


@pytest.mark.gate
def test_exact_slice_verifies_and_keeps_the_offsets_it_was_given(worked_example_text, span_of):
    """`source[start:end] == quote` is the cheapest step and the only one that changes nothing.

    The span still comes back REBUILT, because `verified=True` is what this module exists to
    stamp and `EvidenceSpan` is frozen so that nobody else can.
    """
    span = span_of("$84K annual contract")
    verdict, corrected = verify_span(span, worked_example_text)

    assert verdict is SpanVerdict.VERIFIED
    assert corrected.verified is True
    assert (corrected.start_offset, corrected.end_offset) == (span.start_offset, span.end_offset)
    assert worked_example_text[corrected.start_offset:corrected.end_offset] == corrected.quote


@pytest.mark.gate
def test_flattened_newline_verifies_as_whitespace_and_rewrites_the_quote(span_of):
    """The extractor read a wrapped line and quoted it with the newline as a space.

    Position was right, transcription was cosmetic: VERIFIED_WHITESPACE, no confidence penalty,
    and the stored quote becomes the SOURCE's bytes — newline and all — because a receipt that
    does not match the document cannot be highlighted in it.
    """
    span = span_of("$84K annual contract,", text=WRAPPED_SOURCE.replace("\n", " "))
    verdict, corrected = verify_span(span, WRAPPED_SOURCE)

    assert verdict is SpanVerdict.VERIFIED_WHITESPACE
    assert corrected.verified is True
    assert corrected.quote == "$84K annual\ncontract,"
    assert WRAPPED_SOURCE[corrected.start_offset:corrected.end_offset] == corrected.quote


@pytest.mark.gate
def test_collapsed_whitespace_run_verifies_at_the_stated_start(span_of):
    """A quote whose spaces were collapsed still points at the right sentence.

    The corrected span covers the real, wider region: the model's `end` was short by the
    characters it silently dropped, and storing the model's end would highlight a truncated
    sentence.
    """
    source = "Finance   must   confirm the increase."
    span = _span("Finance must confirm", 0)
    verdict, corrected = verify_span(span, source)

    assert verdict is SpanVerdict.VERIFIED_WHITESPACE
    assert corrected.quote == "Finance   must   confirm"
    assert source[corrected.start_offset:corrected.end_offset] == corrected.quote


@pytest.mark.gate
def test_right_words_wrong_place_relocates_and_the_offsets_are_repaired(worked_example_text):
    """Step 4. The sentence is real; the measurement is not, so the offsets are replaced.

    A span that verified against the text but kept the model's numbers would highlight unrelated
    words in the card — worse than an honest UNVERIFIED, because the reader checks one receipt,
    sees nonsense, and stops checking the ones that are right.
    """
    quote = "Finance to confirm"
    truth = worked_example_text.find(quote)
    span = _span(quote, 3)
    verdict, corrected = verify_span(span, worked_example_text)

    assert verdict is SpanVerdict.VERIFIED_RELOCATED
    assert (corrected.start_offset, corrected.end_offset) == (truth, truth + len(quote))
    assert corrected.verified is True


@pytest.mark.gate
def test_whitespace_differences_plus_a_wrong_place_is_the_weakest_verified_grade():
    """Step 5 — found only after normalising whitespace AND searching the whole document.

    Still a LITERAL match. There is no similarity threshold anywhere in the cascade: a validator
    that accepted a near-enough quote would accept the paraphrase an inventing model produces,
    which is the one thing this unit is for.
    """
    source = "Line one.\nFinance   must   confirm the increase.\nLine three."
    span = _span("Finance must confirm the increase", 0)
    verdict, corrected = verify_span(span, source)

    assert verdict is SpanVerdict.VERIFIED_FUZZY
    assert corrected.quote == "Finance   must   confirm the increase"
    assert source[corrected.start_offset:corrected.end_offset] == corrected.quote


@pytest.mark.gate
def test_a_quote_absent_from_the_source_is_unverified_and_comes_back_untouched(
        worked_example_text):
    """Step 6, the hallucination catch. The model invented the sentence it claims to cite.

    The span is returned UNCHANGED and still `verified=False`: it is kept as testimony about the
    extractor even though it is not evidence about the world, and that flag is the whole
    mechanism by which the policy below and V-5 above can see it.
    """
    span = _span("Legal has already countersigned the agreement", 0)
    verdict, corrected = verify_span(span, worked_example_text)

    assert verdict is SpanVerdict.UNVERIFIED
    assert corrected == span
    assert corrected.verified is False


@pytest.mark.gate
def test_a_paraphrase_of_a_real_sentence_is_unverified(worked_example_text):
    """The failure mode the grades exist to distinguish from a reflowed newline.

    "the $84K yearly contract" is what the source means and not what it says. Every step of the
    cascade is a literal comparison, so a rewording lands in step 6 exactly like an invention —
    which is correct: we cannot tell the two apart, and neither can the reader.
    """
    verdict, _ = verify_span(_span("the $84K yearly contract", 44), worked_example_text)

    assert verdict is SpanVerdict.UNVERIFIED


@pytest.mark.gate
@pytest.mark.parametrize("source, quote, start, why", [
    ("", "anything at all", 0, "empty source — nothing can be at any offset"),
    ("short text", "short text is longer than this source", 0, "span longer than the source"),
    ("Finance must confirm.", "confirm.", 14, "offsets run one character past the end"),
])
def test_offsets_that_cannot_describe_this_text_are_invalid_bounds(source, quote, start, why):
    """Step 1, and it terminates the cascade — the quote is never even looked for.

    Deliberate: an offset past the end of the document is not a near-miss to be repaired by
    search, it is a span computed against different text (a stale `prepared_content` version, or
    offsets taken before PII masking realigned them). Repairing it silently would hide the
    version skew that produced it, which is the failure mode doc 05 names.
    """
    span = _span(quote, start)
    verdict, corrected = verify_span(span, source)

    assert verdict is SpanVerdict.INVALID_BOUNDS, why
    assert corrected == span


@pytest.mark.gate
@pytest.mark.parametrize("start, end, why", [
    (-1, 4, "a negative start is not a position in a string"),
    (7, 7, "an empty range highlights nothing"),
    (9, 4, "an inverted range describes no region"),
])
def test_the_contract_refuses_the_bounds_this_module_would_have_to_reject(start, end, why):
    """The other two branches of step 1 are unreachable through a well-formed span, on purpose.

    `EvidenceSpan` refuses a negative offset and a non-positive range at construction, so a span
    that reaches ALG-08 can only fail bounds by pointing past the end. The branches stay in the
    cascade because that function is the definition of the algorithm; this test is what says the
    contract, not the validator, is the thing keeping them cold.
    """
    with pytest.raises(ValidationError):
        EvidenceSpan(source_ref=SOURCE_REF, quote="need", start_offset=start, end_offset=end)


@pytest.mark.gate
def test_a_quote_that_occurs_twice_relocates_to_the_first_occurrence():
    """Determinism, not preference. `str.find` makes the answer a property of the text.

    A relocation that picked "the occurrence nearest the model's guess" would make the same span
    and the same source resolve to different offsets depending on what the model asserted, and a
    replay in September would then highlight a different sentence than the card did in March.
    """
    quote = "the invoice today"
    first = REPEATED_SOURCE.find(quote)
    second = REPEATED_SOURCE.find(quote, first + 1)
    assert 0 <= first < second, "the fixture really does repeat the phrase"

    verdict, corrected = verify_span(_span(quote, 0), REPEATED_SOURCE)

    assert verdict is SpanVerdict.VERIFIED_RELOCATED
    assert (corrected.start_offset, corrected.end_offset) == (first, first + len(quote))


#: The same word in the two normal forms. NFC composes the accent into one character, NFD keeps
#: it as "e" plus a combining acute — so "café" is four characters or five depending on which
#: normalisation the producer used, and the offsets an extractor reports depend on that choice.
CAFE_NFC = "caf\u00e9"
CAFE_NFD = "cafe\u0301"
_PREFIX = "Meeting at the "
_SUFFIX = " tomorrow"


@pytest.mark.gate
@pytest.mark.parametrize("source, quote, why", [
    (_PREFIX + CAFE_NFC + _SUFFIX, CAFE_NFD,
     "source composed, quote decomposed — the quote is one character LONGER than the source"),
    (_PREFIX + CAFE_NFD + _SUFFIX, CAFE_NFC,
     "source decomposed, quote composed — the quote is one character SHORTER than the source"),
])
def test_unicode_composition_differences_still_verify(source, quote, why):
    """"café" written two ways is one word, and the two ways are different LENGTHS.

    That is why the offsets cannot simply be trusted after normalising: the end moves. The
    validator anchors on the start the model gave, re-derives the end from what it found, and
    rewrites the quote to the source's own bytes — so the receipt round-trips into the real
    document regardless of which normal form either side used. Without this step the entire
    corpus of a producer that emits NFD would read as fabricated.
    """
    span = _span(quote, len(_PREFIX))
    verdict, corrected = verify_span(span, source)

    assert verdict is SpanVerdict.VERIFIED, why
    assert source[corrected.start_offset:corrected.end_offset] == corrected.quote
    assert corrected.quote in (CAFE_NFC, CAFE_NFD)
    assert unicodedata.normalize("NFC", corrected.quote) == CAFE_NFC


@pytest.mark.gate
def test_a_correction_that_cannot_be_expressed_as_a_valid_span_is_unverified():
    """The cap is a contract invariant, so a repair that would break it is not a repair.

    A 400-character quote whose source region is 401 characters (the collapsed run) cannot be
    rewritten without exceeding `MAX_QUOTE_CHARS`. Returning the model's own offsets with a
    verified flag would be worse than admitting we cannot show the receipt — so the cascade
    falls through every remaining step and reports UNVERIFIED.
    """
    quote = "a" * 199 + " " + "b" * 200
    source = "a" * 199 + "  " + "b" * 200
    assert len(quote) == MAX_QUOTE_CHARS and len(source) == MAX_QUOTE_CHARS + 1

    span = _span(quote, 0)
    verdict, corrected = verify_span(span, source)

    assert verdict is SpanVerdict.UNVERIFIED
    assert corrected == span


# ---------------------------------------------------------------------------------------------
# L1.5.1-U1 · the per-claim-type drop policy
# ---------------------------------------------------------------------------------------------


def _result(**claims: Any) -> ExtractionResult:
    """A minimal, valid `ExtractionResult` carrying whatever the test is about.

    Provenance is required for replay, so every field the contract demands is filled with a
    fixed literal — a builder that let a test omit one would be testing a different type than
    the pipeline stores.
    """
    payload: dict[str, Any] = {
        "intent": "inform",
        "stance": "cautious",
        "topics": ["renewal"],
        "model_snapshot": "fake-model-2026-01-01",
        "prompt_version": "l1-extract-3",
        "schema_version": "7",
        "extraction_profile": "email",
        "input_tokens": 1000,
        "output_tokens": 200,
    }
    payload.update(claims)
    return ExtractionResult(**payload)


def _date(evidence: list[EvidenceSpan], eval_time: datetime) -> ResolvedDate:
    return ResolvedDate(as_written="next week", earliest=eval_time + timedelta(days=4),
                        latest=eval_time + timedelta(days=10), certainty=DateCertainty.RANGE,
                        resolved_against=eval_time, evidence=evidence)


def _commitment(evidence: list[EvidenceSpan], *, confidence_bp: int = 8000,
                due: ResolvedDate | None = None) -> Commitment:
    return Commitment(actor="Rohit", action="confirm the increase with Finance",
                      is_conditional=False, due=due, evidence=evidence,
                      confidence_bp=confidence_bp)


@pytest.mark.gate
def test_a_money_claim_whose_literal_is_absent_from_the_source_is_dropped(worked_example_text):
    """The Globe fault, refused: a card that says "$84K" against a contract that says "$8.4K".

    `Money` carries no evidence list — C-02 has `as_written` and nothing else — so its receipt is
    that literal, which the contract defines as the source's own bytes. An amount whose literal
    is nowhere in the message is an amount nobody wrote, and a fabricated amount is worse than a
    missing one because it is ACTED ON.
    """
    real = Money(minor_units=8_400_000, currency="USD", as_written="$84K")
    invented = Money(minor_units=840_000, currency="USD", as_written="$8.4K")

    verified, counters = apply_verdicts(_result(amounts=[real, invented]), worked_example_text)

    assert verified.amounts == [real]
    assert counters.claims_dropped == 1


@pytest.mark.gate
def test_a_money_literal_written_across_a_line_break_survives():
    """Whitespace is not fabrication. The same normalisation the span cascade uses applies here,
    so an amount split by a wrapped line is still the amount the source wrote."""
    source = "the $84,000\nannual figure"
    amount = Money(minor_units=8_400_000, currency="USD", as_written="$84,000 annual")

    verified, counters = apply_verdicts(_result(amounts=[amount]), source)

    assert verified.amounts == [amount]
    assert counters.claims_dropped == 0


@pytest.mark.gate
def test_a_resolved_date_with_no_real_receipt_is_dropped(worked_example_text, eval_time):
    """Same reason as `Money`, different damage: a wrong deadline is chased.

    `ResolvedDate` has no confidence field to carry doubt in, so the only two options are keep it
    at full strength or remove it — and an invented window reaching ALG-17's deadline-proximity
    term would read as real urgency about a date nobody set.
    """
    fabricated = _date([_span("the deadline is October 15", 0)], eval_time)

    verified, counters = apply_verdicts(_result(dates_mentioned=[fabricated]),
                                        worked_example_text)

    assert verified.dates_mentioned == []
    assert counters.claims_dropped == 1


@pytest.mark.gate
def test_a_resolved_date_with_a_real_receipt_survives_with_corrected_offsets(
        worked_example_text, eval_time):
    """The other half of the same rule — the drop policy must not eat real dates."""
    quote = "coming up pretty soon"
    truth = worked_example_text.find(quote)
    grounded = _date([_span(quote, 0)], eval_time)

    verified, counters = apply_verdicts(_result(dates_mentioned=[grounded]), worked_example_text)

    assert len(verified.dates_mentioned) == 1
    (receipt,) = verified.dates_mentioned[0].evidence
    assert (receipt.start_offset, receipt.verified) == (truth, True)
    assert counters.claims_dropped == 0


@pytest.mark.gate
def test_a_commitment_with_a_fabricated_receipt_survives_at_half_confidence(
        worked_example_text):
    """Kept, halved, flagged — and the flag is `verified=False` on the span itself.

    There is no `unverified` boolean on a claim and there must not be one: the receipt already
    says whether it was checked, and a second copy of that fact on the parent is a second thing
    to keep in sync. An unverified commitment is still an open loop somebody may be waiting on,
    which is why the policy downgrades it instead of deleting it.
    """
    fabricated = _span("I will send the signed contract on Monday", 0)

    verified, counters = apply_verdicts(_result(commitments=[_commitment([fabricated])]),
                                        worked_example_text)

    (survivor,) = verified.commitments
    assert survivor.confidence_bp == 8000 * 5 // 10
    assert survivor.evidence == [fabricated]
    assert survivor.evidence[0].verified is False
    assert (counters.claims_flagged, counters.claims_dropped) == (1, 0)


@pytest.mark.gate
def test_a_commitment_keeps_its_promise_and_loses_a_fabricated_deadline(
        worked_example_text, span_of, eval_time):
    """The asymmetry that stops a false chase.

    The promise was really made — its own span resolves — but the date attached to it was
    invented. Dropping the `due` leaves `due=None`, which the contract reads as "no date was
    stated": the commitment is tracked as an open loop and can never be escalated as a missed
    one. A false overdue is the second-last nudge a founder reads.
    """
    real = span_of("I still need Finance to confirm")
    invented = _date([_span("by end of day Friday", 0)], eval_time)

    verified, counters = apply_verdicts(
        _result(commitments=[_commitment([real], due=invented)]), worked_example_text)

    (survivor,) = verified.commitments
    assert survivor.due is None
    assert survivor.confidence_bp == 8000
    assert survivor.evidence[0].verified is True
    assert counters.claims_dropped == 1


@pytest.mark.gate
@pytest.mark.parametrize("claim, confidence_bp", [
    (EntityMention(surface_form="Finance", entity_type="organization",
                   evidence=[_span("Finance", 0)], confidence_bp=9000), 9000),
    (DecisionState(subject="renewal", state="blocked", evidence=[_span("Finance", 0)],
                   confidence_bp=7000), 7000),
    (Dependency(blocker="Finance sign-off", blocked="renewal", dependency_type="approval",
                evidence=[_span("Finance", 0)], confidence_bp=6001), 6001),
    (UnclassifiedObservation(proposed_kind="budget_pressure", description="absorbing an increase",
                             evidence=[_span("Finance", 0)], confidence_bp=5555), 5555),
])
def test_every_keep_and_flag_claim_type_is_halved_when_nothing_resolves(claim, confidence_bp):
    """One row per type in the keep column of the policy table, including the open lane.

    The observation lane is span-validated exactly like any other claim (doc 04's rule) — it is
    reviewed by humans, and a review queue seeded with fabricated quotes is a review queue that
    teaches the reviewer to skim.
    """
    field = {EntityMention: "entity_mentions", DecisionState: "decision_states",
             Dependency: "dependencies", UnclassifiedObservation: "unclassified_observations"}
    verified, counters = apply_verdicts(_result(**{field[type(claim)]: [claim]}),
                                        "a source that mentions none of this")

    (survivor,) = getattr(verified, field[type(claim)])
    assert survivor.confidence_bp == confidence_bp * 5 // 10
    assert counters.claims_flagged == 1


@pytest.mark.gate
@pytest.mark.parametrize("source, quote, start, verdict, numerator, denominator", [
    ("Finance must confirm the increase.", "Finance must confirm", 0,
     SpanVerdict.VERIFIED, 1, 1),
    ("Finance must\nconfirm the increase.", "Finance must confirm", 0,
     SpanVerdict.VERIFIED_WHITESPACE, 1, 1),
    ("Please note: Finance must confirm the increase.", "Finance must confirm", 0,
     SpanVerdict.VERIFIED_RELOCATED, 9, 10),
    ("Please note: Finance   must confirm the increase.", "Finance must confirm", 0,
     SpanVerdict.VERIFIED_FUZZY, 7, 10),
    ("Nothing of the sort was ever written down.", "Finance must confirm", 0,
     SpanVerdict.UNVERIFIED, 5, 10),
])
def test_confidence_is_scaled_by_the_grade_in_integer_basis_points(source, quote, start, verdict,
                                                                  numerator, denominator):
    """The multipliers ALG-08 states, applied to a claim rather than to a span.

    7001 is chosen so every row truncates: `7001 * 9 // 10` is 6300, not 6300.9, and a validator
    that reached for a float here would agree with this test on four rows and disagree on the
    cent. Integer basis points end to end is what makes a composed confidence traceable back to
    the weakest source that produced it.
    """
    span = _span(quote, start)
    graded, _ = verify_span(span, source)
    assert graded is verdict, "the row's premise: this source produces this grade"

    verified, _ = apply_verdicts(_result(commitments=[_commitment([span],
                                                                 confidence_bp=7001)]), source)

    assert verified.commitments[0].confidence_bp == 7001 * numerator // denominator


@pytest.mark.gate
def test_a_claim_keeps_both_its_real_receipt_and_its_invented_one(worked_example_text, span_of):
    """A fabricated span beside a real one is DOWNGRADED, never deleted.

    REWRITTEN (D5). This test previously also asserted `confidence_bp == 8000` and
    `claims_flagged == 0` — i.e. that a claim carrying one verbatim quote and one invented
    sentence pays NOTHING for the invention. That assertion was the defect written down: it made
    stapling a real quote beside a false one the cheapest way to launder a fabrication through
    the one unit built to catch it. The pricing now lives in
    `test_a_real_quote_stapled_beside_an_invention_does_not_launder_it`; what survives here is
    what this test was really about and is still true — RETENTION.

    The invented span is not quietly dropped from the claim's receipt list, because a claim
    stripped of its failures looks fully substantiated and the only record that the extractor
    invented a sentence would be gone. It stays, `verified=False`, where V-5 at the publishing
    seam and any human reading the card can see it. Order is preserved too: the receipts render
    in the order the extractor asserted them.
    """
    real = span_of("Finance to confirm")
    invented = _span("Legal countersigned on Tuesday", 0)

    verified, _ = apply_verdicts(
        _result(commitments=[_commitment([invented, real])]), worked_example_text)

    (survivor,) = verified.commitments
    assert [receipt.verified for receipt in survivor.evidence] == [False, True]
    assert survivor.evidence[0].quote == "Legal countersigned on Tuesday"
    assert survivor.evidence[1].quote == "Finance to confirm"


@pytest.mark.gate
def test_summary_judgements_are_never_touched(worked_example_text):
    """intent, stance and topics are what the message MEANT, not what it said.

    They cite nothing, so there is nothing for a span to substantiate and nothing for the policy
    to downgrade. A validator that halved a stance because a neighbouring commitment was
    unverified would be punishing a judgement for the sins of a quote.
    """
    verified, _ = apply_verdicts(
        _result(intent="negotiate", stance="cautious", topics=["renewal", "pricing"],
                questions=["can we absorb the increase?"],
                commitments=[_commitment([_span("invented entirely", 0)])]),
        worked_example_text)

    assert (verified.intent, verified.stance) == ("negotiate", "cautious")
    assert verified.topics == ["renewal", "pricing"]
    assert verified.questions == ["can we absorb the increase?"]


@pytest.mark.gate
def test_all_evidence_keeps_the_failures_and_corrects_the_rest(worked_example_text):
    """The extractor's ledger, not the claim's receipt list.

    Pruning the fabricated spans out of `all_evidence` would make every extraction look perfectly
    cited and would erase the exact trend U2 exists to watch. So the failures stay, unverified,
    beside the corrected ones.
    """
    quote = "Finance to confirm"
    truth = worked_example_text.find(quote)
    misplaced = _span(quote, 0)
    invented = _span("nothing like this was written", 0)

    verified, _ = apply_verdicts(_result(all_evidence=[misplaced, invented]),
                                 worked_example_text)

    first, second = verified.all_evidence
    assert (first.start_offset, first.verified) == (truth, True)
    assert second == invented


@pytest.mark.gate
def test_the_input_extraction_is_left_alone(worked_example_text):
    """A new result comes back; the stored one is what a replay and an audit read.

    Mutating in place would mean the cached extraction on disk silently becomes the validated
    one, and the question "what did the model actually claim?" would no longer have an answer.
    """
    span = _span("Finance to confirm", 0)
    original = _result(commitments=[_commitment([span])])

    verified, _ = apply_verdicts(original, worked_example_text)

    assert original.commitments[0].confidence_bp == 8000
    assert original.commitments[0].evidence[0] == span
    assert original.commitments[0].evidence[0].verified is False
    assert verified.commitments[0].evidence[0].verified is True


@pytest.mark.gate
def test_a_receipt_shared_by_several_claims_is_counted_once(worked_example_text, span_of):
    """Distinct spans, not span references.

    Four claims extracted from one sentence share one frozen `EvidenceSpan`. Counting it four
    times would let a single popular quote swing the monitor that is supposed to be watching the
    extractor, which is the opposite of what a rate is for.
    """
    shared = span_of("Finance to confirm")
    result = _result(
        commitments=[_commitment([shared])],
        decision_states=[DecisionState(subject="renewal", state="blocked", evidence=[shared],
                                       confidence_bp=7000)],
        all_evidence=[shared])

    _, counters = apply_verdicts(result, worked_example_text)

    assert counters.total_spans == 1
    assert counters.verified == 1


# ---------------------------------------------------------------------------------------------
# L1.5.1-U2 · the unverified-rate monitor
# ---------------------------------------------------------------------------------------------


@pytest.mark.gate
@pytest.mark.parametrize("counters, expected_bp, why", [
    (SpanCounters(), 0, "no spans at all — read it beside total_spans, never alone"),
    (SpanCounters(verified=4), 0, "everything cited"),
    (SpanCounters(unverified=4), BP_FULL, "nothing cited"),
    (SpanCounters(verified=3, unverified=1), 2500, "one in four"),
    (SpanCounters(verified=2, unverified=1), 3333, "one in three truncates, never rounds up"),
    (SpanCounters(verified=1, invalid_bounds=1), 5000,
     "unresolvable offsets are a failure too — excluding them would make a broken extractor "
     "look healthy"),
    (SpanCounters(verified_whitespace=1, verified_relocated=1, verified_fuzzy=1, unverified=1),
     2500, "every verified grade counts as resolved, however weak"),
])
def test_unverified_rate_is_the_failed_share_in_integer_basis_points(counters, expected_bp, why):
    """The whole point of the number: a prompt edit that breaks citation behaviour does not
    raise, does not log an error and does not fail a test — it just quietly produces weaker
    signals. This turns that into an observable step change on a date."""
    assert unverified_rate_bp(counters) == expected_bp, why


@pytest.mark.gate
def test_the_counters_tally_the_grades_a_real_extraction_produced(worked_example_text, span_of):
    """One extraction with one span of each interesting grade — the monitor's actual input."""
    exact = span_of("Finance to confirm")
    relocated = _span("absorb the increase", 0)
    invented = _span("Legal countersigned on Tuesday", 0)
    beyond = _span("increase.", len(worked_example_text) - 2)

    _, counters = apply_verdicts(
        _result(all_evidence=[exact, relocated, invented, beyond]), worked_example_text)

    assert (counters.verified, counters.verified_relocated) == (1, 1)
    assert (counters.unverified, counters.invalid_bounds) == (1, 1)
    assert (counters.total_spans, counters.resolved_spans, counters.failed_spans) == (4, 2, 2)
    assert unverified_rate_bp(counters) == 5000


@pytest.mark.gate
@pytest.mark.parametrize("previous_bp, candidate_bp, blocked, why", [
    (1000, 1500, False, "exactly 5 points worse meets the stated bar and ships"),
    (1000, 1501, True, "one basis point past it does not"),
    (1000, 9000, True, "citation behaviour has collapsed"),
    (1000, 200, False, "an improvement never blocks, however large"),
    (0, MAX_RATE_REGRESSION_BP, False, "from a perfect incumbent, the same threshold applies"),
])
def test_the_release_gate_blocks_only_a_real_regression(previous_bp, candidate_bp, blocked, why):
    """"exceeds the previous by more than 5 percentage points" — strictly greater.

    A gate that also blocked the boundary would reject a prompt that met the bar the doc states,
    and a gate that blocked improvements would freeze the prompt it exists to let people change.
    """
    assert rate_regression_blocks_release(previous_bp, candidate_bp) is blocked, why


@pytest.mark.gate
def test_the_counter_record_cannot_be_edited_after_the_fact():
    """Frozen for the same reason a receipt is: a tally somebody can adjust is not a tally."""
    counters = SpanCounters(verified=1)

    with pytest.raises(FrozenInstanceError):
        counters.verified = 99  # type: ignore[misc]


@pytest.mark.gate
def test_every_verdict_has_a_home_in_the_counters():
    """`from_verdicts` keys on the enum's own values, so adding a grade without a matching field
    fails loudly here instead of silently undercounting the rate for a release."""
    counters = SpanCounters.from_verdicts(list(SpanVerdict))

    assert counters.total_spans == len(SpanVerdict)
    assert counters.failed_spans == 2
    assert unverified_rate_bp(counters) == 2 * BP_FULL // len(SpanVerdict)


@pytest.mark.gate
def test_the_module_reads_no_clock_and_needs_none(worked_example_text, span_of, eval_time):
    """Time arrives as a parameter or not at all.

    `apply_verdicts` never asks what today is: it is handed a `ResolvedDate` that already carries
    the `eval_time` it was resolved against, and it verifies the QUOTE behind that date rather
    than re-deriving the date. That is what makes a March decision reproduce in September, and
    it is why the same call twice returns the same thing.
    """
    result = _result(dates_mentioned=[_date([span_of("pretty soon")], eval_time)])

    first, first_counters = apply_verdicts(result, worked_example_text)
    second, second_counters = apply_verdicts(result, worked_example_text)

    assert first == second
    assert first_counters == second_counters
    assert first.dates_mentioned[0].resolved_against == datetime(2026, 1, 14, 9, 0,
                                                                tzinfo=timezone.utc)


# ---------------------------------------------------------------------------------------------
# The invariants the happy path never asserted — the four defects an adversarial read found.
#
# Every test below reproduces a defect that 866 green tests did not see, because each of them
# checked what the module DOES on a well-formed input rather than what it must never allow on a
# hostile one. The extractor is the adversary here: it is the component whose claims this module
# exists to check, so anything it can set and this module does not overwrite is a claim wearing
# a validator's uniform.
# ---------------------------------------------------------------------------------------------


#: A sentence no source in this file contains, phrased the way an invention is phrased: specific,
#: quotable, and exactly the kind of line a card would render as a receipt.
FABRICATED_QUOTE = "we agreed to a full refund with no questions"


def _stamped(quote: str, start: int = 0) -> EvidenceSpan:
    """A span an extractor emitted with `verified=True` ALREADY SET — the hostile input.

    Nothing stops this construction: `EvidenceSpan.verified` is an ordinary field with an
    ordinary default, so the flag that separates "we opened the document and looked" from "the
    model said so" is writable by the model. That is the premise of D1, and it is why these
    tests build the span this way instead of through `span_of`.
    """
    return EvidenceSpan(source_ref=SOURCE_REF, quote=quote, start_offset=start,
                        end_offset=start + len(quote), verified=True)


@pytest.mark.gate
def test_a_fabricated_span_cannot_keep_a_verified_flag_it_arrived_with(worked_example_text,
                                                                      span_of):
    """D1 · the failure branches must REWRITE the flag, not pass the input through.

    A span graded UNVERIFIED that keeps `verified=True` is the worst object this system can
    produce: it is a fabricated sentence carrying the one bit that means "checked against real
    text". V-5 reads that bit as a receipt, so an invention laundered through this module is
    indistinguishable downstream from a quote we actually found. The verdict says UNVERIFIED and
    the counter says 1 — and neither of those travels with the span; the flag does.
    """
    real = span_of("Finance to confirm")
    invented = _stamped(FABRICATED_QUOTE)

    verified, counters = apply_verdicts(
        _result(commitments=[_commitment([real, invented])],
                all_evidence=[real, invented]), worked_example_text)

    assert counters.unverified == 1, "the module DID grade it a fabrication"
    assert verified.all_evidence[1].verified is False, "and the span must carry that verdict"
    assert verified.commitments[0].evidence[1].verified is False


@pytest.mark.gate
def test_a_verify_span_call_strips_a_claimed_flag_on_both_failure_branches(worked_example_text):
    """D1 · the same rule at the single-span entry point, for both ways a span can fail.

    UNVERIFIED and INVALID_BOUNDS are different diagnoses of the same fact — nothing confirmed
    this quote — so a stamp survives neither. INVALID_BOUNDS matters more than it looks: those
    offsets were computed against different text, so the span is not merely unconfirmed, it is
    unconfirmable, and a checkmark on it is a receipt pointing into a document nobody has.
    """
    absent = _stamped(FABRICATED_QUOTE)
    out_of_range = _stamped("increase.", len(worked_example_text) - 2)

    absent_verdict, absent_out = verify_span(absent, worked_example_text)
    bounds_verdict, bounds_out = verify_span(out_of_range, worked_example_text)

    assert absent_verdict is SpanVerdict.UNVERIFIED
    assert absent_out.verified is False
    assert bounds_verdict is SpanVerdict.INVALID_BOUNDS
    assert bounds_out.verified is False


@pytest.mark.gate
def test_stripping_the_flag_changes_nothing_else_about_the_span(worked_example_text):
    """D1 · the span is still testimony. Only the checkmark is removed.

    The quote and the offsets the extractor asserted are kept verbatim, because they are the
    record of WHAT it claimed — the evidence about the extractor that U2's rate is computed
    from. A validator that also rewrote the failing quote would destroy the only artifact that
    can be shown to whoever has to fix the prompt.
    """
    stamped = _stamped(FABRICATED_QUOTE, start=7)

    _, out = verify_span(stamped, worked_example_text)

    assert (out.source_ref, out.quote) == (stamped.source_ref, stamped.quote)
    assert (out.start_offset, out.end_offset) == (stamped.start_offset, stamped.end_offset)
    assert out.verified is False


# ---------------------------------------------------------------------------------------------
# D4 · an amount is graded on its literal AND on its digits
# ---------------------------------------------------------------------------------------------

#: The group's own headline fault, as a source sentence. The literal is real; the number the
#: extractor derived from it is ten times too large.
EIGHT_POINT_FOUR_K = "Total annual commitment of $8.4K under the renewal."


@pytest.mark.gate
def test_an_amount_whose_digits_contradict_its_own_literal_is_dropped():
    """D4 · the Globe fault, which groundedness alone cannot see.

    "$8.4K" IS in the source, so the literal check passes and the amount survives — carrying
    8_400_000 minor units, which is $84,000. Every layer above compares integers and renders
    strings, so the card reads "$8.4K" and the renewal forecast reads $84,000, and the two
    disagree by 10x with no seam that can notice. The literal and the integer must be checked
    against EACH OTHER, not just against the source.
    """
    ten_times_wrong = Money(minor_units=8_400_000, currency="USD", as_written="$8.4K")

    verified, counters = apply_verdicts(_result(amounts=[ten_times_wrong]), EIGHT_POINT_FOUR_K,
                                        locale="en-US")

    assert verified.amounts == []
    assert counters.claims_dropped == 1


@pytest.mark.gate
def test_an_amount_whose_digits_agree_with_its_literal_survives():
    """D4 · the other half. A correct amount must not be collateral damage."""
    correct = Money(minor_units=840_000, currency="USD", as_written="$8.4K")

    verified, counters = apply_verdicts(_result(amounts=[correct]), EIGHT_POINT_FOUR_K,
                                        locale="en-US")

    assert verified.amounts == [correct]
    assert counters.claims_dropped == 0


@pytest.mark.gate
@pytest.mark.parametrize("as_written, source, locale, why", [
    ("$84,000 annual", "the $84,000 annual figure", "en-US",
     "UNPARSEABLE_TOKEN — 'annual' is prose ALG-10 will not read, not a wrong digit"),
    ("$84,000", "the $84,000 figure", None,
     "AMBIGUOUS_SEPARATOR — with no locale, ALG-10 cannot say whether ',' groups or divides"),
])
def test_an_amount_alg_10_refuses_to_parse_is_kept(as_written, source, locale, why):
    """D4 · REFUSING is not CONTRADICTING, and the difference decides whether money survives.

    `parse_money` returns None for a dozen reasons that are all "I will not guess" — a range, a
    trailing word, an ambiguous separator with no locale. None of them is evidence that the
    extractor's integer is wrong. Dropping on refusal would delete every amount ALG-10 happens
    not to read, which on a connection with no declared locale is most of them, and the deletion
    would be invisible: the card simply would not mention the number the message did.
    """
    amount = Money(minor_units=8_400_000, currency="USD", as_written=as_written)

    verified, counters = apply_verdicts(_result(amounts=[amount]), source, locale=locale)

    assert verified.amounts == [amount], why
    assert counters.claims_dropped == 0


# ---------------------------------------------------------------------------------------------
# D5 · the penalty is per receipt, not per claim
# ---------------------------------------------------------------------------------------------


@pytest.mark.gate
def test_a_real_quote_stapled_beside_an_invention_does_not_launder_it(worked_example_text,
                                                                     span_of):
    """D5 · the cheapest laundering attack, priced.

    Under a strongest-verdict rule a claim with one real receipt and one fabricated one costs
    the extractor NOTHING: the real quote sets the grade and the invention rides along at full
    confidence. That makes citing one true sentence a licence to attach any number of false
    ones, which inverts the incentive the whole unit exists to create. ALG-08 states its
    multipliers inside `verify_span` — per SPAN — so a fabricated receipt is a penalty the claim
    pays, once for each of them.
    """
    real = span_of("Finance to confirm")
    invented = _span("Legal countersigned on Tuesday", 0)

    verified, counters = apply_verdicts(
        _result(commitments=[_commitment([real, invented])]), worked_example_text)

    (survivor,) = verified.commitments
    assert survivor.confidence_bp == 8000 * 5 // 10
    assert counters.claims_flagged == 1


@pytest.mark.gate
def test_two_inventions_cost_twice_what_one_does(worked_example_text, span_of):
    """D5 · per receipt means per receipt. Two fabrications are not one fabrication."""
    real = span_of("Finance to confirm")
    one = _span("Legal countersigned on Tuesday", 0)
    two = _span(FABRICATED_QUOTE, 0)

    verified, _ = apply_verdicts(
        _result(commitments=[_commitment([real, one, two])]), worked_example_text)

    assert verified.commitments[0].confidence_bp == 8000 * 5 // 10 * 5 // 10


@pytest.mark.gate
def test_a_claim_whose_receipts_all_resolve_pays_nothing_extra(worked_example_text, span_of):
    """D5 · the guard on the other side: the per-span penalty must fire only on failures."""
    first = span_of("Finance to confirm")
    second = span_of("absorb the increase")

    verified, counters = apply_verdicts(
        _result(commitments=[_commitment([first, second])]), worked_example_text)

    assert verified.commitments[0].confidence_bp == 8000
    assert counters.claims_flagged == 0


# ---------------------------------------------------------------------------------------------
# D7 · step 3 must start inside the region the model measured
#
# ALG-08 step 3 is written `if normalize_ws(source[start:end]) == normalize_ws(quote)`. The code
# anchors at `start` and RE-DERIVES the end, which is a superset. Two of the three tests below
# pin the part of that superset that is RIGHT and say why the doc's literal form is wrong; the
# first pins the part that was WRONG and is now fixed.
# ---------------------------------------------------------------------------------------------

#: A gap longer than the quote, between the model's stated start and the sentence it quoted.
#: The pre-D7 code walked the whole thing and called the result VERIFIED_WHITESPACE.
LEADING_GAP_SOURCE = "A." + "\n" * 40 + "Finance must confirm the increase."


@pytest.mark.gate
def test_step_three_will_not_walk_out_of_the_region_the_model_measured():
    """D7 · the half of the doc's literal form that the code was missing.

    The model says the quote starts at character 2. Characters 2..22 — the region CV-01 says it
    measured — are forty newlines: nothing but whitespace, no part of the sentence it quoted. It
    was forty characters wrong about where it was reading, which is precisely what
    VERIFIED_RELOCATED (9/10) is for.

    Anchoring on "the first non-space character at or after the stated start" with no bound let
    that span skip the entire gap and collect VERIFIED_WHITESPACE — full confidence, no penalty,
    on a measurement that was not close. The doc's `source[start:end]` comparison catches it for
    free, because that slice is all whitespace and normalises to nothing. So step 3 forgives
    whitespace INSIDE the region the model claimed, never a run of it in front.
    """
    quote = "Finance must confirm"
    start = 2
    assert not LEADING_GAP_SOURCE[start:start + len(quote)].strip(), "the fixture's premise"

    verdict, corrected = verify_span(_span(quote, start), LEADING_GAP_SOURCE)

    assert verdict is SpanVerdict.VERIFIED_RELOCATED
    assert LEADING_GAP_SOURCE[corrected.start_offset:corrected.end_offset] == quote


@pytest.mark.gate
def test_step_three_still_re_derives_the_end_because_cv_01_makes_the_stated_end_derived():
    """D7 · why the doc's literal form is WRONG about the end, stated as an executable argument.

    `EvidenceSpan` CV-01 (`contracts/evidence.py::_require_coherent_span`) refuses any span
    where `len(quote) != end_offset - start_offset`. The stated end is therefore not an
    independent measurement at all — it is `start + len(quote)`, a value the constructor
    derives. The doc's step 3 consequently reduces to comparing the quote against a source
    region of EXACTLY the quote's length.

    Whitespace normalisation can only reconcile two strings of different length by collapsing or
    expanding a run. A same-length region cannot contain a collapsed run. So the doc's literal
    step 3 can forgive length-PRESERVING substitutions ("\\n" for " ") and nothing else — while
    its own ACCEPTANCE row asks for "extra whitespace -> VERIFIED_WHITESPACE, offsets
    corrected", which is a length CHANGE. The two halves of the doc contradict each other, and
    the ACCEPTANCE row is the one that describes a real extractor.

    Below is that exact case: the source has a collapsed run, so the doc's literal comparison
    fails on a span that quoted the right sentence from the right place. Grading it
    VERIFIED_FUZZY at 7/10 would price "the model reflowed the whitespace" as though it were
    "the model did not know where it was reading" — which is what step 5 means, and it would
    skip VERIFIED_RELOCATED's 9/10 entirely on the way there.
    """
    source = "Finance   must   confirm the increase."
    span = _span("Finance must confirm", 0)

    literal = source[span.start_offset:span.end_offset]
    assert " ".join(literal.split()) != " ".join(span.quote.split()), \
        "the doc's own step-3 comparison FAILS on this span"

    verdict, corrected = verify_span(span, source)

    assert verdict is SpanVerdict.VERIFIED_WHITESPACE
    assert source[corrected.start_offset:corrected.end_offset] == "Finance   must   confirm"


@pytest.mark.gate
def test_step_three_forgives_whitespace_and_never_a_word():
    """D7 · the guard on the relaxation: re-deriving the end must not forgive CONTENT.

    The needle is the whitespace-normalised quote matched LITERALLY in a whitespace-folded view,
    so the region step 3 accepts equals the quote modulo whitespace and nothing else. A quote
    that differs from the source by a WORD at the stated start is not a transcription artifact,
    and it must fall through to the searching steps like any other unlocated text.
    """
    source = "Finance must approve the increase."
    verdict, _ = verify_span(_span("Finance must confirm", 0), source)

    assert verdict is SpanVerdict.UNVERIFIED


# ---------------------------------------------------------------------------------------------
# D7 · the whole leading-gap class, not one row of it
#
# The bound above (`limit = end_offset`) narrowed the defect instead of closing it. CV-01 makes
# `end_offset` exactly `start + len(quote)`, so bounding the walk by the stated end only refuses
# a gap that is AT LEAST as long as the quote. Every SHORTER gap still gets walked, and a span
# that was one character wrong about where it was reading still collects VERIFIED_WHITESPACE at
# full confidence. This table pins the verdict across the whole gap-length axis and across the
# four whitespace shapes a real prepared email produces, so the class is closed rather than a
# single fixture.
# ---------------------------------------------------------------------------------------------

#: 20 characters. Every gap length below is expressed relative to this so the table reads as
#: "shorter than the quote / exactly as long / longer" rather than as arbitrary integers.
GAP_QUOTE = "Finance must confirm"

#: The four shapes. "mixed" is the realistic one: a wrapped, indented continuation line.
GAP_FILLERS = {"spaces": " ", "newlines": "\n", "tabs": "\t", "mixed": " \n\t"}


def _gap_source(filler: str, length: int) -> str:
    """`"A."` + `length` whitespace characters + the quote + a tail. The stated start is 2."""
    run = (filler * length)[:length]
    return "A." + run + GAP_QUOTE + " the increase."


@pytest.mark.gate
@pytest.mark.parametrize("shape", sorted(GAP_FILLERS))
@pytest.mark.parametrize("gap", [0, 1, 2, len(GAP_QUOTE) - 1, len(GAP_QUOTE), len(GAP_QUOTE) + 1])
def test_step_three_never_forgives_a_leading_gap_of_any_length(gap, shape):
    """A gap of ANY length in front of the quote is a wrong measurement, not a transcription.

    ALG-08 step 3 is `if normalize_ws(source[start:end]) == normalize_ws(quote)`. The model here
    states a start that sits `gap` characters in front of the sentence it quoted, so the region
    it claims to have measured is `gap` characters of whitespace followed by a TRUNCATED prefix
    of the quote — the doc's comparison fails on every row with `gap >= 1`, and the quote is
    verbatim elsewhere in the source, which is the definition of VERIFIED_RELOCATED (9/10).

    `gap == 0` is the control: the region IS the quote, so step 2 takes it as VERIFIED.

    Only the rows where `gap >= len(quote)` were closed by the previous fix. The rows where the
    gap is SHORTER than the quote — 1, 2, 19 — are the defect: the walk still reaches the
    sentence from inside the stated region and awards VERIFIED_WHITESPACE at full confidence for
    a measurement that was up to nineteen characters wrong.
    """
    source = _gap_source(GAP_FILLERS[shape], gap)
    span = _span(GAP_QUOTE, 2)
    expected = SpanVerdict.VERIFIED if gap == 0 else SpanVerdict.VERIFIED_RELOCATED

    verdict, corrected = verify_span(span, source)

    assert verdict is expected
    assert source[corrected.start_offset:corrected.end_offset] == GAP_QUOTE
    assert corrected.start_offset == 2 + gap
