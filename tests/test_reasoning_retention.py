from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

from genios_engine.api import account_routes, routes


def test_account_wipe_orders_layer4_dependencies_safely():
    tables = account_routes._ORG_SCOPED_TABLES

    assert tables.index("agent_claims") < tables.index("cards")
    assert tables.index("delivery_outbox") < tables.index("cards")
    assert tables.index("card_events") < tables.index("cards")
    assert tables.index("signals") < tables.index("reasoning_runs")
    assert tables.index("reasoning_runs") < tables.index("reasoning_context_payloads")
    assert tables.index("reasoning_context_payloads") < tables.index(
        "reasoning_context_snapshots")
    assert tables.index("reasoning_context_snapshots") < tables.index(
        "reasoning_capability_snapshots")
    assert tables.index("reasoning_runs") < tables.index("config_snapshots")
    assert tables.index("graph_source_refs") < tables.index("graph_facts")
    assert tables.index("source_identity_map") < tables.index("graph_nodes")
    assert tables.index("raw_payloads") < tables.index("source_events")
    for retained_customer_table in (
            "context_read_models", "graph_change_outbox", "discrepancies",
            "rule_mutes", "calibration_nudges", "macv_ledger", "context_attention"):
        assert retained_customer_table in tables

    class _Connection:
        def __init__(self):
            self.tables: list[str] = []

        def execute(self, statement, params):
            sql = str(statement)
            table = sql.split("delete from ", 1)[1].split(" ", 1)[0]
            self.tables.append(table)
            assert params == {"o": "org_1"}
            return SimpleNamespace(rowcount=1)

    connection = _Connection()
    result = account_routes._wipe(connection, "org_1")

    assert connection.tables == tables
    for table in ("reasoning_runs", "reasoning_context_snapshots",
                  "reasoning_capability_snapshots", "config_snapshots",
                  "agent_claims"):
        assert result[table] == 1


def test_scheduled_maintenance_purges_expired_reasoning_context_payloads(monkeypatch):
    class _ExpiringStore:
        def __init__(self, count):
            self.count = count

        def purge_expired(self):
            return self.count

    class _ReasoningStore:
        calls = []

        def __init__(self, *, engine):
            self.engine = engine

        def purge_expired_context_payloads(self, *, eval_time):
            self.calls.append((self.engine, eval_time))
            return 3

    engine = object()
    monkeypatch.setattr(routes, "run_sync_sweep", lambda **_kwargs: {"connections": 0})
    monkeypatch.setattr(routes, "_card_store", SimpleNamespace(
        sweep_lifecycle=lambda: {"expired": 0}))
    monkeypatch.setattr(routes, "_payload_store", _ExpiringStore(1))
    monkeypatch.setattr(routes, "_prepared_store", _ExpiringStore(2))
    monkeypatch.setattr(routes, "_graph", SimpleNamespace(engine=engine))
    monkeypatch.setattr(routes, "_last_calibration_at", datetime.now(timezone.utc))

    from genios_engine.reason import store as reason_store
    monkeypatch.setattr(reason_store, "ReasoningStore", _ReasoningStore)

    # expertise_packages is the retention pass that exists because its absence took the production
    # database over its disk quota into read-only. Stubbed the same way as the reasoning store so
    # this test asserts the sweep RUNS it, with the tenant's engine — not merely that a key appeared
    # in the result.
    packages_calls = []
    from genios_engine.packs.compiler import expertise_publisher
    monkeypatch.setattr(expertise_publisher, "purge_superseded_expertise_packages",
                        lambda eng, **kw: (packages_calls.append(eng), 4)[1])

    result = routes.run_maintenance_sweep()

    assert result["retention"] == {
        "raw_payloads": 1,
        "prepared_content": 2,
        "reasoning_context_payloads": 3,
        "expertise_packages": 4,
    }
    assert packages_calls == [engine]
    assert len(_ReasoningStore.calls) == 1
    called_engine, eval_time = _ReasoningStore.calls[0]
    assert called_engine is engine
    assert eval_time.tzinfo is not None
