"""Derived facts had 0 source refs; retain real event origins without multiplying witnesses."""
import json
from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine, text


@pytest.fixture
def provenance_db():
    engine = create_engine("sqlite://")
    with engine.begin() as conn:
        conn.execute(text("create table source_events (org_id text, event_id text, source text, source_object_id text, occurred_at timestamp)"))
        conn.execute(text("""create table graph_source_refs (
            source_ref_id text primary key, org_id text, fact_version_id text,
            event_id text, source text, source_object_id text, independence_group text,
            evidence text, extractor_version text)"""))
        for org, event, source in (("o", "e1", "gmail"), ("o", "e2", "gcal"), ("other", "foreign", "crm")):
            conn.execute(text("insert into source_events values (:o,:e,:s,:id,:at)"),
                         {"o": org, "e": event, "s": source, "id": "provider-" + event,
                          "at": "2026-08-11T10:00:00+00:00"})
        conn.execute(text("""insert into graph_source_refs values
            ('original','o','original-fact','e1','gmail','provider-e1','original-mailbox',
             '{"text":"We sent the deck."}','extract-v1')"""))
        yield conn
    engine.dispose()


def _write(conn, events):
    from genios_engine.context.derived_provenance import load_event_receipts, write_fact_source_refs
    receipts = load_event_receipts(conn, org_id="o", event_ids=events)
    assert receipts is not None
    write_fact_source_refs(conn, org_id="o", fact_version_id="derived-fact", receipts=receipts)
    return receipts


def _refs(conn):
    return conn.execute(text("select * from graph_source_refs where fact_version_id='derived-fact' order by event_id")).mappings().all()


def test_a_derived_fact_carries_the_provenance_of_both_events_it_came_from(provenance_db):
    receipts = _write(provenance_db, ("e1", "e2"))
    refs = _refs(provenance_db)
    assert [(r["event_id"], r["source"], r["fact_version_id"]) for r in refs] == [
        ("e1", "gmail", "derived-fact"), ("e2", "gcal", "derived-fact")]
    assert refs[0]["independence_group"] == "original-mailbox"
    assert refs[1]["independence_group"] == "gcal"
    assert json.loads(refs[0]["evidence"])["text"] == "We sent the deck."
    assert refs[0]["source_object_id"] == "provider-e1"
    assert receipts[0].occurred_at == datetime(2026, 8, 11, 10, tzinfo=timezone.utc)


def test_repeating_a_derived_write_does_not_create_more_witnesses(provenance_db):
    _write(provenance_db, ("e1", "e1", "e2"))
    original_ids = [r["source_ref_id"] for r in _refs(provenance_db)]
    _write(provenance_db, ("e2", "e1"))
    assert [r["source_ref_id"] for r in _refs(provenance_db)] == original_ids


def test_a_changed_derivation_does_not_keep_a_receipt_for_a_removed_member(provenance_db):
    _write(provenance_db, ("e1", "e2"))
    _write(provenance_db, ("e2",))
    assert [r["event_id"] for r in _refs(provenance_db)] == ["e2"]
    assert provenance_db.execute(text("select count(*) from graph_source_refs where source_ref_id='original'")).scalar() == 1


def test_missing_and_other_tenant_events_do_not_become_derived_evidence(provenance_db):
    _write(provenance_db, ("foreign", "missing", "state:o"))
    assert _refs(provenance_db) == []


def test_an_unavailable_refinement_read_is_distinct_from_a_known_empty_event_set(provenance_db):
    from genios_engine.context.derived_provenance import load_event_receipts
    assert load_event_receipts(provenance_db, org_id="o", event_ids=()) == ()
    provenance_db.execute(text("drop table source_events"))
    assert load_event_receipts(provenance_db, org_id="o", event_ids=("e1",)) is None
    assert provenance_db.execute(text("select 1")).scalar() == 1
