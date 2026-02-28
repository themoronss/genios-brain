"""
Bundle Assembler — Main Assembler

Combines all sub-module outputs into the final ContextBundle.
"""

from core.contracts.context_bundle import (
    ContextBundle,
    ScopeContext,
    MemoryContext,
    PolicyContext,
    ToolContext,
    PrecedentContext,
    SourceRef,
    RetrievalMetrics,
    RelevantChunk,
)
from layers.layer1_retrieval.bundle_assembler.citations_builder import build_source_map
from layers.layer1_retrieval.bundle_assembler.metrics import compute_metrics


def assemble_bundle(
    scope: ScopeContext,
    memory: MemoryContext,
    policy: PolicyContext,
    tools: ToolContext,
    precedents: PrecedentContext,
    relevant_chunks: list[RelevantChunk],
    source_lists: list[list[SourceRef]],
    retrieval_time_ms: float = 0.0,
    query_plan_ref: dict = None,
) -> ContextBundle:
    """
    Assemble the final ContextBundle from all sub-module outputs.

    Args:
        scope: From R1 Scope Resolver.
        memory: From R2 Memory Retriever.
        policy: From R4 Policy Matcher.
        tools: From R3 Tool Orchestrator.
        precedents: From R5 Precedent Retriever.
        relevant_chunks: From VectorStore search.
        source_lists: List of SourceRef lists from each sub-module.
        retrieval_time_ms: Total retrieval time.

    Returns:
        Complete ContextBundle with metrics, citations, and version stamp.
    """
    # Merge all source citations
    source_map = build_source_map(*source_lists)

    # Add vector chunk sources
    for i, chunk in enumerate(relevant_chunks):
        source_map.append(SourceRef(
            source_type="vector",
            source_id=f"chunk_{i}",
            confidence=chunk.similarity,
        ))

    # Build initial bundle (without metrics — we need the bundle to compute them)
    bundle = ContextBundle(
        scope=scope,
        memory=memory,
        policy=policy,
        tools=tools,
        relevant_chunks=relevant_chunks,
        precedents=precedents,
        source_map=source_map,
        query_plan_ref=query_plan_ref or {},
        context_bundle_version="v1",
    )

    # Compute and attach metrics
    bundle.metrics = compute_metrics(bundle, retrieval_time_ms)

    return bundle
