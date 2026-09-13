"""GeniOS MCP server — SCREEN_INTEL_P6_BUILD.md §3.6 (frozen).

    POST /mcp     stateless Streamable-HTTP, JSON-RPC 2.0, JSON responses (never SSE)
    GET  /mcp     405 (no server-initiated stream)      DELETE /mcp  405 (no sessions)

Protocol `2025-06-18` (2025-03-26 accepted). One request per POST — batches were removed from the
protocol in 2025-06-18 and are refused. Notifications and client responses answer 202 with no body.
No new dependency: JSON-RPC over FastAPI, nothing else.

AUTH. Either an agent `gn_live_` key carrying `mcp.read` — which reads AS the seat it is bound to
(`agent_registry.seat_id`, migration 0158; an unbound key answers SEAT_REQUIRED on seat tools) — or
a seat session / device token (`api/moment_routes.principal`). Org-level keys with no agent are
refused: a key with no person behind it has no seat to read as.

SEAT-VISIBLE ONLY. Every tool reads as the seat: facts through P2 `context/fact_visibility`
(`VISIBLE_FACT_SQL` + `viewer_may_read`, the seat's own overlay winning its field), observations
through the private-evidence rule, moments = the seat's own history, cards = the seat's reach,
availability = org-visible windows only (who + when, never why).

Tools: get_context · list_moments · list_cards · get_team_availability · propose_action.
`search_graph` is NOT offered: no seat-filtered graph search exists in the engine (the query
assistant's retrieval is an LLM path and credit-charged), and an unfiltered one would leak other
seats' private facts.

NEVER CREDIT-CHARGED. `propose_action` only creates a `proposed` delegation (group A); nothing is
sent to any provider from here.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import Any, Callable

from fastapi import APIRouter, Request, Response
from fastapi.responses import JSONResponse
from sqlalchemy import text
from starlette.concurrency import run_in_threadpool

from genios_engine.api.device_routes import _bearer, _err
from genios_engine.context import fact_visibility as FV
from genios_engine.platform.auth import ROLE_MEMBER, check_org_kill, seat_role, verify_bearer
from genios_engine.platform.logging import get_logger

router = APIRouter(tags=["mcp"])
_log = get_logger("genios.mcp")

PROTOCOL_VERSION = "2025-06-18"
SUPPORTED_VERSIONS = ("2025-06-18", "2025-03-26")
MCP_SCOPE = "mcp.read"
SERVER_INFO = {"name": "genios", "title": "GeniOS", "version": "1.0.0"}
INSTRUCTIONS = ("GeniOS is the company's context layer. Every tool answers as the seat this "
                "credential is bound to: only what that person may see. propose_action creates a "
                "proposal a named human must approve; it never executes anything.")

PARSE_ERROR = -32700
INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
INVALID_PARAMS = -32602
INTERNAL_ERROR = -32603
SEAT_REQUIRED = -32001           # data.code = "SEAT_REQUIRED"
NOT_AVAILABLE = -32002           # data.code = "NOT_AVAILABLE"

DEFAULT_AWAY_DAYS = 14
MAX_AWAY_DAYS = 180


@dataclass(frozen=True)
class Caller:
    org_id: str
    seat_id: str | None           # None = an unbound agent key
    email: str | None
    role: str | None              # owner | admin | member (the seat's), None when unbound
    agent_id: str | None          # None = a seat session / device

    @property
    def viewer(self) -> str | None:
        v = str(self.email or "").strip().lower()
        return v or None

    @property
    def sees_org_queue(self) -> bool:
        return self.seat_id is not None and self.role not in (None, ROLE_MEMBER)


class RpcError(Exception):
    def __init__(self, code: int, message: str, data: dict | None = None):
        super().__init__(message)
        self.code, self.message, self.data = code, message, data


class ToolError(Exception):
    """A tool ran and could not answer (bad input it can explain, unknown moment…): returned as a
    tool result with isError=true, which the calling model can read and correct."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code, self.message = code, message


