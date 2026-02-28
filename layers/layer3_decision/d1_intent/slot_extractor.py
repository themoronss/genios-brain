"""
D1.2 — Slot Extractor

Extract key slots from the ContextBundle:
  who, what, when, channel, template
"""

from core.contracts.context_bundle import ContextBundle


def extract_slots(bundle: ContextBundle, intent_type: str) -> dict[str, str]:
    """
    Extract structured slots for the action plan.

    Args:
        bundle: ContextBundle from Layer 1.
        intent_type: Canonical intent type.

    Returns:
        Dict of slot_name → value.
    """
    slots = {}

    # Who — primary entity/recipient
    entities = list(bundle.memory.entity_data.keys())
    if entities:
        slots["who"] = entities[0]

    # What — the action
    slots["what"] = _intent_to_action(intent_type)

    # When — timing (from tool state if available)
    calendar = bundle.tools.snapshots.get("calendar", {})
    if calendar.get("next_available"):
        slots["when"] = str(calendar["next_available"])
    else:
        slots["when"] = "asap"

    # Channel — communication channel
    if intent_type in ("follow_up", "reply_email", "send_email", "cold_outreach"):
        slots["channel"] = "email"
    elif intent_type == "schedule_meeting":
        slots["channel"] = "calendar"
    else:
        slots["channel"] = "internal"

    # Template — preferred template
    tone = bundle.memory.preferences.get("tone", "professional")
    entity_tier = _get_entity_tier(bundle)
    if entity_tier == "VIP":
        slots["template"] = f"vip_{intent_type}_template"
    else:
        slots["template"] = f"{tone}_{intent_type}_template"

    return slots


def _intent_to_action(intent_type: str) -> str:
    """Map intent type to human-readable action."""
    return {
        "follow_up": "Send follow-up message",
        "reply_email": "Reply to email thread",
        "send_email": "Compose and send email",
        "cold_outreach": "Send cold outreach",
        "schedule_meeting": "Schedule meeting",
        "general": "Process request",
    }.get(intent_type, "Process request")


def _get_entity_tier(bundle: ContextBundle) -> str:
    """Get highest entity tier from bundle."""
    for _, data in bundle.memory.entity_data.items():
        if isinstance(data, dict) and data.get("tier") == "VIP":
            return "VIP"
    return "standard"
