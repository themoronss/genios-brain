from __future__ import annotations

import json
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from types import MappingProxyType, SimpleNamespace

import pytest

from genios_engine.contracts.reasoning import (
    CandidateCheck,
    CandidateDisposition,
    CheckOutcome,
    ContextSnapshot,
    DecisionCandidate,
    DecisionOutcome,
    EvidenceRef,
    ReasonerResult,
    ReasoningDecision,
    ResultStatus,
)
from genios_engine.reason.store import (
    ContextSnapshotMismatch,
    IdempotencyConflict,
    ReasoningStore,
    _bp,
    _encoded_semantic_hash,
    _json_param,
    _mapping,
    _semantic_hash,
)

NOW = datetime(2026, 8, 6, 9, 30, tzinfo=timezone.utc)


@pytest.mark.parametrize("value", [True, 1.0, 1.5, "100", None])
def test_persistence_basis_points_reject_implicit_numeric_coercion(value):
    with pytest.raises(TypeError, match="integer"):
        _bp(value, "confidence_bp")


def _context() -> ContextSnapshot:
    return ContextSnapshot(
        org_id="org_test",
        graph_version=17,
        root_entity_id="deal_42",
        root_entity_type="deal",
        evaluation_time=NOW,
        selector_version="deal-cooling-v1",
        facts={"deal.stage": "proposal", "deal.value_minor": 2_500_000},
        observations=({"kind": "reply_received", "age_hours": 240},),
        neighbor_facts={"contact.count": 1},
        neighbor_observations=("single_threaded",),
        edge_count=2,
        evidence=(EvidenceRef(
            evidence_id="ev_1",
            field="deal.stage",
            value="proposal",
            source_ref_id="src_1",
            fact_version_id="factv_1",
            occurred_at=NOW - timedelta(days=10),
            confidence_bp=9_000,
            authority_rank=3,
        ),),
        missing_fields=("deal.next_step_at",),
        metadata={"tenant_timezone": "Asia/Kolkata"},
    )


def _candidates() -> tuple[DecisionCandidate, DecisionCandidate, tuple[CandidateCheck, ...]]:
    eligible_check = CandidateCheck(
        play_id="restore_momentum",
        stage="constraint",
        outcome=CheckOutcome.PASS,
        reason_code="read_only_safe",
        evaluator_id="read_only",
        evaluator_version="1",
    )
    eliminated_check = CandidateCheck(
        play_id="send_discount",
        stage="policy",
        outcome=CheckOutcome.ELIMINATE,
        reason_code="approval_missing",
        evaluator_id="commercial_policy",
        evaluator_version="1",
    )
    eligible = DecisionCandidate(
        play_id="restore_momentum",
        play_version="1",
        disposition=CandidateDisposition.ELIGIBLE,
        utility_bp=8_200,
        confidence_bp=8_500,
        score_components={"impact": 8_000, "urgency": 8_600},
        rank_position=1,
        checks=(eligible_check,),
        evidence_ids=("ev_1",),
        parameters={"channel": "email"},
    )
    eliminated = DecisionCandidate(
        play_id="send_discount",
        play_version="1",
        disposition=CandidateDisposition.ELIMINATED,
        utility_bp=5_100,
        confidence_bp=7_000,
        score_components={"impact": 7_000, "risk": 6_500},
        checks=(eliminated_check,),
        evidence_ids=("ev_1",),
    )
    return eligible, eliminated, (eligible_check, eliminated_check)


def _candidate_mappings(values):
    out = []
    for candidate in values:
        item = _mapping(candidate, "candidate")
        item["candidate_id"] = candidate.candidate_id
        out.append(item)
    return out


def _run(context_snapshot_id: str = "ctx_bound") -> dict:
    return {
        "idempotency_key": "event_42:sales.deal_cooling:deal_42",
        "capability_id": "sales.deal_cooling",
        "capability_version": "1.0.0",
        "capability_snapshot_id": "cap_" + "a" * 64,
        "context_snapshot_id": context_snapshot_id,
        "trigger_kind": "event",
        "trigger_ref": "event_42",
        "mode": "live",
        "evaluation_time": NOW,
        "input_manifest": {"rounding": "half_up", "currency": "INR"},
        "reasoner_plan": ["temporal", "risk", "priority", "constraint"],
        "orchestrator_version": "orchestrator-v1",
        "engine_build": "test-build",
        "root_node_id": "deal_42",
    }


def _no_action_output() -> dict:
    return {
        "outcome_kind": "no_action",
        "decision_core": {"reason_code": "no_safe_candidate"},
        "confidence_bp": 0,
        "missing_data": [],
    }


