"""The number catalogue — the mechanism doc 05 §2 calls "not a note".

**The rule this module exists to make structural.** The model writes `{do_nothing_cost_bp}`; it
never writes `2500`. `ReasoningBundle.render()` substitutes from `numbers_used` after generation,
in code, over a mapping built HERE from what the deterministic half already computed. So there is
no code path by which a model's digits reach a customer's card — not because the model was asked
nicely, but because a digit in prose is refused by V-4 and a placeholder with no catalogue entry is
refused by V-5.

**Every number in here was computed by something that is not a model.** The decision's own fields,
E4's computed do-nothing, Rule 11's confidence vector, the selected candidate's score components,
and the units' own findings. Nothing is derived from the context snapshot directly: a fact is an
INPUT, and a card that quotes an input as though the engine concluded it is the "fact with a verb"
failure L4.5 exists to end. If a unit thought a fact mattered, the unit published a metric, and the
metric is here.

**Pure, integer, and clockless.** `eval_time` is a parameter. Sorting is total and deterministic,
so the same decision produces the same catalogue in the same order on every machine — which is what
lets the catalogue be part of a prompt that is cached on `decision_hash`.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from types import MappingProxyType

from genios_engine.contracts.reasoning import (
    CandidateDisposition,
    DecisionOutcome,
    ReasonerResult,
    ReasoningDecision,
    ResultStatus,
)

#: The same shape `contracts.reasoning._PLACEHOLDER` accepts, checked here so an illegal name is
#: caught where it is MINTED rather than where it is used — a catalogue entry the model can see and
#: can never legally reference is worse than a missing one.
_NAME = re.compile(r"[a-z][a-z0-9_]{0,63}")
_UNSAFE = re.compile(r"[^a-z0-9]+")

#: How many entries a prompt may carry. A 22-unit roster publishing four metrics each would put a
#: hundred numbers in front of a model that needs six, and a prompt that lists everything teaches
#: nothing about what matters. The order below is the priority, so a truncation drops the least
#: decision-relevant numbers rather than an arbitrary tail.
MAX_CATALOGUE = 40

#: Metric suffixes that are worth naming to a narrator, in priority order. A key that ends in none
#: of these is a number whose UNIT nobody declared — and a number with no unit in a customer
#: sentence is exactly the drift ("$84K -> $840K") V-4 exists to stop.
_METRIC_SUFFIXES = ("_bp", "_days", "_hours", "_count", "_amount", "_usd", "_pct")


@dataclass(frozen=True, slots=True)
class Number:
    """One computed value the narrative may reference by name."""

    name: str
    value: int
    label: str
    #: Where it came from, so the prompt can group by origin and a reviewer can trace one back.
    origin: str

    def __post_init__(self) -> None:
        if not _NAME.fullmatch(self.name):
            raise ValueError(f"catalogue name {self.name!r} is not a legal placeholder name")
        if isinstance(self.value, bool) or not isinstance(self.value, int):
            raise TypeError(f"catalogue value for {self.name!r} must be an integer")


@dataclass(frozen=True, slots=True)
class Catalogue:
    """Every number this decision may be narrated with, and nothing else."""

    numbers: tuple[Number, ...]
    truncated: int = 0

    def __post_init__(self) -> None:
        seen = [item.name for item in self.numbers]
        if len(seen) != len(set(seen)):
            raise ValueError("a catalogue name is minted once — two values under one name is a "
                             "number the card renders arbitrarily")

    @property
    def by_name(self) -> Mapping[str, int]:
        return MappingProxyType({item.name: item.value for item in self.numbers})

    def subset(self, names: Iterable[str]) -> dict[str, int]:
        """`numbers_used` for a generation that referenced exactly these placeholders.

        Unknown names are NOT dropped here: they are V-5's job, and silently omitting one would
        turn "the model referenced a number that does not exist" into "the bundle is missing a
        number", which is the same failure reported one layer too late to be fixed.
        """
        values = self.by_name
        return {name: values[name] for name in dict.fromkeys(names) if name in values}

    def __contains__(self, name: object) -> bool:
        return any(item.name == name for item in self.numbers)

    def __len__(self) -> int:
        return len(self.numbers)


def _slug(value: object) -> str:
    return _UNSAFE.sub("_", str(value).lower()).strip("_")


def _int(value: object) -> int | None:
    """An integer, or None. Booleans are not integers here: `matched=True` rendering as `1` on a
    customer's card is a number nobody computed."""
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value


