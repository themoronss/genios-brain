"""Layer 4 · Part 2 — the reasoning unit roster.

Seventeen units in four categories, plus the legacy strangler pair and the app-specific units that
predate the framework.  Registration is explicit and central: there is no auto-discovery, because a
unit appearing in the runtime because a file happened to be importable is how a decision gets made
by something nobody reviewed.

A capability names the units it wants; the orchestrator resolves every one of them before any of
them run.  So a unit that exists here but is named by no capability costs nothing, and a unit named
by a capability but absent here is a failed deployment rather than a quiet degradation.
"""

from __future__ import annotations

from genios_engine.reason.registry import ReasonerRegistry

from .alternative_unit import AlternativeUnit
from .confidence import ConfidenceReasoner
from .constraint import ConstraintReasoner
from .context_unit import ContextUnit
from .cost_unit import CostUnit
from .dependency_unit import DependencyUnit
from .impact_unit import ImpactUnit
from .legacy_gate import LegacyScoreGateReasoner
from .legacy_rule import LegacyRuleReasoner
from .opportunity import OpportunityUnit
from .planning import PlanningReasoner
from .policy_unit import PolicyUnit
from .priority import PriorityReasoner
from .recommendation_unit import RecommendationUnit
from .relationship import RelationshipReasoner
from .resource_unit import ResourceUnit
from .risk import RiskReasoner
from .scheduling_unit import SchedulingUnit
from .signal_composition import SignalCompositionReasoner
from .temporal import TemporalReasoner
from .timeline_unit import TimelineUnit
from .tradeoff_unit import TradeoffUnit
from .validation_unit import ValidationUnit

#: Category 1 — Situation Understanding: what is true, in what order, and what blocks what.
SITUATION_UNDERSTANDING = (ContextUnit, TimelineUnit, DependencyUnit, ConstraintReasoner)

#: Category 2 — Business Evaluation: what this situation is worth and what it threatens.
BUSINESS_EVALUATION = (RiskReasoner, OpportunityUnit, ImpactUnit, PriorityReasoner,
                       ConfidenceReasoner)

#: Category 3 — Optimization: among the possible paths, which is best and when.
OPTIMIZATION = (TradeoffUnit, ResourceUnit, SchedulingUnit, CostUnit, PolicyUnit)

#: Category 4 — Decision Support: prepare the field the Decision Maker will judge.
DECISION_SUPPORT = (AlternativeUnit, ValidationUnit, RecommendationUnit)

#: The seventeen units of the frozen architecture.
CORE_UNITS = SITUATION_UNDERSTANDING + BUSINESS_EVALUATION + OPTIMIZATION + DECISION_SUPPORT

#: Units outside the roster: the legacy strangler pair, plus analyses this product needs that the
#: generic taxonomy does not name.  Kept separate so the roster above stays auditable.
SUPPLEMENTARY_UNITS = (LegacyRuleReasoner, LegacyScoreGateReasoner, TemporalReasoner,
                       RelationshipReasoner, SignalCompositionReasoner, PlanningReasoner)


def default_registry() -> ReasonerRegistry:
    """Every unit the runtime can schedule."""
    return ReasonerRegistry(tuple(unit() for unit in CORE_UNITS + SUPPLEMENTARY_UNITS))


__all__ = [
    "BUSINESS_EVALUATION", "CORE_UNITS", "DECISION_SUPPORT", "OPTIMIZATION",
    "SITUATION_UNDERSTANDING", "SUPPLEMENTARY_UNITS", "default_registry",
    "AlternativeUnit", "ConfidenceReasoner", "ConstraintReasoner", "ContextUnit", "CostUnit",
    "DependencyUnit", "ImpactUnit", "LegacyRuleReasoner", "LegacyScoreGateReasoner",
    "OpportunityUnit", "PlanningReasoner", "PolicyUnit", "PriorityReasoner",
    "RecommendationUnit", "RelationshipReasoner", "ResourceUnit", "RiskReasoner",
    "SchedulingUnit", "SignalCompositionReasoner", "TemporalReasoner", "TimelineUnit",
    "TradeoffUnit", "ValidationUnit",
]
