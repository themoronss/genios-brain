from __future__ import annotations

import re
from contextlib import contextmanager
from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from genios_engine.contracts.reasoning import (
    ContextSnapshot,
    DecisionOutcome,
    EvidenceRef,
    ExecutionMode,
    ReasoningRequest,
)
from genios_engine.packs.capabilities import DEAL_COOLING_V1
from genios_engine.packs.snapshot import snapshot_id as config_snapshot_id
from genios_engine.platform.canonical import canonicalize
from genios_engine.reason.audit import _output, _result_rows, _source_manifest, persist_execution
from genios_engine.reason.orchestrator import ReasoningOrchestrator
from genios_engine.reason.reasoners import default_registry
from genios_engine.reason.replay import (
    capability_from_manifest,
    context_from_payload,
    replay_execution,
    replay_persisted,
)
from genios_engine.reason.store import (
    ContextPayloadExpired,
    ReasoningStore,
    ReplayIntegrityError,
    _mapping,
    _semantic_hash,
    _stable_id,
)


NOW = datetime(2026, 8, 6, 12, tzinfo=timezone.utc)
EFFECTIVE_CONFIG = {
    "pack_id": "sales",
    "version": "1.0.0",
    "state": "shadow",
    "scoring": {"gate": {"s_min": 55, "c_min": 60}},
    "rules": [],
    "plays": {},
    "templates": {},
}
CONFIG_SNAPSHOT_ID = config_snapshot_id(EFFECTIVE_CONFIG)


def _context() -> ContextSnapshot:
    return ContextSnapshot(
        org_id="org_1",
        graph_version=21,
        root_entity_id="deal_1",
        root_entity_type="deal",
        evaluation_time=NOW,
        selector_version="deal_cooling.selector.v1",
        facts={
            "deal.status": {"value": "open", "confidence_bp": 9_500, "src_count": 2},
            "deal.value": {"value": 500_000, "confidence_bp": 9_500, "src_count": 2},
            "derived.engagement": {
                "value_bp": 4_000,
                "confidence_bp": 8_500,
                "src_count": 2,
            },
            "thread.last_inbound": {
                "value": (NOW - timedelta(days=10)).isoformat(),
                "confidence_bp": 9_000,
                "src_count": 2,
            },
            "relationship.verified_stakeholder_count": {"value": 2},
        },
        observations=({"kind": "customer_reply", "occurred_at": NOW - timedelta(days=10)},),
        neighbor_facts={
            "deal.status": "open",
            "contact.verified_recipient": True,
            "account.alternate_stakeholder_verified": True,
        },
        neighbor_observations=("pricing_discussed", "buying_intent"),
        edge_count=2,
        evidence=(
            EvidenceRef(
                "ev_status",
                "deal.status",
                "open",
                source_ref_id="email_1",
                fact_version_id="factv_status_1",
                occurred_at=NOW - timedelta(hours=1),
                confidence_bp=9_500,
                authority_rank=3,
                independence_group="crm",
            ),
            EvidenceRef(
                "ev_engagement",
                "derived.engagement",
                4_000,
                confidence_bp=8_500,
                authority_rank=2,
            ),
            EvidenceRef(
                "ev_inbound",
                "thread.last_inbound",
                (NOW - timedelta(days=10)).isoformat(),
                confidence_bp=9_000,
                authority_rank=2,
            ),
        ),
        metadata={"tenant_timezone": "Asia/Kolkata"},
    )


def _request(*, mode: ExecutionMode = ExecutionMode.LIVE) -> ReasoningRequest:
    return ReasoningRequest(
        org_id="org_1",
        capability=DEAL_COOLING_V1,
        context=_context(),
        evaluation_time=NOW,
        trigger_kind="email.received",
        trigger_ref="event_1",
        mode=mode,
        config_snapshot_id=CONFIG_SNAPSHOT_ID,
    )


def _execution(*, mode: ExecutionMode = ExecutionMode.LIVE):
    return ReasoningOrchestrator(default_registry()).execute(_request(mode=mode))


