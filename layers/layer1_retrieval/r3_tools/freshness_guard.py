"""
R3.4 — Freshness Guard

Check tool state freshness based on TTL.
Mark stale results (don't silently drop them).
"""

from datetime import datetime, timezone


def check_freshness(tool_result: dict) -> tuple[dict, bool]:
    """
    Check if a tool result is stale based on its fetched_at and ttl_seconds.

    Args:
        tool_result: Dict with 'fetched_at' (ISO) and 'ttl_seconds'.

    Returns:
        Tuple of (tool_result, is_stale).
        The tool_result dict gets a 'is_stale' key added.
    """
    fetched_at_str = tool_result.get("fetched_at")
    ttl = tool_result.get("ttl_seconds", 120)

    if not fetched_at_str:
        # No timestamp — mark as stale by default
        tool_result["is_stale"] = True
        return tool_result, True

    try:
        fetched_at = datetime.fromisoformat(fetched_at_str)
        if fetched_at.tzinfo is None:
            fetched_at = fetched_at.replace(tzinfo=timezone.utc)

        now = datetime.now(timezone.utc)
        age_seconds = (now - fetched_at).total_seconds()

        is_stale = age_seconds > ttl
        tool_result["is_stale"] = is_stale
        return tool_result, is_stale

    except (ValueError, TypeError):
        tool_result["is_stale"] = True
        return tool_result, True
