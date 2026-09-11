"""Typed business amounts retain the currency and literal after graph persistence."""
import json

import pytest
from sqlalchemy import text

from genios_engine.deliver.render import render_copy
from genios_engine.deliver.slots import compute_slots, _money
from .test_business_fact_store import fact_store
from .test_support_derived_provenance import NOW


@pytest.mark.parametrize("minor,currency,literal", [
    (8400000, "USD", "$84,000"), (125050, "EUR", "EUR 1,250.50"),
    (84000, "JPY", "JPY 84,000"), (0, "USD", "$0"),
])
def test_a_persisted_business_amount_renders_its_source_literal_without_becoming_dollars(fact_store, minor, currency, literal):
    value = dict(minor_units=minor, currency=currency, as_written=literal)
    with fact_store.engine.begin() as c:
        fact_store.write_fact(c, org_id="o", subject_node_id="deal", field="deal.value",
            value=value, value_type="money", confidence=0.85, occurred_at=NOW, event_id="e",
            evidence={"text":literal, "standing":"observed"}, source="gmail", authority_rank=2)
        row = c.execute(text("select value from graph_facts where field='deal.value'")).one()
    facts = {"deal.value":{"value":json.loads(row.value)}}
    slots = compute_slots("stalled_deal", "Acme", facts, NOW)
    assert slots["money"] == literal
    copy = render_copy(reason_code="stalled_deal", template={"fallback":{
        "headline":"Review {entity}", "situation":"Amount stated: {money}", "artifact":""}},
        facts=facts, slots=slots, llm=None)
    assert copy["situation"] == "Amount stated: " + literal


@pytest.mark.parametrize("value", [{}, {"as_written":"$100"},
    {"minor_units":10000,"currency":"USD","as_written":""},
    {"minor_units":True,"currency":"USD","as_written":"$100"}])
def test_malformed_money_does_not_gain_a_renderable_amount(value):
    assert _money(value) is None


def test_existing_numeric_amount_slots_keep_their_legacy_format():
    assert _money(84000) == "$84k"
    assert _money("100") == "$100"
