"""A calendar record establishes meeting and listed people, not verified attendance."""
import json
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, text

from genios_engine.context.graph_store import GraphStore
from genios_engine.context import structured
from .test_event_presence_store import presence_schema
from .test_support_derived_provenance import NOW


@pytest.mark.parametrize("attendees", [2, 11])
def test_calendar_writes_one_receipted_observation_per_established_node_without_replay_duplicates(monkeypatch, attendees):
    engine = create_engine("sqlite://")
    store = object.__new__(GraphStore)
    store._engine = engine
    with engine.begin() as c:
        presence_schema(c)
    # Preserve real observation and source-ref SQL; node/fact/correlation semantics have
    # independent coverage and are outside this observation contract.
    monkeypatch.setattr(store, "bump_version", lambda *a: 1)
    monkeypatch.setattr(store, "find_or_create_node", lambda *a, **kw: kw["canonical_key"])
    monkeypatch.setattr(store, "map_identity", lambda *a, **kw: None)
    monkeypatch.setattr(store, "write_fact", lambda *a, **kw: "fact")
    monkeypatch.setattr(store, "write_edge", lambda *a, **kw: "edge")
    monkeypatch.setattr(store, "write_change", lambda *a, **kw: None)
    monkeypatch.setattr(structured, "correlate_event", lambda *a, **kw: [])
    relations = [{"node_type": "person", "canonical_key": f"p{i}@example.com", "edge_type": "attended"}
                 for i in range(attendees)]
    kwargs = dict(org_id="o", event_id="e", source="gcal", source_object_id="meeting", node_type="meeting",
        occurred_at=NOW, structured_fields={"title": "Investor discussion"}, relations=relations,
        internal_emails=frozenset({"p0@example.com"}))
    first = structured.commit_structured(store, **kwargs)
    second = structured.commit_structured(store, **kwargs)
    expected = {"gcal:meeting"} | ({r["canonical_key"] for r in relations} if attendees <= 10 else set())
    with engine.connect() as c:
        observations = c.execute(text("select * from graph_observations")).mappings().all()
        assert {o["subject_node_id"] for o in observations} == expected
        assert len(observations) == len(expected)
        assert first.observations == len(expected) and second.observations == 0
        refs = c.execute(text("select * from graph_source_refs")).mappings().all()
        assert len(refs) == len(expected)
        assert all(r["event_id"] == "e" and r["source"] == "gcal" for r in refs)
        assert all(json.loads(r["evidence"])["presence"] == "structured_record" for r in refs)
    engine.dispose()
