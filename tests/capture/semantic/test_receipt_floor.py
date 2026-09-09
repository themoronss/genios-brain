"""M1.C2.L-logic.V0.U05 · a receipt must be capable of substantiating something.

    pytest tests/capture/semantic/test_receipt_floor.py -q

WHAT A 96% VERIFICATION RATE WAS HIDING. `LIVE_RUN.md` reported that L1's span verification was
near-total and called L1 the strongest layer. Reading the actual spans changed that verdict. The
validator checks that the quoted text EXISTS in the source — that is its whole job, and it does it
correctly. It does not check that the text can mean anything, and nothing downstream did either.

Measured on the pilot:

  * 49 signals whose entire receipt is a bare datetime literal. `"2026-07-24T12:30:00+05:30"`
    stored as a `deadline_stated`. A timestamp proves a timestamp was printed. It does not
    evidence that anybody stated a deadline.
  * `"Hi Rohit,"` stored THREE times as a `relationship_change`.
  * 39 spans under 25 characters.

A SHAPE FLOOR, NOT A JUDGEMENT. Every rule is decided by looking at the characters — no model, no
similarity, no embedding — for the same reason ALG-08 refuses fuzzy matching one module over. A
floor that reasons about meaning starts refusing sentences it finds unconvincing, and that is a
much worse failure than the one it fixes. The second block below is where that discipline is
pinned: everything a real message actually says must pass.
"""

from __future__ import annotations

import pytest

from genios_engine.capture.semantic.evidence_binder import (
    DATE_BEARING_FIELDS,
    ClaimDraft,
    bind_evidence,
    substantive,
)
from genios_engine.contracts.evidence import EvidenceSpan

pytestmark = pytest.mark.unit

SOURCE_REF = "prepared_content:evt_floor"


def draft(claim_text: str, *, field: str = "commitments",
          evidence: tuple[EvidenceSpan, ...] = ()) -> ClaimDraft:
    return ClaimDraft(field=field, claim_text=claim_text, confidence_bp=8_000,
                      evidence=evidence)


def span_for(quote: str, text: str) -> EvidenceSpan:
    start = text.find(quote)
    assert start >= 0, f"bad fixture quote {quote!r}"
    return EvidenceSpan(source_ref=SOURCE_REF, quote=quote, start_offset=start,
                        end_offset=start + len(quote), verified=False)


# =============================================================================================
# The strings that were being accepted.
# =============================================================================================
@pytest.mark.parametrize("quote", [
    "2026-07-24T12:30:00+05:30",              # 49 of these on the pilot
    "Wed 5 Aug 2026 2:15pm - 2:45pm (IST)",   # a calendar window, whole
    "14 August",
    "Aug 8",
    "Friday",
    "08/09/2026",
    "12:30",
])
def test_a_bare_datetime_cannot_be_a_receipt(quote):
    assert substantive(quote) is False


@pytest.mark.parametrize("quote", [
    "Hi Rohit,",                              # three `relationship_change` signals
    "Hello,",
    "Dear Sir,",
    "Hey Priya",
    "Good morning,",
])
def test_a_bare_salutation_cannot_be_a_receipt(quote):
    assert substantive(quote) is False


def test_an_empty_or_whitespace_quote_cannot_be_a_receipt():
    assert substantive("") is False
    assert substantive("   \n\t ") is False


# =============================================================================================
# And everything a real message says must still pass. This is the half that keeps the floor a
# floor rather than an opinion.
# =============================================================================================
@pytest.mark.parametrize("quote", [
    "Considering 14 August as the last date",          # a date IN a clause
    "Please confirm by Friday.",
    "Open to the intro?",                              # four words, a real approval request
    "Hi Rohit, the invoice is attached",               # a salutation that opens a sentence
    "I'll send the deck tomorrow.",
    "we're giving you six months free on Composio's Growth plan",
    "As we can see the need of the product, we can expect the numbers to hit nearly ~*$2-3k MRR*.",
    "$599/month",                                      # money is not a date
    "Q3",
])
def test_a_real_sentence_passes(quote):
    """Every one of these carries a word outside the patterns, which is exactly how a real
    sentence passes a floor this narrow."""
    assert substantive(quote) is True


def test_the_floor_never_looks_at_meaning():
    """Nonsense with a verb passes, because judging plausibility is not this unit's job and a
    floor that did would be refusing claims on taste."""
    assert substantive("The purple deadline apologised to Tuesday.") is True


# =============================================================================================
# Wired into the binder.
# =============================================================================================
TEXT = "Hi Rohit,\nThe call is at 2026-07-24T12:30:00+05:30 and I'll send the deck tomorrow.\n"


def bind(*drafts, text: str = TEXT):
    return bind_evidence(drafts, prepared_text=text, source_ref=SOURCE_REF)