def _persisted_bundle(execution) -> dict:
    """Build the exact row shape emitted by ReasoningStore, without a database."""
    request = execution.request
    capability = request.capability
    context = request.context
    org_id = request.org_id
    manifest = capability.to_semantic_dict()
    manifest_hash = _semantic_hash(manifest)
    selector = capability.metadata["context_selector"]
    payload = context.to_semantic_dict()
    source_manifest = _source_manifest(execution)
    selector_hash = _semantic_hash(selector)
    payload_hash = _semantic_hash(payload)
    context_material = {
        "schema_version": 2,
        "org_id": org_id,
        "capability_id": capability.capability_id,
        "capability_version": capability.version,
        "capability_snapshot_id": capability.capability_snapshot_id,
        "root_node_id": context.root_entity_id,
        "root_node_type": context.root_entity_type,
        "graph_version": context.graph_version,
        "evaluation_time": request.evaluation_time,
        "selector_version": context.selector_version,
        "selector_hash": selector_hash,
        "payload_hash": payload_hash,
        "source_manifest": source_manifest,
    }
    context_hash = _semantic_hash(context_material)
    context_snapshot_id = _stable_id(
        "ctx", {"org_id": org_id, "context_hash": context_hash})
    reasoner_plan = list(execution.trace.reasoner_plan)
    reasoner_plan_hash = _semantic_hash(reasoner_plan)
    input_manifest = {
        "request_hash": request.semantic_hash,
        "contract_context_snapshot_id": context.context_snapshot_id,
        "contract_context_hash": context.semantic_hash,
        "trace_run_id": execution.trace.run_id,
        "original_trigger_kind": request.trigger_kind,
        "source_manifest": source_manifest,
    }
    run = {
        "org_id": org_id,
        "run_id": "rrun_integrity",
        "idempotency_key": "integrity-test",
        "capability_id": capability.capability_id,
        "capability_version": capability.version,
        "capability_snapshot_id": capability.capability_snapshot_id,
        "context_snapshot_id": context_snapshot_id,
        "config_snapshot_id": request.config_snapshot_id,
        "policy_snapshot_id": request.policy_snapshot_id,
        "trigger_kind": "event",
        "trigger_ref": request.trigger_ref,
        "root_node_id": context.root_entity_id,
        "mode": request.mode.value,
        "status": "completed",
        "evaluation_time": request.evaluation_time,
        "input_manifest": canonicalize(input_manifest),
        "reasoner_plan": canonicalize(reasoner_plan),
        "reasoner_plan_hash": reasoner_plan_hash,
        "orchestrator_version": execution.trace.orchestrator_version,
        "engine_build": "test-build",
        "replay_of_run_id": None,
        "supersedes_run_id": None,
    }
    run["input_hash"] = _semantic_hash({
        "org_id": org_id,
        "context_snapshot_id": context_snapshot_id,
        "capability_snapshot_id": capability.capability_snapshot_id,
        "config_snapshot_id": request.config_snapshot_id,
        "policy_snapshot_id": request.policy_snapshot_id,
        "root_node_id": context.root_entity_id,
        "evaluation_time": request.evaluation_time,
        "trigger_kind": "event",
        "trigger_ref": request.trigger_ref,
        "mode": request.mode.value,
        "replay_of_run_id": None,
        "supersedes_run_id": None,
        "input_manifest": input_manifest,
        "reasoner_plan_hash": reasoner_plan_hash,
        "orchestrator_version": execution.trace.orchestrator_version,
        "engine_build": "test-build",
    })

    store = ReasoningStore.__new__(ReasoningStore)
    prepared_results = store._prepare_results(
        run["run_id"], run["input_hash"], _result_rows(execution))
    candidate_inputs = []
    for candidate in execution.candidates:
        item = _mapping(candidate, "candidate")
        item["candidate_id"] = candidate.candidate_id
        candidate_inputs.append(item)
    prepared_candidates = store._prepare_candidates(run["run_id"], candidate_inputs)
    prepared_checks = store._prepare_checks(
        run["run_id"],
        [_mapping(check, "check") for candidate in execution.candidates
         for check in candidate.checks],
        prepared_candidates,
    )
    prepared_output = store._prepare_output(
        run["run_id"], _output(execution), prepared_candidates, prepared_checks)
    run["output_hash"] = _semantic_hash({
        "reasoner_results": [item["output_hash"] for item in
                             sorted(prepared_results, key=lambda item: item["ordinal"])],
        "candidates": [item["candidate_hash"] for item in
                       sorted(prepared_candidates, key=lambda item: item["candidate_id"])],
        "checks": [item["check_hash"] for item in sorted(
            prepared_checks, key=lambda item: (item["candidate_id"], item["ordinal"]))],
        "decision_hash": prepared_output["decision_hash"],
    })

    def result_row(item):
        row = {**item, "org_id": org_id, "run_id": run["run_id"]}
        for key in ("output", "evidence_refs", "diagnostics"):
            row[key] = canonicalize(row[key])
        return row

    def candidate_row(item):
        row = {**item, "org_id": org_id, "run_id": run["run_id"]}
        for key in ("parameters", "score_components", "evidence_refs"):
            row[key] = canonicalize(row[key])
        return row

    def check_row(item):
        row = {**item, "org_id": org_id, "run_id": run["run_id"]}
        row["detail"] = canonicalize(row["detail"])
        return row

    output_row = {**prepared_output, "org_id": org_id}
    for key in ("ranked_candidate_ids", "decision_core", "missing_data"):
        output_row[key] = canonicalize(output_row[key])
    return {
        "run": run,
        "capability_snapshot": {
            "org_id": org_id,
            "capability_snapshot_id": capability.capability_snapshot_id,
            "capability_id": capability.capability_id,
            "capability_version": capability.version,
            "manifest": canonicalize(manifest),
            "manifest_hash": manifest_hash,
        },
        "config_snapshot": {
            "org_id": org_id,
            "snapshot_id": CONFIG_SNAPSHOT_ID,
            "pack_id": "sales",
            "effective": canonicalize(EFFECTIVE_CONFIG),
            "cause": "test",
        },
        "context_snapshot": {
            "org_id": org_id,
            "context_snapshot_id": context_snapshot_id,
            "capability_id": capability.capability_id,
            "capability_version": capability.version,
            "capability_snapshot_id": capability.capability_snapshot_id,
            "root_node_id": context.root_entity_id,
            "root_node_type": context.root_entity_type,
            "graph_version": context.graph_version,
            "evaluation_time": request.evaluation_time,
            "selector_version": context.selector_version,
            "selector": canonicalize(selector),
            "selector_hash": selector_hash,
            "payload": canonicalize(payload),
            "payload_hash": payload_hash,
            "context_hash": context_hash,
            "source_manifest": canonicalize(source_manifest),
            "item_count": (len(context.facts) + len(context.observations)
                           + len(context.neighbor_facts) + len(context.neighbor_observations)),
            "schema_version": 2,
        },
        "reasoner_results": [result_row(item) for item in prepared_results],
        "candidates": [candidate_row(item) for item in prepared_candidates],
        "candidate_checks": [check_row(item) for item in prepared_checks],
        "output": output_row,
    }


