"""Anthropic tool-use integration for GeniOS.

Usage:
    import anthropic
    from genios import GeniOS
    from genios.integrations.anthropic import as_anthropic_tools, handle_anthropic_tool_call

    genios  = GeniOS(api_key="gn_live_...")
    ai      = anthropic.Anthropic()
    tools   = as_anthropic_tools()

    response = ai.messages.create(
        model="claude-opus-4-7",
        max_tokens=1024,
        tools=tools,
        messages=messages,
    )

    for block in response.content:
        if block.type == "tool_use":
            result = handle_anthropic_tool_call(genios, block)
            messages.append({"role": "user", "content": [{
                "type": "tool_result",
                "tool_use_id": block.id,
                "content": result,
            }]})
"""
from __future__ import annotations

import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from genios.client import GeniOS

_TOOLS = [
    {
        "name": "genios_get_context",
        "description": (
            "Retrieve relationship memory for a person or company from the GeniOS brain. "
            "Call this BEFORE drafting emails, messages, or planning outreach. "
            "Returns relationship stage, sentiment trend, open commitments, last interaction, "
            "and specific action guidance."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "entity": {
                    "type": "string",
                    "description": "Email address, full name, or company name of the contact.",
                },
                "situation": {
                    "type": "string",
                    "description": "What you are about to do — e.g. 'drafting a follow-up about pricing'.",
                },
            },
            "required": ["entity", "situation"],
        },
    },
    {
        "name": "genios_search_contacts",
        "description": (
            "Search contacts in the GeniOS brain by name, email, or company. "
            "Use this to resolve a partial name before calling genios_get_context."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "q": {"type": "string", "description": "Partial name, email, or company."},
                "limit": {"type": "integer", "description": "Max results (default 10)."},
            },
            "required": ["q"],
        },
    },
    {
        "name": "genios_log_interaction",
        "description": (
            "Log an interaction with a contact back to the GeniOS brain. "
            "Call this AFTER sending an email, making a call, or any outreach."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "entity": {"type": "string", "description": "Email or name of the contact."},
                "summary": {"type": "string", "description": "What you did."},
                "channel": {
                    "type": "string",
                    "enum": ["email", "slack", "call", "meeting", "other"],
                },
                "direction": {"type": "string", "enum": ["outbound", "inbound"]},
            },
            "required": ["entity", "summary"],
        },
    },
    {
        "name": "genios_list_insights",
        "description": (
            "List proactive insights the GeniOS brain generated — cooling relationships, "
            "overdue commitments, anomalies."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "description": "Max insights to return (default 10)."},
            },
        },
    },
]


def as_anthropic_tools() -> list[dict]:
    """Return GeniOS tools in Anthropic tool-use format."""
    return _TOOLS


def handle_anthropic_tool_call(client: "GeniOS", block) -> str:
    """Execute a tool_use block from an Anthropic response and return a JSON string."""
    name = block.name
    args = block.input or {}

    if name == "genios_get_context":
        result = client.context(
            entity=args["entity"],
            situation=args.get("situation", ""),
        )
    elif name == "genios_search_contacts":
        result = client._get("/v1/contacts", params={"q": args["q"], "limit": args.get("limit", 10)})
    elif name == "genios_log_interaction":
        payload = {"entity": args["entity"], "summary": args["summary"]}
        if args.get("channel"):
            payload["channel"] = args["channel"]
        if args.get("direction"):
            payload["direction"] = args["direction"]
        result = client._post("/v1/interaction", payload)
    elif name == "genios_list_insights":
        result = client._get("/v1/insights", params={"limit": args.get("limit", 10)})
    else:
        result = {"error": f"unknown tool: {name}"}

    return json.dumps(result)
