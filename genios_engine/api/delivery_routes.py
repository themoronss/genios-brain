"""Layer 5.2's control surface — the dial a tenant actually reaches for.

The delivery gate is only as good as the settings it reads, and until this router existed those
settings could only be written with raw SQL.  A quiet-hours table nobody can edit is not a
feature; it is dead schema that makes the product look like it ignores people.

The original four admission controls still live here:

  ``GET  …/delivery/preferences``   what is stored, at every specificity.
  ``PUT  …/delivery/preferences``   set or change one row.
  ``GET  …/delivery/effective``     **what will actually happen to me, and when.**
  ``GET  …/delivery/held``          what the gate is sitting on right now, and why.

Atlas alignment adds leased recipient context, typed delivery-object/result reads, authenticated
pull-surface inboxes and deterministic analytics. They remain projections of the same outbox
ledger rather than creating a second source of truth.

``/effective`` runs the real resolver and the real units against a real instant and reports the
verdict for every band.  It is the same instinct as ``POST /channels/slack/test``: "did my
setting work?" should be a button, not a support ticket.  Without it a tenant sets quiet hours,
sees nothing change for eleven hours, and cannot distinguish "working" from "broken".

**Two responses to bad configuration, and that asymmetry is deliberate.**  ``build_context``
*degrades* — one tenant's typo must never stop another tenant's mail draining.  This router
*refuses*: it writes, re-resolves inside the same transaction, and rolls back if the result
would degrade.  Same predicate, opposite responses, each correct for its layer — the engine
cannot afford to fail, and the form field cannot afford to lie.  The consequence is the one
that matters: a setting that survives a ``PUT`` is a setting that will actually take effect.

**Authority.**  Reads take ``get_current_org``; writes take ``require_owner``, because a rule
written at ``('*','*')`` silences an entire tenant and a scoped key must not be able to reach
it.  Both already exist in ``platform/auth.py`` — no third auth model is invented here, which is
how two of them would start disagreeing.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel, Field
from sqlalchemy import text

from genios_engine.contracts.delivery import BAND_ORDER, DeliveryCandidate
from genios_engine.deliver.gate import (
    WILDCARD,
    PgDeliveryContext,
    channel_class_for,
    evaluate_delivery,
)
from genios_engine.deliver.presence import ActivityKind, Presence
from genios_engine.deliver.results import load_delivery, load_inbox, load_results
from genios_engine.platform.auth import AuthCtx, get_current_org, require_owner, require_scope
from genios_engine.platform.wiring import make_graph_store

router = APIRouter()
_graph = make_graph_store()

#: The settable columns, and the only strings ever interpolated into a statement here. Every
#: write is keyed off this tuple rather than off the request body, so a field a client invents
#: cannot reach the SQL.
_SETTABLE: tuple[str, ...] = (
    "delivery_enabled", "hold_until", "min_band", "opted_out",
    "tz_name", "quiet_enabled", "quiet_start_hour", "quiet_end_hour", "quiet_weekends",
    "max_interrupts_per_hour", "override_band")


def _org(org_id: str, org: str = Depends(get_current_org)) -> str:
    if org_id != org:
        raise HTTPException(403, "org mismatch")
    return org


def _require_db():
    if _graph is None:
        raise HTTPException(400, "delivery preferences need a configured database")


def _moment(value: str | None) -> datetime:
    """Parse the caller's "pretend it is now" instant, defaulting to actual now.

    Requires an offset. A naive instant would be silently read as UTC, and a tenant in Kolkata
    testing "does 21:30 wake me?" would get an answer about a completely different moment —
    which is worse than an error, because they would believe it.
    """
    if not value:
        return datetime.now(timezone.utc)
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise HTTPException(422, f"at must be an ISO-8601 instant: {exc}") from exc
    if parsed.tzinfo is None:
        raise HTTPException(422, "at must carry a UTC offset (e.g. 2026-08-07T02:00:00+05:30)")
    return parsed


# ── read: what is stored ──────────────────────────────────────────────────────────────
@router.get("/api/org/{org_id}/delivery/preferences")
def list_preferences(org_id: str, org: str = Depends(_org)) -> dict:
    """Every rule this tenant has, most specific first — the shape the settings screen renders."""
    _require_db()
    with _graph.engine.connect() as c:
        rows = c.execute(text(
            "select * from delivery_preferences where org_id=:o "
            "order by (seat_id <> :any) desc, (channel <> :any) desc, seat_id, channel"),
            {"o": org, "any": WILDCARD}).mappings().all()
    return {"preferences": [_public(dict(row)) for row in rows], "wildcard": WILDCARD}


def _public(row: dict[str, Any]) -> dict[str, Any]:
    out = {"seat_id": row.get("seat_id"), "channel": row.get("channel"),
           "scope": _scope(row.get("seat_id"), row.get("channel"))}
    for column in _SETTABLE:
        value = row.get(column)
        out[column] = value.isoformat() if isinstance(value, datetime) else value
    updated = row.get("updated_at")
    out["updated_at"] = updated.isoformat() if isinstance(updated, datetime) else None
    out["updated_by"] = row.get("updated_by")
    return out


def _scope(seat: Any, channel: Any) -> str:
    """A human name for the row's specificity, so a settings screen never has to explain '*'."""
    seated, channelled = str(seat) != WILDCARD, str(channel) != WILDCARD
    if seated and channelled:
        return "seat_channel"
    if seated:
        return "seat"
    if channelled:
        return "org_channel"
    return "org"


