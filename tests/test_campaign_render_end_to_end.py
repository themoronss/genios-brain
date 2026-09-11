"""Shipped campaign corpus, compiled decision and byte-exact source-backed render."""
from genios_engine.deliver.render import _interpolate, _prose_length, render_copy
from genios_engine.deliver.slots import compute_slots
from genios_engine.reason.adapters.expertise import expertise_capability_manifest
from tests.context.test_derived_provenance import provenance_db
from tests.context.test_campaign_evidence_to_decision import compile_campaign
from tests.context.test_support_derived_provenance import NOW
from tests.test_render_compiled_copy import _llm


def test_the_compiled_campaign_keeps_its_full_sentence_and_quote_after_a_rejected_model_draft(provenance_db):
    execution, package, facts = compile_campaign(provenance_db)
    assert execution.decision.confidence_bp == 5000
    template = expertise_capability_manifest(package, root_entity_type="campaign").metadata["render"]
    slots = compute_slots("campaign_awaiting_reply", "The send", facts, NOW)
    quote = facts["campaign.quote"]["value"]
    # Fixed source fixture from compile_campaign; the loader's actual DB verification is
    # independently covered by test_render_verified_quote_loader, not mocked as live proof.
    receipts = [{"event_id": "evt_p0", "quote": quote, "source_verified": True,
                 "from_counterparty": False}]
    expected = _interpolate(template["fallback"]["situation"], slots)
    assert len(expected) > 140
    assert _prose_length(expected, receipts) == 130
    for model in (None, _llm("Initech approved", "Initech funded the send.", ""),
                  _llm("Review the send", expected, "")):
        copy = render_copy(reason_code="campaign_awaiting_reply", template=template,
            facts=facts, slots=slots, quotes=receipts, llm=model)
        assert copy["situation"] == expected
        assert quote in copy["situation"]
        assert "7 people" in copy["situation"] and "7 have not answered" in copy["situation"]
        assert "V-01-trimmed" not in (copy.get("reject_detail") or "")
