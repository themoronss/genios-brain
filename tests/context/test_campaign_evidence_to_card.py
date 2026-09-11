"""Persisted evidence clears trust; shadow mode is a separate publication gate.

This does NOT manufacture an audit bundle or claim a card was persisted. Actual authorized
publication/card persistence remains unverified; the fixture's observed result is refusal.
"""
from sqlalchemy import text

from genios_engine.reason.publication import build_native_publication
from .test_campaign_evidence_to_decision import compile_campaign
from .test_derived_provenance import provenance_db


def test_persisted_campaign_evidence_clears_trust_but_shadow_execution_cannot_publish_a_card(provenance_db):
    execution, package, facts = compile_campaign(provenance_db, persist=True)
    c = provenance_db
    row = c.execute(text("select confidence_evidence,confidence_freshness,confidence_overall "
                         "from context_situations")).one()
    assert tuple(row) == (65, 50, 50)
    count = c.execute(text("select count(*) from graph_facts")).scalar_one()
    refs = c.execute(text("select count(*),count(distinct event_id) from graph_source_refs "
                          "where extractor_version='derived-provenance.v1'")).one()
    assert tuple(refs) == (count * 7, 7)
    assert facts["campaign.contacted"]["value"] == 7
    assert facts["campaign.awaiting"]["value"] == 7
    assert execution.decision.confidence_bp == 5000
    assert execution.decision.selected_candidate_id is not None
    assert execution.authorizes_delivery is False
    assert execution.request.capability.live_delivery_enabled is False
    # Empty means no persisted proof; never populate it with made-up run/candidate/hash IDs
    # to present the compiler fixture as successful authoritative card persistence.
    assert build_native_publication(execution=execution, audit_bundle={}) is None