# ── wiring ────────────────────────────────────────────────────────────────────────────────────
def _engine():
    from genios_engine.platform import devices as D
    return D.stores()[1].engine


class _EngineStore:
    """`deliver/agent_api` reads take a store with `.engine`."""

    def __init__(self, engine):
        self.engine = engine


def _proposer() -> Callable[..., dict] | None:
    """Group A's proposal function (P6 §3.3 semantics), imported lazily so this module has no
    hard dependency on it. Contract: `create_proposal(engine, *, org_id, seat_id, seat_email,
    moment_id, card_id, play, params, agent_id, via) -> {delegation_id, state, instruction,
    agent_id}`; raises ValueError (invalid play/params → nothing written) or LookupError (no such
    moment/card for the seat)."""
    try:
        from genios_engine.executive import delegation as DL
    except ImportError:
        return None
    return getattr(DL, "create_proposal", None)


# ── auth ──────────────────────────────────────────────────────────────────────────────────────
def _unauthorized(code: str, message: str) -> JSONResponse:
    resp = _err(401, code, message)
    resp.headers["WWW-Authenticate"] = 'Bearer realm="genios-mcp"'
    return resp


def _agent_caller(request: Request, token: str):
    ctx = verify_bearer(token)                     # 401 / 403 HTTPExceptions propagate
    if not ctx.agent_id:
        return _err(403, "AGENT_KEY_REQUIRED",
                    "MCP takes an agent key or a signed-in seat; this key belongs to no agent.")
    if MCP_SCOPE not in (ctx.scopes or []):
        return _err(403, "SCOPE_REQUIRED", f"This agent key lacks the '{MCP_SCOPE}' scope.")
    check_org_kill(ctx.org_id)
    with _engine().connect() as c:
        r = c.execute(text(
            "select coalesce(r.status, 'active') as status, r.seat_id, s.email, s.role, s.active, "
            "o.email as org_email from agent_registry r join orgs o on o.id = r.org_id "
            "left join org_seats s on s.org_id = r.org_id and s.seat_id = r.seat_id "
            "where r.org_id = :o and r.agent_id = :a"),
            {"o": ctx.org_id, "a": ctx.agent_id}).first()
    if r is None or r.status == "archived":
        return _unauthorized("AGENT_REVOKED", "This agent is not registered or was archived.")
    request.state.org_id = ctx.org_id
    request.state.agent_id = ctx.agent_id
    if r.seat_id and r.active:
        return Caller(ctx.org_id, r.seat_id, r.email, seat_role(r.email, r.role, r.org_email),
                      ctx.agent_id)
    return Caller(ctx.org_id, None, None, None, ctx.agent_id)


def _authenticate(request: Request):
    """A Caller, or the JSONResponse refusing the credential."""
    token = _bearer(request)
    if not token:
        return _unauthorized("AUTH_REQUIRED", "A bearer credential is required.")
    if token.startswith("gn_"):
        return _agent_caller(request, token)
    from genios_engine.api.moment_routes import principal
    from genios_engine.platform import devices as D
    dstore, cstore = D.stores()
    p = principal(request, dstore)
    if isinstance(p, JSONResponse):
        return p
    with cstore.engine.connect() as c:
        r = c.execute(text(
            "select s.role, o.email as org_email from orgs o left join org_seats s "
            "on s.org_id = o.id and s.seat_id = :s where o.id = :o"),
            {"o": p.org_id, "s": p.seat_id}).first()
    role = seat_role(p.email, r.role if r else None, r.org_email if r else None)
    return Caller(p.org_id, p.seat_id, p.email, role, None)


# ── argument helpers ──────────────────────────────────────────────────────────────────────────
def _bad(message: str) -> RpcError:
    return RpcError(INVALID_PARAMS, message)


def _opt_str(args: dict, key: str, *, max_len: int = 500) -> str | None:
    v = args.get(key)
    if v is None:
        return None
    if not isinstance(v, str) or len(v) > max_len:
        raise _bad(f"'{key}' must be a string of at most {max_len} characters.")
    return v.strip() or None


