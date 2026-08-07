"""Layer 5.2 Delivery Orchestrator — ExecutionObject in, durable DeliveryObject out.

This is the only production materialisation path for an initial execution or reminder. Cards
remain a presentation/read model; they cannot independently authorize an outbound notification.
Concrete audience, channel and interruptibility are resolved here from current directory,
registered destinations and leased presence. Legacy ExecutionObject v1 route fields are read as
semantic audience/format hints only; their concrete channel and interrupt values are ignored.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from typing import Any, Mapping, Sequence

from sqlalchemy import text

from genios_engine.contracts.execution import ChannelClass, ExecutionObject
from genios_engine.contracts.visibility import PARTICIPANTS, PRIVATE, Visibility
from genios_engine.deliver.audience import AudienceResolution, Seat, resolve_audience
from genios_engine.deliver.channels.slack import (
    format_card_message,
    format_execution_message,
    format_reminder_message,
)
from genios_engine.deliver.destination import RegisteredDestination, destination_from_row
from genios_engine.deliver.gate import channel_class_for
from genios_engine.deliver.scheduler import PriorityClass, priority_class, priority_rank
from genios_engine.platform.canonical import canonicalize
from genios_engine.platform.ids import new_id


ORCHESTRATOR_VERSION = "delivery-orchestrator.v2"
_log = logging.getLogger(__name__)
SURFACE_FOR_CONTEXT = {
    "gmail": "extension",
    "email": "extension",
    "email_editor": "extension",
    "crm": "extension",
    "browser": "extension",
    "ide": "application",
    "cursor": "application",
    "claude_code": "application",
    "desktop": "application",
    "mobile": "mobile",
    "dashboard": "dashboard",
    "web": "in_app",
    "web_app": "in_app",
}
_INTERNAL_SURFACES = ("in_app", "dashboard")
_PUSH_CHANNELS = frozenset({"slack", "teams", "webhook", "agent"})


@dataclass(frozen=True, slots=True)
class DeliveryPlan:
    audience: str
    recipient: str | None
    channel: str
    channel_class: ChannelClass
    format_kind: str
    priority_class: PriorityClass
    priority_rank: int
    interrupt: bool
    route_plan: tuple[str, ...]
    reason_code: str


def _destination_ladder(destinations: Sequence[RegisteredDestination], *,
                        priority: PriorityClass, presence: Mapping[str, Any],
                        audience: AudienceResolution,
                        constrained_visibility: bool = False) -> tuple[str, ...]:
    available = {item.channel: item for item in destinations if item.enabled_for("push")}
    for surface in _INTERNAL_SURFACES:
        available.setdefault(surface, RegisteredDestination(surface, {}))

    surface = SURFACE_FOR_CONTEXT.get(str(presence.get("surface") or "").lower())
    contextual = [surface] if surface and surface in {
        "extension", "application", "mobile", "dashboard", "in_app"} else []
    if surface:
        available.setdefault(surface, RegisteredDestination(surface, {}))

    agent_delivery = audience.audience == "agent"
    if audience.audience == "admin_queue" and audience.recipient is None:
        # No active person means there is no authority for a shared webhook or chat push. Keep
        # the work visible only on authenticated tenant surfaces until an admin/owner exists.
        return ("dashboard", "in_app")
    external = sorted(
        (item for item in available.values()
         if ((agent_delivery and item.channel in {"agent", "api"})
             or (not agent_delivery and item.channel in _PUSH_CHANNELS
                 and item.channel != "agent"))
         # A shared webhook/channel cannot preserve a participant/private source ACL even when
         # the logical recipient is authorised. Constrained evidence stays on authenticated,
         # recipient-scoped product surfaces.
         and not constrained_visibility),
        key=lambda item: (-item.priority, item.channel),
    )
    external_names = [item.channel for item in external]

    if agent_delivery:
        preferred = [name for name in ("agent", "api") if name in available]
    elif priority in {PriorityClass.CRITICAL, PriorityClass.HIGH}:
        # An eligible inline surface is more useful than a generic notification. A meeting/focus
        # lease deliberately does not count as eligible; the timing gate holds intrusive routes.
        busy = bool(presence.get("focus_mode")) or str(presence.get("activity")) in {
            "meeting", "presenting", "focus"}
        preferred = ([] if busy else contextual) + external_names
    elif priority is PriorityClass.MEDIUM:
        preferred = contextual + ["in_app", "dashboard"]
    else:
        preferred = ["dashboard", "in_app"]

    # Agent delivery cannot silently fall back to a human inbox while retaining an agent
    # recipient. If its registered transports fail it becomes an operator-visible dead letter.
    fallback = (external_names if agent_delivery
                else contextual + external_names + ["in_app", "dashboard"])
    ordered: list[str] = []
    for name in preferred + fallback:
        if name in available and name not in ordered:
            ordered.append(name)
    return tuple(ordered if ordered else (() if agent_delivery else ("in_app",)))


def plan_delivery(execution: ExecutionObject, *, seats: Sequence[Seat],
                  destinations: Sequence[RegisteredDestination],
                  presence: Mapping[str, Any] | None = None,
                  presence_by_recipient: Mapping[str, Mapping[str, Any]] | None = None,
                  event_detail: Mapping[str, Any] | None = None,
                  execution_owner: str | None = None,
                  requested_audience: str | None = None,
                  agent_recipient: str | None = None) -> DeliveryPlan:
    """Resolve a final route without reading L5's concrete channel/interrupt fields."""
    visibility = Visibility.model_validate(dict(execution.visibility))
    constrained = visibility.scope in {PARTICIPANTS, PRIVATE}
    visible_seats = tuple(
        seat for seat in seats
        if (not constrained or visibility.can_view(seat.email, org_member=True)))
    effective_audience = str((event_detail or {}).get("target_audience")
                             or requested_audience
                             or execution.communication.audience.value)
    if constrained and effective_audience == "agent":
        # Agent ids are not human ACL principals. Until a registered agent carries a verified
        # principal binding, treating it as an email participant would widen source access.
        raise ValueError("constrained source visibility has no verified agent principal")
    resolution = resolve_audience(
        execution_owner=(execution_owner if execution_owner is not None
                         else execution.communication.assignee),
        requested_audience=(requested_audience or execution.communication.audience.value),
        seats=visible_seats,
        event_detail=event_detail,
        agent_recipient=agent_recipient,
    )
    if constrained and resolution.recipient is None:
        raise ValueError("no visibility-authorized active recipient")
    live_presence = dict(
        (presence_by_recipient or {}).get(resolution.recipient or "", presence or {}))
    scheduled = priority_class(execution.priority_bp)
    # A frozen escalation hint may promote delivery scheduling, but Layer 5.2 still determines
    # the actual channel and whether that channel may interrupt in the current context.
    if bool((event_detail or {}).get("interrupt")):
        scheduled = PriorityClass.CRITICAL
    ladder = _destination_ladder(destinations, priority=scheduled,
                                 presence=live_presence, audience=resolution,
                                 constrained_visibility=constrained)
    if resolution.audience == "agent" and (not resolution.recipient or not ladder):
        raise ValueError("agent audience has no active recipient or delivery route")
    channel = ladder[0]
    channel_class = channel_class_for(channel)
    busy = bool(live_presence.get("focus_mode")) or str(live_presence.get("activity")) in {
        "meeting", "presenting", "focus"}
    interrupt = (channel_class is ChannelClass.CHAT
                 and scheduled is PriorityClass.CRITICAL
                 and execution.confidence_bp >= 7_000 and not busy)
    context_reason = "context_surface" if ladder[0] in set(SURFACE_FOR_CONTEXT.values()) else (
        "registered_push" if ladder[0] in _PUSH_CHANNELS else "authenticated_surface")
    return DeliveryPlan(
        audience=resolution.audience,
        recipient=resolution.recipient,
        channel=channel,
        channel_class=channel_class,
        format_kind=format_kind_for(channel),
        priority_class=scheduled,
        priority_rank=priority_rank(scheduled),
        interrupt=interrupt,
        route_plan=ladder,
        reason_code=f"{resolution.reason_code}:{context_reason}",
    )


