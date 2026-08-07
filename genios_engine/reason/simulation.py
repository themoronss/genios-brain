"""Deterministic, read-only counterfactual simulation over a captured context snapshot."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, replace
from types import MappingProxyType
from typing import Any

from genios_engine.contracts.reasoning import ExecutionMode, ReasoningRequest
from genios_engine.platform.canonical import canonicalize, semantic_hash, stable_id

from .orchestrator import ReasoningExecution, ReasoningOrchestrator


def _freeze(value: Any) -> Any:
    canonicalize(value)
    if isinstance(value, Mapping):
        return MappingProxyType({str(key): _freeze(item) for key, item in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(item) for item in value)
    if isinstance(value, (set, frozenset)):
        return tuple(sorted((_freeze(item) for item in value), key=semantic_hash))
    return value


@dataclass(frozen=True, slots=True)
class SimulationScenario:
    scenario_id: str
    fact_overrides: Mapping[str, Any] = None
    neighbor_fact_overrides: Mapping[str, Any] = None
    remove_fields: tuple[str, ...] = ()
    remove_neighbor_fields: tuple[str, ...] = ()
    edge_count: int | None = None

    def __post_init__(self) -> None:
        scenario_id = str(self.scenario_id or "").strip()
        if not scenario_id:
            raise ValueError("scenario_id is required")
        facts = _freeze(dict(self.fact_overrides or {}))
        neighbors = _freeze(dict(self.neighbor_fact_overrides or {}))
        object.__setattr__(self, "scenario_id", scenario_id)
        object.__setattr__(self, "fact_overrides", facts)
        object.__setattr__(self, "neighbor_fact_overrides", neighbors)
        object.__setattr__(self, "remove_fields", tuple(sorted(set(
            str(item).strip() for item in self.remove_fields if str(item).strip()))))
        object.__setattr__(self, "remove_neighbor_fields", tuple(sorted(set(
            str(item).strip() for item in self.remove_neighbor_fields
            if str(item).strip()))))
        if self.edge_count is not None and (
                isinstance(self.edge_count, bool) or not isinstance(self.edge_count, int)
                or self.edge_count < 0):
            raise ValueError("edge_count must be a non-negative integer")

    @property
    def semantic_hash(self) -> str:
        return semantic_hash({
            "scenario_id": self.scenario_id,
            "fact_overrides": self.fact_overrides,
            "neighbor_fact_overrides": self.neighbor_fact_overrides,
            "remove_fields": self.remove_fields,
            "remove_neighbor_fields": self.remove_neighbor_fields,
            "edge_count": self.edge_count,
        })


@dataclass(frozen=True, slots=True)
class SimulationResult:
    scenario: SimulationScenario
    execution: ReasoningExecution
    baseline_selected_play_id: str | None
    simulated_selected_play_id: str | None
    utility_delta_bp: Mapping[str, int]
    outcome_changed: bool

    def __post_init__(self) -> None:
        object.__setattr__(self, "utility_delta_bp", MappingProxyType(
            dict(self.utility_delta_bp)))


def _selected_play(execution: ReasoningExecution) -> str | None:
    selected = execution.selected_candidate
    return selected.play_id if selected is not None else None


def _scenario_request(request: ReasoningRequest,
                      scenario: SimulationScenario) -> ReasoningRequest:
    context = request.context
    facts = dict(context.facts)
    neighbors = dict(context.neighbor_facts)
    for field in scenario.remove_fields:
        facts.pop(field, None)
    for field in scenario.remove_neighbor_fields:
        neighbors.pop(field, None)
    facts.update(scenario.fact_overrides)
    neighbors.update(scenario.neighbor_fact_overrides)
    changed = set(scenario.remove_fields) | set(scenario.fact_overrides)
    changed_neighbors = set(scenario.remove_neighbor_fields) | set(
        scenario.neighbor_fact_overrides)
    simulated_context = replace(
        context,
        facts=facts,
        neighbor_facts=neighbors,
        edge_count=(scenario.edge_count if scenario.edge_count is not None
                    else context.edge_count),
        # Counterfactual values have no source evidence.  Retaining evidence for an overridden
        # field would make confidence look stronger than the scenario warrants.
        evidence=tuple(item for item in context.evidence
                       if item.field not in changed and item.field not in changed_neighbors),
        selector_version=f"{context.selector_version}.simulation.v1",
        metadata={**dict(context.metadata),
                  "simulation_scenario_id": scenario.scenario_id,
                  "simulation_scenario_hash": scenario.semantic_hash},
        missing_fields=tuple(field for field in context.missing_fields
                             if field not in scenario.fact_overrides
                             and not (field.startswith("neighbor:") and
                                      field.split(":", 1)[1]
                                      in scenario.neighbor_fact_overrides)),
    )
    return replace(
        request,
        context=simulated_context,
        mode=ExecutionMode.SIMULATION,
        trigger_kind="simulation.counterfactual",
        trigger_ref=stable_id("scenario", {"scenario_id": scenario.scenario_id}),
        request_id=None,
    )


def simulate(*, baseline: ReasoningExecution, scenarios: tuple[SimulationScenario, ...],
             orchestrator: ReasoningOrchestrator) -> tuple[SimulationResult, ...]:
    """Run scenarios in stable order; never query or mutate the graph and never authorize delivery."""
    baseline_utilities = {item.play_id: item.utility_bp for item in baseline.candidates}
    baseline_selected = _selected_play(baseline)
    results = []
    ids = [item.scenario_id for item in scenarios]
    if len(ids) != len(set(ids)):
        raise ValueError("simulation scenario IDs must be unique")
    for scenario in sorted(scenarios, key=lambda item: item.scenario_id):
        execution = orchestrator.execute(_scenario_request(baseline.request, scenario))
        simulated = {item.play_id: item.utility_bp for item in execution.candidates}
        all_plays = sorted(set(baseline_utilities) | set(simulated))
        deltas = {play_id: simulated.get(play_id, 0) - baseline_utilities.get(play_id, 0)
                  for play_id in all_plays}
        selected = _selected_play(execution)
        results.append(SimulationResult(
            scenario=scenario,
            execution=execution,
            baseline_selected_play_id=baseline_selected,
            simulated_selected_play_id=selected,
            utility_delta_bp=deltas,
            outcome_changed=(baseline.decision.outcome != execution.decision.outcome
                             or baseline_selected != selected),
        ))
    return tuple(results)


__all__ = ["SimulationResult", "SimulationScenario", "simulate"]
