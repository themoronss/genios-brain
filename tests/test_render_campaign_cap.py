"""The declared campaign budget survives the shipped compiler, not just a hand-built template."""
from tests.context.test_derived_provenance import provenance_db
from tests.context.test_campaign_evidence_to_decision import compile_campaign
from genios_engine.reason.adapters.expertise import expertise_capability_manifest
from genios_engine.deliver.render import situation_cap


def test_the_compiled_campaign_carries_its_authored_prose_budget(provenance_db):
    execution, package, facts = compile_campaign(provenance_db)
    template = expertise_capability_manifest(package, root_entity_type="campaign").metadata["render"]
    assert template["situation_cap"] == 140
    assert situation_cap(template) == 140
    prose = template["fallback"]["situation"].format(contacted=7, awaiting=7,
        sent_on="2026-08-11", longest_wait_days=30, quote="")
    assert len(prose) == 130
    assert len(prose) <= situation_cap(template)