class _RecordingStore:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []

    def put_capability_snapshot(self, **kwargs):
        self.calls.append(("capability", kwargs))
        capability = kwargs["capability"]
        return {
            "org_id": kwargs["org_id"],
            "capability_snapshot_id": capability.capability_snapshot_id,
            "capability_id": capability.capability_id,
            "capability_version": capability.version,
            "manifest_hash": capability.semantic_hash,
        }

    def put_context_snapshot(self, **kwargs):
        self.calls.append(("context", kwargs))
        return {
            "org_id": kwargs["org_id"],
            "context_snapshot_id": "ctx_persisted",
            "context_hash": "c" * 64,
        }

    def persist_complete(self, **kwargs):
        self.calls.append(("complete", kwargs))
        return {"run": {"run_id": "rrun_persisted"}, "output": kwargs["output"]}


def test_persist_execution_writes_ordered_complete_tenant_scoped_audit_bundle():
    execution = _execution()
    store = _RecordingStore()

    persisted = persist_execution(
        store=store,
        execution=execution,
        idempotency_key="idem_explicit",
        engine_build="build-42",
    )

    assert [name for name, _ in store.calls] == ["capability", "context", "complete"]
    capability_call = store.calls[0][1]
    context_call = store.calls[1][1]
    complete_call = store.calls[2][1]
    run = complete_call["run"]

    assert capability_call == {"org_id": "org_1", "capability": DEAL_COOLING_V1}
    assert context_call["org_id"] == complete_call["org_id"] == "org_1"
    assert context_call["capability_snapshot_id"] == DEAL_COOLING_V1.capability_snapshot_id
    assert context_call["payload"] == execution.request.context.to_semantic_dict()
    assert context_call["source_manifest"][0]["evidence_id"] == "ev_engagement"
    assert run["idempotency_key"] == "idem_explicit"
    assert run["capability_snapshot_id"] == DEAL_COOLING_V1.capability_snapshot_id
    assert run["context_snapshot_id"] == "ctx_persisted"
    assert run["config_snapshot_id"] == CONFIG_SNAPSHOT_ID
    assert run["policy_snapshot_id"] == execution.request.policy_snapshot_id
    assert run["trigger_kind"] == "event"
    assert run["trigger_ref"] == "event_1"
    assert run["engine_build"] == "build-42"
    assert run["input_manifest"]["request_hash"] == execution.request.semantic_hash
    assert run["input_manifest"]["contract_context_snapshot_id"] == (
        execution.request.context.context_snapshot_id
    )
    assert run["input_manifest"]["contract_context_hash"] == (
        execution.request.context.semantic_hash
    )
    assert run["input_manifest"]["trace_run_id"] == execution.trace.run_id
    assert run["input_manifest"]["original_trigger_kind"] == "email.received"
    assert tuple(complete_call["reasoner_results"][index]["reasoner_id"]
                 for index in range(len(execution.ordered_results))) == (
        tuple(item.reasoner_id for item in execution.ordered_results)
    )
    assert complete_call["candidates"] == execution.candidates
    assert len(complete_call["candidate_checks"]) == sum(
        len(candidate.checks) for candidate in execution.candidates
    )
    assert complete_call["output"]["decision_core"]["contract_decision_hash"] == (
        execution.decision.semantic_hash
    )
    assert persisted["run"]["run_id"] == "rrun_persisted"


