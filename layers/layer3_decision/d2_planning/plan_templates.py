"""
D2.1 — Plan Templates

Template-based plan definitions per intent type.
Each template defines the standard steps, tool calls, and fallbacks.

This is NOT free-form LLM reasoning — it's structured slot-filling.
"""

from core.contracts.decision_packet import ActionStep, ToolCallDraft


# Plan template: dict with steps, tool_calls, fallbacks
PLAN_TEMPLATES: dict[str, dict] = {
    "follow_up": {
        "steps": [
            ActionStep(description="Draft follow-up email using template", tool="email_drafter", order=1),
            ActionStep(description="Show draft preview to user", tool="", order=2, depends_on=0),
            ActionStep(description="Request approval from approver", tool="approval_gate", order=3, depends_on=1),
            ActionStep(description="Send email at recommended window", tool="gmail", order=4, depends_on=2),
        ],
        "tool_calls": [
            ToolCallDraft(
                tool_name="gmail",
                method="send_draft",
                payload={"template": "follow_up", "schedule": True},
                fallback="Save as draft and notify user",
            ),
        ],
        "fallbacks": [
            "If Gmail unavailable → save draft locally",
            "If approval timeout → remind approver after 4h",
        ],
    },
    "reply_email": {
        "steps": [
            ActionStep(description="Fetch latest thread context", tool="gmail", order=1),
            ActionStep(description="Draft reply using preferences", tool="email_drafter", order=2, depends_on=0),
            ActionStep(description="Show draft for review", tool="", order=3, depends_on=1),
            ActionStep(description="Send reply", tool="gmail", order=4, depends_on=2),
        ],
        "tool_calls": [
            ToolCallDraft(
                tool_name="gmail",
                method="reply",
                payload={"in_reply_to": True},
                fallback="Save reply as unsent draft",
            ),
        ],
        "fallbacks": [
            "If thread not found → create new email instead",
        ],
    },
    "cold_outreach": {
        "steps": [
            ActionStep(description="Select outreach template", tool="", order=1),
            ActionStep(description="Personalize with entity data", tool="email_drafter", order=2, depends_on=0),
            ActionStep(description="Run compliance pre-check", tool="", order=3, depends_on=1),
            ActionStep(description="Request approval", tool="approval_gate", order=4, depends_on=2),
            ActionStep(description="Send outreach email", tool="gmail", order=5, depends_on=3),
        ],
        "tool_calls": [
            ToolCallDraft(
                tool_name="gmail",
                method="send_new",
                payload={"template": "cold_outreach"},
                fallback="Queue for manual send",
            ),
        ],
        "fallbacks": [
            "If compliance fails → escalate to founder",
            "If rate-limited → queue and retry",
        ],
    },
    "schedule_meeting": {
        "steps": [
            ActionStep(description="Check calendar availability", tool="calendar", order=1),
            ActionStep(description="Propose meeting time slots", tool="", order=2, depends_on=0),
            ActionStep(description="Send calendar invite", tool="calendar", order=3, depends_on=1),
        ],
        "tool_calls": [
            ToolCallDraft(
                tool_name="calendar",
                method="create_event",
                payload={"type": "meeting"},
                fallback="Suggest manual scheduling",
            ),
        ],
        "fallbacks": [
            "If no availability → suggest next week",
        ],
    },
    "send_email": {
        "steps": [
            ActionStep(description="Draft email", tool="email_drafter", order=1),
            ActionStep(description="Review draft", tool="", order=2, depends_on=0),
            ActionStep(description="Send email", tool="gmail", order=3, depends_on=1),
        ],
        "tool_calls": [
            ToolCallDraft(
                tool_name="gmail",
                method="send_new",
                payload={},
                fallback="Save as draft",
            ),
        ],
        "fallbacks": [
            "If send fails → save and notify",
        ],
    },
    "general": {
        "steps": [
            ActionStep(description="Process request and provide response", tool="", order=1),
        ],
        "tool_calls": [],
        "fallbacks": [],
    },
}


def get_template(intent_type: str) -> dict:
    """Get the plan template for the given intent type."""
    return PLAN_TEMPLATES.get(intent_type, PLAN_TEMPLATES["general"])
