"""
Bundle Assembler — Retrieval Metrics

Compute metrics about what Layer 1 fetched:
total items, tool calls, retrieval time, estimated tokens.
"""

import json

from core.contracts.context_bundle import (
    ContextBundle,
    RetrievalMetrics,
)


def compute_metrics(
    bundle: ContextBundle,
    retrieval_time_ms: float = 0.0,
) -> RetrievalMetrics:
    """
    Compute retrieval metrics from a completed ContextBundle.

    Args:
        bundle: The assembled ContextBundle.
        retrieval_time_ms: Total time spent in Layer 1.

    Returns:
        RetrievalMetrics with counts and estimates.
    """
    # Count memory items
    memory_count = (
        len(bundle.memory.preferences)
        + len(bundle.memory.entity_data)
        + len(bundle.memory.episodic)
        + len(bundle.memory.outcomes)
    )

    # Count tool calls
    tool_count = len(bundle.tools.snapshots)

    # Count precedents
    precedent_count = len(bundle.precedents.past_decisions)

    # Count matched policies
    policy_count = len(bundle.policy.rules)

    # Estimate tokens (rough: serialize to JSON and count chars / 4)
    try:
        serialized = bundle.model_dump_json()
        estimated_tokens = len(serialized) // 4
    except Exception:
        estimated_tokens = 0

    return RetrievalMetrics(
        total_memory_items=memory_count,
        total_tool_calls=tool_count,
        total_precedents=precedent_count,
        total_policies_matched=policy_count,
        retrieval_time_ms=round(retrieval_time_ms, 2),
        estimated_tokens=estimated_tokens,
    )
