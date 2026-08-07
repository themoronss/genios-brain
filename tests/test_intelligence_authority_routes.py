from __future__ import annotations

from contextlib import contextmanager
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from genios_engine.api import intelligence_routes as routes
from genios_engine.platform.auth import AuthCtx
from genios_engine.reason import intelligence


class _Result:
    def __init__(self, *, first=None, rows=(), scalar=None):
        self._first = first
        self._rows = list(rows)
        self._scalar = scalar

    def first(self):
        return self._first

    def fetchall(self):
        return list(self._rows)

    def scalar(self):
        return self._scalar

    def __iter__(self):
        return iter(self._rows)

    def mappings(self):
        """Mirror SQLAlchemy's Result.mappings(): rows as read-only dict views."""
        rows = [dict(vars(r)) if isinstance(r, SimpleNamespace) else dict(r)
                for r in self._rows]
        return SimpleNamespace(all=lambda: rows,
                               first=lambda: (rows[0] if rows else None))


class _CacheMissConnection:
    def execute(self, _statement, _params=None):
        return _Result(first=None)


class _CacheMissEngine:
    @contextmanager
    def connect(self):
        yield _CacheMissConnection()

    @contextmanager
    def begin(self):
        yield _CacheMissConnection()


def _envelope(*, triggered_by="analyze"):
    return {
        "decision_id": "dec_exact",
        "org_id": "org_1",
        "recommendation": {
            "headline": "Cooling deal",
            "action": "restore_momentum",
            "reasoning": "Strongest open signal: cooling_deal.",
        },
        "confidence": 0.72,
        "derivation": [{"conclusion": "cooling_deal", "reasoning_run_id": "run_1"}],
        "uncertainty": [],
        "route": "notify",
        "triggered_by": triggered_by,
        "as_of": {"graph_version": 9, "timestamp": "2026-08-06T12:30:00+00:00"},
    }


def test_decision_cache_key_changes_when_authoritative_signal_state_changes():
    first = routes._cache_key(
        "org_1", "sales", "What now?", 9, {}, "cfg_1", authority_epoch="1:a:sig_1")
    second = routes._cache_key(
        "org_1", "sales", "What now?", 9, {}, "cfg_1", authority_epoch="2:b:sig_2")

    assert first != second


def test_analyze_persists_before_returning_an_actionable_result(monkeypatch):
    graph = SimpleNamespace(engine=_CacheMissEngine(), record_cost=lambda **_kwargs: None)
    persisted = []
    run_calls = []
    monkeypatch.setattr(routes, "_graph", graph)
    monkeypatch.setattr(routes, "_registry", None)
    monkeypatch.setattr(routes, "current_graph_version", lambda *_args: 9)
    monkeypatch.setattr(routes, "_enforce_query_budget", lambda _org_id: None)
    monkeypatch.setattr(routes, "_resolve_contact_facts", lambda *_args: (None, {}))

    def fake_run_query(**kwargs):
        run_calls.append(kwargs)
        return _envelope(), None

    monkeypatch.setattr(routes, "run_query", fake_run_query)
    monkeypatch.setattr(routes, "_persist_decision_envelope",
                        lambda **kwargs: persisted.append(kwargs))

    result = routes.analyze_contact("Ada", org_id="org_1")

    assert result["id"] == "dec_exact"
    assert run_calls[0]["triggered_by"] == "analyze"
    assert persisted[0]["envelope"]["decision_id"] == result["id"]
    assert persisted[0]["triggered_by"] == "analyze"


def test_analyze_fails_closed_when_decision_persistence_fails(monkeypatch):
    graph = SimpleNamespace(engine=_CacheMissEngine(), record_cost=lambda **_kwargs: None)
    monkeypatch.setattr(routes, "_graph", graph)
    monkeypatch.setattr(routes, "_registry", None)
    monkeypatch.setattr(routes, "current_graph_version", lambda *_args: 9)
    monkeypatch.setattr(routes, "_enforce_query_budget", lambda _org_id: None)
    monkeypatch.setattr(routes, "run_query", lambda **_kwargs: (_envelope(), None))
    monkeypatch.setattr(routes, "_persist_decision_envelope",
                        lambda **_kwargs: (_ for _ in ()).throw(HTTPException(503, "unsafe")))

    with pytest.raises(HTTPException) as exc:
        routes.analyze_contact("Ada", org_id="org_1")

    assert exc.value.status_code == 503