def test_context_snapshot_rejects_payload_metadata_spoof_before_database_write():
    store = ReasoningStore.__new__(ReasoningStore)
    payload = _context().to_semantic_dict()
    payload["org_id"] = "org_other"

    with pytest.raises(ContextSnapshotMismatch, match="payload tenant"):
        store.put_context_snapshot(
            org_id="org_test",
            capability_id="sales.deal_cooling",
            capability_version="1.0.0",
            capability_snapshot_id="cap_" + "a" * 64,
            graph_version=17,
            evaluation_time=NOW,
            selector_version="deal-cooling-v1",
            selector={"root_entity_type": "deal"},
            payload=payload,
            root_node_id="deal_42",
            root_node_type="deal",
        )


def test_context_snapshot_rejects_unreplayable_schema_before_database_write():
    store = ReasoningStore.__new__(ReasoningStore)

    with pytest.raises(ValueError, match="unsupported context snapshot schema version"):
        store.put_context_snapshot(
            org_id="org_test",
            capability_id="sales.deal_cooling",
            capability_version="1.0.0",
            capability_snapshot_id="cap_" + "a" * 64,
            graph_version=17,
            evaluation_time=NOW,
            selector_version="deal-cooling-v1",
            selector={"root_entity_type": "deal"},
            payload=_context().to_semantic_dict(),
            root_node_id="deal_42",
            root_node_type="deal",
            schema_version=3,
        )


def test_immutable_contract_serialization_handles_mapping_proxy_without_asdict():
    snapshot = _context()
    mapped = _mapping(snapshot, "context")

    assert isinstance(mapped["facts"], MappingProxyType)
    assert _semantic_hash(mapped) == snapshot.semantic_hash
    encoded = _json_param(mapped)
    assert '"deal.stage":"proposal"' in encoded
    assert '"$datetime":"2026-08-06T09:30:00.000000Z"' in encoded
    assert _encoded_semantic_hash(json.loads(encoded)) == snapshot.semantic_hash

    result = ReasonerResult(
        reasoner_id="risk",
        reasoner_version="1",
        status=ResultStatus.COMPLETED,
        matched=True,
        metrics={"risk_bp": 7_400},
        evidence_ids=("ev_1",),
        diagnostics={"duration_ms": 3},
    )
    prepared = ReasoningStore.__new__(ReasoningStore)._prepare_results(
        "run_1", "f" * 64, [_mapping(result, "result")])
    assert prepared[0]["status"] == "completed"
    assert prepared[0]["output"]["metrics"]["risk_bp"] == 7_400
    assert prepared[0]["evidence_refs"] == ["ev_1"]

    insufficient = ReasonerResult(
        reasoner_id="relationship",
        reasoner_version="1",
        status=ResultStatus.INSUFFICIENT_CONTEXT,
        missing_fields=("contact.verified_recipient",),
        reason_codes=("required_context_missing",),
    )
    prepared_insufficient = ReasoningStore.__new__(ReasoningStore)._prepare_results(
        "run_1", "f" * 64, [_mapping(insufficient, "result")])
    assert prepared_insufficient[0]["status"] == "insufficient_context"
    assert prepared_insufficient[0]["skip_reason_code"] is None


class _BombEngine:
    def __init__(self):
        self.begin_calls = 0

    def begin(self):
        self.begin_calls += 1
        raise AssertionError("database must not be touched before bundle validation")


def test_invalid_complete_bundle_fails_before_opening_transaction():
    _, eliminated, _ = _candidates()
    engine = _BombEngine()
    store = ReasoningStore(engine=engine)

    with pytest.raises(ValueError, match="eliminated candidate requires an eliminate check"):
        store.persist_complete(
            org_id="org_test",
            run=_run(),
            reasoner_results=[],
            candidates=[eliminated],
            candidate_checks=[],
            output=_no_action_output(),
        )

    assert engine.begin_calls == 0


def test_semantic_replay_hashes_ignore_run_local_persistence_ids():
    eligible, eliminated, checks = _candidates()
    decision = ReasoningDecision(
        outcome=DecisionOutcome.DECISION,
        capability_id="sales.deal_cooling",
        capability_version="1.0.0",
        context_snapshot_id="ctx_bound",
        candidates=(eligible, eliminated),
        selected_candidate_id=eligible.candidate_id,
        confidence_bp=8_300,
        uncertainty=("small_sample",),
        do_nothing_consequence="The deal may continue cooling.",
        expires_at=NOW + timedelta(days=7),
        outcome_window_days=14,
    )
    store = ReasoningStore.__new__(ReasoningStore)

    def prepare(run_id):
        candidates = store._prepare_candidates(
            run_id, _candidate_mappings((eligible, eliminated)))
        prepared_checks = store._prepare_checks(
            run_id, [_mapping(check, "check") for check in checks], candidates)
        output = store._prepare_output(
            run_id, _mapping(decision, "decision"), candidates, prepared_checks)
        return candidates, prepared_checks, output

    first_candidates, first_checks, first_output = prepare("run_live")
    replay_candidates, replay_checks, replay_output = prepare("run_replay")

    assert [item["candidate_id"] for item in first_candidates] != [
        item["candidate_id"] for item in replay_candidates]
    assert [item["candidate_hash"] for item in first_candidates] == [
        item["candidate_hash"] for item in replay_candidates]
    assert [item["check_hash"] for item in first_checks] == [
        item["check_hash"] for item in replay_checks]
    assert first_output["decision_hash"] == replay_output["decision_hash"]


