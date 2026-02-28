"""
R2 — Memory Retriever

Orchestrates preference, entity, episodic, and outcome memory retrieval
using the existing MemoryStore, with merge & dedup.
"""

from core.contracts.context_bundle import MemoryContext, SourceRef
from core.contracts.query_plan import QueryPlan
from core.stores.memory_store import MemoryStore
from layers.layer1_retrieval.r2_memory.merge_dedupe import (
    dedupe_memory_items,
    merge_preferences,
)


class MemoryRetriever:
    """Structured memory retrieval by memory type with dedup."""

    def __init__(self, memory_store: MemoryStore = None):
        self.memory_store = memory_store

    def retrieve(
        self, actor_id: str, query_plan: QueryPlan
    ) -> tuple[MemoryContext, list[SourceRef]]:
        """
        Retrieve memory context for the given actor.

        Args:
            actor_id: Actor whose memories to fetch.
            query_plan: Controls budget (max_memory_items).

        Returns:
            Tuple of (MemoryContext, list of SourceRefs for citations).
        """
        if not self.memory_store:
            return self._mock_memory(), []

        sources = []

        # Fetch all memories for this actor
        all_items = self.memory_store.get_by_actor(actor_id)
        all_items = dedupe_memory_items(all_items)

        # Budget enforcement
        max_items = query_plan.budget.max_memory_items
        all_items = all_items[:max_items]

        # Split by type
        preferences_raw = [i for i in all_items if i.get("memory_type") == "preference"]
        entities_raw = [i for i in all_items if i.get("memory_type") == "entity"]
        episodic_raw = [i for i in all_items if i.get("memory_type") == "episodic"]
        outcomes_raw = [i for i in all_items if i.get("memory_type") == "outcome"]

        # Build merged preferences
        preferences = merge_preferences(preferences_raw)

        # Build entity data
        entity_data = {}
        for item in entities_raw:
            content = item.get("content", {})
            if isinstance(content, dict):
                entity_data.update(content)

        # Build source refs
        for item in all_items:
            item_id = item.get("id", "unknown")
            sources.append(SourceRef(
                source_type="memory",
                source_id=str(item_id),
                confidence=item.get("confidence", 1.0),
            ))

        return MemoryContext(
            preferences=preferences,
            entity_data=entity_data,
            episodic=[i.get("content", {}) for i in episodic_raw],
            outcomes=[i.get("content", {}) for i in outcomes_raw],
        ), sources

    def _mock_memory(self) -> MemoryContext:
        """Fallback mock data when no MemoryStore is configured."""
        return MemoryContext(
            preferences={"tone": "confident"},
            entity_data={"Investor X": {"tier": "VIP"}},
        )
