"""Deterministic situation predicates and generic-object bindings.

Layer 3 does not fetch the graph. It can only inspect the BusinessSituationObject and relevant
context slice already frozen by Layer 2. Unknown predicate inputs remain unknown; they are never
coerced to a match just to keep a route alive.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, DecimalException
from enum import Enum
from typing import Any

from genios_engine.contracts.domain_expertise import (
    BusinessSituationObject,
    SituationContextSlice,
)
from genios_engine.contracts.visibility import SCOPES, Visibility
from genios_engine.platform.canonical import semantic_hash

from .errors import SituationContextConflict
from .models import SourceDocument


class PredicateState(str, Enum):
    TRUE = "true"
    FALSE = "false"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class PredicateVerdict:
    state: PredicateState
    missing: tuple[str, ...] = ()


def _normal(value: Any) -> str:
    return "_".join(str(value or "").strip().lower().replace("-", " ").split())


class ContextAdapter:
    """The only compiler component allowed to look inside the situation context slice."""

    def __init__(self, situation: BusinessSituationObject,
                 context: SituationContextSlice | None = None) -> None:
        self.situation = situation
        self.context = context
        if context is not None:
            if context.org_id != situation.org_id:
                raise SituationContextConflict(
                    f"context org {context.org_id!r} does not match situation org "
                    f"{situation.org_id!r}")
            source = Visibility.model_validate(dict(context.visibility))
            target = Visibility.model_validate(dict(situation.visibility))
            if SCOPES.index(source.scope) > SCOPES.index(target.scope) or (
                    source.scope in {"participants", "private"}
                    and not set(target.principals) <= set(source.principals)):
                raise SituationContextConflict(
                    "context visibility is narrower than the BusinessSituationObject visibility")

        self.facts = self._combine(
            context.facts if context is not None else {},
            situation.metadata.get("facts") or {},
            "fact",
        )
        self.neighbor_facts = self._combine(
            context.neighbor_facts if context is not None else {},
            situation.metadata.get("neighbor_facts") or {},
            "neighbor fact",
        )
        context_baselines = context.metadata.get("baselines") if context is not None else {}
        self.baselines = self._combine(
            context_baselines or {}, situation.metadata.get("baselines") or {}, "baseline")
        observations: set[str] = set()
        raw_observations = (
            *(context.observations if context is not None else ()),
            *(situation.metadata.get("observations") or ()),
        )
        for value in raw_observations:
            if isinstance(value, Mapping):
                value = value.get("kind") or value.get("type")
            if value:
                observations.add(str(value))
        self.observations = frozenset(observations)
        self.neighbor_observations = frozenset({
            *(context.neighbor_observations if context is not None else ()),
            *(str(value) for value in situation.metadata.get("neighbor_observations") or ()),
        })
        self.missing_fields = frozenset({
            *(context.missing_fields if context is not None else ()),
            *(str(value) for value in situation.metadata.get("missing_fields") or ()),
        })

    @staticmethod
    def _combine(primary: Any, inline: Any, label: str) -> Mapping[str, Any]:
        if not isinstance(primary, Mapping) or not isinstance(inline, Mapping):
            raise SituationContextConflict(f"{label} collections must be mappings")
        combined = dict(primary)
        for key, value in inline.items():
            if key in combined and semantic_hash(combined[key]) != semantic_hash(value):
                raise SituationContextConflict(
                    f"conflicting {label} {key!r} in context slice and situation metadata")
            combined[key] = value
        return combined

    def _fact(self, path: str, *, neighbor: bool = False) -> tuple[bool, Any]:
        facts = self.neighbor_facts if neighbor else self.facts
        if path not in facts:
            return False, None
        value = facts[path]
        if isinstance(value, Mapping) and "value" in value:
            value = value["value"]
        return True, value

    def _evaluation_time(self) -> datetime | None:
        if self.context is not None:
            return self.context.evaluation_time.astimezone(timezone.utc)
        raw = self.situation.metadata.get("evaluation_time")
        if isinstance(raw, datetime):
            value = raw
        elif isinstance(raw, str):
            try:
                value = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            except ValueError:
                return None
        else:
            return None
        if value.tzinfo is None or value.utcoffset() is None:
            return None
        return value.astimezone(timezone.utc)

    @staticmethod
    def _compare(actual: Any, op: str, expected: Any) -> bool:
        if op == "=":
            return actual == expected
        if op == "!=":
            return actual != expected
        if op == "IN":
            return isinstance(expected, Sequence) and not isinstance(expected, (str, bytes)) \
                and actual in expected
        if op == ">":
            return actual > expected
        if op == ">=":
            return actual >= expected
        if op == "<":
            return actual < expected
        if op == "<=":
            return actual <= expected
        raise ValueError(f"unsupported authored predicate operator {op!r}")

    def _threshold(self, value: Any) -> tuple[bool, Any]:
        if not isinstance(value, Mapping) or "baseline" not in value:
            return True, value
        name = str(value["baseline"])
        if name not in self.baselines:
            return False, name
        baseline = self.baselines[name]
        if isinstance(baseline, Mapping) and "value" in baseline:
            baseline = baseline["value"]
        multiplier = value.get("mult", 1)
        floor = value.get("floor")
        try:
            threshold = Decimal(str(baseline)) * Decimal(str(multiplier))
            if floor is not None:
                threshold = max(threshold, Decimal(str(floor)))
        except (DecimalException, TypeError, ValueError):
            return False, name
        return True, threshold

    def evaluate(self, condition: Mapping[str, Any]) -> PredicateVerdict:
        if "exists" in condition:
            path = str(condition["exists"])
            if path in self.missing_fields:
                return PredicateVerdict(PredicateState.UNKNOWN, (path,))
            return PredicateVerdict(PredicateState.TRUE if self._fact(path)[0]
                                    else PredicateState.FALSE)
        if "absent" in condition:
            path = str(condition["absent"])
            if path in self.missing_fields:
                return PredicateVerdict(PredicateState.UNKNOWN, (path,))
            return PredicateVerdict(PredicateState.FALSE if self._fact(path)[0]
                                    else PredicateState.TRUE)
        if "has_obs" in condition:
            return PredicateVerdict(PredicateState.TRUE if str(condition["has_obs"])
                                    in self.observations else PredicateState.FALSE)
        if "no_obs" in condition:
            return PredicateVerdict(PredicateState.FALSE if str(condition["no_obs"])
                                    in self.observations else PredicateState.TRUE)
        if "neighbor_has_obs" in condition:
            return PredicateVerdict(
                PredicateState.TRUE if str(condition["neighbor_has_obs"])
                in self.neighbor_observations else PredicateState.FALSE)
        if "neighbor_no_obs" in condition:
            return PredicateVerdict(
                PredicateState.FALSE if str(condition["neighbor_no_obs"])
                in self.neighbor_observations else PredicateState.TRUE)
        if condition.get("fn") == "edge_count":
            actual = self.context.edge_count if self.context is not None \
                else self.situation.metadata.get("edge_count")
            if actual is None:
                return PredicateVerdict(PredicateState.UNKNOWN, ("edge_count",))
            known, expected = self._threshold(condition.get("value"))
            if not known:
                return PredicateVerdict(PredicateState.UNKNOWN, (f"baseline:{expected}",))
            try:
                matched = self._compare(actual, str(condition.get("op") or "="), expected)
            except (TypeError, ValueError):
                return PredicateVerdict(PredicateState.UNKNOWN, ("edge_count",))
            return PredicateVerdict(
                PredicateState.TRUE if matched else PredicateState.FALSE)

        path = condition.get("path") or condition.get("neighbor_fact")
        if not path:
            return PredicateVerdict(PredicateState.UNKNOWN, ("unsupported_predicate",))
        path = str(path)
        present, actual = self._fact(path, neighbor="neighbor_fact" in condition)
        if not present:
            return PredicateVerdict(PredicateState.UNKNOWN, (path,))

        if condition.get("fn") in {"days_since", "hours_since"}:
            evaluation_time = self._evaluation_time()
            if evaluation_time is None:
                return PredicateVerdict(PredicateState.UNKNOWN, ("evaluation_time",))
            try:
                observed = actual if isinstance(actual, datetime) else datetime.fromisoformat(
                    str(actual).replace("Z", "+00:00"))
                if observed.tzinfo is None or observed.utcoffset() is None:
                    raise ValueError("naive")
                seconds = (evaluation_time - observed.astimezone(timezone.utc)).total_seconds()
                actual = Decimal(str(seconds)) / Decimal(
                    86_400 if condition["fn"] == "days_since" else 3_600)
            except (TypeError, ValueError):
                return PredicateVerdict(PredicateState.UNKNOWN, (path,))

        known, expected = self._threshold(condition.get("value"))
        if not known:
            return PredicateVerdict(PredicateState.UNKNOWN, (f"baseline:{expected}",))
        try:
            matched = self._compare(actual, str(condition.get("op") or "="), expected)
        except (TypeError, ValueError):
            return PredicateVerdict(PredicateState.UNKNOWN, (path,))
        return PredicateVerdict(PredicateState.TRUE if matched else PredicateState.FALSE)

    def matches(self, conditions: Sequence[Mapping[str, Any]]) -> PredicateVerdict:
        missing: set[str] = set()
        for condition in conditions:
            verdict = self.evaluate(condition)
            if verdict.state is PredicateState.FALSE:
                return verdict
            if verdict.state is PredicateState.UNKNOWN:
                missing.update(verdict.missing)
        if missing:
            return PredicateVerdict(PredicateState.UNKNOWN, tuple(sorted(missing)))
        return PredicateVerdict(PredicateState.TRUE)

    def bind_objects(self, objects: Sequence[SourceDocument]) -> dict[str, tuple[str, ...]]:
        entities: list[tuple[str, set[str]]] = []
        for index, entity in enumerate(self.situation.entities):
            entity_id = str(entity.get("id") or entity.get("entity_id") or f"entity:{index}")
            names = {
                _normal(entity.get("type")),
                _normal(entity.get("object_type")),
                _normal(entity.get("kind")),
                _normal(entity.get("name")),
            }
            entities.append((entity_id, {value for value in names if value}))

        bindings: dict[str, tuple[str, ...]] = {}
        for document in objects:
            identity = document.content.get("identity") or {}
            aliases = identity.get("aliases") or ()
            object_names = {
                _normal(document.id.rsplit(".", 1)[-1]),
                _normal(identity.get("name")),
                *(_normal(alias) for alias in aliases),
            }
            matched = sorted(entity_id for entity_id, names in entities if object_names & names)
            if matched:
                bindings[document.id] = tuple(matched)
        return bindings


__all__ = ["ContextAdapter", "PredicateState", "PredicateVerdict"]
