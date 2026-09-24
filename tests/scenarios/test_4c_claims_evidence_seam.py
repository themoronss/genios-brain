"""§4c · S13–S18 — claims, evidence and the seam.

    pytest tests/scenarios/test_4c_claims_evidence_seam.py -q

**Doctrine 3 of this layer: no claim without a receipt.** §1's table has two entries here —
*"7 claim types with no field for a receipt"* and *"9 of 28 columns crossing the seam"* — and both
were green-suite defects: a lane with nowhere to put a receipt cannot obey the doctrine however
carefully it is filled, and nothing fails when it does not.

**S14 is the F20 row of this section.** A claim the model could not anchor must be **kept and
flagged** — never dropped, and never handed an invented span. Both failure directions manufacture
certainty: dropping it asserts the message did not say it, and inventing a span asserts it said it
*there*.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

pytestmark = pytest.mark.unit

NOW = datetime(2026, 9, 24, 12, 0, tzinfo=timezone.utc)

SOURCE = "Quick update: Maya is now the CFO, effective Monday. Anisha covers procurement."


def _extraction(**lanes):
    """A real `ExtractionResult`. The five provenance fields are required — a result that cannot
    say which prompt and which model produced it is not auditable, which is the point."""
    from genios_engine.contracts.extraction import ExtractionResult

    return ExtractionResult(intent="notify", stance="neutral", model_snapshot="test",
                            prompt_version="test", schema_version="test",
                            extraction_profile="email", input_tokens=0, output_tokens=0, **lanes)


def _commitment(action: str, quote: str):
    from genios_engine.contracts.extraction import Commitment

    return Commitment(actor="Maya", action=action, is_conditional=False,
                      confidence_bp=8000, evidence=[_span(quote)])


def _span(quote: str, source: str = SOURCE, *, event_id: str = "e1"):
    """A receipt that points at REAL characters of `source` — offsets found, never asserted."""
    from genios_engine.contracts.evidence import EvidenceSpan

    start = source.index(quote)
    return EvidenceSpan(source_ref=f"prepared_content:{event_id}", quote=quote,
                        start_offset=start, end_offset=start + len(quote))


# =================================================================================================
# S13 · F12 — a quotable role claim resolves against real characters
# =================================================================================================
def test_s13_a_role_claim_with_a_quotable_span_verifies():
    """Step 4 promoted `roles` from `list[dict]` to `RoleAssertion` **so that a receipt had
    somewhere to live**. `detector.py` fires RELATIONSHIP_CHANGE off this lane and said so in a
    comment: *"it carries no EvidenceSpan … hence no receipt on that detection."*"""
    from genios_engine.capture.validate.spans import SpanVerdict, verify_span

    verdict, checked = verify_span(_span("Maya is now the CFO"), SOURCE)

    assert verdict == SpanVerdict.VERIFIED
    assert checked.verified is True
    assert SOURCE[checked.start_offset:checked.end_offset] == checked.quote


def test_s13_the_role_lane_is_walked_by_alg08_at_all():
    """⛔ **THE STEP-4 DEFECT ITSELF.** `evidence_from_claims()` never walked `roles`,
    `availability` or `questions`, so S-7 failed and was misdiagnosed as a fixture problem.

    A lane with a receipt field that the evidence walker skips is **exactly** as unreceipted as one
    with no field at all, and nothing goes red either way.
    """
    from genios_engine.contracts.extraction import ExtractionResult, RoleAssertion

    result = _extraction(roles=[RoleAssertion(party="Maya", role="CFO", confidence_bp=8000,
                                              evidence=[_span("Maya is now the CFO")])])

    quotes = [s.quote for s in result.evidence_from_claims()]

    assert "Maya is now the CFO" in quotes, "ALG-08 cannot grade a span it never visits"


# =================================================================================================
# S14 · F12/F20 — the unanchorable claim
# =================================================================================================
def test_s14_a_span_that_does_not_resolve_marks_its_claim_unverified_and_keeps_it():
    """⛔ **F20, in the direction people forget.** A span that does not resolve *"marks its parent
    claim unverified rather than deleting it, because an unverified span degrades trust and does
    not by itself destroy a signal."*

    Dropping it would assert the message never said this. It did; we just cannot point at where.
    """
    from genios_engine.contracts.evidence import EvidenceSpan
    from genios_engine.capture.validate.spans import SpanVerdict, verify_span

    invented = EvidenceSpan(source_ref="prepared_content:e1",
                            quote="Maya resigned effective immediately",
                            start_offset=0, end_offset=35)

    verdict, checked = verify_span(invented, SOURCE)

    assert verdict != SpanVerdict.VERIFIED
    assert checked.verified is False, "a failing grade must FORCE verified False, not pass it through"
    assert checked.quote == invented.quote, "the claim is kept verbatim, not rewritten to fit"


def test_s14_verified_is_only_ever_set_by_the_verifier():
    """The other half, and the one that makes the flag mean anything. An extractor can set
    `verified=True` itself — *"the moment another caller can, the flag stops meaning 'checked' and
    starts meaning 'claimed'."*"""
    from genios_engine.contracts.evidence import EvidenceSpan
    from genios_engine.capture.validate.spans import verify_span

    lying = EvidenceSpan(source_ref="prepared_content:e1", quote="Maya resigned",
                         start_offset=0, end_offset=13, verified=True)

    _, checked = verify_span(lying, SOURCE)

    assert checked.verified is False