def format_kind_for(channel: str) -> str:
    return {
        "slack": "slack_message", "teams": "teams_action_card",
        "webhook": "webhook_payload", "agent": "agent_envelope",
        "extension": "inline_suggestion", "mobile": "mobile_card",
        "dashboard": "dashboard_card", "application": "application_card",
        "in_app": "in_app_card", "api": "rest_resource",
    }.get(channel, "delivery_payload")


def _json_mapping(value: Any) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except ValueError:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def _with_inherited_visibility(conn, execution: ExecutionObject) -> ExecutionObject:
    """Backfill v1's missing ACL in memory without changing its stored identity/hash.

    New v2 objects carry the frozen result. A still-live v1 commitment is resolved from its
    immutable reasoning context at every materialization/final-send boundary; silently treating
    an old private email as org-visible would make backwards compatibility a privacy bypass.
    """
    if execution.version != "execution.v1":
        return execution
    row = conn.execute(text(
        "select source_manifest from reasoning_context_snapshots "
        "where org_id=:o and context_snapshot_id=:context"),
        {"o": execution.org_id,
         "context": execution.context_snapshot_id}).mappings().first()
    if row is None:
        # Missing lineage is not permission. This produces no authorised recipient and the
        # materialization failure ledger keeps the operator-visible repair path.
        visibility = Visibility(
            scope=PRIVATE, principals=[], derived_from="unresolved:v1-context")
    else:
        from genios_engine.executive.sweep import _execution_visibility
        evidence_ids = tuple(str(item) for item in
                             (dict(execution.metadata).get("evidence_ids") or ()))
        visibility = _execution_visibility(
            conn, org_id=execution.org_id, source_manifest=row.get("source_manifest"),
            evidence_ids=evidence_ids)
    return replace(execution, visibility=visibility.model_dump())


def _initial_payload(execution: ExecutionObject, card_id: str | None) -> dict[str, Any]:
    return {
        "kind": "execution_initial",
        "execution_id": execution.execution_id,
        "card_id": card_id,
        "headline": execution.goal,
        "situation": execution.do_nothing_consequence,
        "next_action": execution.first_action.label,
        "deadline": execution.deadline_at.isoformat(),
        "confidence_bp": execution.confidence_bp,
    }


def _reminder_payload(execution: ExecutionObject, card_id: str | None,
                      reason_code: str, detail: Mapping[str, Any]) -> dict[str, Any]:
    facts = _json_mapping(detail.get("facts"))
    return {
        "kind": "execution_reminder",
        "urgency": str(detail.get("urgency") or "gentle"),
        "headline": str(facts.get("goal") or execution.goal),
        "situation": _reminder_situation(detail, facts),
        "next_action": str(facts.get("next_action") or execution.first_action.label),
        "consequence": str(facts.get("consequence") or execution.do_nothing_consequence),
        "execution_id": execution.execution_id,
        "card_id": card_id,
        "reason_code": reason_code,
    }


def _agent_payload(execution: ExecutionObject, card_id: str | None, *,
                   kind: str, event_id: str | None, reason_code: str | None,
                   detail: Mapping[str, Any]) -> dict[str, Any]:
    """The complete, versioned machine instruction carried by agent/API routes.

    A human notification may summarize a commitment. An executor may not: dropping later
    actions, dependencies or approval/read-only boundaries would turn a safe Layer 5 plan into a
    different instruction. The immutable ExecutionObject is therefore the agent contract, with
    delivery-event context alongside it rather than mixed into it.
    """
    return {
        "kind": "agent_execution_instruction",
        "schema_version": "genios.agent-delivery.v1",
        "delivery_kind": kind,
        "execution_id": execution.execution_id,
        "execution_hash": execution.semantic_hash,
        "card_id": card_id,
        "execution_event": ({
            "event_id": event_id,
            "reason_code": reason_code,
            "detail": dict(detail),
        } if event_id is not None else None),
        # Canonical JSON preserves MappingProxy metadata and tagged UTC datetimes exactly; a
        # default=str fallback would silently turn nested policy metadata into Python repr text.
        "execution": canonicalize(execution.to_semantic_dict()),
        "safety": {
            "autonomy_allowed": execution.autonomy_allowed,
            "read_only": execution.read_only,
            "approval_action_ids": [item.action_id for item in execution.approval_gates],
        },
    }


