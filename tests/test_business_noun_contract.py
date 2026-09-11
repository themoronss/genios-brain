"""Nine business nouns carry typed values, standing and a checkable receipt."""
import pytest
from pydantic import ValidationError

from genios_engine.contracts.extraction import BusinessFact, ExtractionResult
from genios_engine.contracts.units import Money


FIELDS = ("party.role", "relationship.nature", "deal.stage", "deal.value", "person.title",
          "company.industry", "thread.objective", "campaign.objective", "organization.relationship")
SPAN = dict(source_ref="prepared_content:e", quote="Investor", start_offset=0,
            end_offset=8, verified=False)


def candidate(field="party.role", **overrides):
    data = dict(field=field, subject="Jane", value="Investor", standing="observed",
                evidence=[SPAN], confidence_bp=9000)
    if field == "deal.value":
        data["value"] = dict(minor_units=10000, currency="USD", as_written="$100")
    return BusinessFact(**(data | overrides))


@pytest.mark.parametrize("field", FIELDS)
def test_each_business_noun_preserves_its_receipt_and_explicit_standing(field):
    fact = candidate(field)
    assert fact.field == field and fact.standing == "observed"
    assert fact.evidence[0].quote == "Investor"
    assert isinstance(fact.value, Money if field == "deal.value" else str)
    assert candidate(field, standing="judgement").standing == "judgement"


@pytest.mark.parametrize("override", [dict(evidence=[]), dict(subject=" "),
    dict(field="made.up"), dict(standing="certain"), dict(value="unknown"),
    dict(value=" UNKNOWN "), dict(value=""), dict(value=None), dict(value=42),
    dict(confidence_bp=True), dict(confidence_bp=0.9), dict(confidence_bp=10001)])
def test_an_unsupported_business_claim_cannot_be_constructed(override):
    with pytest.raises((ValidationError, TypeError, ValueError)):
        candidate(**override)


def test_only_deal_value_accepts_typed_money_and_never_a_bare_amount():
    with pytest.raises((ValidationError, TypeError, ValueError)):
        candidate("deal.value", value="100 USD")
    with pytest.raises((ValidationError, TypeError, ValueError)):
        candidate(value=dict(minor_units=10000, currency="USD", as_written="$100"))


def test_business_receipts_survive_the_existing_extraction_envelope_and_old_cache_rows():
    common = dict(intent="inform", stance="neutral", model_snapshot="fixture",
                  prompt_version="fixture", schema_version="1", extraction_profile="email",
                  input_tokens=0, output_tokens=0)
    assert ExtractionResult(**common).business_facts == []
    result = ExtractionResult(**common, business_facts=[candidate()])
    restored = ExtractionResult.model_validate_json(result.model_dump_json())
    assert restored.business_facts == result.business_facts
    assert restored.evidence_from_claims() == result.business_facts[0].evidence