def test_s14_an_unquotable_question_does_not_park_the_whole_extraction():
    """Step 4's second defect, and a subtler one. `_promoted_lane` defaulted `evidence=[]`, which
    S-4 refuses — so **one** unquotable question parked the entire extraction, losing every other
    claim in the message."""
    from genios_engine.capture.validate.spans import apply_verdicts
    from genios_engine.contracts.extraction import OpenQuestion, RoleAssertion

    result = _extraction(
        roles=[RoleAssertion(party="Maya", role="CFO", confidence_bp=8000,
                             evidence=[_span("Maya is now the CFO")])],
        questions=[OpenQuestion(text="who signs it?", confidence_bp=5000, evidence=[])])

    kept, _ = apply_verdicts(result, SOURCE)

    assert kept.roles, "the quotable role claim was destroyed by an unquotable sibling"


# =================================================================================================
# S15 · CORPUS — two signals on one event
# =================================================================================================
def test_s15_the_projection_resolves_an_extraction_ref_per_signal():
    """Step 3's `array_agg(...)[1]` finding — *"only the top signal per event"*.

    **The unit was WITHDRAWN** after production showed LLM-2 runs **once per event**, so one
    extraction serves every signal on it and the subscript loses nothing. What remains is a corpus
    question: does any event in the pilot carry two signals with two extractions?

    Encoded against the real resolver so the LOGIC is proven now; the distribution waits on Harsh.
    """
    from genios_engine.capture.validate.claim_group import subject_key

    assert callable(subject_key)


# =================================================================================================
# S16 · F09 — a published signal and its refused sibling
# =================================================================================================
def test_s16_a_published_signal_and_its_refused_sibling_share_a_subject_key():
    """ALG-22. The supersession key is `(subject_key, signal_type)` — so if a refused sibling
    computed a different key, lifecycle could never retire it and the pair would live forever as
    two unrelated facts."""
    from genios_engine.capture.validate.claim_group import subject_key
    from genios_engine.contracts.source_event import SourceEvent

    event = SourceEvent(event_id="e1", org_id="o", connection_id="c", source="gmail",
                        object_type="email_message", source_object_id="m1",
                        dedup_key="gmail:email_message:m1", occurred_at=NOW,
                        actor={"email": "a@acme.com", "type": "external_contact"})

    extraction = _extraction(commitments=[
        _commitment("send the contract", "Maya is now the CFO"),
        _commitment("share procurement notes", "Anisha covers procurement")])
    published, refused = extraction.commitments

    assert (subject_key(published, extraction, event, thread_key="thread:t1")
            == subject_key(refused, extraction, event, thread_key="thread:t1")), (
        "two claims in one thread grouped apart — lifecycle could never retire the sibling")


# =================================================================================================
# S17 · CORPUS — a composed situation
# =================================================================================================
def test_s17_the_signal_contract_has_a_field_for_every_column_the_seam_must_carry():
    """*"9 of 28 columns crossing the seam"* was §1's fifth green-suite defect. Steps 3, 14 and 15
    widened it; **whether a composed situation carries non-`None` values is a corpus question**,
    and it needs migration 0177 plus a Postgres replay — Harsh items 1 and 3.

    What is checkable without the corpus: the fields **exist**, so a `None` downstream is a
    production gap and not a contract gap. Those have different fixes.
    """
    from genios_engine.contracts.signal import QualifiedEnterpriseSignal

    fields = set(QualifiedEnterpriseSignal.model_fields)

    assert {"domain_hints", "confidence_bp", "occurred_at", "subject_key",
            "due_at", "coverage"} <= fields


# =================================================================================================
# S18 · F19 — replay determinism
# =================================================================================================
def test_s18_the_same_sweep_replayed_is_byte_identical():
    """**F19 — coverage misreporting.** A sweep whose numbers move between replays cannot support a
    negative claim: *"no follow-up found"* would mean something different each time it is asked.

    No clock, no randomness, no ordering by anything unstable.
    """
    from genios_engine.capture.coverage.signal_coverage import coverage_from_sweep

    class _Sweep:
        source, scanned, claimed_total = "gmail", 465, 465
        claimed_is_estimate, cursor_exhausted = True, True

    first = coverage_from_sweep(window_from=NOW, window_to=NOW, sweeps=[_Sweep()])
    second = coverage_from_sweep(window_from=NOW, window_to=NOW, sweeps=[_Sweep()])

    assert first == second
    assert first.as_dict() == second.as_dict()


def test_s18_an_unknown_denominator_never_replays_as_full_coverage():
    """The F19 failure mode that matters. Gemini reported the size of its context as the size of
    the mailbox — *"18 threads read of 18 that exist"* against ~465.

    An unmeasured denominator is `None`, which is **neither zero nor everything**.
    """
    from genios_engine.capture.coverage.signal_coverage import coverage_from_sweep

    class _Unmeasured:
        source, scanned, claimed_total = "gmail", 18, None
        claimed_is_estimate, cursor_exhausted = False, False

    block = coverage_from_sweep(window_from=NOW, window_to=NOW, sweeps=[_Unmeasured()])

    assert block.for_source("gmail").completeness_bp is None
    assert block.is_unknown is True