def _source_for_delivery(execution: ExecutionObject, card_id: str | None, *,
                         kind: str, audience: str, event_id: str | None = None,
                         reason_code: str | None = None,
                         detail: Mapping[str, Any] | None = None) -> dict[str, Any]:
    event_detail = dict(detail or {})
    if audience == "agent":
        return _agent_payload(
            execution, card_id, kind=kind, event_id=event_id,
            reason_code=reason_code, detail=event_detail)
    if kind == "execution_reminder":
        return _reminder_payload(
            execution, card_id, str(reason_code or "execution_reminded"), event_detail)
    return _initial_payload(execution, card_id)


def _reminder_situation(detail: Mapping[str, Any], facts: Mapping[str, Any]) -> str:
    parts: list[str] = []
    if isinstance(facts.get("days_open"), int):
        parts.append(f"open {facts['days_open']}d")
    if isinstance(facts.get("days_remaining"), int):
        days = facts["days_remaining"]
        parts.append("due today" if days == 0 else f"{days}d left")
    if detail.get("escalation_day") is not None:
        parts.append(f"day {detail['escalation_day']} of the escalation ladder")
    return " · ".join(parts)


def render_for_channel(channel: str, payload: Mapping[str, Any], *,
                       base_url: str = "") -> dict[str, Any]:
    source = dict(payload)
    if channel == "slack":
        if source.get("kind") == "execution_reminder":
            return format_reminder_message(source, base_url=base_url)
        if source.get("kind") == "execution_initial":
            return format_execution_message(source, base_url=base_url)
        return format_card_message({
            "card_id": source.get("card_id"), "headline": source.get("headline"),
            "situation": source.get("situation"),
            "urgency_band": "critical" if source.get("priority_class") == "critical" else "high",
            "score": source.get("confidence_bp"),
        }, base_url=base_url)
    card_id = source.get("card_id")
    execution_id = source.get("execution_id")
    if base_url and (card_id or execution_id):
        path = f"cards/{card_id}" if card_id else f"commitments/{execution_id}"
        source["url"] = f"{base_url.rstrip('/')}/{path}"
    return source


def _seats(conn, org_id: str, *, lock: bool = False) -> tuple[Seat, ...]:
    rows = conn.execute(text(
        "select seat_id, role, manager_seat_id, active, email from org_seats where org_id=:o" +
        (" for share" if lock else "")),
        {"o": org_id}).mappings().all()
    return tuple(Seat(
        seat_id=str(row["seat_id"]), role=str(row.get("role") or "member"),
        manager_seat_id=row.get("manager_seat_id"), active=bool(row.get("active")),
        email=(str(row["email"]).strip().lower() if row.get("email") else None))
        for row in rows)


def _presence(conn, org_id: str, now: datetime, *, lock: bool = False) \
        -> dict[str, dict[str, Any]]:
    rows = conn.execute(text(
        "select seat_id, activity, surface, focus_mode, busy_until, expires_at "
        "from delivery_presence where org_id=:o and expires_at>:now" +
        (" for share" if lock else "")),
        {"o": org_id, "now": now}).mappings().all()
    return {str(row["seat_id"]): dict(row) for row in rows}


def _agent_recipient(conn, org_id: str, *, preferred: str | None = None,
                     lock: bool = False) -> str | None:
    row = conn.execute(text(
        "select agent_id from agent_registry where org_id=:o and coalesce(status,'active')='active' "
        "and 'delivery.read'=any(coalesce(allowed_actions,array[]::text[])) "
        "and (:preferred is null or agent_id=:preferred) "
        "order by is_default desc nulls last,agent_id limit 1" +
        (" for share" if lock else "")),
        {"o": org_id, "preferred": preferred}).first()
    if row is None:
        return None
    return str(row.agent_id if hasattr(row, "agent_id") else row[0])


def _destinations_for_agent(conn, org_id: str, agent_id: str | None,
                            destinations: Sequence[RegisteredDestination], *,
                            lock: bool = False) -> tuple[RegisteredDestination, ...]:
    """Bind agent transports to the exact selected agent, never an org-wide bool_or."""
    scoped = [item for item in destinations if item.channel not in {"agent", "api"}]
    if not agent_id:
        return tuple(scoped)
    api_key = conn.execute(text(
        "select id from api_keys where org_id=:o and agent_id=:agent and is_active "
        "and 'delivery.read'=any(coalesce(scopes,array[]::text[])) limit 1" +
        (" for share" if lock else "")),
        {"o": org_id, "agent": agent_id}).first()
    if api_key is not None:
        scoped.append(RegisteredDestination("api", {"priority": 100}))
    row = conn.execute(text(
        "select agent_id,webhook_url,webhook_secret,webhook_config_encrypted "
        "from agent_registry "
        "where org_id=:o and agent_id=:agent and coalesce(status,'active')='active'" +
        (" for share" if lock else "")),
        {"o": org_id, "agent": agent_id}).first()
    if row is not None:
        from genios_engine.deliver.units import configured_agent
        mapping = dict(row._mapping) if hasattr(row, "_mapping") else dict(row)
        if configured_agent(mapping):
            scoped.append(RegisteredDestination("agent", {"priority": 110}))
    return tuple(scoped)


def _reminder_is_current(conn, org_id: str, execution_id: str,
                         event_id: str, *, lock: bool = False) -> tuple[bool, dict[str, Any]]:
    """Return reminder detail only when no committed human/progress fact supersedes it."""
    suffix = " for share" if lock else ""
    event = conn.execute(text(
        "select detail,occurred_at from execution_events where org_id=:o and execution_id=:x "
        "and event_id=:event and kind='execution.reminded'" + suffix),
        {"o": org_id, "x": execution_id, "event": event_id}).mappings().first()
    if event is None:
        return False, {}
    stale = conn.execute(text(
        "select event_id from execution_events where org_id=:o and execution_id=:x "
        "and event_id<>:event and ("
        "(kind='execution.cancelled' and reason_code='human_dismissed') or "
        "((kind='execution.reminded' and (occurred_at>:reminded or "
        "(occurred_at=:reminded and event_id>:event))) or "
        "(occurred_at>=:reminded and kind in ("
        "'execution.action_completed','execution.started',"
        "'execution.waiting','execution.blocked','execution.unblocked',"
        "'execution.replanned','execution.completed','execution.cancelled',"
        "'execution.expired','execution.archived')))) limit 1" + suffix),
        {"o": org_id, "x": execution_id, "event": event_id,
         "reminded": event["occurred_at"]}).first()
    return stale is None, _json_mapping(event.get("detail"))


