"""
Genios MCP server.

Exposes the Genios v1 API as Model Context Protocol tools so Claude (Desktop,
Code, or any MCP client) can pull relationship memory natively, without a
custom agent wrapper.

Tools:
    genios_get_context            Pull relationship memory for a person/company.
    genios_list_segments          List customer/contact segments.
    genios_get_segment_members    Enumerate contacts in a segment.
    genios_org_info               Plan, usage, graph stats.
    genios_sync_status            Data source sync state.
"""
import os
import json
import logging
from typing import Any

import requests
from dotenv import load_dotenv
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

load_dotenv()

API_KEY = os.getenv("GENIOS_API_KEY")
BASE_URL = os.getenv("GENIOS_BASE_URL", "https://api.genios.ai").rstrip("/")
AGENT_ID = os.getenv("GENIOS_AGENT_ID", "claude-mcp")

logging.basicConfig(level=logging.INFO, format="%(asctime)s [genios-mcp] %(message)s")
log = logging.getLogger("genios-mcp")

if not API_KEY:
    log.warning("GENIOS_API_KEY not set — tools will fail until .env is populated.")


def _headers() -> dict:
    return {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}


def _get(path: str, params: dict | None = None) -> dict:
    r = requests.get(f"{BASE_URL}{path}", headers=_headers(), params=params, timeout=15)
    if r.status_code >= 400:
        return {"error": f"HTTP {r.status_code}", "body": r.text[:500]}
    return r.json()


def _post(path: str, payload: dict) -> dict:
    r = requests.post(f"{BASE_URL}{path}", headers=_headers(), json=payload, timeout=20)
    if r.status_code >= 400:
        return {"error": f"HTTP {r.status_code}", "body": r.text[:500]}
    return r.json()


# ── MCP Server ─────────────────────────────────────────────────────────

server = Server("genios")


