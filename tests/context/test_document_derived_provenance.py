"""Document cluster arithmetic retains the revisions it actually compared."""
import json
from types import SimpleNamespace

from sqlalchemy import text

from .test_derived_provenance import provenance_db
from .test_support_derived_provenance import NOW, _fact_schema
from genios_engine.context.derived_provenance import load_event_receipts
from genios_engine.context import document_register as register


def test_a_document_fact_carries_two_event_receipts_without_duplicate_replays(provenance_db):
    conn = provenance_db
    _fact_schema(conn)
    for _ in range(2):
        register._write_fact(conn, org_id="o", node_id="doc", field_name="derived.document_live_copies",
            value=2, value_type="number", now=NOW,
            event_receipts=load_event_receipts(conn, org_id="o", event_ids=("e1", "e2")))
    fact = conn.execute(text("select * from graph_facts")).mappings().one()
    assert json.loads(fact["value"]) == 2
    assert conn.execute(text("select event_id,source from graph_source_refs where fact_version_id=:v order by event_id"),
                        {"v": fact["fact_version_id"]}).all() == [("e1", "gmail"), ("e2", "gcal")]


def test_every_copy_count_keeps_the_events_of_all_compared_documents(provenance_db, monkeypatch):
    conn = provenance_db
    _fact_schema(conn)
    artefacts = tuple(register.Artefact(node_id=f"doc{i}", title="Security policy",
        facts={"document.title": "Security policy", "document.modified_at": NOW.isoformat(),
               "document.content_hash": "identical"}, head="policy", internal_kind=None,
        attached_people=1, owner_seen_at=None, owner_is_us=False, event_ids=(event,))
        for i, event in enumerate(("e1", "e2")))
    monkeypatch.setattr(register, "gather", lambda *a, **kw: register.Register(org_id="o", now=NOW, artefacts=artefacts))
    monkeypatch.setattr(register, "register_domains", lambda: ("admin",))
    monkeypatch.setattr(register, "read_register", lambda reg: [])
    monkeypatch.setattr(register, "_reconcile", lambda *a, **kw: 0)
    # Use the actual transaction and fact/ref writers; situation rendering is another unit.
    from contextlib import nullcontext
    store = SimpleNamespace(engine=SimpleNamespace(begin=lambda: nullcontext(conn)))
    assert register.refresh_document_situations(store, "o", now=NOW) == 4
    facts = conn.execute(text("select fact_version_id from graph_facts")).scalars().all()
    assert len(facts) == 4
    for version in facts:
        assert conn.execute(text("select event_id from graph_source_refs where fact_version_id=:v order by event_id"),
                            {"v": version}).scalars().all() == ["e1", "e2"]
