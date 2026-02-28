"""
Tests for R2 — Memory Retrieval sub-modules.
Tests entity linker, merge/dedupe, and memory retriever.
"""

from layers.layer1_retrieval.r2_memory.entity_linker import (
    extract_entity_references,
    extract_names_from_text,
)
from layers.layer1_retrieval.r2_memory.merge_dedupe import (
    content_hash,
    dedupe_memory_items,
    merge_preferences,
)
from layers.layer1_retrieval.r2_memory.memory_retriever import MemoryRetriever
from core.contracts.query_plan import QueryPlan


# --- Entity Linker ---

def test_extract_entity_references_match():
    entities = [{"name": "Investor X"}, {"name": "John Smith"}]
    matched = extract_entity_references("follow up with Investor X", entities)
    assert "Investor X" in matched
    assert "John Smith" not in matched


def test_extract_entity_references_no_match():
    entities = [{"name": "Investor X"}]
    matched = extract_entity_references("check the calendar", entities)
    assert len(matched) == 0


def test_extract_names_from_text():
    names = extract_names_from_text("Email John Smith about Investor X")
    assert "John Smith" in names


# --- Merge & Dedupe ---

def test_content_hash_deterministic():
    h1 = content_hash({"tone": "confident"})
    h2 = content_hash({"tone": "confident"})
    assert h1 == h2


def test_content_hash_different():
    h1 = content_hash({"tone": "confident"})
    h2 = content_hash({"tone": "casual"})
    assert h1 != h2


def test_dedupe_removes_duplicates():
    items = [
        {"content": {"tone": "confident"}, "confidence": 0.8},
        {"content": {"tone": "confident"}, "confidence": 0.9},
    ]
    result = dedupe_memory_items(items)
    assert len(result) == 1
    assert result[0]["confidence"] == 0.9  # higher confidence kept


def test_dedupe_keeps_unique():
    items = [
        {"content": {"tone": "confident"}, "confidence": 0.8},
        {"content": {"tone": "casual"}, "confidence": 0.7},
    ]
    result = dedupe_memory_items(items)
    assert len(result) == 2


def test_merge_preferences_conflict():
    items = [
        {"content": {"tone": "confident"}, "confidence": 0.8},
        {"content": {"tone": "casual"}, "confidence": 0.9},
    ]
    merged = merge_preferences(items)
    assert merged["tone"] == "casual"  # higher confidence wins


def test_merge_preferences_combines():
    items = [
        {"content": {"tone": "confident"}, "confidence": 0.8},
        {"content": {"style": "brief"}, "confidence": 0.7},
    ]
    merged = merge_preferences(items)
    assert merged["tone"] == "confident"
    assert merged["style"] == "brief"


# --- Memory Retriever (mock mode) ---

def test_memory_retriever_mock():
    retriever = MemoryRetriever(memory_store=None)
    plan = QueryPlan(
        intent_type="follow_up",
        raw_intent="Follow up with Investor X",
        required_contexts=["memory"],
    )
    memory, sources = retriever.retrieve("u1", plan)
    assert memory.preferences["tone"] == "confident"
    assert "Investor X" in memory.entity_data
    assert len(sources) == 0  # no sources in mock mode
