"""
D2.2 — Step Builder

Build the action plan from a template + slots + judgement constraints.
"""

from core.contracts.decision_packet import ActionPlan, ActionStep, ToolCallDraft
from layers.layer3_decision.d2_planning.plan_templates import get_template


def build_plan(
    intent_type: str,
    slots: dict[str, str],
) -> ActionPlan:
    """
    Build an ActionPlan from the template + slots.

    Args:
        intent_type: Canonical intent type.
        slots: Extracted slots (who, what, when, channel, template).

    Returns:
        ActionPlan with steps and tool call drafts.
    """
    template = get_template(intent_type)

    # Deep-copy steps from template
    steps = [step.model_copy() for step in template["steps"]]

    # Enrich tool call payloads with slot data
    tool_calls = []
    for tc in template["tool_calls"]:
        enriched = tc.model_copy()
        enriched.payload = {**enriched.payload}
        if slots.get("who"):
            enriched.payload["recipient"] = slots["who"]
        if slots.get("template"):
            enriched.payload["template"] = slots["template"]
        if slots.get("when"):
            enriched.payload["schedule_time"] = slots["when"]
        tool_calls.append(enriched)

    fallbacks = list(template["fallbacks"])

    return ActionPlan(
        steps=steps,
        tool_calls=tool_calls,
        fallbacks=fallbacks,
    )
