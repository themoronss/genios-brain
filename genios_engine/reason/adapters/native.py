"""Bounded context selection and execution for native Layer 4 capabilities."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from genios_engine.contracts.reasoning import (
    CapabilityManifest,
    ContextSnapshot,
    EvidenceRef,
    ExecutionMode,
    ReasoningRequest,
)
from genios_engine.platform.canonical import canonical_dumps, semantic_hash, stable_id
from genios_engine.reason.engine import NodeContext
from genios_engine.reason.orchestrator import ReasoningExecution, ReasoningOrchestrator
from genios_engine.reason.reasoners import default_registry

from .legacy_context import semantic_legacy_value

_DEFAULT_ORCHESTRATOR = ReasoningOrchestrator(default_registry())


def _selected_fields(capability: CapabilityManifest) -> tuple[tuple[str, ...], tuple[str, ...]]:
    root = set(capability.required_fields)
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
    seed = {
        "org_id": org_id,
        "node_id": node_id,
        "partition": "neighbor" if neighbor else "root",
        "field": field,
        "value_hash": semantic_hash(value),
        "source_ref_id": source_ref,
        "fact_version_id": fact_version,
        "occurred_at": occurred,
    }
    return EvidenceRef(
        evidence_id=stable_id("evidence", seed),
        field=field,
        value=value,
        context_scope="neighbor" if neighbor else "root",
        source_ref_id=source_ref,
        fact_version_id=fact_version,
        occurred_at=occurred,
        confidence_bp=_confidence_bp(mapping) if mapping else 5_000,
        authority_rank=authority_rank,
        independence_group=(str(mapping["independence_group"])
                            if mapping.get("independence_group") else "unattributed"),
    )


def native_context_snapshot(*, org_id: str, context: NodeContext,
                            capability: CapabilityManifest, evaluation_time: datetime,
                            graph_version: int) -> ContextSnapshot:
    """Select exactly the fields declared by one capability from the mutable graph view."""
    root_fields, neighbor_fields = _selected_fields(capability)
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
    ))
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
        metadata={"bounded": True, "capability_id": capability.capability_id},
    )


def reason_native_capability(*, org_id: str, context: NodeContext,
                             capability: CapabilityManifest, evaluation_time: datetime,
                             graph_version: int, config_snapshot_id: str | None,
                             mode: ExecutionMode,
                             orchestrator: ReasoningOrchestrator | None = None
                             ) -> ReasoningExecution:
    snapshot = native_context_snapshot(
        org_id=org_id,
        context=context,
        capability=capability,
        evaluation_time=evaluation_time,
        graph_version=graph_version,
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
    return (orchestrator or _DEFAULT_ORCHESTRATOR).execute(request)


__all__ = ["native_context_snapshot", "reason_native_capability"]
