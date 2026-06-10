"""g-i-2 neural layer — LLM gateway + external confidence + symbolic-wins fusion.

Public API:
    from core.neural import (
        LLMClient, LLMCall, LLMResponse,           # core LLM wrapper
        CostGuard, BudgetExceededError,            # per-org budget circuit breaker
        Gateway, GatewayDecision, RoutingChoice,   # symbolic-first routing
        ConfidenceScorer, ConfidenceBreakdown,     # external confidence
        fuse, FusionResult, FusionConflict,        # symbolic-wins policy
    )
"""

from core.neural.client import LLMCall, LLMClient, LLMResponse
from core.neural.confidence import ConfidenceBreakdown, ConfidenceScorer
from core.neural.cost_guard import BudgetExceededError, CostGuard
from core.neural.fusion import FusionConflict, FusionResult, fuse
from core.neural.gateway import Gateway, GatewayDecision, RoutingChoice

__all__ = [
    "BudgetExceededError",
    "ConfidenceBreakdown",
    "ConfidenceScorer",
    "CostGuard",
    "FusionConflict",
    "FusionResult",
    "Gateway",
    "GatewayDecision",
    "LLMCall",
    "LLMClient",
    "LLMResponse",
    "RoutingChoice",
    "fuse",
]
