import json
from sqlalchemy import text
from genios_engine.deliver.card_builder import load_evidence_quotes
from .test_render_verified_quote_loader import quote_store, QUOTE


def test_recipient_presence_does_not_hide_an_older_actual_quote(quote_store):
    with quote_store.engine.begin() as c:
        for i in range(10):
            c.execute(text("insert into graph_observations values ('o',:id,'p','e','event_presence','2026-09-10','active')"),dict(id=f"presence{i}"))
            c.execute(text("insert into graph_source_refs values ('o',:id,'e','{}')"),dict(id=f"presence{i}"))
    quotes = load_evidence_quotes(quote_store,"o","p",limit=1)
    assert len(quotes) == 1 and quotes[0]["quote"] == QUOTE


def test_a_representative_campaign_quote_is_only_attributed_to_the_event_that_contains_it(quote_store):
    with quote_store.engine.begin() as c:
        c.execute(text("delete from graph_observations"))
        c.execute(text("create table graph_facts (org_id text,subject_node_id text,fact_version_id text,field text,value text,status text,valid_to text)"))
        c.execute(text("alter table graph_source_refs add column fact_version_id text"))
        c.execute(text("alter table source_events add column occurred_at text"))
        c.execute(text("update graph_source_refs set fact_version_id='fv',observation_id=null"))
        c.execute(text("update source_events set occurred_at='2026-08-11'"))
        c.execute(text("insert into graph_facts values ('o','p','fv','campaign.quote',:q,'active',null)"),dict(q=json.dumps(QUOTE)))
        for i in range(10):
            c.execute(text("insert into source_events values ('o',:e,null,'{\"email\":\"different@example.com\"}','participants','[\"different@example.com\"]','2026-09-10')"),dict(e=f"unrelated{i}"))
            c.execute(text("insert into graph_source_refs values ('o',null,:e,'{}','fv')"),dict(e=f"unrelated{i}"))
            c.execute(text("insert into prepared_content values ('o',:e,'A different message in the same campaign.')"),dict(e=f"unrelated{i}"))
    [quote] = load_evidence_quotes(quote_store,"o","p",limit=1)
    assert quote["event_id"] == "e"
    assert quote["quote"] == QUOTE and quote["source_verified"] is True
    assert quote["author"] == "owner@example.com"
    assert quote["visibility_scope"] == "org"
