"""
Tests for Bundle Assembler — assembler, citations, and metrics.
"""

from core.contracts.context_bundle import (
    ScopeContext,
    MemoryContext,
    PolicyContext,
    ToolContext,
    PrecedentContext,
    RelevantChunk,
    SourceRef,
)
from layers.layer1_retrieval.bundle_assembler.assembler import assemble_bundle
from layers.layer1_retrieval.bundle_assembler.citations_builder import build_source_map
from layers.layer1_retrieval.bundle_assembler.metrics import compute_metrics


# --- Citations Builder ---

def test_build_source_map_merges():
    list1 = [SourceRef(source_type="memory", source_id="m1")]
    list2 = [SourceRef(source_type="policy", source_id="p1")]
    merged = build_source_map(list1, list2)
    assert len(merged) == 2


def test_build_source_map_dedupes():
    list1 = [SourceRef(source_type="memory", source_id="m1")]
    list2 = [SourceRef(source_type="memory", source_id="m1")]
    merged = build_source_map(list1, list2)
    assert len(merged) == 1


# --- Assembler ---

def test_assemble_bundle_complete():
    scope = ScopeContext(workspace_id="w1", actor_id="u1", role="founder")
    memory = MemoryContext(preferences={"tone": "confident"})
    policy = PolicyContext(rules=[{"id": "P1"}])
    tools = ToolContext(snapshots={"gmail": {"thread_exists": True}})
    precedents = PrecedentContext(past_decisions=[{"id": "d1"}])
    chunks = [RelevantChunk(content="test", similarity=0.8)]

    bundle = assemble_bundle(
        scope=scope,
        memory=memory,
        policy=policy,
        tools=tools,
        precedents=precedents,
        relevant_chunks=chunks,
        source_lists=[[SourceRef(source_type="memory", source_id="m1")]],
    )

    assert bundle.scope.workspace_id == "w1"
    assert bundle.context_bundle_version == "v1"
    assert len(bundle.source_map) >= 2  # memory + vector chunk
    assert bundle.metrics.total_memory_items > 0
    assert bundle.metrics.total_tool_calls == 1
    assert bundle.metrics.total_precedents == 1


# --- Metrics ---

def test_compute_metrics():
    scope = ScopeContext(workspace_id="w1", actor_id="u1", role="founder")
    bundle = assemble_bundle(
        scope=scope,
        memory=MemoryContext(preferences={"tone": "confident"}, entity_data={"X": {}}),
        policy=PolicyContext(rules=[{"id": "P1"}, {"id": "P2"}]),
        tools=ToolContext(snapshots={"gmail": {}}),
        precedents=PrecedentContext(),
        relevant_chunks=[],
        source_lists=[],
    )

    assert bundle.metrics.total_memory_items >= 2  # 1 pref + 1 entity
    assert bundle.metrics.total_tool_calls == 1
    assert bundle.metrics.total_policies_matched == 2
    assert bundle.metrics.estimated_tokens > 0