@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="genios_search_contacts",
            description=(
                "Search or list contacts in the user's Genios brain. "
                "Use this FIRST when the user mentions someone by partial name "
                "('Alice at Acme', 'Ashish from HDFC', 'the Adobe recruiter') — "
                "resolve to a canonical email, THEN call genios_get_context. "
                "Also handles common dashboard prompts:\n"
                "  - 'who needs attention' → needs_attention=true\n"
                "  - 'contacts I haven't replied to in 2 weeks' → silent_days=14\n"
                "  - 'what's overdue' → overdue=true\n"
                "  - 'active contacts this month' → recent_days=30\n"
                "Broadcast/marketing senders are excluded by default. "
                "Returns: id, name, email, company, stage, days since last contact, "
                "open commitment count, context_score."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "q": {"type": "string", "description": "Partial name, email, or company. Leave empty for recent contacts."},
                    "stage": {"type": "string", "description": "Optional filter: ACTIVE, WARM, COLD, DORMANT, NEEDS_ATTENTION, AT_RISK."},
                    "needs_attention": {"type": "boolean", "default": False, "description": "Shortcut for stage=NEEDS_ATTENTION."},
                    "recent_days": {"type": ["integer", "string"], "description": "Only contacts with last interaction within N days."},
                    "silent_days": {"type": ["integer", "string"], "description": "Only contacts we haven't interacted with in >= N days (re-engagement)."},
                    "overdue": {"type": "boolean", "default": False, "description": "Only contacts with overdue commitments."},
                    "exclude_broadcast": {"type": "boolean", "default": True, "description": "Hide noreply/marketing senders. Set false to include them."},
                    "limit": {"type": ["integer", "string"], "default": 20, "description": "Max results (1-100)."},
                },
            },
        ),
        Tool(
            name="genios_get_context",
            description=(
                "Retrieve relationship memory for a person or company from the user's Genios brain. "
                "Use this BEFORE drafting emails, messages, or planning outreach. "
                "Returns: relationship_stage, sentiment_trend, communication_style, "
                "topics_of_interest, open_commitments, last_interaction, and agent guidance. "
                "Call this proactively whenever the user mentions a named person or company — "
                "it prevents reintroducing yourself, forgetting commitments, and tone mismatches.\n\n"
                "IMPORTANT: When the response includes a `related_outbound` field, it lists "
                "the user's recent outbound messages on the same topic to OTHER contacts. "
                "Read those excerpts and reuse the framing — do NOT ask the user for "
                "context that's already in related_outbound."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "entity": {
                        "type": "string",
                        "description": "Email address OR full name OR company name of the contact.",
                    },
                    "situation": {
                        "type": "string",
                        "description": "What you're about to do (e.g. 'drafting reply about Q2 pricing'). Helps Genios return the most relevant context.",
                    },
                },
                "required": ["entity"],
            },
        ),
        Tool(
            name="genios_list_segments",
            description=(
                "List all customer/contact segments defined in the user's Genios brain. "
                "Use when the user refers to a group ('my enterprise customers', 'champions', 'at-risk accounts')."
            ),
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="genios_get_segment_members",
            description=(
                "Enumerate contacts in a specific segment. "
                "Use after genios_list_segments to answer 'who's in segment X'."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "segment_id": {"type": "string", "description": "Segment ID from genios_list_segments."},
                    "limit": {"type": "integer", "default": 50, "description": "Max members to return."},
                },
                "required": ["segment_id"],
            },
        ),
        Tool(
            name="genios_org_info",
            description="Org profile, plan tier, usage stats, and graph totals (contacts, clusters).",
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="genios_list_insights",
            description=(
                "List proactive insights generated by GeniOS's background scanner. "
                "These are things GeniOS noticed without anyone asking — anomalies, "
                "cooling relationships, overdue commitments going stale. "
                "Use when the user asks 'what should I know?' or 'any alerts?'"
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "status": {"type": "string", "description": "Filter: pending | delivered | dismissed. Default: all non-dismissed."},
                    "limit": {"type": ["integer", "string"], "default": 10},
                },
            },
        ),
        Tool(
            name="genios_log_interaction",
            description=(
                "Write-back: log an action you just took on a contact. "
                "Call this AFTER sending an email, making a call, or any outreach. "
                "Keeps the brain fresh in real-time without waiting for Gmail sync."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "entity": {"type": "string", "description": "Email or name of the contact you acted on."},
                    "summary": {"type": "string", "description": "What you did. E.g. 'Sent follow-up email about Q2 pricing'"},
                    "direction": {"type": "string", "default": "outbound", "description": "outbound (you sent) or inbound (you received)"},
                    "channel": {"type": "string", "default": "email", "description": "email | slack | call | meeting | other"},
                    "sentiment": {"type": "number", "description": "Your assessment: -1.0 (negative) to 1.0 (positive)"},
                    "topics": {"type": "array", "items": {"type": "string"}, "description": "Topics discussed"},
                },
                "required": ["entity", "summary"],
            },
        ),
        Tool(
            name="genios_log_outcome",
            description=(
                "Feedback: report whether the context you got was useful. "
                "Call this when you know the result of an action — e.g. customer replied, "
                "deal closed, no response after 7 days. Helps the brain learn."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "context_id": {"type": "string", "description": "The bundle_id from the /v1/context response."},
                    "outcome": {"type": "string", "description": "positive | negative | neutral"},
                    "details": {"type": "string", "description": "What happened. E.g. 'Customer replied within 1 hour'"},
                },
                "required": ["context_id", "outcome"],
            },
        ),
        Tool(
            name="genios_trigger_scan",
            description=(
                "Trigger a manual proactive scan NOW. Runs anomaly detection, "
                "root cause analysis, and generates fresh insights. Use when user says "
                "'scan my contacts' or 'check for anything unusual'."
            ),
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="genios_sync_status",
            description="Check data source sync state (Gmail, Calendar, Slack, etc.) — tells you how fresh the context is.",
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="genios_search_messages",
            description=(
                "Search the user's own recent sent + received messages across the whole network. "
                "Use this when drafting outreach to find similar prior messages the user has already "
                "written on the same topic — reuse their framing instead of asking them for context. "
                "Also useful for 'what did I say about X last week' and 'who have I been emailing "
                "about project Y'. Scoped to the caller's org; respects privacy settings. "
                "Results include subject, excerpt, contact, topics, and timestamp."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "q": {"type": "string", "description": "Keyword or phrase (full-text search over subject + body)."},
                    "direction": {"type": "string", "description": "outbound | inbound. Omit for both."},
                    "days": {"type": ["integer", "string"], "default": 14, "description": "Recency window in days (1-365)."},
                    "limit": {"type": ["integer", "string"], "default": 10, "description": "Max results (1-50)."},
                    "contact_id": {"type": "string", "description": "Optional: scope to a single contact UUID."},
                },
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    log.info(f"call_tool: {name} args={json.dumps(arguments)[:200]}")

    if name == "genios_search_contacts":
        params: dict = {}
        if arguments.get("q"):
            params["q"] = arguments["q"]
        if arguments.get("stage"):
            params["stage"] = arguments["stage"]
        if arguments.get("needs_attention"):
            params["needs_attention"] = "true"
        if arguments.get("recent_days") is not None:
            params["recent_days"] = int(arguments["recent_days"])
        if arguments.get("silent_days") is not None:
            params["silent_days"] = int(arguments["silent_days"])
        if arguments.get("overdue"):
            params["overdue"] = "true"
        if arguments.get("exclude_broadcast") is False:
            params["exclude_broadcast"] = "false"
        if arguments.get("limit"):
            params["limit"] = int(arguments["limit"])
        if params:
            qs = "&".join(f"{k}={v}" for k, v in params.items())
            path = f"/v1/contacts?{qs}"
        else:
            path = "/v1/contacts"
        return [TextContent(type="text", text=json.dumps(_get(path), indent=2))]

    if name == "genios_get_context":
        entity = arguments.get("entity", "").strip()
        if not entity:
            return [TextContent(type="text", text=json.dumps({"error": "entity is required"}))]
        payload = {"entity": entity, "agent_id": AGENT_ID}
        situation = arguments.get("situation", "").strip()
        if situation:
            payload["situation"] = situation[:500]
        data = _post("/v1/context", payload)
        return [TextContent(type="text", text=json.dumps(data, indent=2))]

    if name == "genios_list_segments":
        return [TextContent(type="text", text=json.dumps(_get("/v1/segments"), indent=2))]

    if name == "genios_get_segment_members":
        sid = arguments.get("segment_id")
        if not sid:
            return [TextContent(type="text", text=json.dumps({"error": "segment_id is required"}))]
        limit = int(arguments.get("limit", 50))
        data = _get(f"/v1/segment/{sid}/members", params={"limit": limit})
        return [TextContent(type="text", text=json.dumps(data, indent=2))]

    if name == "genios_org_info":
        return [TextContent(type="text", text=json.dumps(_get("/v1/org"), indent=2))]

    if name == "genios_sync_status":
        return [TextContent(type="text", text=json.dumps(_get("/v1/sync"), indent=2))]

    if name == "genios_list_insights":
        params = {}
        if arguments.get("status"):
            params["status"] = arguments["status"]
        if arguments.get("limit"):
            params["limit"] = int(arguments["limit"])
        qs = "&".join(f"{k}={v}" for k, v in params.items()) if params else ""
        path = f"/v1/insights?{qs}" if qs else "/v1/insights"
        return [TextContent(type="text", text=json.dumps(_get(path), indent=2))]

    if name == "genios_log_interaction":
        payload = {
            "entity": arguments["entity"],
            "summary": arguments["summary"],
        }
        for k in ("direction", "channel", "sentiment", "topics"):
            if arguments.get(k) is not None:
                payload[k] = arguments[k]
        payload["agent_id"] = AGENT_ID
        return [TextContent(type="text", text=json.dumps(_post("/v1/interaction", payload), indent=2))]

    if name == "genios_log_outcome":
        payload = {
            "context_id": arguments["context_id"],
            "outcome": arguments["outcome"],
            "agent_id": AGENT_ID,
        }
        if arguments.get("details"):
            payload["details"] = arguments["details"]
        return [TextContent(type="text", text=json.dumps(_post("/v1/outcome", payload), indent=2))]

    if name == "genios_trigger_scan":
        return [TextContent(type="text", text=json.dumps(_post("/v1/scan", {}), indent=2))]

    if name == "genios_search_messages":
        params: dict = {}
        if arguments.get("q"):
            params["q"] = arguments["q"]
        if arguments.get("direction"):
            params["direction"] = arguments["direction"]
        if arguments.get("days") is not None:
            params["days"] = int(arguments["days"])
        if arguments.get("limit") is not None:
            params["limit"] = int(arguments["limit"])
        if arguments.get("contact_id"):
            params["contact_id"] = arguments["contact_id"]
        qs = "&".join(f"{k}={v}" for k, v in params.items()) if params else ""
        path = f"/v1/messages/search?{qs}" if qs else "/v1/messages/search"
        return [TextContent(type="text", text=json.dumps(_get(path), indent=2))]

    return [TextContent(type="text", text=json.dumps({"error": f"unknown tool: {name}"}))]


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
