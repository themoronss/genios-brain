"""Persistence boundary for complete deterministic reasoning executions."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import timedelta
from typing import Any

from genios_engine import __version__ as ENGINE_VERSION
from genios_engine.contracts.reasoning import DecisionOutcome, ExecutionMode
from genios_engine.platform.canonical import stable_id

from .orchestrator import ReasoningExecution
from .store import ReasoningStore, ReasoningStoreError

_PERSISTABLE_OUTCOMES = {
    DecisionOutcome.DECISION,
    DecisionOutcome.NO_ACTION,
    DecisionOutcome.DEFER,
    DecisionOutcome.INSUFFICIENT_CONTEXT,
    DecisionOutcome.BLOCKED,
    DecisionOutcome.FAILED,
}


def _trigger_family(trigger_kind: str, mode: ExecutionMode) -> str:
    if mode == ExecutionMode.REPLAY:
        return "replay"
    value = trigger_kind.lower()
    if "query" in value:
        return "query"
    if "schedule" in value or "sweep" in value or "cron" in value:
        return "schedule"
    if "manual" in value:
        return "manual"
    return "event"


def _source_manifest(execution: ReasoningExecution) -> list[dict[str, Any]]:
    return [{
        "evidence_id": item.evidence_id,
        "field": item.field,
        "source_ref_id": item.source_ref_id,
        "fact_version_id": item.fact_version_id,
        "occurred_at": item.occurred_at,
        "confidence_bp": item.confidence_bp,
        "authority_rank": item.authority_rank,
        "independence_group": item.independence_group,
    } for item in execution.request.context.evidence]


def _result_rows(execution: ReasoningExecution) -> list[dict[str, Any]]:
    steps = {step.reasoner_id: step for step in execution.trace.steps}
    rows = []
    for ordinal, result in enumerate(execution.ordered_results):
        step = steps[result.reasoner_id]
        rows.append({
            **result.to_semantic_dict(),
            "ordinal": ordinal,
            "input_hash": step.input_hash,
            "diagnostics": result.diagnostics,
            "skip_reason_code": (result.reason_codes[0]
                                 if result.status.value == "skipped" and result.reason_codes
                                 else None),
            "error_code": (result.reason_codes[0]
                           if result.status.value == "failed" and result.reason_codes else None),
        })
    return rows


def _output(execution: ReasoningExecution) -> dict[str, Any]:
    decision = execution.decision
    ranked = tuple(item.candidate_id for item in execution.candidates
                   if item.rank_position is not None)
    return {
        "outcome_kind": decision.outcome,
        "selected_candidate_id": decision.selected_candidate_id,
        "ranked_candidate_ids": ranked,
        "decision_core": {
            "contract_decision_hash": decision.semantic_hash,
            "contract_decision_id": decision.decision_id,
            "capability_id": decision.capability_id,
            "capability_version": decision.capability_version,
            "context_snapshot_id": decision.context_snapshot_id,
            "uncertainty": decision.uncertainty,
            "do_nothing_consequence": decision.do_nothing_consequence,
            "expires_at": decision.expires_at,
            "outcome_window_days": decision.outcome_window_days,
            "reasoner_result_hashes": tuple(
                (item.reasoner_id, item.semantic_hash) for item in execution.ordered_results),
            "candidate_hashes": tuple(item.semantic_hash for item in execution.candidates),
        },
        "confidence_bp": decision.confidence_bp,
        "missing_data": decision.uncertainty,
    }


def _write_execution_bundle(*, store, execution: ReasoningExecution,
                            idempotency_key: str | None, replay_of_run_id: str | None,
                            engine_build: str, context_payload_ttl_hours: int,
                            connection=None) -> dict[str, Any]:
    """Write all bundle rows, optionally through one caller-owned transaction."""
    request = execution.request
    context = request.context
    capability = request.capability
    connection_kw = {"_conn": connection} if connection is not None else {}
    stored_capability = store.put_capability_snapshot(
        org_id=request.org_id, capability=capability, **connection_kw)
    selector = capability.metadata.get("context_selector")
    if not isinstance(selector, Mapping):
        selector = {
            "root_entity_type": context.root_entity_type,
            "selector_version": context.selector_version,
        }
    stored_context = store.put_context_snapshot(
        org_id=request.org_id,
        capability_id=capability.capability_id,
        capability_version=capability.version,
        capability_snapshot_id=stored_capability["capability_snapshot_id"],
        graph_version=context.graph_version,
        evaluation_time=request.evaluation_time,
        selector_version=context.selector_version,
        selector=selector,
        payload=context.to_semantic_dict(),
        root_node_id=context.root_entity_id,
        root_node_type=context.root_entity_type,
        source_manifest=_source_manifest(execution),
        expires_at=request.evaluation_time + timedelta(hours=context_payload_ttl_hours),
        item_count=(len(context.facts) + len(context.observations)
                    + len(context.neighbor_facts) + len(context.neighbor_observations)),
        **connection_kw,
    )

    persistence_key = idempotency_key or stable_id("idem", {
        "request_hash": request.semantic_hash,
        "mode": request.mode,
        "replay_of_run_id": replay_of_run_id,
    })
    run = {
        "idempotency_key": persistence_key,
        "capability_id": capability.capability_id,
        "capability_version": capability.version,
        "capability_snapshot_id": capability.capability_snapshot_id,
        "context_snapshot_id": stored_context["context_snapshot_id"],
        "config_snapshot_id": request.config_snapshot_id,
        "policy_snapshot_id": request.policy_snapshot_id,
        "trigger_kind": _trigger_family(request.trigger_kind, request.mode),
        "trigger_ref": request.trigger_ref,
        "mode": request.mode,
        "evaluation_time": request.evaluation_time,
        "input_manifest": {
            "request_hash": request.semantic_hash,
            "contract_context_snapshot_id": context.context_snapshot_id,
            "contract_context_hash": context.semantic_hash,
            "trace_run_id": execution.trace.run_id,
            "original_trigger_kind": request.trigger_kind,
            "source_manifest": _source_manifest(execution),
        },
        "reasoner_plan": execution.trace.reasoner_plan,
        "orchestrator_version": execution.trace.orchestrator_version,
        "engine_build": str(engine_build),
        "root_node_id": context.root_entity_id,
        "replay_of_run_id": replay_of_run_id,
    }
    checks = tuple(check for candidate in execution.candidates for check in candidate.checks)
    return store.persist_complete(
        org_id=request.org_id,
        run=run,
        reasoner_results=_result_rows(execution),
        candidates=execution.candidates,
        candidate_checks=checks,
        output=_output(execution),
        **connection_kw,
    )


def persist_execution(*, store: ReasoningStore, execution: ReasoningExecution,
                      idempotency_key: str | None = None,
                      replay_of_run_id: str | None = None,
                      engine_build: str = ENGINE_VERSION,
                      context_payload_ttl_hours: int = 720) -> dict[str, Any]:
    """Commit capability, context, results, candidates, checks, and output as one audit bundle.

    Failed and negative outcomes are audit records, never delivery authority. Persisting them is
    what makes fail-closed behavior inspectable and replayable instead of leaving only a log line.
    """
    if execution.decision.outcome not in _PERSISTABLE_OUTCOMES:
        raise ReasoningStoreError(
            f"cannot persist non-authoritative outcome: {execution.decision.outcome.value}")
    if (isinstance(context_payload_ttl_hours, bool)
            or not isinstance(context_payload_ttl_hours, int)
            or context_payload_ttl_hours <= 0):
        raise ValueError("context_payload_ttl_hours must be a positive integer")
    if execution.request.mode == ExecutionMode.REPLAY and not replay_of_run_id:
        raise ValueError("replay execution requires replay_of_run_id")

    write_args = {
        "store": store,
        "execution": execution,
        "idempotency_key": idempotency_key,
        "replay_of_run_id": replay_of_run_id,
        "engine_build": engine_build,
        "context_payload_ttl_hours": context_payload_ttl_hours,
    }
    if isinstance(store, ReasoningStore):
        with store.engine.begin() as connection:
            return _write_execution_bundle(**write_args, connection=connection)
    # Lightweight protocol doubles remain useful for contract tests and custom stores.
    return _write_execution_bundle(**write_args)


__all__ = ["persist_execution"]
