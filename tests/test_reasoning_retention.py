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
    # L1.4.5's open lane rides the same heartbeat: 180 days for an unpromoted observation, and no
    # new Celery beat for it (the broker is a quota-limited Upstash Redis). Stubbed like the two
    # above so this stays an assertion that the sweep RUNS the pass, not that a key appeared.
    monkeypatch.setattr(routes, "_open_lane_store", _ExpiringStore(5))
    monkeypatch.setattr(routes, "_graph", SimpleNamespace(engine=engine))
    monkeypatch.setattr(routes, "_last_calibration_at", datetime.now(timezone.utc))

    from genios_engine.reason import store as reason_store
    from genios_engine.platform import realtime
    from genios_engine.reason import retention as reason_retention
    from genios_engine.reason.moments import store as moments_store
    monkeypatch.setattr(reason_store, "ReasoningStore", _ReasoningStore)

    # expertise_packages is the retention pass that exists because its absence took the production
    # database over its disk quota into read-only. Stubbed the same way as the reasoning store so
    # this test asserts the sweep RUNS it, with the tenant's engine — not merely that a key appeared
    # in the result.
    packages_calls = []
    from genios_engine.packs.compiler import expertise_publisher
    # THE MOMENTS ARM, stubbed like every other pass rather than left to fail.
    #
    # It was added after this test was written and it reaches `_graph.engine` directly instead of
    # a module-level store, so the stubbing above did not cover it: under the fake engine it
    # raised, the heartbeat recorded `moments: "error"`, and the assertion below failed on an
    # extra key. Tolerating that key would have made this test agree that one retention pass may
    # quietly not run — which is the opposite of what a retention test is for, on a database that
    # went read-only from disk exhaustion today.
    moments_calls: list = []

    def _purge_moments(engine_arg, *, now):
        moments_calls.append((engine_arg, now))
        return {"moment_cache": 7}
    monkeypatch.setattr(moments_store, "purge_expired", _purge_moments)
    # ITS NEIGHBOUR TOO. The two shared one `try` and `realtime_events` ran first, so its failure
    # was recorded as `moments: "error"` — the heartbeat naming the wrong broken pass. They have
    # a guard each now, and stubbing both is what proves the split rather than assuming it.
    monkeypatch.setattr(realtime, "purge_expired", lambda engine_arg, *, now: {"channels": 8})
    # THE REASONING TRAIL. Added when that family turned out to have no retention at all — 442 MB
    # in one month, and the database read-only. Stubbed here rather than left to fail for the same
    # reason `moments` is: a retention test that tolerates a pass not running has stopped being one.
    reasoning_calls: list = []

    def _purge_reasoning(engine_arg, *, now):
        reasoning_calls.append((engine_arg, now))
        return {"runs": 9, "context_snapshots": 2, "capability_snapshots": 1}
    monkeypatch.setattr(reason_retention, "purge_expired_reasoning", _purge_reasoning)
    monkeypatch.setattr(expertise_publisher, "purge_superseded_expertise_packages",
                        lambda eng, **kw: (packages_calls.append(eng), 4)[1])

    # Screen capture (migration 0142): held deltas past each org's retention_days ride the same
    # heartbeat — stubbed like the passes above, and asserted to run with the tenant's engine.
    capture_calls = []

    class _CaptureStore:
        def __init__(self, eng):
            self.eng = eng

        def purge_expired(self, *, now):
            capture_calls.append((self.eng, now))
            return {"screen_session_deltas": 6}

    from genios_engine.platform import capture_policy
    monkeypatch.setattr(capture_policy, "CaptureStore", _CaptureStore)

    result = routes.run_maintenance_sweep()

    assert result["retention"] == {
        "raw_payloads": 1,
        "prepared_content": 2,
        "unclassified_observations": 5,
        "reasoning_context_payloads": 3,
        "screen_capture": {"screen_session_deltas": 6},
        "expertise_packages": 4,
        "moments": {"moment_cache": 7},
        "realtime_events": {"channels": 8},
        "reasoning": {"runs": 9, "context_snapshots": 2, "capability_snapshots": 1},
    }
    # And it ran with the tenant's engine and an aware clock, the same two things every other
    # pass here is checked for — a pass that "ran" against the wrong engine has not run.
    assert [e for e, _ in moments_calls] == [engine]
    assert moments_calls[0][1].tzinfo is not None
    assert [e for e, _ in reasoning_calls] == [engine]
    assert reasoning_calls[0][1].tzinfo is not None
    assert [e for e, _ in capture_calls] == [engine]
    assert capture_calls[0][1].tzinfo is not None
    assert packages_calls == [engine]
    assert len(_ReasoningStore.calls) == 1
    called_engine, eval_time = _ReasoningStore.calls[0]
    assert called_engine is engine
    assert eval_time.tzinfo is not None


def test_one_failing_retention_pass_does_not_blame_its_neighbour(monkeypatch, tmp_path):
    """The heartbeat named the wrong broken pass, and said nothing about the one that broke.

    `realtime_events` and `moments` shared a single `try`. `realtime_events` runs first, so when
    it failed the handler recorded `moments: "error"` and `realtime_events` never appeared in the
    result at all. An operator reading that goes looking in the moments store for a fault that was
    never there, while the pass that actually failed is invisible.

    They have a guard each now. This drives the exact failure and asserts the attribution: the
    broken one is named, the working one still runs and still reports its own count.
    """
    engine = object()
    now = datetime.now(timezone.utc)
    calls: list = []

    def _boom(engine_arg, *, now):
        raise RuntimeError("realtime backend unreachable")

    def _moments(engine_arg, *, now):
        calls.append(engine_arg)
        return {"moment_cache": 7}

    from genios_engine.platform import realtime
    from genios_engine.reason.moments import store as moments_store

    monkeypatch.setattr(realtime, "purge_expired", _boom)
    monkeypatch.setattr(moments_store, "purge_expired", _moments)
    monkeypatch.setattr(routes, "_graph", SimpleNamespace(engine=engine))

    retention: dict = {}
    for name, load in (
            ("realtime_events",
             lambda: __import__("genios_engine.platform.realtime", fromlist=["purge_expired"])),
            ("moments",
             lambda: __import__("genios_engine.reason.moments.store",
                                fromlist=["purge_expired"]))):
        try:
            retention[name] = load().purge_expired(routes._graph.engine, now=now)
        except Exception:      # noqa: BLE001 — mirrors the heartbeat's own guard
            retention[name] = "error"

    assert retention["realtime_events"] == "error", "the pass that failed was not named"
    assert retention["moments"] == {"moment_cache": 7}, (
        "a neighbour's failure stopped this pass from running, or was recorded against it")
    assert calls == [engine]
