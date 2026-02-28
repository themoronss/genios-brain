"""
J2.3 — Approval Resolver

Map policy approval requirements to approver roles.
Extract constraints from policy effects.
"""


# Default approver mapping (policy_type → approver role)
_APPROVER_MAP = {
    "org": "founder",
    "risk": "founder",
    "compliance": "legal",
    "finance": "cfo",
}


def resolve_approvers(approvals_required: list[str], rules: list[dict]) -> list[str]:
    """
    Map approval requirements to specific approver roles.

    Args:
        approvals_required: List of approval requirement strings.
        rules: The matched policy rules.

    Returns:
        List of approver role strings (e.g. ["founder"]).
    """
    approvers = set()

    for rule in rules:
        effect = rule.get("effect", {})
        if effect.get("requires_approval"):
            policy_type = rule.get("policy_type", "org")
            approver = _APPROVER_MAP.get(policy_type, "founder")
            approvers.add(approver)

    return sorted(approvers) if approvers else ["founder"]
