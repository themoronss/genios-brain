"""
MCP tool definitions + dispatcher.

Schemas mirror genios-mcp/server.py so a local stdio client and the remote
streamable-HTTP endpoint expose an identical tool surface. Dispatch proxies
each tool to the existing /v1/* routes via an in-process ASGI transport —
the auth token the MCP client supplied is passed straight through, so every
tool inherits the same quota, plan gates, and org isolation as a direct
REST caller.
"""
from __future__ import annotations

from typing import Any

import httpx

TOOLS: list[dict[str, Any]] = [
    {
        "name": "genios_search_contacts",
        "description": (
            "Search or list contacts in the user's Genios brain. Call FIRST "
            "when the user mentions someone by partial name, then pass the "
            "resolved email to genios_get_context. Handles 'who needs "
            "attention' (needs_attention=true), 'contacts I haven't replied "
            "to in N days' (silent_days=N), 'overdue' (overdue=true), "
            "'active this month' (recent_days=30). Broadcast senders "
            "excluded by default."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "q": {"type": "string"},
                "stage": {"type": "string"},
                "needs_attention": {"type": "boolean", "default": False},
                "recent_days": {"type": ["integer", "string"]},
                "silent_days": {"type": ["integer", "string"]},
                "overdue": {"type": "boolean", "default": False},
                "exclude_broadcast": {"type": "boolean", "default": True},
                "limit": {"type": ["integer", "string"], "default": 20},
            },
        },
    },
    {
        "name": "genios_get_context",
        "description": (
            "Retrieve relationship memory for a person or company. Call "
            "BEFORE drafting outreach. Returns relationship_stage, "
            "sentiment_trend, communication_style, topics, open_commitments, "
            "last_interaction, and agent guidance."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "entity": {"type": "string"},
                "situation": {"type": "string"},
            },
            "required": ["entity"],
        },
    },
    {
        "name": "genios_list_segments",
        "description": "List all contact segments defined in the org.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "genios_get_segment_members",
        "description": "Enumerate contacts in a specific segment.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "segment_id": {"type": "string"},
                "limit": {"type": "integer", "default": 50},
            },
            "required": ["segment_id"],
        },
    },
    {
        "name": "genios_org_info",
        "description": "Org profile, plan tier, usage, and graph totals.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "genios_list_insights",
        "description": (
            "List proactive insights (anomalies, cooling relationships, "
            "overdue commitments). Use for 'what should I know' / 'any alerts'."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "status": {"type": "string"},
                "limit": {"type": ["integer", "string"], "default": 10},
            },
        },
    },
    {
        "name": "genios_log_interaction",
        "description": (
            "Write-back: log an action just taken on a contact (email sent, "
            "call made, meeting). Keeps the brain fresh between Gmail syncs."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "entity": {"type": "string"},
                "summary": {"type": "string"},
                "direction": {"type": "string", "default": "outbound"},
                "channel": {"type": "string", "default": "email"},
                "sentiment": {"type": "number"},
                "topics": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["entity", "summary"],
        },
    },
    {
        "name": "genios_log_outcome",
        "description": (
            "Feedback: report whether the retrieved context was useful. "
            "Helps the brain learn which retrievals drove outcomes."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "context_id": {"type": "string"},
                "outcome": {"type": "string"},
                "details": {"type": "string"},
            },
            "required": ["context_id", "outcome"],
        },
    },
    {
        "name": "genios_trigger_scan",
        "description": (
            "Trigger a manual proactive scan now. Runs anomaly detection "
            "and generates fresh insights."
        ),
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "genios_sync_status",
        "description": "Sync state of connected data sources (Gmail, Calendar, Slack).",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        # ── Phase 5: flagship live search tool ──
        "name": "genios_live_search",
        "description": (
            "Live multi-tool search. Use when the user asks for SPECIFIC "
            "data the cached graph may not have — an invoice, a transaction, "
            "an upcoming meeting, the contents of an uploaded document. "
            "Brain dispatches in real time to Gmail, Calendar, and uploaded "
            "docs in parallel and returns merged results in <2s. "
            "Examples: 'last invoice from Razorpay', 'next meeting with Rohit', "
            "'what does the pricing PDF say about enterprise tier'."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "sources": {
                    "type": "array",
                    "items": {"type": "string", "enum": ["gmail", "calendar", "docs"]},
                    "description": "Optional explicit sources; omit to auto-route.",
                },
                "limit_per_source": {"type": "integer", "default": 5},
            },
            "required": ["query"],
        },
    },
    {
        # ── Phase 5: recent activity stream ──
        "name": "genios_recent",
        "description": (
            "Recent brain activity: latest recommendations, lifecycle "
            "transitions, fresh insights. Use for 'what's new', 'last 24h', "
            "or as a daily catch-up call."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "days": {"type": "integer", "default": 1, "description": "Lookback window (default 1 day)"},
                "limit": {"type": "integer", "default": 10},
            },
        },
    },
]


