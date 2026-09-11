"""Recipients have evidence without being made the speakers of somebody else's words."""
import json

import pytest
from sqlalchemy import create_engine, text

from genios_engine.context import pipeline
from genios_engine.context.extract.extractor import Extraction
from genios_engine.context.graph_store import GraphStore
from .test_event_presence_store import presence_schema
from .test_support_derived_provenance import NOW


@pytest.mark.parametrize("path", ["plain", "observation", "question", "mention"])
def test_each_outbound_recipient_gets_evidence_without_inheriting_the_senders_claim(monkeypatch, path):
    engine = create_engine("sqlite://")
    store = object.__new__(GraphStore)
    store._engine = engine
    with engine.begin() as c:
        presence_schema(c)
    for method in ("write_fact", "write_edge", "write_change"):
        monkeypatch.setattr(store, method, lambda *a, **kw: None)
    monkeypatch.setattr(store, "bump_version", lambda *a: 1)
    monkeypatch.setattr(store, "find_or_create_node", lambda *a, **kw: kw["canonical_key"])
    monkeypatch.setattr(pipeline, "correlate_event", lambda *a, **kw: [])
    monkeypatch.setattr(pipeline, "close_loops_for_reply", lambda *a, **kw: None)
    monkeypatch.setattr(pipeline, "record_ask", lambda *a, **kw: "loop")
    monkeypatch.setattr(pipeline, "resolve_canon_mention", lambda *a, **kw: None)
    body = "Could you review the deck in Atlas?"
    ex = Extraction(ok=True, relevance=0.9, noise_type="none", domains=[],
        entity_mentions=[], fact_candidates=[], commitments=[], questions=[], observations=[])
    if path == "observation":
        ex.observations = [{"kind": "review_requested", "evidence_text": body}]
    if path == "question":
        ex.questions = [{"evidence_text": body, "directed_at": "investor@gmail.com"}]
    if path == "mention":
        ex.entity_mentions = [{"type": "tool", "name": "Atlas", "evidence_text": "Atlas"}]
    kwargs = dict(org_id="o", event_id="e", source="gmail", content=body,
        sender_email="owner@gmail.com", recipient_emails=["investor@gmail.com", "partner@gmail.com", "investor@gmail.com"],
        internal_emails=frozenset({"owner@gmail.com"}), occurred_at=NOW,
        llm=None, store=store, qualified_extraction=ex, is_inbound=False)
    pipeline.process_event(**kwargs)
    pipeline.process_event(**kwargs)
    with engine.connect() as c:
        rows = c.execute(text("select * from graph_observations where subject_node_id!='owner@gmail.com'")).mappings().all()
        assert len(rows) == 2
        assert {r["subject_node_id"] for r in rows} == {"investor@gmail.com", "partner@gmail.com"}
        assert all(r["kind"] == "event_presence" for r in rows)
        refs = c.execute(text("select r.* from graph_source_refs r join graph_observations ob on ob.observation_id=r.observation_id where ob.kind='event_presence'")).mappings().all()
        assert len(refs) == 2
        assert all(r["event_id"] == "e" and r["source"] == "gmail" for r in refs)
        assert all(json.loads(r["evidence"])["speaker_node_id"] == "owner@gmail.com" for r in refs)
    engine.dispose()