# ── read: what will actually happen ───────────────────────────────────────────────────
@router.get("/api/org/{org_id}/delivery/effective")
def effective_preferences(org_id: str, org: str = Depends(_org),
                          seat_id: str | None = Query(None),
                          channel: str = Query("slack"),
                          at: str | None = Query(None)) -> dict:
    """Resolve the rules for one person on one channel, and say what happens to each band.

    The verdicts are produced by the same functions the drain calls, against the same resolver,
    at the instant the caller names. Not a simulation of the gate — the gate, asked a question.
    A second code path here would be a second set of answers, and the one people would trust is
    whichever one they saw last.
    """
    _require_db()
    now = _moment(at)
    seat = seat_id or WILDCARD
    if channel == WILDCARD:
        # "What happens on every channel at once?" is not a well-formed question — the answer
        # differs per adapter, which is the whole reason channel_class exists. Naming one is a
        # smaller ask than returning an answer that is only true for some of them.
        from genios_engine.deliver.channels.base import supported_channels
        raise HTTPException(422, f"channel must be a concrete adapter, one of {supported_channels()}")
    with _graph.engine.connect() as conn:
        resolver = PgDeliveryContext(conn)
        probe = _probe(org, seat, channel, band=BAND_ORDER[0], interrupt=False)
        context = resolver.resolve(probe, now=now)
        verdicts = {}
        for band in BAND_ORDER:
            for interrupt in (False, True):
                subject = _probe(org, seat, channel, band=band, interrupt=interrupt)
                decision = evaluate_delivery(subject, context, now=now)
                verdicts[f"{band}{'_interrupt' if interrupt else ''}"] = {
                    "verdict": decision.verdict.value,
                    "unit": decision.unit,
                    "reason_code": decision.reason_code,
                    "not_before": (decision.not_before.isoformat()
                                   if decision.not_before else None)}

    resolved = context.to_semantic_dict()
    return {"at": now.isoformat(), "seat_id": seat, "channel": channel,
            "scope": _scope(seat, channel),
            "channel_class": channel_class_for(channel).value,
            "resolved": resolved,
            "local_time": now.astimezone(context.profile.zone).isoformat(),
            "in_quiet_hours": context.profile.is_quiet(now.astimezone(context.profile.zone)),
            "verdicts": verdicts,
            "config_error": context.config_error}


