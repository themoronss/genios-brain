from core.contracts.context_bundle import (
    ContextBundle,
    ScopeContext,
    MemoryContext,
    PolicyContext,
    ToolContext,
    RelevantChunk
)


class RetrievalEngine:

    def __init__(self, memory_store=None, vector_store=None):
        """
        Args:
            memory_store: Optional MemoryStore instance.
                          If provided, memory is fetched from Supabase.
                          If None, mock data is used (for testing).
            vector_store: Optional VectorStore instance.
                          If provided, semantic search is performed.
                          If None, no relevant chunks are returned.
        """
        self.memory_store = memory_store
        self.vector_store = vector_store

    def run(self, intent: str, workspace_id: str, actor_id: str) -> ContextBundle:
        """
        Layer 1 - Retrieval
        Responsibilities:
        - Resolve scope
        - Retrieve memory
        - Retrieve policy
        - Retrieve tool state
        - Retrieve relevant context (semantic search)
        - Assemble ContextBundle
        """

        scope = self._resolve_scope(workspace_id, actor_id)
        memory = self._retrieve_memory(actor_id)
        policy = self._retrieve_policy(workspace_id)
        tools = self._retrieve_tool_state(intent)
        relevant_chunks = self._retrieve_relevant_context(intent, workspace_id)

        return ContextBundle(
            scope=scope,
            memory=memory,
            policy=policy,
            tools=tools,
            relevant_chunks=relevant_chunks
        )

    def _resolve_scope(self, workspace_id: str, actor_id: str) -> ScopeContext:
        return ScopeContext(
            workspace_id=workspace_id,
            actor_id=actor_id,
            role="founder"  # mock role for now
        )

    def _retrieve_memory(self, actor_id: str) -> MemoryContext:
        if self.memory_store:
            # Real DB retrieval via Supabase
            preferences = self.memory_store.get_preferences(actor_id)
            entity_data = self.memory_store.get_entity_data(actor_id)
            return MemoryContext(
                preferences=preferences,
                entity_data=entity_data
            )

        # Mock fallback (for testing without DB)
        return MemoryContext(
            preferences={"tone": "confident"},
            entity_data={"Investor X": {"tier": "VIP"}}
        )

    def _retrieve_relevant_context(
        self, intent: str, workspace_id: str
    ) -> list[RelevantChunk]:
        """
        Perform semantic search using vector embeddings.
        Returns empty list if no vector_store is configured.
        """
        if not self.vector_store:
            return []

        results = self.vector_store.search(
            query=intent,
            workspace_id=workspace_id,
            top_k=5,
            threshold=0.3
        )

        return [
            RelevantChunk(
                content=r["content"],
                similarity=r["similarity"],
                metadata=r.get("metadata", {})
            )
            for r in results
        ]

    def _retrieve_policy(self, workspace_id: str) -> PolicyContext:
        return PolicyContext(
            rules=[
                {
                    "id": "P_VIP_APPROVAL",
                    "condition": {"recipient_tier": "VIP"},
                    "effect": {"requires_approval": True}
                }
            ]
        )

    def _retrieve_tool_state(self, intent: str) -> ToolContext:
        return ToolContext(
            snapshots={
                "gmail": {
                    "last_reply_days_ago": 10,
                    "thread_exists": True
                }
            }
        )

