import pytest

from genios_engine.capture.semantic import extractor as ex
from genios_engine.capture.validate.spans import apply_verdicts
from .test_business_noun_contract import FIELDS
from .test_business_noun_prompt import request_for


TEXT = "Jane is an Investor. We are raising a $100 seed investment."


def payload_fact(field="party.role", **overrides):
    quote = "We are raising a $100 seed investment." if field == "deal.value" else "Jane is an Investor."
    value = dict(minor_units=10000, currency="USD", as_written="$100") if field == "deal.value" else "Investor"
    return dict(field=field, subject="Jane", value=value, standing="observed",
        confidence_bp=9000, evidence=[dict(quote=quote, start_offset=TEXT.index(quote),
            end_offset=TEXT.index(quote) + len(quote))]) | overrides


def parse(facts):
    req = request_for(TEXT)
    return ex.parse_response(dict(intent="inform", stance="neutral", business_facts=facts),
        request=req, call=ex.assemble_call(req, nonce="deadbeefcafe0001"),
        model_snapshot="fixture", input_tokens=0, output_tokens=0)


@pytest.mark.parametrize("field", FIELDS)
def test_each_business_field_is_parsed_bound_and_verified_in_the_existing_lane(field):
    parsed = parse([payload_fact(field)])
    assert parsed.result is not None
    [fact] = parsed.result.business_facts
    assert fact.field == field and fact.evidence[0].verified is False
    checked, _ = apply_verdicts(parsed.result, TEXT, locale="en_US")
    assert checked.business_facts[0].evidence[0].verified is True
    assert parsed.diagnostics.claims_offered == 1


@pytest.mark.parametrize("bad", [dict(field="invented.field"), dict(value="unknown"),
    dict(value=42), dict(standing="certain"), dict(confidence_bp=0.9), dict(evidence=[]),
    dict(evidence=[dict(quote="Made up founder role", start_offset=0, end_offset=20)])])
def test_one_malformed_business_fact_does_not_delete_its_valid_sibling(bad):
    parsed = parse([payload_fact(), payload_fact(**bad)])
    assert parsed.result is not None
    # The parser never stamps verified=True. ALG-08 owns fabricated-receipt removal;
    # exercising that real seam avoids moving verification into the extraction model step.
    if bad.get("evidence") and bad["evidence"][0]["quote"] == "Made up founder role":
        assert len(parsed.result.business_facts) == 2
        assert not any(s.verified for f in parsed.result.business_facts for s in f.evidence)
    else:
        assert len(parsed.result.business_facts) == 1
    checked, _ = apply_verdicts(parsed.result, TEXT, locale="en_US")
    assert len(checked.business_facts) == 1
    assert parsed.diagnostics.claims_offered == 2
    assert checked.business_facts[0].value == "Investor"
    assert checked.business_facts[0].evidence[0].verified is True