def _probe(org: str, seat: str, channel: str, *, band: str,
           interrupt: bool) -> DeliveryCandidate:
    """A candidate that stands for "a message like this", used only to ask the gate a question.

    ``channel`` must be a concrete adapter. ``'*'`` is a *scope* in the preferences table, never
    a route a message can travel on, and the contract refuses it — correctly, because a delivery
    that names no channel is not a delivery. Callers with a wildcard rule expand it first.
    """
    return DeliveryCandidate(
        org_id=org, subject_id=f"probe:{band}", channel=channel,
        channel_class=channel_class_for(channel), band=band, interrupt=interrupt,
        recipient=None if seat == WILDCARD else seat)


def _governed_channels(channel: str) -> tuple[str, ...]:
    """The concrete adapters a rule at this specificity actually governs.

    A wildcard rule applies to all of them, so validating it means validating it against each —
    a setting that is harmless for the digest can still be broken for chat, and the tenant would
    only find out at 03:00. One adapter ships today, which makes this loop a no-op now and the
    correct shape the day a second one lands.
    """
    if channel != WILDCARD:
        return (channel,)
    from genios_engine.deliver.channels.base import supported_channels
    return supported_channels()


# ── write ─────────────────────────────────────────────────────────────────────────────
class PreferenceUpdate(BaseModel):
    """One row's worth of settings.

    Only fields the caller actually sent are written, which is what makes an explicit ``null``
    mean *clear this and inherit again* while an omitted field means *leave it alone*. Collapsing
    those two would make it impossible to remove an override without deleting the whole row and
    re-typing every other setting on it.
    """

    seat_id: str = Field(WILDCARD)
    channel: str = Field(WILDCARD)
    delivery_enabled: bool | None = None
    hold_until: datetime | None = None
    min_band: str | None = None
    opted_out: bool | None = None
    tz_name: str | None = None
    quiet_enabled: bool | None = None
    quiet_start_hour: int | None = None
    quiet_end_hour: int | None = None
    quiet_weekends: bool | None = None
    max_interrupts_per_hour: int | None = None
    override_band: str | None = None


@router.put("/api/org/{org_id}/delivery/preferences")
def set_preferences(org_id: str, body: PreferenceUpdate,
                    ctx: AuthCtx = Depends(require_owner)) -> dict:
    """Write one rule — and refuse it if the *resolved* result would not be usable.

    The check is on the resolution, not on the body, and that distinction is the whole point.
    A row is legal in isolation and still broken in combination: a seat that sets
    ``quiet_start_hour=9`` against an org row whose ``quiet_end_hour`` is also 9 produces the
    ambiguous all-day window the engine has to degrade around. Writing, re-resolving and rolling
    back inside one transaction is what makes "it saved" mean "it will take effect".
    """
    _require_db()
    if org_id != ctx.org_id:
        raise HTTPException(403, "org mismatch")
    org = ctx.org_id
    if body.hold_until is not None and body.hold_until.tzinfo is None:
        raise HTTPException(422, "hold_until must carry a UTC offset")

    provided = [name for name in _SETTABLE if name in body.model_fields_set]
    if not provided:
        raise HTTPException(422, f"send at least one of {list(_SETTABLE)}")

    seat, channel = (body.seat_id or WILDCARD).strip(), (body.channel or WILDCARD).strip()
    if not seat or not channel:
        raise HTTPException(422, "seat_id and channel must be non-empty ('*' for all)")

    columns = ", ".join(provided)
    placeholders = ", ".join(f":{name}" for name in provided)
    assignments = ", ".join(f"{name}=excluded.{name}" for name in provided)
    params: dict[str, Any] = {name: getattr(body, name) for name in provided}
    params.update({"o": org, "seat": seat, "ch": channel, "by": ctx.actor_id})

    with _graph.engine.begin() as conn:
        conn.execute(text("select id from orgs where id=:o for update"), {"o": org})
        conn.execute(text(
            f"insert into delivery_preferences (org_id, seat_id, channel, {columns}, updated_by) "
            f"values (:o, :seat, :ch, {placeholders}, :by) "
            "on conflict (org_id, seat_id, channel) do update set "
            f"{assignments}, updated_by=excluded.updated_by, updated_at=now()"),
            params)

        # Re-resolve inside the transaction. The engine degrades bad settings so the drain
        # survives; this surface refuses them so they are never written in the first place.
        # Raising unwinds `engine.begin()`, which rolls back the insert above — the tenant is
        # left exactly as they were rather than half-configured into a degraded state.
        # This resolver shares the mutation transaction so the just-written rule is validated.
        # It must not call rollback between reads or it would discard the upsert being checked.
        resolver = PgDeliveryContext(conn, release_between=False)
        now = datetime.now(timezone.utc)
        for concrete in _governed_channels(channel):
            context = resolver.resolve(
                _probe(org, seat, concrete, band=BAND_ORDER[0], interrupt=False), now=now)
            if context.config_error:
                raise HTTPException(422, context.config_error)

    return {"saved": True, "seat_id": seat, "channel": channel, "scope": _scope(seat, channel),
            "set": provided}


