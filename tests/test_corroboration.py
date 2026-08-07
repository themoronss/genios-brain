"""Cross-source corroboration — the second-brain write.

Two tools asserting the same fact must look DIFFERENT from one tool asserting it once:
the scoring ladder (one:60 / two:85 / three+:100) reads src_count from source refs. The
no-op branch of write_fact used to return before writing any ref, so a confirming
source left zero trace and the ladder was dead code. These tests freeze the repaired
behaviour with a fake connection (house style: no DB)."""
from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

from genios_engine.context.graph_store import GraphStore

T = datetime(2026, 8, 1, tzinfo=timezone.utc)


class _FakeConn:
    """Pattern-matching stand-in for a SQLAlchemy connection."""

    def __init__(self, *, held=None, ref_exists=False):
        self.held = held
        self.ref_exists = ref_exists
        self.executed: list[tuple[str, dict]] = []

    def execute(self, statement, params=None):
        sql = " ".join(str(statement).split())
        self.executed.append((sql, params or {}))
        if sql.startswith("select fact_version_id, value"):
            return SimpleNamespace(first=lambda: self.held)
        if sql.startswith("select 1 from graph_source_refs"):
            hit = SimpleNamespace() if self.ref_exists else None
            return SimpleNamespace(first=lambda: hit)
        return SimpleNamespace(first=lambda: None, rowcount=1)


def _store():
    s = GraphStore.__new__(GraphStore)          # no engine needed — conn is injected
    return s


def _held(value='"open"', rank=2):
    return SimpleNamespace(fact_version_id="fv_1", value=value,
                           authority_rank=rank, occurred_at=T)


def _write(store, conn, *, value="open", source="hubspot", rank=3):
    return store.write_fact(conn, org_id="o1", subject_node_id="n1", field="deal.status",
                            value=value, value_type="string", confidence=0.9,
                            occurred_at=T, event_id="evt_2", evidence={"text": "x"},
                            source=source, authority_rank=rank)


def test_same_value_from_second_source_writes_corroborating_ref():
    store, conn = _store(), _FakeConn(held=_held())
    out = _write(store, conn)                    # CRM confirms what email said
    assert out is None                           # still a no-op VERSION-wise
    ref_inserts = [(s, p) for s, p in conn.executed
                   if s.startswith("insert into graph_source_refs")]
    assert len(ref_inserts) == 1                 # ...but the confirmation is RECORDED
    assert ref_inserts[0][1]["fv"] == "fv_1"     # attached to the held (current) version
    assert '"corroborates": true' in ref_inserts[0][1]["ex"].lower()


def test_re_sync_of_same_event_does_not_inflate():
    store, conn = _store(), _FakeConn(held=_held(), ref_exists=True)
    assert _write(store, conn) is None
    assert not any(s.startswith("insert into graph_source_refs")
                   for s, _ in conn.executed)    # dedup by (version, event)


def test_new_fact_still_writes_normally():
    store, conn = _store(), _FakeConn(held=None)
    out = _write(store, conn)
    assert out is not None                       # fresh insert path untouched
    assert any(s.startswith("insert into graph_facts") for s, _ in conn.executed)
