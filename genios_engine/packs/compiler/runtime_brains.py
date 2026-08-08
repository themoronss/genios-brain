"""Pinned readers for Organization, Behavior, and Adaptive brain entries.

Layer 6 owns publication.  Layer 3 receives immutable versions and never updates them.  Selection
is explicit by capability, entity/subject key, or a subject key named on the situation; unrelated
tenant memory is not swept into a package merely because it exists.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping, Sequence
from datetime import datetime
from typing import Any, Protocol

from sqlalchemy import text

from genios_engine.contracts.domain_expertise import (
    BrainKind,
    BusinessSituationObject,
    ExpertiseEvidence,
)
from genios_engine.contracts.visibility import SCOPES, Visibility
from genios_engine.platform.canonical import semantic_hash, stable_id

from .errors import BrainPolicyViolation
from .models import RoutePlan, RuntimeBrainEntry, RuntimeBrainSnapshot

_PERMISSION_CATEGORIES = frozenset({
    "approval", "compliance", "constraint", "permission", "policy", "retention", "security",
})
_PREFERENCE_PRECEDENCE = {
    BrainKind.BEHAVIOR: 1,
    BrainKind.ORGANIZATION: 2,
    BrainKind.ADAPTIVE: 3,
}


class RuntimeBrains(Protocol):
    def snapshot(self, *, situation: BusinessSituationObject, plan: RoutePlan,
                 object_ids: Sequence[str]) -> RuntimeBrainSnapshot: ...


def _row_value(row: Any, name: str, default: Any = None) -> Any:
    if isinstance(row, Mapping):
        return row.get(name, default)
    return getattr(row, name, default)


def _json(value: Any) -> dict[str, Any]:
    if isinstance(value, str):
        value = json.loads(value)
    return dict(value or {})


def _visibility_allows_package(entry: Mapping[str, Any], package: Mapping[str, Any]) -> bool:
    """Can every member of the package audience also see the brain evidence?"""
    source = Visibility.model_validate(dict(entry))
    target = Visibility.model_validate(dict(package))
    if SCOPES.index(source.scope) > SCOPES.index(target.scope):
        return False
    if source.scope in {"participants", "private"}:
        return set(target.principals) <= set(source.principals)
    return True


def _selectors(situation: BusinessSituationObject, plan: RoutePlan,
               object_ids: Sequence[str]) -> tuple[str, ...]:
    values = set(situation.brain_subject_keys)
    values.update(plan.capability_ids)
    values.update(object_ids)
    values.add(situation.id)
    for entity in situation.entities:
        value = entity.get("id") or entity.get("entity_id")
        if value:
            values.add(str(value))
    return tuple(sorted(values))


def _relevant(entry: RuntimeBrainEntry, *, capabilities: set[str],
              selectors: set[str]) -> bool:
    if entry.subject_key in selectors:
        return True
    capability = entry.value.get("capability_id")
    if capability is not None and str(capability) in capabilities:
        return True
    segments = set(entry.subject_key.split(":"))
    return bool(segments & selectors)


def _validate_axis(entry: RuntimeBrainEntry) -> None:
    category = str(entry.value.get("category") or entry.value.get("kind") or "").lower()
    if entry.brain in {BrainKind.BEHAVIOR, BrainKind.ADAPTIVE} \
            and category in _PERMISSION_CATEGORIES:
        raise BrainPolicyViolation(
            f"{entry.brain.value} entry {entry.entry_id!r} attempts to define "
            f"permission-axis knowledge ({category})")


def _category(entry: RuntimeBrainEntry) -> str:
    return str(entry.value.get("category") or entry.value.get("kind") or "").lower()


def _resolve_conflicts(entries: Sequence[RuntimeBrainEntry]) \
        -> tuple[tuple[RuntimeBrainEntry, ...], tuple[str, ...], tuple[Mapping[str, Any], ...]]:
    """Resolve only explicitly-declared conflicts; unrelated knowledge is never deep-merged."""
    unkeyed: list[RuntimeBrainEntry] = []
    groups: dict[tuple[str, str], list[RuntimeBrainEntry]] = {}
    for entry in entries:
        raw_key = entry.value.get("conflict_key")
        if not raw_key:
            unkeyed.append(entry)
            continue
        axis = "permission" if _category(entry) in _PERMISSION_CATEGORIES else "preference"
        groups.setdefault((axis, str(raw_key)), []).append(entry)

    selected = list(unkeyed)
    shadowed: list[str] = []
    resolutions: list[Mapping[str, Any]] = []
    for (axis, conflict_key), candidates in sorted(groups.items()):
        if axis == "permission":
            ranked = [(1 if item.brain is BrainKind.ORGANIZATION else 0, item)
                      for item in candidates]
        else:
            ranked = [(_PREFERENCE_PRECEDENCE[item.brain], item) for item in candidates]
        top = max(rank for rank, _ in ranked)
        winners = [item for rank, item in ranked if rank == top]
        if len(winners) != 1:
            raise BrainPolicyViolation(
                f"ambiguous {axis} conflict {conflict_key!r} has {len(winners)} "
                f"entries at the same precedence: {sorted(item.entry_id for item in winners)}")
        winner = winners[0]
        losers = sorted(item.entry_id for item in candidates if item is not winner)
        selected.append(winner)
        shadowed.extend(losers)
        resolutions.append({
            "axis": axis,
            "conflict_key": conflict_key,
            "winner_entry_id": winner.entry_id,
            "winner_brain": winner.brain.value,
            "shadowed_entry_ids": tuple(losers),
        })
    ordered = tuple(sorted(selected, key=lambda item: (
        item.brain.value, item.subject_key, item.version, item.entry_id)))
    return ordered, tuple(sorted(shadowed)), tuple(resolutions)


def _build_snapshot(entries: Iterable[RuntimeBrainEntry], *,
                    situation: BusinessSituationObject, plan: RoutePlan,
                    object_ids: Sequence[str]) -> RuntimeBrainSnapshot:
    selectors = set(_selectors(situation, plan, object_ids))
    capabilities = set(plan.capability_ids)
    included: list[RuntimeBrainEntry] = []
    excluded: list[str] = []
    for entry in sorted(entries, key=lambda item: (
            item.brain.value, item.subject_key, item.version, item.entry_id)):
        if entry.org_id != situation.org_id:
            continue
        if not _relevant(entry, capabilities=capabilities, selectors=selectors):
            continue
        _validate_axis(entry)
        if not _visibility_allows_package(entry.visibility, situation.visibility):
            excluded.append(entry.entry_id)
            continue
        included.append(entry)

    selected, shadowed, resolutions = _resolve_conflicts(included)
    selected_ids = {entry.entry_id for entry in selected}
    manifest = [{
        "brain": entry.brain,
        "entry_id": entry.entry_id,
        "subject_key": entry.subject_key,
        "version": entry.version,
        "content_hash": semantic_hash(entry.value),
        "confidence_bp": entry.confidence_bp,
        "learning_id": entry.learning_id,
        "selected": entry.entry_id in selected_ids,
    } for entry in included]
    snapshot_id = stable_id("runtime_brains", {
        "org_id": situation.org_id,
        "entries": manifest,
    })
    evidence = tuple(ExpertiseEvidence(
        brain=entry.brain,
        source_ref=f"brain:{entry.entry_id}",
        source_version=str(entry.version),
        content_hash=semantic_hash(entry.value),
        confidence_bp=entry.confidence_bp,
        visibility=entry.visibility,
        trace_ids=(entry.trace_id,),
        metadata={
            "learning_id": entry.learning_id,
            "subject_key": entry.subject_key,
            "selection": "selected" if entry.entry_id in selected_ids else "shadowed",
            "conflict_key": entry.value.get("conflict_key"),
        },
    ) for entry in included)
    return RuntimeBrainSnapshot(
        entries=selected,
        evidence=evidence,
        snapshot_id=snapshot_id,
        excluded_entry_ids=tuple(sorted(excluded)),
        shadowed_entry_ids=shadowed,
        conflict_resolutions=resolutions,
    )


class InMemoryRuntimeBrains:
    def __init__(self, entries: Iterable[RuntimeBrainEntry] = ()) -> None:
        self.entries = tuple(entries)

    def snapshot(self, *, situation: BusinessSituationObject, plan: RoutePlan,
                 object_ids: Sequence[str]) -> RuntimeBrainSnapshot:
        return _build_snapshot(self.entries, situation=situation, plan=plan,
                               object_ids=object_ids)


class PostgresRuntimeBrains:
    """Read the active versions published by Layer 6 through one tenant-scoped query."""

    def __init__(self, connection) -> None:
        self.connection = connection

    def snapshot(self, *, situation: BusinessSituationObject, plan: RoutePlan,
                 object_ids: Sequence[str]) -> RuntimeBrainSnapshot:
        selectors = _selectors(situation, plan, object_ids)
        rows = self.connection.execute(text(
            "select org_id,entry_id,brain,subject_key,version,value,confidence_bp,learning_id,"
            "effective_at,visibility,trace_id "
            "from learned_brain_entries "
            "where org_id=:o and active and brain in ('organization','behavior','adaptive') "
            "and ((value->>'capability_id')=any(cast(:capabilities as text[])) "
            "or subject_key=any(cast(:selectors as text[])) "
            "or exists (select 1 from unnest(cast(:selectors as text[])) selected(value) "
            "where position(':' || selected.value || ':' in ':' || subject_key || ':')>0)) "
            "order by brain,subject_key,version,entry_id"),
            {"o": situation.org_id, "capabilities": list(plan.capability_ids),
             "selectors": list(selectors)}).mappings().all()
        entries = tuple(RuntimeBrainEntry(
            org_id=str(_row_value(row, "org_id")),
            brain=BrainKind(str(_row_value(row, "brain"))),
            entry_id=str(_row_value(row, "entry_id")),
            subject_key=str(_row_value(row, "subject_key")),
            version=int(_row_value(row, "version")),
            value=_json(_row_value(row, "value")),
            confidence_bp=int(_row_value(row, "confidence_bp")),
            learning_id=str(_row_value(row, "learning_id")),
            effective_at=_row_value(row, "effective_at"),
            visibility=_json(_row_value(row, "visibility")),
            trace_id=str(_row_value(row, "trace_id")),
        ) for row in rows)
        return _build_snapshot(entries, situation=situation, plan=plan,
                               object_ids=object_ids)


__all__ = [
    "InMemoryRuntimeBrains",
    "PostgresRuntimeBrains",
    "RuntimeBrainEntry",
    "RuntimeBrains",
]