@router.delete("/api/org/{org_id}/delivery/preferences/{seat_id}/{channel}")
def clear_preferences(org_id: str, seat_id: str, channel: str,
                      ctx: AuthCtx = Depends(require_owner)) -> dict:
    """Drop a whole rule so its settings inherit from the level above again."""
    _require_db()
    if org_id != ctx.org_id:
        raise HTTPException(403, "org mismatch")
    with _graph.engine.begin() as conn:
        conn.execute(text("select id from orgs where id=:o for update"), {"o": ctx.org_id})
        result = conn.execute(text(
            "delete from delivery_preferences where org_id=:o and seat_id=:seat "
            "and channel=:ch"), {"o": ctx.org_id, "seat": seat_id, "ch": channel})
    return {"deleted": int(result.rowcount or 0), "seat_id": seat_id, "channel": channel}


# ── read: what the gate is holding ────────────────────────────────────────────────────
@router.get("/api/org/{org_id}/delivery/held")
def held_messages(org_id: str, org: str = Depends(_org),
                  limit: int = Query(50, ge=1, le=200)) -> dict:
    """Everything the gate stopped or is sitting on, with the unit and reason that did it.

    The answer to "why didn't I get told about that?", which is asked far more often — and far
    more angrily — than "why did I get told about that?". It reads the row rather than a log,
    because by the time anybody asks, the clock has moved on and the log has rotated.
    """
    _require_db()
    with _graph.engine.connect() as conn:
        rows = conn.execute(text(
            "select card_id, channel, recipient, band, channel_class, interrupt, status, "
            "defer_count, gate_unit, gate_reason, next_attempt_at, created_at, last_error "
            "from delivery_outbox where org_id=:o "
            "and (status='suppressed' or (status='queued' and defer_count > 0)) "
            "order by created_at desc limit :l"),
            {"o": org, "l": limit}).mappings().all()

    held = []
    for row in rows:
        held.append({
            "card_id": row["card_id"], "channel": row["channel"],
            "recipient": row["recipient"], "band": row["band"],
            "channel_class": row["channel_class"], "interrupt": bool(row["interrupt"]),
            "status": row["status"], "defer_count": int(row["defer_count"] or 0),
            "held_by": row["gate_unit"], "reason_code": row["gate_reason"],
            "retryable": row["status"] == "queued",
            "next_attempt_at": (row["next_attempt_at"].isoformat()
                                if row["next_attempt_at"] else None),
            "created_at": row["created_at"].isoformat() if row["created_at"] else None})
    return {"held": held,
            "deferred": sum(1 for item in held if item["status"] == "queued"),
            "suppressed": sum(1 for item in held if item["status"] == "suppressed")}


# ── live delivery context ─────────────────────────────────────────────────────────────
class PresenceUpdate(BaseModel):
    """A leased context signal from a browser, app, extension or agent surface."""

    seat_id: str
    activity: ActivityKind = ActivityKind.UNKNOWN
    surface: str = "unknown"
    focus_mode: bool = False
    busy_until: datetime | None = None
    ttl_seconds: int = Field(300, ge=30, le=3600)
    metadata: dict[str, Any] = Field(default_factory=dict)


