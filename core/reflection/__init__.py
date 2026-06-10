"""g-i-2 reflection + 80/20 routing + structured correction capture.

Per MD g-i-2 §2.3.2:
- Reflection is SELECTIVE (only high-stakes / low-confidence) — never per-artifact
- Prefer FLAG-to-human over silent auto-fix (LLM self-correction has known limits)
- 80/20 routing: autonomous | notify+act (reversible only) | flag-to-human
- User persona redlines (g-i-9) force flag regardless

Public API:
    from core.reflection import (
        should_reflect, RoutingDecision, Route,
        route_decision, capture_correction,
    )
"""

from core.reflection.human_flag import (
    Route,
    RoutingDecision,
    capture_correction,
    route_decision,
)
from core.reflection.trigger import ReflectionTrigger, should_reflect

__all__ = [
    "ReflectionTrigger",
    "Route",
    "RoutingDecision",
    "capture_correction",
    "route_decision",
    "should_reflect",
]
