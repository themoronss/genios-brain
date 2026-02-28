"""
Bundle Assembler — Citations Builder

Collects source references from each sub-module and builds
a unified source_map linking every fact to its origin.
"""

from core.contracts.context_bundle import SourceRef


def build_source_map(*source_lists: list[SourceRef]) -> list[SourceRef]:
    """
    Merge source reference lists from all sub-modules into one.

    Args:
        *source_lists: Variable number of SourceRef lists.

    Returns:
        Combined, deduplicated list of SourceRefs.
    """
    seen = set()
    merged = []

    for sources in source_lists:
        for ref in sources:
            key = f"{ref.source_type}:{ref.source_id}"
            if key not in seen:
                seen.add(key)
                merged.append(ref)

    return merged
