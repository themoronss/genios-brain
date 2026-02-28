"""
J1.3 — Staleness Detector

Check tool_context.stale_flags for expired data.
Stale data should trigger clarifying questions, not silent failure.
"""

from core.contracts.context_bundle import ContextBundle


def detect_stale_data(bundle: ContextBundle) -> list[dict]:
    """
    Check for stale tool state in the bundle.

    Args:
        bundle: ContextBundle from Layer 1.

    Returns:
        List of stale data entries: [{"tool": ..., "reason": ...}]
    """
    stale_entries = []

    for tool_name, is_stale in bundle.tools.stale_flags.items():
        if is_stale:
            stale_entries.append({
                "tool": tool_name,
                "reason": f"{tool_name} data has expired (TTL exceeded)",
            })

    return stale_entries
