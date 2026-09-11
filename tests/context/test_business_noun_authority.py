"""The real active committer writes the right business subject, rank and receipt."""
import json
from datetime import timedelta

import pytest
from sqlalchemy import text

from genios_engine.context import pipeline
from genios_engine.context.extract.extractor import Extraction
from .test_business_fact_store import fact_store
from .test_support_derived_provenance import NOW


TEXT = "Jane Investor at example.com. This thread is for fundraising, not selling. Seed One aims to raise $100."


@pytest.fixture
def business_store(fact_store, monkeypatch):
    with fact_store.engine.begin() as c:
        c.execute(text("""create table graph_nodes (node_id text primary key, version integer,
            org_id text, node_type text, canonical_key text, display_name text,
            identity_strength text, created_by_event_id text, valid_to text)"""))
        c.execute(text("""create table graph_aliases (org_id text, alias_type text, alias_key text,
            node_id text, origin text, created_by_event_id text, unique(org_id,alias_type,alias_key))"""))
        for node, kind, key, label in [("jane", "person", "jane@example.com", "Jane"),
            ("company", "company", "example.com", "Example Capital"),
            ("campaign", "campaign", "campaign:seed", "Seed One"),
            ("firm", "organization", "org:example", "Example Firm")]:
            c.execute(text("insert into graph_nodes (node_id,version,org_id,node_type,canonical_key,display_name) values (:n,1,'o',:t,:k,:d)"),
                      dict(n=node,t=kind,k=key,d=label))
    # Outbox/correlation are separate tested layers; identity resolution and fact/ref SQL are real.
    monkeypatch.setattr(fact_store, "bump_version", lambda *a: 1)
    monkeypatch.setattr(fact_store, "write_change", lambda *a, **kw: None)
    monkeypatch.setattr(fact_store, "write_edge", lambda *a, **kw: None)
    monkeypatch.setattr(pipeline, "correlate_event", lambda *a, **kw: [])
    monkeypatch.setattr(pipeline, "close_loops_for_reply", lambda *a, **kw: None)
    return fact_store


def business_fact(field="thread.objective", subject="thread", value="fundraising", standing="observed"):
    return dict(field=field, subject=subject, value=value, standing=standing, business_fact=True,
        evidence_text=TEXT, evidence_spans=[dict(source_ref="prepared_content:e", quote=TEXT,
            start_offset=0, end_offset=len(TEXT), verified=True)])


def commit(store, facts, *, at=NOW, roles=None, objective=None, relationships=None, recipients=None):
    ex = Extraction(ok=True, relevance=0.9, noise_type="none", domains=[],
        entity_mentions=[], fact_candidates=facts, commitments=[], questions=[], observations=[],
        roles=roles or [], objective=objective or {}, relationships=relationships or [])
    return pipeline.process_event(org_id="o", event_id="e", source="gmail", content=TEXT,
        sender_email="jane@example.com", sender_name="Jane", recipient_emails=recipients or [],
        thread_id="t", occurred_at=at, llm=None, store=store, qualified_extraction=ex)


@pytest.mark.parametrize("reverse", [False, True])
def test_the_active_committer_preserves_observation_authority_in_both_write_orders(business_store, reverse):
    writes = [(business_fact(), NOW-timedelta(days=1)),
              (business_fact(value="selling", standing="judgement"), NOW)]
    for fact, at in reversed(writes) if reverse else writes:
        commit(business_store, [fact], at=at)
    with business_store.engine.connect() as c:
        row = c.execute(text("select f.*,n.node_type from graph_facts f join graph_nodes n on n.node_id=f.subject_node_id where f.field='thread.objective' and f.status='active'")).mappings().one()
        assert row["node_type"] == "thread"
        assert json.loads(row["value"]) == "fundraising"
        assert (row["authority_rank"],row["confidence"]) == (2,0.85)
        receipt = c.execute(text("select evidence from graph_source_refs where fact_version_id=:f"), {"f":row["fact_version_id"]}).scalar_one()
        evidence = json.loads(receipt)
        assert evidence["standing"] == "observed"
        assert evidence["spans"][0]["quote"] == TEXT


@pytest.mark.parametrize("field,subject,kind,value", [
    ("party.role","Jane","person","investor"),
    ("relationship.nature","jane@example.com","person","investor"),
    ("person.title","Jane","person","Partner"),
    ("company.industry","example.com","company","venture capital"),
    ("deal.stage","example.com","deal","seed"),
    ("deal.value","example.com","deal",dict(minor_units=10000,currency="USD",as_written="$100")),
    ("campaign.objective","Seed One","campaign","fundraising"),
    ("organization.relationship","Example Firm","organization","investor"),
])
def test_business_facts_land_on_the_named_typed_subject_not_the_sender(business_store,field,subject,kind,value):
    commit(business_store,[business_fact(field,subject,value,"judgement")])
    with business_store.engine.connect() as c:
        row = c.execute(text("select f.*,n.node_type from graph_facts f join graph_nodes n on n.node_id=f.subject_node_id where f.field=:f and f.status='active'"),dict(f=field)).mappings().one()
        assert row["node_type"] == kind
        assert row["authority_rank"] == 1 and row["confidence"] == 0.4
        assert json.loads(row["value"]) == value
        assert row["value_type"] == ("money" if field == "deal.value" else "string")


def test_an_unresolved_business_subject_is_not_silently_assigned_to_the_sender(business_store):
    commit(business_store,[business_fact("person.title","Another Jane","CEO")])
    with business_store.engine.connect() as c:
        assert c.execute(text("select count(*) from graph_facts where field='person.title'")).scalar_one() == 0


def test_legacy_role_interpretation_cannot_overwrite_a_stated_business_role(business_store):
    commit(business_store,[business_fact("party.role","Jane","investor")],
        roles=[dict(party="jane@example.com",role="counterparty",evidence_text=TEXT)])
    with business_store.engine.connect() as c:
        row = c.execute(text("select value,authority_rank from graph_facts where field='party.role' and status='active'")).one()
        assert json.loads(row.value) == "investor" and row.authority_rank == 2


def test_legacy_relationship_interpretation_cannot_overwrite_a_stated_relationship(business_store):
    commit(business_store,[business_fact("relationship.nature","Jane","investor")],
        relationships=[dict(party="jane@example.com",nature="customer",evidence_text=TEXT)])
    with business_store.engine.connect() as c:
        row = c.execute(text("select value,authority_rank from graph_facts where field='relationship.nature' and status='active'")).one()
        assert json.loads(row.value) == "investor" and row.authority_rank == 2


def test_a_legacy_objective_without_explicit_standing_is_a_judgement(business_store):
    commit(business_store,[],objective=dict(type="fundraising",evidence_text=TEXT),
           recipients=["person@gmail.com"])
    with business_store.engine.connect() as c:
        row = c.execute(text("select authority_rank,confidence from graph_facts where field='thread.objective' and status='active'")).one()
        assert (row.authority_rank,row.confidence) == (1,0.4)
