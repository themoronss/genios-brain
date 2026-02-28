"""
L2.1 — Candidate Memory Generator

Extract potential memory updates from the outcome + decision.
Does NOT write anything — just proposes candidates.
"""

from core.contracts.decision_packet import DecisionPacket
from core.contracts.learning_report import MemoryUpdate, OutcomeRecord


def generate_candidates(
    decision: DecisionPacket,
    outcome: OutcomeRecord,
) -> list[MemoryUpdate]:
    """
    Extract candidate memory updates from the decision + outcome.

    Types of candidates:
    - Last successful intent (always on success)
    - Entity interaction log (if recipient exists)
    - Template effectiveness (if template was used)
    - Failure case capture (always on failure)

    Args:
        decision: DecisionPacket from Layer 3.
        outcome: OutcomeRecord from L1.

    Returns:
        List of candidate MemoryUpdate (not yet approved).
    """
    candidates = []

    intent = decision.intent_type
    who = decision.intent_slots.get("who", "")
    template = decision.intent_slots.get("template", "")

    if outcome.execution_result in ("approved", "auto_executed"):
        # Successful intent pattern
        candidates.append(MemoryUpdate(
            field="last_successful_intent",
            new_value=intent,
            confidence=0.8,
            operation="upsert",
            evidence_refs=[f"outcome:{outcome.execution_result}"],
            reason=f"Intent '{intent}' completed successfully",
        ))

        # Entity interaction
        if who:
            candidates.append(MemoryUpdate(
                field=f"last_interaction_{who}",
                new_value={"intent": intent, "result": outcome.execution_result},
                confidence=0.7,
                operation="upsert",
                evidence_refs=[f"decision:{intent}", f"entity:{who}"],
                reason=f"Successful interaction with {who}",
            ))

        # Template effectiveness
        if template:
            candidates.append(MemoryUpdate(
                field=f"template_success_{template}",
                new_value=True,
                confidence=0.6,
                operation="append",
                evidence_refs=[f"template:{template}"],
                reason=f"Template '{template}' used successfully",
            ))

    elif outcome.execution_result in ("rejected", "failed"):
        # Failure case — always capture
        candidates.append(MemoryUpdate(
            field=f"failure_case_{intent}",
            new_value={
                "intent": intent,
                "errors": [str(e) for e in outcome.tool_errors],
                "feedback": outcome.user_feedback,
                "comment": outcome.user_comment,
            },
            confidence=1.0,
            operation="append",
            evidence_refs=[f"outcome:{outcome.execution_result}"],
            reason=f"Capturing failure for intent '{intent}'",
            review_required=False,  # failures are always safe to log
        ))

    # User edit → preference learning candidate
    if outcome.user_feedback == "edit":
        candidates.append(MemoryUpdate(
            field="preference_edits",
            new_value={"intent": intent, "comment": outcome.user_comment},
            confidence=0.5,
            operation="append",
            evidence_refs=[f"feedback:edit"],
            reason="User edited the output — potential preference signal",
            review_required=True,  # edits need review before becoming preferences
        ))

    return candidates
