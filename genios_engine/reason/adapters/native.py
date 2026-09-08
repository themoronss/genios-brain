"""Bounded context selection and execution for native Layer 4 capabilities."""

from __future__ import annotations

import logging
from collections.abc import Callable, Mapping
from datetime import datetime, timezone
from typing import Any
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from genios_engine.contracts.reasoning import (
    CapabilityManifest,
    ContextSnapshot,
    EvidenceRef,
    ExecutionMode,
    ReasoningRequest,
)
from genios_engine.platform.canonical import canonical_dumps
from genios_engine.reason.engine import NodeContext
from genios_engine.reason.evidence import build_evidence_ref
from genios_engine.reason.orchestrator import ReasoningExecution, ReasoningOrchestrator
from genios_engine.reason.reasoners import default_registry

from .legacy_context import semantic_legacy_value
from .situation_projection import SITUATION_NAMESPACE, SituationProjection

_DEFAULT_ORCHESTRATOR = ReasoningOrchestrator(default_registry())
_log = logging.getLogger(__name__)


def _selected_fields(capability: CapabilityManifest) -> tuple[tuple[str, ...], tuple[str, ...]]:
    # Gate set UNION selection set: pull everything available, gate on the core.
    root = set(capability.required_fields) | set(capability.selection_fields)
    neighbor: set[str] = set()
    for reasoner in capability.reasoners:
        for field in reasoner.required_fields:
            if field.startswith("neighbor:"):
                neighbor.add(field.split(":", 1)[1])
            else:
                root.add(field)
    for play in capability.plays:
        for condition in play.preconditions:
            field = str(condition.get("field") or "")
            if not field:
                continue
            (neighbor if condition.get("neighbor") else root).add(field)
    return tuple(sorted(root)), tuple(sorted(neighbor))


def _confidence_bp(record: Mapping) -> int:
    raw = record.get("confidence_bp", record.get("confidence", 5_000))
    try:
        amount = Decimal(str(raw))
    except (InvalidOperation, ValueError):
        return 5_000
    if not amount.is_finite():
        return 0
    if amount <= 1:
        amount *= 10_000
    elif amount <= 100:
        amount *= 100
    return min(10_000, max(0, int(amount.quantize(Decimal("1"), rounding=ROUND_HALF_UP))))


def _evidence(*, org_id: str, node_id: str, field: str, record, neighbor: bool
              ) -> EvidenceRef:
    mapping = record if isinstance(record, Mapping) else {}
    value = mapping.get("value") if "value" in mapping else record
    value = semantic_legacy_value(value)
    occurred = mapping.get("occurred_at")
    if isinstance(occurred, str):
        try:
            occurred = datetime.fromisoformat(occurred.replace("Z", "+00:00"))
        except ValueError:
            occurred = None
    if isinstance(occurred, datetime):
        if occurred.tzinfo is None or occurred.utcoffset() is None:
            occurred = occurred.replace(tzinfo=timezone.utc)
        occurred = occurred.astimezone(timezone.utc)
    else:
        occurred = None
    source_ref = str(mapping["source_ref_id"]) if mapping.get("source_ref_id") else None
    fact_version = str(mapping["fact_version_id"]) if mapping.get("fact_version_id") else None
    rank = mapping.get("authority_rank", 1)
    try:
        authority_rank = min(4, max(1, int(rank)))
    except (TypeError, ValueError, OverflowError):
        authority_rank = 1
    # DLG-11 · one builder, one seed. `partition` used to be a seed component here and it is
    # not one anywhere now: a neighbour-scoped reading is a claim about a DIFFERENT ENTITY (the
    # 1-hop neighbourhood), so `build_evidence_ref` folds the scope into `entity_ref` instead —
    # the distinction is preserved, and it is preserved somewhere the other two lanes can
    # reproduce without knowing this file exists. `value_hash` and `fact_version_id` leave the
    # identity for the reason the legacy adapter states, and stay on the ref as lineage.
    return build_evidence_ref(
        org_id=org_id,
        entity_ref=node_id,
        field=field,
        value=value,
        context_scope="neighbor" if neighbor else "root",
        source_ref=source_ref,
        observed_at=occurred,
        fact_version_id=fact_version,
        confidence_bp=_confidence_bp(mapping) if mapping else 5_000,
        authority_rank=authority_rank,
        independence_group=(str(mapping["independence_group"])
                            if mapping.get("independence_group") else "unattributed"),
    )