def test_real_reasoning_store_writes_the_entire_bundle_through_one_transaction():
    token = object()

    class _Engine:
        begin_calls = 0

        @contextmanager
        def begin(self):
            self.begin_calls += 1
            yield token

    class _AtomicStore(ReasoningStore):
        def __init__(self):
            self._engine = _Engine()
            self.connections = []

        def put_capability_snapshot(self, **kwargs):
            self.connections.append(kwargs.pop("_conn"))
            capability = kwargs["capability"]
            return {"capability_snapshot_id": capability.capability_snapshot_id}

        def put_context_snapshot(self, **kwargs):
            self.connections.append(kwargs.pop("_conn"))
            return {"context_snapshot_id": "ctx_persisted"}

        def persist_complete(self, **kwargs):
            self.connections.append(kwargs.pop("_conn"))
            return {"run": {"run_id": "rrun_persisted"}, "output": kwargs["output"]}

    store = _AtomicStore()

    persisted = persist_execution(store=store, execution=_execution())

    assert store.engine.begin_calls == 1
    assert store.connections == [token, token, token]
    assert persisted["run"]["run_id"] == "rrun_persisted"


def test_failed_outcome_is_persisted_as_non_authoritative_audit_evidence():
    execution = _execution()
    failed_decision = replace(
        execution.decision,
        outcome=DecisionOutcome.FAILED,
        candidates=(),
        selected_candidate_id=None,
        outcome_window_days=None,
    )
    failed_execution = replace(execution, candidates=(), decision=failed_decision)
    store = _RecordingStore()

    persisted = persist_execution(store=store, execution=failed_execution)

    assert [name for name, _ in store.calls] == ["capability", "context", "complete"]
    assert store.calls[-1][1]["output"]["outcome_kind"] == DecisionOutcome.FAILED
    assert persisted["run"]["run_id"] == "rrun_persisted"


def test_canonical_capability_manifest_and_context_payload_round_trip_exactly():
    context = _context()

    restored_capability = capability_from_manifest(
        canonicalize(DEAL_COOLING_V1.to_semantic_dict())
    )
    restored_context = context_from_payload(canonicalize(context.to_semantic_dict()))

    assert restored_capability.to_semantic_dict() == DEAL_COOLING_V1.to_semantic_dict()
    assert restored_capability.semantic_hash == DEAL_COOLING_V1.semantic_hash
    assert restored_capability.capability_snapshot_id == DEAL_COOLING_V1.capability_snapshot_id
    assert restored_context.to_semantic_dict() == context.to_semantic_dict()
    assert restored_context.semantic_hash == context.semantic_hash
    assert restored_context.context_snapshot_id == context.context_snapshot_id
    assert restored_context.evidence[-1].occurred_at == NOW - timedelta(hours=1)


