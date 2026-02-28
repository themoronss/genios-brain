"""
D0 — Decision Router

Route to the correct decision template based on:
  - intent_type (from Layer 1 / Layer 2)
  - judgement constraints
  - available tools
"""

from core.contracts.context_bundle import ContextBundle
from core.contracts.judgement_report import JudgementReport


# Supported intent types and their plan template keys
_SUPPORTED_INTENTS = {
    "follow_up",
    "reply_email",
    "send_email",
    "cold_outreach",
    "schedule_meeting",
    "general",
}


def resolve_route(
    bundle: ContextBundle,
    judgement: JudgementReport,
) -> dict:
    """
    Determine the decision route.

    Args:
        bundle: ContextBundle from Layer 1.
        judgement: JudgementReport from Layer 2.

    Returns:
        Route dict with intent_type, template_key, and overrides.
    """
    # Get intent from query_plan_ref (populated by Layer 1 R0)
    intent_type = bundle.query_plan_ref.get("intent_type", "general")

    # Validate it's a supported intent
    if intent_type not in _SUPPORTED_INTENTS:
        intent_type = "general"

    # Check if judgement blocks normal routing
    overrides = {}
    if judgement.need_more_info.value:
        overrides["force_mode"] = "ask_clarifying"
    if judgement.policy.status == "deny":
        overrides["force_mode"] = "propose_only"

    return {
        "intent_type": intent_type,
        "template_key": intent_type,
        "overrides": overrides,
    }