def _opt_int(args: dict, key: str, default: int, lo: int, hi: int) -> int:
    v = args.get(key, default)
    if isinstance(v, bool) or not isinstance(v, int) or not lo <= v <= hi:
        raise _bad(f"'{key}' must be an integer between {lo} and {hi}.")
    return v


def _opt_date(args: dict, key: str) -> date | None:
    v = _opt_str(args, key, max_len=40)
    if v is None:
        return None
    try:
        return date.fromisoformat(v[:10])
    except ValueError:
        raise _bad(f"'{key}' must be a date (YYYY-MM-DD).") from None


def _plain(data: Any) -> Any:
    """JSON-safe (datetimes, Decimals → strings/numbers) — structuredContent must serialize."""
    return json.loads(json.dumps(data, default=str))


# ── tools ─────────────────────────────────────────────────────────────────────────────────────
_ENTITY_TYPES = {"person": "person_360", "company": "company_360", "deal": "deal_360",
                 "meeting": "meeting_360"}


def _resolve_entity(c, org_id: str, entity: str) -> list:
    """Live nodes an agent's `entity` names: a node id, else an email / LinkedIn / person-name
    alias, else an exact display name. At most 5."""
    from genios_engine.platform.identity import norm_email, norm_linkedin_url, person_name_key
    live = ("select node_id, node_type, display_name from graph_nodes where org_id = :o "
            "and valid_to is null ")
    rows = c.execute(text(live + "and node_id = :e limit 1"), {"o": org_id, "e": entity}).all()
    if rows:
        return rows
    keys = [(t, k) for t, k in (("email", norm_email(entity)),
                                ("linkedin_url", norm_linkedin_url(entity)),
                                ("person_name", person_name_key(entity))) if k]
    ids: list[str] = []
    if keys:
        ids = [r.node_id for r in c.execute(text(
            "select distinct node_id from graph_aliases where org_id = :o "
            "and alias_type = any(:t) and alias_key = any(:k) limit 5"),
            {"o": org_id, "t": sorted({t for t, _ in keys}), "k": sorted({k for _, k in keys})})]
    if ids:
        return c.execute(text(live + "and node_id = any(:ids) order by node_id limit 5"),
                         {"o": org_id, "ids": ids}).all()
    return c.execute(text(live + "and lower(display_name) = lower(:e) order by node_id limit 5"),
                     {"o": org_id, "e": entity}).all()


def _read_entity(c, org_id: str, node, viewer: str | None) -> dict | None:
    """The entity 360 as THIS seat may read it: org facts, plus the seat's own private overlay
    (which wins its field — P2 §3.4), never another seat's. Observations whose evidence is another
    seat's private event are dropped. None when nothing is readable (then the entity is unknown to
    this seat, exactly as the P3 recall treats it)."""
    from genios_engine.reason.moments.common import VISIBLE_EVENT_SQL, VISIBLE_FACT_SQL, value_of
    params = {"o": org_id, "n": node.node_id, "viewer": viewer}
    pg = c.dialect.name == "postgresql"
    cols = ("f.field, f.value, f.confidence, f.authority_rank, f.occurred_at"
            + (", f.visibility_scope, f.visibility_principals" if pg else ""))
    facts: dict[str, dict] = {}
    for r in c.execute(text(
            f"select {cols} from graph_facts f where f.org_id = :o and f.subject_node_id = :n "
            "and f.valid_to is null and f.status = 'active'"
            + (" and " + VISIBLE_FACT_SQL if pg else "") + " order by f.field"), params):
        scope = getattr(r, "visibility_scope", None)
        principals = getattr(r, "visibility_principals", None)
        if not FV.viewer_may_read(scope, principals, viewer):      # belt and braces over the SQL
            continue
        private = scope == FV.PRIVATE
        if r.field in facts and not private:
            continue                       # the seat's own overlay wins its field
        facts[r.field] = {"value": value_of(r.value), "confidence": float(r.confidence),
                          "authority": r.authority_rank,
                          "occurred_at": r.occurred_at.isoformat() if r.occurred_at else None,
                          "private": private}
    obs_sql = ("select o.kind, o.occurred_at from graph_observations o "
               + ("left join source_events se on se.org_id = o.org_id "
                  "and se.event_id = o.created_by_event_id " if pg else "")
               + "where o.org_id = :o and o.subject_node_id = :n and o.status = 'active'"
               + (" and " + VISIBLE_EVENT_SQL if pg else "")
               + " order by o.occurred_at desc limit 20")
    observations = [{"kind": r.kind, "at": r.occurred_at.isoformat() if r.occurred_at else None}
                    for r in c.execute(text(obs_sql), params)]
    if not facts and not observations:
        return None
    return {"node_id": node.node_id, "node_type": node.node_type,
            "display_name": node.display_name,
            "model_type": _ENTITY_TYPES.get(node.node_type, "entity_360"),
            "facts": facts, "observations": observations}