@router.put("/api/org/{org_id}/delivery/context")
def set_delivery_context(org_id: str, body: PresenceUpdate,
                         ctx: AuthCtx = Depends(
                             require_scope("delivery.context.write"))) -> dict:
    """Publish a short lease; scoped credentials may address only their own agent identity."""
    _require_db()
    if org_id != ctx.org_id:
        raise HTTPException(403, "org mismatch")
    _bind_presence_identity(ctx, body.seat_id)
    now = datetime.now(timezone.utc)
    expires = now + timedelta(seconds=body.ttl_seconds)
    busy = body.busy_until
    if busy is not None:
        if busy.tzinfo is None:
            raise HTTPException(422, "busy_until must carry a UTC offset")
        busy = min(busy.astimezone(timezone.utc), expires)
    try:
        presence = Presence(org_id=ctx.org_id, seat_id=body.seat_id,
                            activity=body.activity, surface=body.surface,
                            focus_mode=body.focus_mode, observed_at=now,
                            expires_at=expires, busy_until=busy)
    except (TypeError, ValueError) as exc:
        raise HTTPException(422, str(exc)) from exc
    import json
    with _graph.engine.begin() as conn:
        conn.execute(text("select id from orgs where id=:o for update"), {"o": ctx.org_id})
        conn.execute(text(
            "insert into delivery_presence (org_id, seat_id, activity, surface, focus_mode, "
            "busy_until, observed_at, expires_at, metadata) "
            "values (:o,:s,:a,:surface,:focus,:busy,:observed,:expires,cast(:meta as jsonb)) "
            "on conflict (org_id, seat_id) do update set activity=excluded.activity, "
            "surface=excluded.surface, focus_mode=excluded.focus_mode, "
            "busy_until=excluded.busy_until, observed_at=excluded.observed_at, "
            "expires_at=excluded.expires_at, metadata=excluded.metadata, updated_at=now()"),
            {"o": presence.org_id, "s": presence.seat_id,
             "a": presence.activity.value, "surface": presence.surface,
             "focus": presence.focus_mode, "busy": presence.busy_until,
             "observed": presence.observed_at, "expires": presence.expires_at,
             "meta": json.dumps(body.metadata, default=str)})
    return jsonable_encoder(presence.to_semantic_dict())


@router.get("/api/org/{org_id}/delivery/context/{seat_id}")
def get_delivery_context(org_id: str, seat_id: str,
                         ctx: AuthCtx = Depends(require_scope("delivery.read"))) -> dict:
    _require_db()
    if org_id != ctx.org_id:
        raise HTTPException(403, "org mismatch")
    _bind_presence_identity(ctx, seat_id)
    with _graph.engine.connect() as conn:
        row = conn.execute(text(
            "select org_id, seat_id, activity, surface, focus_mode, busy_until, observed_at, "
            "expires_at from delivery_presence where org_id=:o and seat_id=:s"),
            {"o": ctx.org_id, "s": seat_id}).mappings().first()
    if row is None:
        raise HTTPException(404, "no delivery context for seat")
    from genios_engine.deliver.presence import presence_from_row
    presence = presence_from_row(dict(row))
    now = datetime.now(timezone.utc)
    return {**jsonable_encoder(presence.to_semantic_dict()), "active": presence.active_at(now),
            "effective_busy_until": jsonable_encoder(presence.effective_busy_until(now))}


def _bind_presence_identity(ctx: AuthCtx, seat_id: str) -> None:
    """Owners manage all seats; scoped callers are self-bound to an authenticated agent id."""
    if ctx.scopes is not None and (not ctx.agent_id or seat_id != ctx.agent_id):
        raise HTTPException(403, "scoped client may access only its own delivery context")


@router.delete("/api/org/{org_id}/delivery/context/{seat_id}")
def clear_delivery_context(org_id: str, seat_id: str,
                           ctx: AuthCtx = Depends(require_owner)) -> dict:
    _require_db()
    if org_id != ctx.org_id:
        raise HTTPException(403, "org mismatch")
    with _graph.engine.begin() as conn:
        conn.execute(text("select id from orgs where id=:o for update"), {"o": ctx.org_id})
        result = conn.execute(text(
            "delete from delivery_presence where org_id=:o and seat_id=:s"),
            {"o": ctx.org_id, "s": seat_id})
    return {"deleted": int(result.rowcount or 0), "seat_id": seat_id}