def _projected_declarations(capability: CapabilityManifest) -> frozenset[str]:
    """Every `situation.*` field this capability declares, anywhere it can declare one.

    Read from the capability rather than from the projection so the guard below can fire on a
    manifest that was built WITH a projection and is being reasoned WITHOUT one — which is the
    only way the two can drift, and it is a caller error rather than a thin situation.
    """
    names = set(capability.required_fields) | set(capability.selection_fields)
    for reasoner in capability.reasoners:
        names.update(reasoner.required_fields)
    return frozenset(name for name in names if name.startswith(SITUATION_NAMESPACE))


def native_context_snapshot(*, org_id: str, context: NodeContext,
                            capability: CapabilityManifest, evaluation_time: datetime,
                            graph_version: int,
                            projection: SituationProjection | None = None) -> ContextSnapshot:
    """Select exactly the fields declared by one capability from the mutable graph view.

    DLG-06 · IN-1. `projection` is Layer 2's BSO in snapshot shape — trends, cohort positions,
    anomalies, the six confidence axes, typed absence, the M-4 lifecycle. It is MERGED rather than
    resolved: a projected fact is not in the graph and must never be looked for there, so the
    `situation.*` names are removed from the graph selection before it runs and re-added
    afterwards with the evidence the projection minted. Without that, every projected field would
    be reported `missing` by the very selector that is supposed to supply it.

    The projection's unknown-typed names go to `missing_fields` — never into `facts` as a zero or
    a false. That is the whole of doc 06's UNKNOWABLE rule at this seam: `reason.guards.
    required_missing` already treats a declared field Layer 2 published as missing as missing, so
    an unassessed confidence axis stops a unit that declared it instead of feeding it a midpoint.
    """
    root_fields, neighbor_fields = _selected_fields(capability)
    declared_projected = _projected_declarations(capability)
    if projection is None:
        if declared_projected:
            raise ValueError(
                f"capability {capability.capability_id} declares projected situation facts "
                f"{sorted(declared_projected)} but no projection was supplied — the manifest and "
                "the snapshot were built from different inputs, and reasoning on the difference "
                "would report Layer 2's own readings as missing")
        projected_facts: dict[str, Any] = {}
        projected_evidence: tuple[EvidenceRef, ...] = ()
        projected_unknown: tuple[str, ...] = ()
        projection_receipt: Mapping[str, Any] | None = None
    else:
        if projection.root_entity_id != context.node_id:
            raise ValueError(
                f"projection is anchored on {projection.root_entity_id!r} and the snapshot on "
                f"{context.node_id!r} — a projected evidence ref seeded from a different entity "
                "is an id the backfill cannot reproduce")
        missing_declared = sorted(declared_projected - set(projection.facts)
                                  - set(projection.unknown_fields))
        if missing_declared:
            raise ValueError(
                f"capability {capability.capability_id} declares {missing_declared}, which this "
                "situation's projection neither carries nor types as unknown")
        projected_facts = dict(projection.facts)
        projected_evidence = projection.evidence
        projected_unknown = projection.unknown_fields
        projection_receipt = projection.receipt
    # A projected name is NOT a graph field. Removing it here is what stops the selector looking
    # for `situation.trend.reply_latency` on a company node and reporting an honest absence.
    root_fields = tuple(name for name in root_fields
                        if not name.startswith(SITUATION_NAMESPACE))
    neighbor_fields = tuple(name for name in neighbor_fields
                            if not name.startswith(SITUATION_NAMESPACE))
    # A root field absent on the anchor but present in its 1-hop neighbourhood RESOLVES from there.
    #
    # This is not a convenience. An aggregate anchor — a company — owns no facts directly; the
    # relationship it names lives on the people and threads beneath it, which is exactly where L2
    # writes thread.ball_in_court, deal.status and commitment.due_at. Requiring those on the
    # company node itself asks for a fact the model has no reason to place there, so every compiled
    # capability returned INSUFFICIENT_CONTEXT against a graph that already held its answer.
    #
    # Provenance is preserved, not blurred: the evidence for a borrowed field is emitted with
    # context_scope="neighbor", so a reader can always tell whether the anchor asserted something
    # itself or inherited it. An explicit `neighbor:` declaration still resolves only from the
    # neighbourhood — this widens where a root field MAY be found, never what counts as evidence.
    _borrowed = {field for field in root_fields
                 if field not in context.facts and field in context.neighbor_facts}
    facts = {field: semantic_legacy_value(
                 context.facts[field] if field in context.facts
                 else context.neighbor_facts[field])
             for field in root_fields
             if field in context.facts or field in _borrowed}
    # A borrowed field appears in BOTH partitions, and both placements are load-bearing: `facts`
    # is where the capability looks for a root field, and `neighbor_facts` is the partition its
    # neighbour-scoped evidence must be resolvable against (ContextSnapshot enforces that an
    # evidence ref's field exists in the scope it names). Listing it only in `facts` made the
    # snapshot self-inconsistent and every reasoning call raised instead of deciding.
    neighbor_facts = {field: semantic_legacy_value(context.neighbor_facts[field])
                      for field in set(neighbor_fields) | _borrowed
                      if field in context.neighbor_facts}
    evidence = tuple(
        [_evidence(org_id=org_id, node_id=context.node_id, field=field,
                   record=(context.facts[field] if field in context.facts
                           else context.neighbor_facts[field]),
                   neighbor=field in _borrowed)
         for field in root_fields
         if field in context.facts or field in _borrowed]
        + [_evidence(org_id=org_id, node_id=context.node_id, field=field,
                     record=context.neighbor_facts[field], neighbor=True)
           for field in neighbor_fields if field in context.neighbor_facts]
    )
    missing = tuple(sorted(
        [field for field in root_fields
         if field not in context.facts and field not in _borrowed]
        + [f"neighbor:{field}" for field in neighbor_fields
           if field not in context.neighbor_facts]
        + list(projected_unknown)
    ))
    # MERGED LAST, and it cannot collide: `SituationProjection` refuses a name outside its own
    # namespace and the graph selection above has had that namespace removed.
    facts.update(projected_facts)
    evidence = evidence + tuple(projected_evidence)
    observations = tuple(sorted((semantic_legacy_value({
        "kind": item.get("kind"),
        "occurred_at": item.get("occurred_at"),
    }) for item in context.obs if item.get("kind")), key=canonical_dumps))
    return ContextSnapshot(
        org_id=org_id,
        graph_version=graph_version,
        root_entity_id=context.node_id,
        root_entity_type=context.node_type,
        evaluation_time=evaluation_time,
        selector_version=f"{capability.capability_id}.selector.v1",
        facts=facts,
        observations=observations,
        neighbor_facts=neighbor_facts,
        neighbor_observations=tuple(sorted(str(item) for item in context.neighbor_obs)),
        edge_count=context.edge_count,
        evidence=evidence,
        missing_fields=missing,
        metadata={"bounded": True, "capability_id": capability.capability_id,
                  **({"situation_projection": projection_receipt}
                     if projection_receipt is not None else {})},
    )