def tool_get_context(caller: Caller, args: dict) -> dict:
    entity = _opt_str(args, "entity")
    if not entity:
        raise _bad("'entity' is required: a node id, an email, a LinkedIn URL or a name.")
    with _engine().connect() as c:
        readable = [e for e in (_read_entity(c, caller.org_id, n, caller.viewer)
                                for n in _resolve_entity(c, caller.org_id, entity)) if e]
    if not readable:
        return {"found": False, "entity": entity}
    if len(readable) > 1:
        return {"found": False, "ambiguous": True, "entity": entity,
                "candidates": [{k: e[k] for k in ("node_id", "node_type", "display_name")}
                               for e in readable]}
    return {"found": True, "entity": readable[0]}


def tool_list_moments(caller: Caller, args: dict) -> dict:
    from genios_engine.contracts.moments import KINDS
    from genios_engine.reason.moments import store as M
    limit = _opt_int(args, "limit", 20, 1, 200)
    kind = _opt_str(args, "kind", max_len=60)
    if kind is not None and kind not in KINDS:
        raise _bad(f"'kind' must be one of {', '.join(KINDS)}.")
    before_raw = _opt_str(args, "before", max_len=60)
    before = None
    if before_raw:
        try:
            before = datetime.fromisoformat(before_raw.replace("Z", "+00:00"))
        except ValueError:
            raise _bad("'before' must be an ISO-8601 timestamp.") from None
        before = before if before.tzinfo else before.replace(tzinfo=timezone.utc)
    return M.history(_engine(), org_id=caller.org_id, seat_id=caller.seat_id, limit=limit,
                     before=before, kind=kind)


_CARD_COLUMNS = ("signal_id", "card_id", "urgency_band", "headline", "situation", "score",
                 "state", "created_at")


def _session_cards(engine, org_id: str) -> list[dict]:
    """The live authoritative queue (the same rows `agent_api.poll_signals` reads) for a caller
    with no agent identity. The seat filter is applied by the caller."""
    from genios_engine.reason.authority import (AUTHORITATIVE_SCORE_SQL,
                                                AUTHORITATIVE_SIGNAL_JOINS,
                                                AUTHORITATIVE_SIGNAL_PREDICATE)
    with engine.connect() as c:
        return [dict(r) for r in c.execute(text(
            "select k.signal_id, k.card_id, k.urgency_band, k.headline, k.situation, "
            + AUTHORITATIVE_SCORE_SQL + " as score, k.state, k.created_at from cards k "
            "join signals s on s.signal_id=k.signal_id and s.org_id=k.org_id "
            + AUTHORITATIVE_SIGNAL_JOINS +
            " where k.org_id=:o and k.state in ('queued','surfaced','snoozed') "
            "and k.expires_at > :authority_time and s.status='open' and "
            + AUTHORITATIVE_SIGNAL_PREDICATE +
            " order by selected_rc.final_utility_bp desc, k.card_id"),
            {"o": org_id, "authority_time": datetime.now(timezone.utc)}).mappings()]


