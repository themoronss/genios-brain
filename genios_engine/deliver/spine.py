"""Layer 5.2 · Phase 3 — the durable outbox spine (Delivery Outbox manager, section 5.1).

The Atlas's durable heart. A hash-verified execution and its fully resolved v2 plan become **one
tenant-scoped logical row plus an append-only ``queued`` event in one transaction** — no adapter
is ever called inline. A later worker claims that row with ``FOR UPDATE SKIP LOCKED`` and an
expiring fencing token; the physical ``started`` attempt commits with the attention reservation
*before* any network I/O, so a crash can never create an invisible provider call. A malformed
frozen object lands in ``delivery_materialization_failures`` rather than crashing all tenants.

The only Layer 5.2 module besides the API that touches SQL; every statement names real 0043
columns and binds authenticated ``org_id``.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import text

from genios_engine.contracts.delivery import DeliveryLifecycle, DeliveryObject
from genios_engine.platform.canonical import canonical_dumps
from genios_engine.platform.ids import new_id
from .scheduler import rank_sql


def logical_dedupe_key(org_id: str, execution_id: str, event_kind: str) -> str:
    """The deterministic logical key that makes ten destinations one delivery.

    Keyed on the *source* (execution + which of its events this is — initial vs a specific
    reminder/escalation), never on the route. Two workers materialising the same event compute the
    same key, and the ``(org_id, dedupe_key)`` unique index elects one winner.
    """
    return f"{execution_id}:{event_kind}"


def log_delivery_event(conn, *, org_id: str, delivery_id: str, kind: str, at: datetime,
                       actor: str | None = None, idempotency_key: str | None = None,
                       detail: dict | None = None) -> str:
    """Append one lifecycle fact. Idempotency key (when given) makes a repeated receipt a no-op.

    Only a keyed event carries the conflict clause — the partial unique index covers exactly the
    ``idempotency_key is not null`` rows, so an unkeyed system event (a materialiser ``queued``, a
    worker ``failed``) is a plain append with nothing to collide with.
    """
    event_id = new_id("dev")
    params = {"id": event_id, "o": org_id, "d": delivery_id, "k": kind, "at": at, "actor": actor,
              "idem": idempotency_key, "detail": canonical_dumps(detail or {})}
    insert = ("insert into delivery_events (id, org_id, delivery_id, kind, occurred_at, actor, "
              "idempotency_key, detail) values (:id, :o, :d, :k, :at, :actor, :idem, :detail)")
    if idempotency_key is not None:
        insert += (" on conflict (org_id, delivery_id, idempotency_key) "
                   "where idempotency_key is not null do nothing")
    conn.execute(text(insert), params)
    return event_id


def materialize(conn, obj: DeliveryObject, *, at: datetime, card_id: str | None = None,
                payload: dict | None = None) -> bool:
    """Insert one logical delivery + its ``queued`` event atomically. Idempotent on the dedupe key.

    Returns True if this call materialised the delivery, False if an equal logical delivery already
    existed (the deduper's one-winner guarantee). No adapter is called; a worker drains it later.
    """
    result = conn.execute(text(
        "insert into delivery_outbox "
        "(id, org_id, delivery_id, card_id, channel, payload, status, attempts, created_at, "
        " next_attempt_at, recipient, band, channel_class, interrupt, execution_id, "
        " execution_hash, audience, destination, fmt, priority, daily_budget, source, "
        " route_ladder, route_cursor, retry_generation, lifecycle, dedupe_key, "
        " authority_expires_at, legacy_reconcile) "
        "values (:id, :o, :did, :card, :ch, :pl, 'queued', 0, :at, :at, :rcp, :band, :cc, :intr, "
        " :ex, :exh, :aud, :dst, :fmt, :pri, :budget, :src, :ladder, :cur, :rg, 'queued', :dk, "
        " :authexp, false) "
        "on conflict (org_id, dedupe_key) where dedupe_key is not null and legacy_reconcile = false "
        "do nothing"),
        {"id": new_id("dobx"), "o": obj.org_id, "did": obj.delivery_id, "card": card_id,
         "ch": obj.live_channel, "pl": canonical_dumps(payload or {}), "at": at,
         "rcp": obj.recipient, "band": obj.band, "cc": obj.channel_class.value,
         "intr": obj.channel_class.value == "chat", "ex": obj.execution_id,
         "exh": obj.execution_hash, "aud": obj.audience.value, "dst": obj.destination,
         "fmt": obj.fmt.value, "pri": obj.priority.value, "budget": obj.daily_budget,
         "src": canonical_dumps(dict(obj.source)), "ladder": canonical_dumps(list(obj.route_ladder)),
         "cur": obj.route_cursor, "rg": obj.retry_generation, "dk": obj.dedupe_key,
         "authexp": obj.authority_expires_at})
    if result.rowcount != 1:
        return False
    log_delivery_event(conn, org_id=obj.org_id, delivery_id=obj.delivery_id,
                       kind=DeliveryLifecycle.QUEUED.value, at=at, actor="materializer")
    return True


def record_materialization_failure(conn, *, org_id: str, execution_id: str | None,
                                   reason_code: str, at: datetime, detail: dict | None = None) -> str:
    """A frozen object we could not turn into a delivery. Visible to ops, never silently dropped."""
    fid = new_id("dmf")
    conn.execute(text(
        "insert into delivery_materialization_failures "
        "(id, org_id, execution_id, reason_code, detail, created_at) "
        "values (:id, :o, :ex, :rc, :detail, :at)"),
        {"id": fid, "o": org_id, "ex": execution_id, "rc": reason_code,
         "detail": canonical_dumps(detail or {}), "at": at})
    return fid


def claim_due(conn, *, org_id: str, worker_id: str, at: datetime, limit: int = 20,
              lease_seconds: int = 300) -> list[dict]:
    """Claim due, unclaimed rows with an expiring fencing token — the multi-worker safe path.

    ``FOR UPDATE SKIP LOCKED`` means two workers never fight over the same row; a claim whose lease
    has passed is reclaimable. Sets ``claimed_by``/``claim_expires_at``/``fence_token`` so the
    later ``started`` attempt can prove it still owns the row before touching the network.
    """
    fence = new_id("fence")
    rows = conn.execute(text(
        "with due as ("
        "  select id from delivery_outbox "
        # The mirror of the legacy drain's `dedupe_key is null`: this claimer must not be able to
        # pick up a row the legacy path wrote, or the two workers can send the same card twice.
        "  where org_id = :o and status = 'queued' and legacy_reconcile = false "
        "    and dedupe_key is not null "
        "    and (next_attempt_at is null or next_attempt_at <= :at) "
        "    and (claimed_by is null or claim_expires_at < :at) "
        # NOT `order by priority` — that column is text, so Postgres sorted it alphabetically
        # (background < critical < high < low < medium) and claimed critical work after
        # background work. The rank is generated from contracts.delivery._PRIORITY_RANK and
        # carries the same 4-hour starvation aging as the in-process scheduler.
        "  order by " + rank_sql("priority", "created_at", ":at") + " desc, created_at "
        "  for update skip locked limit :lim) "
        "update delivery_outbox d set claimed_by = :w, claim_expires_at = :exp, fence_token = :f "
        "from due where d.id = due.id "
        "returning d.id, d.delivery_id, d.execution_id, d.channel, d.route_ladder, "
        "          d.route_cursor, d.retry_generation, d.fence_token"),
        {"o": org_id, "at": at, "lim": limit, "w": worker_id,
         "exp": at + timedelta(seconds=lease_seconds), "f": fence}).mappings().all()
    return [dict(r) for r in rows]


def recover_expired_claims(conn, *, at: datetime) -> int:
    """Mark the unfinished attempt of an expired claim ``unknown`` before anyone reclaims the row.

    An expired worker may have POSTed to a provider before dying; we must never silently retry over
    that ambiguity. Attempts with no settle time under an expired claim become ``unknown``; the row
    itself is freed for a fresh claim by ``claim_due`` (its expired lease no longer protects it).
    """
    result = conn.execute(text(
        "update delivery_attempts a set outcome = 'unknown', settled_at = :at "
        "from delivery_outbox d "
        "where a.org_id = d.org_id and a.delivery_id = d.delivery_id "
        "  and a.outcome = 'started' and a.settled_at is null "
        "  and d.claim_expires_at is not null and d.claim_expires_at < :at "
        "  and a.claim_token = d.fence_token"),
        {"at": at})
    return result.rowcount


__all__ = ["claim_due", "log_delivery_event", "logical_dedupe_key", "materialize",
           "recover_expired_claims", "record_materialization_failure"]
