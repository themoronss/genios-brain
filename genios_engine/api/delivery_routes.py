"""Layer 5.2's control surface — the dial a tenant actually reaches for.

The delivery gate is only as good as the settings it reads, and until this router existed those
settings could only be written with raw SQL.  A quiet-hours table nobody can edit is not a
feature; it is dead schema that makes the product look like it ignores people.

Four things live here, and the third is the one that earns the file:

  ``GET  …/delivery/preferences``   what is stored, at every specificity.
  ``PUT  …/delivery/preferences``   set or change one row.
  ``GET  …/delivery/effective``     **what will actually happen to me, and when.**
  ``GET  …/delivery/held``          what the gate is sitting on right now, and why.

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

import json
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import text

from genios_engine.contracts.delivery import BAND_ORDER, DeliveryCandidate, DeliveryLifecycle
from genios_engine.deliver.gate import (
    WILDCARD,
    PgDeliveryContext,
    channel_class_for,
    evaluate_delivery,
)
from genios_engine.deliver.scheduler import rank_sql
from genios_engine.executive.communication import CHAT_CHANNELS
from genios_engine.platform.auth import AuthCtx, get_current_org, require_owner
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
        raise HTTPException(422, f"channel must be a concrete adapter, one of {CHAT_CHANNELS}")
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
    return tuple(CHAT_CHANNELS) or ("slack",)


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
        resolver = PgDeliveryContext(conn)
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
                      org: str = Depends(_org)) -> dict:
    """Drop a whole rule so its settings inherit from the level above again."""
    _require_db()
    with _graph.engine.begin() as conn:
        result = conn.execute(text(
            "delete from delivery_preferences where org_id=:o and seat_id=:seat "
            "and channel=:ch"), {"o": org, "seat": seat_id, "ch": channel})
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


# =======================================================================================
# Layer 5.2 control-plane surface (v2 DeliveryObject / lifecycle / analytics / capabilities).
# Every read is org-scoped in SQL before LIMIT so a hidden row cannot distort a count or a page.
# =======================================================================================

_RESULT_COLS = ("delivery_id, execution_id, recipient, audience, channel, channel_class, fmt, "
                "priority, band, lifecycle, status, route_ladder, route_cursor, retry_generation, "
                "created_at, delivered_at, viewed_at, accepted_at, executed_at, ignored_at")


@router.get("/api/org/{org_id}/delivery/results")
def list_results(org_id: str, org: str = Depends(_org),
                 lifecycle: str | None = Query(None), limit: int = Query(50, le=200)) -> dict:
    _require_db()
    where = "org_id = :o and delivery_id is not null"
    params: dict[str, Any] = {"o": org, "l": limit}
    if lifecycle is not None:
        where += " and lifecycle = :lc"
        params["lc"] = lifecycle
    with _graph.engine.connect() as c:
        rows = c.execute(text(f"select {_RESULT_COLS} from delivery_outbox where {where} "
                              "order by created_at desc limit :l"), params).mappings().all()
    return {"count": len(rows), "results": [_result_row(r) for r in rows]}


@router.get("/api/org/{org_id}/delivery/results/{delivery_id}")
def get_result(org_id: str, delivery_id: str, org: str = Depends(_org)) -> dict:
    _require_db()
    with _graph.engine.connect() as c:
        row = c.execute(text(f"select {_RESULT_COLS} from delivery_outbox "
                             "where org_id = :o and delivery_id = :d"),
                        {"o": org, "d": delivery_id}).mappings().first()
        if row is None:
            raise HTTPException(404, "no such delivery")
        events = c.execute(text("select kind, occurred_at, actor from delivery_events "
                                "where org_id = :o and delivery_id = :d order by occurred_at"),
                           {"o": org, "d": delivery_id}).mappings().all()
    return {**_result_row(row), "events": [dict(e) for e in events]}


@router.get("/api/org/{org_id}/delivery/results/{delivery_id}/attempts")
def get_attempts(org_id: str, delivery_id: str, org: str = Depends(_org)) -> dict:
    _require_db()
    with _graph.engine.connect() as c:
        rows = c.execute(text(
            "select channel, retry_generation, attempt_no, outcome, provider_status, "
            "started_at, settled_at from delivery_attempts "
            "where org_id = :o and delivery_id = :d order by started_at"),
            {"o": org, "d": delivery_id}).mappings().all()
    return {"delivery_id": delivery_id, "attempts": [dict(r) for r in rows]}


class ReceiptBody(BaseModel):
    lifecycle: str = Field(..., description="viewed | ignored | accepted | executed | delivered")
    idempotency_key: str | None = None


@router.post("/api/org/{org_id}/delivery/results/{delivery_id}/events")
def record_receipt(org_id: str, delivery_id: str, body: ReceiptBody,
                   org: str = Depends(_org)) -> dict:
    """Record an engagement receipt. Idempotent by ``idempotency_key``; chronology-validated."""
    _require_db()
    from genios_engine.deliver.tracker import (ChronologyError, IllegalTransition,
                                               record_transition)
    try:
        target = DeliveryLifecycle(body.lifecycle)
    except ValueError:
        raise HTTPException(422, f"unknown lifecycle {body.lifecycle!r}")
    now = datetime.now(timezone.utc)
    try:
        with _graph.engine.begin() as c:
            moved = record_transition(c, org_id=org, delivery_id=delivery_id, target=target,
                                      at=now, now=now, actor="client",
                                      idempotency_key=body.idempotency_key)
    except IllegalTransition as exc:
        raise HTTPException(409, str(exc))
    except ChronologyError as exc:
        raise HTTPException(422, str(exc))
    return {"recorded": moved, "delivery_id": delivery_id, "lifecycle": body.lifecycle}


@router.get("/api/org/{org_id}/delivery/inbox")
def inbox(org_id: str, org: str = Depends(_org), limit: int = Query(50, le=200)) -> dict:
    """The durable pull surface — open deliveries a client polls for."""
    _require_db()
    with _graph.engine.connect() as c:
        rows = c.execute(text(
            f"select {_RESULT_COLS} from delivery_outbox where org_id = :o "
            "and delivery_id is not null and lifecycle in ('queued','deferred','delivered','viewed') "
            # Same rank as the claimer, generated from the same map. `priority` is a text column,
            # so ordering by it directly sorts alphabetically — background < critical < high <
            # low < medium — and with limit defaulting to 50 a critical delivery could be pushed
            # off the page by background rows. Two surfaces over the same table disagreeing about
            # what "most important first" means is worse than either ordering alone.
            "order by " + rank_sql("priority", "created_at", ":now") + " desc, created_at "
            "limit :l"), {"o": org, "l": limit,
                          "now": datetime.now(timezone.utc)}).mappings().all()
    return {"count": len(rows), "inbox": [_result_row(r) for r in rows]}


@router.get("/api/org/{org_id}/delivery/dead-letters")
def dead_letters(org_id: str, org: str = Depends(_org)) -> dict:
    """Terminal transport failures + unresolved materialization failures — nothing invisible."""
    _require_db()
    with _graph.engine.connect() as c:
        failed = c.execute(text(
            "select delivery_id, execution_id, channel, last_error, created_at "
            "from delivery_outbox where org_id = :o and (status = 'failed' or lifecycle = 'failed') "
            "order by created_at desc limit 100"), {"o": org}).mappings().all()
        matfail = c.execute(text(
            "select id, execution_id, reason_code, created_at from delivery_materialization_failures "
            "where org_id = :o and resolved_at is null order by created_at desc limit 100"),
            {"o": org}).mappings().all()
    return {"terminal_failures": [dict(r) for r in failed],
            "materialization_failures": [dict(r) for r in matfail]}


@router.get("/api/org/{org_id}/delivery/analytics")
def analytics(org_id: str, org: str = Depends(_org), days: int = Query(7, le=90)) -> dict:
    _require_db()
    from datetime import timedelta
    from genios_engine.deliver.analytics import delivery_analytics, recipient_fatigue
    since = datetime.now(timezone.utc) - timedelta(days=days)
    with _graph.engine.connect() as c:
        report = delivery_analytics(c, org_id=org, since=since)
        report["fatigue"] = recipient_fatigue(c, org_id=org, since=since)
    return report


@router.get("/api/org/{org_id}/delivery/capabilities")
def capabilities(org_id: str, org: str = Depends(_org)) -> dict:
    """Fail-closed capability truth per unit: engine_ready / operational / integration_required."""
    _require_db()
    from genios_engine.deliver.units import capability_report
    with _graph.engine.connect() as c:
        configured = {r[0] for r in c.execute(text(
            "select channel from org_channels where org_id = :o and active"), {"o": org})}
        # NOT `secret_ciphertext is not null`. A row can hold a value that no longer decrypts —
        # a rotated GENIOS_CRYPTO_KEY, a truncated copy, a hand-edited row — and the null check
        # reported all three as credentialed. The tenant is then told the channel is operational
        # and finds out otherwise when a real delivery fails at 2am. Decrypt it and check its
        # shape, which is the only question "is this credential usable" actually asks.
        rows = c.execute(text(
            "select channel, secret_ciphertext, config from org_channels "
            "where org_id = :o and active"), {"o": org}).all()
    # Sealed first; plaintext `config` as the documented rolling-migration fallback (0043's own
    # note: "Existing plaintext config stays as a rolling-migration fallback until rotated").
    # Ignoring the fallback swapped one wrong answer for another: the sealed column has NO
    # writer anywhere in the codebase, so `credentialed` was permanently empty and the surface
    # reported `credential_unusable` for a Slack channel that demonstrably delivers — the send
    # path (outbox.py) reads `config`, so the capability probe must ask the SAME store or the
    # two surfaces contradict each other about the same channel.
    credentialed = {ch for ch, blob, cfg in rows
                    if _credential_usable(ch, blob) or _plaintext_credential_usable(ch, cfg)}
    return {"units": capability_report(configured_channels=configured,
                                       credentialed_channels=credentialed)}


def _plaintext_credential_usable(channel: str, cfg) -> bool:
    """The rolling-migration fallback: the same `config` JSONB the send path actually uses.

    Same shape check as the sealed path, so "usable" means one thing. Removed when a sealing
    writer + backfill land and `secret_ciphertext` becomes the only store."""
    if not cfg:
        return False
    cfg = cfg if isinstance(cfg, dict) else json.loads(cfg or "{}")
    secret = cfg.get("webhook_url") or cfg.get("token") or cfg.get("secret") or ""
    return _credential_shape_ok(channel, str(secret))


def _credential_usable(channel: str, ciphertext: str | None) -> bool:
    """Does this sealed credential decrypt AND look like what the channel needs?

    Fail-closed on every error path: an unusable credential must never read as usable, and the
    three ways it becomes unusable (missing key, undecryptable blob, wrong shape) are all
    exceptions rather than falsy values.
    """
    if not ciphertext:
        return False
    from genios_engine.platform.config import get_settings
    from genios_engine.platform.crypto import decrypt
    key = getattr(get_settings(), "crypto_key", None)
    if not key:
        return False
    try:
        secret = decrypt(ciphertext.encode() if isinstance(ciphertext, str) else ciphertext, key)
    except Exception:      # noqa: BLE001 — any decrypt failure is an unusable credential
        return False
    return _credential_shape_ok(channel, secret)


def _credential_shape_ok(channel: str, secret: str) -> bool:
    """The minimum shape check per channel. Deliberately shallow — this answers "could this
    plausibly be the right kind of secret", not "will the provider accept it"; only a send probe
    answers the second, and pretending otherwise is how the null check got here."""
    secret = (secret or "").strip()
    if not secret:
        return False
    if channel == "slack":
        return secret.startswith("https://hooks.slack.com/")
    if channel in ("webhook", "agent_push", "api"):
        return secret.startswith(("http://", "https://")) or len(secret) >= 16
    return len(secret) >= 8


def _result_row(row: dict[str, Any]) -> dict[str, Any]:
    import json
    ladder = row.get("route_ladder")
    if isinstance(ladder, str):
        try:
            ladder = json.loads(ladder)
        except Exception:  # noqa: BLE001
            ladder = None
    out = {k: (v.isoformat() if isinstance(v, datetime) else v) for k, v in dict(row).items()}
    out["route_ladder"] = ladder
    return out


__all__ = ["router"]
