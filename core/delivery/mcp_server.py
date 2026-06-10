"""MCP server — exposes engine capabilities as MCP tools (per Group 3 lock: HTTP+SSE).

Per MD g-i-7 §0: agent priority > human. Tools exposed:
- intelligence.query       -> wraps core.decision.decide; returns Envelope
- intelligence.explain     -> wraps core.artifacts trace; returns Trace JSON
- intelligence.feedback    -> wraps core.delivery.feedback_capture
- intelligence.graph_view  -> wraps core.artifacts.graph_view (read-only)

This module exposes the TOOL REGISTRY contract. The actual MCP protocol
(JSON-RPC framing over HTTP+SSE) is wired in the FastAPI router. Keeping the
tool definitions here lets us unit-test them without a transport.

For the design partner's first context-inject tool (Claude Code / Cursor /
custom), the same registry is consumed — agent-platform-agnostic.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class MCPTool:
    """One tool exposed via MCP. Schema-validated input + JSON output."""

    name: str
    description: str
    input_schema: dict[str, Any]
    handler: Callable[[dict[str, Any]], dict[str, Any]]


@dataclass
class MCPServer:
    """In-memory registry of tools. Transport layer (FastAPI route) calls dispatch()."""

    tools: dict[str, MCPTool] = field(default_factory=dict)

    def register(self, tool: MCPTool) -> None:
        if tool.name in self.tools:
            raise ValueError(f"Duplicate MCP tool: {tool.name}")
        self.tools[tool.name] = tool

    def list_tools(self) -> list[dict[str, Any]]:
        """MCP protocol — list available tools to the agent."""
        return [
            {
                "name": t.name,
                "description": t.description,
                "input_schema": t.input_schema,
            }
            for t in self.tools.values()
        ]

    def dispatch(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """Invoke a tool. Returns its JSON output. Raises KeyError if unknown tool."""
        if name not in self.tools:
            raise KeyError(f"Unknown MCP tool: {name}")
        return self.tools[name].handler(arguments)


# ─────────────────────────────────────────────────────────────────────────────
# Default tool definitions — wired in core/main.py at app startup
# ─────────────────────────────────────────────────────────────────────────────


_QUERY_INPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["org_id", "query", "facts"],
    "properties": {
        "org_id": {"type": "string"},
        "query": {"type": "object"},
        "facts": {"type": "object"},
        "module_id": {"type": "string"},
        "user_id": {"type": "string"},
    },
}

_EXPLAIN_INPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["org_id", "decision_id"],
    "properties": {
        "org_id": {"type": "string"},
        "decision_id": {"type": "string"},
    },
}

_FEEDBACK_INPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["org_id", "user_id", "action"],
    "properties": {
        "org_id": {"type": "string"},
        "user_id": {"type": "string"},
        "decision_id": {"type": "string"},
        "insight_id": {"type": "string"},
        "action": {
            "type": "string",
            "enum": ["thumbs_up", "thumbs_down", "edit", "snooze", "never_show"],
        },
        "edit_diff": {"type": "object"},
    },
}

_GRAPH_VIEW_INPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["org_id", "center_node_ids"],
    "properties": {
        "org_id": {"type": "string"},
        "center_node_ids": {"type": "array", "items": {"type": "string"}},
        "hops": {"type": "integer", "minimum": 0, "maximum": 3},
    },
}


def default_tool_definitions(
    *,
    query_handler: Callable[[dict[str, Any]], dict[str, Any]],
    explain_handler: Callable[[dict[str, Any]], dict[str, Any]],
    feedback_handler: Callable[[dict[str, Any]], dict[str, Any]],
    graph_view_handler: Callable[[dict[str, Any]], dict[str, Any]],
) -> list[MCPTool]:
    """Construct the standard tool set. Handlers wire to engine/store via callers."""
    return [
        MCPTool(
            name="intelligence.query",
            description="Ask the engine. Returns an Envelope with derivation + uncertainty.",
            input_schema=_QUERY_INPUT_SCHEMA,
            handler=query_handler,
        ),
        MCPTool(
            name="intelligence.explain",
            description="Fetch the trace + narrator output for a past decision_id.",
            input_schema=_EXPLAIN_INPUT_SCHEMA,
            handler=explain_handler,
        ),
        MCPTool(
            name="intelligence.feedback",
            description="Record 👍/👎/edit feedback on a decision/insight (becomes a Correction).",
            input_schema=_FEEDBACK_INPUT_SCHEMA,
            handler=feedback_handler,
        ),
        MCPTool(
            name="intelligence.graph_view",
            description="Read-only subgraph view (provenance + weight + trust visible).",
            input_schema=_GRAPH_VIEW_INPUT_SCHEMA,
            handler=graph_view_handler,
        ),
    ]
