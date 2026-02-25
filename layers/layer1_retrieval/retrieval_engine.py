from core.contracts.context_bundle import (
    ContextBundle,
    ScopeContext,
    MemoryContext,
    PolicyContext,
    ToolContext
)


class RetrievalEngine:

    def run(self, intent: str, workspace_id: str, actor_id: str) -> ContextBundle:
        """
        Layer 1 - Retrieval
        Responsibilities:
        - Resolve scope
        - Retrieve memory
        - Retrieve policy
        - Retrieve tool state
        - Assemble ContextBundle
        """

        scope = self._resolve_scope(workspace_id, actor_id)
        memory = self._retrieve_memory(actor_id)
        policy = self._retrieve_policy(workspace_id)
        tools = self._retrieve_tool_state(intent)

        return ContextBundle(
            scope=scope,
            memory=memory,
            policy=policy,
            tools=tools
        )

    def _resolve_scope(self, workspace_id: str, actor_id: str) -> ScopeContext:
        return ScopeContext(
            workspace_id=workspace_id,
            actor_id=actor_id,
            role="founder"  # mock role for now
        )

    def _retrieve_memory(self, actor_id: str) -> MemoryContext:
        return MemoryContext(
            preferences={"tone": "confident"},
            entity_data={"Investor X": {"tier": "VIP"}}
        )

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