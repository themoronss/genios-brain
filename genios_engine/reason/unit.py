"""Layer 4 · Part 2 — the reasoning unit framework.

Every unit in GeniOS has the same anatomy.  That is the whole point: you do not build seventeen
systems, you build one framework and seventeen implementations of it.  A unit that looks like every
other unit can be reviewed, tested, timed, and replaced by someone who has never seen it before.

    Input      → what the capability handed this unit
    Validator  → refuse to reason from inputs that cannot support a conclusion
    Retriever  → select the slice of the frozen snapshot this unit needs
    Analyzer   → plugins each contribute partial evidence  ← the IP lives here
    Calculator → pure integer arithmetic over that evidence
    Evaluator  → turn numbers into meaning (82 → high risk)
    Builder    → one typed object, the same shape every unit returns
    Metrics    → what this unit publishes, declared rather than discovered

Two deliberate departures from a literal reading of the architecture, both forced by laws that
outrank the diagram:

**The Retriever does not fetch.**  Units are forbidden to touch a database, network, or clock —
that is what makes a decision replayable months later.  Retrieval already happened when Layer 2
froze the ContextSnapshot.  So "Retriever" here means *select and shape* from that frozen input,
which is the only form of retrieval that can survive replay.

**The stages are methods, not files.**  The value of the framework is uniformity, isolated
testability, and the plugin seam inside the Analyzer — none of which require eight files around a
forty-line calculation.  `evaluate()` below is a template method: it runs the stages in order,
enforces the contract between them, and cannot be overridden by a subclass, so no unit can quietly
skip validation or invent its own result shape.

**Why plugins matter.**  Risk is not one algorithm.  It is time decay *plus* revenue exposure
*plus* relationship health *plus* policy — each a small deterministic contribution that can be
tested, tuned, and versioned alone.  A unit composes plugins; it does not hide a monolith.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from enum import Enum
from types import MappingProxyType
from typing import Any, Protocol, runtime_checkable

from genios_engine.contracts.reasoning import (
    CandidateAdjustment,
    CandidateCheck,
    Finding,
    ReasonerResult,
    ReasonerSpec,
    ReasoningRequest,
    ResultStatus,
)

from .protocols import MissingContextError
from .reasoners.common import active_spec, clamp_bp, missing_fields

UNIT_FRAMEWORK_VERSION = "1.0.0"


class UnitCategory(str, Enum):
    """The four families of the frozen architecture.

    Category is declared, not inferred, so the roster can be audited: it is how you answer "do we
    actually have anything that optimises?" without reading seventeen files.
    """

    SITUATION_UNDERSTANDING = "situation_understanding"
    BUSINESS_EVALUATION = "business_evaluation"
    OPTIMIZATION = "optimization"
    DECISION_SUPPORT = "decision_support"


@dataclass(frozen=True, slots=True)
class Observation:
    """One plugin's partial contribution — never a conclusion.

    A plugin says "the last inbound message was 31 days ago, which reads as 6,200bp of decay".
    It does not say what to do about it.  Deciding is Part 3's job, and keeping observations
    conclusion-free is what stops a plugin from becoming a decision authority by accident.
    """

    plugin_id: str
    kind: str
    metrics: Mapping[str, int] = field(default_factory=dict)
    evidence_ids: tuple[str, ...] = ()
    reason_codes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for name, value in self.metrics.items():
            if isinstance(value, bool) or not isinstance(value, int):
                raise ValueError(f"observation metric {name} must be an integer")
        object.__setattr__(self, "metrics", MappingProxyType(dict(self.metrics)))
        object.__setattr__(self, "evidence_ids", tuple(sorted(set(self.evidence_ids))))
        object.__setattr__(self, "reason_codes", tuple(sorted(set(self.reason_codes))))


@runtime_checkable
class AnalyzerPlugin(Protocol):
    """A single deterministic contribution to one unit's analysis."""

    @property
    def plugin_id(self) -> str:
        ...

    def contribute(self, view: UnitView) -> tuple[Observation, ...]:
        ...


@dataclass(frozen=True, slots=True)
class UnitView:
    """What the Retriever selected: the unit's own bounded window on the frozen situation.

    Units read this rather than the whole request, so a unit's inputs are visible in one place and
    a reviewer can see exactly what it was allowed to look at.
    """

    request: ReasoningRequest
    spec: ReasonerSpec
    prior: Mapping[str, ReasonerResult]
    facts: Mapping[str, Any] = field(default_factory=dict)
    evidence_ids: tuple[str, ...] = ()

    @property
    def config(self) -> Mapping[str, Any]:
        """Per-capability tuning for this unit, authored in Layer 3 and versioned with it."""
        return self.spec.config

    def prior_metric(self, reasoner_id: str, name: str, default: int = 0) -> int:
        """Read a metric a declared dependency published, or the default if it did not run."""
        result = self.prior.get(reasoner_id)
        if result is None or result.status != ResultStatus.COMPLETED:
            return default
        value = result.metrics.get(name, default)
        return default if isinstance(value, bool) or not isinstance(value, int) else value


@dataclass(frozen=True, slots=True)
class Verdict:
    """The Evaluator's reading: what the numbers mean, in this unit's own terms."""

    matched: bool | None = None
    metrics: Mapping[str, int] = field(default_factory=dict)
    reason_codes: tuple[str, ...] = ()
    findings: tuple[Finding, ...] = ()
    adjustments: tuple[CandidateAdjustment, ...] = ()
    checks: tuple[CandidateCheck, ...] = ()


