"""Versioned reasoner registry and deterministic DAG planning."""

from __future__ import annotations

import heapq
from collections.abc import Iterable

from genios_engine.contracts.reasoning import ReasonerSpec

from .protocols import Reasoner


class ReasonerRegistryError(ValueError):
    pass


class UnknownReasoner(ReasonerRegistryError):
    pass


class ReasonerDependencyError(ReasonerRegistryError):
    pass


class ReasonerRegistry:
    def __init__(self, reasoners: Iterable[Reasoner] = ()) -> None:
        self._reasoners: dict[tuple[str, str], Reasoner] = {}
        for reasoner in reasoners:
            self.register(reasoner)

    def register(self, reasoner: Reasoner) -> None:
        if not isinstance(reasoner, Reasoner):
            raise TypeError("reasoner does not satisfy the Reasoner protocol")
        key = (reasoner.spec.reasoner_id, reasoner.spec.version)
        held = self._reasoners.get(key)
        if held is not None and held is not reasoner:
            raise ReasonerRegistryError(f"reasoner already registered: {key[0]}@{key[1]}")
        self._reasoners[key] = reasoner

    def get(self, spec: ReasonerSpec) -> Reasoner:
        key = (spec.reasoner_id, spec.version)
        reasoner = self._reasoners.get(key)
        if reasoner is None:
            raise UnknownReasoner(f"unknown reasoner: {key[0]}@{key[1]}")
        return reasoner

    def ordered(self, specs: Iterable[ReasonerSpec]) -> tuple[Reasoner, ...]:
        plan = self.topological_order(specs)
        return tuple(self.get(spec) for spec in plan)

    @staticmethod
    def topological_order(specs: Iterable[ReasonerSpec]) -> tuple[ReasonerSpec, ...]:
        by_id: dict[str, ReasonerSpec] = {}
        for spec in specs:
            if spec.reasoner_id in by_id:
                raise ReasonerDependencyError(f"duplicate reasoner id: {spec.reasoner_id}")
            by_id[spec.reasoner_id] = spec
        indegree = {reasoner_id: 0 for reasoner_id in by_id}
        children: dict[str, set[str]] = {reasoner_id: set() for reasoner_id in by_id}
        for spec in by_id.values():
            for dependency in spec.dependencies:
                if dependency not in by_id:
                    raise ReasonerDependencyError(
                        f"{spec.reasoner_id} depends on missing reasoner {dependency}")
                if spec.reasoner_id == dependency:
                    raise ReasonerDependencyError(f"self dependency: {spec.reasoner_id}")
                if spec.reasoner_id not in children[dependency]:
                    children[dependency].add(spec.reasoner_id)
                    indegree[spec.reasoner_id] += 1
        ready = [reasoner_id for reasoner_id, degree in indegree.items() if degree == 0]
        heapq.heapify(ready)
        ordered: list[ReasonerSpec] = []
        while ready:
            reasoner_id = heapq.heappop(ready)
            ordered.append(by_id[reasoner_id])
            for child in sorted(children[reasoner_id]):
                indegree[child] -= 1
                if indegree[child] == 0:
                    heapq.heappush(ready, child)
        if len(ordered) != len(by_id):
            cyclic = sorted(reasoner_id for reasoner_id, degree in indegree.items() if degree > 0)
            raise ReasonerDependencyError("reasoner dependency cycle: " + ", ".join(cyclic))
        return tuple(ordered)
