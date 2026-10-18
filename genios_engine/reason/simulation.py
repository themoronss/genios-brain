"""Deterministic, read-only counterfactual simulation over a captured context snapshot.

THE TIME-PASSES WHAT-IF (STEP-12, `06` D39; tree `yc2_w27_s12` M32.C2.L-logic.V1.U08). `simulate`
answers a counterfactual in the formula's utilities and needs a finished decision to start from, so it
could not state the one scenario every file has: NOTHING HAPPENS. `time_passes` does, from the file's
own numbers and its playbook — no model, no I/O, no decision: after N days of nothing, how long the file
has been quiet; against the playbook's stop rule (a prior, cited) whether the work is then dormant and
how many days of nothing are left before it is; whether its next date passes; which of its open
situations go past the window their kind holds them to; and the playbook's own words for what doing
nothing costs, carried as its prior. Every number it says is one it was handed or computed from them.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, replace
from datetime import datetime, timedelta
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


# ── the time-passes what-if ─────────────────────────────────────────────────────────────────────

#: The days of nothing the dossier asks about (STEP-12): a few days, a week, two weeks.
TIME_STEPS: tuple[int, ...] = (3, 7, 14)
#: A situation still in play (`context/workstreams.OPEN_STATUSES`); an ended one goes past nothing.
_OPEN = frozenset({"active", "partial"})


def _n(value: float) -> str:
    """A day count as a reader says it — `92`, `12.5` — never with a trailing `.0`."""
    return str(int(value)) if float(value).is_integer() else f"{value:g}"


@dataclass(frozen=True, slots=True)
class TimePasses:
    """What N days of nothing does to one file."""
    days: int
    quiet_days_then: float | None          # quiet now + N; None when the file has no touch
    stop_after_days: int | None            # the playbook's stop rule — a prior, cited
    stop_cited: str | None
    dormant_then: bool | None              # quiet then past the stop rule; None without one
    days_to_dormant: float | None          # the days of nothing left before it is dormant
    next_date: datetime | None
    passes_next_date: bool | None          # N days of nothing pass the next date; None without one
    situations_past_window: tuple[str, ...]   # open situations past their window by then
    do_nothing: str | None                 # the playbook's own words for what doing nothing costs
    says: str

    def as_dict(self) -> dict[str, Any]:
        return {"days": self.days, "quiet_days_then": self.quiet_days_then,
                "stop_after_days": self.stop_after_days, "stop_cited": self.stop_cited,
                "dormant_then": self.dormant_then, "days_to_dormant": self.days_to_dormant,
                "next_date": self.next_date.isoformat() if self.next_date else None,
                "passes_next_date": self.passes_next_date,
                "situations_past_window": list(self.situations_past_window),
                "do_nothing": self.do_nothing, "says": self.says}


def time_passes(*, days: int, now: datetime, quiet_days: float | None,
                stop_after_days: int | None, stop_cited: str | None, do_nothing: str | None,
                lifecycle: Any, next_date: datetime | None) -> TimePasses:
    """What `days` days of nothing do to a file — its quiet days (`FileTimeline.days_quiet`), its
    playbook's stop rule and do-nothing words (`KindPlaybook.stop`, `.do_nothing_consequence`), its
    situations' lifecycle (`context/workstreams.Lifecycle`) and its next date."""
    if isinstance(days, bool) or not isinstance(days, int) or days < 1:
        raise ValueError(f"days is a positive whole number of days, not {days!r}")
    then = None if quiet_days is None else round(float(quiet_days) + days, 1)
    dormant = to_dormant = None
    if then is not None and stop_after_days:
        dormant = then > stop_after_days
        # What is left AFTER the N days — the scenario's own state, not today's (`03` F162).
        to_dormant = max(0.0, round(stop_after_days - then, 1))
    passes = None if next_date is None else next_date <= now + timedelta(days=days)
    past = tuple(sorted(
        s.situation_id for s in getattr(lifecycle, "situations", ()) or ()
        if s.status in _OPEN and s.days_since_seen is not None
        and s.days_since_seen + days > s.quiet_window_days))

    said = [f"After {days} days of nothing"]
    if then is None:
        said.append("the file has no touch to count quiet days from.")
    elif not stop_after_days:
        said.append(f"the file has been quiet {_n(then)} days; its playbook names no stop rule, "
                    "so whether the work goes dormant is not said.")
    else:
        said.append(f"the file has been quiet {_n(then)} days; its playbook's stop rule — a prior — "
                    f"calls the work dormant after {stop_after_days}: "
                    + ("it would be dormant." if dormant else
                       f"{_n(to_dormant)} more days of nothing before it is."))
    if passes is not None:
        said.append("The next date passes." if passes else "The next date is still ahead.")
    if past:
        said.append(f"{len(past)} open situation(s) go past their window.")
    return TimePasses(days=days, quiet_days_then=then, stop_after_days=stop_after_days or None,
                      stop_cited=stop_cited if stop_after_days else None, dormant_then=dormant,
                      days_to_dormant=to_dormant, next_date=next_date, passes_next_date=passes,
                      situations_past_window=past, do_nothing=do_nothing or None,
                      says=" ".join(said))


def what_if_nothing(*, now: datetime, quiet_days: float | None, stop_after_days: int | None,
                    stop_cited: str | None, do_nothing: str | None, lifecycle: Any,
                    next_date: datetime | None) -> tuple[TimePasses, ...]:
    """The what-if at each of `TIME_STEPS` — what the dossier shows."""
    return tuple(time_passes(days=n, now=now, quiet_days=quiet_days,
                             stop_after_days=stop_after_days, stop_cited=stop_cited,
                             do_nothing=do_nothing, lifecycle=lifecycle, next_date=next_date)
                 for n in TIME_STEPS)


__all__ = ["SimulationResult", "SimulationScenario", "TIME_STEPS", "TimePasses", "simulate",
           "time_passes", "what_if_nothing"]