# ── typed output, pull surfaces and analytics ─────────────────────────────────────────
@router.get("/api/org/{org_id}/delivery/results")
def delivery_results(org_id: str, org: str = Depends(_org),
                     channel: str | None = Query(None),
                     limit: int = Query(100, ge=1, le=500)) -> dict:
    _require_db()
    with _graph.engine.connect() as conn:
        results = load_results(conn, org, channel=channel, limit=limit)
    return {"results": jsonable_encoder([item.to_semantic_dict() for item in results])}


@router.get("/api/org/{org_id}/delivery/results/{delivery_id}")
def delivery_result(org_id: str, delivery_id: str, org: str = Depends(_org)) -> dict:
    _require_db()
    with _graph.engine.connect() as conn:
        pair = load_delivery(conn, org, delivery_id)
    if pair is None:
        raise HTTPException(404, "delivery not found")
    delivery, result = pair
    return jsonable_encoder({"delivery": delivery.to_semantic_dict(),
                             "result": result.to_semantic_dict()})


@router.get("/api/org/{org_id}/delivery/inbox")
def delivery_inbox(org_id: str,
                   ctx: AuthCtx = Depends(require_scope("delivery.read")),
                   channel: str = Query("in_app"), recipient: str | None = Query(None),
                   limit: int = Query(100, ge=1, le=500)) -> dict:
    """Pull surface for app, dashboard, API, extension and mobile clients."""
    _require_db()
    from genios_engine.deliver.channels.surface import SURFACE_CHANNELS
    if org_id != ctx.org_id:
        raise HTTPException(403, "org mismatch")
    if channel not in SURFACE_CHANNELS:
        raise HTTPException(422, f"channel must be a pull surface: {sorted(SURFACE_CHANNELS)}")
    if ctx.scopes is not None:
        if not ctx.agent_id or recipient != ctx.agent_id:
            raise HTTPException(403, "scoped client must request only its own recipient inbox")
        if channel != "api":
            raise HTTPException(403, "scoped agent inbox is available only on the API surface")
    with _graph.engine.connect() as conn:
        rows = load_inbox(conn, ctx.org_id, channel=channel, recipient=recipient,
                          include_org_wide=ctx.scopes is None,
                          audience="agent" if ctx.scopes is not None else None,
                          limit=limit)
    return {"deliveries": jsonable_encoder([
        {"delivery": delivery.to_semantic_dict(), "result": result.to_semantic_dict()}
        for delivery, result in rows])}


@router.get("/api/org/{org_id}/delivery/analytics")
def delivery_analytics(org_id: str, org: str = Depends(_org),
                       days: int = Query(28, ge=1, le=365)) -> dict:
    _require_db()
    from genios_engine.deliver.analytics import load_analytics
    with _graph.engine.connect() as conn:
        report = load_analytics(conn, org, days=days)
    return jsonable_encoder(report)


# ── lifecycle receipts and operations ─────────────────────────────────────────────────
class DeliveryEventUpdate(BaseModel):
    event_type: str
    idempotency_key: str = Field(min_length=1, max_length=192)
    reason_code: str | None = None
    occurred_at: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


