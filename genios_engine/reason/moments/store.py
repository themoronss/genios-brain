"""Moments persistence — the one writer of `moments`, `moment_cache`, `moment_feedback`.

PERSIST = ONE TRANSACTION: the seat's advisory lock → idempotency check → dedupe (cache) → guards
→ insert moment → `realtime_events(moment.new)` when shown (transactional outbox, plan §9.6) →
cache row. A retried request answers exactly what the first one did.

NEVER CREDIT-CHARGED (D6): nothing here touches billing.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone

from sqlalchemy import text

from genios_engine.platform import realtime
from genios_engine.reason.moments import guards as G
from genios_engine.reason.moments.common import aware, iso


class MomentConflict(Exception):
    """A moment id already taken by another seat."""


def server_moment_id(seat_id: str, request_id: str) -> str:
    return "mom_" + hashlib.sha256(f"{seat_id}|{request_id}".encode()).hexdigest()[:24]


def cache_key(*, seat_id: str, capability_id: str, subject_ids, trigger: str,
              subject_version: str) -> str:
    blob = json.dumps([seat_id, capability_id, sorted(set(subject_ids or ())), trigger,
                       subject_version], separators=(",", ":"))
    return hashlib.sha256(blob.encode()).hexdigest()


def trigger_digest(*parts) -> str:
    return hashlib.sha256(json.dumps(list(parts), default=str,
                                     separators=(",", ":")).encode()).hexdigest()[:32]


def cached(conn, key: str, now: datetime) -> dict | None:
    r = conn.execute(text("select moment from moment_cache where key = :k and expires_at > :now"),
                     {"k": key, "now": now}).first()
    if r is None:
        return None
    m = r.moment
    return json.loads(m) if isinstance(m, str) else dict(m)


def _public(moment: dict) -> dict:
    """The §6.2 response fields of a moment dict (no storage-only keys)."""
    keys = ("moment_id", "kind", "priority", "headline", "body", "actions", "evidence",
            "ttl_seconds", "capability_id", "capability_version")
    return {k: moment.get(k) for k in keys}


def persist(engine, *, org_id: str, seat_id: str, device_id: str | None, origin: str,
            moment: dict, subject_ids, now: datetime | None = None,
            key: str | None = None) -> dict:
    """Store `moment` (the §6.2 shape) and decide whether it is shown. Returns the moment with
    `display` and `reason`. Raises MomentConflict when the id belongs to another seat."""
    now = now or datetime.now(timezone.utc)
    ttl = int(moment.get("ttl_seconds") or 900)
    shown = False
    with engine.begin() as c:
        G.lock_seat(c, org_id, seat_id)
        prior = c.execute(text(
            "select org_id, seat_id, display, suppressed_reason from moments where moment_id = :m"),
            {"m": moment["moment_id"]}).first()
        if prior is not None:
            if (prior.org_id, prior.seat_id) != (org_id, seat_id):
                raise MomentConflict(moment["moment_id"])
            return {**_public(moment), "display": bool(prior.display),
                    "reason": prior.suppressed_reason}
        if key:
            hit = cached(c, key, now)
            if hit is not None:
                return {**_public(hit), "display": False, "reason": G.DUPLICATE}
        state = G.load_state(c, org_id=org_id, seat_id=seat_id, device_id=device_id, now=now)
        display, reason = G.decide(state, kind=moment["kind"], priority=moment["priority"],
                                   now=now)
        c.execute(text(
            "insert into moments (moment_id, org_id, seat_id, device_id, origin, kind, priority, "
            "capability_id, capability_version, subject_node_ids, headline, body, actions, "
            "evidence, display, suppressed_reason, created_at, expires_at) values "
            "(:m, :o, :s, :d, :origin, :kind, :prio, :cap, :capv, cast(:subj as text[]), :h, :b, "
            "cast(:a as jsonb), cast(:e as jsonb), :disp, :why, :now, :exp)"),
            {"m": moment["moment_id"], "o": org_id, "s": seat_id, "d": device_id,
             "origin": origin, "kind": moment["kind"], "prio": moment["priority"],
             "cap": moment["capability_id"], "capv": str(moment["capability_version"]),
             "subj": sorted(set(subject_ids or ())), "h": moment["headline"],
             "b": moment.get("body"), "a": json.dumps(moment.get("actions") or []),
             "e": json.dumps(moment.get("evidence") or []), "disp": display, "why": reason,
             "now": now, "exp": now + timedelta(seconds=ttl)})
        out = {**_public(moment), "display": display, "reason": reason}
        if display:
            realtime.publish(c, org_id=org_id, seat_id=seat_id, kind="moment.new",
                             payload={**out, "seat_id": seat_id, "origin": origin,
                                      "device_id": device_id, "created_at": iso(now)})
            shown = True
        if key:
            c.execute(text(
                "insert into moment_cache (key, org_id, seat_id, moment, expires_at) "
                "values (:k, :o, :s, cast(:m as jsonb), :exp) on conflict (key) do update set "
                "moment = excluded.moment, expires_at = excluded.expires_at"),
                {"k": key, "o": org_id, "s": seat_id, "m": json.dumps(_public(moment)),
                 "exp": now + timedelta(seconds=ttl)})
    if shown:
        realtime.wake()
    return out


def record_feedback(engine, *, org_id: str, seat_id: str, actor: str | None, moment_id: str,
                    action: str, reason: str | None, at: datetime) -> dict | None:
    """Store one feedback action; also into L6's `learning_event_inbox` (0046), idempotently, and
    announce it (`moment.updated`) so the seat's other devices drop a dismissed toast. None when
    the moment is not this seat's."""
    at = aware(at)
    with engine.begin() as c:
        m = c.execute(text(
            "select capability_id, capability_version from moments "
            "where moment_id = :m and org_id = :o and seat_id = :s"),
            {"m": moment_id, "o": org_id, "s": seat_id}).first()
        if m is None:
            return None
        new = c.execute(text(
            "insert into moment_feedback (org_id, moment_id, seat_id, capability_id, action, "
            "reason, at) values (:o, :m, :s, :cap, :a, :r, :at) "
            "on conflict (moment_id, action, at) do nothing returning 1"),
            {"o": org_id, "m": moment_id, "s": seat_id, "cap": m.capability_id, "a": action,
             "r": reason, "at": at}).first() is not None
        if new:
            payload = {"kind": "moment_feedback", "moment_id": moment_id, "seat_id": seat_id,
                       "capability_id": m.capability_id,
                       "capability_version": m.capability_version, "action": action,
                       "reason": reason, "at": iso(at)}
            ref = f"moment_feedback:{moment_id}:{action}:{iso(at)}"
            c.execute(text(
                "insert into learning_event_inbox (org_id, event_id, actor, source_ref, "
                "visibility_scope, visibility, payload, observed_at) values "
                "(:o, :e, :actor, :ref, 'private', cast(:vis as jsonb), cast(:p as jsonb), now()) "
                "on conflict do nothing"),
                {"o": org_id, "e": "momfb_" + hashlib.sha256(ref.encode()).hexdigest()[:32],
                 "actor": actor or seat_id, "ref": ref,
                 "vis": json.dumps({"scope": "private", "principals": [actor or seat_id]}),
                 "p": json.dumps(payload)})
            if action != "shown":
                realtime.publish(c, org_id=org_id, seat_id=seat_id, kind="moment.updated",
                                 payload={"moment_id": moment_id, "feedback": action,
                                          "at": iso(at)})
    if new and action != "shown":
        realtime.wake()
    return {"moment_id": moment_id, "action": action, "recorded": new}