def test_replay_bundle_verifies_every_persisted_semantic_hash_before_execution():
    bundle = _persisted_bundle(_execution())

    ReasoningStore.__new__(ReasoningStore).verify_replay_bundle(bundle, org_id="org_1")


@pytest.mark.parametrize(
    ("path", "replacement", "message"),
    (
        (("capability_snapshot", "manifest", "expiry_hours"), 999,
         "capability manifest hash"),
        (("context_snapshot", "selector", "max_edges"), 999,
         "context selector hash"),
        (("run", "mode"), "simulation", "run input hash"),
        (("run", "trigger_kind"), "manual", "run input hash"),
        (("run", "trigger_ref"), "different-event", "run input hash"),
        (("run", "policy_snapshot_id"), "policy_tampered", "capability policy snapshot"),
        (("run", "replay_of_run_id"), "rrun_parent", "run input hash"),
        (("run", "supersedes_run_id"), "rrun_old", "run input hash"),
        (("config_snapshot", "effective", "version"), "9.9.9", "config snapshot id"),
        (("run", "root_node_id"), "deal_other", "run root node"),
        (("reasoner_results", 0, "output", "matched"), False,
         "reasoner output hash"),
        (("candidates", 0, "confidence_bp"), 1,
         "candidate hash"),
        (("candidate_checks", 0, "reason_code"), "tampered",
         "candidate check hash"),
        (("output", "confidence_bp"), 1,
         "decision output hash"),
    ),
)
def test_replay_bundle_rejects_tampered_capability_context_run_and_children(
        path, replacement, message):
    bundle = deepcopy(_persisted_bundle(_execution()))
    target = bundle
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = replacement

    with pytest.raises(ReplayIntegrityError, match=message):
        ReasoningStore.__new__(ReasoningStore).verify_replay_bundle(
            bundle, org_id="org_1")


def test_replay_execution_exactly_matches_every_decision_artifact_and_never_authorizes():
    execution = _execution()

    replayed, comparison = replay_execution(
        execution, ReasoningOrchestrator(default_registry())
    )

    assert execution.authorizes_delivery is False  # native capability remains shadow-locked
    assert replayed.request.mode == ExecutionMode.REPLAY
    assert replayed.authorizes_delivery is False
    assert comparison.matches is True
    assert comparison.decision_matches is True
    assert comparison.reasoners_match is True
    assert comparison.candidates_match is True
    assert comparison.differences == ()
    assert replayed.decision.semantic_hash == execution.decision.semantic_hash
    assert tuple((item.reasoner_id, item.semantic_hash) for item in replayed.ordered_results) == (
        tuple((item.reasoner_id, item.semantic_hash) for item in execution.ordered_results)
    )
    assert tuple(item.semantic_hash for item in replayed.candidates) == (
        tuple(item.semantic_hash for item in execution.candidates)
    )


def test_replay_rejects_expired_context_payload_even_before_retention_purge():
    bundle = _persisted_bundle(_execution())
    bundle["context_snapshot"]["payload_expires_at"] = (
        datetime.now(timezone.utc) - timedelta(seconds=1))

    with pytest.raises(ContextPayloadExpired):
        ReasoningStore.__new__(ReasoningStore).verify_replay_bundle(bundle, org_id="org_1")


def test_persisted_replay_loader_checks_ttl_before_loading_capability():
    store = ReasoningStore.__new__(ReasoningStore)
    store.load_bundle = lambda **_kwargs: {
        "run": {"capability_snapshot_id": DEAL_COOLING_V1.capability_snapshot_id,
                "config_snapshot_id": None},
        "context_snapshot": {
            "context_snapshot_id": "ctx_expired",
            "payload": {"org_id": "org_1"},
            "payload_expires_at": datetime.now(timezone.utc) - timedelta(seconds=1),
        },
    }
    store.load_capability_snapshot = lambda **_kwargs: pytest.fail(
        "expired replay must stop before capability loading")

    with pytest.raises(ContextPayloadExpired, match="ctx_expired"):
        store.load_replay_bundle(org_id="org_1", run_id="rrun_expired")


class _ReplayBundleStore:
    def __init__(self, bundle: dict) -> None:
        self.bundle = bundle
        self.calls: list[dict[str, str]] = []

    def load_replay_bundle(self, **kwargs):
        self.calls.append(kwargs)
        return self.bundle