def test_a_claim_standing_only_on_a_timestamp_is_refused():
    out = bind(draft("meeting time", evidence=(span_for("2026-07-24T12:30:00+05:30", TEXT),)))

    assert out.claims == ()
    assert out.counters.unsubstantive == 1


def test_a_claim_standing_only_on_a_greeting_is_refused():
    out = bind(draft("relationship", evidence=(span_for("Hi Rohit,", TEXT),)))

    assert out.claims == ()
    assert out.counters.unsubstantive == 1


def test_a_claim_keeps_its_real_receipt_and_loses_only_the_fragment():
    """Per receipt, not per claim — the same rule the history guard follows. A timestamp stapled
    beside a real sentence must not cost the sentence, and must not ride in on it."""
    real = span_for("I'll send the deck tomorrow.", TEXT)
    stamp = span_for("2026-07-24T12:30:00+05:30", TEXT)

    out = bind(draft("send the deck", evidence=(real, stamp)))

    assert len(out.claims) == 1
    assert out.claims[0].evidence == (real,)
    assert out.counters.unsubstantive == 0


def test_thin_receipts_are_counted_apart_from_hallucinations_and_history():
    """Three different failures, three counters. `no_evidence` blocks a prompt release and must
    not be inflated by a model that cited a real but useless fragment."""
    out = bind(draft("the moon is a hologram"),
               draft("greeting", evidence=(span_for("Hi Rohit,", TEXT),)))

    assert out.counters.no_evidence == 1
    assert out.counters.unsubstantive == 1
    assert out.counters.quoted_history == 0


def test_history_outranks_shape():
    """A quoted timestamp is refused for being somebody else's message, not for being thin.
    History is the stronger and more useful fact, so it is checked first."""
    reply = "Thanks.\nOn Sat, 8 Aug 2026 at 14:22, X wrote:\n> 2026-07-24T12:30:00+05:30\n"
    out = bind(draft("t", evidence=(span_for("2026-07-24T12:30:00+05:30", reply),)), text=reply)

    assert out.counters.quoted_history == 1
    assert out.counters.unsubstantive == 0


def test_the_denominator_survives_the_new_drop():
    out = bind(draft("greeting", evidence=(span_for("Hi Rohit,", TEXT),)),
               draft("send the deck", evidence=(span_for("I'll send the deck tomorrow.", TEXT),)))

    assert out.counters.claims_in == 2
    assert out.counters.bound == 1


# =============================================================================================
# THE LANE SCOPE — retired U05 did not have it, and the golden corpus caught that within one run.
#
# U05 applied the datetime rule to every lane. `tests/golden/l1/test_golden_corpus.py` failed
# with `document_msa_extract: date {'as_written': 'October 15, 2026'} not extracted`, and it was
# right: in an MSA, "October 15, 2026" is not a fragment standing in for a claim — it IS the
# claim. A floor that cannot tell "the receipt is a date" from "the claim is a date" refuses
# correct extractions. U05 retired; U07 scopes the rule to the lane.
# =============================================================================================
def test_a_date_literal_is_a_complete_receipt_for_a_date_claim():
    """The golden corpus case, stated as a unit test so the regression cannot return silently."""
    assert substantive("October 15, 2026", "dates_mentioned") is True
    assert substantive("2026-07-24T12:30:00+05:30", "dates_mentioned") is True


def test_a_commitments_own_due_date_is_a_date_claim_too():
    """`commitments.due` is bound under its own label precisely so a dropped deadline is legible
    as a dropped deadline. Its receipt is the date it was written as."""
    assert substantive("October 15, 2026", "commitments.due") is True


def test_the_same_literal_is_still_refused_in_every_other_lane():
    """The scope is a scope, not a hole. The 49 pilot signals were `deadline_stated`,
    `financial_obligation` and friends — none of them a date lane."""
    for field in ("commitments", "entity_mentions", "decision_states", "dependencies",
                  "unclassified_observations", "amounts", None):
        assert substantive("2026-07-24T12:30:00+05:30", field) is False, field


def test_a_greeting_is_refused_in_every_lane_including_the_date_ones():
    """No lane's claim is a salutation, so that rule is deliberately unscoped."""
    for field in (*DATE_BEARING_FIELDS, "commitments", "entity_mentions", None):
        assert substantive("Hi Rohit,", field) is False, field


def test_the_binder_reads_the_lane_off_the_draft():
    """End to end: the same span, the same text, two lanes, two outcomes."""
    text = "The agreement is dated October 15, 2026 and renews annually.\n"
    span = span_for("October 15, 2026", text)

    kept = bind(draft("effective date", field="dates_mentioned", evidence=(span,)), text=text)
    refused = bind(draft("a promise", field="commitments", evidence=(span,)), text=text)

    assert len(kept.claims) == 1
    assert refused.claims == ()
    assert refused.counters.unsubstantive == 1