def tool_list_cards(caller: Caller, args: dict) -> dict:
    """The open cards the seat reaches. An agent key goes through `agent_api.poll_signals` (its
    stored data scope enforced, the read metered as every agent read is — metering is not a credit
    charge); a member seat is then narrowed to its reach (assignment + declared responsibility,
    `deliver/seat_access`); an owner / admin seat keeps the org queue, as on the dashboard."""
    from genios_engine.deliver.seat_access import SEAT_REACH_SQL
    limit = _opt_int(args, "limit", 50, 1, 200)
    engine = _engine()
    if caller.agent_id:
        from genios_engine.deliver.agent_api import poll_signals
        rows = poll_signals(_EngineStore(engine), caller.org_id, caller.agent_id)
    else:
        rows = _session_cards(engine, caller.org_id)
    if rows and not caller.sees_org_queue:
        with engine.connect() as c:
            reach = {r.card_id for r in c.execute(text(
                "select k.card_id from cards k where k.org_id = :o and k.card_id = any(:ids) "
                "and " + SEAT_REACH_SQL),
                {"o": caller.org_id, "ids": [r["card_id"] for r in rows], "seat": caller.seat_id})}
        rows = [r for r in rows if r["card_id"] in reach]
    return {"cards": [{k: r.get(k) for k in _CARD_COLUMNS} for r in rows[:limit]],
            "has_more": len(rows) > limit}


def tool_get_team_availability(caller: Caller, args: dict) -> list | dict:
    from genios_engine.reason.team.away import team_away
    start = _opt_date(args, "from") or datetime.now(timezone.utc).date()
    end = _opt_date(args, "to") or start + timedelta(days=DEFAULT_AWAY_DAYS)
    if end < start:
        raise _bad("'to' must not be before 'from'.")
    if (end - start).days > MAX_AWAY_DAYS:
        raise _bad(f"At most {MAX_AWAY_DAYS} days per request.")
    with _engine().connect() as c:
        return {"away": team_away(c, caller.org_id, start=start, end=end),
                "from": start.isoformat(), "to": end.isoformat()}


def tool_propose_action(caller: Caller, args: dict) -> dict:
    moment_id = _opt_str(args, "moment_id", max_len=200)
    card_id = _opt_str(args, "card_id", max_len=200)
    if (moment_id is None) == (card_id is None):
        raise _bad("Give exactly one of 'moment_id' or 'card_id'.")
    play = _opt_str(args, "play", max_len=100)
    if not play:
        raise _bad("'play' is required.")
    params = args.get("params")
    if not isinstance(params, dict):
        raise _bad("'params' must be an object.")
    agent_id = _opt_str(args, "agent_id", max_len=200)
    fn = _proposer()
    if fn is None:
        raise RpcError(NOT_AVAILABLE, "Agent proposals are not available on this deployment yet.",
                       {"code": "NOT_AVAILABLE"})
    try:
        out = fn(_engine(), org_id=caller.org_id, seat_id=caller.seat_id,
                 seat_email=caller.email, moment_id=moment_id, card_id=card_id, play=play,
                 params=params, agent_id=agent_id, via="mcp")
    except LookupError as e:
        raise ToolError("NOT_FOUND", str(e) or "No such moment or card for this seat.") from None
    except ValueError as e:
        raise ToolError(getattr(e, "code", None) or "INVALID_PROPOSAL", str(e)) from None
    return dict(out or {})


@dataclass(frozen=True)
class Tool:
    name: str
    title: str
    description: str
    input_schema: dict
    fn: Callable[[Caller, dict], Any]
    seat: bool = True                        # needs a seat (SEAT_REQUIRED when unbound)
    read_only: bool = True
    extra: dict = field(default_factory=dict)

    def spec(self) -> dict:
        return {"name": self.name, "title": self.title, "description": self.description,
                "inputSchema": self.input_schema,
                "annotations": {"readOnlyHint": self.read_only, "openWorldHint": False}}