def _initial_is_current(conn, org_id: str, execution_id: str, *, lock: bool = False) -> bool:
    """Initial delivery is stale once progress or a reminder has already happened."""
    suffix = " for share" if lock else ""
    row = conn.execute(text(
        "select event_id from execution_events where org_id=:o and execution_id=:x and kind in ("
        "'execution.action_completed','execution.reminded','execution.started',"
        "'execution.waiting','execution.blocked','execution.unblocked',"
        "'execution.replanned','execution.completed','execution.cancelled',"
        "'execution.expired','execution.archived') limit 1" + suffix),
        {"o": org_id, "x": execution_id}).first()
    return row is None


def current_delivery_plan(conn, *, org_id: str, execution_id: str,
                          event_id: str | None, now: datetime) \
        -> tuple[ExecutionObject, DeliveryPlan] | None:
    """Re-plan one live execution under read locks immediately before transport.

    Materialisation is intentionally optimistic and refreshable. This function is the final
    authority barrier: reassignment, reporting-line edits, destination revocation and active
    presence are read again and locked in the same transaction that remains open through the
    provider call. A route mismatch therefore returns ``None`` to the caller instead of leaking
    a delivery to a formerly-authorised recipient.
    """
    # Management mutations acquire the same tenant row FOR UPDATE before changing delivery
    # preferences, destinations, agents or seats. Holding its shared lock through transport
    # makes those writes linearizable with this final authority proof.
    if conn.execute(text("select id from orgs where id=:o for share"),
                    {"o": org_id}).first() is None:
        return None
    global_flag = conn.execute(text(
        "select enabled from feature_flags where key='kill_switch_all' for share")).first()
    global_enabled = (global_flag.enabled if hasattr(global_flag, "enabled")
                      else global_flag[0] if global_flag is not None else False)
    tenant = conn.execute(text(
        "select enabled from feature_flags where key='kill_switch:' || :o for share"),
        {"o": org_id}).first()
    tenant_enabled = (tenant.enabled if hasattr(tenant, "enabled")
                      else tenant[0] if tenant is not None else True)
    if not bool(global_enabled) or not bool(tenant_enabled):
        return None
    conn.execute(text(
        "select graph_version from graph_versions where org_id=:o for share"),
        {"o": org_id})
    row = conn.execute(text(
        "select payload,assignee,audience,state,signal_id from executions "
        "where org_id=:o and execution_id=:x "
        "and closed_at is null and expires_at>:now "
        "and state in ('pending','running','waiting','blocked') "
        "and not exists (select 1 from execution_events dismissed "
        "where dismissed.org_id=executions.org_id "
        "and dismissed.execution_id=executions.execution_id "
        "and dismissed.kind='execution.cancelled' "
        "and dismissed.reason_code='human_dismissed') for share"),
        {"o": org_id, "x": execution_id, "now": now}).mappings().first()
    if row is None:
        return None
    execution = _with_inherited_visibility(
        conn, ExecutionObject.from_semantic_dict(_json_mapping(row["payload"])))
    if execution.execution_id != execution_id:
        raise ValueError("stored execution identity mismatch")

    detail: dict[str, Any] = {}
    if event_id:
        current, detail = _reminder_is_current(
            conn, org_id, execution_id, event_id, lock=True)
        if not current:
            raise ValueError("delivery event authority is missing")
    elif not _initial_is_current(conn, org_id, execution_id, lock=True):
        raise ValueError("initial delivery was superseded by execution progress")

    # Reuse Layer 5's guard at the actual provider boundary. An open row is not enough: a reply,
    # closed subject, superseding execution or revoked L4 decision may have landed since the last
    # executive sweep. The graph-version lock above serializes this proof with graph mutation.
    from genios_engine.executive.execution_guard import GuardAction, validate
    from genios_engine.executive.execution_store import validation_input
    verdict = validate(
        execution,
        validation_input(
            conn, execution, row, now=now, signal_id=row.get("signal_id"),
            lock_authority=True))
    if verdict.action not in {GuardAction.PROCEED, GuardAction.REROUTE}:
        return None

    seats = _seats(conn, org_id, lock=True)
    requested = _requested_audience(execution, row, detail)
    preferred_agent = ((detail.get("target_seat") or row.get("assignee"))
                       if requested == "agent" else None)
    selected_agent = _agent_recipient(
        conn, org_id, preferred=str(preferred_agent) if preferred_agent else None, lock=True)
    presence = _presence(conn, org_id, now, lock=True)

    channel_rows = conn.execute(text(
        "select channel,config,config_encrypted from org_channels "
        "where org_id=:o and active for share"),
        {"o": org_id}).mappings().all()
    from genios_engine.deliver.units import configured_channel
    valid_destinations = [
        destination_from_row(item) for item in channel_rows
        if configured_channel(dict(item))]
    destinations = _destinations_for_agent(
        conn, org_id, selected_agent,
        valid_destinations, lock=True)

    return execution, plan_delivery(
        execution, seats=seats, destinations=destinations,
        presence_by_recipient=presence, event_detail=detail,
        execution_owner=row.get("assignee"), requested_audience=requested,
        agent_recipient=selected_agent)


def _requested_audience(execution: ExecutionObject, row: Mapping[str, Any],
                        detail: Mapping[str, Any] | None = None) -> str:
    return str((detail or {}).get("target_audience") or row.get("audience")
               or execution.communication.audience.value)


def _daily_budget(value: Any) -> int:
    effective = _json_mapping(value)
    scoring = effective.get("scoring") if isinstance(effective.get("scoring"), Mapping) else {}
    raw = scoring.get("budget_per_user_day", 7)
    try:
        return max(1, min(15, int(raw)))
    except (TypeError, ValueError):
        return 7


