"""
D5.3 — Save Instruction Compiler

Define what to store after decision:
  - Decision log entry
  - Outcome placeholder
  - Memory updates
"""

from core.contracts.decision_packet import SaveInstruction


def compile_save_instructions(
    intent_type: str,
    execution_mode: str,
    slots: dict[str, str],
) -> list[SaveInstruction]:
    """
    Determine what should be persisted after this decision.

    Args:
        intent_type: Final intent type.
        execution_mode: How the plan will be executed.
        slots: Extracted slots.

    Returns:
        List of save instructions for the orchestrator.
    """
    instructions = []

    # Always log the decision
    instructions.append(SaveInstruction(
        store="decision_log",
        key=f"decision_{intent_type}",
        value={
            "intent_type": intent_type,
            "execution_mode": execution_mode,
            "slots": slots,
        },
    ))

    # Placeholder for outcome tracking
    instructions.append(SaveInstruction(
        store="outcome",
        key=f"outcome_{intent_type}",
        value={"status": "pending"},
    ))

    # If there's a recipient, log the interaction
    who = slots.get("who")
    if who:
        instructions.append(SaveInstruction(
            store="memory",
            key=f"last_interaction_{who}",
            value={
                "action": intent_type,
                "mode": execution_mode,
            },
        ))

    return instructions
