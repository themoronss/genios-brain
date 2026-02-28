"""
R0.2 — Context Requirements Generator

Given an intent_type, decide which retrieval contexts are required.
"""

from layers.layer1_retrieval.r0_query_builder.intent_normalizer import IntentType


# Which contexts are required for each intent type.
# scope + policies are ALWAYS required.
_CONTEXT_REQUIREMENTS: dict[IntentType, list[str]] = {
    IntentType.FOLLOW_UP: ["scope", "memory", "tools", "policies", "precedents"],
    IntentType.SCHEDULE_MEETING: ["scope", "memory", "tools", "policies"],
    IntentType.REPLY_EMAIL: ["scope", "memory", "tools", "policies", "precedents"],
    IntentType.COLD_OUTREACH: ["scope", "memory", "policies", "precedents"],
    IntentType.SEND_EMAIL: ["scope", "memory", "tools", "policies"],
    IntentType.GENERAL: ["scope", "memory", "policies"],
}

# Mandatory contexts — always included regardless of intent
_MANDATORY = {"scope", "policies"}


def get_required_contexts(intent_type: IntentType) -> list[str]:
    """
    Return the list of context sections required for this intent type.

    Args:
        intent_type: Canonical intent type.

    Returns:
        List of context section names (e.g. ["scope", "memory", "tools", "policies"]).
    """
    contexts = set(_CONTEXT_REQUIREMENTS.get(intent_type, ["scope", "policies"]))
    contexts |= _MANDATORY
    return sorted(contexts)