async def call_tool(
    client: httpx.AsyncClient,
    name: str,
    arguments: dict[str, Any],
    bearer_token: str,
    agent_id: str,
) -> Any:
    """Dispatch an MCP tool call to the matching /v1 endpoint.

    `client` is a long-lived AsyncClient bound to the in-process ASGI
    transport (no socket, no external network). Caller owns its lifecycle.
    """
    headers = {"Authorization": f"Bearer {bearer_token}"}

    if name == "genios_search_contacts":
        params: dict[str, Any] = {}
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
        return await _get(client, "/v1/contacts", headers, params)

    if name == "genios_get_context":
        entity = (arguments.get("entity") or "").strip()
        if not entity:
            return {"error": "entity is required"}
        payload: dict[str, Any] = {"entity": entity, "agent_id": agent_id}
        situation = (arguments.get("situation") or "").strip()
        if situation:
            payload["situation"] = situation[:500]
        return await _post(client, "/v1/context", headers, payload)

    if name == "genios_list_segments":
        return await _get(client, "/v1/segments", headers)

    if name == "genios_get_segment_members":
        sid = arguments.get("segment_id")
        if not sid:
            return {"error": "segment_id is required"}
        return await _get(
            client,
            f"/v1/segment/{sid}/members",
            headers,
            {"limit": int(arguments.get("limit", 50))},
        )

    if name == "genios_org_info":
        return await _get(client, "/v1/org", headers)

    if name == "genios_sync_status":
        return await _get(client, "/v1/sync", headers)

    if name == "genios_list_insights":
        params = {}
        if arguments.get("status"):
            params["status"] = arguments["status"]
        if arguments.get("limit"):
            params["limit"] = int(arguments["limit"])
        return await _get(client, "/v1/insights", headers, params or None)

    if name == "genios_log_interaction":
        payload = {"entity": arguments["entity"], "summary": arguments["summary"], "agent_id": agent_id}
        for k in ("direction", "channel", "sentiment", "topics"):
            if arguments.get(k) is not None:
                payload[k] = arguments[k]
        return await _post(client, "/v1/interaction", headers, payload)

    if name == "genios_log_outcome":
        payload = {
            "context_id": arguments["context_id"],
            "outcome": arguments["outcome"],
            "agent_id": agent_id,
        }
        if arguments.get("details"):
            payload["details"] = arguments["details"]
        return await _post(client, "/v1/outcome", headers, payload)

    if name == "genios_trigger_scan":
        return await _post(client, "/v1/scan", headers, {})

    # ── Phase 5: genios_live_search — dispatcher direct call ──────────────
    if name == "genios_live_search":
        query = (arguments.get("query") or "").strip()
        if not query:
            return {"error": "query is required"}
        org_id = _resolve_org_id_from_bearer(bearer_token)
        if not org_id:
            return {"error": "auth_required"}
        sources = arguments.get("sources") or None
        limit_per = int(arguments.get("limit_per_source") or 5)
        try:
            from app.retrieval import live_dispatcher
            return live_dispatcher.dispatch(
                org_id, query,
                sources=sources, limit_per_source=limit_per,
            )
        except Exception as e:
            return {"error": "live_dispatch_failed", "detail": str(e)[:200]}

    # ── Phase 5: genios_recent — recent activity wrapper ──────────────────
    if name == "genios_recent":
        days = int(arguments.get("days", 1))
        limit = int(arguments.get("limit", 10))
        return await _get(
            client, "/v1/insights", headers,
            {"limit": limit, "recent_days": days},
        )

    return {"error": f"unknown tool: {name}"}


async def _get(client: httpx.AsyncClient, path: str, headers: dict, params: dict | None = None) -> Any:
    try:
        r = await client.get(path, headers=headers, params=params, timeout=15.0)
    except httpx.HTTPError as e:
        return {"error": "upstream_error", "detail": str(e)[:200]}
    if r.status_code >= 400:
        return {"error": f"HTTP {r.status_code}", "body": r.text[:500]}
    return _safe_json(r)


