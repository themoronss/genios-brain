"""
D2.2 — Step Builder

Build the action plan from a template + slots + judgement constraints.
"""

from typing import Optional

from core.contracts.context_bundle import ContextBundle
from core.contracts.decision_packet import ActionPlan, ActionStep, ToolCallDraft
from layers.layer3_decision.d2_planning.plan_templates import get_template
from layers.layer3_decision.d2_planning.tool_call_drafter import draft_tool_calls


def build_plan(
    intent_type: str,
    slots: dict[str, str],
    context_bundle: Optional[ContextBundle] = None,
) -> ActionPlan:
    """
    Build an ActionPlan from the template + slots.

    For email intents (follow_up, reply_email, cold_outreach):
        - Calls Gemini to generate email content
        - Embeds generated content in tool payloads

    Args:
        intent_type: Canonical intent type.
        slots: Extracted slots (who, what, when, channel, template, context, tone).
        context_bundle: Optional ContextBundle for rich context.

    Returns:
        ActionPlan with steps and tool call drafts (including AI-generated content).
    """
    template = get_template(intent_type)

    # Deep-copy steps from template
    steps = [step.model_copy() for step in template["steps"]]

    # Enrich tool calls with slots + optional LLM-generated content
    tool_calls = draft_tool_calls(
        intent_type=intent_type,
        tool_calls_templates=template["tool_calls"],
        slots=slots,
        context_bundle=context_bundle,
    )

    fallbacks = list(template["fallbacks"])

    return ActionPlan(
        steps=steps,
        tool_calls=tool_calls,
        fallbacks=fallbacks,
    )