class _Result:
    def __init__(self, *, first=None, rows=(), scalar=None):
        self._first = first
        self._rows = list(rows)
        self._scalar = scalar

    def first(self):
        return self._first

    def scalar(self):
        return self._scalar

    def mappings(self):
        return self

    def all(self):
        return self._rows


class _ConflictConnection:
    def __init__(self):
        self.calls = []

    def execute(self, statement, params):
        sql = str(statement)
        self.calls.append((sql, dict(params)))
        if "from reasoning_context_snapshots" in sql:
            return _Result(first=SimpleNamespace(
                capability_id="sales.deal_cooling",
                capability_version="1.0.0",
                capability_snapshot_id="cap_" + "a" * 64,
                root_node_id="deal_42",
                evaluation_time=NOW,
                context_hash="c" * 64,
            ))
        if "select 1 from reasoning_context_payloads" in sql:
            return _Result(first=SimpleNamespace(present=True))
        if "insert into reasoning_runs" in sql:
            return _Result(first=None)
        if "select run_id, input_hash, output_hash from reasoning_runs" in sql:
            return _Result(first=SimpleNamespace(
                run_id="rrun_existing", input_hash="0" * 64, output_hash="1" * 64))
        raise AssertionError(f"unexpected SQL: {sql}")


class _ConflictEngine:
    def __init__(self):
        self.connection = _ConflictConnection()

    @contextmanager
    def begin(self):
        yield self.connection


def test_idempotency_key_reuse_with_different_content_fails_tenant_scoped():
    engine = _ConflictEngine()
    store = ReasoningStore(engine=engine)

    with pytest.raises(IdempotencyConflict):
        store.persist_complete(
            org_id="org_test",
            run=_run(),
            reasoner_results=[],
            candidates=[],
            candidate_checks=[],
            output=_no_action_output(),
        )

    assert engine.connection.calls
    assert all(params.get("o") == "org_test" for _, params in engine.connection.calls)


class _ReadConnection:
    def __init__(self, allowed_org="org_test"):
        self.allowed_org = allowed_org
        self.calls = []

    def execute(self, statement, params):
        sql = str(statement)
        params = dict(params)
        self.calls.append((sql, params))
        assert "org_id" in sql
        assert "o" in params
        if params["o"] != self.allowed_org:
            return _Result(first=None)
        if "from reasoning_runs" in sql:
            return _Result(first={
                "org_id": self.allowed_org,
                "run_id": params["r"],
                "context_snapshot_id": "ctx_bound",
                "input_manifest": {},
                "reasoner_plan": [],
            })
        if "from reasoning_context_snapshots" in sql:
            return _Result(first={
                "org_id": self.allowed_org,
                "context_snapshot_id": "ctx_bound",
                "source_manifest": [],
                "payload": {"facts": {}},
            })
        if "from reasoning_reasoner_results" in sql:
            return _Result(rows=[])
        if "from reasoning_candidates" in sql:
            return _Result(rows=[])
        if "from reasoning_candidate_checks" in sql:
            return _Result(rows=[])
        if "from reasoning_run_outputs" in sql:
            return _Result(first={
                "org_id": self.allowed_org,
                "run_id": params["r"],
                "ranked_candidate_ids": [],
                "decision_core": {},
                "missing_data": [],
            })
        raise AssertionError(f"unexpected SQL: {sql}")


class _ReadEngine:
    def __init__(self):
        self.connection = _ReadConnection()

    @contextmanager
    def connect(self):
        yield self.connection


def test_load_bundle_never_reads_by_run_id_without_tenant_scope():
    engine = _ReadEngine()
    store = ReasoningStore(engine=engine)

    bundle = store.load_bundle(org_id="org_test", run_id="rrun_1")
    assert bundle["run"]["org_id"] == "org_test"
    assert store.load_bundle(org_id="org_other", run_id="rrun_1") is None

    assert engine.connection.calls
    assert all(params["o"] in {"org_test", "org_other"}
               for _, params in engine.connection.calls)
