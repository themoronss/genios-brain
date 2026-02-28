"""
J1.1 — Required Fields Validator

Per-intent required fields list.
Returns missing fields that block safe action.
"""

from core.contracts.context_bundle import ContextBundle


# Required fields per intent type.
# Each entry: (field_path, human_label)
_REQUIRED_FIELDS: dict[str, list[tuple[str, str]]] = {
    "follow_up": [
        ("memory.entity_data", "Entity data for recipient"),
        ("memory.preferences", "User communication preferences"),
        ("tools.snapshots", "Email thread state"),
    ],
    "reply_email": [
        ("tools.snapshots", "Email thread state"),
        ("memory.preferences", "User communication preferences"),
    ],
    "send_email": [
        ("memory.preferences", "User communication preferences"),
    ],
    "cold_outreach": [
        ("memory.preferences", "User communication preferences"),
        ("policy.rules", "Outreach policies"),
    ],
    "schedule_meeting": [
        ("tools.snapshots", "Calendar availability"),
    ],
    "general": [],
}


def validate_required_fields(
    bundle: ContextBundle, intent_type: str
) -> list[dict]:
    """
    Check that all required fields for this intent are present and non-empty.

    Args:
        bundle: ContextBundle from Layer 1.
        intent_type: Canonical intent type.

    Returns:
        List of missing field dicts: [{"field": ..., "label": ...}]
    """
    required = _REQUIRED_FIELDS.get(intent_type, [])
    missing = []

    for field_path, label in required:
        if not _field_has_data(bundle, field_path):
            missing.append({"field": field_path, "label": label})

    return missing


def _field_has_data(bundle: ContextBundle, field_path: str) -> bool:
    """Check if a dotted field path has non-empty data in the bundle."""
    parts = field_path.split(".")
    obj = bundle

    for part in parts:
        if hasattr(obj, part):
            obj = getattr(obj, part)
        elif isinstance(obj, dict):
            obj = obj.get(part)
        else:
            return False

    # Check for empty containers
    if obj is None:
        return False
    if isinstance(obj, (dict, list)) and len(obj) == 0:
        return False

    return True
