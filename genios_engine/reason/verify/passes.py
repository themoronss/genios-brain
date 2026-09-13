"""The verify post-pass — SCREEN_INTEL_P4 §3.1 (registered by group A's `run_post_passes`).

    run(engine, card_store, org_id, *, now) -> int      (situations emitted)

Two deterministic jobs, each reading only what changed since its own watermark (0154):
  1. VERIFY — every discrepancy opened or changed since the watermark (and every snooze that has
     woken) becomes one `verify` situation for the OWNER seat through `reason.team.emit.
     emit_situation`: a card (the durable copy) + a `verify` moment whose actions are
     accept / keep / snooze with the discrepancy id. Re-emitted only when the digest (held +
     challenger + recipient) changes. A discrepancy with a PRIVATE side goes only to a seat that
     may read it (`store.private_principals`) — never to an owner who may not.
  2. P-13 — duplicate outreach (`reason/moments/engagement.emit_duplicate_outreach`).
Never credit-charged (D6). A failure is logged by the caller's hook, never fails the chain.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone

from sqlalchemy import text

from genios_engine.platform.logging import get_logger
from genios_engine.reason.moments.common import value_of
from genios_engine.reason.verify import store as V

_log = get_logger("genios.verify")

PASS_ID = "verify"
TTL_SECONDS = 7 * 86400
BATCH = 200
_EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)
#: The fact that names who answers for a subject, by node type.
_OWNER_FIELDS = ("deal.owner", "commitment.owner", "contract.owner", "account.owner")


# ── watermarks (0154) ───────────────────────────────────────────────────────────────────────────
def watermark(conn, org_id: str, pass_id: str) -> datetime:
    wm = conn.execute(text("select watermark from post_pass_watermarks where org_id = :o "
                           "and pass_id = :p"), {"o": org_id, "p": pass_id}).scalar()
    if wm is None:
        return _EPOCH
    return wm if wm.tzinfo else wm.replace(tzinfo=timezone.utc)


def advance(conn, org_id: str, pass_id: str, to: datetime) -> None:
    conn.execute(text(
        "insert into post_pass_watermarks (org_id, pass_id, watermark, updated_at) "
        "values (:o, :p, :w, now()) on conflict (org_id, pass_id) do update set "
        "watermark = greatest(post_pass_watermarks.watermark, excluded.watermark), "
        "updated_at = now()"), {"o": org_id, "p": pass_id, "w": to})


# ── who hears about it ──────────────────────────────────────────────────────────────────────────
def _active_seats(conn, org_id: str) -> dict[str, str]:
    """lower(email) → seat_id for every active seat with an address."""
    return {r.e: r.seat_id for r in conn.execute(text(
        "select lower(email) as e, seat_id from org_seats where org_id = :o and active "
        "and email is not null order by created_at, seat_id"), {"o": org_id})}


def owner_seat(conn, org_id: str, subject_node_id: str, seats: dict[str, str]) -> str | None:
    """The seat that answers for the subject: its named owner (an org-visible `*.owner` fact that
    is a seat's address), else the workspace owner (the seat on `orgs.email`), else the first
    active admin."""
    for r in conn.execute(text(
            "select value from graph_facts where org_id = :o and subject_node_id = :s "
            "and field = any(:f) and valid_to is null and status = 'active' "
            "and visibility_scope is distinct from 'private'"),
            {"o": org_id, "s": subject_node_id, "f": list(_OWNER_FIELDS)}):
        key = str(value_of(r.value) or "").strip().lower()
        if key in seats:
            return seats[key]
    org_email = conn.execute(text("select lower(email) from orgs where id = :o"),
                             {"o": org_id}).scalar()
    if org_email and org_email in seats:
        return seats[org_email]
    return conn.execute(text(
        "select seat_id from org_seats where org_id = :o and active and role = 'admin' "
        "order by created_at, seat_id limit 1"), {"o": org_id}).scalar()


def recipient(conn, org_id: str, row, seats: dict[str, str]) -> str | None:
    owner = owner_seat(conn, org_id, row.subject_node_id, seats)
    allowed = V.private_principals(row)
    if allowed is None:
        return owner
    readers = sorted(seats[e] for e in allowed if e in seats)
    if owner in readers:
        return owner
    return readers[0] if readers else None          # nobody who may read it → nobody is told


# ── 1. verify ───────────────────────────────────────────────────────────────────────────────────
def compose(row, *, seat_id: str) -> dict:
    """The situation for one discrepancy — values and sources only, never a quote."""
    p = V.public(row)
    held, ch = p["held"], p["challenger"]
    field = row.field
    subject = p["subject"] or "this record"
    headline = f"Which is right? {subject}: {field}"[:300]
    body = (f"On record: {V.render_value(held['value'])}"
            + (f" ({held['source']})" if held.get("source") else "")
            + f". New: {V.render_value(ch['value'])}"
            + (f" ({ch['source']}" + (f", {ch['at'][:10]}" if ch.get("at") else "") + ")"
               if ch.get("source") else "")
            + ".")
    payload = {"discrepancy_id": row.id}
    actions = [{"id": "accept", "label": f"Use {V.render_value(ch['value'])}", "payload": payload},
               {"id": "keep", "label": f"Keep {V.render_value(held['value'])}",
                "payload": payload},
               {"id": "snooze", "label": "Ask me in a week",
                "payload": {**payload, "snooze_days": 7}}]
    evidence = [{"kind": "discrepancy", "discrepancy_id": row.id,
                 "node_id": row.subject_node_id, "field": field, "held": held,
                 "challenger": ch}]
    digest = hashlib.sha256(json.dumps(
        [row.id, held.get("value"), ch.get("value"), row.challenger_digest, seat_id],
        default=str, sort_keys=True).encode()).hexdigest()[:32]
    return {"kind": "verify", "key": f"discrepancy:{row.id}", "seat_id": seat_id,
            "subject_node_ids": [row.subject_node_id], "headline": headline, "body": body[:2000],
            "actions": actions, "evidence": evidence, "priority": "high",
            "ttl_seconds": TTL_SECONDS, "digest": digest}


def run_verify(engine, card_store, org_id: str, *, now: datetime, emit) -> int:
    with engine.begin() as c:
        # A snooze that has run out is a live question again.
        c.execute(text(
            "update discrepancies set status = 'open', updated_at = :now where org_id = :o "
            "and status = 'snoozed' and snoozed_until is not null and snoozed_until <= :now"),
            {"o": org_id, "now": now})
    with engine.connect() as c:
        wm = watermark(c, org_id, PASS_ID)
        batch = sorted(V.rows(c, org_id=org_id, status="open", extra="and d.updated_at > :wm ",
                              params={"wm": wm}, cap=BATCH),
                       key=lambda r: (r.updated_at, r.id))
        seats = _active_seats(c, org_id)
        plans = [(r, recipient(c, org_id, r, seats)) for r in batch]
    emitted, done_to = 0, None
    for row, seat_id in plans:
        if seat_id is not None:
            try:
                sit = compose(row, seat_id=seat_id)
                if emit(engine, card_store, org_id, **sit) is not None:
                    emitted += 1
            except Exception:      # noqa: BLE001 — stop here; the watermark keeps this row
                _log.exception("verify emit failed org=%s discrepancy=%s", org_id, row.id)
                break
        done_to = row.updated_at
    if done_to is not None:
        with engine.begin() as c:
            advance(c, org_id, PASS_ID, done_to)
    return emitted


def run(engine, card_store, org_id: str, *, now: datetime | None = None) -> int:
    """The registered post-pass (P4 §3.1)."""
    now = now or datetime.now(timezone.utc)
    total = 0
    try:
        from genios_engine.reason.team.emit import emit_situation
    except ImportError:         # group A's emitter not merged yet → nothing to emit through
        emit_situation = None
        _log.info("verify pass: reason.team.emit unavailable; discrepancies not announced")
    if emit_situation is not None:
        total += run_verify(engine, card_store, org_id, now=now, emit=emit_situation)
    from genios_engine.reason.moments.engagement import emit_duplicate_outreach
    total += emit_duplicate_outreach(engine, org_id, now=now)
    return total


__all__ = ["PASS_ID", "advance", "compose", "owner_seat", "recipient", "run", "run_verify",
           "watermark"]
