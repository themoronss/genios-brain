"""Synthetic anchors inherit event evidence, not a count of copied graph rows."""
import pytest
from sqlalchemy import create_engine, text

from genios_engine.context.outreach_situations import _EVENT_COUNTS
from genios_engine.context.situations import evidence_score


@pytest.fixture
def neighborhood_db():
    engine = create_engine("sqlite://")
    with engine.begin() as conn:
        for sql in (
            "create table graph_nodes (org_id text,node_id text,node_type text,valid_to timestamp)",
            "create table graph_edges (org_id text,from_node_id text,to_node_id text,valid_to timestamp)",
            "create table graph_observations (org_id text,observation_id text,subject_node_id text,status text,occurred_at timestamp)",
            "create table graph_facts (org_id text,fact_version_id text,subject_node_id text,status text,valid_to timestamp)",
            "create table graph_source_refs (org_id text,observation_id text,fact_version_id text,event_id text,source text)",
            "create table source_events (org_id text,event_id text,source text,occurred_at timestamp)",
        ):
            conn.execute(text(sql))
        for node, kind in (("anchor", "thread"), ("p1", "person"), ("p2", "person"),
                           ("far", "person"), ("empty", "campaign"), ("empty-person", "person")):
            conn.execute(text("insert into graph_nodes values ('o',:n,:k,null)"), {"n": node, "k": kind})
        conn.execute(text("insert into graph_edges values ('o','p1','anchor',null),('o','anchor','p2',null),('o','p1','far',null),('o','empty-person','empty',null)"))
        for i in range(7):
            node = "p1" if i < 3 else "p2" if i < 6 else "far"
            conn.execute(text("insert into source_events values ('o',:e,'gmail','2026-08-11T12:00:00+00:00')"), {"e": f"e{i}"})
            conn.execute(text("insert into graph_observations values ('o',:id,:n,'active','2026-09-10T12:00:00+00:00')"), {"id": f"obs{i}", "n": node})
            conn.execute(text("insert into graph_source_refs values ('o',:id,null,:e,'gmail')"), {"id": f"obs{i}", "e": f"e{i}"})
        yield conn
    engine.dispose()


def _counts(conn):
    return {r.node_id: r for r in conn.execute(text(_EVENT_COUNTS),
        {"o": "o", "now": "2026-09-10T12:00:00+00:00"})}


def test_two_neighbours_in_opposite_directions_supply_six_events_and_score_65(neighborhood_db):
    stats = _counts(neighborhood_db).get("anchor")
    assert stats is not None
    assert (stats.events, stats.sources) == (6, 1)
    assert evidence_score(event_count=stats.events, source_count=stats.sources) == 65
    assert str(stats.last_at).startswith("2026-08-11")  # not observation write/sweep time


def test_a_neighbourhood_without_source_events_still_scores_zero(neighborhood_db):
    stats = _counts(neighborhood_db).get("empty")
    assert evidence_score(event_count=getattr(stats, "events", 0),
                          source_count=getattr(stats, "sources", 0)) == 0


def test_duplicate_observations_facts_and_foreign_refs_do_not_inflate_evidence(neighborhood_db):
    c = neighborhood_db
    c.execute(text("insert into graph_observations values ('o','copy','p2','active','2026-09-10')"))
    c.execute(text("insert into graph_facts values ('o','fv','anchor','active',null)"))
    c.execute(text("insert into graph_source_refs values ('o','copy',null,'e0','gmail'),('o',null,'fv','e0','gmail'),('foreign','obs1',null,'foreign','crm')"))
    c.execute(text("insert into source_events values ('foreign','foreign','crm','2026-09-10')"))
    stats = _counts(c).get("anchor")
    assert stats is not None and (stats.events, stats.sources) == (6, 1)


def test_future_events_retired_edges_and_non_person_company_neighbours_do_not_contribute(neighborhood_db):
    c = neighborhood_db
    c.execute(text("update source_events set occurred_at='2026-09-11T12:00:00+00:00' where event_id='e0'"))
    c.execute(text("update graph_edges set valid_to='2026-09-01' where to_node_id='p2'"))
    c.execute(text("insert into graph_edges values ('o','anchor','far',null)"))
    c.execute(text("update graph_nodes set node_type='thread' where node_id='far'"))
    stats = _counts(c).get("anchor")
    assert stats is not None and (stats.events, stats.sources) == (2, 1)