def _insert(conn, *, row: Mapping[str, Any], execution: ExecutionObject,
            event_id: str | None, kind: str, source: Mapping[str, Any], plan: DeliveryPlan,
            base_url: str, now: datetime) -> int:
    logical = (f"execution:{execution.execution_id}:initial" if event_id is None
               else f"execution:{execution.execution_id}:event:{event_id}")
    subject = (f"exec:{execution.execution_id}:initial" if event_id is None
               else f"exec:{execution.execution_id}:{event_id}")
    source_with_priority = {**dict(source), "priority_class": plan.priority_class.value}
    delivery_id = new_id("ob")
    values = {
        "i": delivery_id, "o": execution.org_id, "subject": subject,
        "channel": plan.channel,
        "payload": json.dumps(render_for_channel(plan.channel, source_with_priority,
                                                   base_url=base_url), default=str),
        "signal": row.get("signal_id"), "run": execution.reasoning_run_id,
        "decision": execution.decision_hash, "expires": execution.expires_at,
        "recipient": plan.recipient,
        "band": ("critical" if plan.priority_class is PriorityClass.CRITICAL else
                 "high" if plan.priority_class is PriorityClass.HIGH else "standard"),
        "cclass": plan.channel_class.value, "interrupt": plan.interrupt,
        "execution": execution.execution_id, "execution_hash": execution.semantic_hash,
        "event": event_id, "kind": kind, "audience": plan.audience,
        "destination": plan.channel, "format": plan.format_kind,
        "reason": plan.reason_code, "dedupe": logical,
        "priority_class": plan.priority_class.value, "priority_rank": plan.priority_rank,
        "budget": _daily_budget(row.get("delivery_effective_config")),
        "source": json.dumps(source_with_priority, default=str),
        "routes": json.dumps(plan.route_plan), "now": now,
    }

    # Migration 0046 added a logical key, but pre-upgrade executive reminders already occupy
    # the older (org, card_id, channel) unique key. Adopt an unattempted queued row in place so
    # the first v2 sweep neither loses the delivery to an ON CONFLICT no-op nor creates a second
    # row when current routing selects another channel. Any transport evidence freezes the old
    # row: not knowing whether it reached a provider is never permission to manufacture a copy.
    legacy = conn.execute(text(
        "select id,channel,status,attempts,claim_token,next_attempt_at,"
        "legacy_reconciliation_required from delivery_outbox "
        "where org_id=:o and card_id=:subject and delivery_kind='legacy_card' "
        "order by (channel=:channel) desc,created_at,id for update"),
        {"o": execution.org_id, "subject": subject, "channel": plan.channel}
    ).mappings().all()
    if legacy:
        safe = [item for item in legacy if item["status"] == "queued"
                and int(item.get("attempts") or 0) == 0 and not item.get("claim_token")
                and not bool(item.get("legacy_reconciliation_required"))
                and item.get("next_attempt_at") is not None
                and item["next_attempt_at"] <= now]
        if len(safe) != len(legacy):
            return 0
        adopted = safe[0]
        for obsolete in safe[1:]:
            conn.execute(text(
                "update delivery_outbox set status='cancelled',lifecycle_status='cancelled',"
                "last_error='superseded duplicate legacy execution delivery',updated_at=:now "
                "where org_id=:o and id=:id and delivery_kind='legacy_card' and attempts=0"),
                {"now": now, "o": execution.org_id, "id": obsolete["id"]})
        values["i"] = adopted["id"]
        inserted = conn.execute(text(
            "update delivery_outbox set channel=:channel,payload=cast(:payload as jsonb),"
            "status='queued',next_attempt_at=least(next_attempt_at,:now),last_error=null,"
            "signal_id=:signal,reasoning_run_id=:run,reasoning_decision_hash=:decision,"
            "authority_expires_at=:expires,recipient=:recipient,band=:band,"
            "channel_class=:cclass,interrupt=:interrupt,execution_id=:execution,"
            "execution_hash=:execution_hash,execution_event_id=:event,delivery_kind=:kind,"
            "audience=:audience,destination=:destination,format_kind=:format,"
            "route_reason=:reason,dedupe_key=:dedupe,priority_class=:priority_class,"
            "priority_rank=:priority_rank,daily_budget=:budget,"
            "source_payload=cast(:source as jsonb),route_plan=cast(:routes as jsonb),"
            "route_index=0,retry_generation=0,generation_attempts=0,"
            "destination_fingerprint=null,control_failures=0,claim_token=null,claimed_at=null,"
            "claimed_until=null,lifecycle_status='queued',updated_at=:now "
            "where org_id=:o and id=:i and delivery_kind='legacy_card' and status='queued' "
            "and attempts=0 and not legacy_reconciliation_required returning id"), values).first()
    else:
        inserted = conn.execute(text(
        "insert into delivery_outbox (id,org_id,card_id,channel,payload,status,"
        "signal_id,reasoning_run_id,reasoning_decision_hash,authority_expires_at,"
        "recipient,band,channel_class,interrupt,execution_id,execution_hash,"
        "execution_event_id,delivery_kind,audience,destination,format_kind,route_reason,"
        "dedupe_key,priority_class,priority_rank,daily_budget,source_payload,route_plan,route_index,"
        "lifecycle_status,created_at,updated_at) values ("
        ":i,:o,:subject,:channel,cast(:payload as jsonb),'queued',:signal,:run,:decision,"
        ":expires,:recipient,:band,:cclass,:interrupt,:execution,:execution_hash,:event,"
        ":kind,:audience,:destination,:format,:reason,:dedupe,:priority_class,:priority_rank,:budget,"
        "cast(:source as jsonb),cast(:routes as jsonb),0,'queued',:now,:now) "
        "on conflict do nothing returning id"),
        values).first()
    if inserted is None:
        return 0
    conn.execute(text(
        "insert into delivery_events (event_id,org_id,delivery_id,event_type,reason_code,"
        "actor_id,idempotency_key,metadata,occurred_at) values "
        "(:e,:o,:d,'queued',:r,'delivery',:key,cast(:m as jsonb),:at) on conflict do nothing"),
        {"e": new_id("dev"), "o": execution.org_id,
         "r": plan.reason_code, "key": f"queued:{logical}",
         "m": json.dumps({"channel": plan.channel, "route_plan": plan.route_plan}),
         "at": now, "d": values["i"]})
    return 1