def _schema(props: dict, required: tuple[str, ...] = ()) -> dict:
    out = {"type": "object", "properties": props, "additionalProperties": False}
    if required:
        out["required"] = list(required)
    return out


TOOLS: dict[str, Tool] = {t.name: t for t in (
    Tool("get_context", "Entity context",
         "What the company knows about one person, company, deal or meeting — facts and recent "
         "activity — as this seat may see it.",
         _schema({"entity": {"type": "string", "description":
                             "A node id, an email address, a LinkedIn URL or an exact name."}},
                 ("entity",)), tool_get_context),
    Tool("list_moments", "Recent moments",
         "This seat's recent moments (the in-context nudges GeniOS showed), newest first, with "
         "the last feedback on each.",
         _schema({"limit": {"type": "integer", "minimum": 1, "maximum": 200, "default": 20},
                  "kind": {"type": "string"},
                  "before": {"type": "string", "format": "date-time"}}), tool_list_moments),
    Tool("list_cards", "Open cards",
         "The open decision cards routed to this seat, highest priority first.",
         _schema({"limit": {"type": "integer", "minimum": 1, "maximum": 200, "default": 50}}),
         tool_list_cards),
    Tool("get_team_availability", "Team availability",
         "Teammates who are away between two dates — who and when, never why.",
         _schema({"from": {"type": "string", "format": "date"},
                  "to": {"type": "string", "format": "date"}}),
         tool_get_team_availability, seat=False),
    Tool("propose_action", "Propose an action",
         "Propose one typed action (a play) for a moment or card. Creates a PROPOSAL only: a "
         "named human must approve it before the client's own agent executes anything.",
         {"type": "object", "additionalProperties": False,
          "properties": {"moment_id": {"type": "string"}, "card_id": {"type": "string"},
                         "play": {"type": "string", "enum": ["email.reschedule", "task.reassign",
                                                             "email.follow_up_draft"]},
                         "params": {"type": "object"}, "agent_id": {"type": "string"}},
          "required": ["play", "params"],
          "oneOf": [{"required": ["moment_id"]}, {"required": ["card_id"]}]},
         tool_propose_action, read_only=False),
)}


# ── JSON-RPC ──────────────────────────────────────────────────────────────────────────────────
def _rpc_result(rid, result) -> JSONResponse:
    return JSONResponse({"jsonrpc": "2.0", "id": rid, "result": result})


def _rpc_error(rid, code: int, message: str, data: dict | None = None, *,
               status: int = 200) -> JSONResponse:
    err = {"code": code, "message": message}
    if data is not None:
        err["data"] = data
    return JSONResponse({"jsonrpc": "2.0", "id": rid, "error": err}, status_code=status)


def _tool_result(data: Any, *, is_error: bool = False) -> dict:
    plain = _plain(data)
    structured = plain if isinstance(plain, dict) else {"items": plain}
    return {"content": [{"type": "text", "text": json.dumps(plain)}],
            "structuredContent": structured, "isError": is_error}


def _audit(caller: Caller, tool: str, result: str) -> None:
    """One agent_events row per agent tool call — the Agents page's call count and audit."""
    if not caller.agent_id:
        return
    from genios_engine.platform.ids import new_id
    try:
        eid = new_id("aev")
        with _engine().begin() as c:
            c.execute(text(
                "insert into agent_events (id, org_id, agent_id, client_event_id, action_taken, "
                "target_hint, result, occurred_at) values (:i, :o, :a, :i, :act, "
                "cast(:th as jsonb), :r, now())"),
                {"i": eid, "o": caller.org_id, "a": caller.agent_id, "act": f"mcp.{tool}",
                 "th": json.dumps({"entity": f"mcp.{tool}"}), "r": result})
    except Exception:      # noqa: BLE001 — auditing never fails the read
        _log.warning("mcp audit write failed org=%s agent=%s", caller.org_id, caller.agent_id)


