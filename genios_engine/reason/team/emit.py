"""emit_situation — one team/verify situation → card + moment + `team_situations` row, ONE transaction
(SCREEN_INTEL_P4 §3.1, frozen; group A owns, group B calls).

    emit_situation(engine, card_store, org_id, *, kind, key, seat_id, subject_node_ids, headline,
                   body, actions, evidence, priority="high", ttl_seconds, digest)
        -> (card_id, moment_id) | None

Re-emits only when `digest` changes; None when it did not (a rerun of the chain writes nothing).

THE CARD PATH, AND WHY IT IS NOT `CardStore.insert_card`. `insert_card` writes only under a
`card_build_claims` lease on a signal that carries a complete Layer 4 authority chain (reasoning
run, selected candidate, capability snapshot, config snapshot, pack) and re-proves that chain in
its own transaction. A deterministic post-pass has no L4 run; minting one would forge exactly the
authority those joins exist to check. So the cheapest CORRECT path is a `signals` row of the
situation's own (`rule_id` = the capability, no reasoning run, `reason_code` = kind) and the card
written directly beside it — same `cards` columns, same `card_events` log, `card_id` stable across
re-emits (refreshed in place while nobody has touched it; a fresh card only once the user already
decided the previous one). CONSEQUENCE, stated: `CardStore.queue()` joins the L4 authority chain,
so these cards are NOT in the app queue until that read learns a branch for authority-free cards;
they are readable by id, via `team_situations`, in history, and through the moment's `open_card`.

THE MOMENT is the durable card's toast: the same guards as every moment (shadow, DND, quiet hours,
rate caps — `reason/moments/guards.py`) decide `display`; a suppressed toast is still stored and
the card is written either way. `realtime_events(moment.new)` rides the same transaction.

NEVER CREDIT-CHARGED: nothing here touches billing.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from typing import Iterable

from sqlalchemy import text

from genios_engine.platform import realtime
from genios_engine.platform.ids import new_id
from genios_engine.reason.moments import guards as G
from genios_engine.reason.moments.common import iso

KINDS = ("team", "verify")
PRIORITIES = ("low", "normal", "high", "critical")
BUILDER_VERSION = "team.emit.v1"
CARD_TTL_DAYS = 7
#: cards DDL (0008): headline ≤ 60, situation ≤ 140 — validated at render for L4 cards; clipped here.
HEADLINE_MAX, SITUATION_MAX = 60, 140
MOMENT_HEADLINE_MAX, MOMENT_BODY_MAX = 300, 2000
_BAND = {"low": "standard", "normal": "standard", "high": "high", "critical": "critical"}
_SCORE = {"low": 40, "normal": 55, "high": 75, "critical": 90}
_REFRESHABLE = ("built", "queued", "surfaced")


def _h(*parts) -> str:
    return hashlib.sha256(json.dumps(list(parts), default=str, separators=(",", ":"))
                          .encode()).hexdigest()


def clip(value, limit: int) -> str:
    s = " ".join(str(value or "").split())
    return s if len(s) <= limit else s[:limit - 1].rstrip() + "…"


def card_url(card_id: str) -> str:
    """Where a person opens the durable card (pinned §3.4: `<dashboard_url>/dashboard/cards?card=`)."""
    from genios_engine.platform.config import get_settings
    base = str(getattr(get_settings(), "dashboard_url", "") or "").rstrip("/")
    return f"{base}/dashboard/cards?card={card_id}"


def _with_open_card(actions: Iterable[dict] | None, card_id: str) -> list[dict]:
    """The caller's actions (≤ 7) + the pinned `open_card` action, always last, always present —
    a caller-supplied `open_card` is replaced so the payload shape cannot drift."""
    out = [dict(a) for a in (actions or ()) if isinstance(a, dict) and a.get("id") != "open_card"]
    return out[:7] + [{"id": "open_card",
                       "payload": {"card_id": card_id, "url": card_url(card_id)}}]


def emit_situation(engine, card_store, org_id: str, *, kind: str, key: str, seat_id: str,
                   subject_node_ids, headline: str, body: str | None, actions, evidence,
                   priority: str = "high", ttl_seconds: int, digest: str,
                   capability_id: str | None = None, now: datetime | None = None,
                   expires_at: datetime | None = None) -> tuple[str, str] | None:
    """See the module docstring. `capability_id`, `now` and `expires_at` are optional extensions
    (defaults: `<kind>.situation`, the wall clock, now + 7 d for the card)."""
    if kind not in KINDS:
        raise ValueError(f"kind must be one of {KINDS}")
    if priority not in PRIORITIES:
        raise ValueError(f"priority must be one of {PRIORITIES}")
    if not key or not seat_id or not digest:
        raise ValueError("key, seat_id and digest are required")
    now = now or datetime.now(timezone.utc)
    capability = capability_id or f"{kind}.situation"
    subjects = sorted({str(s) for s in (subject_node_ids or ()) if s})
    evidence = [dict(e) for e in (evidence or ()) if isinstance(e, dict)][:20]
    card_exp = expires_at or now + timedelta(days=CARD_TTL_DAYS)
    ttl = max(60, min(int(ttl_seconds or 900), 86400))
    shown = False
    with engine.begin() as c:
        c.execute(text("select pg_advisory_xact_lock(hashtextextended(:k, 0))"),
                  {"k": f"team_situations:{org_id}:{kind}:{key}"})
        G.lock_seat(c, org_id, seat_id)
        held = c.execute(text(
            "select digest, card_id from team_situations "
            "where org_id = :o and kind = :k and key = :key"),
            {"o": org_id, "k": kind, "key": key}).first()
        if held is not None and held.digest == digest:
            return None
        card_id = _write_card(
            c, org_id=org_id, kind=kind, key=key, seat_id=seat_id, subjects=subjects,
            headline=headline, body=body, actions=actions, evidence=evidence, priority=priority,
            capability=capability, digest=digest, now=now, expires_at=card_exp,
            held_card_id=held.card_id if held is not None else None)
        moment_id, shown = _write_moment(
            c, org_id=org_id, kind=kind, key=key, seat_id=seat_id, subjects=subjects,
            headline=headline, body=body, actions=_with_open_card(actions, card_id),
            evidence=evidence, priority=priority, capability=capability, digest=digest, now=now,
            ttl=ttl, card_id=card_id)
        c.execute(text(
            "insert into team_situations (org_id, kind, key, subject_node_ids, seat_id, digest, "
            "card_id, moment_id, state, first_at, last_at) values (:o, :k, :key, "
            "cast(:subj as text[]), :s, :d, :card, :mom, 'open', :now, :now) "
            "on conflict (org_id, kind, key) do update set subject_node_ids = "
            "excluded.subject_node_ids, seat_id = excluded.seat_id, digest = excluded.digest, "
            "card_id = excluded.card_id, moment_id = excluded.moment_id, state = 'open', "
            "last_at = excluded.last_at"),
            {"o": org_id, "k": kind, "key": key, "subj": subjects, "s": seat_id, "d": digest,
             "card": card_id, "mom": moment_id, "now": now})
    if shown:
        realtime.wake()
    return card_id, moment_id


def _log_card_event(c, card_id: str, org_id: str, kind: str, cause: str, detail: dict) -> None:
    c.execute(text(
        "insert into card_events (id, card_id, org_id, kind, cause, actor_id, detail) "
        "values (:id, :cid, :o, :k, :cause, 'system', cast(:d as jsonb))"),
        {"id": new_id("cev"), "cid": card_id, "o": org_id, "k": kind, "cause": cause,
         "d": json.dumps(detail, default=str)})


def _write_card(c, *, org_id, kind, key, seat_id, subjects, headline, body, actions, evidence,
                priority, capability, digest, now, expires_at, held_card_id) -> str:
    card_actions = json.dumps([dict(a) for a in (actions or ()) if isinstance(a, dict)][:8],
                              default=str)
    why = json.dumps(evidence, default=str)
    head, sit = clip(headline, HEADLINE_MAX), clip(body or headline, SITUATION_MAX)
    band, score = _BAND[priority], _SCORE[priority]
    if held_card_id:
        # Refresh IN PLACE while nobody has decided anything about the card (the CardStore rule:
        # presentation only; state, snooze and history untouched).
        refreshed = c.execute(text(
            "update cards set assignee = :seat, urgency_band = :band, headline = :head, "
            "situation = :sit, score = :score, actions = cast(:act as jsonb), "
            "why = cast(:why as jsonb), expires_at = greatest(expires_at, :exp), "
            "builder_version = :bver where card_id = :id and org_id = :o "
            "and state = any(:refreshable) and resolved_at is null returning signal_id"),
            {"seat": seat_id, "band": band, "head": head, "sit": sit, "score": score,
             "act": card_actions, "why": why, "exp": expires_at, "bver": BUILDER_VERSION,
             "id": held_card_id, "o": org_id, "refreshable": list(_REFRESHABLE)}).first()
        if refreshed is not None:
            c.execute(text(
                "update signals set evidence = cast(:ev as jsonb), score = :score, "
                "eval_time = :now where signal_id = :sig and org_id = :o"),
                {"ev": why, "score": score, "now": now, "sig": refreshed.signal_id, "o": org_id})
            _log_card_event(c, held_card_id, org_id, "card.rebuilt", capability,
                            {"digest": digest, "builder_version": BUILDER_VERSION})
            return held_card_id
    # First emission, or the user already decided the previous card: a new generation.
    signal_id = "sig_team_" + _h(org_id, kind, key, digest)[:28]
    c.execute(text(
        "insert into signals (signal_id, org_id, rule_id, rule_version, level, subject_node_id, "
        "score, score_inputs, reason_code, evidence, status, eval_time, capability_id, "
        "capability_version) values (:sig, :o, :rule, 1, 'observation', :subj, :score, "
        "'{}'::jsonb, :reason, cast(:ev as jsonb), 'open', :now, :rule, '1') "
        "on conflict (signal_id) do nothing"),
        {"sig": signal_id, "o": org_id, "rule": capability,
         "subj": subjects[0] if subjects else key, "score": score, "reason": kind, "ev": why,
         "now": now})
    card_id = new_id("card")
    row = c.execute(text(
        "insert into cards (card_id, signal_id, org_id, assignee, domain, level, urgency_band, "
        "headline, situation, score, score_block, actions, why, context_tags, render_mode, "
        "template_version, capability_key, capability_version, builder_version, state, "
        "expires_at) values (:id, :sig, :o, :seat, :dom, 'observation', :band, :head, :sit, "
        ":score, '{}'::jsonb, cast(:act as jsonb), cast(:why as jsonb), '{}', 'template', "
        ":tv, :cap, '1', :bver, 'queued', :exp) on conflict (signal_id) do nothing "
        "returning card_id"),
        {"id": card_id, "sig": signal_id, "o": org_id, "seat": seat_id, "dom": kind,
         "band": band, "head": head, "sit": sit, "score": score, "act": card_actions,
         "why": why, "tv": f"{capability}@1", "cap": capability, "bver": BUILDER_VERSION,
         "exp": expires_at}).first()
    if row is None:        # the same generation already carded (a retried emit)
        return c.execute(text("select card_id from cards where signal_id = :s and org_id = :o"),
                         {"s": signal_id, "o": org_id}).scalar()
    _log_card_event(c, card_id, org_id, "card.created", capability,
                    {"band": band, "render_mode": "template", "situation_key": key})
    return card_id


def _write_moment(c, *, org_id, kind, key, seat_id, subjects, headline, body, actions, evidence,
                  priority, capability, digest, now, ttl, card_id) -> tuple[str, bool]:
    moment_id = "mom_" + _h(seat_id, kind, key, digest)[:24]
    if c.execute(text("select 1 from moments where moment_id = :m"),
                 {"m": moment_id}).first() is not None:
        return moment_id, False
    state = G.load_state(c, org_id=org_id, seat_id=seat_id, device_id=None, now=now)
    display, reason = G.decide(state, kind=kind, priority=priority, now=now)
    head = clip(headline, MOMENT_HEADLINE_MAX)
    text_body = clip(body, MOMENT_BODY_MAX) if body else None
    c.execute(text(
        "insert into moments (moment_id, org_id, seat_id, device_id, origin, kind, priority, "
        "capability_id, capability_version, subject_node_ids, headline, body, actions, evidence, "
        "display, suppressed_reason, created_at, expires_at, card_id) values (:m, :o, :s, null, "
        "'server', :kind, :prio, :cap, '1', cast(:subj as text[]), :h, :b, cast(:a as jsonb), "
        "cast(:e as jsonb), :disp, :why, :now, :exp, :card)"),
        {"m": moment_id, "o": org_id, "s": seat_id, "kind": kind, "prio": priority,
         "cap": capability, "subj": subjects, "h": head, "b": text_body,
         "a": json.dumps(actions, default=str), "e": json.dumps(evidence, default=str),
         "disp": display, "why": reason, "now": now, "exp": now + timedelta(seconds=ttl),
         "card": card_id})
    if display:
        realtime.publish(c, org_id=org_id, seat_id=seat_id, kind="moment.new", payload={
            "moment_id": moment_id, "kind": kind, "priority": priority, "headline": head,
            "body": text_body, "actions": actions, "evidence": evidence, "ttl_seconds": ttl,
            "capability_id": capability, "capability_version": "1", "display": True,
            "reason": None, "seat_id": seat_id, "origin": "server", "device_id": None,
            "card_id": card_id, "subject_node_ids": subjects, "created_at": iso(now)})
    return moment_id, bool(display)


__all__ = ["BUILDER_VERSION", "KINDS", "clip", "emit_situation"]