def _materialization_failure(conn, *, org_id: str, execution_id: str,
                             event_id: str | None, exc: Exception, now: datetime) -> None:
    key = event_id or "initial"
    conn.execute(text(
        "insert into delivery_materialization_failures "
        "(org_id,execution_id,execution_event_id,error_class,detail,first_seen_at,last_seen_at) "
        "values (:o,:x,:event,:class,:detail,:now,:now) "
        "on conflict (org_id,execution_id,execution_event_id) do update set "
        "error_class=excluded.error_class,detail=excluded.detail,"
        "occurrences=delivery_materialization_failures.occurrences+1,"
        "last_seen_at=excluded.last_seen_at,resolved_at=null"),
        {"o": org_id, "x": execution_id, "event": key,
         "class": type(exc).__name__, "detail": str(exc)[:500], "now": now})
    _log.warning("delivery materialization rejected org=%s execution=%s event=%s error=%s",
                 org_id, execution_id, key, type(exc).__name__)


def _resolve_materialization_failure(conn, *, org_id: str, execution_id: str,
                                     event_id: str | None, now: datetime) -> None:
    conn.execute(text(
        "update delivery_materialization_failures set resolved_at=:now,last_seen_at=:now "
        "where org_id=:o and execution_id=:x and execution_event_id=:event "
        "and resolved_at is null"),
        {"now": now, "o": org_id, "x": execution_id, "event": event_id or "initial"})