class _DecisionConnection:
    def __init__(self, envelope):
        self.envelope = envelope

    def execute(self, _statement, _params=None):
        return _Result(first=SimpleNamespace(envelope=self.envelope))


class _DecisionEngine:
    def __init__(self, envelope):
        self.envelope = envelope

    @contextmanager
    def connect(self):
        yield _DecisionConnection(self.envelope)


def _bundle(run_id: str, confidence_bp: int):
    return {
        "reasoner_results": [
            {"reasoner_id": "goal"},
            {"reasoner_id": f"priority_{run_id}"},
        ],
        "candidate_checks": [{"check_hash": f"check_{run_id}"}],
        "context_snapshot": {
            "source_manifest": [{"evidence_ref_id": f"evidence_{run_id}"}],
        },
        "output": {"confidence_bp": confidence_bp},
    }


def test_explain_represents_every_contributing_reasoning_run(monkeypatch):
    envelope = {
        "confidence": 0.74,
        "as_of": {"graph_version": 9},
        "derivation": [
            {"rule_id": "cooling", "conclusion": "cooling_deal",
             "reasoning_run_id": "run_a", "matched_facts": {}},
            {"rule_id": "single_thread", "conclusion": "single_threaded_deal",
             "reasoning_run_id": "run_b", "matched_facts": {}},
        ],
    }
    loaded = []

    class FakeReasoningStore:
        def __init__(self, *, engine):
            self.engine = engine

        def load_bundle(self, *, org_id, run_id):
            loaded.append((org_id, run_id))
            return _bundle(run_id, 8100 if run_id == "run_a" else 6700)

    monkeypatch.setattr(routes, "_graph", SimpleNamespace(engine=_DecisionEngine(envelope)))
    monkeypatch.setattr(routes, "ReasoningStore", FakeReasoningStore)

    result = routes.explain_decision("dec_1", org_id="org_1")

    assert loaded == [("org_1", "run_a"), ("org_1", "run_b")]
    assert result["reasoning_run_ids"] == ["run_a", "run_b"]
    assert [run["reasoning_run_id"] for run in result["reasoning_runs"]] == ["run_a", "run_b"]
    assert "reasoning_run_id" not in result
    assert result["confidence_breakdown"]["deterministic_basis_points_by_run"] == {
        "run_a": 8100,
        "run_b": 6700,
    }
    assert {item["reasoning_run_id"] for item in result["source_facts"]} == {"run_a", "run_b"}
    assert {item["reasoning_run_id"] for item in result["constraints_checked"]} == {
        "run_a", "run_b",
    }


class _RetrievalConnection:
    def __init__(self):
        self.statements = []
        self.signal_scope = None

    def execute(self, statement, params=None):
        sql = str(statement)
        self.statements.append(sql)
        if "from graph_nodes" in sql and "length(display_name)" in sql:
            return _Result(rows=[SimpleNamespace(
                node_id="node_root", display_name="Acme", node_type="deal")])
        if "from graph_edges" in sql:
            return _Result(rows=[SimpleNamespace(nid="node_z"), SimpleNamespace(nid="node_a")])
        if "from signals" in sql:
            self.signal_scope = params["ids"]
            return _Result(rows=[])
        if "from graph_nodes" in sql and "node_id=:n" in sql:
            return _Result(first=None)
        raise AssertionError(f"unexpected query: {sql}")


class _RetrievalEngine:
    def __init__(self):
        self.connection = _RetrievalConnection()

    @contextmanager
    def connect(self):
        yield self.connection


def test_retrieval_uses_total_orders_sorted_scope_and_only_trace_linked_signals():
    engine = _RetrievalEngine()
    store = SimpleNamespace(engine=engine)

    signals, facts, focus = intelligence._retrieve(store, "org_1", "What about Acme?")

    assert signals == []
    assert facts == []
    assert focus == "Acme"
    assert engine.connection.signal_scope == ["node_a", "node_root", "node_z"]
    sql = "\n".join(engine.connection.statements).lower()
    assert "lower(display_name) asc, node_id asc" in sql
    assert "edge_version_id asc limit 40" in sql
    assert "s.reasoning_run_id is not null" in sql
    assert "join reasoning_runs rr" in sql
    assert "rr.config_snapshot_id=s.config_snapshot_id" in sql
    assert "ro.outcome_kind='decision'" in sql
    assert "s.signal_id asc limit 15" in sql


