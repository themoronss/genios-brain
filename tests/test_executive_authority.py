from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from genios_engine.executive import brief, memory, modes, summary
from genios_engine.executive.authority import authoritative_play_win_rates


NOW = datetime(2026, 8, 6, 12, tzinfo=timezone.utc)


class _Row(SimpleNamespace):
    @property
    def _mapping(self):
        return vars(self)


class _Result:
    def __init__(self, rows=(), *, scalar=0):
        self._rows = list(rows)
        self._scalar = scalar

    def fetchall(self):
        return list(self._rows)

    def scalar(self):
        return self._scalar

    def first(self):
        return self._rows[0] if self._rows else None

    def __iter__(self):
        return iter(self._rows)


class _ScriptedConnection:
    def __init__(self, responder=None):
        self.statements: list[tuple[str, dict]] = []
        self.responder = responder or (lambda _sql, _params: _Result())

    def execute(self, statement, params=None):
        sql = str(statement)
        values = dict(params or {})
        self.statements.append((sql, values))
        return self.responder(sql, values)


class _Engine:
    def __init__(self, connection):
        self.connection = connection

    @contextmanager
    def connect(self):
        yield self.connection


def _store(connection):
    return SimpleNamespace(engine=_Engine(connection))


def _assert_current_authority(sql: str) -> None:
    lowered = sql.lower()
    assert "join reasoning_runs rr" in lowered
    assert "join reasoning_run_outputs ro" in lowered
    assert "selected_rc.candidate_id=ro.selected_candidate_id" in lowered
    assert "rr.status='completed' and rr.mode='live'" in lowered
    assert "rcap.manifest->'live_delivery_enabled' = 'true'::jsonb" in lowered
    assert "authority_pack.state='active'" in lowered
    # Freshness is the signal's own lifecycle + expiry, NOT "the graph has not moved since".
    # This assertion used to require `authority_ctx.graph_version = max(graph_version)`, which
    # reason/authority.py:238-244 removed as a bug fix: it emptied the queue the instant any
    # write bumped the graph version (every 6-hourly sync did), while the cards were still open
    # and valid. Asserting its ABSENCE keeps the regression from being reintroduced.
    assert "graph_version = (select coalesce(max(gv.graph_version),0)" not in lowered
    assert "s.authority_expires_at > :authority_time" in lowered


def test_brief_loader_uses_audited_projection_and_bound_config(monkeypatch):
    signal = _Row(
        signal_id="sig_1",
        rule_id="stalled_deal",
        level="prescriptive",
        subject_node_id="node_1",
        score=81,
        score_inputs={"U": 90, "I": 80, "R": 70, "C": 88},
        reason_code="stalled_deal",
        evidence=["evidence_selected"],
        play="follow_up",
        eval_time=NOW,
        config_snapshot_id="cfg_bound",
        scoring_cfg={},
        templates={"stalled_deal": {"fallback": {"situation": "{entity}: stalled deal"}}},
        display_name="Acme",
    )

    def respond(sql, _params):
        if "from signals s" in sql:
            return _Result([signal])
        return _Result()

    connection = _ScriptedConnection(respond)
    monkeypatch.setattr(brief, "authoritative_play_win_rates", lambda *_args: {})

    class _RegistryMustNotOverrideHistory:
        def effective(self, _org_id):
            raise AssertionError("current registry config must not render a historical decision")

    result = brief.load_briefs(
        _store(connection), "org_1", registry=_RegistryMustNotOverrideHistory(), eval_time=NOW)

    signal_sql, params = next(
        (sql, params) for sql, params in connection.statements if "from signals s" in sql)
    _assert_current_authority(signal_sql)
    selected = signal_sql.lower().split("from signals s", 1)[0]
    assert "selected_rc.final_utility_bp" in selected
    assert "authority_payload.payload->'evidence'" in selected
    assert "selected_rc.evidence_refs" in selected
    assert "selected_rc.play_id as play" in selected
    assert "authority_cfg.effective->'scoring'" in selected
    assert "authority_cfg.effective->'templates'" in selected
    assert "s.score as score" not in selected
    assert "s.reason_code" not in selected
    assert "s.evidence" not in selected
    assert "s.play" not in selected
    assert params["authority_time"] == NOW
    assert result[0]["score"] == 81
    assert result[0]["evidence"] == ["evidence_selected"]
    assert result[0]["recommendation"]["play"]["play_id"] == "follow_up"
    assert result[0]["provenance"]["config_snapshot_id"] == "cfg_bound"
    assert any("from graph_versions" in sql.lower() and "for share" in sql.lower()
               for sql, _params in connection.statements)


