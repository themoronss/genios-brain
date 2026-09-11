from genios_engine.context.qes_adapter import adapt_qes_extraction
from genios_engine.capture.validate.spans import apply_verdicts
from tests.test_business_noun_validation import parse, payload_fact, TEXT


def test_verified_business_facts_cross_the_active_qes_adapter_with_standing_and_spans():
    parsed = parse([payload_fact(), payload_fact("deal.value", standing="judgement")])
    verified, _ = apply_verdicts(parsed.result, TEXT, locale="en_US")
    adapted = adapt_qes_extraction(verified, confidence_bp=9000)
    assert len(adapted.fact_candidates) == 2
    role, amount = adapted.fact_candidates
    assert role["subject"] == "Jane" and role["field"] == "party.role"
    assert role["standing"] == "observed" and role["business_fact"] is True
    assert role["evidence_text"] == "Jane is an Investor."
    assert role["evidence_spans"] == [s.model_dump(mode="json") for s in verified.business_facts[0].evidence]
    assert amount["value"] == dict(minor_units=10000, currency="USD", as_written="$100")
    assert amount["standing"] == "judgement"
    assert adapted.input_tokens == adapted.output_tokens == 0


def test_unverified_business_receipts_cannot_be_laundered_into_the_graph_candidate_lane():
    adapted = adapt_qes_extraction(parse([payload_fact()]).result, confidence_bp=9000)
    assert adapted.fact_candidates == []
