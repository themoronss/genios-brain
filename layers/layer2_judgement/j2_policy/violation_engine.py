"""
J2.2 — Violation Engine

Evaluate policy rules against the ContextBundle.
Detect violations, determine allow/deny/needs_approval.
"""

from core.contracts.context_bundle import ContextBundle
from core.contracts.judgement_report import PolicyVerdict


def evaluate_policies(bundle: ContextBundle) -> PolicyVerdict:
    """
    Evaluate all matched policies and produce a verdict.

    Logic:
    - If any rule has effect.requires_approval → needs_approval
    - If any rule has effect.deny → deny
    - Otherwise → allow
    - Collect all violations and constraints

    Args:
        bundle: ContextBundle with policy.rules populated by Layer 1.

    Returns:
        PolicyVerdict with status, violations, approvals, constraints.
    """
    rules = bundle.policy.rules
    reasons = []
    violations = []
    approvals_required = []
    constraints = []

    has_deny = False
    has_approval = False

    for rule in rules:
        effect = rule.get("effect", {})
        policy_id = rule.get("id", "unknown")
        policy_type = rule.get("policy_type", "unknown")

        # Check for hard deny
        if effect.get("deny"):
            has_deny = True
            violations.append(f"Policy {policy_id} ({policy_type}): hard deny")
            reasons.append(f"Blocked by policy {policy_id}")

        # Check for approval requirement
        if effect.get("requires_approval"):
            has_approval = True
            approvals_required.append(f"Approval required by policy {policy_id}")
            reasons.append(f"Policy {policy_id} requires approval")

        # Check for risk flags
        if effect.get("risk_flag"):
            violations.append(f"Risk flag: {effect['risk_flag']} (policy {policy_id})")
            reasons.append(f"Risk: {effect['risk_flag']}")

        # Collect constraints
        if effect.get("delay_until"):
            constraints.append(f"Delay until {effect['delay_until']}")
        if effect.get("template"):
            constraints.append(f"Must use template: {effect['template']}")

    # Determine status
    if has_deny:
        status = "deny"
    elif has_approval:
        status = "needs_approval"
    else:
        status = "allow"

    return PolicyVerdict(
        status=status,
        reasons=reasons,
        violations=violations,
        approvals_required=approvals_required,
        constraints=constraints,
    )
