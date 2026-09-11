from genios_engine.capture.validate.spans import apply_verdicts
from genios_engine.contracts.extraction import ExtractionResult
from .test_business_noun_contract import candidate


def result_for(facts):
    result = ExtractionResult(intent="inform", stance="neutral", model_snapshot="fixture",
        prompt_version="fixture", schema_version="1", extraction_profile="email",
        input_tokens=0, output_tokens=0, business_facts=facts)
    return result.model_copy(update={"all_evidence": result.evidence_from_claims()})


def test_business_receipts_are_actually_verified_by_alg08_and_fabrications_are_dropped():
    original = result_for([candidate()])
    verified, counters = apply_verdicts(original, "Investor", locale="en_US")
    assert verified.business_facts[0].evidence[0].verified is True
    assert verified.business_facts[0].confidence_bp == 9000
    assert original.business_facts[0].evidence[0].verified is False
    rejected, counters = apply_verdicts(original, "Hello", locale="en_US")
    assert rejected.business_facts == []
    assert counters.claims_dropped == 1


def test_deal_money_is_checked_against_its_own_receipt_not_just_any_text_in_the_message():
    span = dict(source_ref="prepared_content:e", quote="The deal is $100.",
                start_offset=0, end_offset=17, verified=False)
    # Fix the offsets from the actual source, not a model's claimed length.
    span["end_offset"] = len(span["quote"])
    good = candidate("deal.value", evidence=[span])
    bad = candidate("deal.value", evidence=[span],
                    value=dict(minor_units=100000, currency="USD", as_written="$100"))
    unrelated = candidate("deal.value", evidence=[span],
        value=dict(minor_units=20000, currency="USD", as_written="$200"))
    checked, counts = apply_verdicts(result_for([good, bad, unrelated]),
        "The deal is $100. Another deal is $200.", locale="en_US")
    assert [f.value.minor_units for f in checked.business_facts] == [10000]
    assert counts.claims_dropped == 2
