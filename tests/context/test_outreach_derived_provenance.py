"""The campaign receipt list is not its twenty-item display preview."""
from contextlib import contextmanager
from types import SimpleNamespace

from sqlalchemy import text

from .test_derived_provenance import provenance_db
from .test_support_derived_provenance import _fact_schema, NOW
from .test_campaign_silence import campaign, rows
from genios_engine.context import outreach_situations as outreach


def test_a_campaign_retains_all_source_events_beyond_its_display_preview():
    members = [f"p{i}" for i in range(25)]
    grouping = campaign(members)
    [finding] = outreach.read_campaign_silence(rows(
        waiting={member: 30 for member in members}, campaigns=(grouping,)), NOW, {})
    assert len(finding.inputs["events"]) == 20
    assert finding.event_ids == grouping.event_ids
    assert finding.evidence_nodes == tuple(members)


def test_an_outreach_finding_reads_the_events_of_its_actual_fact_subject(provenance_db):
    _fact_schema(provenance_db)
    provenance_db.execute(text("alter table graph_facts add column valid_to timestamp"))
    provenance_db.execute(text("insert into graph_facts (fact_version_id,org_id,subject_node_id,status) values ('original-fact','o','person','active')"))
    finding = outreach._Finding(concerns_node="person")
    receipts = outreach._finding_receipts(provenance_db, org_id="o", finding=finding)
    assert [r.event_id for r in receipts] == ["e1"]


def test_the_outreach_refresh_actually_writes_the_campaign_receipts(provenance_db, monkeypatch):
    _fact_schema(provenance_db)
    finding = outreach._Finding(anchor="campaign", canonical_key="campaign:fixture",
        display_name="Campaign", correlation_id="campaign:fixture", concerns_node="person",
        facts=[("campaign.contacted", 2, "number")], missing=[], inputs={"events": ["e1","e2"]})
    # Compatible historical input also has to work; the new complete field takes precedence
    # for real readings, while old fixture/persisted shapes carry only inputs.events.
    @contextmanager
    def begin():
        yield provenance_db
    store = SimpleNamespace(engine=SimpleNamespace(begin=begin),
        find_or_create_node=lambda *a, **k: "anchor", write_edge=lambda *a, **k: None)
    monkeypatch.setattr(outreach, "_gather", lambda *a, **k: ({}, {}, {}))
    monkeypatch.setattr(outreach, "READINGS", (("campaign", lambda *a: [finding]),))
    monkeypatch.setattr(outreach, "domains_declaring", lambda _: ("admin",))
    monkeypatch.setattr(outreach, "_upsert", lambda *a, **k: None)
    monkeypatch.setattr(outreach, "_reconcile", lambda *a, **k: 0)
    outreach.refresh_state_situations(store, "o", now=NOW)
    refs = provenance_db.execute(text("select event_id,source from graph_source_refs where fact_version_id='fv_desk_o_anchor_campaign.contacted' order by event_id")).all()
    assert refs == [("e1", "gmail"), ("e2", "gcal")]