async def _post(client: httpx.AsyncClient, path: str, headers: dict, payload: dict) -> Any:
    try:
        r = await client.post(path, headers=headers, json=payload, timeout=20.0)
    except httpx.HTTPError as e:
        return {"error": "upstream_error", "detail": str(e)[:200]}
    if r.status_code >= 400:
        return {"error": f"HTTP {r.status_code}", "body": r.text[:500]}
    return _safe_json(r)


def _safe_json(r: httpx.Response) -> Any:
    try:
        return r.json()
    except ValueError:
        return {"error": "invalid_json_from_upstream", "body": r.text[:500]}


# ── Phase 4: Proactive push — pending_alerts piggyback ──────────────────────
# Every successful MCP tool response is wrapped with up to 3 pending_alerts
# from the brain. The MCP system prompt instructs Claude to surface them
# naturally as "btw, brain noticed...". This is THE proactive moment.

import hashlib as _hashlib  # local alias to avoid top-level reorg

_MAX_ALERTS_PER_RESPONSE = 3


def _resolve_org_id_from_bearer(bearer_token: str) -> str | None:
    """Hash + lookup. Mirrors verify_api_key in app/api/deps.py but doesn't
    raise — returns None on failure so MCP responses keep working."""
    if not bearer_token or not bearer_token.startswith("gn_live_"):
        return None
    try:
        from sqlalchemy import text as _text
        from app.database import SessionLocal
        hashed = _hashlib.sha256(bearer_token.encode()).hexdigest()
        db = SessionLocal()
        try:
            row = db.execute(
                _text("""
                    SELECT id FROM orgs
                    WHERE api_key = :raw OR api_key_hash = :h
                    LIMIT 1
                """),
                {"raw": bearer_token, "h": hashed},
            ).fetchone()
            if row:
                return str(row[0])
            row = db.execute(
                _text("""
                    SELECT org_id FROM api_keys
                    WHERE key_hash = :h AND is_active = TRUE
                    LIMIT 1
                """),
                {"h": hashed},
            ).fetchone()
            if row:
                return str(row[0])
        finally:
            db.close()
    except Exception:
        return None
    return None


def drain_pending_alerts(org_id: str, limit: int = _MAX_ALERTS_PER_RESPONSE) -> list:
    """Pop up to `limit` undelivered alerts for this org, mark delivered."""
    if not org_id:
        return []
    try:
        from sqlalchemy import text as _text
        from app.database import SessionLocal
        db = SessionLocal()
        try:
            rows = db.execute(
                _text("""
                    SELECT id, insight_type, contact_name, title, body,
                           suggested_action, priority, confidence
                    FROM pending_alerts
                    WHERE org_id = :oid
                      AND delivered = FALSE
                      AND (expires_at IS NULL OR expires_at > NOW())
                    ORDER BY priority DESC, created_at DESC
                    LIMIT :lim
                """),
                {"oid": org_id, "lim": int(limit)},
            ).fetchall()
            if not rows:
                return []
            ids = [str(r[0]) for r in rows]
            db.execute(
                _text("""
                    UPDATE pending_alerts
                    SET delivered = TRUE,
                        delivered_at = NOW(),
                        delivered_via = 'mcp'
                    WHERE id = ANY(CAST(:ids AS uuid[]))
                """),
                {"ids": ids},
            )
            db.commit()
            return [
                {
                    "id": str(r[0]),
                    "type": r[1],
                    "contact": r[2],
                    "title": r[3],
                    "body": r[4],
                    "suggested_action": r[5],
                    "priority": float(r[6] or 0.0),
                    "confidence": float(r[7] or 0.0),
                }
                for r in rows
            ]
        finally:
            db.close()
    except Exception:
        return []


def attach_pending_alerts(data: Any, bearer_token: str) -> Any:
    """Wrap a tool response with pending_alerts piggyback. Best-effort —
    on any failure, returns the original data unchanged."""
    if data is None or not isinstance(data, (dict, list)):
        return data
    try:
        org_id = _resolve_org_id_from_bearer(bearer_token)
        if not org_id:
            return data
        alerts = drain_pending_alerts(org_id)
        if not alerts:
            return data
        if isinstance(data, list):
            return {"result": data, "pending_alerts": alerts}
        out = dict(data)
        out["pending_alerts"] = alerts
        return out
    except Exception:
        return data