def test_memory_open_decisions_are_authority_filtered_at_one_time():
    connection = _ScriptedConnection()

    result = memory.load_memory(_store(connection), "org_1", eval_time=NOW)

    signal_sql, params = next(
        (sql, params) for sql, params in connection.statements if "from signals s" in sql)
    _assert_current_authority(signal_sql)
    selected = signal_sql.lower().split("from signals s", 1)[0]
    assert "selected_rc.final_utility_bp" in selected
    assert "s.score" not in selected
    assert "s.reason_code" not in selected
    assert params["authority_time"] == NOW
    overdue_sql, overdue_params = next(
        (sql, params) for sql, params in connection.statements
        if "commitment.due_at" in sql)
    assert "now()" not in overdue_sql.lower()
    assert overdue_params["evaluation_time"] == NOW
    attention_sql, attention_params = next(
        (sql, params) for sql, params in connection.statements
        if "from context_attention a" in sql)
    _assert_current_authority(attention_sql)
    assert "a.score" not in attention_sql.lower()
    assert "a.inputs->>'recency'" in attention_sql.lower()
    assert attention_params["authority_time"] == NOW
    assert result["open_decisions"] == []


def test_summary_counts_and_top_share_one_authoritative_row_set():
    top = _Row(reason_code="cooling_deal", score=82, display_name="Acme", total=12, high=3)

    def respond(sql, _params):
        if "from signals s" in sql:
            return _Result([top])
        return _Result(scalar=0)

    connection = _ScriptedConnection(respond)

    result = summary.build_summary(
        _store(connection), "org_1", horizon="one_minute", eval_time=NOW)

    signal_queries = [(sql, params) for sql, params in connection.statements
                      if "count(*) over () as total" in sql]
    assert len(signal_queries) == 1
    signal_sql, params = signal_queries[0]
    _assert_current_authority(signal_sql)
    assert "count(*) over () as total" in signal_sql.lower()
    assert "selected_rc.final_utility_bp" in signal_sql.lower()
    assert params["authority_time"] == NOW
    assert result["counts"]["open"] == 12
    assert result["counts"]["high"] == 3
    assert result["top_items"] == [
        {"reason": "cooling_deal", "score": 82, "entity": "Acme"}
    ]
    attention_sql, attention_params = next(
        (sql, params) for sql, params in connection.statements
        if "from context_attention a" in sql)
    _assert_current_authority(attention_sql)
    assert "band in ('high','critical')" not in attention_sql.lower()
    assert attention_params["authority_time"] == NOW


def test_play_measurement_groups_by_selected_candidate_not_mutable_signal_play():
    connection = _ScriptedConnection(
        lambda sql, _params: _Result([_Row(
            pack_id="sales", pack_version="1.0.0", play="follow_up", wins=7, n=11)])
        if "from canonical_judgments" in sql else _Result())

    rates = authoritative_play_win_rates(_store(connection), "org_1", eval_time=NOW)

    sql, params = connection.statements[0]
    lowered = sql.lower()
    assert "selected_rc.play_id as play" in lowered
    assert "ro.decision_hash=s.reasoning_decision_hash" in lowered
    assert "selected_rc.candidate_id=s.reasoning_candidate_id" in lowered
    assert "ce.occurred_at < ac.authority_expires_at" in lowered
    assert "ce.occurred_at >= ac.card_created_at" in lowered
    assert "ce.occurred_at <= :as_of" in lowered
    assert "ce.kind='human.card_action'" in lowered
    assert "from canonical_judgments" in lowered
    assert "select s.play" not in lowered
    assert params == {"o": "org_1", "as_of": NOW}
    assert rates == {"sales@1.0.0:follow_up": {
        "pack_id": "sales", "pack_version": "1.0.0", "play_id": "follow_up",
        "wins": 7, "n": 11, "rate_lb": 0.354}}


def test_preventive_is_not_suppressed_by_an_unauthoritative_open_projection():
    rule = {
        "id": "stalled_deal",
        "when": [
            {"path": "deal.status", "op": "=", "value": "open"},
            {"fn": "days_since", "path": "deal.last_inbound", "op": ">=", "value": 7},
        ],
    }

    def respond(sql, _params):
        if "from graph_facts" in sql:
            return _Result([
                _Row(nid="node_1", field="deal.status", value="open"),
                _Row(nid="node_1", field="deal.last_inbound",
                     value="2026-08-01T12:00:00+00:00"),
            ])
        if "from graph_nodes" in sql:
            return _Result([_Row(node_id="node_1", display_name="Acme")])
        return _Result()

    connection = _ScriptedConnection(respond)
    registry = SimpleNamespace(effective=lambda _org_id: ({"rules": [rule]}, "cfg_1"))

    result = modes.load_preventive(
        _store(connection), "org_1", registry=registry, eval_time=NOW)

    signal_sql, params = next(
        (sql, params) for sql, params in connection.statements if "from signals s" in sql)
    _assert_current_authority(signal_sql)
    assert params["authority_time"] == NOW
    assert result[0]["rule_id"] == "stalled_deal"
    assert result[0]["mode"] == "preventive"


def test_executive_loaders_reject_naive_evaluation_time_before_querying():
    connection = _ScriptedConnection()
    naive = datetime(2026, 8, 6, 12)

    with pytest.raises(ValueError, match="timezone-aware"):
        brief.load_briefs(_store(connection), "org_1", eval_time=naive)
    with pytest.raises(ValueError, match="timezone-aware"):
        memory.load_memory(_store(connection), "org_1", eval_time=naive)
    with pytest.raises(ValueError, match="timezone-aware"):
        summary.build_summary(_store(connection), "org_1", eval_time=naive)
    assert connection.statements == []
