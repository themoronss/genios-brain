from __future__ import annotations

from genios_engine.reason.registry import ReasonerRegistry

from .confidence import ConfidenceReasoner
from .constraint import ConstraintReasoner
from .legacy_rule import LegacyRuleReasoner
from .legacy_gate import LegacyScoreGateReasoner
from .planning import PlanningReasoner
from .priority import PriorityReasoner
from .relationship import RelationshipReasoner
from .risk import RiskReasoner
from .signal_composition import SignalCompositionReasoner
from .temporal import TemporalReasoner


def default_registry() -> ReasonerRegistry:
    return ReasonerRegistry((
        LegacyRuleReasoner(), LegacyScoreGateReasoner(), TemporalReasoner(),
        RelationshipReasoner(), RiskReasoner(),
        SignalCompositionReasoner(), ConstraintReasoner(), PriorityReasoner(),
        ConfidenceReasoner(), PlanningReasoner(),
    ))


__all__ = ["default_registry", "LegacyRuleReasoner", "LegacyScoreGateReasoner", "TemporalReasoner",
           "RelationshipReasoner", "RiskReasoner", "ConstraintReasoner", "PriorityReasoner",
           "ConfidenceReasoner", "PlanningReasoner", "SignalCompositionReasoner"]