def _refresh_pending(conn, *, org_id: str, seats: Sequence[Seat],
                     destinations: Sequence[RegisteredDestination],
                     presence: Mapping[str, Mapping[str, Any]], base_url: str,
                     now: datetime, limit: int) -> tuple[int, int]:
    """Refresh a safely mutable logical delivery from current execution/directory truth.

    Execution identity deliberately survives reassignment, and a quiet-hours deferral may wait
    long enough for the owner, manager, priority or payload to change. Replanning the same row is
    safe before the first physical provider attempt, and after attempts only when every recorded
    outcome proves non-delivery. Unknown, started or delivered evidence permanently freezes the
    recipient/route and forces manual recovery instead of risking a duplicate or privacy leak.
    """
    rows = conn.execute(text(
        "select d.id,d.execution_id,d.execution_event_id,d.delivery_kind,d.source_payload,"
        "d.execution_hash,d.recipient,d.audience,d.channel,d.channel_class,d.format_kind,"
        "d.interrupt,d.priority_class,d.priority_rank,d.route_reason,d.route_plan,d.daily_budget,"
        "d.retry_generation,d.generation_attempts,"
        "x.payload,x.card_id,x.assignee,x.audience as execution_audience,"
        "cs.effective as delivery_effective_config,e.detail as event_detail,"
        "e.reason_code as event_reason_code "
        "from delivery_outbox d join executions x "
        "on x.org_id=d.org_id and x.execution_id=d.execution_id "
        "left join config_snapshots cs on cs.org_id=x.org_id "
        "and cs.snapshot_id=x.config_snapshot_id "
        "left join execution_events e on e.org_id=d.org_id "
        "and e.execution_id=d.execution_id and e.event_id=d.execution_event_id "
        "where d.org_id=:o and d.delivery_kind<>'legacy_card' and d.source_payload is not null "
        "and d.status='queued' and d.lifecycle_status in ('queued','deferred') "
        "and (d.attempts=0 or (exists (select 1 from delivery_attempts safe "
        "where safe.org_id=d.org_id and safe.delivery_id=d.id) and not exists "
        "(select 1 from delivery_attempts unsafe where unsafe.org_id=d.org_id "
        "and unsafe.delivery_id=d.id and unsafe.outcome in ('started','unknown','delivered')))) "
        "and x.closed_at is null "
        "and x.state in ('pending','running','waiting','blocked') "
        "order by d.created_at,d.id limit :l for update of d skip locked"),
        {"o": org_id, "l": max(1, min(int(limit), 500))}).mappings().all()
    refreshed = invalid = 0
    for row in rows:
        execution: ExecutionObject | None = None
        event_id = str(row["execution_event_id"]) if row.get("execution_event_id") else None
        try:
            execution = _with_inherited_visibility(
                conn, ExecutionObject.from_semantic_dict(_json_mapping(row["payload"])))
            if execution.execution_id != row["execution_id"]:
                raise ValueError("stored execution identity mismatch")
            detail = _json_mapping(row.get("event_detail"))
            requested = str(detail.get("target_audience") or row.get("execution_audience")
                            or execution.communication.audience.value)
            preferred_agent = ((detail.get("target_seat") or row.get("assignee"))
                               if requested == "agent" else None)
            selected_agent = _agent_recipient(
                conn, org_id, preferred=str(preferred_agent) if preferred_agent else None)
            scoped_destinations = _destinations_for_agent(
                conn, org_id, selected_agent, destinations)
            plan = plan_delivery(
                execution, seats=seats, destinations=scoped_destinations,
                presence_by_recipient=presence, event_detail=detail,
                execution_owner=row.get("assignee"), requested_audience=requested,
                agent_recipient=selected_agent)
            source = _source_for_delivery(
                execution, row.get("card_id"), kind=str(row["delivery_kind"]),
                audience=plan.audience, event_id=event_id,
                reason_code=(str(row["event_reason_code"])
                             if row.get("event_reason_code") else None),
                detail=detail)
            source = {**source, "priority_class": plan.priority_class.value}
            routes = json.dumps(plan.route_plan)
            payload = json.dumps(render_for_channel(plan.channel, source, base_url=base_url),
                                 default=str)
            band = ("critical" if plan.priority_class is PriorityClass.CRITICAL else
                    "high" if plan.priority_class is PriorityClass.HIGH else "standard")
            changed = conn.execute(text(
                "update delivery_outbox set execution_hash=:hash,recipient=:recipient,"
                "audience=:audience,channel=:channel,destination=:channel,channel_class=:class,"
                "format_kind=:format,interrupt=:interrupt,priority_class=:priority,"
                "priority_rank=:rank,band=:band,route_reason=:reason,"
                "route_plan=cast(:routes as jsonb),route_index=0,daily_budget=:budget,"
                "source_payload=cast(:source as jsonb),payload=cast(:payload as jsonb),"
                "retry_generation=retry_generation+1,generation_attempts=0,"
                "destination_fingerprint=null,control_failures=0,"
                "next_attempt_at=case when attempts=0 then least(next_attempt_at,:now) "
                "else next_attempt_at end,gate_unit=null,gate_reason=null,"
                "lifecycle_status='queued',updated_at=:now "
                "where org_id=:o and id=:id and status='queued' "
                "and (attempts=0 or (exists (select 1 from delivery_attempts safe "
                "where safe.org_id=delivery_outbox.org_id "
                "and safe.delivery_id=delivery_outbox.id) and not exists "
                "(select 1 from delivery_attempts unsafe "
                "where unsafe.org_id=delivery_outbox.org_id "
                "and unsafe.delivery_id=delivery_outbox.id "
                "and unsafe.outcome in ('started','unknown','delivered')))) "
                "and (execution_hash is distinct from :hash or recipient is distinct from :recipient "
                "or audience is distinct from :audience or channel is distinct from :channel "
                "or channel_class is distinct from :class or format_kind is distinct from :format "
                "or interrupt is distinct from :interrupt or route_reason is distinct from :reason "
                "or priority_class is distinct from :priority or priority_rank is distinct from :rank "
                "or daily_budget is distinct from :budget "
                "or source_payload is distinct from cast(:source as jsonb) "
                "or payload is distinct from cast(:payload as jsonb) "
                "or route_plan is distinct from cast(:routes as jsonb)) returning id"),
                {"hash": execution.semantic_hash, "recipient": plan.recipient,
                 "audience": plan.audience, "channel": plan.channel,
                 "class": plan.channel_class.value, "format": plan.format_kind,
                 "interrupt": plan.interrupt, "priority": plan.priority_class.value,
                 "rank": plan.priority_rank, "band": band, "reason": plan.reason_code,
                 "routes": routes, "budget": _daily_budget(row.get("delivery_effective_config")),
                 "source": json.dumps(source, default=str), "payload": payload,
                 "now": now, "o": org_id, "id": row["id"]}).first()
            if changed is not None:
                refreshed += 1
                conn.execute(text(
                    "insert into delivery_events (event_id,org_id,delivery_id,event_type,"
                    "reason_code,actor_id,idempotency_key,metadata,occurred_at) values "
                    "(:e,:o,:d,'queued','current_route_refreshed','delivery',:key,"
                    "cast(:m as jsonb),:at) on conflict do nothing"),
                    {"e": new_id("dev"), "o": org_id, "d": row["id"],
                     "key": (f"refresh:{int(row.get('retry_generation') or 0) + 1}:"
                             f"{execution.semantic_hash}:{plan.recipient}:{plan.channel}"),
                     "m": json.dumps({"route_plan": plan.route_plan}), "at": now})
            _resolve_materialization_failure(
                conn, org_id=org_id, execution_id=str(row["execution_id"]),
                event_id=event_id, now=now)
        except (KeyError, TypeError, ValueError) as exc:
            invalid += 1
            detail = f"delivery refresh rejected: {exc}"[:300]
            conn.execute(text(
                "update delivery_outbox set status='failed_terminal',lifecycle_status='failed',"
                "last_error=:error,updated_at=:now where org_id=:o and id=:id "
                "and status='queued'"),
                {"error": detail, "now": now, "o": org_id, "id": row["id"]})
            conn.execute(text(
                "insert into delivery_events (event_id,org_id,delivery_id,event_type,reason_code,"
                "actor_id,idempotency_key,metadata,occurred_at) values "
                "(:e,:o,:d,'failed','route_refresh_rejected','delivery',:key,"
                "cast(:m as jsonb),:at) on conflict do nothing"),
                {"e": new_id("dev"), "o": org_id, "d": row["id"],
                 "key": (f"refresh-failed:{execution.semantic_hash}" if execution is not None
                         else f"refresh-failed:{now.isoformat()}"),
                 "m": json.dumps({"error_class": type(exc).__name__}), "at": now})
            _materialization_failure(
                conn, org_id=org_id, execution_id=str(row.get("execution_id") or "unknown"),
                event_id=event_id, exc=exc, now=now)
    return refreshed, invalid