def reason_native_capability(*, org_id: str, context: NodeContext,
                             capability: CapabilityManifest, evaluation_time: datetime,
                             graph_version: int, config_snapshot_id: str | None,
                             mode: ExecutionMode,
                             orchestrator: ReasoningOrchestrator | None = None,
                             projection: SituationProjection | None = None,
                             interpreter: Callable[[ReasoningRequest], ReasoningRequest] | None = None
                             ) -> ReasoningExecution:
    """Build the snapshot, optionally interpret its genuine ambiguity, then execute.

    R-1 (`reason/interpretation.AmbiguityInterpreter`) is the only thing `interpreter` is ever
    handed, and it is handed a request and returns a request: a typed reading of an ambiguous claim
    enters as one more FACT with one more evidence ref, and the orchestrator below runs on it exactly
    as it runs on a fact a connector wrote. That ordering is the doctrine — the model contributes an
    input to a deterministic computation and never participates in the computation.

    `None` (every existing caller) is byte-identical to the behaviour before this parameter existed,
    and so is an interpreter that finds nothing or fails: `augment` returns the SAME request object
    when it has nothing to add, so the `context_snapshot_id` does not move and neither does the
    decision hash.
    """
    snapshot = native_context_snapshot(
        org_id=org_id,
        context=context,
        capability=capability,
        evaluation_time=evaluation_time,
        graph_version=graph_version,
        projection=projection,
    )
    request = ReasoningRequest(
        org_id=org_id,
        capability=capability,
        context=snapshot,
        evaluation_time=evaluation_time,
        trigger_kind="capability.graph_scan",
        trigger_ref=capability.capability_id,
        mode=mode,
        config_snapshot_id=config_snapshot_id,
    )
    if interpreter is not None:
        # A failing interpreter must never cost a decision. R-1's own gate already falls back to
        # silence on every internal failure; this is the outer boundary for the case the gate itself
        # cannot reach — a bad client object, a raised import — and it degrades to the request that
        # was going to be executed anyway.
        try:
            interpreted = interpreter(request)
        except Exception:      # noqa: BLE001 — interpretation is optional; the decision is not
            _log.exception("R-1 interpretation failed for org=%s node=%s — reasoning uninterpreted",
                           org_id, context.node_id)
        else:
            if isinstance(interpreted, ReasoningRequest):
                request = interpreted
    return (orchestrator or _DEFAULT_ORCHESTRATOR).execute(request)


__all__ = ["native_context_snapshot", "reason_native_capability"]