@router.post("/api/org/{org_id}/delivery/results/{delivery_id}/events")
def record_delivery_event(org_id: str, delivery_id: str, body: DeliveryEventUpdate,
                          ctx: AuthCtx = Depends(
                              require_scope("delivery.receipts.write"))) -> dict:
    """Record a client-observed lifecycle receipt, idempotently and in order."""
    _require_db()
    if org_id != ctx.org_id:
        raise HTTPException(403, "org mismatch")
    from genios_engine.deliver.tracker import (
        DeliveryState,
        DeliveryTransitionError,
        append_event,
    )
    allowed = {"viewed", "ignored", "accepted", "executed", "failed"}
    if body.event_type not in allowed:
        raise HTTPException(422, f"event_type must be one of {sorted(allowed)}")
    if body.occurred_at is not None and body.occurred_at.tzinfo is None:
        raise HTTPException(422, "occurred_at must carry a UTC offset")
    try:
        with _graph.engine.begin() as conn:
            delivery_row = conn.execute(text(
                "select recipient,audience,channel from delivery_outbox "
                "where org_id=:o and id=:d for update"),
                {"o": ctx.org_id, "d": delivery_id}).first()
            if delivery_row is None:
                raise HTTPException(404, "delivery not found")
            recipient = (delivery_row.recipient if hasattr(delivery_row, "recipient")
                         else delivery_row[0])
            audience = (delivery_row.audience if hasattr(delivery_row, "audience")
                        else delivery_row[1])
            channel = (delivery_row.channel if hasattr(delivery_row, "channel")
                       else delivery_row[2])
            if ctx.scopes is not None and (
                    not ctx.agent_id or recipient != ctx.agent_id
                    or audience != "agent" or channel not in {"agent", "api"}):
                raise HTTPException(403, "scoped client may receipt only its own agent delivery")
            result = append_event(
                conn, org_id=ctx.org_id, delivery_id=delivery_id,
                target=DeliveryState(body.event_type),
                reason_code=body.reason_code or f"client_{body.event_type}",
                actor_id=ctx.actor_id or "org_owner",
                idempotency_key=body.idempotency_key,
                occurred_at=body.occurred_at,
                metadata=body.metadata)
    except DeliveryTransitionError as exc:
        status = 404 if str(exc) == "delivery not found" else 409
        raise HTTPException(status, str(exc)) from exc
    return jsonable_encoder(result)


@router.get("/api/org/{org_id}/delivery/results/{delivery_id}/attempts")
def delivery_attempts(org_id: str, delivery_id: str, org: str = Depends(_org)) -> dict:
    _require_db()
    with _graph.engine.connect() as conn:
        rows = conn.execute(text(
            "select attempt_id,attempt_number,channel,outcome,retryable,provider_message_id,"
            "http_status,retry_after_seconds,error_class,detail,started_at,completed_at "
            "from delivery_attempts where org_id=:o and delivery_id=:d "
            "order by attempt_number"), {"o": org, "d": delivery_id}).mappings().all()
    return {"attempts": jsonable_encoder([dict(row) for row in rows])}


@router.get("/api/org/{org_id}/delivery/dead-letters")
def delivery_dead_letters(org_id: str, org: str = Depends(_org),
                          limit: int = Query(100, ge=1, le=500)) -> dict:
    _require_db()
    with _graph.engine.connect() as conn:
        rows = conn.execute(text(
            "select id,execution_id,card_id,recipient,channel,priority_class,attempts,control_failures,"
            "last_error,updated_at,exists (select 1 from delivery_attempts unsafe "
            "where unsafe.org_id=delivery_outbox.org_id "
            "and unsafe.delivery_id=delivery_outbox.id "
            "and unsafe.outcome in ('started','unknown','delivered')) "
            "or legacy_reconciliation_required "
            "as ambiguous_transport_evidence from delivery_outbox where org_id=:o "
            "and status='failed_terminal' order by updated_at desc,id limit :l"),
            {"o": org, "l": limit}).mappings().all()
        materialization = conn.execute(text(
            "select execution_id,execution_event_id,error_class,detail,occurrences,"
            "first_seen_at,last_seen_at from delivery_materialization_failures where org_id=:o "
            "and resolved_at is null order by last_seen_at desc,execution_id limit :l"),
            {"o": org, "l": limit}).mappings().all()
    return {"dead_letters": jsonable_encoder([dict(row) for row in rows]),
            "materialization_failures": jsonable_encoder(
                [dict(row) for row in materialization])}


class DeliveryReplayRequest(BaseModel):
    acknowledge_ambiguous_delivery_risk: bool = False


