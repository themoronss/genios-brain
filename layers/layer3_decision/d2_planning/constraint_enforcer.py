"""
D2.5 — Constraint Enforcer

Apply J5 constraints from JudgementReport to the action plan.
Modifies steps, adds mandatory constraints, filters out disallowed actions.
"""

from core.contracts.decision_packet import ActionPlan, ActionStep
from core.contracts.judgement_report import JudgementReport


def enforce_constraints(
    plan: ActionPlan,
    judgement: JudgementReport,
) -> tuple[ActionPlan, int]:
    """
    Apply judgement constraints to the plan.

    Constraints from J5 are MUST/SHOULD/MUST-NOT rules.
    This function modifies the plan in-place and returns the count
    of constraints applied.

    Args:
        plan: The ActionPlan from step_builder.
        judgement: JudgementReport from Layer 2.

    Returns:
        Tuple of (modified plan, count of constraints applied).
    """
    constraints = judgement.multi_factor.constraints
    applied = 0

    for constraint in constraints:
        constraint_lower = constraint.lower()

        # MUST NOT: block execution → inject approval gate
        if constraint_lower.startswith("must not:"):
            plan.fallbacks.insert(0, f"BLOCKED: {constraint}")
            applied += 1

        # MUST: do not send without approval → ensure approval step exists
        elif "approval" in constraint_lower and "must:" in constraint_lower:
            has_approval = any("approval" in s.description.lower() for s in plan.steps)
            if not has_approval:
                plan.steps.insert(-1, ActionStep(
                    description="Request approval before execution",
                    tool="approval_gate",
                    order=len(plan.steps),
                ))
            applied += 1

        # SHOULD: use template → update tool call payloads
        elif "template" in constraint_lower and "should:" in constraint_lower:
            for tc in plan.tool_calls:
                tc.payload["constraint_template"] = constraint.split(":")[-1].strip()
            applied += 1

        # SHOULD: use tone → add as metadata
        elif "tone" in constraint_lower and "should:" in constraint_lower:
            for tc in plan.tool_calls:
                tc.payload["tone"] = constraint.split(":")[-1].strip().split(" ")[-2]
            applied += 1

        else:
            # Generic constraint → add to fallbacks as reminder
            plan.fallbacks.append(f"Constraint: {constraint}")
            applied += 1

    return plan, applied
