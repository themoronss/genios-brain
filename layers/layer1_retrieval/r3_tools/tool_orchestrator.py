"""
R3.2 — Tool Orchestrator

Runs all registered tool providers, respects budget, collects normalized results.
"""

from core.contracts.context_bundle import ToolContext, SourceRef
from core.contracts.query_plan import QueryPlan
from layers.layer1_retrieval.r3_tools.provider_base import (
    ToolProvider,
    MockGmailProvider,
    MockCalendarProvider,
)
from layers.layer1_retrieval.r3_tools.freshness_guard import check_freshness


# Default registered providers (mock for MVP)
_DEFAULT_PROVIDERS: list[ToolProvider] = [
    MockGmailProvider(),
    MockCalendarProvider(),
]


class ToolOrchestrator:
    """Runs tool providers and collects state within budget."""

    def __init__(self, providers: list[ToolProvider] = None):
        self.providers = providers if providers is not None else _DEFAULT_PROVIDERS

    def retrieve(
        self, query_plan: QueryPlan, workspace_id: str
    ) -> tuple[ToolContext, list[SourceRef]]:
        """
        Fetch tool state from all relevant providers.

        Args:
            query_plan: Controls intent_type + budget.
            workspace_id: Current workspace.

        Returns:
            Tuple of (ToolContext, list of SourceRefs).
        """
        snapshots = {}
        stale_flags = {}
        sources = []
        calls_made = 0

        for provider in self.providers:
            # Budget enforcement
            if calls_made >= query_plan.budget.max_tool_calls:
                break

            # Only call providers that support this intent
            if not provider.supports(query_plan.intent_type):
                continue

            result = provider.fetch(
                entities=query_plan.entities,
                workspace_id=workspace_id,
            )
            calls_made += 1

            # Check freshness
            result, is_stale = check_freshness(result)

            tool_name = provider.tool_name
            snapshots[tool_name] = result.get("result_summary", result)
            stale_flags[tool_name] = is_stale

            sources.append(SourceRef(
                source_type="tool",
                source_id=f"{tool_name}:{result.get('fetched_at', 'unknown')}",
                confidence=0.5 if is_stale else 1.0,
            ))

        return ToolContext(
            snapshots=snapshots,
            stale_flags=stale_flags,
        ), sources
