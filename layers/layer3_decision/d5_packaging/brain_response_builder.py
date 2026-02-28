"""
D5.1 — Brain Response Builder

Build user-facing message + UI blocks for the orchestrator.
"""

from core.contracts.decision_packet import (
    BrainResponse,
    UIBlock,
    ActionPlan,
    ExecutionMode,
)


# Execution mode → user message template
_MODE_MESSAGES = {
    "auto_execute": "I'll handle this right away.",
    "needs_approval": "I've prepared this for you. Please review and approve.",
    "propose_only": "Here's what I'd suggest. Let me know if you'd like to proceed.",
    "ask_clarifying": "I need a bit more information before I can act.",
}


def build_brain_response(
    intent_type: str,
    slots: dict[str, str],
    execution: ExecutionMode,
    plan: ActionPlan,
    trace_why: list[str],
) -> BrainResponse:
    """
    Build the user-facing response with message and UI blocks.

    Args:
        intent_type: Final intent type.
        slots: Extracted slots.
        execution: ExecutionMode from D3.
        plan: ActionPlan from D2.
        trace_why: Key reasons from D4.

    Returns:
        BrainResponse ready for the orchestrator.
    """
    # Build user message
    base = _MODE_MESSAGES.get(execution.mode, "Here's what I found.")
    who = slots.get("who", "")
    what = slots.get("what", "")
    user_message = f"{base}\n\n**Action**: {what}"
    if who:
        user_message += f" → {who}"

    # Build UI blocks
    ui_blocks = []

    # Draft block (show what we'll do)
    steps_text = "\n".join(f"  {i+1}. {s.description}" for i, s in enumerate(plan.steps))
    ui_blocks.append(UIBlock(
        block_type="draft",
        title="Action Plan",
        content=steps_text,
    ))

    # Reason block (show why)
    if trace_why:
        reasons_text = "\n".join(f"  • {r}" for r in trace_why[:5])
        ui_blocks.append(UIBlock(
            block_type="reason",
            title="Why This Decision",
            content=reasons_text,
        ))

    # Action button (based on mode)
    if execution.mode == "needs_approval":
        ui_blocks.append(UIBlock(
            block_type="action_button",
            title="Approve",
            content="Approve this action to proceed",
        ))
    elif execution.mode == "ask_clarifying":
        questions = "\n".join(f"  • {q}" for q in execution.questions)
        ui_blocks.append(UIBlock(
            block_type="info",
            title="Questions",
            content=questions,
        ))

    return BrainResponse(
        user_message=user_message,
        ui_blocks=ui_blocks,
        tool_instructions=list(plan.tool_calls),
        save_instructions=[],
    )
