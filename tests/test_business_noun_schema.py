import json

from genios_engine.capture.semantic.schema_gen import generate_schema_block
from .test_business_noun_contract import FIELDS


def test_the_generated_business_schema_lists_typed_values_and_not_an_untyped_escape_hatch():
    [fact] = json.loads(generate_schema_block())["business_facts"]
    for field in FIELDS:
        assert field in fact["field"]
    assert "observed" in fact["standing"] and "judgement" in fact["standing"]
    assert "deal.value" in fact["value"]
    for money_field in ("minor_units", "currency", "as_written"):
        assert money_field in fact["value"]
    assert "any JSON" not in fact["value"]
    assert "omit" in fact["evidence"][0]["verified"]
