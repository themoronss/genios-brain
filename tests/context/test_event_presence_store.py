"""Presence is one event/subject receipt, never a copied semantic claim."""
import json
from sqlalchemy import create_engine, text

from genios_engine.context.graph_store import GraphStore
from .test_support_derived_provenance import NOW


def presence_schema(conn):
    conn.execute(text("create table source_events (org_id text,event_id text,source_object_id text)"))
    conn.execute(text("insert into source_events values ('o','e','provider-event')"))
    conn.execute(text("""create table graph_observations (observation_id text primary key,
        org_id text,subject_node_id text,kind text,occurred_at timestamp,confidence real,
        created_by_event_id text,status text default 'active')"""))
    conn.execute(text("""create table graph_source_refs (source_ref_id text primary key,
        org_id text,fact_version_id text,edge_version_id text,observation_id text,event_id text,
        source text,evidence text,extractor_version text,source_object_id text)"""))


def test_replaying_event_presence_keeps_one_observation_and_a_real_source_receipt():
    store = GraphStore("sqlite://")
    engine = store.engine
    with engine.begin() as conn:
        presence_schema(conn)
        kwargs = dict(org_id="o", subject_node_id="person", occurred_at=NOW,
            event_id="e", source="gcal", evidence={"relation": "listed_participant"})
        assert store.write_event_presence(conn, **kwargs) is True
        assert store.write_event_presence(conn, **kwargs) is False
        observation = conn.execute(text("select * from graph_observations")).mappings().one()
        receipt = conn.execute(text("select * from graph_source_refs")).mappings().one()
        assert observation["kind"] == "event_presence"
        assert observation["confidence"] == 1.0
        assert receipt["observation_id"] == observation["observation_id"]
        assert (receipt["event_id"], receipt["source"], receipt["source_object_id"]) == ("e", "gcal", "provider-event")
        assert json.loads(receipt["evidence"]) == {"relation": "listed_participant"}
        # The same event establishes a second subject, not an independent second source.
        assert store.write_event_presence(conn, **{**kwargs, "subject_node_id": "meeting"}) is True
        assert conn.execute(text("select count(distinct source) from graph_source_refs")).scalar() == 1
    engine.dispose()