class _PersistConnection:
    def __init__(self, held):
        self.held = held
        self.calls = 0

    def execute(self, _statement, _params=None):
        self.calls += 1
        return _Result(first=self.held if self.calls == 2 else None)


class _PersistEngine:
    def __init__(self, held):
        self.connection = _PersistConnection(held)

    @contextmanager
    def begin(self):
        yield self.connection


def _held_decision(envelope):
    return SimpleNamespace(
        org_id="org_1", module_id="sales", question="What now?", envelope=envelope,
        graph_version=9, cache_key="cache_1", triggered_by="query",
    )


def test_decision_persistence_accepts_only_the_exact_held_envelope(monkeypatch):
    envelope = _envelope(triggered_by="query")
    engine = _PersistEngine(_held_decision(dict(envelope)))
    monkeypatch.setattr(routes, "_graph", SimpleNamespace(engine=engine))

    routes._persist_decision_envelope(
        org_id="org_1", module_id="sales", question="What now?", envelope=envelope,
        graph_version=9, cache_key="cache_1", triggered_by="query")

    assert engine.connection.calls == 2


def test_decision_persistence_fails_closed_on_semantic_id_collision(monkeypatch):
    envelope = _envelope(triggered_by="query")
    different = dict(envelope)
    different["explanation"] = "A different envelope under the same id."
    engine = _PersistEngine(_held_decision(different))
    monkeypatch.setattr(routes, "_graph", SimpleNamespace(engine=engine))

    with pytest.raises(HTTPException) as exc:
        routes._persist_decision_envelope(
            org_id="org_1", module_id="sales", question="What now?", envelope=envelope,
            graph_version=9, cache_key="cache_1", triggered_by="query")

    assert exc.value.status_code == 503


class _FeedbackConnection:
    def __init__(self, *, authoritative=True):
        self.authoritative = authoritative
        self.statements = []

    def execute(self, statement, params=None):
        sql = str(statement)
        self.statements.append((sql, dict(params or {})))
        if "select id from orgs" in sql:
            return _Result(first=SimpleNamespace(id="org_1"))
        if "select k.card_id, k.assignee" in sql:
            return _Result(first=(SimpleNamespace(
                card_id="card_1", assignee="seat_1", pack_id="sales",
                pack_version="1.0.0", authority_pack_revision=3,
                capability_id="legacy.sales.cooling_deal", capability_version="1.0.0",
                rule_id="cooling_deal")
                                  if self.authoritative else None))
        if "insert into card_feedback_verdicts" in sql:
            return _Result(first=SimpleNamespace(verdict_version=1))
        return _Result()


class _FeedbackEngine:
    def __init__(self, *, authoritative=True):
        self.connection = _FeedbackConnection(authoritative=authoritative)

    @contextmanager
    def begin(self):
        yield self.connection


def test_card_feedback_is_current_authority_checked_and_idempotent(monkeypatch):
    engine = _FeedbackEngine()
    monkeypatch.setattr(routes, "_graph", SimpleNamespace(engine=engine))

    response = routes.intelligence_feedback(
        routes.FeedbackBody(action="thumbs_down", insight_id="card_1", user_id="spoofed"),
        ctx=AuthCtx(org_id="org_1", actor_id="seat_1", scopes=["feedback.write"]),
    )

    sql = "\n".join(statement.lower() for statement, _ in engine.connection.statements)
    insert_params = next(params for statement, params in engine.connection.statements
                         if "insert into card_feedback_verdicts" in statement.lower())
    assert response["routed_to_g_i_3"] is True
    assert "select id from orgs where id=:o for share" in sql
    assert "select id from orgs" in engine.connection.statements[0][0].lower()
    assert "select graph_version from graph_versions" in sql and "for share" in sql
    assert "join reasoning_runs rr" in sql
    assert "k.state in ('queued','surfaced','snoozed','delivered')" in sql
    assert "on conflict (org_id,card_id) do nothing" in sql
    assert "insert into card_feedback_revisions" in sql
    assert insert_params["cause"] == "wrong"
    assert insert_params["actor"] == "seat_1"
    assert "spoofed" not in insert_params.values()


