"""Normalize a mutable legacy ``NodeContext`` into an immutable semantic snapshot."""

from __future__ import annotations

import math
from collections.abc import Mapping
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from genios_engine.contracts.reasoning import ContextSnapshot, EvidenceRef
from genios_engine.platform.canonical import canonical_dumps, semantic_hash, stable_id
from genios_engine.reason.engine import NodeContext
from genios_engine.reason.rules import Rule


def semantic_legacy_value(value: Any) -> Any:
    """Convert legacy numeric state to strict semantic values without losing precision."""
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("legacy context contains a non-finite float")
        return Decimal(str(value))
    if isinstance(value, datetime):
        if value.tzinfo is None or value.utcoffset() is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
    if isinstance(value, Mapping):
        if any(not isinstance(key, str) for key in value):
            raise ValueError("legacy semantic mapping keys must be strings")
        return {key: semantic_legacy_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return tuple(semantic_legacy_value(item) for item in value)
    if isinstance(value, (set, frozenset)):
        normalized = (semantic_legacy_value(item) for item in value)
        return tuple(sorted(normalized, key=canonical_dumps))
    return value


def _relevant_fields(rule: Rule) -> tuple[set[str], set[str]]:
    facts = set(rule.evidence_fields)
    neighbors: set[str] = set()
    if rule.urgency.get("path"):
        facts.add(str(rule.urgency["path"]))
    if rule.linked_deal:
        facts.add("deal.value")
    for condition in rule.when:
        for key in ("path", "exists", "absent"):
            if condition.get(key):
                facts.add(str(condition[key]))
        if condition.get("neighbor_fact"):
            neighbors.add(str(condition["neighbor_fact"]))
    return facts, neighbors


def _confidence_bp(record: Mapping[str, Any]) -> int:
    raw = record.get("confidence", Decimal("0.5"))
    if isinstance(raw, bool):
        return 5_000
    try:
        amount = Decimal(str(raw))
    except Exception:
        return 5_000
    if not amount.is_finite():
        return 0
    if amount <= 1:
        amount *= 10_000
    elif amount <= 100:
        amount *= 100
    return min(10_000, max(0, int(amount.quantize(Decimal("1"), rounding=ROUND_HALF_UP))))


def _authority_rank(record: Mapping[str, Any]) -> int:
    raw = record.get("authority_rank", 1)
    try:
        value = int(raw)
    except (TypeError, ValueError, OverflowError):
        value = 1
    return min(4, max(1, value))


def _occurred_at(record: Mapping[str, Any]) -> datetime | None:
    raw = record.get("occurred_at")
    if isinstance(raw, datetime):
        return semantic_legacy_value(raw)
    if isinstance(raw, str):
        try:
            parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            return None
        return semantic_legacy_value(parsed)
    return None


def legacy_context_snapshot(*, org_id: str, context: NodeContext, rule: Rule,
                            evaluation_time: datetime, graph_version: int = 0,
                            selector_version: str = "legacy.selector.v1") -> ContextSnapshot:
    """Select only the rule-relevant legacy context and content-address it."""
    fact_fields, neighbor_fields = _relevant_fields(rule)
    facts = {
        field: semantic_legacy_value(context.facts[field])
        for field in sorted(fact_fields)
        if field in context.facts
    }
    neighbor_facts = {
        field: semantic_legacy_value(context.neighbor_facts[field])
        for field in sorted(neighbor_fields)
        if field in context.neighbor_facts
    }
    observations = tuple(sorted((
        semantic_legacy_value({
            "kind": item.get("kind"),
            "occurred_at": item.get("occurred_at"),
        })
        for item in context.obs
        if item.get("kind")
    ), key=canonical_dumps))

    evidence = []
    for field in sorted(set(rule.evidence_fields)):
        record = context.facts.get(field)
        if not isinstance(record, Mapping):
            continue
        value = semantic_legacy_value(record.get("value"))
        occurred_at = _occurred_at(record)
        seed = {
            "org_id": org_id,
            "node_id": context.node_id,
            "field": field,
            "value_hash": semantic_hash(value),
            "occurred_at": occurred_at,
            "source_ref_id": record.get("source_ref_id"),
            "fact_version_id": record.get("fact_version_id"),
        }
        evidence.append(EvidenceRef(
            evidence_id=stable_id("evidence", seed),
            field=field,
            value=value,
            source_ref_id=(str(record["source_ref_id"])
                           if record.get("source_ref_id") else None),
            fact_version_id=(str(record["fact_version_id"])
                             if record.get("fact_version_id") else None),
            occurred_at=occurred_at,
            confidence_bp=_confidence_bp(record),
            authority_rank=_authority_rank(record),
            independence_group=(str(record["independence_group"])
                                if record.get("independence_group") else "unattributed"),
        ))

    return ContextSnapshot(
        org_id=org_id,
        graph_version=graph_version,
        root_entity_id=context.node_id,
        root_entity_type=context.node_type,
        evaluation_time=evaluation_time,
        selector_version=selector_version,
        facts=facts,
        observations=observations,
        neighbor_facts=neighbor_facts,
        neighbor_observations=tuple(sorted(str(item) for item in context.neighbor_obs)),
        edge_count=int(context.edge_count),
        evidence=tuple(evidence),
        metadata={"baselines": semantic_legacy_value(context.baselines)},
    )


__all__ = ["legacy_context_snapshot", "semantic_legacy_value"]
