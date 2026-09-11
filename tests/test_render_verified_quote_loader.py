"""Only bytes found in the same tenant's retained source earn the quote allowance."""
import json
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, text

from genios_engine.deliver.card_builder import load_evidence_quotes

QUOTE = 'We sent the deck — "please review".\n' + 'Supporting material remains attached. ' * 10


@pytest.fixture
def quote_store():
    engine = create_engine("sqlite://")
    with engine.begin() as c:
        for sql in (
            "create table graph_nodes (org_id text,node_id text,node_type text,canonical_key text,valid_to text)",
            "create table graph_edges (org_id text,from_node_id text,to_node_id text,edge_type text,valid_to text)",
            "create table graph_observations (org_id text,observation_id text,subject_node_id text,created_by_event_id text,kind text,occurred_at text,status text)",
            "create table graph_source_refs (org_id text,observation_id text,event_id text,evidence text)",
            "create table source_events (org_id text,event_id text,parent_object_id text,actor text,visibility_scope text,visibility_principals text)",
            "create table prepared_content (org_id text,event_id text,clean_text text)",
        ):
            c.execute(text(sql))
        c.execute(text("insert into graph_nodes values ('o','p','person','p@example.com',null)"))
        c.execute(text("insert into graph_observations values ('o','obs','p','e','request','2026-08-11T12:00:00+00:00','active')"))
        c.execute(text("insert into graph_source_refs values ('o','obs','e',:evidence)"), {"evidence": json.dumps({"text": QUOTE})})
        c.execute(text("insert into source_events values ('o','e',null,'{\"email\":\"owner@example.com\"}','org','[]')"))
        c.execute(text("insert into prepared_content values ('o','e',:body)"), {"body": "Subject: deck\n" + QUOTE})
    yield SimpleNamespace(engine=engine)
    engine.dispose()


def test_a_verified_source_quote_keeps_every_byte_beyond_300_characters(quote_store):
    [quote] = load_evidence_quotes(quote_store, "o", "p", identities=("owner@example.com",))
    assert quote["quote"] == QUOTE
    assert quote["source_verified"] is True
    assert quote["event_id"] == "e"
    assert quote["from_counterparty"] is False


def test_another_tenants_text_cannot_verify_a_quote(quote_store):
    with quote_store.engine.begin() as c:
        c.execute(text("update prepared_content set org_id='other'"))
    [quote] = load_evidence_quotes(quote_store, "o", "p")
    assert quote["source_verified"] is False


def test_a_missing_verification_table_retains_the_previous_quote_path(quote_store):
    with quote_store.engine.begin() as c:
        c.execute(text("drop table prepared_content"))
    [quote] = load_evidence_quotes(quote_store, "o", "p")
    assert quote["quote"] == QUOTE.strip()[:300]
    assert quote["source_verified"] is False


def test_a_campaign_quote_is_loaded_from_its_derived_fact_receipt_without_person_observations(quote_store):
    with quote_store.engine.begin() as c:
        c.execute(text("delete from graph_observations"))
        c.execute(text("create table graph_facts (org_id text,subject_node_id text,fact_version_id text,field text,value text,status text,valid_to text)"))
        c.execute(text("alter table graph_source_refs add column fact_version_id text"))
        c.execute(text("alter table source_events add column occurred_at text"))
        c.execute(text("update graph_source_refs set fact_version_id='fv_quote',observation_id=null"))
        c.execute(text("insert into graph_facts values ('o','p','fv_quote','campaign.quote',:quote,'active',null)"), {"quote": json.dumps(QUOTE)})
    [quote] = load_evidence_quotes(quote_store, "o", "p", identities=("owner@example.com",))
    assert quote["quote"] == QUOTE
    assert quote["source_verified"] is True
    assert quote["from_counterparty"] is False