def _call_tool(caller: Caller, params: dict) -> dict:
    name = params.get("name")
    tool = TOOLS.get(name) if isinstance(name, str) else None
    if tool is None:
        raise RpcError(INVALID_PARAMS, f"Unknown tool: {name}")
    args = params.get("arguments")
    args = {} if args is None else args
    if not isinstance(args, dict):
        raise RpcError(INVALID_PARAMS, "'arguments' must be an object.")
    if tool.seat and not caller.seat_id:
        _audit(caller, tool.name, "blocked")
        raise RpcError(SEAT_REQUIRED, "This credential is not bound to a seat. An owner binds the "
                                      "agent to a seat in Agents → Seat.", {"code": "SEAT_REQUIRED"})
    try:
        data = tool.fn(caller, args)
    except ToolError as e:
        _audit(caller, tool.name, "error")
        return _tool_result({"error": {"code": e.code, "message": e.message}}, is_error=True)
    _audit(caller, tool.name, "ok")
    return _tool_result(data)


def _dispatch(caller: Caller, method: str, params: dict):
    if method == "initialize":
        asked = params.get("protocolVersion")
        version = asked if asked in SUPPORTED_VERSIONS else PROTOCOL_VERSION
        return {"protocolVersion": version, "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": SERVER_INFO, "instructions": INSTRUCTIONS}
    if method == "ping":
        return {}
    if method == "tools/list":
        return {"tools": [t.spec() for t in TOOLS.values()]}
    if method == "tools/call":
        return _call_tool(caller, params)
    raise RpcError(METHOD_NOT_FOUND, f"Method not found: {method}")


def _handle(request: Request, raw: bytes, version: str | None):
    caller = _authenticate(request)
    if isinstance(caller, JSONResponse):
        return caller
    if version and version not in SUPPORTED_VERSIONS:
        return _rpc_error(None, INVALID_REQUEST, f"Unsupported MCP-Protocol-Version: {version}",
                          status=400)
    try:
        msg = json.loads(raw)
    except (ValueError, UnicodeDecodeError):
        return _rpc_error(None, PARSE_ERROR, "Parse error", status=400)
    if isinstance(msg, list):
        return _rpc_error(None, INVALID_REQUEST, "JSON-RPC batches are not supported.", status=400)
    if not isinstance(msg, dict) or msg.get("jsonrpc") != "2.0":
        return _rpc_error(None, INVALID_REQUEST, "Not a JSON-RPC 2.0 message.", status=400)
    if "method" not in msg or "id" not in msg:
        return Response(status_code=202)          # a notification or a client response
    rid, method = msg.get("id"), msg.get("method")
    if isinstance(rid, bool) or not isinstance(rid, (str, int)) or not isinstance(method, str):
        return _rpc_error(None, INVALID_REQUEST, "Invalid request id or method.", status=400)
    params = msg.get("params")
    params = {} if params is None else params
    if not isinstance(params, dict):
        return _rpc_error(rid, INVALID_PARAMS, "'params' must be an object.")
    try:
        return _rpc_result(rid, _dispatch(caller, method, params))
    except RpcError as e:
        return _rpc_error(rid, e.code, e.message, e.data)
    except Exception:      # noqa: BLE001 — a tool bug is an error response, never a 500 page
        _log.exception("mcp %s failed org=%s", method, caller.org_id)
        return _rpc_error(rid, INTERNAL_ERROR, "Internal error")


@router.post("/mcp")
async def mcp_post(request: Request):
    raw = await request.body()
    return await run_in_threadpool(_handle, request, raw,
                                   request.headers.get("mcp-protocol-version"))


@router.get("/mcp")
@router.delete("/mcp")
def mcp_not_allowed():
    """Stateless server: no server-initiated SSE stream (GET) and no session to end (DELETE)."""
    return Response(status_code=405, headers={"Allow": "POST"})


__all__ = ["Caller", "PROTOCOL_VERSION", "TOOLS", "router"]