def _days_between(later: datetime | None, earlier: datetime | None) -> int | None:
    if later is None or earlier is None:
        return None
    return (later - earlier).days


def build_catalogue(decision: ReasoningDecision, results: Sequence[ReasonerResult] = (), *,
                    eval_time: datetime) -> Catalogue:
    """Every number the narrative may use, in priority order. Pure; `eval_time` is the clock."""
    entries: list[Number] = []
    seen: set[str] = set()

    def add(name: str, value: object, label: str, origin: str) -> None:
        number = _int(value)
        if number is None or name in seen:
            return
        seen.add(name)
        entries.append(Number(name=name, value=number, label=label, origin=origin))

    # ── 1 · the decision itself. What it committed to, how sure it is, how long it has. ──────
    add("confidence_pct", decision.confidence_bp // 100,
        "how confident the engine is in this decision, as a percentage", "decision")
    add("outcome_window_days", decision.outcome_window_days,
        "days within which the outcome of acting should be visible", "decision")
    add("decision_expires_in_days", _days_between(decision.expires_at, eval_time),
        "days until this decision's authority expires and it must be re-reasoned", "decision")

    considered = len(decision.candidates)
    eliminated = sum(1 for item in decision.candidates
                     if item.disposition == CandidateDisposition.ELIMINATED)
    add("alternatives_considered", max(0, considered - 1),
        "how many other actions were weighed against the recommended one", "decision")
    add("alternatives_eliminated", eliminated,
        "how many actions an authored rule removed from consideration outright", "decision")
    add("constraints_applied", len(decision.constraints_applied),
        "how many corpus rules were evaluated against this decision", "decision")
    add("citations_available", len(decision.citations),
        "how many authored expert claims this decision rests on", "decision")

    # ── 2 · E4's COMPUTED cost of doing nothing. The contrast the card closes on. ────────────
    do_nothing = dict(decision.do_nothing or {})
    if do_nothing:
        add("do_nothing_cost_bp", do_nothing.get("cost_bp"),
            "the priced cost of not acting, in basis points of the exposure", "do_nothing")
        add("do_nothing_horizon_days", _days_between(do_nothing.get("horizon"), eval_time),
            "days until the cost of not acting is fully realised", "do_nothing")

    # ── 3 · Rule 11's named inputs. Doc 09 case 4: the hedging is bound to the weakest axis. ─
    vector = dict(decision.confidence_vector or {})
    add("independent_evidence_groups", vector.get("independent_evidence_groups"),
        "how many INDEPENDENT sources of evidence agree", "confidence")
    add("evidence_coverage_pct", _pct(vector.get("evidence_coverage_bp")),
        "what share of the facts this decision needed were actually available", "confidence")
    add("corroboration_pct", _pct(vector.get("corroboration_bp")),
        "how strongly the available evidence corroborates itself", "confidence")
    add("source_quality_pct", _pct(vector.get("source_quality_bp")),
        "the authority of the sources this decision read", "confidence")

    # ── 4 · what the ranking actually said about the winner. ────────────────────────────────
    selected = _selected(decision)
    if selected is not None:
        add("recommended_score_pct", selected.utility_bp // 100,
            "the recommended action's final score, as a percentage", "ranking")
        add("formula_score_pct", _pct(selected.formula_utility_bp),
            "what the weighted formula alone scored the recommended action", "ranking")
        add("override_divergence_bp",
            selected.utility_divergence_bp, "by how much a prior disagreed with the formula, in "
            "basis points (signed)", "ranking")
        runner_up = _runner_up(decision)
        if runner_up is not None:
            add("runner_up_score_pct", runner_up.utility_bp // 100,
                "the next best action's score, as a percentage", "ranking")
            add("score_gap_bp", selected.utility_bp - runner_up.utility_bp,
                "how far ahead the recommended action ranked, in basis points", "ranking")
        for component, value in sorted(selected.score_components.items()):
            if component == "formula_utility":
                continue                       # already named above, under the name a card reads
            add(f"{_slug(component)}_component_pct", _pct(value),
                f"the {component.replace('_', ' ')} component of the recommended action's score",
                "ranking")

    # ── 5 · what the UNITS found. Sorted by magnitude so a truncation keeps what mattered. ──
    for name, value, label, origin in _finding_numbers(results):
        add(name, value, label, origin)

    truncated = max(0, len(entries) - MAX_CATALOGUE)
    return Catalogue(numbers=tuple(entries[:MAX_CATALOGUE]), truncated=truncated)


