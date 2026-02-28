"""
R2.2 — Entity Linker

Extract entity references from intent text and map them to entity IDs.
MVP: keyword-based matching.
"""

import re


def extract_entity_references(intent: str, known_entities: list[dict]) -> list[str]:
    """
    Find which known entities are mentioned in the intent text.

    Args:
        intent: Raw intent text.
        known_entities: List of dicts with at least a "name" key.

    Returns:
        List of matched entity names.
    """
    text_lower = intent.lower()
    matched = []

    for entity in known_entities:
        name = entity.get("name", "")
        if name and name.lower() in text_lower:
            matched.append(name)

    return matched


def extract_names_from_text(text: str) -> list[str]:
    """
    Heuristic: find capitalized multi-word sequences that look like names.

    Args:
        text: Raw text to extract from.

    Returns:
        List of potential entity name strings.
    """
    pattern = r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]*)+)\b"
    matches = re.findall(pattern, text)

    # Filter out matches that start with common action verbs
    action_words = {"Email", "Send", "Reply", "Draft", "Schedule", "Book",
                    "Check", "Follow", "Get", "Set", "Make", "Write"}
    filtered = []
    for m in matches:
        first_word = m.split()[0]
        if first_word in action_words:
            rest = m[len(first_word):].strip()
            if rest and rest[0].isupper():
                filtered.append(rest)
        else:
            filtered.append(m)
    return filtered
