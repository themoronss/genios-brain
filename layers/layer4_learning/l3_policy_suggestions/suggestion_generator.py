"""
L3 — Policy Suggestion Generator

Detect patterns that suggest governance improvements:
  - Repeated approvals → propose auto-execute policy
  - Frequent violations → add guardrails
  - Threshold tuning opportunities

IMPORTANT: In MVP, these are SUGGESTIONS ONLY. No auto policy changes.
"""

from core.contracts.decision_packet import DecisionPacket
from core.contracts.learning_report import OutcomeRecord, PolicySuggestion


def generate_suggestions(
    decision: DecisionPacket,
    outcome: OutcomeRecord,
) -> list[PolicySuggestion]:
    """
    Generate policy suggestions from the current decision + outcome.

    In MVP, this analyzes a single run. Future versions will use
    historical data for pattern mining.

    Args:
        decision: DecisionPacket from Layer 3.
        outcome: OutcomeRecord from L1.

    Returns:
        List of PolicySuggestions (human-reviewable only).
    """
    suggestions = []
    intent = decision.intent_type

    # 1. Repeated approval detection
    # If action was approved and mode was needs_approval → suggest auto-exec
    if (
        outcome.execution_result == "approved"
        and decision.execution_mode == "needs_approval"
    ):
        suggestions.append(PolicySuggestion(
            suggestion_type="threshold_change",
            description=(
                f"Intent '{intent}' was manually approved. "
                "If this pattern repeats, consider lowering the approval threshold "
                "for this intent type to enable auto-execution."
            ),
            evidence=[
                f"intent_type: {intent}",
                f"execution_mode: needs_approval",
                f"user_feedback: {outcome.user_feedback}",
            ],
            priority="low",
            proposed_change={
                "target": "approval_threshold",
                "intent_type": intent,
                "direction": "lower",
            },
        ))

    # 2. Rejection → suggest guardrail
    if outcome.user_feedback == "reject":
        suggestions.append(PolicySuggestion(
            suggestion_type="guardrail",
            description=(
                f"User rejected '{intent}' action. "
                "Consider adding a guardrail policy to prevent similar proposals."
            ),
            evidence=[
                f"intent_type: {intent}",
                f"user_comment: {outcome.user_comment}",
                f"execution_mode: {decision.execution_mode}",
            ],
            priority="medium",
            proposed_change={
                "target": "new_guardrail",
                "intent_type": intent,
                "trigger": "rejection",
            },
        ))

    # 3. Tool errors → suggest fallback policy
    if outcome.tool_errors:
        suggestions.append(PolicySuggestion(
            suggestion_type="new_policy",
            description=(
                f"Tool errors occurred during '{intent}'. "
                "Consider adding a retry/fallback policy for the affected tools."
            ),
            evidence=[
                f"errors: {len(outcome.tool_errors)}",
                f"retries: {outcome.retries}",
            ],
            priority="medium" if len(outcome.tool_errors) > 1 else "low",
            proposed_change={
                "target": "fallback_policy",
                "intent_type": intent,
                "error_count": len(outcome.tool_errors),
            },
        ))

    return suggestions