def _pct(value: object) -> int | None:
    number = _int(value)
    return None if number is None else number // 100


def _selected(decision: ReasoningDecision):
    if decision.outcome != DecisionOutcome.DECISION or decision.selected_candidate_id is None:
        return None
    return next((item for item in decision.candidates
                 if item.candidate_id == decision.selected_candidate_id), None)


def _runner_up(decision: ReasoningDecision):
    ranked = sorted((item for item in decision.candidates
                     if item.disposition == CandidateDisposition.ELIGIBLE
                     and item.rank_position is not None),
                    key=lambda item: item.rank_position)
    return ranked[1] if len(ranked) > 1 else None


def _finding_numbers(results: Sequence[ReasonerResult]
                     ) -> list[tuple[str, int, str, str]]:
    """Every magnitude a unit published, ordered by how big it is.

    `value_bp` first, because G-03 canonised it as "how big the thing is" for EVERY unit — before
    it existed a reader had to know which key of `metrics` was the magnitude for that particular
    unit, and a narrator cannot know that. Then the unit-suffixed metrics, which are the numbers
    whose unit somebody declared.

    Ordered by absolute magnitude and broken by name, so the order is total: a catalogue that
    reordered between two runs of the same decision would change the prompt, and a prompt cached on
    `decision_hash` would then be cached on something that is not the decision.
    """
    harvested: list[tuple[int, str, int, str, str]] = []
    for result in results:
        if result.status != ResultStatus.COMPLETED:
            continue
        unit = _slug(result.reasoner_id)
        for finding in result.findings:
            if finding.value_bp is not None:
                name = f"{unit}_{_slug(finding.kind)}_bp"
                harvested.append((abs(finding.value_bp), name, finding.value_bp,
                                  f"{result.reasoner_id} measured {finding.kind.replace('_', ' ')} "
                                  "at this magnitude, in basis points (signed)", unit))
            for key, value in sorted(finding.metrics.items()):
                entry = _metric_entry(unit, result.reasoner_id, key, value,
                                      f"{result.reasoner_id} · {finding.kind}")
                if entry is not None:
                    harvested.append(entry)
        for key, value in sorted(result.metrics.items()):
            entry = _metric_entry(unit, result.reasoner_id, key, value, result.reasoner_id)
            if entry is not None:
                harvested.append(entry)
    harvested.sort(key=lambda item: (-item[0], item[1]))
    out: list[tuple[str, int, str, str]] = []
    for _magnitude, name, value, label, origin in harvested:
        out.append((name, value, label, origin))
    return out


def _metric_entry(unit: str, reasoner_id: str, key: str, value: object, source: str
                  ) -> tuple[int, str, int, str, str] | None:
    number = _int(value)
    if number is None or not key.endswith(_METRIC_SUFFIXES):
        return None
    name = f"{unit}_{_slug(key)}"
    if not _NAME.fullmatch(name):
        return None
    return (abs(number), name, number,
            f"{source} published {key.replace('_', ' ')}", unit)


__all__ = ["Catalogue", "MAX_CATALOGUE", "Number", "build_catalogue"]
