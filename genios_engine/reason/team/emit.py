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

THE CARD CONTRACT FIRST (STEP-14, `yc2_w27_s14` M43.C4.L-integration.V1.U03; s14-F10). This writer runs no renderer and
no validator — production's *"Which is right? Maria Exconde: party.role"* was one of its cards. Before anything is
written, the words the card AND its moment show pass `contracts/card_contract` against the situation's own evidence:
no internal field name or unfilled slot, no money unless its evidence holds money, no quote that is not its
evidence's words (a clipped quote is still its words), no number or date its evidence does not hold. Refused: no
card, no moment, no situation row — `None`, counted per rule in `counts` (`refused_contract:<rule>`) and logged.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timedelta, timezone
from typing import Iterable

from sqlalchemy import text

from genios_engine.contracts import card_contract
from genios_engine.platform import card_lifecycle
from genios_engine.platform import card_refusals
from genios_engine.platform import realtime
from genios_engine.platform.ids import new_id
from genios_engine.platform.logging import get_logger
from genios_engine.platform.self_identity import SelfIdentity
from genios_engine.reason.moments import guards as G
from genios_engine.reason.moments.common import iso
from genios_engine.contracts.reasoning import DecisionOutcome, OutputLane
from genios_engine.reason.output_lane import LaneChoice, route

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
#: The lane of what a post-pass observed (`signals.output_lane`, 0189; STEP-13 `yc2_w27_s13`
#: M36.C1.L-data.V0.U05, `03` F186) — no decision was made, so none is routed from one. A `verify`
#: situation is a discrepancy between two sources the owner settles (accept, keep): the router's own
#: conflict, a ruling and not more evidence. A `team` situation is something to watch.
_LANE = {"verify": route(outcome=DecisionOutcome.NO_ACTION, confidence_bp=0, conflict_open=True),
         "team": LaneChoice(OutputLane.MONITOR, "a situation of the team a post-pass observed; no "
                                                "decision was made, so it is shown to watch")}


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


_log = get_logger("genios.reason.team.emit")

#: Evidence that holds money: a key naming an amount, or a value carrying a currency.
_MONEY_KEYS = ("amount", "price", "invoice", "payment", "fee", "revenue", "budget", "cost")
#: A clipped text ends in an ellipsis (`clip`) — the quote before it is still the evidence's words.
_CLIPPED = re.compile(r"\s*(?:…|\.\.\.)\s*(?=”|\"|$)")


def _money_in(evidence) -> bool:
    flat = json.dumps(evidence, default=str, ensure_ascii=False).lower()
    return any(f'"{k}' in flat for k in _MONEY_KEYS) or any(s in flat for s in ("₹", "$", "€", "£"))


def refusals(*, headline: str, body: str | None, evidence, corpus: Iterable[str] = ()) -> tuple:
    """What `contracts/card_contract` refuses in a situation's card and moment, against its own evidence and what its
    writer composed its words from (`corpus`: the facts' values and the counts code computed — never the words)."""
    texts = [_CLIPPED.sub("", t) for t in (headline, body or "") if t]
    card = card_contract.CardText(headline=texts[0] if texts else "", situation=texts[-1] if texts else "",
                                  draft=None)
    return card_contract.check(card, us=SelfIdentity(),
                               corpus=[json.dumps(evidence, default=str, ensure_ascii=False),
                                       *(str(c) for c in corpus or () if c is not None)],
                               money_evidence=_money_in(evidence))


def _keep_refusals(engine, org_id: str, *, ref: str, refused, counts: dict | None) -> None:
    """Keep what the contract refused where `scripts/pipeline_health` reads it (`platform/card_refusals`, 0222).
    ⛔ Keeping it may never cost the emitter: unkept, it is counted `refusals_unkept` and logged."""
    try:
        with engine.begin() as c:
            card_refusals.record(c, org_id=org_id, writer=card_refusals.TEAM, ref=ref, refusals=refused)
    except Exception as exc:      # noqa: BLE001 — see the docstring
        if counts is not None:
            counts["refusals_unkept"] = counts.get("refusals_unkept", 0) + 1
        _log.warning("could not keep the card contract's refusal org=%s key=%s: %s", org_id, ref, exc)


def emit_situation(engine, card_store, org_id: str, *, kind: str, key: str, seat_id: str,
                   subject_node_ids, headline: str, body: str | None, actions, evidence,
                   priority: str = "high", ttl_seconds: int, digest: str,
                   capability_id: str | None = None, now: datetime | None = None,
                   expires_at: datetime | None = None, counts: dict | None = None,
                   corpus: Iterable[str] = ()) -> tuple[str, str] | None:
    """See the module docstring. `capability_id`, `now` and `expires_at` are optional extensions
    (defaults: `<kind>.situation`, the wall clock, now + 7 d for the card); `counts` gathers what the
    card contract refused; `corpus` is what the words were composed from beyond the evidence (`refusals`)."""
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
    refused = refusals(headline=headline, body=body, evidence=evidence, corpus=corpus)
    if refused:
        for r in refused:
            if counts is not None:
                counts[f"refused_contract:{r.rule}"] = counts.get(f"refused_contract:{r.rule}", 0) + 1
        _log.warning("team card refused by the card contract org=%s key=%s: %s", org_id, key,
                     "; ".join(f"{r.rule}: {r.found}" for r in refused))
        _keep_refusals(engine, org_id, ref=f"{kind}:{key}", refused=refused, counts=counts)
        return None
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