class ReasoningUnit(ABC):
    """Base class for every Layer 4 reasoning unit.

    Subclasses declare their identity and implement the analytical stages.  They must not read a
    database, network, clock, random source, environment variable, or language model — the
    orchestrator's determinism guarantee is only as strong as the purest unit in the plan.
    """

    unit_id: str = ""
    version: str = "1.0.0"
    category: UnitCategory = UnitCategory.SITUATION_UNDERSTANDING
    publishes: tuple[str, ...] = ()
    plugins: tuple[AnalyzerPlugin, ...] = ()

    def __init__(self) -> None:
        if not self.unit_id:
            raise ValueError(f"{type(self).__name__} must declare a unit_id")
        self._descriptor = ReasonerSpec(reasoner_id=self.unit_id, version=self.version)
        seen = [plugin.plugin_id for plugin in self.plugins]
        if len(seen) != len(set(seen)):
            raise ValueError(f"{self.unit_id} registers a duplicate analyzer plugin")

    # -- identity ------------------------------------------------------------------------------

    @property
    def spec(self) -> ReasonerSpec:
        return self._descriptor

    # -- stages a unit implements -------------------------------------------------------------

    def validate(self, view: UnitView) -> None:
        """Refuse inputs that cannot support a conclusion.

        The default enforces the unit's declared `required_fields`.  Raising `MissingContextError`
        is how a unit says "I will not guess" — the orchestrator turns it into a typed
        insufficient-context result instead of letting a fabricated answer through.
        """
        absent = missing_fields(view.request, view.spec.required_fields)
        if absent:
            raise MissingContextError(*absent)

    def retrieve(self, request: ReasoningRequest, spec: ReasonerSpec,
                 prior: Mapping[str, ReasonerResult]) -> UnitView:
        """Select this unit's window on the frozen snapshot. Selection only — never IO."""
        wanted = tuple(field for field in spec.required_fields
                       if not field.startswith("neighbor:"))
        facts = {name: request.context.facts[name]
                 for name in wanted if name in request.context.facts}
        evidence = tuple(sorted(item.evidence_id for item in request.context.evidence
                                if item.field in facts))
        return UnitView(request=request, spec=spec, prior=prior,
                        facts=MappingProxyType(facts), evidence_ids=evidence)

    def analyze(self, view: UnitView) -> tuple[Observation, ...]:
        """Run every plugin and collect partial evidence.

        Sorted by plugin id so the observation order — and therefore every hash downstream of it —
        is a property of the unit's composition, not of registration order.
        """
        observations: list[Observation] = []
        for plugin in sorted(self.plugins, key=lambda item: item.plugin_id):
            observations.extend(plugin.contribute(view))
        return tuple(observations)

    @abstractmethod
    def calculate(self, view: UnitView,
                  observations: Sequence[Observation]) -> Mapping[str, int]:
        """Combine observations into this unit's metrics. Pure integer arithmetic only."""

    @abstractmethod
    def evaluate_meaning(self, view: UnitView, metrics: Mapping[str, int],
                         observations: Sequence[Observation]) -> Verdict:
        """Turn numbers into meaning — a threshold crossed, a candidate blocked, a gate matched."""

    def build(self, view: UnitView, verdict: Verdict,
              observations: Sequence[Observation]) -> ReasonerResult:
        """Assemble the one object shape every unit returns."""
        evidence = set(view.evidence_ids)
        for observation in observations:
            evidence.update(observation.evidence_ids)
        return ReasonerResult(
            reasoner_id=self.unit_id,
            reasoner_version=self.version,
            status=ResultStatus.COMPLETED,
            matched=verdict.matched,
            metrics={name: clamp_bp(value) if name.endswith("_bp") else value
                     for name, value in verdict.metrics.items()},
            findings=verdict.findings,
            adjustments=verdict.adjustments,
            checks=verdict.checks,
            evidence_ids=tuple(sorted(evidence)),
            reason_codes=verdict.reason_codes,
        )

    # -- the template method: fixed for every unit --------------------------------------------

    def evaluate(self, request: ReasoningRequest,
                 prior_results: Mapping[str, ReasonerResult]) -> ReasonerResult:
        """Run the stages in order. Deliberately not overridable in spirit: the sequence *is* the
        framework, and a unit that could reorder or skip a stage would not be one of seventeen
        interchangeable parts any more."""
        spec = active_spec(request, self.unit_id)
        view = self.retrieve(request, spec, prior_results)
        self.validate(view)
        observations = self.analyze(view)
        metrics = self.calculate(view, observations)
        verdict = self.evaluate_meaning(view, metrics, observations)
        undeclared = sorted(set(verdict.metrics) - set(self.publishes)) if self.publishes else []
        if undeclared:
            # A unit publishing an undeclared metric is how a shared value like confidence_bp gets
            # moved by something nobody knew was moving it.
            raise ValueError(
                f"{self.unit_id} published undeclared metrics: {', '.join(undeclared)}")
        return self.build(view, verdict, observations)


__all__ = ["UNIT_FRAMEWORK_VERSION", "AnalyzerPlugin", "Observation", "ReasoningUnit",
           "UnitCategory", "UnitView", "Verdict"]
