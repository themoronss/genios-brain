"""
R2.5 — Merge & Dedupe

Merge conflicting memory items by confidence score.
Deduplicate items with identical content.
"""

import hashlib
import json


def content_hash(content: dict) -> str:
    """Create a deterministic hash of a dict for deduplication."""
    serialized = json.dumps(content, sort_keys=True, default=str)
    return hashlib.sha256(serialized.encode()).hexdigest()[:16]


def dedupe_memory_items(items: list[dict]) -> list[dict]:
    """
    Remove duplicate memory items based on content hash.

    Args:
        items: List of memory item dicts (must have "content" key).

    Returns:
        Deduplicated list, keeping the highest-confidence version.
    """
    seen: dict[str, dict] = {}

    for item in items:
        c = item.get("content", {})
        h = content_hash(c) if isinstance(c, dict) else content_hash({"_raw": c})

        if h not in seen:
            seen[h] = item
        else:
            # Keep the one with higher confidence
            existing_conf = seen[h].get("confidence", 0.0)
            new_conf = item.get("confidence", 0.0)
            if new_conf > existing_conf:
                seen[h] = item

    return list(seen.values())


def merge_preferences(items: list[dict]) -> dict:
    """
    Merge multiple preference memory items into one dict.
    If keys conflict, the higher-confidence value wins.

    Args:
        items: List of preference memory dicts with "content" and "confidence".

    Returns:
        Merged preferences dict.
    """
    merged = {}
    confidence_map: dict[str, float] = {}

    for item in items:
        content = item.get("content", {})
        conf = item.get("confidence", 0.5)

        if not isinstance(content, dict):
            continue

        for key, value in content.items():
            if key not in merged or conf > confidence_map.get(key, 0.0):
                merged[key] = value
                confidence_map[key] = conf

    return merged