class _ReasonerDriftOrchestrator:
    def __init__(self) -> None:
        self._delegate = ReasoningOrchestrator(default_registry())
        self.last_request = None

    def execute(self, request):
        self.last_request = request
        actual = self._delegate.execute(request)
        first = replace(
            actual.ordered_results[0],
            reason_codes=actual.ordered_results[0].reason_codes + ("synthetic_drift",),
        )
        return replace(actual, ordered_results=(first, *actual.ordered_results[1:]))


def test_persisted_replay_is_tenant_scoped_never_authorizes_and_detects_hash_drift():
    execution = _execution()
    recording_store = _RecordingStore()
    persist_execution(
        store=recording_store,
        execution=execution,
        idempotency_key="idem_original",
    )
    complete_call = recording_store.calls[-1][1]
    run = dict(complete_call["run"])
    run["org_id"] = "org_1"
    bundle = {
        "run": run,
        "context_snapshot": {
            "payload": canonicalize(execution.request.context.to_semantic_dict())
        },
        "capability_snapshot": {
            "manifest": canonicalize(execution.request.capability.to_semantic_dict())
        },
        "output": canonicalize(complete_call["output"]),
    }
    store = _ReplayBundleStore(bundle)
    drifting_orchestrator = _ReasonerDriftOrchestrator()

    replayed, comparison = replay_persisted(
        store=store,
        org_id="org_1",
        run_id="rrun_original",
        orchestrator=drifting_orchestrator,
    )

    assert store.calls == [{"org_id": "org_1", "run_id": "rrun_original"}]
    assert drifting_orchestrator.last_request.mode == ExecutionMode.REPLAY
    assert replayed.authorizes_delivery is False
    assert comparison.matches is False
    assert comparison.decision_matches is True
    assert comparison.reasoners_match is False
    assert comparison.candidates_match is True
    assert comparison.differences == ("reasoner_results",)


def test_migration_0029_has_splitter_safe_tenant_scoped_capability_and_signal_links():
    migration = Path(__file__).resolve().parents[1] / (
        "migrations/0029_l4_capability_and_signal_trace.sql"
    )
    sql = migration.read_text()
    lowered = sql.lower()
    cleaned = re.sub(r"--[^\n]*", "", sql)
    statements = [statement.strip() for statement in cleaned.split(";") if statement.strip()]

    assert "do $$" not in lowered
    assert len(statements) == 6
    assert statements[0].lower().startswith(
        "create table if not exists reasoning_capability_snapshots"
    )
    assert "primary key (org_id, capability_snapshot_id)" in lowered
    assert "unique (org_id, capability_id, capability_version)" in lowered
    assert "foreign key (org_id, capability_snapshot_id)" in lowered
    assert "references reasoning_capability_snapshots (org_id, capability_snapshot_id)" in lowered
    assert "alter table signals add column if not exists reasoning_run_id text" in lowered
    assert "foreign key (org_id, reasoning_run_id)" in lowered
    assert "references reasoning_runs (org_id, run_id)" in lowered
    assert "on signals (org_id, reasoning_run_id)" in lowered
    assert "where reasoning_run_id is not null" in lowered


def test_migration_0030_preserves_replay_bytes_and_signal_run_config_integrity():
    migration = Path(__file__).resolve().parents[1] / (
        "migrations/0030_l4_replay_and_signal_integrity.sql"
    )
    sql = migration.read_text()
    lowered = sql.lower()

    assert "add column if not exists selector jsonb" in lowered
    assert "'insufficient_context'" in lowered
    assert "'failed'" in lowered
    assert "unique (org_id, run_id, config_snapshot_id)" in lowered
    assert "foreign key (org_id, config_snapshot_id)" in lowered
    assert "references config_snapshots (org_id, snapshot_id)" in lowered
    assert "foreign key (org_id, reasoning_run_id, config_snapshot_id)" in lowered
    assert "references reasoning_runs (org_id, run_id, config_snapshot_id)" in lowered
    assert "reasoning_run_id is null or config_snapshot_id is not null" in lowered
    assert "not valid" in lowered


def test_migration_0031_cascades_tenant_owned_config_snapshots():
    migration = Path(__file__).resolve().parents[1] / (
        "migrations/0031_l4_signal_authority_projection.sql"
    )
    lowered = migration.read_text().lower()

    assert "alter table config_snapshots" in lowered
    assert "foreign key (org_id) references orgs (id) on delete cascade" in lowered
    assert "config_snapshots_org_fk" in lowered
