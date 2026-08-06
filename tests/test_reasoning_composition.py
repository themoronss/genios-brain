from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone

from genios_engine.contracts.reasoning import (ContextSnapshot, DecisionOutcome, EvidenceRef,
                                               ExecutionMode, ReasoningRequest, ResultStatus)
from genios_engine.packs.capabilities import DEAL_HEALTH_V1
from genios_engine.reason.orchestrator import ReasoningOrchestrator
from genios_engine.reason.composer import compose_deal_health
from genios_engine.reason.reasoners import default_registry


NOW = datetime(2026, 8, 6, 12, tzinfo=timezone.utc)


def _request(*, audited: bool = True) -> ReasoningRequest:
    members = (
        {"signal_id": "sig_1", "rule_id": "cooling_deal",
         "reason_code": "cooling_deal", "subject_node_id": "deal_1", "score": 82,
         "score_inputs": {"U": 80, "C": 90},
         "reasoning_run_id": "rrun_1" if audited else None,
         "config_snapshot_id": "cfg_sales"},
        {"signal_id": "sig_2", "rule_id": "single_threaded",
         "reason_code": "single_threaded_deal", "subject_node_id": "person_1", "score": 74,
         "score_inputs": {"U": 70, "C": 85},
         "reasoning_run_id": "rrun_2",
         "config_snapshot_id": "cfg_sales"},
    )
    evidence = tuple(EvidenceRef(
        f"ev_{index}", "signals.open", member,
        source_ref_id=member["signal_id"],
        fact_version_id=(member["reasoning_run_id"] or "missing_run"),
        confidence_bp=9_000,
        authority_rank=2,
        independence_group=member["reasoning_run_id"] or member["signal_id"],
    ) for index, member in enumerate(members, start=1))
    context = ContextSnapshot(
        org_id="org_1", graph_version=42, root_entity_id="deal_1",
        root_entity_type="deal", evaluation_time=NOW,
        selector_version="sales.deal_health.selector.v1",
        facts={"signals.open": members}, evidence=evidence)
    return ReasoningRequest(
        org_id="org_1", capability=DEAL_HEALTH_V1, context=context,
        evaluation_time=NOW, trigger_kind="signal.composition", trigger_ref="deal_1",
        mode=ExecutionMode.LIVE, config_snapshot_id="cfg_sales")


def test_compound_deal_signal_is_a_real_layer4_decision_with_two_ranked_safe_plays():
    execution = ReasoningOrchestrator(default_registry()).execute(_request())

    assert execution.decision.outcome == DecisionOutcome.DECISION
    assert execution.selected_candidate.play_id == "review_deal"
    assert [candidate.play_id for candidate in execution.candidates] == [
        "review_deal", "monitor_deal"]
    assert execution.authorizes_delivery is True
    assert execution.authorizes_external_mutation is False
    assert set(execution.selected_candidate.evidence_ids) == {"ev_1", "ev_2"}


def test_compound_signal_with_an_unaudited_parent_fails_closed():
    execution = ReasoningOrchestrator(default_registry()).execute(_request(audited=False))

    assert execution.ordered_results[0].status == ResultStatus.FAILED
    assert execution.decision.outcome == DecisionOutcome.FAILED
    assert execution.candidates == ()
    assert execution.authorizes_delivery is False


def test_composer_projects_the_capability_suffix_used_by_the_sweep_fired_set():
    class _Result:
        def fetchall(self):
            return []

        def __iter__(self):
            return iter(())

    class _Connection:
        def __init__(self):
            self.statements = []

        def execute(self, statement, _params=None):
            self.statements.append(str(statement))
            return _Result()

    class _Engine:
        def __init__(self, connection):
            self.connection = connection

        @contextmanager
        def connect(self):
            yield self.connection

    class _Store:
        def __init__(self, connection):
            self.engine = _Engine(connection)

    connection = _Connection()

    assert compose_deal_health(
        _Store(connection), "org_1", NOW, "cfg_sales", adj={}, fired=set(),
        graph_version=42, pack_authority_revision=7,
    ) == {"emitted": 0, "active": set(), "audit_failed": 0}

    parent_sql = next(sql for sql in connection.statements
                      if "s.rule_id <>" in sql.lower())
    assert "regexp_replace(rr.capability_id, '^.*\\.', '') as rule_id" in parent_sql
    assert "rr.capability_id as rule_id" not in parent_sql