def moment_out(r) -> dict:
    created, expires = aware(r["created_at"]), aware(r["expires_at"])
    return {"moment_id": r["moment_id"], "kind": r["kind"], "priority": r["priority"],
            "headline": r["headline"], "body": r["body"], "actions": r["actions"] or [],
            "evidence": r["evidence"] or [],
            "ttl_seconds": int((expires - created).total_seconds()),
            "capability_id": r["capability_id"], "capability_version": r["capability_version"],
            "origin": r["origin"], "subject_node_ids": list(r["subject_node_ids"] or []),
            "display": bool(r["display"]), "reason": r["suppressed_reason"],
            "created_at": iso(created), "expires_at": iso(expires), "feedback": r["feedback"]}


def history(engine, *, org_id: str, seat_id: str, limit: int = 50,
            before: datetime | None = None, kind: str | None = None) -> dict:
    """§2.6 (pinned): the seat's own moments, newest first, with the last feedback action."""
    limit = max(1, min(int(limit or 50), 200))
    with engine.connect() as c:
        rows = c.execute(text(
            "select m.*, fb.action as feedback from moments m left join lateral ("
            "select f.action from moment_feedback f where f.moment_id = m.moment_id "
            "order by f.at desc, f.created_at desc limit 1) fb on true "
            "where m.org_id = :o and m.seat_id = :s "
            "and (cast(:before as timestamptz) is null or m.created_at < cast(:before as timestamptz)) "
            "and (cast(:kind as text) is null or m.kind = cast(:kind as text)) "
            "order by m.created_at desc, m.moment_id desc limit :n"),
            {"o": org_id, "s": seat_id, "before": before, "kind": kind, "n": limit + 1}
        ).mappings().all()
    more = len(rows) > limit
    items = [moment_out(r) for r in rows[:limit]]
    return {"moments": items, "next_before": items[-1]["created_at"] if more and items else None}


def purge_expired(engine, *, now: datetime | None = None, batch: int = 5000,
                  max_batches: int = 20) -> dict:
    """Retention (maintenance heartbeat): expired cache rows; moments older than their org's
    capture `retention_days` (90 without a policy row) — a moment names counterparties and is
    derived from captured content, so it keeps the capture clock. Feedback cascades."""
    now = now or datetime.now(timezone.utc)
    with engine.begin() as c:
        cache_n = c.execute(text("delete from moment_cache where expires_at < :now"),
                            {"now": now}).rowcount or 0
    deleted = 0
    for _ in range(max_batches):
        with engine.begin() as c:
            n = c.execute(text(
                "delete from moments t using (select m.moment_id from moments m "
                "left join capture_policies p on p.org_id = m.org_id "
                "where m.created_at < :now - make_interval(days => coalesce(p.retention_days, 90)) "
                "limit :n) v where t.moment_id = v.moment_id"), {"now": now, "n": batch}
            ).rowcount or 0
        deleted += n
        if n < batch:
            break
    return {"moment_cache": cache_n, "moments": deleted}


__all__ = ["MomentConflict", "cache_key", "cached", "history", "moment_out", "persist",
           "purge_expired", "record_feedback", "server_moment_id", "trigger_digest"]
