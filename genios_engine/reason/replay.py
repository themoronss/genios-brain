"""Replay deterministic Layer 4 decisions from immutable input snapshots.

⛔ `03` F139 FOR COVERED FILES (STEP-12, tree `yc2_w27_s12` M33.C1.L-logic.V1.U03). With the test-mode
decider on, a replay re-executes the run and `decide` calls the model again — its cache lives in the
process, so a fresh process pays and may answer differently. A covered file's decision is the expert's
review (`reason/expert/decide`), and that review is stored once (`expert_reviews`): `replay_persisted`
rebuilds such a run's request FROM the stored review, says whether it is the request the run stored
(`review_matches`), and executes it on the expert's own orchestrator — no decider, no R-1, no model, in
any process.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, replace
from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from genios_engine.contracts.reasoning import (
    CapabilityManifest,
    ContextSnapshot,
    EvidenceRef,
    ExecutionMode,
    Goal,
    IntelligenceObject,
    PlayDefinition,
    ReasonerSpec,
    ReasoningRequest,
)

from .orchestrator import ReasoningExecution, ReasoningOrchestrator
from .store import ReasoningStore


@dataclass(frozen=True, slots=True)
class ReplayComparison:
    decision_matches: bool
    reasoners_match: bool
    candidates_match: bool
    expected_decision_hash: str
    actual_decision_hash: str
    differences: tuple[str, ...] = ()
    #: An expert decision only: the request rebuilt from its stored review is the request the run
    #: stored (`_from_the_stored_review`). True for every other run — it rests on no review.
    review_matches: bool = True

    @property
    def matches(self) -> bool:
        return (self.decision_matches and self.reasoners_match and self.candidates_match
                and self.review_matches)


def decanonicalize(value: Any) -> Any:
    """Restore explicitly tagged canonical JSON values used by the replay store."""
    if isinstance(value, Mapping):
        if set(value) == {"$datetime"}:
            return datetime.fromisoformat(str(value["$datetime"]).replace("Z", "+00:00"))
        if set(value) == {"$date"}:
            return date.fromisoformat(str(value["$date"]))
        if set(value) == {"$decimal"}:
            return Decimal(str(value["$decimal"]))
        if set(value) == {"$uuid"}:
            return UUID(str(value["$uuid"]))
        return {str(key): decanonicalize(item) for key, item in value.items()}
    if isinstance(value, list):
        return tuple(decanonicalize(item) for item in value)
    return value


def capability_from_manifest(value: Mapping[str, Any]) -> CapabilityManifest:
    data = decanonicalize(value)
    return CapabilityManifest(
        capability_id=data["capability_id"],
        version=data["version"],
        domain=data["domain"],
        root_entity_type=data["root_entity_type"],
        goal=Goal(**data["goal"]),
        reasoners=tuple(ReasonerSpec(**item) for item in data["reasoners"]),
        plays=tuple(PlayDefinition(**item) for item in data["plays"]),
        required_fields=tuple(data.get("required_fields") or ()),
        # RESTORED, not merely available. `CapabilityManifest.to_semantic_dict` carries
        # `selection_fields` and `capability_snapshot_id` is the address of that dict, so a reader
        # that dropped the field rebuilt a capability that could not address to the row it was
        # read from: every compiled manifest round-tripped here came back with a DIFFERENT
        # `capability_snapshot_id` (measured: 9 selection fields -> 0, ids unequal). Replay is the
        # audit's proof that a stored decision is the decision that was made; a replay conducted
        # under a capability that is not the stored one proves something else.
        selection_fields=tuple(data.get("selection_fields") or ()),
        intelligence_objects=tuple(IntelligenceObject(**item)
                                   for item in data.get("intelligence_objects") or ()),
        ranking_weights=data.get("ranking_weights") or {},
        policies=tuple(data.get("policies") or ()),
        live_delivery_enabled=data.get("live_delivery_enabled", True),
        do_nothing_consequence=data["do_nothing_consequence"],
        expiry_hours=data["expiry_hours"],
        metadata=data.get("metadata") or {},
    )


def context_from_payload(value: Mapping[str, Any]) -> ContextSnapshot:
    data = decanonicalize(value)
    return ContextSnapshot(
        org_id=data["org_id"],
        graph_version=data["graph_version"],
        root_entity_id=data["root_entity_id"],
        root_entity_type=data["root_entity_type"],
        evaluation_time=data["evaluation_time"],
        selector_version=data["selector_version"],
        facts=data.get("facts") or {},
        observations=tuple(data.get("observations") or ()),
        neighbor_facts=data.get("neighbor_facts") or {},
        neighbor_observations=tuple(data.get("neighbor_observations") or ()),
        edge_count=data.get("edge_count", 0),
        evidence=tuple(EvidenceRef(**item) for item in data.get("evidence") or ()),
        missing_fields=tuple(data.get("missing_fields") or ()),
        metadata=data.get("metadata") or {},
    )


def compare_executions(expected: ReasoningExecution,
                       actual: ReasoningExecution) -> ReplayComparison:
    expected_reasoners = tuple((item.reasoner_id, item.semantic_hash)
                               for item in expected.ordered_results)
    actual_reasoners = tuple((item.reasoner_id, item.semantic_hash)
                             for item in actual.ordered_results)
    expected_candidates = tuple(item.semantic_hash for item in expected.candidates)
    actual_candidates = tuple(item.semantic_hash for item in actual.candidates)
    decision_matches = expected.decision.semantic_hash == actual.decision.semantic_hash
    reasoners_match = expected_reasoners == actual_reasoners
    candidates_match = expected_candidates == actual_candidates
    differences = []
    if not decision_matches:
        differences.append("decision_hash")
    if not reasoners_match:
        differences.append("reasoner_results")
    if not candidates_match:
        differences.append("candidates")
    return ReplayComparison(
        decision_matches,
        reasoners_match,
        candidates_match,
        expected.decision.semantic_hash,
        actual.decision.semantic_hash,
        tuple(differences),
    )


def replay_execution(execution: ReasoningExecution,
                     orchestrator: ReasoningOrchestrator) -> tuple[ReasoningExecution,
                                                                   ReplayComparison]:
    request = replace(execution.request, mode=ExecutionMode.REPLAY, request_id=None)
    replayed = orchestrator.execute(request)
    return replayed, compare_executions(execution, replayed)


def request_from_replay_bundle(bundle: Mapping[str, Any]) -> ReasoningRequest:
    run = bundle["run"]
    context_row = bundle["context_snapshot"]
    capability_row = bundle["capability_snapshot"]
    capability = capability_from_manifest(capability_row["manifest"])
    context = context_from_payload(context_row["payload"])
    input_manifest = run.get("input_manifest") or {}
    return ReasoningRequest(
        org_id=run["org_id"],
        capability=capability,
        context=context,
        evaluation_time=run["evaluation_time"],
        trigger_kind=input_manifest.get("original_trigger_kind") or run["trigger_kind"],
        trigger_ref=run.get("trigger_ref"),
        mode=ExecutionMode.REPLAY,
        config_snapshot_id=run.get("config_snapshot_id"),
        policy_snapshot_id=run.get("policy_snapshot_id"),
    )


def _from_the_stored_review(store: ReasoningStore,
                            request: ReasoningRequest) -> tuple[ReasoningRequest, str | None]:
    """An expert run's request rebuilt from the review it names (`expert_reviews`, by file and
    fingerprint), and why it is not the stored request — None when it is. A review gone, or not valid,
    rebuilds nothing: the stored request is replayed, and the comparison says so."""
    from .expert import decide as expert
    from .expert import store as reviews

    record = request.context.facts.get(expert.F_REVIEW)
    pointer = record.get("value") if isinstance(record, Mapping) else None
    pointer = pointer if isinstance(pointer, Mapping) else {}
    with store.engine.connect() as conn:
        row = reviews.read_review(conn, request.org_id, str(pointer.get("file_id") or ""),
                                  str(pointer.get("fingerprint") or ""))
    if row is None or row.status != reviews.VALID:
        return request, "expert_review_missing"
    rebuilt = expert.request_for(
        row, org_id=request.org_id, root_entity_type=request.context.root_entity_type,
        domain=request.capability.domain, eval_time=request.evaluation_time,
        graph_version=request.context.graph_version, mode=ExecutionMode.REPLAY,
        live_delivery_enabled=request.capability.live_delivery_enabled,
        config_snapshot_id=request.config_snapshot_id)
    same = (rebuilt.context.context_snapshot_id == request.context.context_snapshot_id
            and rebuilt.capability.capability_snapshot_id
            == request.capability.capability_snapshot_id)
    return (rebuilt, None) if same else (request, "expert_review")


def replay_persisted(*, store: ReasoningStore, org_id: str, run_id: str,
                     orchestrator: ReasoningOrchestrator) -> tuple[ReasoningExecution,
                                                                   ReplayComparison]:
    """Replay without querying the live graph and compare every semantic decision artifact.

    An expert decision (STEP-12 M33) is replayed from its stored review on the expert's own
    orchestrator, whatever orchestrator the caller holds — see the module docstring."""
    bundle = store.load_replay_bundle(org_id=org_id, run_id=run_id)
    request = request_from_replay_bundle(bundle)
    review_differs = None
    from .expert import decide as expert
    if expert.is_expert(request.capability.capability_id):
        request, review_differs = _from_the_stored_review(store, request)
        orchestrator = expert.orchestrator()
    replayed = orchestrator.execute(request)
    core = (bundle.get("output") or {}).get("decision_core") or {}
    expected_decision = str(core.get("contract_decision_hash") or "")
    expected_reasoners = tuple(tuple(item) for item in core.get("reasoner_result_hashes") or ())
    expected_candidates = tuple(core.get("candidate_hashes") or ())
    # The SAME function the writer used (`audit.audited_results`), not a second reconstruction of
    # it: the stored list is every DECLARED unit — the ones that ran, then the ones the Unit
    # Selector dropped, each carrying its receipt — and rebuilding only `ordered_results` here
    # compared 20 rows against 15 and called an honest run forged. Imported inside the function
    # because `audit` imports this module's neighbours and a module-level import would make the
    # two files import each other.
    from .audit import audited_results

    actual_reasoners = tuple((item.reasoner_id, item.semantic_hash)
                             for item, _input_hash in audited_results(replayed))
    actual_candidates = tuple(item.semantic_hash for item in replayed.candidates)
    decision_matches = expected_decision == replayed.decision.semantic_hash
    reasoners_match = expected_reasoners == actual_reasoners
    candidates_match = expected_candidates == actual_candidates
    differences = tuple(name for name, matched in (
        ("decision_hash", decision_matches),
        ("reasoner_results", reasoners_match),
        ("candidates", candidates_match),
    ) if not matched) + ((review_differs,) if review_differs else ())
    return replayed, ReplayComparison(
        decision_matches=decision_matches,
        reasoners_match=reasoners_match,
        candidates_match=candidates_match,
        expected_decision_hash=expected_decision,
        actual_decision_hash=replayed.decision.semantic_hash,
        differences=differences,
        review_matches=review_differs is None,
    )


__all__ = ["ReplayComparison", "capability_from_manifest", "compare_executions",
           "context_from_payload", "decanonicalize", "replay_execution",
           "replay_persisted", "request_from_replay_bundle"]
