"""OpenAI function-calling integration for GeniOS.

Usage:
    from genios import GeniOS
    from genios.integrations.openai import as_openai_tools, handle_openai_tool_call

    client = GeniOS(api_key="gn_live_...")
    tools  = as_openai_tools()

    response = openai.chat.completions.create(
        model="gpt-4o",
        messages=messages,
        tools=tools,
    )

    for tool_call in response.choices[0].message.tool_calls or []:
        result = handle_openai_tool_call(client, tool_call)
        messages.append({"role": "tool", "tool_call_id": tool_call.id, "content": result})
"""
from __future__ import annotations

import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from genios.client import GeniOS

_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "genios_get_context",
            "description": (
                "Retrieve relationship memory for a person or company from the GeniOS brain. "
                "Call this BEFORE drafting emails, messages, or planning outreach. "
                "Returns relationship stage, sentiment trend, open commitments, last interaction, "
                "and specific action guidance."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "entity": {
                        "type": "string",
                        "description": "Email address, full name, or company name of the contact.",
                    },
                    "situation": {
                        "type": "string",
                        "description": "What you are about to do — e.g. 'drafting a follow-up email about pricing'.",
                    },
                },
                "required": ["entity", "situation"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "genios_search_contacts",
            "description": (
                "Search contacts in the GeniOS brain by name, email, or company. "
                "Use this to resolve a partial name before calling genios_get_context."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "q": {"type": "string", "description": "Partial name, email, or company."},
                    "limit": {"type": "integer", "description": "Max results (default 10)."},
                },
                "required": ["q"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "genios_log_interaction",
            "description": (
                "Log an interaction with a contact back to the GeniOS brain. "
                "Call this AFTER sending an email, making a call, or any outreach "
                "so the brain stays up to date."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "entity": {"type": "string", "description": "Email or name of the contact."},
                    "summary": {"type": "string", "description": "What you did."},
                    "channel": {
                        "type": "string",
                        "enum": ["email", "slack", "call", "meeting", "other"],
                        "description": "Communication channel used.",
                    },
                    "direction": {
                        "type": "string",
                        "enum": ["outbound", "inbound"],
                    },
                },
                "required": ["entity", "summary"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "genios_list_insights",
            "description": (
                "List proactive insights the GeniOS brain generated — cooling relationships, "
                "overdue commitments, anomalies. Use when the user asks 'what should I know?' "
                "or 'any alerts?'"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "description": "Max insights to return (default 10)."},
                },
            },
        },
    },
]


def as_openai_tools() -> list[dict]:
    """Return GeniOS tools in OpenAI function-calling format."""
    return _TOOLS


def handle_openai_tool_call(client: "GeniOS", tool_call) -> str:
    """Execute a tool_call object from an OpenAI response and return a JSON string."""
    name = tool_call.function.name
    args = json.loads(tool_call.function.arguments or "{}")

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
