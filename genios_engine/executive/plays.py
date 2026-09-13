"""The typed plays a client's agent may be asked to run — SCREEN_INTEL_P6_BUILD §3.2 (frozen).

GeniOS never writes to a provider. A play is the exact, typed request a named human approves and
the CLIENT'S OWN agent executes (§1). This module owns the three things that make a play safe to
hand over:

  * the schemas (`additionalProperties:false` everywhere) and a STRICT validator — invalid params
    are a 422 that writes nothing. `jsonschema` is a dev-only dependency (pyproject), so production
    always runs the built-in check below; when `jsonschema` is importable it runs as well and its
    errors are added, never substituted;
  * agent selection — an ACTIVE agent with a webhook whose `allowed_actions` names the play,
    `is_default` first, then by id;
  * the words — the human-readable instruction, and the frozen §3.1 request document whose bytes
    the approval pins. Evidence travels only through P2 fact visibility (`context/fact_visibility`):
    a private fact reaches an agent only when every principal it serves may read it.

No LLM, no connector client, never credit-charged.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable

from sqlalchemy import text

PLAY_RESCHEDULE = "email.reschedule"
PLAY_REASSIGN = "task.reassign"
PLAY_FOLLOW_UP = "email.follow_up_draft"

_DT = {"type": "string", "format": "date-time"}
_EMAIL = {"type": "string", "format": "email"}
_ID = {"type": "string", "minLength": 1, "maxLength": 512}

SCHEMAS: dict[str, dict] = {
    PLAY_RESCHEDULE: {
        "type": "object", "additionalProperties": False,
        "required": ["meeting_ref", "attendees", "current_start", "proposed_windows",
                     "message_draft", "timezone"],
        "properties": {
            "meeting_ref": {
                "type": "object", "additionalProperties": False,
                "required": ["provider", "event_id"],
                "properties": {"provider": {"type": "string", "enum": ["google", "microsoft"]},
                               "event_id": _ID, "calendar_id": _ID}},
            "attendees": {"type": "array", "items": _EMAIL, "maxItems": 100},
            "current_start": _DT,
            "proposed_windows": {
                "type": "array", "minItems": 1, "maxItems": 3,
                "items": {"type": "object", "additionalProperties": False,
                          "required": ["start", "end"],
                          "properties": {"start": _DT, "end": _DT}}},
            "message_draft": {"type": "string", "minLength": 1, "maxLength": 4000},
            "timezone": {"type": "string", "minLength": 1, "maxLength": 64},
        }},
    PLAY_REASSIGN: {
        "type": "object", "additionalProperties": False,
        "required": ["task_ref", "from_seat_email", "to_seat_email", "note"],
        "properties": {
            "task_ref": {"type": "object", "additionalProperties": False,
                         "required": ["provider", "id"],
                         "properties": {"provider": {"type": "string", "minLength": 1,
                                                     "maxLength": 64},
                                        "id": _ID}},
            "from_seat_email": _EMAIL,
            "to_seat_email": _EMAIL,
            "note": {"type": "string", "maxLength": 2000},
        }},
    PLAY_FOLLOW_UP: {
        "type": "object", "additionalProperties": False,
        "required": ["thread_ref", "to", "subject", "body_draft", "send"],
        "properties": {
            "thread_ref": {"type": "object", "additionalProperties": False,
                           "required": ["provider", "thread_id"],
                           "properties": {"provider": {"type": "string",
                                                       "enum": ["gmail", "outlook"]},
                                          "thread_id": _ID}},
            "to": {"type": "array", "minItems": 1, "maxItems": 50, "items": _EMAIL},
            "subject": {"type": "string", "maxLength": 300},
            "body_draft": {"type": "string", "minLength": 1, "maxLength": 10000},
            "send": {"type": "boolean", "const": False},
        }},
}
PLAYS = frozenset(SCHEMAS)

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_TYPES = {"object": dict, "array": list, "string": str, "boolean": bool}


def _parse_dt(value: Any) -> datetime | None:
    if not isinstance(value, str) or "T" not in value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt if dt.tzinfo is not None else None       # an offset is required (RFC 3339)


def _check(schema: dict, value: Any, path: str, errors: list[str]) -> None:
    want = schema.get("type")
    if want is not None:
        py = _TYPES[want]
        # bool is an int subclass and int is never a string/object — but `True` must not pass as
        # anything but a boolean, and nothing else may pass as one.
        if not isinstance(value, py) or (want != "boolean" and isinstance(value, bool)):
            errors.append(f"{path or '$'}: expected {want}")
            return
    if "const" in schema and not (type(value) is type(schema["const"])
                                  and value == schema["const"]):
        errors.append(f"{path or '$'}: must be {json.dumps(schema['const'])}")
    if "enum" in schema and value not in schema["enum"]:
        errors.append(f"{path or '$'}: must be one of {schema['enum']}")
    if isinstance(value, str):
        if len(value.strip()) < schema.get("minLength", 0):
            errors.append(f"{path}: too short")
        if "maxLength" in schema and len(value) > schema["maxLength"]:
            errors.append(f"{path}: too long (max {schema['maxLength']})")
        fmt = schema.get("format")
        if fmt == "date-time" and _parse_dt(value) is None:
            errors.append(f"{path}: not an RFC 3339 date-time with offset")
        if fmt == "email" and not _EMAIL_RE.match(value):
            errors.append(f"{path}: not an email address")
    if isinstance(value, list):
        if len(value) < schema.get("minItems", 0):
            errors.append(f"{path}: needs at least {schema['minItems']} item(s)")
        if "maxItems" in schema and len(value) > schema["maxItems"]:
            errors.append(f"{path}: at most {schema['maxItems']} item(s)")
        for i, item in enumerate(value):
            _check(schema.get("items") or {}, item, f"{path}[{i}]", errors)
    if isinstance(value, dict):
        props = schema.get("properties") or {}
        for key in schema.get("required") or ():
            if key not in value:
                errors.append(f"{path + '.' if path else ''}{key}: required")
        for key, item in value.items():
            where = f"{path + '.' if path else ''}{key}"
            if key in props:
                _check(props[key], item, where, errors)
            elif schema.get("additionalProperties") is False:
                errors.append(f"{where}: unknown field")


def _jsonschema_errors(schema: dict, params: Any) -> list[str]:
    try:
        import jsonschema          # dev-only dependency; production runs the built-in check alone
    except Exception:              # noqa: BLE001
        return []
    validator = jsonschema.Draft202012Validator(schema)
    return [f"{'.'.join(str(p) for p in e.absolute_path) or '$'}: {e.message}"
            for e in validator.iter_errors(params)]


def _semantic(play: str, params: dict) -> list[str]:
    errors: list[str] = []
    if play == PLAY_RESCHEDULE:
        for i, w in enumerate(params.get("proposed_windows") or ()):
            s, e = _parse_dt(w.get("start")), _parse_dt(w.get("end"))
            if s is not None and e is not None and e <= s:
                errors.append(f"proposed_windows[{i}]: end must be after start")
        tz = params.get("timezone")
        if isinstance(tz, str) and tz.strip():
            try:
                from zoneinfo import ZoneInfo
                ZoneInfo(tz)
            except Exception:      # noqa: BLE001 — unknown / malformed zone
                errors.append("timezone: not an IANA time zone")
    if play == PLAY_REASSIGN:
        a, b = params.get("from_seat_email"), params.get("to_seat_email")
        if isinstance(a, str) and isinstance(b, str) and a.strip().lower() == b.strip().lower():
            errors.append("to_seat_email: must differ from from_seat_email")
    return errors


def validate(play: str, params: Any, *, use_jsonschema: bool = True) -> list[str]:
    """Every reason `params` is not a valid `play` request; [] = valid. Strict: unknown fields,
    wrong types and a `send` other than false are all errors."""
    schema = SCHEMAS.get(str(play or ""))
    if schema is None:
        return [f"play: unknown play {play!r} (one of {sorted(PLAYS)})"]
    errors: list[str] = []
    _check(schema, params, "", errors)
    if use_jsonschema:
        errors += [e for e in _jsonschema_errors(schema, params) if e not in errors]
    if not errors:
        errors = _semantic(play, params)
    return errors


# ── agents ────────────────────────────────────────────────────────────────────────────────────
def select_agent(conn, org_id: str, play: str, agent_id: str | None = None) -> str | None:
    """The agent that runs `play` for this org: active, has a webhook, lists the play in
    `allowed_actions`; the default agent first. `agent_id` narrows to that one (None when it does
    not qualify). One statement."""
    return conn.execute(text(
        "select agent_id from agent_registry where org_id = :o and status = 'active' "
        "and :p = any(allowed_actions) and coalesce(webhook_url, '') <> '' "
        "and (cast(:a as text) is null or agent_id = cast(:a as text)) "
        "order by is_default desc, agent_id limit 1"),
        {"o": org_id, "p": play, "a": agent_id}).scalar()


def agents_by_play(conn, org_id: str) -> dict[str, str]:
    """play → the agent `select_agent` would pick, for every play some agent allows. One
    statement — for producers that consider several plays per pass."""
    out: dict[str, str] = {}
    for r in conn.execute(text(
            "select agent_id, allowed_actions from agent_registry where org_id = :o "
            "and status = 'active' and coalesce(webhook_url, '') <> '' "
            "order by is_default desc, agent_id"), {"o": org_id}):
        for play in (r.allowed_actions or ()):
            if play in PLAYS:
                out.setdefault(play, r.agent_id)
    return out


def delegate_action(play: str, params: dict, agent_id: str | None) -> dict | None:
    """§3.5: the moment/card action that opens a proposal — None unless an agent runs the play and
    the params are valid (a producer never offers a request that would 422)."""
    if not agent_id or validate(play, params):
        return None
    return {"id": "delegate", "label": "Ask my agent",
            "payload": {"play": play, "params": params, "agent_id": agent_id}}


# ── words ─────────────────────────────────────────────────────────────────────────────────────
def _names(emails: Iterable[str]) -> str:
    items = [str(e) for e in emails if e]
    if len(items) <= 3:
        return ", ".join(items) or "no attendees"
    return ", ".join(items[:3]) + f" +{len(items) - 3}"


def instruction(play: str, params: dict) -> str:
    """The one paragraph a human approves — every fact in it is a field of `params`."""
    if play == PLAY_RESCHEDULE:
        ref = params["meeting_ref"]
        windows = "; ".join(f"{w['start']} → {w['end']}" for w in params["proposed_windows"])
        return (f"Reschedule the {ref['provider']} calendar event {ref['event_id']} (now "
                f"{params['current_start']}) with {_names(params['attendees'])}. Offer: {windows} "
                f"({params['timezone']}). Message: {params['message_draft']}")
    if play == PLAY_REASSIGN:
        ref = params["task_ref"]
        return (f"Reassign {ref['provider']} task {ref['id']} from {params['from_seat_email']} to "
                f"{params['to_seat_email']}." + (f" Note: {params['note']}" if params["note"]
                                                 else ""))
    if play == PLAY_FOLLOW_UP:
        ref = params["thread_ref"]
        return (f"Draft (do not send) a reply on {ref['provider']} thread {ref['thread_id']} to "
                f"{_names(params['to'])}. Subject: {params['subject']}. Body: "
                f"{params['body_draft']}")
    raise ValueError(f"unknown play {play!r}")


def summary(play: str, params: dict | None) -> str:
    """A short label for realtime events and history rows."""
    p = params or {}
    if play == PLAY_RESCHEDULE:
        return f"Reschedule with {_names(p.get('attendees') or ())}"
    if play == PLAY_REASSIGN:
        return f"Reassign to {p.get('to_seat_email') or 'a teammate'}"
    if play == PLAY_FOLLOW_UP:
        return f"Draft a follow-up to {_names(p.get('to') or ())}"
    return str(play or "")


def iso_utc(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    dt = dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def request_document(*, delegation_id: str, org_id: str, agent_id: str, play: str, params: dict,
                     context: dict, approved_by: str | None, approved_at: datetime | None,
                     expires_at: datetime | None, result_url: str | None) -> dict:
    """The §3.1 body (frozen field order). Before approval the approval fields are null — that is
    the preview a human reads; the approval fills them and the bytes are frozen."""
    ctx = context or {}
    return {"type": "action.requested", "version": 1, "delegation_id": delegation_id,
            "org_id": org_id, "agent_id": agent_id, "play": play, "params": params,
            "context": {"moment_id": ctx.get("moment_id"), "card_id": ctx.get("card_id"),
                        "headline": ctx.get("headline"), "evidence": ctx.get("evidence") or []},
            "approved_by": approved_by, "approved_at": iso_utc(approved_at),
            "expires_at": iso_utc(expires_at), "result_url": result_url}


def request_body(doc: dict) -> bytes:
    """The exact bytes sent on every attempt: compact, ASCII, field order as built."""
    return json.dumps(doc, separators=(",", ":"), ensure_ascii=True, default=str).encode("ascii")


def body_sha256(body: bytes) -> str:
    return hashlib.sha256(body).hexdigest()


# ── evidence through P2 fact visibility ───────────────────────────────────────────────────────
def request_evidence(conn, org_id: str, evidence: Iterable[Any], audience: Iterable[str] | None,
                     *, limit: int = 20) -> list[dict]:
    """`evidence` minus every item naming a (node, field) whose active fact is PRIVATE to
    principals `audience` does not cover. An empty audience (an agent bound to nobody) reads no
    private fact at all — the conservative default."""
    from genios_engine.context.fact_visibility import PRIVATE, audience_may_read, private_fact_index
    private = private_fact_index(conn, org_id)
    who = [a for a in (audience or ()) if a]
    out: list[dict] = []
    for item in evidence or ():
        if not isinstance(item, dict):
            continue
        fields = private.get(str(item.get("node_id") or "")) or {}
        field = item.get("field")
        if field and field in fields and not audience_may_read(PRIVATE, fields[field], who):
            continue
        out.append(dict(item))
        if len(out) >= limit:
            break
    return out


# ── producer helpers ──────────────────────────────────────────────────────────────────────────
def reschedule_windows(start: datetime, end: datetime | None, *, now: datetime,
                       count: int = 2) -> list[dict]:
    """Deterministic alternatives a human edits before approving: the same time of day on the next
    `count` weekdays after the meeting, same duration (30 min when the end is unknown)."""
    start = start if start.tzinfo else start.replace(tzinfo=timezone.utc)
    duration = (end - start) if end is not None and end > start else timedelta(minutes=30)
    out: list[dict] = []
    day = start
    while len(out) < count:
        day = day + timedelta(days=1)
        if day.weekday() >= 5 or day <= now:
            continue
        out.append({"start": iso_utc(day), "end": iso_utc(day + duration)})
    return out


__all__ = ["PLAYS", "PLAY_FOLLOW_UP", "PLAY_REASSIGN", "PLAY_RESCHEDULE", "SCHEMAS",
           "agents_by_play", "body_sha256", "delegate_action", "instruction", "request_body",
           "request_document", "request_evidence", "reschedule_windows", "select_agent",
           "summary", "validate"]