def test_snooze_feedback_is_timing_audit_not_a_negative_l6_verdict(monkeypatch):
    class TimingConnection(_FeedbackConnection):
        def execute(self, statement, params=None):
            result = super().execute(statement, params)
            if "insert into card_events" in str(statement):
                return _Result(first=SimpleNamespace(id=params["id"]))
            return result

    engine = _FeedbackEngine()
    engine.connection = TimingConnection()
    monkeypatch.setattr(routes, "_graph", SimpleNamespace(engine=engine))

    response = routes.intelligence_feedback(
        routes.FeedbackBody(action="snooze", insight_id="card_1"),
        ctx=AuthCtx(org_id="org_1", actor_id="seat_1", scopes=["feedback.write"]),
    )

    sql = "\n".join(statement.lower() for statement, _ in engine.connection.statements)
    event_params = next(params for statement, params in engine.connection.statements
                        if "insert into card_events" in statement.lower())
    assert "human.feedback_signal" in sql and "on conflict (id) do nothing" in sql
    assert "card_feedback_verdicts" not in sql
    assert "card_feedback_revisions" not in sql
    assert event_params["cause"] == "snooze"
    assert response["changed"] is True and response["verdict_version"] is None


def test_owner_can_reauthorize_identical_legacy_organization_preference(monkeypatch):
    class LegacyPreferenceConnection(_FeedbackConnection):
        def execute(self, statement, params=None):
            sql = str(statement)
            self.statements.append((sql, dict(params or {})))
            if "select id from orgs" in sql:
                return _Result(first=SimpleNamespace(id="org_1"))
            if "select k.card_id, k.assignee" in sql:
                return _Result(first=SimpleNamespace(
                    card_id="card_1", assignee="seat_1", pack_id="sales",
                    pack_version="1.0.0", authority_pack_revision=3,
                    capability_id="legacy.sales.cooling_deal", capability_version="1.0.0",
                    rule_id="cooling_deal"))
            if "insert into card_feedback_verdicts" in sql:
                return _Result()
            if "update card_feedback_verdicts" in sql:
                return _Result(first=SimpleNamespace(
                    feedback_id="fb_existing", verdict_version=4))
            return _Result()

    engine = _FeedbackEngine()
    engine.connection = LegacyPreferenceConnection()
    monkeypatch.setattr(routes, "_graph", SimpleNamespace(engine=engine))

    response = routes.intelligence_feedback(
        routes.FeedbackBody(
            action="edit", insight_id="card_1",
            edit_diff={"preference": {
                "key": "meeting_window", "value": "morning",
                "scope": "organization", "category": "calendar",
            }}),
        ctx=AuthCtx(org_id="org_1", actor_id="owner_1", scopes=None),
    )

    update_sql, update_params = next(
        (sql, params) for sql, params in engine.connection.statements
        if "update card_feedback_verdicts" in sql)
    revision_params = next(
        params for sql, params in engine.connection.statements
        if "insert into card_feedback_revisions" in sql)
    assert "organization_authorized" in update_sql
    assert update_params["owner"] is True
    assert revision_params["owner"] is True
    assert revision_params["fid"] == "fb_existing"
    assert response["changed"] is True
    assert response["verdict_version"] == 4


def test_card_feedback_rejects_stale_or_cross_tenant_card(monkeypatch):
    engine = _FeedbackEngine(authoritative=False)
    monkeypatch.setattr(routes, "_graph", SimpleNamespace(engine=engine))

    with pytest.raises(HTTPException) as exc:
        routes.intelligence_feedback(
            routes.FeedbackBody(action="thumbs_up", insight_id="card_1"),
            ctx=AuthCtx(org_id="org_1", actor_id="seat_1", scopes=["feedback.write"]))

    assert exc.value.status_code == 409
    assert not any("insert into card_events" in statement.lower()
                   for statement, _ in engine.connection.statements)


def test_feedback_action_is_a_closed_enum(monkeypatch):
    engine = _FeedbackEngine()
    monkeypatch.setattr(routes, "_graph", SimpleNamespace(engine=engine))

    with pytest.raises(HTTPException) as exc:
        routes.intelligence_feedback(
            routes.FeedbackBody(action="run_arbitrary", insight_id="card_1"),
            ctx=AuthCtx(org_id="org_1", actor_id="seat_1", scopes=["feedback.write"]))

    assert exc.value.status_code == 422
    assert engine.connection.statements == []