def close_stale(engine, org_id: str, *, kind: str, prefixes: tuple[str, ...],
                keep_keys: set[str], now: datetime | None = None) -> int:
    """Situations of `kind` whose key starts with one of `prefixes` and that the pass did NOT
    produce this run no longer hold (the owner is back, the promise was kept, the recipient
    changed): state → closed, and their card — if nobody has decided anything about it yet —
    resolved with a `situation_cleared` event. Returns situations closed."""
    now = now or datetime.now(timezone.utc)
    closed = 0
    with engine.begin() as c:
        rows = c.execute(text(
            "select key, card_id from team_situations where org_id = :o and kind = :k "
            "and state = 'open' for update"), {"o": org_id, "k": kind}).all()
        for r in rows:
            if r.key in keep_keys or not r.key.startswith(prefixes):
                continue
            c.execute(text("update team_situations set state = 'closed', last_at = :now "
                           "where org_id = :o and kind = :k and key = :key"),
                      {"o": org_id, "k": kind, "key": r.key, "now": now})
            closed += 1
            if r.card_id:
                # STEP-16 (`yc2_w27_s16` M47.C1.L-data.V0.U01): through the one writer of `resolved`.
                card_lifecycle.resolve_cards(c, org_id=org_id, cause=card_lifecycle.SITUATION_CLEARED,
                                             card_ids=[r.card_id], evidence={"situation_key": r.key}, at=now,
                                             states=("built", "queued", "surfaced", "snoozed"))
    return closed


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
            # The lane rides on the card the surface reads (M36.C1.L-data.V0.U07): a lane that
            # stops at `signals` reached nobody (0190).
            "output_lane = :lane, lane_reason = :lane_reason, "
            "builder_version = :bver where card_id = :id and org_id = :o "
            "and state = any(:refreshable) and resolved_at is null returning signal_id"),
            {"seat": seat_id, "band": band, "head": head, "sit": sit, "score": score,
             "act": card_actions, "why": why, "exp": expires_at, "bver": BUILDER_VERSION,
             "lane": _LANE[kind].lane.value, "lane_reason": _LANE[kind].reason,
             "id": held_card_id, "o": org_id, "refreshable": list(_REFRESHABLE)}).first()
        if refreshed is not None:
            c.execute(text(
                "update signals set evidence = cast(:ev as jsonb), score = :score, "
                "eval_time = :now where signal_id = :sig and org_id = :o"),
                {"ev": why, "score": score, "now": now, "sig": refreshed.signal_id, "o": org_id})
            # the words ride on the event: a card refreshed in place otherwise loses what it said
            _log_card_event(c, held_card_id, org_id, "card.rebuilt", capability,
                            {"digest": digest, "builder_version": BUILDER_VERSION,
                             "headline": head, "situation": sit,
                             # STEP-14 fix (the crosscheck's finding 9): its words as every card's events keep them.
                             "words": {"headline": head, "situation": sit}})
            return held_card_id
        # The user SNOOZED the previous card: its words stay as answered, but it must not wake
        # later beside the new generation saying something no longer true — resolve it.
        card_lifecycle.resolve_cards(c, org_id=org_id, cause=card_lifecycle.SUPERSEDED, card_ids=[held_card_id],
                                     evidence={"digest": digest}, at=now, states=("snoozed",))
    # First emission, or the user already decided the previous card: a new generation.
    signal_id = "sig_team_" + _h(org_id, kind, key, digest)[:28]
    c.execute(text(
        "insert into signals (signal_id, org_id, rule_id, rule_version, level, subject_node_id, "
        "score, score_inputs, reason_code, evidence, status, eval_time, capability_id, "
        "capability_version, output_lane, lane_reason) values (:sig, :o, :rule, 1, 'observation', "
        ":subj, :score, '{}'::jsonb, :reason, cast(:ev as jsonb), 'open', :now, :rule, '1', "
        ":lane, :lane_reason) "
        "on conflict (signal_id) do nothing"),
        {"sig": signal_id, "o": org_id, "rule": capability,
         "subj": subjects[0] if subjects else key, "score": score, "reason": kind, "ev": why,
         "now": now, "lane": _LANE[kind].lane.value, "lane_reason": _LANE[kind].reason})
    card_id = new_id("card")
    row = c.execute(text(
        "insert into cards (card_id, signal_id, org_id, assignee, domain, level, urgency_band, "
        "headline, situation, score, score_block, actions, why, context_tags, render_mode, "
        "template_version, capability_key, capability_version, builder_version, output_lane, "
        "lane_reason, state, expires_at) values (:id, :sig, :o, :seat, :dom, 'observation', :band, "
        ":head, :sit, :score, '{}'::jsonb, cast(:act as jsonb), cast(:why as jsonb), '{}', "
        "'template', :tv, :cap, '1', :bver, :lane, :lane_reason, 'queued', :exp) "
        "on conflict (signal_id) do nothing "
        "returning card_id"),
        {"id": card_id, "sig": signal_id, "o": org_id, "seat": seat_id, "dom": kind,
         "band": band, "head": head, "sit": sit, "score": score, "act": card_actions,
         "why": why, "tv": f"{capability}@1", "cap": capability, "bver": BUILDER_VERSION,
         "lane": _LANE[kind].lane.value, "lane_reason": _LANE[kind].reason,
         "exp": expires_at}).first()
    if row is None:        # the same generation already carded (a retried emit)
        return c.execute(text("select card_id from cards where signal_id = :s and org_id = :o"),
                         {"s": signal_id, "o": org_id}).scalar()
    _log_card_event(c, card_id, org_id, "card.created", capability,
                    {"band": band, "render_mode": "template", "situation_key": key,
                     "digest": digest, "headline": head, "situation": sit,
                     "words": {"headline": head, "situation": sit}})
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
