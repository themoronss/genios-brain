"""LangGraph / LangChain tool integration for GeniOS.

Usage:
    from genios import GeniOS
    from genios.integrations.langgraph import GeniosToolkit
    from langgraph.prebuilt import create_react_agent

    genios  = GeniOS(api_key="gn_live_...")
    toolkit = GeniosToolkit(client=genios)
    tools   = toolkit.get_tools()

    agent = create_react_agent(model, tools)
    agent.invoke({"messages": [("user", "What do I know about Rohit?")]})
"""
from __future__ import annotations

import json
from typing import TYPE_CHECKING, Optional, Type

try:
    from langchain_core.tools import BaseTool
    from pydantic import BaseModel, Field
    _LANGCHAIN_AVAILABLE = True
except ImportError:
    _LANGCHAIN_AVAILABLE = False

if TYPE_CHECKING:
    from genios.client import GeniOS


def _require_langchain():
    if not _LANGCHAIN_AVAILABLE:
        raise ImportError(
            "langchain-core is required: pip install langchain-core"
        )


if _LANGCHAIN_AVAILABLE:
    class _GetContextInput(BaseModel):
        entity: str = Field(description="Email address, full name, or company name.")
        situation: str = Field(description="What you are about to do — helps return the most relevant context.")

    class _SearchInput(BaseModel):
        q: str = Field(description="Partial name, email, or company to search.")
        limit: int = Field(default=10, description="Max results.")

    class _LogInteractionInput(BaseModel):
        entity: str = Field(description="Email or name of the contact.")
        summary: str = Field(description="What you did.")
        channel: str = Field(default="email", description="email | slack | call | meeting | other")
        direction: str = Field(default="outbound", description="outbound | inbound")

    class _ListInsightsInput(BaseModel):
        limit: int = Field(default=10, description="Max insights to return.")

    class _GetContextTool(BaseTool):
        name: str = "genios_get_context"
        description: str = (
            "Retrieve relationship memory for a person or company from the GeniOS brain. "
            "Call this BEFORE drafting emails or planning outreach. Returns relationship stage, "
            "sentiment trend, open commitments, and specific action guidance."
        )
        args_schema: Type[BaseModel] = _GetContextInput
        _client: "GeniOS"

        def __init__(self, client: "GeniOS", **kwargs):
            super().__init__(**kwargs)
            self._client = client

        def _run(self, entity: str, situation: str) -> str:
            return json.dumps(self._client.context(entity=entity, situation=situation))

        async def _arun(self, entity: str, situation: str) -> str:
            return self._run(entity, situation)

    class _SearchContactsTool(BaseTool):
        name: str = "genios_search_contacts"
        description: str = (
            "Search contacts in the GeniOS brain by name, email, or company. "
            "Use this to resolve a partial name before calling genios_get_context."
        )
        args_schema: Type[BaseModel] = _SearchInput
        _client: "GeniOS"

        def __init__(self, client: "GeniOS", **kwargs):
            super().__init__(**kwargs)
            self._client = client

        def _run(self, q: str, limit: int = 10) -> str:
            return json.dumps(self._client._get("/v1/contacts", params={"q": q, "limit": limit}))

        async def _arun(self, q: str, limit: int = 10) -> str:
            return self._run(q, limit)

    class _LogInteractionTool(BaseTool):
        name: str = "genios_log_interaction"
        description: str = (
            "Log an interaction with a contact back to the GeniOS brain. "
            "Call this AFTER sending an email or any outreach so the brain stays up to date."
        )
        args_schema: Type[BaseModel] = _LogInteractionInput
        _client: "GeniOS"

        def __init__(self, client: "GeniOS", **kwargs):
            super().__init__(**kwargs)
            self._client = client

        def _run(self, entity: str, summary: str, channel: str = "email", direction: str = "outbound") -> str:
            return json.dumps(self._client._post("/v1/interaction", {
                "entity": entity, "summary": summary,
                "channel": channel, "direction": direction,
            }))

        async def _arun(self, entity: str, summary: str, channel: str = "email", direction: str = "outbound") -> str:
            return self._run(entity, summary, channel, direction)

    class _ListInsightsTool(BaseTool):
        name: str = "genios_list_insights"
        description: str = (
            "List proactive insights the GeniOS brain generated — cooling relationships, "
            "overdue commitments, anomalies. Use when the user asks 'what should I know?'"
        )
        args_schema: Type[BaseModel] = _ListInsightsInput
        _client: "GeniOS"

        def __init__(self, client: "GeniOS", **kwargs):
            super().__init__(**kwargs)
            self._client = client

        def _run(self, limit: int = 10) -> str:
            return json.dumps(self._client._get("/v1/insights", params={"limit": limit}))

        async def _arun(self, limit: int = 10) -> str:
            return self._run(limit)


class GeniosToolkit:
    """All GeniOS tools as LangChain/LangGraph BaseTool instances."""

    def __init__(self, client: "GeniOS"):
        _require_langchain()
        self._client = client

    def get_tools(self) -> list:
        return [
            _GetContextTool(client=self._client),
            _SearchContactsTool(client=self._client),
            _LogInteractionTool(client=self._client),
            _ListInsightsTool(client=self._client),
        ]
