"""g-i-2 guardrails — hard-constraint enforcement + source-grounding verification.

Public API:
    from core.guardrails import (
        check_hard_constraints, ConstraintViolation,   # block outputs violating hard rules
        verify_grounding, GroundingResult,             # claim -> source-fact check
    )
"""

from core.guardrails.constraints import ConstraintViolation, check_hard_constraints
from core.guardrails.grounding import GroundingResult, verify_grounding

__all__ = [
    "ConstraintViolation",
    "GroundingResult",
    "check_hard_constraints",
    "verify_grounding",
]