def enqueue_execution_deliveries(engine, org_id: str, *,
                                 destinations: Sequence[RegisteredDestination],
                                 base_url: str = "", eval_time: datetime | None = None,
                                 limit: int = 200) -> dict[str, int]:
    """Materialise initial executions and reminder events, idempotently."""
    now = eval_time or datetime.now(timezone.utc)
    counts = {"initial": 0, "events": 0, "refreshed": 0, "invalid": 0}
    with engine.begin() as conn:
        # Account erasure takes this tenant row FOR UPDATE. Holding it FOR SHARE for the whole
        # materialisation transaction prevents a reset from returning and then having an old
        # execution resurrect its delivery row. The advisory lock also serializes two scheduler
        # instances for this org, including the legacy-row adoption path below.
        if conn.execute(text("select id from orgs where id=:o for share"),
                        {"o": org_id}).first() is None:
            return counts
        conn.execute(text(
            "select pg_advisory_xact_lock(hashtextextended(:key,0))"),
            {"key": f"delivery-materialize:{org_id}"})
        seats = _seats(conn, org_id)
        presence = _presence(conn, org_id, now)
        initial = conn.execute(text(
            "select x.*,cs.effective as delivery_effective_config from executions x "
            "left join config_snapshots cs on cs.org_id=x.org_id "
            "and cs.snapshot_id=x.config_snapshot_id "
            "where x.org_id=:o and x.closed_at is null "
            "and x.state in ('pending','running','waiting','blocked') "
            "and not exists (select 1 from execution_events superseding "
            "where superseding.org_id=x.org_id and superseding.execution_id=x.execution_id "
            "and superseding.kind in ('execution.action_completed','execution.reminded',"
            "'execution.started','execution.waiting','execution.blocked',"
            "'execution.unblocked','execution.replanned','execution.completed',"
            "'execution.cancelled','execution.expired','execution.archived')) "
            "and not exists (select 1 from delivery_outbox d where d.org_id=x.org_id "
            "and d.dedupe_key='execution:' || x.execution_id || ':initial') "
            "order by x.priority_bp desc, x.created_at, x.execution_id limit :l"),
            {"o": org_id, "l": max(1, min(int(limit), 500))}).mappings().all()
        events = conn.execute(text(
            "select e.event_id,e.reason_code,e.detail,e.occurred_at,x.*,"
            "cs.effective as delivery_effective_config "
            "from execution_events e join executions x "
            "on x.org_id=e.org_id and x.execution_id=e.execution_id "
            "left join config_snapshots cs on cs.org_id=x.org_id "
            "and cs.snapshot_id=x.config_snapshot_id "
            "where e.org_id=:o and e.kind='execution.reminded' and x.closed_at is null "
            "and x.state in ('pending','running','waiting','blocked') "
            "and not exists (select 1 from execution_events superseding "
            "where superseding.org_id=e.org_id and superseding.execution_id=e.execution_id "
            "and superseding.event_id<>e.event_id and ("
            "(superseding.kind='execution.cancelled' "
            "and superseding.reason_code='human_dismissed') or "
            "(superseding.kind='execution.reminded' and "
            "(superseding.occurred_at>e.occurred_at or "
            "(superseding.occurred_at=e.occurred_at and superseding.event_id>e.event_id))) or "
            "(superseding.occurred_at>=e.occurred_at and superseding.kind in ("
            "'execution.action_completed','execution.started','execution.waiting',"
            "'execution.blocked','execution.unblocked','execution.replanned',"
            "'execution.completed','execution.cancelled','execution.expired',"
            "'execution.archived')))) "
            "and not exists (select 1 from delivery_outbox d where d.org_id=e.org_id "
            "and d.dedupe_key='execution:' || e.execution_id || ':event:' || e.event_id) "
            "order by e.occurred_at,e.event_id limit :l"),
            {"o": org_id, "l": max(1, min(int(limit), 500))}).mappings().all()

        for row in initial:
            try:
                execution = _with_inherited_visibility(
                    conn, ExecutionObject.from_semantic_dict(_json_mapping(row["payload"])))
                if execution.execution_id != row["execution_id"]:
                    raise ValueError("stored execution identity mismatch")
                requested = _requested_audience(execution, row)
                selected_agent = _agent_recipient(
                    conn, org_id,
                    preferred=(row.get("assignee") if requested == "agent" else None))
                scoped_destinations = _destinations_for_agent(
                    conn, org_id, selected_agent, destinations)
                plan = plan_delivery(execution, seats=seats, destinations=scoped_destinations,
                                     presence_by_recipient=presence,
                                     execution_owner=row.get("assignee"),
                                     requested_audience=requested,
                                     agent_recipient=selected_agent)
                counts["initial"] += _insert(
                    conn, row=row, execution=execution, event_id=None,
                    kind="execution_initial", source=_source_for_delivery(
                        execution, row.get("card_id"), kind="execution_initial",
                        audience=plan.audience),
                    plan=plan, base_url=base_url, now=now)
                _resolve_materialization_failure(
                    conn, org_id=org_id, execution_id=str(row["execution_id"]),
                    event_id=None, now=now)
            except (KeyError, TypeError, ValueError) as exc:
                counts["invalid"] += 1
                _materialization_failure(
                    conn, org_id=org_id, execution_id=str(row.get("execution_id") or "unknown"),
                    event_id=None, exc=exc, now=now)

        for row in events:
            try:
                execution = _with_inherited_visibility(
                    conn, ExecutionObject.from_semantic_dict(_json_mapping(row["payload"])))
                if execution.execution_id != row["execution_id"]:
                    raise ValueError("stored execution identity mismatch")
                detail = _json_mapping(row.get("detail"))
                requested = _requested_audience(execution, row, detail)
                preferred_agent = ((detail.get("target_seat") or row.get("assignee"))
                                   if requested == "agent" else None)
                selected_agent = _agent_recipient(
                    conn, org_id, preferred=str(preferred_agent) if preferred_agent else None)
                scoped_destinations = _destinations_for_agent(
                    conn, org_id, selected_agent, destinations)
                plan = plan_delivery(execution, seats=seats, destinations=scoped_destinations,
                                     presence_by_recipient=presence,
                                     event_detail=detail,
                                     execution_owner=row.get("assignee"),
                                     requested_audience=requested,
                                     agent_recipient=selected_agent)
                counts["events"] += _insert(
                    conn, row=row, execution=execution, event_id=str(row["event_id"]),
                    kind="execution_reminder",
                    source=_source_for_delivery(
                        execution, row.get("card_id"), kind="execution_reminder",
                        audience=plan.audience, event_id=str(row["event_id"]),
                        reason_code=str(row["reason_code"]), detail=detail),
                    plan=plan, base_url=base_url, now=now)
                _resolve_materialization_failure(
                    conn, org_id=org_id, execution_id=str(row["execution_id"]),
                    event_id=str(row["event_id"]), now=now)
            except (KeyError, TypeError, ValueError) as exc:
                counts["invalid"] += 1
                _materialization_failure(
                    conn, org_id=org_id, execution_id=str(row.get("execution_id") or "unknown"),
                    event_id=str(row.get("event_id") or "unknown"), exc=exc, now=now)
        refreshed, invalid = _refresh_pending(
            conn, org_id=org_id, seats=seats, destinations=destinations,
            presence=presence, base_url=base_url, now=now, limit=limit)
        counts["refreshed"] += refreshed
        counts["invalid"] += invalid
    return counts


__all__ = ["DeliveryPlan", "ORCHESTRATOR_VERSION", "SURFACE_FOR_CONTEXT",
           "current_delivery_plan",
           "enqueue_execution_deliveries", "format_kind_for", "plan_delivery",
           "render_for_channel"]
