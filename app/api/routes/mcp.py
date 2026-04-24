"""
MCP (Model Context Protocol) Streamable-HTTP endpoint.

Serves the MCP JSON-RPC protocol at POST /mcp so any remote MCP client
(Claude Web custom connectors, ChatGPT connectors, Cursor, Cline, ...) can
reach the Genios brain without running a local stdio process.

Deploys with the rest of the FastAPI app — no extra service, no extra port.
Protocol scope: initialize, notifications/initialized, tools/list,
tools/call, ping. Stateless, JSON responses only (no SSE streaming) — the
10 Genios tools are all synchronous, so streaming would add complexity
without benefit.

Auth: the client sends `Authorization: Bearer gn_live_*` on every request.
The token is validated against the same `orgs` table used by /v1/*, and
forwarded verbatim to the internal /v1/* dispatch so all plan gates, rate
limits, and org isolation keep working unchanged.
"""
from __future__ import annotations

import logging
import uuid
from typing import Any

import httpx
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.api.routes.mcp_oauth import resolve_oauth_token
from app.api.routes.mcp_tools import TOOLS, call_tool

logger = logging.getLogger(__name__)

router = APIRouter(tags=["mcp"])

PROTOCOL_VERSION = "2025-03-26"
SERVER_NAME = "genios"
SERVER_VERSION = "1.0.0"

# Lazy-built in-process HTTP client that loops back into this same FastAPI app
# via an ASGI transport — no socket, no external network hop.
_asgi_client: httpx.AsyncClient | None = None


def _get_asgi_client(request: Request) -> httpx.AsyncClient:
    global _asgi_client
    if _asgi_client is None:
        transport = httpx.ASGITransport(app=request.app)
        _asgi_client = httpx.AsyncClient(transport=transport, base_url="http://mcp.internal")
    return _asgi_client


# ── JSON-RPC helpers ─────────────────────────────────────────────────────────

def _rpc_result(req_id: Any, result: Any) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": req_id, "result": result}


def _rpc_error(req_id: Any, code: int, message: str, data: Any = None) -> dict[str, Any]:
    err: dict[str, Any] = {"code": code, "message": message}
    if data is not None:
        err["data"] = data
    return {"jsonrpc": "2.0", "id": req_id, "error": err}


def _extract_bearer(request: Request) -> str | None:
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        return auth[7:].strip() or None
    return None


def _resolve_bearer(bearer: str) -> str | None:
    """Return the underlying gn_live_* key for a bearer, or None if invalid.

    - Raw `gn_live_*` passes through unchanged (local stdio, CLI, curl).
    - Any other token is looked up as an OAuth access_token (Claude Web).
    """
    if bearer.startswith("gn_live_"):
        return bearer
    return resolve_oauth_token(bearer)


async def _dispatch(request: Request, body: dict[str, Any], bearer: str) -> dict[str, Any] | None:
    method = body.get("method")
    req_id = body.get("id")
    params = body.get("params") or {}

    # Notifications carry no id and expect no response.
    is_notification = "id" not in body

    if method == "initialize":
        return _rpc_result(
            req_id,
            {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
                "instructions": (
                    "You have access to genios_* tools — call them directly, they are always available. "
                    "NEVER fabricate, guess, or infer relationship data, contacts, insights, or priorities. "
                    "If any tool call fails or returns an error field, respond with: "
                    "'GeniOS data unavailable. Please try again.' and stop. "
                    "When the user asks for priorities, alerts, or relationship status: "
                    "call genios_list_insights first, then genios_org_info if needed. "
                    "Every insight or contact detail you present must come directly from a tool result."
                ),
            },
        )

    if method in ("notifications/initialized", "initialized"):
        return None  # ack-only

    if method == "ping":
        return _rpc_result(req_id, {})

    if method == "tools/list":
        return _rpc_result(req_id, {"tools": TOOLS})

    if method == "tools/call":
        name = params.get("name")
        arguments = params.get("arguments") or {}
        if not name:
            return _rpc_error(req_id, -32602, "Missing 'name' in tools/call params")

        agent_id = request.headers.get("x-genios-agent-id", "mcp")
        client = _get_asgi_client(request)
        try:
            data = await call_tool(client, name, arguments, bearer, agent_id)
        except Exception as exc:  # noqa: BLE001 — surface as JSON-RPC error
            logger.exception("mcp tool %s failed", name)
            return _rpc_error(req_id, -32000, f"Tool execution failed: {exc}")

        import json

        return _rpc_result(
            req_id,
            {
                "content": [{"type": "text", "text": json.dumps(data, indent=2, default=str)}],
                "isError": bool(isinstance(data, dict) and data.get("error")),
            },
        )

    if is_notification:
        return None
    return _rpc_error(req_id, -32601, f"Method not found: {method}")