@router.post("/api/org/{org_id}/delivery/results/{delivery_id}/replay")
def replay_delivery(org_id: str, delivery_id: str,
                    body: DeliveryReplayRequest | None = None,
                    ctx: AuthCtx = Depends(require_owner)) -> dict:
    """Owner-controlled replay; ambiguous transport requires an explicit risk acknowledgement."""
    _require_db()
    if org_id != ctx.org_id:
        raise HTTPException(403, "org mismatch")
    from genios_engine.deliver.tracker import DeliveryState, DeliveryTransitionError, append_event
    now = datetime.now(timezone.utc)
    try:
        with _graph.engine.begin() as conn:
            row = conn.execute(text(
                "select status,channel,delivery_kind,legacy_reconciliation_required "
                "from delivery_outbox "
                "where org_id=:o and id=:d for update"),
                {"o": ctx.org_id, "d": delivery_id}).mappings().first()
            if row is None:
                raise HTTPException(404, "delivery not found")
            if row["status"] != "failed_terminal":
                raise HTTPException(409, "only a failed_terminal delivery can be replayed")
            unsafe = conn.execute(text(
                "select outcome,attempt_number from delivery_attempts where org_id=:o "
                "and delivery_id=:d and outcome in ('started','unknown','delivered') "
                "order by attempt_number desc limit 1 for share"),
                {"o": ctx.org_id, "d": delivery_id}).mappings().first()
            legacy_unsafe = bool(row.get("legacy_reconciliation_required"))
            ambiguous = unsafe is not None or legacy_unsafe
            acknowledged = bool(body and body.acknowledge_ambiguous_delivery_risk)
            if ambiguous and not acknowledged:
                raise HTTPException(409, {
                    "error": "ambiguous_delivery_replay_requires_acknowledgement",
                    "message": "The provider may already have delivered this item. Inspect the "
                               "attempt ledger, then explicitly acknowledge duplicate-delivery "
                               "risk before replaying.",
                    "outcome": (str(unsafe["outcome"]) if unsafe is not None
                                else "legacy_cutover_unknown"),
                })
            replay_reason = ("owner_forced_ambiguous_replay" if ambiguous
                             else "owner_replay")
            append_event(conn, org_id=ctx.org_id, delivery_id=delivery_id,
                         target=DeliveryState.QUEUED, reason_code=replay_reason,
                         actor_id=ctx.actor_id or "org_owner",
                         idempotency_key=f"replay:{now.isoformat()}", occurred_at=now,
                         metadata={"ambiguous_risk_acknowledged": acknowledged})
            conn.execute(text(
                "update delivery_outbox set status='queued',next_attempt_at=:now,last_error=null,"
                "retry_generation=retry_generation+:bump,generation_attempts=0,control_failures=0,"
                "legacy_reconciliation_required=false,"
                "manual_replay_approved_at=case when :legacy then :now "
                "else manual_replay_approved_at end,claim_token=null,"
                "claimed_at=null,claimed_until=null,updated_at=:now where org_id=:o and id=:d"),
                {"now": now, "o": ctx.org_id, "d": delivery_id,
                 # Preserve the stable receiver idempotency key for ACK-loss recovery. A
                 # definite non-delivery starts a fresh route generation.
                 "legacy": legacy_unsafe,
                 "bump": 0 if unsafe is not None else 1})
    except DeliveryTransitionError as exc:
        raise HTTPException(409, str(exc)) from exc
    return {"replayed": True, "delivery_id": delivery_id,
            "ambiguous_risk_acknowledged": bool(
                body and body.acknowledge_ambiguous_delivery_risk)}


@router.get("/api/org/{org_id}/delivery/capabilities")
def delivery_capabilities(org_id: str, org: str = Depends(_org)) -> dict:
    _require_db()
    from genios_engine.deliver.units import delivery_runtime, delivery_units
    with _graph.engine.connect() as conn:
        runtime = delivery_runtime(conn, org)
    return {"units": [
        {"key": item.key, "engine_ready": item.engine_ready,
         "operational": bool(runtime.get(item.key)),
         "available_channels": list(item.available_channels),
         "configured_channels": list(runtime.get(item.key, ())),
         "integration_required": list(item.integration_required)}
        for item in delivery_units()]}


__all__ = ["router"]
