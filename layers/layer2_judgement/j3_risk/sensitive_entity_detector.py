"""
J3.1 — Sensitive Entity Detector

Detect VIP investors, legal, HR, finance, security entities and topics.
"""

from core.contracts.context_bundle import ContextBundle


# Sensitive keywords by category
_SENSITIVE_KEYWORDS = {
    "legal": ["legal", "lawsuit", "compliance", "regulation", "contract", "nda"],
    "finance": ["revenue", "valuation", "funding", "investment", "equity", "shares"],
    "hr": ["termination", "fired", "harassment", "compensation", "salary"],
    "security": ["password", "credentials", "breach", "vulnerability", "access"],
}


def detect_sensitive_entities(
    bundle: ContextBundle, intent_type: str
) -> list[str]:
    """
    Detect sensitive entities and topics from the ContextBundle.

    Args:
        bundle: ContextBundle from Layer 1.
        intent_type: For context-aware detection.

    Returns:
        List of sensitive entity/topic strings.
    """
    sensitive = []

    # 1. Check entity data for VIP tier
    for entity_name, data in bundle.memory.entity_data.items():
        if isinstance(data, dict) and data.get("tier") == "VIP":
            sensitive.append(f"VIP: {entity_name}")

    # 2. Check for sensitive topics in entity names
    all_entity_names = " ".join(bundle.memory.entity_data.keys()).lower()
    for category, keywords in _SENSITIVE_KEYWORDS.items():
        for kw in keywords:
            if kw in all_entity_names:
                sensitive.append(f"{category}: {kw}")

    # 3. External-facing intents are inherently more sensitive
    if intent_type in ("cold_outreach", "send_email"):
        sensitive.append("external_communication")

    return sensitive
