"""
R0.3 — Retrieval Plan Composer

Build the final QueryPlan from intent + requirements + budgets.
This is the main entry point for R0.
"""

import re
from core.contracts.query_plan import QueryPlan, RetrievalBudget
from layers.layer1_retrieval.r0_query_builder.intent_normalizer import (
    normalize_intent,
    IntentType,
)
from layers.layer1_retrieval.r0_query_builder.requirements_generator import (
    get_required_contexts,
)
from layers.layer1_retrieval.r0_query_builder import budgets


def build_query_plan(raw_intent: str) -> QueryPlan:
    """
    Full R0 pipeline: normalize intent → determine requirements → compose plan.

    Args:
        raw_intent: The user's original prompt text.

    Returns:
        A QueryPlan object ready for downstream sub-modules.
    """
    intent_type = normalize_intent(raw_intent)
    required_contexts = get_required_contexts(intent_type)
    entities = extract_entities(raw_intent)

    budget = RetrievalBudget(
        max_tool_calls=budgets.MAX_TOOL_CALLS,
        max_memory_items=budgets.MAX_MEMORY_ITEMS,
        max_tokens=budgets.MAX_TOKENS,
        max_precedents=budgets.MAX_PRECEDENTS,
    )

    # Build TTL overrides from tool defaults
    ttl_overrides = {}
    if "tools" in required_contexts:
        ttl_overrides = dict(budgets.TOOL_TTL_MAP)

    return QueryPlan(
        intent_type=intent_type.value,
        raw_intent=raw_intent,
        required_contexts=required_contexts,
        entities=entities,
        budget=budget,
        ttl_overrides=ttl_overrides,
    )


def extract_entities(text: str) -> list[str]:
    """
    Simple entity extraction: find capitalized multi-word names.
    MVP heuristic — not an NER model.

    Examples:
        "Follow up with Investor X" → ["Investor X"]
        "Email John Smith about the deal" → ["John Smith"]
    """
    # Match sequences of 2+ capitalized words (skip single common words)
    pattern = r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]*)+)\b"
    matches = re.findall(pattern, text)

    # Filter out common phrases that aren't entities
    stop_phrases = {"Follow Up", "Dear Sir", "Dear Madam", "Best Regards"}
    stop_starts = {"Email", "Send", "Reply", "Draft", "Schedule", "Book",
                   "Check", "Follow", "Get", "Set", "Make", "Write"}
    filtered = []
    for m in matches:
        if m in stop_phrases:
            continue
        first_word = m.split()[0]
        if first_word in stop_starts:
            # Try to salvage: remove the action word
            rest = m[len(first_word):].strip()
            if rest and rest[0].isupper():
                filtered.append(rest)
        else:
            filtered.append(m)
    return filtered
