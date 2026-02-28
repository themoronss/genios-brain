"""
L2.3 — Write Policy Gate

Determines which memory updates can auto-write vs need review.

Hard rules (to prevent memory poisoning):
Auto-write only if ALL are true:
  - user approved OR repeatedly used pattern
  - risk class not high OR explicitly whitelisted
  - update confidence above threshold
  - not contradicting existing memory

Otherwise: queue for review.
"""

from core.contracts.learning_report import MemoryUpdate


# Confidence threshold for auto-write
AUTO_WRITE_CONFIDENCE = 0.7

# Fields that are always safe to auto-write
SAFE_FIELDS = {
    "last_successful_intent",
    "failure_case_",
}

# Fields that always need review
REVIEW_FIELDS = {
    "preference_",
    "template_success_",
}


def gate_updates(
    candidates: list[MemoryUpdate],
    execution_result: str,
    risk_level: str = "low",
) -> list[MemoryUpdate]:
    """
    Apply write policy gate to candidate updates.

    Marks each update as auto_approved or review_required.

    Args:
        candidates: Candidate MemoryUpdates from L2.1.
        execution_result: The execution outcome.
        risk_level: Risk level from Layer 2.

    Returns:
        Gated list with auto_approved / review_required flags set.
    """
    gated = []

    for update in candidates:
        update = update.model_copy()

        # Already marked for review
        if update.review_required:
            gated.append(update)
            continue

        # Check if field is in safe list
        is_safe = any(update.field.startswith(sf) for sf in SAFE_FIELDS)

        # Check if field needs review
        needs_review = any(update.field.startswith(rf) for rf in REVIEW_FIELDS)

        # Apply gate rules
        if needs_review:
            update.review_required = True
            update.auto_approved = False
        elif (
            is_safe
            and update.confidence >= AUTO_WRITE_CONFIDENCE
            and execution_result in ("approved", "auto_executed")
            and risk_level != "high"
        ):
            update.auto_approved = True
            update.review_required = False
        elif update.confidence >= AUTO_WRITE_CONFIDENCE and risk_level == "low":
            update.auto_approved = True
            update.review_required = False
        else:
            update.review_required = True
            update.auto_approved = False

        gated.append(update)

    return gated