# ── HTTP surface ─────────────────────────────────────────────────────────────

@router.post("/mcp")
async def mcp_post(request: Request):
    raw_bearer = _extract_bearer(request)
    bearer = _resolve_bearer(raw_bearer) if raw_bearer else None
    if not bearer:
        # Advertise both auth schemes so Claude Web triggers OAuth discovery
        # while CLI/stdio clients can still paste a gn_live_* key directly.
        resource = _issuer_url(request)
        return JSONResponse(
            status_code=401,
            content={
                "jsonrpc": "2.0",
                "id": None,
                "error": {
                    "code": -32001,
                    "message": "Missing or invalid credential. Send 'Authorization: Bearer <gn_live_* or OAuth access_token>'.",
                },
            },
            headers={
                "WWW-Authenticate": (
                    f'Bearer realm="genios-mcp", '
                    f'resource_metadata="{resource}/.well-known/oauth-protected-resource"'
                ),
            },
        )

    try:
        body = await request.json()
    except Exception:
        return JSONResponse(
            status_code=400,
            content=_rpc_error(None, -32700, "Parse error: body is not valid JSON"),
        )

    # Batch support — a JSON array of requests.
    if isinstance(body, list):
        responses: list[dict[str, Any]] = []
        for item in body:
            if not isinstance(item, dict):
                responses.append(_rpc_error(None, -32600, "Invalid Request"))
                continue
            resp = await _dispatch(request, item, bearer)
            if resp is not None:
                responses.append(resp)
        if not responses:
            return JSONResponse(status_code=202, content=None)
        return JSONResponse(content=responses, headers=_session_headers(request))

    if not isinstance(body, dict):
        return JSONResponse(status_code=400, content=_rpc_error(None, -32600, "Invalid Request"))

    resp = await _dispatch(request, body, bearer)
    if resp is None:
        return JSONResponse(status_code=202, content=None, headers=_session_headers(request))
    return JSONResponse(content=resp, headers=_session_headers(request))


@router.get("/mcp")
async def mcp_get(request: Request):
    """Streamable-HTTP GET is used by clients to open a server-push SSE channel.

    We are stateless and don't push unsolicited messages, so we reject it —
    clients will fall back to POST-only operation.
    """
    return JSONResponse(
        status_code=405,
        content={"error": "Server-initiated streams not supported; use POST /mcp"},
        headers={"Allow": "POST, DELETE"},
    )


@router.delete("/mcp")
async def mcp_delete(request: Request):
    """Session teardown — stateless server, so this is a no-op."""
    return JSONResponse(status_code=204, content=None)


@router.get("/mcp/health")
async def mcp_health():
    return {"status": "ok", "name": SERVER_NAME, "version": SERVER_VERSION, "protocol": PROTOCOL_VERSION}


def _issuer_url(request: Request) -> str:
    proto = request.headers.get("x-forwarded-proto", request.url.scheme)
    host = request.headers.get("x-forwarded-host") or request.headers.get("host") or request.url.hostname
    return f"{proto}://{host}"


def _session_headers(request: Request) -> dict[str, str]:
    # Echo the client-supplied session id if present; otherwise mint one so
    # well-behaved clients have something to cache. Stateless — we don't
    # retain it.
    sid = request.headers.get("mcp-session-id") or uuid.uuid4().hex
    return {"Mcp-Session-Id": sid}
